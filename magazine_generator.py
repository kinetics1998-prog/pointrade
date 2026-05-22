   #!/usr/bin/env python3
"""
📰 BIZ DIGEST — Magazine Generator v3
- Claude API выжимки статей
- Кликабельные рубрики
- Inline-кнопка в Telegram
- Лого в обложке
"""

import json, os, re, sys, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DATA_DIR = Path(__file__).parent / "data"
MAGAZINE_DIR = Path(__file__).parent / "magazines"
GITHUB_PAGES_URL = os.environ.get("GITHUB_PAGES_URL", "")

RUBRICS = {
    "business":   {"name": "БІЗНЕС",      "color": "#c44536"},
    "money":      {"name": "ГРОШІ",       "color": "#1d9e75"},
    "tech":       {"name": "ТЕХНОЛОГІЇ",   "color": "#185fa5"},
    "psychology": {"name": "ПСИХОЛОГІЯ",   "color": "#7b4e8a"},
    "markets":    {"name": "РИНКИ",        "color": "#854f0b"},
    "lifehacks":  {"name": "ЛАЙФХАКИ",     "color": "#3b6d11"},
}

RUBRIC_KEYWORDS = {
    "money": ["грн","гривн","долар","євро","курс","банк","кредит","інвестиц","накопич","фінанс","оренд","ціни","подорож","бюджет","зарплат","пенсі"],
    "tech": ["google","ai","штучн","інтелект","gemini","claude","стартап","додаток","застосунок","кібер","wordpress","дрон","цифров","програм","software","tech"],
    "psychology": ["кадров","мотивац","команд","лідер","кар'єр","психолог","втом","стрес","баланс","вигоран","жінок","жінки","робоч"],
    "markets": ["ринок","ринки","аналітик","млрд","млн","зростан","експорт","імпорт","агросектор","прибут","виробництв","холдинг","індекс","інфляц"],
    "lifehacks": ["лайфхак","порад","як ","секрет","спосіб","корисн","продуктивн","ефективн","правил","помилк"],
    "business": ["компанія","бізнес","підприєм","бренд","маркет","продаж","клієнт","партнер","угод","засновник","CEO","ресторан","магазин"],
}


def detect_rubric(article):
    text = (article.get("title","") + " " + article.get("summary","")).lower()
    scores = {}
    for rubric, keywords in RUBRIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0: scores[rubric] = score
    if scores: return max(scores, key=scores.get)
    cat = article.get("category","")
    if cat in ("UA_TECH","WORLD_TECH"): return "tech"
    if cat == "UA_ECON": return "markets"
    return "business"


def clean_html(text):
    text = re.sub(r'<[^>]+>', '', text)
    for old, new in [("&amp;","&"),("&#8217;","'"),("&#38;","&"),("&nbsp;"," "),("&quot;",'"')]:
        text = text.replace(old, new)
    return text.replace("\n"," ").strip()


def fetch_article_text(url):
    """Забирает текст статьи с сайта."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BizDigest/1.0)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # Убираем скрипты, стили
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:3000]  # Макс 3000 символов для API
    except Exception as e:
        print(f"  Fetch error {url}: {e}")
        return ""


def summarize_with_claude(title, article_text):
    """Делает выжимку через Claude API."""
    if not ANTHROPIC_API_KEY or not article_text:
        return ""

    prompt = f"""Ти — редактор бізнес-дайджесту для українських підприємців.

Стаття: "{title}"
Текст: {article_text[:2500]}

