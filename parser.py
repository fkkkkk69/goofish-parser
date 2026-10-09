import json
import os
import random
import subprocess
import sys
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

# Старый фиксированный список: нужен только чтобы не завалить уведомлениями при переходе на поиск по брендам подписчиков
LEGACY_KEYWORDS = [
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

MAX_BRANDS_PER_SUB = 5
EMPTY_STREAK_ALERT = 3  # алерт только после стольких пустых запусков подряд
ADMIN_DEFAULT = "2034814464"

MAX_WORKERS = 1  # Снижено с 3 — последовательный поиск, чтобы не триггерить антибот-защиту Goofish и продлить жизнь сессии


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


import re as _re

def extract_item_id(item):
    """Достаём настоящий id товара из оригинальной ссылки goofish.com,
    а не из поля item_id (оно может не совпадать с id в URL)."""
    link = item.get("link", "")
    m = _re.search(r'[?&]id=(\d+)', link)
    if m:
        return m.group(1)
    return item.get("item_id")


SEARCH_ERRORS = []


def _search_once(keyword):
    result = subprocess.run(
        [
            "xianyu", "search", keyword,
            "--format", "json",
            "--storage-state", STATE_FILE,
            "--pages", "1",
            "--sort", "latest",
        ],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        err = f"rc={result.returncode}: {(result.stderr or result.stdout)[-300:]}"
        return None, err
    data = json.loads(result.stdout)
    if not data:
        return [], f"empty result, stderr: {(result.stderr or '')[-200:]}"
    return data, None


def search_keyword(keyword):
    err = None
    for attempt in range(2):  # одна повторная попытка при пустом ответе/ошибке
        time.sleep(random.uniform(3, 6))  # пауза против антибота
        try:
            data, err = _search_once(keyword)
        except Exception as e:
            data, err = None, f"exception: {str(e)[:200]}"
        if data:
            return data
        print(f"Поиск '{keyword}' пустой (попытка {attempt + 1}): {err}")
    SEARCH_ERRORS.append(err)
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
        if b in keyword:  # проверяем только поисковый запрос, не текст объявления — там часто спам-теги со всеми брендами разом
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
    import html
    from telebot import types
    item_id = item.get("id", "")
    title = html.escape(str(item.get("title", ""))[:200])
    text = (
        f"🆕 Новый товар на Goofish!\n\n"
        f"<b>{title}</b>\n"
        f"💴 ¥{html.escape(str(item.get('price', '?')))}\n"
        f"🔍 Запрос: {html.escape(str(keyword))}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("📱 В приложении", url=f"https://fkkkkk69.github.io/xy-open/?id={item_id}"),
        types.InlineKeyboardButton("🌐 В браузере", url=f"https://www.goofish.com/item?id={item_id}"),
    )
    try:
        bot.send_message(int(chat_id), text, parse_mode="HTML", reply_markup=kb)
        return True
    except Exception as e:
        print(f"Не удалось отправить {chat_id}: {e}")
        try:  # запасной вариант: простой текст без разметки
            bot.send_message(int(chat_id), f"🆕 {item.get('title','')[:200]}\n¥{item.get('price','?')} ({keyword})\nhttps://www.goofish.com/item?id={item_id}")
            return True
        except Exception as e2:
            print(f"Повторно не удалось {chat_id}: {e2}")
            return False


def maybe_alert(report, zero):
    import datetime as _dt
    now = _dt.datetime.utcnow()
    last = report.get("last_alert_utc")
    if report.get("empty_streak", 0) < EMPTY_STREAK_ALERT:
        return
    if last:
        try:
            if (now - _dt.datetime.fromisoformat(last)).total_seconds() < 6 * 3600:
                return
        except Exception:
            pass
    admin = os.environ.get("ADMIN_CHAT_ID") or ADMIN_DEFAULT  # только админу, не подписчикам
    try:
        bot.send_message(int(admin),
            f"⚠️ Парсер Goofish не получает данные уже {report['empty_streak']} запусков подряд: "
            f"{zero} из {report['keywords_total']} поисков пустые. Возможна блокировка или устаревшая сессия (state.json). "
            f"Ошибка: {(report.get('error_samples') or ['?'])[0][:200]}")
        report["last_alert_utc"] = now.isoformat(timespec="seconds")
    except Exception as e:
        print(f"Не удалось отправить алерт: {e}")


def write_report(report):
    import json, datetime
    report["finished_utc"] = datetime.datetime.utcnow().isoformat(timespec="seconds")
    with open("last_run.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)


def build_keywords(subs):
    """Ищем только бренды, выбранные подписчиками (объединение без дублей)."""
    out, seen_kw = [], set()
    for sub in subs:
        for b in sub.get("brands", [])[:MAX_BRANDS_PER_SUB]:
            b = str(b).strip().lower()
            if b and b not in seen_kw:
                seen_kw.add(b)
                out.append(b)
    return out


def main():
    seen = load_seen()
    first_run = len(seen) == 0
    new_items = []
    subs = get_subscribers()
    KEYWORDS = build_keywords(subs)
    if not KEYWORDS:
        print("Нет подписчиков с брендами — искать нечего.")
        return
    # Бренды, по которым уже искали раньше (хранятся в seen.json как 'kw:<бренд>').
    # Для самого первого перехода считаем известными все бренды старого списка.
    known_kw = {x[3:] for x in seen if isinstance(x, str) and x.startswith("kw:")}
    if not known_kw:
        known_kw = {k.lower() for k in LEGACY_KEYWORDS}
    new_kw = {k for k in KEYWORDS if k not in known_kw}
    report = {"keywords_total": len(KEYWORDS), "per_keyword_items": {}, "new_items": 0,
              "subscribers": None, "sent": 0, "send_failed": 0, "sample_new": []}
    try:
        with open("last_run.json", encoding="utf-8") as f:
            _prev = json.load(f)
    except Exception:
        _prev = {}
    report["last_alert_utc"] = _prev.get("last_alert_utc")
    report["empty_streak"] = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_keyword = {executor.submit(search_keyword, kw): kw for kw in KEYWORDS}
        for future in as_completed(future_to_keyword):
            keyword = future_to_keyword[future]
            try:
                items = future.result()
            except Exception as e:
                print(f"Ошибка потока для '{keyword}': {e}")
                items = []
            report["per_keyword_items"][keyword] = len(items)
            for item in items:
                item_id = extract_item_id(item)
                if not first_run:
                    print(f"DEBUG raw item link={item.get('link')!r} item_id_field={item.get('item_id')!r} extracted={item_id!r}")
                if item_id and item_id not in seen:
                    seen.add(item_id)
                    # новый бренд: текущие лоты только запоминаем, чтобы не прислать сразу кучу старых
                    if not first_run and keyword not in new_kw:
                        new_items.append({
                            "id": item_id,
                            "title": item.get("title", ""),
                            "price": item.get("price", 0),
                            "link": f"https://fleamarket.taobao.com/npc/itemDetail.html?id={item_id}",  # формат ссылки, который открывается в приложении Xianyu, а не в браузере
                            "keyword": keyword.lower(),
                        })

    zero = sum(1 for v in report["per_keyword_items"].values() if v == 0)
    report["zero_keywords"] = zero
    report["error_samples"] = list(dict.fromkeys(SEARCH_ERRORS))[:3]
    if report["keywords_total"] and zero / report["keywords_total"] >= 0.9:
        report["session_suspect"] = True
        report["empty_streak"] = _prev.get("empty_streak", 0) + 1
        maybe_alert(report, zero)
        write_report(report)
        return

    for k in KEYWORDS:
        seen.add(f"kw:{k}")
    save_seen(seen)
    report["new_items"] = len(new_items)
    report["sample_new"] = [f"{i['keyword']} | {i['price']} | {i['title'][:40]}" for i in new_items[:8]]
    if first_run:
        print(f"Первый запуск: сохранено {len(seen)} товаров как уже виденные.")
        return

    if "--silent" in sys.argv:
        print(f"Тихий запуск: {len(new_items)} товаров помечены как виденные, уведомления не отправляются.")
        write_report(report)
        return

    print(f"Найдено новых: {len(new_items)}, подписчиков: {len(subs)}")
    report["subscribers"] = len(subs)

    for item in new_items:
        for sub in subs:
            if matches(item, sub):
                ok = notify(sub["chat_id"], item, item["keyword"])
                report["sent" if ok else "send_failed"] += 1
                time.sleep(1)
    write_report(report)


if __name__ == "__main__":
    main()
