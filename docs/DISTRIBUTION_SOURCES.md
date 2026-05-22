# Звідки брати кейси про дистрибуцію, KPI ТП, мотивацію байєрів, category management

Версія: 2026-05-22
Контекст: бізнесу читачів Pointrade цікаві кейси про:
- KPI польових команд (торгові представники, мерчандайзери)
- Мотивацію байєрів і робота з мережами
- Управління категорією і полицею (category management)
- Trade-маркетинг і промо-акції
- Переговори з рітейлерами (Біла Книга / Joint Business Plan)

---

## 1. УКРАЇНСЬКІ ДЖЕРЕЛА (priority=1)

### RSS (підключено в rss_sources_v9.py)
| Джерело | URL | Що дає |
|---|---|---|
| **RAU** (Retail Association of Ukraine) | `rau.ua/feed/` | Звіти ринку, інтерв'ю КАМів, конференції |
| **AllRetail.ua** | `allretail.ua/feed/` | Розбори кейсів АТБ/Сільпо/Новус/Метро |
| **Retailers.ua** | `retailers.ua/feed` | Новини мереж, рейтинги, аналітика |

### Без RSS (треба парсинг або ручний моніторинг)
- **Trade-marketing UA** (Facebook-група, ~12K учасників) — реальні кейси промо
- **Forbes Ukraine рубрика «Бізнес»** — інтерв'ю CEO мереж
- **mind.ua** (вже є) — регулярні розбори FMCG/HoReCa
- **NACS Ukraine** (Асоціація рітейлерів і постачальників) — звіти, white papers

### Telegram (треба парсер @username → канал → RSS через bridges)
- `@rauretail` — RAU офіційний
- `@retailersUA` — щоденні апдейти мереж
- `@ekonomicheskaya` — макроекономіка з прицілом на ритейл
- `@sales_for_real` — практика B2B-продажів, кейси
- `@kam_diary` — щоденник КАМа (категорійних/ключових менеджерів)

### Подкасти (треба транскрибувати в текст)
- **«Що з рітейлом»** (RAU) — щотижневі випуски, реальні CEO мереж
- **«Кар'єра у FMCG»** (Forbes Ukraine) — інтерв'ю керівників

### Конференції / звіти (треба моніторити сайти)
- **RAU Summit** (раз на рік) — найбільший івент, є презентації PDF
- **Nielsen IQ Ukraine** quarterly reports — безкоштовні summary
- **GfK Ukraine** — споживчі панелі, місячні дайджести

---

## 2. ПОЛЬСЬКІ ДЖЕРЕЛА (priority=1, паралель для Марека)

### RSS (підключено)
| Джерело | URL | Що дає |
|---|---|---|
| **Wiadomości Handlowe** | `wiadomoscihandlowe.pl/rss` | Найдетальніший рітейл-портал PL |
| **Portal Spożywczy** | `portalspozywczy.pl/rss/wiadomosci.xml` | FMCG/продовольство |
| **Dla Handlu** | `dlahandlu.pl/rss/all.xml` | Категорійка, переговори |

### Без RSS
- **Reach Local** PL — case studies промо-кампаній
- **GS1 Polska** — стандарти даних про товар, GDSN
- **GfK Polonia** quarterly

---

## 3. ЕКСПЕРТНІ ГОЛОСИ (LinkedIn / Substack — треба моніторити вручну)

### Україна
- **Дмитро Ткаченко** — KAM-консультант, ex-Coca-Cola, ex-Carlsberg. Пише про переговори з мережами.
- **Олександр Сорока** — категорійний менеджмент, працював в АТБ
- **Олена Гуцал** — trade-маркетинг, ex-Henkel
- **Євген Чичваркін** (хоч і не UA) — кейси Euroset/HEMA, цитується експертами

### Польща / EU
- **Krzysztof Cybruch** — ex-Biedronka, тепер consultant. LinkedIn активний.
- **Piotr Patkowski** — Trade Marketing Network, кейси промо в PL.

