import re
import pandas as pd
import matplotlib.pyplot as plt

FILE = "tobaza.csv"


BASKET = {
    "Молоко":            (["молок"], ["сгущ", "сух", "шоколад", "коктейл", "кокос", "йогурт"]),
    "Кефир":             (["кефир"], []),
    "Сметана":           (["сметан"], []),
    "Творог":            (["творог"], ["сырок", "глазир"]),
    "Йогурт":            (["йогурт"], []),
    "Сливки":            (["сливк"], []),
    "Сыр":               (["сыр"], ["сырок", "сырн", "сырник", "сырков"]),
    "Масло сливочное":   (["масло", "сливоч"], []),
    "Масло подсолнечное":(["масло", "подсолн"], []),
    "Вода":              (["вода"], ["сладк"]),
    "Сок":               (["сок"], []),
    "Чай":               (["чай"], ["чайник", "чайн"]),
    "Квас":              (["квас"], []),
    "Лимонад":           (["лимонад"], []),
    "Морс":              (["морс"], []),
    "Кисель":            (["кисел"], []),
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

df = pd.read_csv(FILE, sep=";", encoding="utf-8-sig")
df["Цена"] = pd.to_numeric(df["Цена"], errors="coerce")
df["Дата"] = pd.to_datetime(df["Дата"], errors="coerce")
df = df.dropna(subset=["Цена", "Дата"])
df = df[df["Цена"] > 0]
df = df.drop_duplicates(subset=["Магазин", "Товар", "Дата"], keep="last")
df["норм"] = df["Товар"].apply(normalize)

print(" ОБЩАЯ ИНФОРМАЦИЯ ")
print("Строк в таблице:", len(df))
print("Дней сбора данных:", df["Дата"].nunique())
print(df.groupby("Магазин").size())

print("\n=== СРЕДНЯЯ ЦЕНА: магазин x категория ===")
mean_prices = df.groupby(["Категория", "Магазин"])["Цена"].mean().unstack()
print(mean_prices.round(1))

mean_prices.plot(kind="bar", figsize=(8, 5))
plt.title("Средняя цена по категориям")
plt.ylabel("Цена (тг)")
plt.xticks(rotation=0)
plt.tight_layout()
plt.savefig("chart_mean_prices.png")
plt.show()

parts = []
for item, (include, exclude) in BASKET.items():
    sub = df[df["норм"].apply(lambda n: matches(n, include, exclude))]
    if sub.empty:
        print(f"Позиция '{item}' не найдена ни в одном магазине")
        continue
    cheapest = sub.groupby(["Дата", "Магазин"])["Цена"].min().reset_index()
    cheapest["Позиция"] = item
    parts.append(cheapest)

if not parts:
    print("\nКорзина пустая: подгони слова в BASKET под свои данные.")
else:
    basket = pd.concat(parts)
    table = basket.pivot_table(index=["Дата", "Позиция"], columns="Магазин", values="Цена")
    table = table.dropna() 

    print("\n=== ПОЗИЦИИ КОРЗИНЫ (самая дешёвая в каждом магазине) ===")
    print(table.round(0))

    if table.empty:
        print("Нет позиций, найденных сразу в двух магазинах.")
    else:
        totals = table.groupby("Дата").sum()
        print("\n=== СУММА КОРЗИНЫ ПО ДНЯМ ===")
        print(totals.round(0))

        stores = list(totals.columns)
        if len(stores) == 2:
            a, b = stores
            last = totals.iloc[-1]
            cheaper = b if last[b] < last[a] else a
            diff = abs(last[a] - last[b]) / max(last[a], last[b]) * 100
            print(f"\nВывод: за последний день корзина в '{cheaper}' "
                  f"дешевле на {diff:.1f}%")

        totals.plot(marker="o", figsize=(8, 5))
        plt.title("Стоимость корзины по дням")
        plt.ylabel("Сумма (тг)")
        plt.xlabel("Дата")
        plt.tight_layout()
        plt.savefig("chart_basket.png")
        plt.show()
