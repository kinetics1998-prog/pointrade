#!/usr/bin/env python3
"""
📰 BIZ DIGEST — RSS Collector
Собирает бизнес-новости из украинских и международных источников.
Запускай 2 раза в день (утро + вечер).

Использование:
    python3 rss_collector.py              # собрать + показать в консоли
    python3 rss_collector.py --telegram   # собрать + отправить в Telegram
    python3 rss_collector.py --test       # протестировать какие фиды работают

Настройка Telegram (опционально):
    1. Создай бота: @BotFather → /newbot
    2. Получи токен
    3. Создай канал, добавь бота админом
    4. Впиши токен и chat_id ниже
"""

import feedparser
import json
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time

# ============================================================
# НАСТРОЙКИ — ИЗМЕНИ ПОД СЕБЯ
# ============================================================

# Telegram — берётся из переменных окружения (GitHub Secrets)
# Или впиши вручную для локального запуска
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Папка для хранения собранных статей
DATA_DIR = Path(__file__).parent / "data"
ARCHIVE_FILE = DATA_DIR / "archive.json"
TODAY_FILE = DATA_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.json"

# Сколько часов назад считать "свежими"
FRESH_HOURS = 14  # утренний сбор ловит вечерние + ночные

# ============================================================
# ИСТОЧНИКИ RSS — Украина + Мир
# ============================================================

FEEDS = {
    # === УКРАИНА: БИЗНЕС И TECH ===
    "🇺🇦 AIN.ua": {
        "urls": [
            "https://ain.ua/feed/",
            "https://ain.ua/ru/feed/",
        ],
        "category": "UA_TECH",
        "desc": "IT-бізнес, стартапи, технології",
    },
    "🇺🇦 MC.today": {
        "urls": [
            "https://mc.today/feed/",
            "https://mc.today/uk/feed/",
        ],
        "category": "UA_BIZ",
        "desc": "Гроші, кар'єра, підприємництво",
    },
    "🇺🇦 DOU.ua": {
        "urls": [
            "https://dou.ua/feed/",
            "https://dou.ua/lenta/feed/",
        ],
        "category": "UA_TECH",
        "desc": "IT-спільнота, зарплати, ринок",
    },
    "🇺🇦 Epravda (Бізнес)": {
        "urls": [
            "https://www.epravda.com.ua/rss/",
            "https://www.epravda.com.ua/rss/news/",
        ],
        "category": "UA_ECON",
        "desc": "Економічні новини України",
    },
    "🇺🇦 NV Бізнес": {
        "urls": [
            "https://nv.ua/rss/ukr/biz.xml",
            "https://biz.nv.ua/ukr/rss.xml",
        ],
        "category": "UA_BIZ",
        "desc": "Бізнес-новини від НВ",
    },
    "🇺🇦 The Page": {
        "urls": [
            "https://thepage.ua/rss",
            "https://thepage.ua/ua/rss",
        ],
        "category": "UA_BIZ",
        "desc": "Бізнес та фінанси",
    },
    "🇺🇦 SPEKA": {
        "urls": [
            "https://speka.media/feed",
            "https://speka.media/rss",
        ],
        "category": "UA_TECH",
        "desc": "Стартапи та інновації",
    },
    "🇺🇦 Liga.Бізнес": {
        "urls": [
            "https://biz.liga.net/all/rss.xml",
            "https://biz.liga.net/rss/all.xml",
        ],
        "category": "UA_BIZ",
        "desc": "Діловий портал Liga",
    },
    "🇺🇦 Forbes Ukraine": {
        "urls": [
            "https://forbes.ua/feed",
            "https://forbes.ua/rss",
        ],
        "category": "UA_BIZ",
        "desc": "Рейтинги, мільярдери, бізнес",
    },
    "🇺🇦 mind.ua": {
        "urls": [
            "https://mind.ua/rss",
            "https://mind.ua/feed",
        ],
        "category": "UA_BIZ",
        "desc": "Аналітика для бізнесу",
    },
}

# ============================================================
# ОСНОВНОЙ КОД
# ============================================================

def get_article_id(title: str, link: str) -> str:
    """Уникальный ID статьи для дедупликации."""
    raw = f"{title}|{link}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def load_archive() -> set:
    """Загрузить ID уже собранных статей."""
    if ARCHIVE_FILE.exists():
        try:
            data = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
            return set(data.get("seen_ids", []))
        except Exception:
            return set()
    return set()


