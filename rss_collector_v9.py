#!/usr/bin/env python3
"""
📰 BIZ DIGEST v9 — RSS Collector з AI-збагаченням
Drop-in replacement для rss_collector.py.

Що нового v9:
- 40+ джерел (UA/PL/RO/TR/EU + дистрибуція + FMCG)
- AI-блок "Що це означає для бізнесу" (4 персонажі)
- impact_score 0-3 + теги
- балансування ринків (не дозволяємо одному джерелу домінувати)

Використання:
    python3 rss_collector_v9.py                  # збір + AI-enrichment
    python3 rss_collector_v9.py --test           # перевірити які фіди живі
    python3 rss_collector_v9.py --no-ai          # без OpenAI (швидкий тест)
    python3 rss_collector_v9.py --telegram       # + Telegram

ENV:
    OPENAI_API_KEY      — для AI-enrichment
    TELEGRAM_BOT_TOKEN  — опціонально
    TELEGRAM_CHAT_ID    — опціонально
"""

import feedparser
import json
import os
import re
import sys
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path

from rss_sources_v9 import RSS_FEEDS
from ai_prompt_v9 import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from translate import translate_batch
from validate import validate_batch

# ============================================================
# НАСТРОЙКИ
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

DATA_DIR = Path(__file__).parent / "data"
ARCHIVE_FILE = DATA_DIR / "archive.json"
TODAY_FILE = DATA_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.json"
PENDING_FILE = DATA_DIR / "pending_review.json"  # impact=3 АБО score 5-7 чекають редактора
REJECTED_FILE = DATA_DIR / "rejected.json"      # score < 5 — silent reject, для debug

FRESH_HOURS = 14
MAX_PER_FEED = 8
MAX_PRIORITY = 2  # priority<=2 в кожен запуск
MIN_DISTRIBUTION = 3  # мін матеріалів з niche=distribution
EDITOR_REVIEW_IMPACT = 3  # impact >= 3 → редакторська черга, не публікувати автоматом

# market_tag → CAT_LABEL для фронтенду (бекап якщо AI не повернув category)
MARKET_TO_CAT = {
    "ua": "UA_BIZ",
    "pl": "PL_BIZ",
    "ro": "RO_BIZ",
    "tr": "TR_BIZ",
    "eu": "PL_BIZ",
    "global": "UA_BIZ",
}


# ============================================================
# DEDUP
# ============================================================

def article_id(title: str, link: str) -> str:
    return hashlib.md5(f"{title}|{link}".encode()).hexdigest()[:12]


def load_archive() -> set:
    if ARCHIVE_FILE.exists():
        try:
            return set(json.loads(ARCHIVE_FILE.read_text(encoding="utf-8")).get("seen_ids", []))
        except Exception:
            return set()
    return set()


