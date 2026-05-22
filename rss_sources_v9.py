"""
RSS sources для pointrade.business/news — pipeline v9
Заміна для FEEDS у rss_collector.py

Структура: (url, market_tag, language, source_name, priority, niche)
- market_tag: ua, pl, ro, tr, eu, global
- priority: 1 (must-have) / 2 (regular) / 3 (опціональний)
- niche: general, distribution, fmcg, customs, tech (опціонально)

Перед production: запустити validate_feeds (rss_collector_v9.py --test).

ОНОВЛЕННЯ 2026-05-22:
- Додано блок DISTRIBUTION & CATEGORY MANAGEMENT (AllRetail, RAU, wiadomoscihandlowe)
- Прибрано непрацюючі Reuters/FT — замінено на робочі альтернативи
- Додано mind.ua, AIN.UA вже на priority=1
"""

RSS_FEEDS = [
    # ==================== EUROPE / GLOBAL — ядро ====================
    ("https://www.politico.eu/feed/",                            "eu",     "en", "Politico Europe",            1, "general"),
    ("https://www.euronews.com/business/rss",                    "eu",     "en", "Euronews Business",          2, "general"),
    ("https://sifted.eu/feed",                                   "eu",     "en", "Sifted (FT-backed)",         1, "tech"),
    ("https://www.eu-startups.com/feed/",                        "eu",     "en", "EU-Startups",                2, "tech"),
    ("https://siliconcanals.com/feed/",                          "eu",     "en", "Silicon Canals",             3, "tech"),

    # ==================== POLAND ====================
    ("https://forsal.pl/rss.xml",                                "pl",     "pl", "Forsal",                     1, "general"),
    ("https://www.bankier.pl/rss/wiadomosci.xml",                "pl",     "pl", "Bankier — wiadomości",       1, "general"),
    ("https://www.bankier.pl/rss/wiadomosci-gospodarcze.xml",    "pl",     "pl", "Bankier — gospodarka",       1, "general"),
    ("https://www.pb.pl/rss",                                    "pl",     "pl", "Puls Biznesu",               1, "general"),
    ("https://businessinsider.com.pl/.feed",                     "pl",     "pl", "Business Insider Polska",    2, "general"),
    ("https://300gospodarka.pl/feed",                            "pl",     "pl", "300Gospodarka",              2, "general"),
    ("https://www.money.pl/rss/wiadomosci.xml",                  "pl",     "pl", "Money.pl",                   2, "general"),

    # ==================== UKRAINE ====================
    ("https://www.liga.net/biznes/rss.xml",                      "ua",     "uk", "Liga Business",              1, "general"),
    ("https://biz.nv.ua/ukr/rss/all.xml",                        "ua",     "uk", "NV Business",                1, "general"),
    ("https://forbes.ua/rss",                                    "ua",     "uk", "Forbes Ukraine",             1, "general"),
    ("https://mind.ua/rss",                                      "ua",     "uk", "mind.ua",                    1, "general"),
    ("https://www.epravda.com.ua/rss/",                          "ua",     "uk", "Економічна Правда",          1, "general"),
    ("https://ain.ua/feed/",                                     "ua",     "uk", "AIN.UA (tech/startups)",     1, "tech"),
    ("https://speka.media/rss",                                  "ua",     "uk", "SPEKA",                      2, "tech"),
    ("https://mc.today/feed/",                                   "ua",     "uk", "MC.today",                   2, "general"),
    ("https://kyivindependent.com/feed/",                        "ua",     "en", "Kyiv Independent",           2, "general"),
    ("https://thepage.ua/rss",                                   "ua",     "uk", "The Page",                   2, "general"),
    ("https://biz.liga.net/all/rss.xml",                         "ua",     "uk", "Liga.Бізнес",                1, "general"),

    # ==================== TURKEY ====================
    ("https://www.dailysabah.com/rss/category/business",         "tr",     "en", "Daily Sabah Business",       1, "general"),
    ("https://www.hurriyetdailynews.com/rss/economy",            "tr",     "en", "Hurriyet Daily News",        1, "general"),
    ("https://www.aa.com.tr/en/rss/default?cat=economy",         "tr",     "en", "Anadolu Agency EN",          1, "general"),
    ("https://www.aa.com.tr/tr/rss/default?cat=ekonomi",         "tr",     "tr", "Anadolu Ajansı TR",          2, "general"),
    ("https://www.trtworld.com/rss/business.rss",                "tr",     "en", "TRT World Business",         2, "general"),

    # ==================== ROMANIA ====================
    ("https://www.zf.ro/rss",                                    "ro",     "ro", "Ziarul Financiar",           1, "general"),
    ("https://www.bursa.ro/rss/index.xml",                       "ro",     "ro", "Bursa",                      1, "general"),
    ("https://economica.net/feed/",                              "ro",     "ro", "Economica.net",              2, "general"),
    ("https://www.business-review.eu/feed",                      "ro",     "en", "Business Review Romania",    1, "general"),
    ("https://www.romania-insider.com/rss.xml",                  "ro",     "en", "Romania Insider",            2, "general"),

    # ==================== PRIVATE LABEL / FMCG / MANUFACTURING ====================
    ("https://www.privatelabelmag.com/feed/",                    "global", "en", "Private Label Magazine",     2, "fmcg"),
    ("https://www.cleanlink.com/rss/news.xml",                   "global", "en", "CleanLink (cleaning industry)", 3, "fmcg"),
    ("https://www.fmcgnews.com/feed/",                           "global", "en", "FMCG News",                  3, "fmcg"),

    # ==================== DISTRIBUTION & CATEGORY MANAGEMENT ====================
    # Нова рубрика для кейсів дистрибуції, KPI команд, переговорів з мережами,
    # category management, мотивації ТП, роботи з байєрами.
    ("https://rau.ua/feed/",                                     "ua",     "uk", "RAU (Retail Association UA)", 1, "distribution"),
    ("https://allretail.ua/feed/",                               "ua",     "uk", "AllRetail.ua",                1, "distribution"),
    ("https://retailers.ua/feed",                                "ua",     "uk", "Retailers.ua",                1, "distribution"),
    ("https://www.wiadomoscihandlowe.pl/rss",                    "pl",     "pl", "Wiadomości Handlowe (PL)",   1, "distribution"),
    ("https://www.portalspozywczy.pl/rss/wiadomosci.xml",        "pl",     "pl", "Portal Spożywczy (PL)",      1, "distribution"),
    ("https://www.dlahandlu.pl/rss/all.xml",                     "pl",     "pl", "Dla Handlu (PL)",            2, "distribution"),
    ("https://www.modernretail.com/feed/",                       "global", "en", "Modern Retail",              2, "distribution"),
    ("https://www.retaildive.com/feeds/news/",                   "global", "en", "Retail Dive",                2, "distribution"),
    ("https://www.progressivegrocer.com/rss.xml",                "global", "en", "Progressive Grocer",         3, "distribution"),
]


