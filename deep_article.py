#!/usr/bin/env python3
"""
deep_article.py — генератор глибокого розбору для важливих новин.

Це Purple Cow Pointrade — не короткий переказ, а full-length стаття
900-1300 слів з 4-персональним розбором, чек-лістом дій, таблицею
"до vs після", прикладами і м'яким CTA.

Модель: Claude Sonnet 4.6 (Opus 4.7 для топових — overkill зазвичай).

Використання:
    # за story_id з дата-файлу
    python3 deep_article.py --id <hash>

    # за заголовком (пошук у всіх дата-файлах)
    python3 deep_article.py --title "Гетманцев"

    # вручну подати джерельну новину
    python3 deep_article.py --manual "Заголовок | Текст джерела"

    # повний прогін однієї статті з debug
    python3 deep_article.py --id <hash> --verbose

Виходи:
    1. news/insights/YYYY-MM-DD-slug.html — повна стаття
    2. Якщо --id заданий: оновлює відповідну статтю в data/YYYY-MM-DD.json
       полем `deep_article_url` (фронт показує посилання "Повний розбір")

ENV:
    ANTHROPIC_API_KEY
    DEEP_MODEL — за замовчуванням claude-sonnet-4-6
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
INSIGHTS_DIR = ROOT / "news" / "insights"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEEP_MODEL = os.environ.get("DEEP_MODEL", "claude-sonnet-4-6")


SYSTEM_PROMPT = """Ти — опытный бизнес-журналист и консультант по международной торговле между Украиной, Польшей и Турцией. Пишешь практичные, полезные статьи для предпринимателей (импортёров, дистрибьюторов, производителей и категорийных менеджеров).

Стиль: максимально практичный, без воды, с чёткими выводами и рекомендациями. Тон — спокойный, экспертный, "взрослый", без паники и сенсаций.

Обязательная структура статьи:

1. Сильный, цепляющий заголовок (вариант + подзаголовок)
2. Lead (первые 2–3 абзаца) — суть новости + почему это важно именно сейчас
3. Что такое суть (объяснение простыми словами + сравнительная таблица где возможно)
4. Что это реально меняет для каждой роли (отдельные подзаголовки):
   - UA-импортёр
   - PL-дистрибьютор
   - TR-производитель / экспортёр в Украину
   - Category Manager / закупщик
5. Практические рекомендации: Что делать прямо сейчас (конкретный чек-лист 5–7 пунктов)
6. Возможности и риски (где можно выиграть, а где нужно подготовиться)
7. Заключение + мягкий CTA к платформе Pointrade (закрытая B2B-сеть UA-PL-TR)

Дополнительно:
- Используй таблицу сравнения "Сейчас vs После" (где возможно)
- Добавь 1–2 конкретных примера из жизни
- Объём 900–1300 слов
- В конце предложи 2–3 варианта альтернативного заголовка

ФОРМАТ ОТВЕТА — JSON БЕЗ markdown-обёртки:
{
  "title_main": "основной заголовок",
  "title_sub": "подзаголовок",
  "title_alternatives": ["вариант 2", "вариант 3"],
  "body_html": "<полная статья в HTML с тегами h2, h3, p, table, ul, blockquote>",
  "tldr": "1 короткое предложение для превью на главной",
  "tags": ["максимум 5"],
  "word_count": 1100
}

В body_html:
- Заголовки секций — h2
- Подзаголовки внутри секций — h3
- Таблицы — обычный HTML table с thead/tbody, без классов
- Чек-листы — ul/li с описательными пунктами (НЕ галочки)
- Подсветки — blockquote для CTA и ключевых insights
- Никаких пустых div, спанов, инлайн-стилей. Чистый семантический HTML.
"""


USER_TEMPLATE = """Напиши большую качественную статью на русском языке на основе новости:

ИСХОДНАЯ НОВОСТЬ:
Заголовок: {title}
Текст: {body}
Дата: {pub_date}
Источник: {source}

Целевая аудитория: UA-импортёры, PL-дистрибьюторы, TR-производители, Category Managers/закупщики в рознице и сетях.

