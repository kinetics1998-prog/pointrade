# Pointrade — Roadmap

Дорожня карта на основі CEO-review (LIME-first → marketplace) + McKinsey-аналізу
ринку (ZYNT, agentic commerce, closed networks). Локнуті стратегічні рішення:

- **Premise:** приватна торгова мережа 20-50 перевірених партнерів, не open marketplace
- **Markets:** UA / PL / RO / TR (4 країни)
- **Anchor:** LIME як перший якірний бренд, інші партнери приєднуються поетапно
- **AI-matching path:** реальний Claude API pipeline (не fake numbers), запуск
  ТІЛЬКИ після 30+ заповнених профілів у БД
- **Design:** Mediterranean Trade Editorial v2 (warm cream + terracotta + brass +
  Fraunces + Geist) застосовано на 5 сторінок
- **Bot:** Biz Digest Bot (потребує rotation токену)

---

## Q2 2026 — Foundation (травень-червень)

**Метрика кварталу:** 30 заповнених профілів у `signal_profiles` + 5 реальних
B2B-контактів між партнерами через платформу.

### Технічно — закінчити що почато
- [x] 5 сторінок у єдиному дизайні з backend-зв'язкою
- [x] `leads` таблиця + `save_lead.php` працює
- [x] `signal_profiles` таблиця створена
- [ ] **Перезалити `save_profile.php` коректно** (зараз SQL замість PHP — див. TOMORROW.md)
- [ ] **Bot token rotation** + вписати у `signal_config.php`
- [ ] Smoke-test усіх 3 форм (waitlist на `/`, partner.html квіз, orbit/onboarding.html)

### Контентно — наповнити мережу
- [ ] Особисто запросити 30 з твоїх 20-50 партнерів заповнити onboarding
- [ ] Створити Telegram-групу "Pointrade members" (не канал — група для діалогу)
- [ ] Запостити 3-5 реальних дайджест-випусків через існуючий `biz-digest.py`

### Не робити цього кварталу
- Не запускати "AI-matching" поки не буде 30+ профілів — інакше повторюється
  trust-killer що ми вже виправили (фейкові цифри 17/23/31)
- Не починати Stripe інтеграцію
- Не додавати другий бренд у каталог поки LIME-каталог не приніс перших 5 контактів

---

## Q3 2026 — Turn on matching (липень-вересень)

**Метрика кварталу:** 10 реальних B2B-контактів через платформу + перший платний
Member.

### Технічно — AI pipeline
- [ ] Написати `orbit/match_lead.php` — Claude API matching по 30+ профілях
  - Prompt: "Користувач у ринку X шукає Y. Ось N профілів з БД. Поверни top-3
    з обґрунтуванням."
  - Output → `leads.matched_to` JSON
- [ ] Додати поле `companies.looking_for` / `offering` / `min_volume_eur` у
  `signal_profiles` якщо ще нема (треба перевірити schema)
- [ ] Інтегрувати ZYNT-style "buying signals" як bonus у match-результат:
  3-4 RSS-моніторинг на компанію (новини про неї, зміни на сайті)
  - Layer 1: WebSearch + RSS моніторинг
  - Layer 2: Claude API summary "що змінилось у компанії за тиждень"

### Backend — auth для members
- [ ] Простий login (email magic link) для `/orbit/dashboard.html`
- [ ] Member може бачити свої матчі + статус кожного

### Не робити
- Не додавати payment processor у backend (Stripe Hosted Checkout простіше)
- Не будувати API для зовнішніх інтеграцій

---

## Q4 2026 — Monetize не raise (жовтень-грудень)

**Метрика кварталу:** 20 платних Member × €29 = €580/міс recurring revenue.

### Монетизація
- [ ] Stripe Hosted Checkout для €29/міс Member
- [ ] Member-only фічі живі: дашборд матчів, member-чат у Telegram, інтро від куратора
- [ ] Cancellation flow (без darkPattern)

### Каталог — multi-brand
- [ ] PDF-парсер через Claude vision API (як написано в README)
- [ ] Завести 4-5 каталогів партнерів окрім LIME
- [ ] Кожен партнер отримує свій URL `/catalog/<slug>` з тим самим LIME-template

### Topic→People фіча
- [ ] У news/ дайджесті: біля кожної новини кнопка "Хто з мережі це стосується?"
- [ ] Claude матчить заголовок новини проти `signal_profiles` → показує 1-3
  релевантних member для коментаря

### Не робити
- Не починати SaaS-команду мрії (data scientist + ML engineer)
- Не йти у raise — у тебе перші €580/міс будуть, але це не impressive для VC.
  Краще нарощувати органічно до €5k/міс перш ніж розмивати

---

## 2027 — тільки якщо Q4 метрики виконані

### Найм
- 1 community manager (UA + PL мови) — 100% часу на запрошення партнерів
  АБО 1 backend engineer щоб розвантажити тебе
- НЕ обидва одразу

### B2B2B (white-label)
- Дистриб'ютори / асоціації купляють закриті мікро-мережі під своїм брендом
- Це найшвидший шлях до 6-7 значних місячних доходів без масового growth-marketing

### Тільки тепер думати про raise
- Бо буде що показати: €5-10k/міс recurring, 100+ active members, 50+ closed deals
- Якщо до того часу — ні, бо pitch без traction = no funding

---

## Що з McKinsey-док НЕ робимо (і чому)

| Рекомендація | Чому ні |
|---|---|
| Pitch під €3-5M раунд зараз | У тебе нема team, working AI, метрик трекшн. Іти у raise = згаяти 3-6 міс на нічого |
| 100k користувачів за 18 міс | Консультантська математика. Реальна сила = 20-50 vetted, не 100k cold |
| 15-20% частки ринку за 24 міс | Те саме. Pointrade — не Alibaba, не намагайся стати |
| AI-агент веде переговори | Phase 4 з roadmap. Без 30+ профілів і власного matching це фантастика 2027+ |
| Beta на 5k user у PL+UA | Нереально для solo. Beta = 30-50 партнерів кого ти знаєш |
| Transaction Layer + 2-5% commission | Потребує payment + escrow + KYC + dispute. Solo не зробиш до 2027 |

---

## Single number to track

**Q2:** скільки з твоїх 20-50 партнерів реально заповнили `signal_profiles`.
Якщо <20 за квартал — затримка з matching до Q4.

**Q3:** скільки реальних B2B-контактів між партнерами через платформу.
Не лідів, не кліків — РЕАЛЬНИХ зустрічей/угод.

**Q4:** скільки платних Member × €29 / міс. Метрика яку показуєш собі (не інвесторам).

Якщо 3 числа = 30 / 10 / 20 — ти на правильному шляху, продовжуй.
Якщо 3 числа = 5 / 0 / 0 — щось не так з product-market fit, рахувати знову з нуля.

---

Last updated: 2026-05-10 by Claude during user's sleep session.