def save_archive(seen_ids: set):
    """Сохранить архив ID."""
    # Храним только последние 5000 ID чтобы файл не рос бесконечно
    ids_list = list(seen_ids)[-5000:]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_FILE.write_text(
        json.dumps({"seen_ids": ids_list, "updated": datetime.now().isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def parse_date(entry) -> datetime | None:
    """Попробовать получить дату публикации."""
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None)
        if val:
            try:
                return datetime(*val[:6])
            except Exception:
                pass
    return None


def fetch_feed(name: str, config: dict) -> list[dict]:
    """Получить статьи из одного источника (пробуя несколько URL)."""
    articles = []
    cutoff = datetime.now() - timedelta(hours=FRESH_HOURS)

    for url in config["urls"]:
        try:
            d = feedparser.parse(url)
            if d.entries:
                for entry in d.entries[:15]:  # макс 15 с одного фида
                    pub_date = parse_date(entry)

                    # Пропускаем старые статьи если есть дата
                    if pub_date and pub_date < cutoff:
                        continue

                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    summary = getattr(entry, "summary", "")[:300].strip()

                    if title and link:
                        articles.append({
                            "id": get_article_id(title, link),
                            "source": name,
                            "category": config["category"],
                            "title": title,
                            "link": link,
                            "summary": summary,
                            "published": pub_date.isoformat() if pub_date else None,
                            "fetched": datetime.now().isoformat(),
                        })
                break  # Если первый URL сработал — не пробуем второй
        except Exception as e:
            continue  # Пробуем следующий URL

    return articles


def collect_all() -> list[dict]:
    """Собрать статьи из всех источников."""
    seen_ids = load_archive()
    all_articles = []

    print(f"\n{'='*60}")
    print(f"📰 BIZ DIGEST — Сбор {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    for name, config in FEEDS.items():
        articles = fetch_feed(name, config)
        new_articles = [a for a in articles if a["id"] not in seen_ids]

        if articles:
            print(f"  ✅ {name}: {len(articles)} найдено, {len(new_articles)} новых")
        else:
            print(f"  ❌ {name}: фид недоступен")

        for a in new_articles:
            seen_ids.add(a["id"])
        all_articles.extend(new_articles)

    # Сохраняем
    save_archive(seen_ids)

    # Сохраняем дневной файл
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if TODAY_FILE.exists():
        existing = json.loads(TODAY_FILE.read_text(encoding="utf-8"))
    else:
        existing = []
    existing.extend(all_articles)
    TODAY_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"\n📊 Итого: {len(all_articles)} новых статей")
    print(f"💾 Сохранено: {TODAY_FILE}")

    return all_articles


def format_for_console(articles: list[dict]) -> str:
    """Красивый вывод в консоль."""
    if not articles:
        return "\n🤷 Новых статей нет. Попробуй позже.\n"

    lines = [f"\n{'='*60}", f"📰 ДАЙДЖЕСТ — {len(articles)} новых статей", f"{'='*60}\n"]

    # Группируем по категориям
    categories = {}
    for a in articles:
        cat = a["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(a)

    cat_names = {
        "UA_TECH": "🇺🇦 Украина: Tech & Стартапы",
        "UA_BIZ": "🇺🇦 Украина: Бизнес",
        "UA_ECON": "🇺🇦 Украина: Экономика",
        "WORLD_TECH": "🌍 Мир: Tech",
        "WORLD_BIZ": "🌍 Мир: Бизнес",
    }

    for cat, cat_articles in categories.items():
        lines.append(f"\n--- {cat_names.get(cat, cat)} ---\n")
        for i, a in enumerate(cat_articles[:10], 1):
            lines.append(f"  {i}. [{a['source']}] {a['title']}")
            lines.append(f"     🔗 {a['link']}")
            if a.get("summary"):
                # Чистим HTML из summary
                import re
                clean = re.sub(r'<[^>]+>', '', a["summary"])[:150]
                lines.append(f"     📝 {clean}...")
            lines.append("")

    return "\n".join(lines)


def format_for_telegram(articles: list[dict]) -> str:
    """Красивое форматирование для Telegram (HTML) — 5 лучших с описанием."""
    if not articles:
        return "🤷 Новых бизнес-новостей пока нет."

    import re

    # Приоритет категорий (бизнес важнее tech-новостей)
    cat_priority = {
        "UA_BIZ": 1, "UA_ECON": 2, "UA_TECH": 3,
        "WORLD_BIZ": 4, "WORLD_TECH": 5,
    }

    # Эмодзи для категорий
    cat_emoji = {
        "UA_BIZ": "💼", "UA_ECON": "📊", "UA_TECH": "🚀",
        "WORLD_BIZ": "🌍", "WORLD_TECH": "⚡",
    }

    # Сортируем: сначала UA бизнес, потом мир
    sorted_articles = sorted(articles, key=lambda a: cat_priority.get(a["category"], 99))

    # Берём по 1 из каждой категории для разнообразия, потом добираем
    seen_cats = set()
    top = []
    for a in sorted_articles:
        if a["category"] not in seen_cats and len(top) < 5:
            top.append(a)
            seen_cats.add(a["category"])
    # Добираем до 5 если категорий меньше
    for a in sorted_articles:
        if len(top) >= 5:
            break
        if a not in top:
            top.append(a)

    now = datetime.now().strftime("%d.%m.%Y")
    hour = datetime.now().hour
    greeting = "🌅 Доброе утро" if hour < 12 else "🌆 Добрый вечер"

    lines = []
    lines.append(f"{greeting}!")
    lines.append(f"")
    lines.append(f"📰 <b>BIZ DIGEST</b>  •  {now}")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    for i, a in enumerate(top[:5], 1):
        emoji = cat_emoji.get(a["category"], "📌")
        source_short = a["source"].replace("🇺🇦 ", "").replace("🌍 ", "")

        # Чистим HTML из summary
        summary = re.sub(r'<[^>]+>', '', a.get("summary", ""))
        summary = summary.replace("&amp;", "&").replace("&#8217;", "'").replace("&#38;", "&")
        summary = summary.strip()[:200]
        # Обрезаем на последнем пробеле
        if len(summary) >= 200:
            summary = summary[:summary.rfind(" ")] + "..."

        lines.append(f"{emoji} <b>{i}. {a['title']}</b>")
        lines.append(f"")
        if summary:
            lines.append(f"    {summary}")
            lines.append(f"")
        lines.append(f"    🔗 <a href=\"{a['link']}\">Читать →</a>  •  <i>{source_short}</i>")
        lines.append(f"")
        if i < 5:
            lines.append(f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
            lines.append(f"")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 Всего собрано: {len(articles)} статей из {len(set(a['source'] for a in articles))} источников")
    lines.append(f"")
    lines.append(f"💡 <i>Выбирай что переслать партнёрам!</i>")

    return "\n".join(lines)


def send_telegram(text: str):
    """Отправить в Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\n⚠️  Telegram не настроен. Заполни TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID")
        return False

    import urllib.request
    import urllib.parse

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print("✅ Отправлено в Telegram!")
                return True
            else:
                print(f"❌ Telegram ошибка: {result}")
                return False
    except Exception as e:
        print(f"❌ Telegram ошибка: {e}")
        return False


def test_feeds():
    """Протестировать все фиды — какие работают."""
    print(f"\n{'='*60}")
    print("🔍 ТЕСТ RSS-ФИДОВ")
    print(f"{'='*60}\n")

    working = 0
    broken = 0

    for name, config in FEEDS.items():
        found = False
        for url in config["urls"]:
            try:
                d = feedparser.parse(url)
                if d.entries:
                    print(f"  ✅ {name}")
                    print(f"     URL: {url}")
                    print(f"     Статей: {len(d.entries)}")
                    print(f"     Пример: {d.entries[0].title[:70]}")
                    print()
                    working += 1
                    found = True
                    break
            except Exception:
                continue

        if not found:
            print(f"  ❌ {name}")
            for url in config["urls"]:
                print(f"     Пробовал: {url}")
            print()
            broken += 1

    print(f"\n{'='*60}")
    print(f"📊 Результат: {working} работают, {broken} недоступны")
    print(f"{'='*60}\n")


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    if "--test" in sys.argv:
        test_feeds()
    else:
        articles = collect_all()

        # Показать в консоли
        print(format_for_console(articles))

        # Отправить в Telegram если попросили
        if "--telegram" in sys.argv:
            tg_text = format_for_telegram(articles)
            send_telegram(tg_text)
