import json
import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DIR = Path(__file__).resolve().parent
FILE = DIR / "tobaza.csv"
FAV_FILE = DIR / "favorites.json"

BASKET = {
    "Молоко":             (["молок"], ["сгущ", "сух", "шоколад", "коктейл", "кокос", "йогурт"]),
    "Кефир":              (["кефир"], []),
    "Сметана":            (["сметан"], []),
    "Творог":             (["творог"], ["сырок", "глазир"]),
    "Йогурт":             (["йогурт"], []),
    "Сливки":             (["сливк"], []),
    "Сыр":                (["сыр"], ["сырок", "сырн", "сырник", "сырков"]),
    "Масло сливочное":    (["масло", "сливоч"], []),
    "Масло подсолнечное": (["масло", "подсолн"], []),
    "Вода":               (["вода"], ["сладк"]),
    "Сок":                (["сок"], []),
    "Чай":                (["чай"], ["чайник", "чайн"]),
    "Квас":               (["квас"], []),
    "Лимонад":            (["лимонад"], []),
    "Морс":               (["морс"], []),
    "Кисель":             (["кисел"], []),
}


def normalize(name):
    name = str(name).lower()
    name = name.replace("ё", "е")
    name = re.sub(r"(\d)([а-я])", r"\1 \2", name)
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def has_word(norm_name, w):
    if " " in w:
        return w in norm_name
    return any(token.startswith(w) for token in norm_name.split())


def matches(norm_name, include, exclude):
    return all(has_word(norm_name, w) for w in include) and not any(has_word(norm_name, w) for w in exclude)


UNITS = r"(кг|гр|г|литр[а-я]*|мл|л)"
MULTI_RE = re.compile(r"(\d+)\s*[xх*]\s*(\d+(?:\.\d+)?)\s*" + UNITS + r"(?![а-я])")
SINGLE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*" + UNITS + r"(?![а-я])(?:\s*[xх*]\s*(\d+)(?![\d.]))?")


def extract_unit(name):
    """Возвращает (единица, количество): ('кг', 0.2) или ('л', 1.5). Если объёма нет, (None, None)."""
    s = str(name).lower().replace("ё", "е").replace(",", ".")
    m = MULTI_RE.search(s)
    if m:
        count, size, unit = int(m.group(1)), float(m.group(2)), m.group(3)
    else:
        m = SINGLE_RE.search(s)
        if not m:
            return (None, None)
        size, unit = float(m.group(1)), m.group(2)
        count = int(m.group(3)) if m.group(3) else 1

    if unit == "кг":
        kind, amount = "кг", size
    elif unit in ("г", "гр"):
        kind, amount = "кг", size / 1000
    elif unit == "мл":
        kind, amount = "л", size / 1000
    else:
        kind, amount = "л", size
    total = amount * count
    return (kind, total) if total > 0 else (None, None)

@st.cache_data
def load_data():
    df = pd.read_csv(FILE, sep=";", encoding="utf-8-sig")
    df["Цена"] = pd.to_numeric(df["Цена"], errors="coerce")
    df["Дата"] = pd.to_datetime(df["Дата"], errors="coerce")
    df = df.dropna(subset=["Цена", "Дата"])
    df = df[df["Цена"] > 0]
    df = df.drop_duplicates(subset=["Магазин", "Товар", "Дата"], keep="last")
    df["норм"] = df["Товар"].apply(normalize)

    units = df["Товар"].apply(extract_unit)
    df["Ед."] = units.apply(lambda u: u[0])
    df["Объём"] = pd.to_numeric(units.apply(lambda u: u[1]), errors="coerce")
    df["Цена за ед."] = df["Цена"] / df["Объём"]
    return df

