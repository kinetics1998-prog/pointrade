#!/usr/bin/env python3
"""
validate.py — крок 2.5 pipeline v9. Контроль якості.

Перевіряє AI-збагачені статті на бізнес-грамотність:
- Чи цифри і валюти правдоподібні
- Чи поради конкретні (а не «треба моніторити»)
- Чи теги відповідають змісту
- Чи impact_score адекватний

Модель: Claude Sonnet 4.6 (краще міркує за gpt-4o-mini, дешевше за Opus).

Базується на frameworks.md — короткому файлі з фреймворками
категорійки + червоними прапорами bad AI-output.

ENV:
    ANTHROPIC_API_KEY — обов'язково
    VALIDATOR_MODEL    — опц. (default: claude-sonnet-4-6)

Routing logic у rss_collector_v9.py:
    score >= 8 → нормальний маршрут (impact=3 → редактор, інше → автопаблік)
    score 5-7  → ЗАВЖДИ в pending_review.json з прапором 🔍 AI-flagged
    score < 5  → data/rejected.json (silent reject, для debug)

CLI:
    python3 validate.py path/to/story.json
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
FRAMEWORKS_FILE = ROOT / "frameworks.md"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
VALIDATOR_MODEL = os.environ.get("VALIDATOR_MODEL", "claude-sonnet-4-6")


SYSTEM_PROMPT_TEMPLATE = """Ти — суворий бізнес-редактор Pointrade. Твоя робота — НЕ пропускати на сайт маячню.

Тобі дається стаття після AI-збагачення (заголовок_uk, summary_uk, what_it_means для 4 персонажів, tags, impact_score). Твоє завдання — оцінити її якість 0-10 і повернути JSON з прапорами проблем.

Орієнтуйся на цей короткий гайд:

{frameworks}

---

Поверни ЧИСТИЙ JSON без markdown:

{{
  "score": 0-10,
  "flags": ["hallucinated_number"|"generic_advice"|"wrong_currency"|"irrelevant_persona"|"wrong_tag"|"banned_words"|"logic_error"|"impact_too_high"|"impact_too_low"|...],
  "suggestions": "1-3 короткі речення з конкретикою що саме не так. Якщо все добре — порожній рядок.",
  "verdict": "publish" | "review" | "reject"
}}

Routing:
- score >= 8 → "publish"
- score 5-7  → "review"
- score < 5  → "reject"