# ============== ПРАВИЛА ВИКОРИСТАННЯ У PIPELINE ==============
# 1. У rss_collector_v9.py імпорт:
#       from rss_sources_v9 import RSS_FEEDS
#
# 2. Loop:
#       for url, market, lang, name, priority, niche in RSS_FEEDS:
#           if priority > MAX_PRIORITY: continue
#           feed = feedparser.parse(url)
#           for entry in feed.entries[:per_feed_limit]:
#               draft = {
#                   "source_name": name,
#                   "source_url": entry.link,
#                   "market": market,
#                   "source_lang": lang,
#                   "niche": niche,            # для попереднього тегу
#                   "title_orig": entry.title,
#                   ...
#               }
#
# 3. У AI-prompt: передавати source_lang і обов'язкову мову виходу (uk).
#
# 4. ДЕДУПЛІКАЦІЯ: за source_url або md5(title+link).
#
# 5. БАЛАНСУВАННЯ:
#    MAX_DRAFTS_PER_RUN=30 → беріть max 8 з одного джерела;
#    гарантуйте мінімум 3 з niche=distribution якщо є — це новий
#    стратегічний контент-вектор.
#
# ============== ПРИОРИТЕТНОСТЬ ==============
# priority=1 (24 джерела): обов'язково в кожен запуск
# priority=2 (14 джерел): додавати якщо priority=1 не дав достатньо
# priority=3 ( 4 джерела): фолбек / нішеві теми
#
# ============== ВАЛІДАЦІЯ ==============
# python3 rss_collector_v9.py --test
# Якщо URL вертає 404/403 — закоментуйте рядок і додайте # DEAD: дата
