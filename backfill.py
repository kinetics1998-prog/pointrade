#!/usr/bin/env python3
"""
backfill.py — переобробляє старі статті через новий pipeline v9.

Що робить:
1. Сканує data/YYYY-MM-DD.json
2. Для кожної статті: translate → enrich → validate
3. Зберігає назад у файл з новими полями (title_uk, summary_uk, what_it_means, tags, impact_score, validator_*)
4. Пропускає статті які ВЖЕ оброблені (мають validator_score або editor_reviewed)
5. Підтримує dry-run для оцінки вартості

Використання:
    python3 backfill.py --dry-run                # рахує що треба зробити
    python3 backfill.py --days 3                 # останні 3 дні
    python3 backfill.py --days 7 --no-validate   # тільки translate + enrich
    python3 backfill.py --all                    # ВСЕ (всі 38 днів)
    python3 backfill.py --file data/2026-05-15.json   # конкретний файл

ENV:
    ANTHROPIC_API_KEY — обов'язково
    OPENAI_API_KEY    — обов'язково
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from translate import translate_article, _load_cache as load_translation_cache
from validate import validate_one
from ai_prompt_v9 import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Орієнтовна вартість per article (грубо, в $)
COST_TRANSLATE = 0.0008   # Haiku 4.5 на ~500 токенів
COST_ENRICH = 0.0010      # gpt-4o-mini на ~1500 токенів
COST_VALIDATE = 0.0030    # Sonnet 4.6 на ~1500 токенів


MARKET_TO_CAT = {
    "ua": "UA_BIZ", "pl": "PL_BIZ", "ro": "RO_BIZ", "tr": "TR_BIZ",
    "eu": "PL_BIZ", "global": "UA_BIZ",
}


def is_already_processed(story: dict) -> bool:
    """Стаття вже пройшла новий pipeline?"""
    return bool(
        story.get("validator_score") is not None
        or story.get("editor_reviewed")
        or (story.get("title_uk") and story.get("what_it_means"))
    )


def detect_lang(source: str) -> str:
    """Грубий detect мови з emoji-prefix."""
    s = source or ""
    if "🇺🇦" in s or "UA" in s.upper(): return "uk"
    if "🇵🇱" in s or "PL" in s.upper(): return "pl"
    if "🇷🇴" in s or "RO" in s.upper(): return "ro"
    if "🇹🇷" in s or "TR" in s.upper(): return "tr"
    return "en"


def detect_market(category: str, source: str) -> str:
    """Грубий detect ринку."""
    c = (category or "").upper()
    s = source or ""
    if c.startswith("UA_") or "🇺🇦" in s: return "ua"
    if c.startswith("PL"): return "pl"
    if c.startswith("RO"): return "ro"
    if c.startswith("TR"): return "tr"
    return "global"


def enrich_via_openai(story: dict, lang: str, market: str, client) -> dict | None:
    """STEP 2 — gpt-4o-mini збагачення."""
    body_orig = story.get("summary") or story.get("body_orig") or ""
    title_orig = story.get("title") or story.get("title_orig") or ""

    prompt = USER_PROMPT_TEMPLATE.format(
        source_name=story.get("source", "?"),
        source_lang=lang,
        title_orig=title_orig,
        body_orig=body_orig[:3000],
        market=market,
        pub_date=story.get("published") or "невідомо",
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
        return {
            "title_uk": data.get("title_uk", title_orig),
            "summary_uk": data.get("summary_uk", body_orig[:300]),
            "what_it_means": data.get("what_it_means", {}),
            "tags": data.get("tags", []),
            "impact_score": int(data.get("impact_score", 0) or 0),
            "category": data.get("category") or MARKET_TO_CAT.get(market, "UA_BIZ"),
        }
    except Exception as e:
        print(f"    ⚠ enrich error: {str(e)[:80]}")
        return None


def process_story(story: dict, openai_client, anthropic_client, do_validate: bool, translation_cache: dict) -> tuple[dict, bool]:
    """
    Обробляє одну статтю. Повертає (updated_story, ok_bool).
    Мутує translation_cache.
    """
    lang = detect_lang(story.get("source", ""))
    market = detect_market(story.get("category", ""), story.get("source", ""))
    source_url = story.get("link") or story.get("source_url") or ""

    title = story.get("title") or story.get("title_orig") or ""
    body = story.get("summary") or story.get("body_orig") or ""

    # STEP 1 — translate
    if lang != "uk":
        tr = translate_article(source_url, title, body, lang, cache=translation_cache)
        if not tr.get("skipped"):
            story["_title_pre_translate"] = title
            story["_body_pre_translate"] = body
            story["title"] = tr["title_uk"]
            story["title_orig"] = tr["title_uk"]
            story["summary"] = tr["body_uk"]
            story["body_orig"] = tr["body_uk"]
            story["_translated_by"] = "claude-haiku-4-5-20251001"

    # STEP 2 — enrich
    enriched = enrich_via_openai(story, lang, market, openai_client)
    if not enriched:
        return story, False

    story.update(enriched)
    # legacy compat
    story["title"] = enriched["title_uk"]
    story["summary"] = enriched["summary_uk"]
    story["market"] = market
    story["source_lang"] = lang

    # STEP 2.5 — validate
    if do_validate:
        verdict = validate_one(story, client=anthropic_client)
        story["validator_score"] = verdict["score"]
        story["validator_flags"] = verdict["flags"]
        story["validator_suggestions"] = verdict["suggestions"]
        story["validator_verdict"] = verdict["verdict"]
    else:
        story["validator_verdict"] = "publish"

    return story, True


def process_file(path: Path, openai_client, anthropic_client, do_validate: bool, translation_cache: dict, dry_run: bool) -> dict:
    """Обробляє один data/YYYY-MM-DD.json. Повертає stats."""
    stories = json.loads(path.read_text(encoding="utf-8"))
    to_process = [s for s in stories if not is_already_processed(s)]
    already_done = len(stories) - len(to_process)

    stats = {
        "file": path.name,
        "total": len(stories),
        "skip_done": already_done,
        "to_process": len(to_process),
        "ok": 0,
        "fail": 0,
        "reject": 0,
        "review": 0,
        "publish": 0,
    }

    if dry_run or not to_process:
        return stats

    print(f"\n📂 {path.name} — {len(to_process)} нових (вже оброблено: {already_done})")

    for i, story in enumerate(to_process, 1):
        title_preview = (story.get("title") or "")[:60]
        try:
            updated, ok = process_story(story, openai_client, anthropic_client, do_validate, translation_cache)
            if ok:
                stats["ok"] += 1
                v = updated.get("validator_verdict", "publish")
                stats[v] = stats.get(v, 0) + 1
                icon = {"publish": "✅", "review": "🔍", "reject": "🗑"}.get(v, "•")
                impact = updated.get("impact_score", 0)
                score = updated.get("validator_score", "—")
                print(f"  [{i}/{len(to_process)}] {icon} impact={impact} QA={score}/10  {title_preview}")
            else:
                stats["fail"] += 1
                print(f"  [{i}/{len(to_process)}] ⊘ skip {title_preview}")
        except Exception as e:
            stats["fail"] += 1
            print(f"  [{i}/{len(to_process)}] ❌ ERROR: {str(e)[:80]}")

        time.sleep(0.25)

    # Збереження
    path.write_text(json.dumps(stories, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, help="останні N днів")
    ap.add_argument("--all", action="store_true", help="ВСЕ")
    ap.add_argument("--file", type=str, help="один конкретний файл")
    ap.add_argument("--dry-run", action="store_true", help="не виконувати, тільки оцінити")
    ap.add_argument("--no-validate", action="store_true", help="без Sonnet (тільки translate+enrich)")
    args = ap.parse_args()

    # Збір файлів
    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted(DATA_DIR.glob("2*.json"), reverse=True)
        # лишаємо тільки YYYY-MM-DD.json (без archive, rates, etc.)
        files = [f for f in files if re.match(r"^\d{4}-\d{2}-\d{2}\.json$", f.name)]
        if args.days:
            files = files[: args.days]
        elif not args.all:
            print("Вкажи --days N, або --all, або --file path. --dry-run для оцінки.")
            print("Файлів доступно:", len(files))
            sys.exit(0)

    # Dry-run підрахунок
    total_to_process = 0
    for f in files:
        try:
            stories = json.loads(f.read_text(encoding="utf-8"))
            to_process = sum(1 for s in stories if not is_already_processed(s))
            total_to_process += to_process
        except Exception:
            continue

    do_validate = not args.no_validate
    cost_per = COST_TRANSLATE + COST_ENRICH + (COST_VALIDATE if do_validate else 0)
    est_cost = total_to_process * cost_per

    print(f"\n{'='*60}")
    print(f"📊 BACKFILL PLAN")
    print(f"{'='*60}")
    print(f"  Файлів:          {len(files)}")
    print(f"  Статей до обробки: {total_to_process}")
    print(f"  Pipeline:        translate + enrich" + ("" if not do_validate else " + validate"))
    print(f"  Орієнтовна $:    ~${est_cost:.2f}")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("DRY RUN — без виконання. Запусти без --dry-run для реальної обробки.")
        return

    # API clients
    if not ANTHROPIC_API_KEY or not OPENAI_API_KEY:
        print("❌ Потрібні обидва ключі ANTHROPIC_API_KEY і OPENAI_API_KEY.")
        sys.exit(1)

    try:
        from openai import OpenAI
        from anthropic import Anthropic
    except ImportError:
        print("❌ pip install -r requirements.txt")
        sys.exit(1)

    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    translation_cache = load_translation_cache()

    # Обробка
    total_stats = {"ok": 0, "fail": 0, "publish": 0, "review": 0, "reject": 0, "skip_done": 0}
    start = time.time()
    for f in files:
        s = process_file(f, openai_client, anthropic_client, do_validate, translation_cache, dry_run=False)
        for k in ("ok", "fail", "publish", "review", "reject", "skip_done"):
            total_stats[k] = total_stats.get(k, 0) + s.get(k, 0)

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"✅ DONE за {elapsed/60:.1f} хв")
    print(f"   Оброблено: {total_stats['ok']}   Помилки: {total_stats['fail']}")
    print(f"   📊 publish: {total_stats['publish']}   review: {total_stats['review']}   reject: {total_stats['reject']}")
    print(f"   Раніше готових: {total_stats['skip_done']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
