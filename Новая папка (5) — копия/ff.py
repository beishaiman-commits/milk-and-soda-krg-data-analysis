from datetime import date
import csv
import json
import re
import requests
from bs4 import BeautifulSoup
import time

d = date.today().isoformat()
baza = []

print("Запуск общего сбора цен...................................")

korzina_urls = [
    (name, f"https://api.korzinavdom.kz/client/showcases?page={p}&size=50&categoryNumber={cat}")
    for name, cat in [("Напитки", 9), ("Молочные продукты", 3)]
    for p in range(15)
]

h_api = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0.0.0",
    "Accept": "application/json, text/plain, */*"
}

for kat_name, url in korzina_urls:
    print(f"Лезем в Корзину за категорией: {kat_name}...................................")
    try:
        r = requests.get(url, headers=h_api, timeout=20)
        if r.status_code == 200:
            items = r.json().get('data', {}).get('page', {}).get('content', [])
            for it in items:
                nam = it.get('productName')
                prc = it.get('productPrice', {}).get('current')
                if nam and prc is not None:
                    baza.append({
                        "магаз": "Корзина",
                        "категория": kat_name,
                        "товар": nam.strip(),
                        "цена": float(prc),
                        "дата": d
                    })
        else:
            print(f"Статус {r.status_code} для {kat_name}")
    except Exception as err:
        print(f"Ошибка с Корзиной ({kat_name}): {err}")
    time.sleep(1)
ayan_cats = [
    ("Напитки", "https://ayanmarket.kz/shop/napitki-20"),
    ("Молочные продукты", "https://ayanmarket.kz/shop/molochnye-produkty-syr-i-yaytsa-19")
]

ayan_urls = [
    (name, base if p == 1 else f"{base}?page={p}")
    for name, base in ayan_cats
    for p in range(1, 15)
]

h_html = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0.0.0"
}


def parse_price(card):
    text = card.get_text(" ", strip=True).replace("\xa0", " ")
    m = re.search(r"(\d[\d ]*)\s*₸", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(" ", ""))
    except ValueError:
        return None


for kat_name, url in ayan_urls:
    print(f"Лезем в Аян за категорией: {kat_name}.............................")
    try:
        r = requests.get(url, headers=h_html, timeout=20)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            seen = set()

            for a in soup.select("a.block[title]"):
                name = a["title"].strip()
                if name.isupper():
                    name = " ".join(w.capitalize() for w in name.split())
                href = a.get("href", "")
                if not name or href in seen:
                    continue
                card = a
                for _ in range(6):
                    if card is None or "₸" in card.get_text():
                        break
                    card = card.parent
                if card is None:
                    continue
                price_val = parse_price(card)
                if price_val and price_val > 0:
                    seen.add(href)
                    baza.append({
                        "магаз": "Аян Маркет",
                        "категория": kat_name,
                        "товар": name,
                        "цена": price_val,
                        "дата": d
                    })
            print(f"  найдено: {len(seen)}")
        else:
            print(f"Статус {r.status_code} для {kat_name}")
    except Exception as err:
        print(f"Ошибка с Аяном ({kat_name}): {err}")

print(f"Всего собрано со всех магазинов: {len(baza)}.")

if baza:
    with open("tobaza.csv", "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if f.tell() == 0:
            w.writerow(["Магазин", "Категория", "Товар", "Цена", "Дата"])
        for x in baza:
            w.writerow([x["магаз"], x["категория"], x["товар"], x["цена"], x["дата"]])
    print("Сохранили всё в tobaza.csv")

    with open("tobaza.json", "a", encoding="utf-8") as f_json:
        json.dump(baza, f_json, ensure_ascii=False, indent=2)
    print("И в json тоже кинули")
else:
    print("Пусто... ничего не собралось :(")