Сгенерируй полную статью в готовом для публикации виде. Верни ТОЛЬКО валидный JSON по схеме из system-промпта, без markdown-обёртки, без ```json."""


def slugify(text: str, maxlen: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip().lower())
    return text[:maxlen].strip("-") or "article"


def find_story(query: str, by_id: bool = True) -> tuple[dict, Path] | None:
    """Знайти статтю за id або заголовком серед усіх дата-файлів."""
    for f in sorted(DATA_DIR.glob("2*.json"), reverse=True):
        try:
            stories = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for s in stories:
            if by_id and s.get("id") == query:
                return s, f
            if not by_id:
                t = (s.get("title_uk") or s.get("title") or "")
                if query.lower() in t.lower():
                    return s, f
    return None


def generate(title: str, body: str, source: str, pub_date: str) -> dict:
    if not ANTHROPIC_API_KEY:
        raise SystemExit("❌ ANTHROPIC_API_KEY не заданий")
    try:
        from anthropic import Anthropic
    except ImportError:
        raise SystemExit("❌ pip install anthropic")

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    print(f"\n🧠 Генерую через {DEEP_MODEL}...")
    print(f"   Заголовок: {title[:80]}")

    resp = client.messages.create(
        model=DEEP_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": USER_TEMPLATE.format(
                title=title,
                body=body[:5000],
                pub_date=pub_date or "—",
                source=source or "—",
            ),
        }],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    data = json.loads(raw)

    print(f"   ✓ {data.get('word_count', '?')} слів")
    print(f"   ✓ Заголовок: {data.get('title_main', '')[:80]}")
    return data


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Pointrade</title>
<meta name="description" content="{tldr}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;1,9..144,400&family=Geist:wght@300;400;500&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--ink:#1F1A14;--paper:#FAF6EE;--soft:#F2EDE2;--softer:#EBE5D6;--muted:#7B7166;--line:rgba(31,26,20,0.08);--line-2:rgba(31,26,20,0.16);--accent:#C25A3F;--brass:#A8884C;--display:'Fraunces',Georgia,serif;--sans:'Geist',system-ui,sans-serif;--mono:'Geist Mono',monospace}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--sans);background:var(--paper);color:var(--ink);font-size:17px;line-height:1.7;-webkit-font-smoothing:antialiased}}
.topbar{{position:sticky;top:0;z-index:50;background:rgba(250,246,238,0.92);backdrop-filter:saturate(180%) blur(14px);border-bottom:0.5px solid var(--line-2);padding:14px 24px;display:flex;align-items:center;justify-content:space-between}}
.brand{{font-family:var(--mono);font-size:13px;font-weight:500;letter-spacing:0.22em;color:var(--ink);text-decoration:none}}
.brand b{{color:var(--accent);font-weight:500;letter-spacing:0}}
.back-link{{font-family:var(--mono);font-size:11px;letter-spacing:0.08em;color:var(--muted);text-decoration:none;padding:8px 10px;border-radius:5px}}
.back-link:hover{{background:var(--soft);color:var(--ink)}}
.article{{max-width:720px;margin:0 auto;padding:48px 24px 80px}}
.eyebrow{{font-family:var(--mono);font-size:11px;letter-spacing:0.22em;color:var(--accent);text-transform:uppercase;margin-bottom:24px;display:flex;align-items:center;gap:12px}}
.eyebrow::before{{content:'';width:28px;height:1px;background:var(--accent)}}
h1.main{{font-family:var(--display);font-size:clamp(34px,5vw,52px);font-weight:500;line-height:1.05;letter-spacing:-0.02em;margin-bottom:14px;font-variation-settings:"opsz" 144}}
.subtitle{{font-family:var(--display);font-size:clamp(18px,2.3vw,22px);font-weight:400;font-style:italic;color:var(--muted);line-height:1.4;margin-bottom:36px}}
.meta{{display:flex;gap:14px;font-family:var(--mono);font-size:11px;letter-spacing:.06em;color:var(--muted);padding-bottom:28px;margin-bottom:36px;border-bottom:0.5px solid var(--line-2)}}
.body h2{{font-family:var(--display);font-size:28px;font-weight:500;letter-spacing:-0.015em;line-height:1.2;margin:42px 0 16px}}
.body h3{{font-family:var(--display);font-size:21px;font-weight:500;line-height:1.25;margin:28px 0 10px;color:var(--ink)}}
.body p{{margin-bottom:18px;font-size:17px;line-height:1.75;color:var(--ink)}}
.body p strong{{color:var(--ink);font-weight:500}}
.body ul,.body ol{{margin:0 0 22px 22px}}
.body li{{margin-bottom:9px;line-height:1.65}}
.body blockquote{{margin:24px 0;padding:18px 22px;background:rgba(168,136,76,.08);border-left:3px solid var(--brass);border-radius:4px;font-style:italic;color:var(--ink)}}
.body blockquote p{{margin:0;font-size:16px}}
.body table{{width:100%;border-collapse:collapse;margin:24px 0;font-size:14.5px}}
.body table thead{{background:var(--soft)}}
.body table th{{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:10px 12px;text-align:left;border-bottom:1px solid var(--line-2);font-weight:500}}
.body table td{{padding:10px 12px;border-bottom:0.5px solid var(--line);vertical-align:top}}
.body a{{color:var(--accent);text-decoration:underline;text-decoration-thickness:0.5px;text-underline-offset:3px}}
.tags{{display:flex;flex-wrap:wrap;gap:6px;margin-top:32px;padding-top:24px;border-top:0.5px solid var(--line-2)}}
.tag{{font-family:var(--mono);font-size:10px;padding:3px 9px;background:var(--soft);border-radius:99px;color:var(--muted);letter-spacing:.04em}}
.alt-titles{{margin-top:48px;padding:20px;background:var(--softer);border-radius:6px;font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.04em}}
.alt-titles div{{margin-bottom:6px}}
.alt-titles strong{{color:var(--ink);font-weight:500}}
.source-attr{{margin-top:24px;font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.05em}}
.source-attr a{{color:var(--muted);text-decoration:none;opacity:.7}}
.source-attr a:hover{{opacity:1;color:var(--ink)}}
footer{{border-top:0.5px solid var(--line-2);padding:28px 24px;background:var(--soft)}}
.foot-inner{{max-width:720px;margin:0 auto;display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;font-family:var(--mono);font-size:10px;letter-spacing:.1em;color:var(--muted)}}
.foot-inner a{{color:var(--muted);text-decoration:none;text-transform:uppercase}}
.foot-inner a:hover{{color:var(--ink)}}
</style>
</head>
<body>
<div class="topbar">
  <a href="../../index.html" class="brand">POIN<b>·</b>TRADE</a>
  <a href="../" class="back-link">← До новин</a>
</div>
<article class="article">
  <div class="eyebrow">✦ Поглиблений розбір</div>
  <h1 class="main">{title}</h1>
  <p class="subtitle">{subtitle}</p>
  <div class="meta">
    <span>{date}</span>
    <span>•</span>
    <span>{wc} слів · ~{read_min} хв читання</span>
  </div>
  <div class="body">
{body}
  </div>
  <div class="tags">{tags_html}</div>
  <div class="source-attr">Першоджерело: <a href="{source_url}" target="_blank" rel="noopener">{source_name} ↗</a></div>
  <div class="alt-titles">
    <div><strong>Альтернативні заголовки (для тестування):</strong></div>
    {alt_titles_html}
  </div>
</article>
<footer>
  <div class="foot-inner">
    <a href="../../index.html">POIN<b style="color:var(--accent)">·</b>TRADE</a>
    <a href="../">← Усі новини</a>
  </div>
</footer>
</body>
</html>"""


def render_html(data: dict, story: dict | None) -> str:
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in (data.get("tags") or [])[:5])
    alt_titles_html = "".join(f'<div>· {t}</div>' for t in (data.get("title_alternatives") or [])[:3])
    wc = data.get("word_count", 1000)
    read_min = max(1, round(wc / 220))
    pub = (story or {}).get("published") or datetime.now().isoformat()
    return HTML_TEMPLATE.format(
        title=data.get("title_main", "Без заголовка"),
        subtitle=data.get("title_sub", ""),
        date=pub[:10],
        wc=wc,
        read_min=read_min,
        body=data.get("body_html", ""),
        tags_html=tags_html,
        alt_titles_html=alt_titles_html,
        tldr=data.get("tldr", ""),
        source_url=(story or {}).get("link") or (story or {}).get("source_url") or "#",
        source_name=(story or {}).get("source") or "оригінал",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="story id (12-char hash)")
    ap.add_argument("--title", help="пошук за частиною заголовка")
    ap.add_argument("--manual", help="формат: 'Заголовок | Текст джерела'")
    ap.add_argument("--source", default="вручну", help="назва джерела для --manual")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not any([args.id, args.title, args.manual]):
        print(__doc__)
        sys.exit(0)

    story = None
    story_file = None

    if args.manual:
        if "|" not in args.manual:
            print("❌ Формат --manual: 'Заголовок | Текст джерела'")
            sys.exit(1)
        title, body = args.manual.split("|", 1)
        title, body = title.strip(), body.strip()
        source_name = args.source
        pub_date = datetime.now().isoformat()
        source_url = ""
        slug_base = title
    else:
        found = find_story(args.id or args.title, by_id=bool(args.id))
        if not found:
            print(f"❌ Стаття не знайдена: {args.id or args.title}")
            sys.exit(1)
        story, story_file = found
        title = story.get("title_uk") or story.get("title") or story.get("title_orig", "")
        body = story.get("body_orig") or story.get("summary_uk") or story.get("summary", "")
        source_name = story.get("source", "")
        pub_date = story.get("published", "")
        source_url = story.get("link") or story.get("source_url", "")
        slug_base = title
        print(f"📥 Знайдено: {title[:80]}")
        print(f"   у файлі: {story_file.name}")

    data = generate(title, body, source_name, pub_date)

    if args.verbose:
        print("\n--- AI VERDICT ---")
        print(json.dumps({k: v for k, v in data.items() if k != "body_html"}, ensure_ascii=False, indent=2))

    # Save HTML
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = (pub_date or datetime.now().isoformat())[:10]
    slug = f"{date_str}-{slugify(slug_base)}"
    out_path = INSIGHTS_DIR / f"{slug}.html"
    html = render_html(data, story)
    out_path.write_text(html, encoding="utf-8")

    print(f"\n✅ Saved: {out_path}")
    print(f"   URL: /news/insights/{slug}.html")

    # Update story in data file
    if story and story_file:
        stories = json.loads(story_file.read_text(encoding="utf-8"))
        for i, s in enumerate(stories):
            if s.get("id") == story.get("id"):
                stories[i]["deep_article_url"] = f"/news/insights/{slug}.html"
                stories[i]["deep_article_title"] = data.get("title_main")
                stories[i]["deep_article_tldr"] = data.get("tldr")
                stories[i]["deep_article_word_count"] = data.get("word_count")
                break
        story_file.write_text(json.dumps(stories, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   ✓ Оновлено {story_file.name} з deep_article_url")


if __name__ == "__main__":
    main()
