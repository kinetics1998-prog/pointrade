#!/usr/bin/env python3
"""
telegram_digest.py — щоденний дайджест у Telegram.

Бере topN найкращих статей за день з data/YYYY-MM-DD.json,
сортує за editor_priority + impact_score, формує красивий пост
з імпакт-бейджами і лінками на поглиблений розбір (якщо є).

Запуск:
    python3 telegram_digest.py              # сьогодні, top 3
    python3 telegram_digest.py --top 5      # top 5
    python3 telegram_digest.py --date 2026-05-22
    python3 telegram_digest.py --dry-run    # не відсилати, тільки показати

ENV:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
    POINTRADE_BASE_URL — default http://pointrade.business
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
BASE_URL = os.environ.get("POINTRADE_BASE_URL", "http://pointrade.business")

IMPACT_EMOJI = {0: "", 1: "⚪", 2: "🟡", 3: "🔴"}


def pick_top(date_str: str, top_n: int) -> list[dict]:
    """Вибрати топ N статей за день."""
    f = DATA_DIR / f"{date_str}.json"
    if not f.exists():
        return []
    try:
        stories = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []

    # Фільтруємо: тільки нового формату, не "не впливає" х4, не reject
    def is_new_format(s):
        return bool(
            s.get("validator_score") is not None
            or s.get("what_it_means")
            or s.get("tags")
        )

    def is_all_skip(s):
        wm = s.get("what_it_means") or {}
        keys = ("ua_importer", "pl_distributor", "tr_manufacturer", "category_manager")
        has_any = any(wm.get(k) for k in keys)
        if not has_any:
            return False
        return all(
            not (wm.get(k) or "").strip() or (wm.get(k) or "").strip().lower().startswith("не впливає")
            for k in keys
        )

    candidates = [
        s for s in stories
        if is_new_format(s)
        and not is_all_skip(s)
        and s.get("editor_decision") != "reject"
    ]

    # Сортування:
    # 1. Спочатку статті з deep_article_url (їх читати найцікавіше)
    # 2. Потім за editor_priority + impact_score + validator_score
    def sort_key(s):
        has_deep = 1 if s.get("deep_article_url") else 0
        priority = s.get("editor_priority", 0) or 0
        impact = s.get("impact_score") or 0
        score = s.get("validator_score") or 0
        return (-has_deep, -priority, -impact, -score)

    candidates.sort(key=sort_key)
    return candidates[:top_n]


def format_story(s: dict) -> str:
    """Один блок про одну статтю в HTML для Telegram."""
    title = s.get("title_uk") or s.get("title") or "Без заголовка"
    summary = s.get("summary_uk") or s.get("summary") or ""
    impact = s.get("impact_score") or 0
    impact_emo = IMPACT_EMOJI.get(impact, "")

    tags = s.get("tags") or []
    tags_str = " ".join(f"#{t.replace('-', '_')}" for t in tags[:3])

    # Лінк: якщо є deep article — лінкуємо на нього (це Purple Cow)
    if s.get("deep_article_url"):
        link = f"{BASE_URL}{s['deep_article_url']}"
        link_label = "✦ Поглиблений розбір →"
    else:
        # Інакше — на оригінальне джерело
        link = s.get("link") or s.get("source_url") or ""
        link_label = f"Читати в {s.get('source', 'оригіналі')} →"

    # Що означає для бізнесу — беремо найкращу пораду з 4 (не "не впливає")
    wm = s.get("what_it_means") or {}
    persona_labels = {
        "ua_importer": "🇺🇦 UA-імпортеру",
        "pl_distributor": "🇵🇱 PL-дистриб'ютору",
        "tr_manufacturer": "🇹🇷 TR-виробнику",
        "category_manager": "📑 Категорійному менеджеру",
    }
    means_block = ""
    for k, label in persona_labels.items():
        v = (wm.get(k) or "").strip()
        if v and not v.lower().startswith("не впливає"):
            means_block = f"\n\n💡 <b>{label}:</b>\n{escape_html(v[:280])}"
            break  # перший релевантний

    lines = [
        f"{impact_emo + ' ' if impact_emo else ''}<b>{escape_html(title)}</b>",
        "",
        escape_html(summary[:400]),
    ]
    if means_block:
        lines.append(means_block)
    if tags_str:
        lines.append(f"\n<i>{escape_html(tags_str)}</i>")
    if link:
        lines.append(f'\n🔗 <a href="{link}">{link_label}</a>')

    return "\n".join(lines)


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_digest(stories: list[dict], date_str: str) -> str:
    """Зібрати повний текст дайджесту."""
    hour = datetime.now().hour
    greeting = "🌅 Доброго ранку" if hour < 14 else "🌆 Доброго вечора"
    date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")

    lines = [
        f"{greeting}!",
        "",
        f"📰 <b>POINTRADE</b> · {date_display}",
        f"━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for i, s in enumerate(stories, 1):
        lines.append(f"<b>{i}.</b> {format_story(s)}")
        if i < len(stories):
            lines.append("\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n")

    deep_count = sum(1 for s in stories if s.get("deep_article_url"))
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    if deep_count:
        lines.append(f"✦ <b>{deep_count}</b> поглиблених розборів у цьому випуску")
    lines.append(f'🌐 <a href="{BASE_URL}/news/">Усі новини на pointrade.business</a>')

    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠ TELEGRAM_BOT_TOKEN/CHAT_ID не задані")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print("✅ Дайджест надіслано")
                return True
            print(f"❌ Telegram error: {result}")
            return False
    except Exception as e:
        print(f"❌ Telegram exception: {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    stories = pick_top(args.date, args.top)
    if not stories:
        print(f"🤷 Нема статей нового формату за {args.date}")
        sys.exit(0)

    text = build_digest(stories, args.date)
    print(f"\n{'='*60}")
    print(f"📨 ДАЙДЖЕСТ {args.date} (top {len(stories)})")
    print(f"{'='*60}")
    print(text)
    print(f"{'='*60}\n")

    if args.dry_run:
        print("DRY RUN — не відсилаю")
        return

    send_telegram(text)


if __name__ == "__main__":
    main()