@st.cache_data
def basket_table(df, agg):
    parts, dropped = [], []
    for item, (include, exclude) in BASKET.items():
        sub = df[df["норм"].apply(lambda n: matches(n, include, exclude))]
        sub = sub.dropna(subset=["Цена за ед."])
        if sub.empty:
            dropped.append(item)
            continue
        unit = sub["Ед."].mode().iloc[0]          
        sub = sub[sub["Ед."] == unit]
        grouped = sub.groupby(["Дата", "Магазин"])["Цена за ед."].agg(agg).reset_index()
        grouped["Позиция"] = f"{item} (тг/{unit})"
        parts.append(grouped)
    if not parts:
        return None, dropped
    table = pd.concat(parts).pivot_table(index=["Дата", "Позиция"], columns="Магазин", values="Цена за ед.")
    table = table.dropna()
    return (table if not table.empty else None), dropped


def safe_label(text):
    """Подпись линии графика: двоеточия, точки и скобки ломают Altair, поэтому заменяем их."""
    return re.sub(r"[:.\[\]\\'\"]", lambda m: {":": " -", ".": ","}.get(m.group(), " "), str(text))



def load_favs():
    try:
        return json.loads(FAV_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_favs(favs):
    FAV_FILE.write_text(json.dumps(favs, ensure_ascii=False, indent=2), encoding="utf-8")


def add_fav(store, product):
    favs = load_favs()
    item = {"Магазин": store, "Товар": product}
    if item not in favs:
        favs.append(item)
        save_favs(favs)


def remove_fav(store, product):
    favs = [f for f in load_favs() if not (f["Магазин"] == store and f["Товар"] == product)]
    save_favs(favs)


st.set_page_config(page_title="Сравнение цен", layout="wide")
st.title("Сравнение цен в магазинах")

try:
    df = load_data()
except FileNotFoundError:
    st.error(f"Файл {FILE.name} не найден. Положи его в папку с dashboard.py и запусти парсер.")
    st.stop()

if df.empty:
    st.warning("В файле нет корректных данных.")
    st.stop()

st.sidebar.header("Фильтры")
stores = sorted(df["Магазин"].unique())
cats = sorted(df["Категория"].unique())
sel_stores = st.sidebar.multiselect("Магазины", stores, default=stores)
sel_cats = st.sidebar.multiselect("Категории", cats, default=cats)
view = df[df["Магазин"].isin(sel_stores) & df["Категория"].isin(sel_cats)]


c1, c2, c3 = st.columns(3)
c1.metric("Строк данных", len(view))
c2.metric("Дней сбора", view["Дата"].nunique())
c3.metric("Уникальных товаров", view["Товар"].nunique())

tab_avg, tab_basket, tab_change, tab_hist, tab_fav, tab_data = st.tabs(
    ["Средние цены", "Корзина", "Что изменилось", "История товара", "⭐ Избранное", "Данные"]
)


with tab_avg:
    if view.empty:
        st.info("Нет данных под выбранные фильтры.")
    else:
        kind = st.radio("Показатель", ["Медиана", "Среднее"], horizontal=True,
                        help="Медиана устойчива к выбросам (дорогие и бракованные товары), среднее нет.")
        agg = "median" if kind == "Медиана" else "mean"
        stat = view.groupby(["Категория", "Магазин"])["Цена"].agg(agg).unstack()

        st.subheader(f"{kind} цена по категориям (тг)")
        long = stat.reset_index().melt(id_vars="Категория", var_name="Магазин", value_name="Цена")
        bars = alt.Chart(long).mark_bar().encode(
            x=alt.X("Категория:N", title=None, axis=alt.Axis(labelAngle=0)),
            xOffset="Магазин:N",
            y=alt.Y("Цена:Q", title="Цена (тг)"),
            color=alt.Color("Магазин:N", title="Магазин"),
            tooltip=["Категория", "Магазин", alt.Tooltip("Цена:Q", format=".1f")],
        )
        labels = bars.mark_text(dy=-8).encode(text=alt.Text("Цена:Q", format=".0f"))
        st.altair_chart(bars + labels, width="stretch")
        st.dataframe(stat.round(1))

        st.subheader("Как распределены цены")
        st.caption("Ящик показывает, где лежит половина цен (от 25% до 75%), линия внутри это медиана. "
                   "Шкала логарифмическая, чтобы дорогие товары не сплющивали картинку.")
        box = alt.Chart(view[["Категория", "Магазин", "Цена"]]).mark_boxplot(extent="min-max").encode(
            x=alt.X("Магазин:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Цена:Q", scale=alt.Scale(type="log"), title="Цена (тг)"),
            color=alt.Color("Магазин:N", legend=None),
            column=alt.Column("Категория:N", title=None),
        )
        st.altair_chart(box)

with tab_basket:
    st.subheader("Корзина: цена за 1 кг или 1 л")
    mode = st.radio("Как сравнивать товары внутри позиции",
                    ["Медиана цены за единицу", "Самый дешёвый товар"], horizontal=True)
    agg_b = "median" if mode.startswith("Медиана") else "min"

    table, dropped = basket_table(df, agg_b)
    if table is None:
        st.info("Не нашлось позиций, которые есть в обоих магазинах. Подгони слова BASKET в dashboard.py.")
    else:
        totals = table.groupby("Дата").sum()
        cols = list(totals.columns)
        if len(cols) == 2:
            a, b = cols
            last = totals.iloc[-1]
            cheaper = b if last[b] < last[a] else a
            diff = abs(last[a] - last[b]) / max(last[a], last[b]) * 100
            st.success(f"За последний день набор в «{cheaper}» дешевле на {diff:.1f}%")

            last_date = table.index.get_level_values("Дата").max()
            day = table.xs(last_date, level="Дата")
            wins_a = int((day[a] < day[b]).sum())
            wins_b = int((day[b] < day[a]).sum())
            st.write(f"По позициям: «{a}» дешевле в {wins_a}, «{b}» дешевле в {wins_b} из {len(day)}.")

        st.caption("Набор = по 1 кг или 1 л каждой позиции. Цена считается за единицу из объёма в названии, "
                   "поэтому маленькие и большие упаковки сравнимы.")
        if dropped:
            st.caption("Не вошли (нет объёма в названии или нет в данных): " + ", ".join(dropped))
        st.line_chart(totals)
        with st.expander("Показать цены по позициям"):
            st.dataframe(table.round(0))
with tab_change:
    st.subheader("Что дорожало и дешевело")
    dates = sorted(view["Дата"].dt.date.unique())
    if len(dates) < 2:
        st.info("Нужно хотя бы два дня данных.")
    else:
        d1, d2 = st.columns(2)
        d_from = d1.selectbox("С даты", dates, index=0)
        d_to = d2.selectbox("По дату", dates, index=len(dates) - 1)
        if d_from >= d_to:
            st.warning("Начальная дата должна быть раньше конечной.")
        else:
            was = view[view["Дата"].dt.date == d_from].set_index(["Магазин", "Товар"])["Цена"]
            now = view[view["Дата"].dt.date == d_to].set_index(["Магазин", "Товар"])["Цена"]
            ch = pd.concat([was.rename("Было"), now.rename("Стало")], axis=1, join="inner").reset_index()
            ch["Изменение, %"] = (ch["Стало"] - ch["Было"]) / ch["Было"] * 100

            if ch.empty:
                st.info("Нет товаров, которые есть в обе даты.")
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("Подорожало", int((ch["Изменение, %"] > 0).sum()))
                m2.metric("Подешевело", int((ch["Изменение, %"] < 0).sum()))
                m3.metric("Без изменений", int((ch["Изменение, %"] == 0).sum()))

                st.write("Среднее изменение цены по магазинам, %:")
                st.dataframe(ch.groupby("Магазин")["Изменение, %"].mean().round(2).to_frame())

                left, right = st.columns(2)
                with left:
                    st.write("Сильнее всего подорожали")
                    st.dataframe(ch.nlargest(10, "Изменение, %").round(1), hide_index=True)
                with right:
                    st.write("Сильнее всего подешевели")
                    st.dataframe(ch.nsmallest(10, "Изменение, %").round(1), hide_index=True)

with tab_hist:
    st.subheader("Как менялась цена товара")
    query = st.text_input("Поиск по названию (например: кефир)")
    if query:
        found = view[view["норм"].str.contains(normalize(query), na=False)]
        names = sorted(found["Товар"].unique())[:200]
        if not names:
            st.info("Ничего не найдено.")
        else:
            product = st.selectbox("Товар", names)
            one = found[found["Товар"] == product]

            col = "Цена"
            if one["Цена за ед."].notna().any():
                choice = st.radio("Показатель", ["Цена", "Цена за кг/л"], horizontal=True)
                col = "Цена" if choice == "Цена" else "Цена за ед."
            hist = one.pivot_table(index="Дата", columns="Магазин", values=col)
            st.line_chart(hist)
            if hist.shape[0] < 2:
                st.caption("Пока есть данные только за один день, динамики не видно.")

            for i, store in enumerate(sorted(one["Магазин"].unique())):
                st.button(f"⭐ В избранное: {store}", key=f"fav_hist_{i}",
                          on_click=add_fav, args=(store, product))
with tab_fav:
    st.subheader("Товары под наблюдением")

    with st.expander("Добавить товар в избранное", expanded=not load_favs()):
        q = st.text_input("Поиск товара", key="fav_query")
        if q:
            res = df[df["норм"].str.contains(normalize(q), na=False)]
            pairs = res[["Магазин", "Товар"]].drop_duplicates().sort_values(["Магазин", "Товар"]).head(200)
            options = {f"{s} — {p}": (s, p) for s, p in zip(pairs["Магазин"], pairs["Товар"])}
            if not options:
                st.info("Ничего не найдено.")
            else:
                chosen = st.selectbox("Товар", list(options), key="fav_choice")
                st.button("⭐ Добавить", key="fav_add", on_click=add_fav, args=options[chosen])

    favs = load_favs()
    if not favs:
        st.info("Пока ничего не выбрано. Найди товар выше или во вкладке «История товара».")
    else:
        series, columns = [], st.columns(3)
        for i, fav in enumerate(favs):
            s, p = fav["Магазин"], fav["Товар"]
            h = df[(df["Магазин"] == s) & (df["Товар"] == p)].sort_values("Дата")
            with columns[i % 3]:
                if h.empty:
                    st.caption(f"{p} ({s}): нет данных")
                else:
                    last_price = h["Цена"].iloc[-1]
                    delta = None
                    if len(h) > 1:
                        delta = f"{last_price - h['Цена'].iloc[-2]:+.0f} ₸ к прошлому дню"
                    st.metric(f"{p} ({s})", f"{last_price:.0f} ₸", delta=delta, delta_color="inverse",
                              help=f"Минимум {h['Цена'].min():.0f} ₸, максимум {h['Цена'].max():.0f} ₸, "
                                   f"наблюдений: {len(h)}")
                    h = h.assign(Метка=safe_label(f"{s} - {p}"))
                    series.append(h[["Дата", "Метка", "Цена"]])
                st.button("Убрать", key=f"fav_rm_{i}", on_click=remove_fav, args=(s, p))

        if series:
            chart_mode = st.radio("График", ["Цена, тг", "Изменение, % от первой цены"], horizontal=True)
            pivot = pd.concat(series).pivot_table(index="Дата", columns="Метка", values="Цена")
            if chart_mode.startswith("Изменение"):
                pivot = pivot / pivot.bfill().iloc[0] * 100 - 100
            st.line_chart(pivot)
            if pivot.shape[0] < 2:
                st.caption("Пока данных за один день, график появится после следующих запусков парсера.")

with tab_data:
    st.subheader("Все данные")
    shown = view.drop(columns=["норм", "Ед.", "Объём"])
    st.dataframe(shown, width="stretch")
    st.download_button("Скачать CSV", shown.to_csv(index=False, sep=";").encode("utf-8-sig"),
    file_name="prices_filtered.csv", mime="text/csv")
#    streamlit run dashboard.py