### Глобально
- **Tom Mulroy** — Category Management Association (CMA), США. Стандарти.
- **Steve Boal** — Quotient → Inmar. Промо-аналітика.

---

## 4. КНИГИ І СТАНДАРТИ (для фундаменту контенту)

### Базові
- "Category Management Principles" — Singh & Blattberg (UK)
- "Retail Management" — Levy/Weitz (US, 12+ edition)
- "ECR Best Practices" — Efficient Consumer Response (EU стандарт)

### Українські переклади
- "Управління продажами" — Барбара Джефрі Сміт (Ranok)
- "Trade marketing" — Анатолій Хитров (KSE Press)

### Глобальні бенчмарки
- **GS1 Global** — стандарти даних про товар
- **EHI Retail Institute** (DE) — KPI бенчмарки рітейлу
- **NACS** (US convenience) — KPI ТП у каналі c-store

---

## 5. ЯК ЦЕ ВМОНТУВАТИ В PIPELINE

### Крок 1. RSS (вже зроблено)
У `rss_sources_v9.py` додано блок DISTRIBUTION з niche="distribution":
- RAU, AllRetail, Retailers.ua (UA)
- Wiadomości Handlowe, Portal Spożywczy, Dla Handlu (PL)
- Modern Retail, Retail Dive, Progressive Grocer (global)

### Крок 2. AI-промпт (вже зроблено)
У `ai_prompt_v9.py`:
- Додано 4-й персонаж `category_manager` у `what_it_means`
- Додано теги: `дистрибуція`, `переговори-з-мережами`, `KPI-команди`,
  `категорійний-менеджмент`, `трейд-маркетинг`, `управління-полицею`,
  `мотивація-ТП`, `робота-з-байєрами`, `промо-акції`
- Додано `category: "distribution-case"` і `"category-management"`

### Крок 3. Frontend (наступний крок)
У `news/index.html` додати:
- Категорія-чіп "Дистрибуція" в фільтр
- Бейдж для distribution-case з іконкою 🚚
- Експандабельний блок "Що це означає для category manager"

### Крок 4. Окрема рубрика (через 4 тижні даних)
Коли назбирається 50+ кейсів — окрема сторінка `/news/distribution/` з:
- Архівом кейсів за категоріями (молочка, кава, побутова хімія...)
- Фільтрами по мережах (АТБ, Сільпо, Метро, Біла Книга, Biedronka, Lidl)
- "Кейс тижня" — найкращий розбір

---

## 6. КОНТЕНТ-СТРАТЕГІЯ (як перетворити news у insights)

Не просто переказувати чужі кейси — додавати **executable takeaways**:

❌ "АТБ змінила KPI байєрів" (просто новина)

✅ "АТБ перейшла на share-of-shelf KPI. Як скопіювати:
1. Формула: SOS_high_margin × growth × penalty_OOS
2. Дашборд в Power BI: 2 тижні впровадження
3. Очікуваний приріст маржі: +1.8 п.п. (досвід АТБ за 6 міс.)
4. Ризик: тиск на P1 бренди — закладіть trade-budget +15%"

Цей формат — те, за що читач готовий платити Member €49/міс
(згідно з ROI-таблицею в customs_section_plan.md).

---

## 7. ЩО НЕ РОБИТИ

- ❌ Платні джерела (ICIS, Mintel, Statista премум) — поки немає revenue
- ❌ Інтерв'ю напряму — це окремий контент-формат, потребує редактора
- ❌ Український переклад глобальних звітів без локалізації — це low-value
- ❌ Парсити LinkedIn без офіційного API — ризик блокування

---

## 8. KPI РУБРИКИ ДИСТРИБУЦІЇ (Q3 2026)

Цілі через 3 місяці після запуску:
- 50+ розборів кейсів у архіві
- 5+ постійних експертів-колумністів (LinkedIn + UA)
- 3+ партнерства з консалтингом (PROSAR, Promodo Retail)
- 25% від загального трафіку news/ йде на distribution-теги
- 8% конверсія в Telegram-підписку #дистрибуція
