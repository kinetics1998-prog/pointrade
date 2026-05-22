#!/usr/bin/env python3
"""
translate.py — крок 1 pipeline v9.

Claude Haiku 4.5 перекладає title + body новини на українську,
БЕЗ редакторської обробки. Чиста передача змісту, цифр, назв.

Далі rss_collector_v9.py передає перекладений текст у gpt-4o-mini
для бізнес-збагачення (4 персонажі, impact_score, теги).

Чому Haiku 4.5 а не gpt-4o-mini для перекладу:
- сильніша в редагуванні і збереженні цифр/номіналів
- TR/RO/PL/EN → uk: менше калькованих конструкцій
- prompt caching: system-prompt кешується 5 хв, batch translations
  одного запуску стають дешевшими

ENV:
    ANTHROPIC_API_KEY — обов'язково
    ANTHROPIC_MODEL    — опц. (default: claude-haiku-4-5-20251001)

Кеш:
    data/translations_cache.json — md5(source_url) → переклад.
    Якщо одна новина приходить з 2 RSS-фідів (синдикація) —
    перекладаємо лише раз.

CLI для тесту:
    python3 translate.py "https://example.com/news/123" "Original title" "Original body..." pl
"""

import json
import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent / "data"
CACHE_FILE = DATA_DIR / "translations_cache.json"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

# Skip translation для цих мов — вони вже uk або близькі для AI-збагачення
SKIP_LANGS = {"uk"}

SYSTEM_PROMPT = """Ти — професійний перекладач бізнес-новин з PL/RO/TR/EN на українську (uk-UA).

Правила перекладу:
1. ТІЛЬКИ переклад. Не редагуй, не скорочуй, не додавай контекст.
2. Зберігай ВСІ цифри, дати, валюти, відсотки точно як в оригіналі.
3. Назви компаній — оригінал (Carrefour, Biedronka, Migros). НЕ транслітеруй.
4. Назви країн і міст — українською (Польща, Стамбул, Бухарест).
5. Назви законів і урядових органів — українською з оригіналом у дужках першого разу:
   «Сейм (Sejm)», «Закон про акциз (Ustawa akcyzowa)».
6. Технічні терміни — українською, з англійським у дужках якщо вузький термін:
   «частка полиці (share-of-shelf)».
7. НЕ використовуй кальки: «наразі», «вкрай», «колосальний», «вагомий».
8. Поверни ЧИСТИЙ JSON без markdown-обгортки:
   {"title_uk": "...", "body_uk": "..."}
"""


# ============================================================
# CACHE
# ============================================================

def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_key(source_url: str, title: str) -> str:
    return hashlib.md5(f"{source_url}|{title}".encode()).hexdigest()[:16]


# ============================================================
# TRANSLATE
# ============================================================

def translate_article(
    source_url: str,
    title: str,
    body: str,
    source_lang: str,
    cache: Optional[dict] = None,
) -> dict:
    """
    Повертає {"title_uk": ..., "body_uk": ..., "cached": bool, "skipped": bool}.

    - Якщо source_lang в SKIP_LANGS → повертає оригінал з skipped=True
    - Якщо переклад уже в кеші → cached=True
    - Інакше викликає Anthropic API
    """
    if source_lang in SKIP_LANGS:
        return {"title_uk": title, "body_uk": body, "cached": False, "skipped": True}

    if cache is None:
        cache = _load_cache()

    key = _cache_key(source_url, title)
    if key in cache:
        c = cache[key]
        return {"title_uk": c["title_uk"], "body_uk": c["body_uk"], "cached": True, "skipped": False}

    if not ANTHROPIC_API_KEY:
        # Fallback — без перекладу
        return {"title_uk": title, "body_uk": body, "cached": False, "skipped": True, "error": "no ANTHROPIC_API_KEY"}

    try:
        from anthropic import Anthropic
    except ImportError:
        return {"title_uk": title, "body_uk": body, "cached": False, "skipped": True, "error": "anthropic not installed"}

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    user_msg = (
        f"Мова оригіналу: {source_lang}\n\n"
        f"TITLE:\n{title}\n\n"
        f"BODY:\n{body[:4000]}\n\n"
        f"Переклади на українську. Поверни JSON: "
        f'{{"title_uk": "...", "body_uk": "..."}}'
    )

    try:
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = resp.content[0].text.strip()
        # Подекуди модель може повернути JSON в ```json блоці — почистимо
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
        data = json.loads(raw)
        title_uk = data.get("title_uk", title)
        body_uk = data.get("body_uk", body)

        cache[key] = {
            "title_uk": title_uk,
            "body_uk": body_uk,
            "source_lang": source_lang,
            "translated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        _save_cache(cache)

        return {"title_uk": title_uk, "body_uk": body_uk, "cached": False, "skipped": False}
    except Exception as e:
        return {"title_uk": title, "body_uk": body, "cached": False, "skipped": True, "error": str(e)}


def translate_batch(drafts: list[dict]) -> list[dict]:
    """
    Прогнати весь список drafts через переклад.
    Мутує кожен draft: підставляє title_orig і body_orig перекладеною версією,
    зберігає оригінали в _title_pre_translate і _body_pre_translate.

    Подальший AI-enrichment (gpt-4o-mini) отримає вже-український вхід.
    """
    cache = _load_cache()
    translated = 0
    skipped = 0
    cached_count = 0
    errored = 0

    print(f"\n🌐 Переклад {len(drafts)} матеріалів через {ANTHROPIC_MODEL}...")

    for i, d in enumerate(drafts, 1):
        result = translate_article(
            source_url=d.get("source_url", ""),
            title=d.get("title_orig", ""),
            body=d.get("body_orig", ""),
            source_lang=d.get("source_lang", "en"),
            cache=cache,
        )

        if result.get("skipped"):
            if result.get("error"):
                errored += 1
                print(f"  [{i}/{len(drafts)}] ⚠ {d.get('source','')} — {result['error'][:60]}")
            else:
                skipped += 1
            continue

        # Зберігаємо оригінали і підставляємо переклад
        d["_title_pre_translate"] = d.get("title_orig", "")
        d["_body_pre_translate"] = d.get("body_orig", "")
        d["title_orig"] = result["title_uk"]
        d["body_orig"] = result["body_uk"]
        d["_translated_by"] = ANTHROPIC_MODEL

        if result.get("cached"):
            cached_count += 1
        else:
            translated += 1

        # rate limiting only on real API calls
        if not result.get("cached"):
            time.sleep(0.2)

    print(f"  ✓ Перекладено: {translated}   З кешу: {cached_count}   Пропущено (uk): {skipped}   Помилки: {errored}")
    return drafts


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(0)
    url, title, body, lang = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    result = translate_article(url, title, body, lang)
    print(json.dumps(result, ensure_ascii=False, indent=2))
