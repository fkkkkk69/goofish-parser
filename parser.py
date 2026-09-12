import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import telebot

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
WORKER_URL = os.environ["WORKER_URL"]
API_SECRET = os.environ["API_SECRET"]
STATE_FILE = "state.json"
SEEN_FILE = "seen.json"

bot = telebot.TeleBot(TG_BOT_TOKEN)

# Полный список ключевых слов для поиска на Goofish (объединение всех подписчиков)
KEYWORDS = [
    "undercover",
    "number nine",
    "hysteric glamour",
    "rick owens",
    "raf simons",
    "jeremy scott",
    "walter van beirendonck",
    "424",
    "gucci",
    "prada",
    "helmut lang",
    "moschino",
    "junya watanabe",
    "diesel",
    "balmain",
    "ppfm",
    "tornado mart",
    "vivienne westwood",
    "c2h4",
    "undercoverism",
    "maison margiela",
    "yohji yamamoto",
    "y-3",
    "rick owens drkshdw",
    "boris bidjan saberi",
    "carol christian poell",
    "kiko kostadinov",
    "issey miyake",
    "junya watanabe man",
    "comme des garcons",
    "john galliano",
    "jean paul gaultier",
    "amiri",
    "stone island",
    "bernhard willhelm",
    "hussein chalayan",
    "ann demeulemeester",
    "dries van noten",
    "dirk bikkembergs",
    "marina yee",
    "craig green",
    "post archive faction",
    "kanghyuk",
    "andersson bell",
    "hyein seo",
    "jil sander",
    "lemaire",
    "carpe diem",
    "m.a+",
    "label under construction",
    "layer-0",
    "julius",
    "devoa",
    "ziggy chen",
    "uma wang",
    "inaisce",
    "guidi",
    "a1923",
    "individual sentiments",
    "obscur",
    "leon emanuel blanck",
    "thom krom",
    "off-white",
    "balenciaga",
    "vetements",
    "chrome hearts",
    "gallery dept",
    "palm angels",
    "casablanca",
    "rhude",
    "givenchy",
    "dior homme",
    "louis vuitton",
    "heron preston",
    "fear of god",
    "yeezy",
    "sp5der",
    "denim tears",
    "hellstar",
    "corteiz",
    "c.p. company",
    "nike",
    "arcteryx",
    "moncler",
    "canada goose",
    "trapstar",
    "syna world",
    "benjart",
    "hoodrich",
    "burberry",
    "lacoste",
    "the north face",
    "oakley",
    "salomon",
    "asics",
    "saint laurent",
    "ysl",
    "dior",
    "the kooples",
    "allsaints",
    "zadig & voltaire",
    "american apparel",
    "urban outfitters",
    "cheap monday",
    "unif",
    "marc jacobs",
    "tripp nyc",
    "lip service",
    "dr. martens",
    "converse",
    "juicy couture",
    "von dutch",
    "ed hardy",
    "kmiri",
    "lgb",
    "20471120",
    "chanel",
    "if six was nine",
]

MAX_WORKERS = 3  # Параллельный поиск вместо последовательного (было DELAY_BETWEEN_KEYWORDS=5 сек между брендами)


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def get_subscribers():
    try:
        r = requests.get(f"{WORKER_URL}/subscribers", headers={"X-API-Key": API_SECRET}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Не удалось получить подписчиков: {e}")
        return []


def search_keyword(keyword):
    try:
        result = subprocess.run(
            [
                "xianyu", "search", keyword,
                "--format", "json",
                "--storage-state", STATE_FILE,
                "--pages", "1",
            ],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"Ошибка поиска '{keyword}': {result.stderr[:300]}")
            return []
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Исключение при поиске '{keyword}': {e}")
        return []


def matches(item, sub):
    raw_price = item.get("price", 0)
    try:
        price = float(str(raw_price).replace(",", "").strip())
    except (ValueError, TypeError):
        price = 0
    name_lower = (item.get("title") or "").lower()
    keyword = item["keyword"]

    brands = [b.lower() for b in sub.get("brands", [])]
    if not brands:
        return False

    matched_brand = None
    for b in brands:
        if b in keyword or b in name_lower:
            matched_brand = b
            break
    if matched_brand is None:
        return False

    brand_prices = sub.get("brand_prices") or {}
    price_range = brand_prices.get(matched_brand)
    if price_range is None:
        price_range = sub.get("global_price")

    if price_range:
        if price < price_range.get("min", 0) or price > price_range.get("max", 9999999):
            return False

    return True


def notify(chat_id, item, keyword):
    text = (
        f"🆕 Новый товар на Goofish!\n\n"
        f"*{item.get('title', '')}*\n"
        f"💴 ¥{item.get('price', '?')}\n"
        f"🔍 Запрос: {keyword}\n"
        f"🔗 [Открыть]({item.get('link', '')})"
    )
    try:
        bot.send_message(int(chat_id), text, parse_mode="Markdown")
    except Exception as e:
        print(f"Не удалось отправить {chat_id}: {e}")


def main():
    seen = load_seen()
    first_run = len(seen) == 0
    new_items = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_keyword = {executor.submit(search_keyword, kw): kw for kw in KEYWORDS}
        for future in as_completed(future_to_keyword):
            keyword = future_to_keyword[future]
            try:
                items = future.result()
            except Exception as e:
                print(f"Ошибка потока для '{keyword}': {e}")
                items = []
            for item in items:
                item_id = item.get("item_id")
                if item_id and item_id not in seen:
                    seen.add(item_id)
                    if not first_run:
                        new_items.append({
                            "id": item_id,
                            "title": item.get("title", ""),
                            "price": item.get("price", 0),
                            "link": item.get("link", ""),
                            "keyword": keyword.lower(),
                        })

    save_seen(seen)
    if first_run:
        print(f"Первый запуск: сохранено {len(seen)} товаров как уже виденные.")
        return

    subs = get_subscribers()
    print(f"Найдено новых: {len(new_items)}, подписчиков: {len(subs)}")

    for item in new_items:
        for sub in subs:
            if matches(item, sub):
                notify(sub["chat_id"], item, item["keyword"])
                time.sleep(1)


if __name__ == "__main__":
    main()