Напиши коротку виважку (3-4 речення, максимум 400 символів) українською мовою. Тільки суть — що сталося, чому це важливо для бізнесу, що робити. Без вступів, без "У статті йдеться". Пиши як Bloomberg — сухо, чітко, по факту."""

    data = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            text = result.get("content", [{}])[0].get("text", "")
            return text.strip()
    except Exception as e:
        print(f"  Claude API error: {e}")
        return ""


def select_articles(articles, count=7):
    for a in articles: a["_rubric"] = detect_rubric(a)
    seen, top = set(), []
    for target in ["business","money","tech","psychology","markets","lifehacks"]:
        for a in articles:
            if a["_rubric"] == target and target not in seen:
                top.append(a); seen.add(target); break
    for a in articles:
        if len(top) >= count: break
        if a not in top: top.append(a)
    return top[:count]


def enrich_articles(articles):
    """Добавляет AI-выжимки к статьям."""
    if not ANTHROPIC_API_KEY:
        print("No API key, skipping summaries")
        return articles

    print("Generating AI summaries...")
    for i, a in enumerate(articles):
        title = clean_html(a["title"])
        print(f"  [{i+1}/{len(articles)}] {title[:50]}...")

        # Сначала пробуем забрать текст с сайта
        full_text = fetch_article_text(a["link"])

        if full_text:
            summary = summarize_with_claude(title, full_text)
        else:
            # Фолбек: используем RSS-описание
            rss_text = clean_html(a.get("summary", ""))
            if rss_text:
                summary = summarize_with_claude(title, rss_text)
            else:
                summary = ""

        if summary:
            a["ai_summary"] = summary
            print(f"    OK: {summary[:60]}...")
        else:
            a["ai_summary"] = clean_html(a.get("summary", ""))[:200]
            print(f"    Fallback to RSS summary")

    return articles


def render_card(article, index):
    r = RUBRICS.get(article.get("_rubric","business"), RUBRICS["business"])
    title = clean_html(article["title"])
    summary = article.get("ai_summary", clean_html(article.get("summary","")))[:400]
    source = article["source"].replace("\U0001f1fa\U0001f1e6 ","").replace("\U0001f30d ","")
    link = article["link"]
    rubric_id = article.get("_rubric","business")
    bg = "#faf8f5" if index % 2 == 1 else "#ffffff"

    first = 'border-radius:10px 10px 0 0;margin-top:0;' if index == 1 else ''
    last = 'border-radius:0 0 10px 10px;' if index == 7 else ''
    border_top = '' if index == 1 else 'border-top:0.5px solid rgba(0,0,0,0.06);'

    return f'''<article id="r-{rubric_id}" style="background:{bg};border-left:3px solid {r['color']};padding:20px 20px 20px 24px;{first}{last}{border_top}">
<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:6px;">
<span style="font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:{r['color']};">{r['name']}</span>
<span style="font-size:10px;color:#999;">{index:02d}</span></div>
<h2 style="font-family:'Playfair Display',Georgia,serif;font-size:17px;font-weight:700;line-height:1.32;color:#1a1a1a;margin-bottom:8px;">{title}</h2>
<p style="font-size:13.5px;line-height:1.7;color:#444;margin-bottom:12px;">{summary}</p>
<div style="display:flex;justify-content:space-between;align-items:center;padding-top:8px;border-top:1px solid rgba(0,0,0,0.05);">
<a href="{link}" style="font-size:12px;font-weight:700;color:{r['color']};text-decoration:none;" target="_blank">Джерело →</a>
<span style="font-size:11px;color:#aaa;">{source}</span></div>
</article>'''


def generate_magazine(articles, top_articles):
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    days = ["Понеділок","Вівторок","Середа","Четвер","П'ятниця","Субота","Неділя"]
    edition = "Ранковий випуск" if now.hour < 14 else "Вечірній випуск"

    rubric_set = list(dict.fromkeys(a.get("_rubric","business") for a in top_articles))

    # Кликабельные рубрики
    pills = ""
    for rkey in ["business","money","tech","psychology","markets","lifehacks"]:
        if rkey in rubric_set:
            r = RUBRICS[rkey]
            pills += f'<a href="#r-{rkey}" style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;padding:6px 14px;color:#c8d6e5;border:0.5px solid #445;text-decoration:none;transition:background 0.2s;" onmouseover="this.style.background=\'rgba(255,255,255,0.1)\'" onmouseout="this.style.background=\'transparent\'">{r["name"]}</a>'

    cards = "".join(render_card(a, i) for i, a in enumerate(top_articles, 1))

    # SVG лого (вариант 6 — геометрический B)
    logo_svg = '''<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="8" cy="8" r="3" fill="#f5ebe0"/><circle cx="20" cy="4" r="2.5" fill="#f5ebe0"/>
<circle cx="32" cy="8" r="3" fill="#f5ebe0"/><circle cx="8" cy="20" r="2.5" fill="#f5ebe0"/>
<circle cx="20" cy="20" r="3" fill="#f5ebe0"/><circle cx="32" cy="20" r="2.5" fill="#f5ebe0"/>
<circle cx="8" cy="32" r="3" fill="#f5ebe0"/><circle cx="20" cy="36" r="2.5" fill="#f5ebe0"/>
<circle cx="32" cy="32" r="3" fill="#f5ebe0"/>
<line x1="8" y1="8" x2="20" y2="4" stroke="#f5ebe0" stroke-width="0.8" opacity="0.4"/>
<line x1="20" y1="4" x2="32" y2="8" stroke="#f5ebe0" stroke-width="0.8" opacity="0.4"/>
<line x1="8" y1="8" x2="8" y2="20" stroke="#f5ebe0" stroke-width="0.8" opacity="0.4"/>
<line x1="32" y1="8" x2="32" y2="20" stroke="#f5ebe0" stroke-width="0.8" opacity="0.4"/>
<line x1="8" y1="8" x2="20" y2="20" stroke="#f5ebe0" stroke-width="0.8" opacity="0.3"/>
<line x1="32" y1="8" x2="20" y2="20" stroke="#f5ebe0" stroke-width="0.8" opacity="0.3"/>
<line x1="8" y1="20" x2="20" y2="20" stroke="#f5ebe0" stroke-width="0.8" opacity="0.4"/>
<line x1="20" y1="20" x2="32" y2="20" stroke="#f5ebe0" stroke-width="0.8" opacity="0.4"/>
<line x1="8" y1="20" x2="8" y2="32" stroke="#f5ebe0" stroke-width="0.8" opacity="0.4"/>
<line x1="32" y1="20" x2="32" y2="32" stroke="#f5ebe0" stroke-width="0.8" opacity="0.4"/>
<line x1="8" y1="32" x2="20" y2="36" stroke="#f5ebe0" stroke-width="0.8" opacity="0.4"/>
<line x1="20" y1="36" x2="32" y2="32" stroke="#f5ebe0" stroke-width="0.8" opacity="0.4"/>
<line x1="8" y1="20" x2="20" y2="20" stroke="#f5ebe0" stroke-width="0.8" opacity="0.3"/>
<line x1="20" y1="20" x2="8" y2="32" stroke="#f5ebe0" stroke-width="0.8" opacity="0.3"/>
<line x1="20" y1="20" x2="32" y2="32" stroke="#f5ebe0" stroke-width="0.8" opacity="0.3"/>
</svg>'''

    return f'''<!DOCTYPE html>
<html lang="uk"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BIZ DIGEST — {date_str}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#f0ece6;font-family:'DM Sans',system-ui,sans-serif;-webkit-font-smoothing:antialiased}}article+article{{border-top:0.5px solid rgba(0,0,0,0.06)}}html{{scroll-behavior:smooth}}@media(max-width:480px){{article{{padding:16px 16px 16px 20px!important}}h2{{font-size:15px!important}}}}</style></head>
<body>
<header style="background:#1b2838;color:#f5ebe0;padding:2.5rem 1.5rem;text-align:center;border-radius:0 0 16px 16px;">
<div style="display:flex;justify-content:center;margin-bottom:12px;">{logo_svg}</div>
<div style="font-size:10px;letter-spacing:0.3em;text-transform:uppercase;color:#5a6a7a;margin-bottom:14px;">Business digest for entrepreneurs</div>
<h1 style="font-family:'Playfair Display',serif;font-size:clamp(2.2rem,8vw,3.5rem);font-weight:900;line-height:1.05;">BIZ DIGEST</h1>
<p style="font-family:'Playfair Display',serif;font-size:14px;font-style:italic;color:#8899aa;margin-top:6px;">{edition}</p>
<p style="font-size:11px;color:#556;margin-top:14px;">{days[now.weekday()]}, {date_str} · {len(articles)} матеріалів</p>
<nav style="display:flex;flex-wrap:wrap;justify-content:center;gap:0;margin-top:18px;">{pills}</nav>
</header>
<main style="max-width:640px;margin:0 auto;padding:14px 12px 2rem;">{cards}</main>
<footer style="text-align:center;padding:1.5rem 1rem 2.5rem;">
<div style="font-size:2.5rem;font-weight:900;color:#1b2838;">{len(articles)}</div>
<div style="font-family:'Playfair Display',serif;font-style:italic;color:#888;font-size:14px;margin-top:4px;">матеріалів зібрано сьогодні</div>
<div style="font-size:10px;color:#aaa;letter-spacing:0.15em;text-transform:uppercase;margin-top:16px;">BIZ DIGEST · {date_str}</div>
</footer></body></html>'''


def send_telegram_button(text, url):
    """Отправка с inline-кнопкой."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return

    keyboard = json.dumps({
        "inline_keyboard": [[
            {"text": "📰 Відкрити журнал", "url": url}
        ]]
    })

    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": keyboard,
        "disable_web_page_preview": "true",
    }).encode()

    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            r = json.loads(resp.read())
            if r.get("ok"): print("Telegram: OK (with button)")
    except Exception as e:
        print(f"Telegram: {e}")


