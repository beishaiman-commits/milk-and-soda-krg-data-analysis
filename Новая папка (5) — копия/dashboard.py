import re
import altair as alt
import pandas as pd
import streamlit as st

FILE = "tobaza.csv"

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


@st.cache_data
def load_data():
    df = pd.read_csv(FILE, sep=";", encoding="utf-8-sig")
    df["Цена"] = pd.to_numeric(df["Цена"], errors="coerce")
    df["Дата"] = pd.to_datetime(df["Дата"], errors="coerce")
    df = df.dropna(subset=["Цена", "Дата"])
    df = df[df["Цена"] > 0]
    df = df.drop_duplicates(subset=["Магазин", "Товар", "Дата"], keep="last")
    df["норм"] = df["Товар"].apply(normalize)
    return df


def basket_table(df):
    parts = []
    for item, (include, exclude) in BASKET.items():
        sub = df[df["норм"].apply(lambda n: matches(n, include, exclude))]
        if sub.empty:
            continue
        cheapest = sub.groupby(["Дата", "Магазин"])["Цена"].min().reset_index()
        cheapest["Позиция"] = item
        parts.append(cheapest)
    if not parts:
        return None
    table = pd.concat(parts).pivot_table(index=["Дата", "Позиция"], columns="Магазин", values="Цена")
    table = table.dropna()
    return table if not table.empty else None



st.set_page_config(page_title="Сравнение цен", layout="wide")
st.title("Сравнение цен в магазинах")

try:
    df = load_data()
except FileNotFoundError:
    st.error(f"Файл {FILE} не найден. Положи его в папку с dashboard.py и запусти парсер.")
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

tab1, tab2, tab3, tab4 = st.tabs(["Средние цены", "Корзина", "История товара", "Данные"])


with tab1:
    if view.empty:
        st.info("Нет данных под выбранные фильтры.")
    else:
        mean = view.groupby(["Категория", "Магазин"])["Цена"].mean().unstack()
        st.subheader("Средняя цена по категориям (тг)")

        # столбики магазинов рядом (а не стопкой), чтобы их можно было сравнить
        long = mean.reset_index().melt(id_vars="Категория", var_name="Магазин", value_name="Средняя цена")
        bars = alt.Chart(long).mark_bar().encode(
            x=alt.X("Категория:N", title=None, axis=alt.Axis(labelAngle=0)),
            xOffset="Магазин:N",
            y=alt.Y("Средняя цена:Q", title="Цена (тг)"),
            color=alt.Color("Магазин:N", title="Магазин"),
            tooltip=["Категория", "Магазин", alt.Tooltip("Средняя цена:Q", format=".1f")],
        )
        labels = bars.mark_text(dy=-8).encode(text=alt.Text("Средняя цена:Q", format=".0f"))
        st.altair_chart(bars + labels, width="stretch")

        st.dataframe(mean.round(1))


with tab2:
    st.subheader("Корзина: самая дешёвая цена по каждой позиции")
    table = basket_table(df)
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
            st.success(f"За последний день корзина в «{cheaper}» дешевле на {diff:.1f}%")
        st.caption(f"Позиций в сравнении: {table.index.get_level_values('Позиция').nunique()}. "
                   "Берётся самый дешёвый товар под правило, а не одинаковый товар.")
        st.line_chart(totals)
        with st.expander("Показать цены по позициям"):
            st.dataframe(table.round(0))

with tab3:
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
            hist = one.pivot_table(index="Дата", columns="Магазин", values="Цена")
            st.line_chart(hist)
            if hist.shape[0] < 2:
                st.caption("Пока есть данные только за один день, динамики не видно.")

with tab4:
    st.subheader("Все данные")
    shown = view.drop(columns=["норм"])
    st.dataframe(shown, width="stretch")
    st.download_button("Скачать CSV", shown.to_csv(index=False, sep=";").encode("utf-8-sig"),file_name="prices_filtered.csv", mime="text/csv")
#    streamlit run dashboard.py