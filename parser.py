import json
import os
import subprocess
import time

import telebot

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]
STATE_FILE = "state.json"  # логин-сессия xianyu-cli
SEEN_FILE = "seen.json"

bot = telebot.TeleBot(TG_BOT_TOKEN)

# Бренды/ключевые слова для мониторинга на Goofish (личное использование)
KEYWORDS = [
    "undercover",
    "number nine",
    "rick owens",
    "raf simons",
    "undercoverism",
    # добавляй свои
]

DELAY_BETWEEN_KEYWORDS = 5


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


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


def notify(item, keyword):
    text = (
        f"🆕 Новый товар на Goofish!\n\n"
        f"*{item.get('title', '')}*\n"
        f"💴 ¥{item.get('price', '?')}\n"
        f"🔍 Запрос: {keyword}\n"
        f"🔗 [Открыть]({item.get('link', '')})"
    )
    try:
        bot.send_message(int(TG_CHAT_ID), text, parse_mode="Markdown")
    except Exception as e:
        print(f"Не удалось отправить: {e}")


def main():
    seen = load_seen()
    first_run = len(seen) == 0
    new_count = 0

    for keyword in KEYWORDS:
        items = search_keyword(keyword)
        for item in items:
            item_id = item.get("item_id")
            if item_id and item_id not in seen:
                seen.add(item_id)
                if not first_run:
                    notify(item, keyword)
                    new_count += 1
                    time.sleep(1)
        time.sleep(DELAY_BETWEEN_KEYWORDS)

    save_seen(seen)
    if first_run:
        print(f"Первый запуск: сохранено {len(seen)} товаров как уже виденные.")
    else:
        print(f"Найдено новых: {new_count}")


if __name__ == "__main__":
    main()