def send_telegram_text(text):
    """Обычная текстовая отправка."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    data = urllib.parse.urlencode({"chat_id":TELEGRAM_CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":"true"}).encode()
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            r = json.loads(resp.read())
            if r.get("ok"): print("Telegram: OK")
    except Exception as e:
        print(f"Telegram: {e}")


def morning_mode(articles):
    """Утро: AI-выжимки + журнал + кнопка в Telegram."""
    top = select_articles(articles, 7)
    top = enrich_articles(top)

    html = generate_magazine(articles, top)
    MAGAZINE_DIR.mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime("%Y-%m-%d") + ".html"
    (MAGAZINE_DIR / filename).write_text(html, encoding="utf-8")
    print(f"Magazine: {MAGAZINE_DIR / filename}")

    repo = os.environ.get("GITHUB_REPOSITORY","kinetics1998-prog/biz-digest")
    if GITHUB_PAGES_URL:
        url = f"{GITHUB_PAGES_URL}/magazines/{filename}"
    else:
        url = f"https://{repo.split('/')[0]}.github.io/{repo.split('/')[1]}/magazines/{filename}"

    date_str = datetime.now().strftime("%d.%m.%Y")
    text = f"Доброго ранку.\n\n<b>BIZ DIGEST</b> · {date_str}\n\n{len(articles)} матеріалів з {len(set(a['source'] for a in articles))} джерел\nВиважки від AI — читай суть без реклами"

    send_telegram_button(text, url)


def evening_mode(articles):
    """Вечер: 2 топ-новости текстом."""
    for a in articles: a["_rubric"] = detect_rubric(a)
    biz = [a for a in articles if a["_rubric"] in ("business","money","markets")]
    if len(biz) < 2: biz = articles
    top2 = biz[:2]

    lines = ["<b>BIZ DIGEST</b> · вечірнє\n"]
    for a in top2:
        title = clean_html(a["title"])
        summary = clean_html(a.get("summary",""))[:150]
        if len(summary) >= 150: summary = summary[:summary.rfind(" ")] + "..."
        r = RUBRICS.get(a.get("_rubric","business"), RUBRICS["business"])
        source = a["source"].replace("\U0001f1fa\U0001f1e6 ","").replace("\U0001f30d ","")
        lines.append(f"<b>{r['name']}</b>\n{title}\n<i>{summary}</i>\n<a href=\"{a['link']}\">Читати →</a> · {source}\n")

    send_telegram_text("\n".join(lines))


def main():
    data_files = sorted(DATA_DIR.glob("202*.json"), reverse=True)
    if not data_files: print("No data"); sys.exit(1)
    articles = json.loads(data_files[0].read_text(encoding="utf-8"))
    if not articles: print("Empty"); sys.exit(1)
    print(f"Articles: {len(articles)}")

    mode = "morning"
    if "--evening" in sys.argv: mode = "evening"
    elif "--morning" in sys.argv: mode = "morning"
    else: mode = "morning" if datetime.now().hour < 14 else "evening"

    if mode == "morning":
        morning_mode(articles)
    else:
        evening_mode(articles)


if __name__ == "__main__":
    main()