Будь чесним. Краще зайвий раз відправити в редакторську чергу ніж пропустити маячню на сайт. Але не педантичним: якщо порада конкретна і логічна — це 8+, навіть якщо без точних цифр.
"""


def _load_frameworks() -> str:
    if FRAMEWORKS_FILE.exists():
        return FRAMEWORKS_FILE.read_text(encoding="utf-8")
    return "(frameworks.md не знайдено)"


def _build_user_msg(story: dict) -> str:
    wm = story.get("what_it_means", {}) or {}
    return (
        f"СТАТТЯ:\n\n"
        f"Заголовок (uk): {story.get('title_uk') or story.get('title', '')}\n"
        f"Категорія: {story.get('category', '?')}\n"
        f"Теги: {', '.join(story.get('tags', []) or [])}\n"
        f"Impact: {story.get('impact_score', 0)}\n\n"
        f"Summary (uk):\n{story.get('summary_uk') or story.get('summary', '')}\n\n"
        f"Що це означає:\n"
        f"  UA-імпортер: {wm.get('ua_importer', '—')}\n"
        f"  PL-дистриб'ютор: {wm.get('pl_distributor', '—')}\n"
        f"  TR-виробник: {wm.get('tr_manufacturer', '—')}\n"
        f"  Категорійний менеджер: {wm.get('category_manager', '—')}\n\n"
        f"Джерело: {story.get('source', '?')} ({story.get('market', '?')}, {story.get('source_lang', '?')})\n"
        f"URL: {story.get('source_url') or story.get('link', '')}\n\n"
        f"Оригінал заголовка: {story.get('_title_pre_translate') or '(не збережено)'}\n\n"
        f"Оціни і поверни JSON."
    )


def validate_one(story: dict, client=None) -> dict:
    """
    Повертає dict з полями score, flags, suggestions, verdict.
    При помилці API — повертає score=7 verdict=review (безпечне дефолт)
    щоб людина переглянула.
    """
    if not ANTHROPIC_API_KEY:
        return {
            "score": 7, "flags": ["no_api_key"], "suggestions": "ANTHROPIC_API_KEY не заданий",
            "verdict": "review",
        }

    if client is None:
        try:
            from anthropic import Anthropic
        except ImportError:
            return {
                "score": 7, "flags": ["anthropic_not_installed"], "suggestions": "pip install anthropic",
                "verdict": "review",
            }
        client = Anthropic(api_key=ANTHROPIC_API_KEY)

    sys_prompt = SYSTEM_PROMPT_TEMPLATE.format(frameworks=_load_frameworks())

    try:
        resp = client.messages.create(
            model=VALIDATOR_MODEL,
            max_tokens=600,
            system=[{
                "type": "text",
                "text": sys_prompt,
                "cache_control": {"type": "ephemeral"},  # frameworks кешуються 5 хв
            }],
            messages=[{"role": "user", "content": _build_user_msg(story)}],
        )
        raw = resp.content[0].text.strip()
        # Прибрати ```json якщо є
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        data = json.loads(raw)
        # Sanity-check
        score = int(data.get("score", 7) or 7)
        verdict = data.get("verdict")
        if verdict not in ("publish", "review", "reject"):
            verdict = "publish" if score >= 8 else "review" if score >= 5 else "reject"
        return {
            "score": score,
            "flags": data.get("flags", []) or [],
            "suggestions": data.get("suggestions", "") or "",
            "verdict": verdict,
        }
    except Exception as e:
        return {
            "score": 7, "flags": ["validator_error"],
            "suggestions": f"validator виключення: {str(e)[:120]}",
            "verdict": "review",
        }


def validate_batch(stories: list[dict]) -> tuple[list[dict], dict]:
    """
    Прогнати весь список через валідатор. Мутує кожну статтю —
    додає поля validator_score, validator_flags, validator_suggestions, validator_verdict.

    Повертає (stories, summary_dict).
    """
    if not stories:
        return stories, {"publish": 0, "review": 0, "reject": 0}

    try:
        from anthropic import Anthropic
    except ImportError:
        print("\n⚠ anthropic SDK не встановлений — пропускаю validate")
        for s in stories:
            s["validator_verdict"] = "publish"  # fallback: пускаємо як було
        return stories, {"publish": len(stories), "review": 0, "reject": 0}

    if not ANTHROPIC_API_KEY:
        print("\n⚠ ANTHROPIC_API_KEY не заданий — пропускаю validate")
        for s in stories:
            s["validator_verdict"] = "publish"
        return stories, {"publish": len(stories), "review": 0, "reject": 0}

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    print(f"\n🛡  Валідація {len(stories)} матеріалів через {VALIDATOR_MODEL}...")

    summary = {"publish": 0, "review": 0, "reject": 0}
    for i, s in enumerate(stories, 1):
        result = validate_one(s, client=client)
        s["validator_score"] = result["score"]
        s["validator_flags"] = result["flags"]
        s["validator_suggestions"] = result["suggestions"]
        s["validator_verdict"] = result["verdict"]
        summary[result["verdict"]] = summary.get(result["verdict"], 0) + 1

        icon = {"publish": "✅", "review": "🔍", "reject": "🗑"}[result["verdict"]]
        flags_str = f" [{', '.join(result['flags'][:3])}]" if result["flags"] else ""
        title_preview = (s.get("title_uk") or s.get("title") or "")[:55]
        print(f"  [{i}/{len(stories)}] {icon} {result['score']}/10  {title_preview}{flags_str}")

        time.sleep(0.2)

    print(f"\n  📊 publish: {summary['publish']}   review: {summary['review']}   reject: {summary['reject']}")
    return stories, summary


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    path = Path(sys.argv[1])
    story = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(story, list):
        # передали день — валідуємо всі
        validated, summary = validate_batch(story)
        print("\nSummary:", summary)
    else:
        result = validate_one(story)
        print(json.dumps(result, ensure_ascii=False, indent=2))