def save_archive(seen_ids: set):
    ids_list = list(seen_ids)[-5000:]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_FILE.write_text(
        json.dumps({"seen_ids": ids_list, "updated": datetime.now().isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_date(entry):
    for f in ("published_parsed", "updated_parsed"):
        v = getattr(entry, f, None)
        if v:
            try:
                return datetime(*v[:6])
            except Exception:
                pass
    return None


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


# ============================================================
# FETCH RSS
# ============================================================

def fetch_one(url: str, market: str, lang: str, name: str, niche: str) -> list[dict]:
    cutoff = datetime.now() - timedelta(hours=FRESH_HOURS)
    out = []
    try:
        d = feedparser.parse(url)
        for entry in (d.entries or [])[:MAX_PER_FEED]:
            pub = parse_date(entry)
            if pub and pub < cutoff:
                continue
            title = (getattr(entry, "title", "") or "").strip()
            link = (getattr(entry, "link", "") or "").strip()
            summary = clean_html(getattr(entry, "summary", ""))[:3000]
            if not (title and link):
                continue
            out.append({
                "id": article_id(title, link),
                "source": name,
                "source_url": link,
                "market": market,
                "source_lang": lang,
                "niche": niche,
                "title_orig": title,
                "body_orig": summary,
                "published": pub.isoformat() if pub else None,
                "fetched": datetime.now().isoformat(),
            })
    except Exception as e:
        print(f"  ⚠ {name}: {e}")
    return out


def collect_drafts() -> list[dict]:
    seen = load_archive()
    drafts = []

    print(f"\n{'='*60}")
    print(f"📰 PIPELINE v9 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    by_niche: dict[str, list] = {}

    for url, market, lang, name, priority, niche in RSS_FEEDS:
        if priority > MAX_PRIORITY:
            continue
        items = fetch_one(url, market, lang, name, niche)
        new = [a for a in items if a["id"] not in seen]
        for a in new:
            seen.add(a["id"])
            by_niche.setdefault(niche, []).append(a)
        if items:
            print(f"  ✅ {name}: {len(items)} знайдено, {len(new)} нових")
        else:
            print(f"  ❌ {name}: фід порожній або недоступний")

    # Балансування: гарантуємо мін кількість distribution якщо є
    distribution = by_niche.get("distribution", [])
    if len(distribution) >= MIN_DISTRIBUTION:
        print(f"\n  📊 Distribution: {len(distribution)} матеріалів (мін {MIN_DISTRIBUTION} ✅)")
    elif distribution:
        print(f"\n  📊 Distribution: {len(distribution)} (нижче мін {MIN_DISTRIBUTION} — це ок, ще накопичиться)")

    for niche_list in by_niche.values():
        drafts.extend(niche_list)

    save_archive(seen)
    return drafts


# ============================================================
# AI ENRICHMENT
# ============================================================

def enrich_one(draft: dict, client) -> dict | None:
    prompt = USER_PROMPT_TEMPLATE.format(
        source_name=draft["source"],
        source_lang=draft["source_lang"],
        title_orig=draft["title_orig"],
        body_orig=draft["body_orig"],
        market=draft["market"],
        pub_date=draft.get("published") or "невідомо",
    )
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        if data.get("skip"):
            return None
        # збираємо фінальний об'єкт для frontend
        out = {
            **draft,
            "title_uk": data.get("title_uk", draft["title_orig"]),
            "summary_uk": data.get("summary_uk", draft["body_orig"][:300]),
            "what_it_means": data.get("what_it_means", {}),
            "tags": data.get("tags", []),
            "impact_score": int(data.get("impact_score", 0) or 0),
            "category": data.get("category") or MARKET_TO_CAT.get(draft["market"], "UA_BIZ"),
            # legacy-поля для зворотної сумісності
            "title": data.get("title_uk", draft["title_orig"]),
            "summary": data.get("summary_uk", draft["body_orig"][:300]),
            "link": draft["source_url"],
        }
        return out
    except Exception as e:
        print(f"    ⚠ AI помилка для '{draft['title_orig'][:50]}': {e}")
        # fallback — без AI, але запис лишається
        return {
            **draft,
            "title": draft["title_orig"],
            "summary": draft["body_orig"][:300],
            "link": draft["source_url"],
            "category": MARKET_TO_CAT.get(draft["market"], "UA_BIZ"),
        }


def enrich_all(drafts: list[dict], skip_ai: bool = False) -> list[dict]:
    if skip_ai or not OPENAI_API_KEY:
        if not OPENAI_API_KEY:
            print("\n⚠ OPENAI_API_KEY не заданий — пропускаю AI-enrichment")
        return [{
            **d,
            "title": d["title_orig"],
            "summary": d["body_orig"][:300],
            "link": d["source_url"],
            "category": MARKET_TO_CAT.get(d["market"], "UA_BIZ"),
        } for d in drafts]

    try:
        from openai import OpenAI
    except ImportError:
        print("\n⚠ openai пакет не встановлений (pip install openai) — пропускаю AI")
        return [{**d, "title": d["title_orig"], "summary": d["body_orig"][:300],
                 "link": d["source_url"], "category": MARKET_TO_CAT.get(d["market"], "UA_BIZ")}
                for d in drafts]

    client = OpenAI(api_key=OPENAI_API_KEY)
    enriched = []
    print(f"\n🤖 AI-enrichment {len(drafts)} матеріалів через {OPENAI_MODEL}...")
    for i, d in enumerate(drafts, 1):
        result = enrich_one(d, client)
        if result:
            enriched.append(result)
            badge = {0: " ", 1: "⚪", 2: "🟡", 3: "🔴"}.get(result.get("impact_score", 0), " ")
            print(f"  [{i}/{len(drafts)}] {badge} {result['title_uk'][:60]}")
        else:
            print(f"  [{i}/{len(drafts)}] ⊘ skip")
        time.sleep(0.3)  # не б'ємо rate-limit
    return enriched


# ============================================================
# SAVE
# ============================================================

def _load_json(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_json(path: Path, data: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_two_tier(stories: list[dict]):
    """
    Триканальна маршрутизація (з врахуванням validator_verdict):

    1. verdict="reject"  (validator score < 5) → data/rejected.json (silent reject, debug)
    2. verdict="review"  (validator score 5-7) → pending_review.json з flag "🔍 AI-flagged"
    3. verdict="publish" (validator score >= 8):
       - impact_score < 3 → одразу data/YYYY-MM-DD.json
       - impact_score == 3 → pending_review.json для редакторського takeaway

    Якщо validator не запускався → verdict вважається "publish" (back-compat).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rejected = []
    needs_review = []
    auto_pub = []

    for s in stories:
        verdict = s.get("validator_verdict") or "publish"
        impact = s.get("impact_score") or 0

        if verdict == "reject":
            rejected.append(s)
        elif verdict == "review":
            # Validator не пропустив якість — людина дивиться
            s["editor_flag"] = "ai_flagged"
            needs_review.append(s)
        else:  # publish
            if impact >= EDITOR_REVIEW_IMPACT:
                # Високий impact — людина додає executable takeaway
                s["editor_flag"] = "high_impact"
                needs_review.append(s)
            else:
                auto_pub.append(s)

    # 1. Auto-publish
    existing_today = _load_json(TODAY_FILE)
    today_ids = {a.get("id") for a in existing_today if a.get("id")}
    new_today = [s for s in auto_pub if s.get("id") not in today_ids]
    existing_today.extend(new_today)
    _save_json(TODAY_FILE, existing_today)

    # 2. Review queue
    pending = _load_json(PENDING_FILE)
    pending_ids = {a.get("id") for a in pending if a.get("id")}
    new_pending = [{**s, "editor_status": "pending"} for s in needs_review if s.get("id") not in pending_ids]
    pending.extend(new_pending)
    _save_json(PENDING_FILE, pending)

    # 3. Rejected (silent — для debug промпта)
    if rejected:
        rejected_log = _load_json(REJECTED_FILE)
        rejected_ids = {a.get("id") for a in rejected_log if a.get("id")}
        new_rejected = [s for s in rejected if s.get("id") not in rejected_ids]
        rejected_log.extend(new_rejected)
        _save_json(REJECTED_FILE, rejected_log[-500:])  # тримаємо тільки останні 500

    print(f"\n💾 Auto-publish: +{len(new_today)} → {TODAY_FILE.name} (всього {len(existing_today)})")
    print(f"📝 На редакторський огляд: +{len(new_pending)} → {PENDING_FILE.name} (черга {len(pending)})")
    if rejected:
        print(f"🗑  Відхилено валідатором: +{len(rejected)} → {REJECTED_FILE.name} (для debug промпта)")
    if new_pending:
        ai_flag_count = sum(1 for s in new_pending if s.get("editor_flag") == "ai_flagged")
        high_count = sum(1 for s in new_pending if s.get("editor_flag") == "high_impact")
        print(f"   ⚠ Відкрий editor/review.html — {high_count} high-impact + {ai_flag_count} AI-flagged")


# Зворотна сумісність — старий виклик
def save_today(stories: list[dict]):
    save_two_tier(stories)


# ============================================================
# TEST FEEDS
# ============================================================

def test_feeds():
    print(f"\n🔍 Тестування {len(RSS_FEEDS)} фідів...\n")
    ok, dead = 0, []
    for url, market, lang, name, priority, niche in RSS_FEEDS:
        try:
            d = feedparser.parse(url)
            if d.entries:
                print(f"  ✅ [{market}/{niche}] {name} ({len(d.entries)})")
                ok += 1
            else:
                print(f"  ❌ [{market}/{niche}] {name} — порожній")
                dead.append(name)
        except Exception as e:
            print(f"  ❌ [{market}/{niche}] {name} — {e}")
            dead.append(name)
    print(f"\n{'='*60}")
    print(f"📊 {ok}/{len(RSS_FEEDS)} живі. Мертві: {', '.join(dead) if dead else 'немає'}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    if "--test" in sys.argv:
        test_feeds()
        sys.exit(0)

    skip_ai = "--no-ai" in sys.argv
    skip_translate = "--no-translate" in sys.argv
    skip_validate = "--no-validate" in sys.argv
    drafts = collect_drafts()
    print(f"\n📥 Зібрано {len(drafts)} draft-ів")

    if not drafts:
        print("Нема нових матеріалів. Виходжу.")
        sys.exit(0)

    # STEP 1 — Claude Haiku перекладає PL/RO/TR/EN → uk
    if not skip_translate:
        drafts = translate_batch(drafts)
    else:
        print("\n⏭  Переклад пропущено (--no-translate)")

    # STEP 2 — gpt-4o-mini робить бізнес-збагачення (4 персонажі, impact, теги)
    enriched = enrich_all(drafts, skip_ai=skip_ai)

    # STEP 2.5 — Claude Sonnet валідує бізнес-грамотність
    # publish/review/reject — рішення базується на frameworks.md
    if not skip_validate:
        enriched, _summary = validate_batch(enriched)
    else:
        print("\n⏭  Валідація пропущена (--no-validate) — все маршрутизується як publish")

    # STEP 3 — триканальна маршрутизація:
    #   reject → rejected.json (silent)
    #   review (низький score або high impact) → pending_review.json
    #   publish + impact<3 → автопаблік
    save_two_tier(enriched)

    print(f"\n✅ Готово. {len(enriched)} матеріалів оброблено.")
