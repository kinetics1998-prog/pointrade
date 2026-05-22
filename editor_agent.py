#!/usr/bin/env python3
"""
editor_agent.py — STEP 3 у pipeline v9.

AI-редактор приймає фінальне рішення для кожної обробленої статті:
- auto_publish      → одразу на сайт
- auto_deepen       → AI рекомендує згенерувати поглиблений розбір
- to_human_review   → людина у editor/review.html має глянути
- reject            → у rejected.json

Логіка детерміністична (без додаткових AI-викликів) — спирається на:
- validator_verdict / validator_score (від Sonnet critic)
- impact_score (від gpt-4o-mini enricher)
- tags (від gpt-4o-mini enricher)
- наявність what_it_means

Це дешевий швидкий шар який економить твій час як людини-редактора:
очевидні випадки автоматизуються, до тебе доходить тільки сумнівне.
"""

# Теги які тригерять auto_deepen — статті які ти точно хочеш бачити
# у вигляді 1000-словних розборів. Можна редагувати.
DEEPEN_TRIGGER_TAGS = {
    "регуляція",
    "категорійний-менеджмент",
    "митниця",
    "дистрибуція",
    "переговори-з-мережами",
    "трейд-маркетинг",
    "управління-полицею",
    "податки",
    "інвестиції",
}


def decide(story: dict) -> dict:
    """
    Приймає рішення про маршрут статті.
    Повертає dict з прапорами і обґрунтуванням.

    Викликається ПІСЛЯ validator у pipeline (тобто має validator_score).
    Якщо validator не запускався (--no-validate), приймає консервативно
    і відправляє у людську чергу.
    """
    impact = int(story.get("impact_score") or 0)
    score = story.get("validator_score")
    verdict = story.get("validator_verdict") or "review"
    tags = set(story.get("tags") or [])
    has_what_it_means = bool(story.get("what_it_means"))

    decision = {
        "auto_publish": False,
        "auto_deepen": False,
        "to_human_review": False,
        "reject": False,
        "priority": 0,            # 0-10 для сортування у черзі
        "reasoning": "",
    }

    # 1. Якщо critic явно сказав reject — відхиляємо
    if verdict == "reject":
        decision["reject"] = True
        decision["reasoning"] = "critic-validator: reject"
        return decision

    # 2. Якщо валідатор не пройшов (відсутній score) — людська черга
    if score is None:
        decision["to_human_review"] = True
        decision["priority"] = 5 + impact
        decision["reasoning"] = "validator не запускався — потрібна ручна перевірка"
        return decision

    # 3. Високоякісна стаття з тегом для deep dive → AI рекомендує поглиблений розбір
    deepen_tags = tags & DEEPEN_TRIGGER_TAGS
    if score >= 8 and impact >= 2 and deepen_tags and has_what_it_means:
        decision["auto_deepen"] = True
        decision["auto_publish"] = True  # також публікуємо коротку версію
        decision["priority"] = 9 + min(impact - 2, 1)
        decision["reasoning"] = (
            f"AI-редактор: impact={impact}, QA={score}/10, теги {sorted(deepen_tags)} — "
            f"кандидат на ✦ Поглиблений розбір"
        )
        return decision

    # 4. Висока якість, низький-середній impact → автопаблік
    if score >= 8 and impact < 3:
        decision["auto_publish"] = True
        decision["priority"] = 3 + impact
        decision["reasoning"] = f"AI-редактор: QA={score}/10, автопаблік"
        return decision

    # 5. High impact без deepen-теги → людина має додати executable takeaway
    if impact >= 3:
        decision["to_human_review"] = True
        decision["priority"] = 8
        decision["reasoning"] = f"AI-редактор: impact={impact} — high-impact, людина додає takeaway"
        return decision

    # 6. Сумнівна якість (score 5-7) → людська черга
    if 5 <= score <= 7:
        decision["to_human_review"] = True
        decision["priority"] = 4 + impact
        decision["reasoning"] = f"AI-редактор: QA={score}/10 — потрібна перевірка"
        return decision

    # 7. Низька якість (score < 5) — теоретично сюди не доходимо (verdict=reject),
    # але якщо score не нормалізований — fallback на reject
    decision["reject"] = True
    decision["reasoning"] = f"AI-редактор: QA={score}/10 — нижче порогу"
    return decision


def apply_to_batch(stories: list[dict]) -> dict:
    """
    Прогнати весь батч через editor.
    Мутує stories — додає editor_decision, editor_priority, editor_reasoning,
    auto_deepen_recommended.
    Повертає summary.
    """
    summary = {"auto_publish": 0, "auto_deepen": 0, "to_human_review": 0, "reject": 0}
    print(f"\n🤖 AI-редактор: розподіляю {len(stories)} статей...")
    for s in stories:
        d = decide(s)
        s["editor_decision"] = (
            "auto_deepen" if d["auto_deepen"]
            else "auto_publish" if d["auto_publish"]
            else "reject" if d["reject"]
            else "to_human_review"
        )
        s["editor_priority"] = d["priority"]
        s["editor_reasoning"] = d["reasoning"]
        if d["auto_deepen"]:
            s["auto_deepen_recommended"] = True
            summary["auto_deepen"] += 1
        if d["auto_publish"]:
            summary["auto_publish"] += 1
        if d["to_human_review"]:
            summary["to_human_review"] += 1
        if d["reject"]:
            summary["reject"] += 1
    print(f"  📊 auto_publish: {summary['auto_publish']}   ✦ deepen: {summary['auto_deepen']}   "
          f"👤 human: {summary['to_human_review']}   🗑 reject: {summary['reject']}")
    return summary


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    story = json.loads(open(sys.argv[1], encoding="utf-8").read())
    if isinstance(story, list):
        apply_to_batch(story)
    else:
        result = decide(story)
        print(json.dumps(result, ensure_ascii=False, indent=2))
