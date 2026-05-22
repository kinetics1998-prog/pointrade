# Pointrade — Deploy Guide

Як запустити Pointrade на проді.

## ⚠️ Найчастіша помилка при деплої PHP

**Не вставляй SQL-міграції замість PHP-коду у File Manager!**

Симптом: відкриваєш `https://chysto.media/signal/orbit/save_profile.php` →
бачиш `CREATE TABLE IF NOT EXISTS...` як plain text. Це означає файл містить
SQL замість PHP. Браузер показує `CORS policy` помилку при submit форми
(бо PHP не виконується → CORS-заголовки не відправляються).

**Як уникнути:** PHP-файли копіюй виключно з GitHub raw URL:
- https://raw.githubusercontent.com/kinetics1998-prog/signal/main/orbit/save_lead.php
- https://raw.githubusercontent.com/kinetics1998-prog/signal/main/orbit/save_profile.php
- https://raw.githubusercontent.com/kinetics1998-prog/signal/main/orbit/_db.php

SQL-міграції (`migrations/*.sql`) запускаються ТІЛЬКИ через phpMyAdmin → SQL tab,
ніколи не в PHP-файли.

**Перевірка що PHP працює:** відкрий endpoint у браузері напряму:
```
https://chysto.media/signal/orbit/save_lead.php
https://chysto.media/signal/orbit/save_profile.php
```
Має повернути JSON `{"error":"method_not_allowed"}` — це нормально (GET не дозволений,
але PHP запускається). Якщо бачиш HTML, SQL, або щось інше → файл зламано.

---

## Архітектура

| Компонент | Де живе | URL |
|---|---|---|
| Static frontend (HTML/CSS/JS/img) | GitHub Pages, гілка `main` | `kinetics1998-prog.github.io/signal/` |
| Backend API (PHP) | Hostinger `~/public_html/signal/` | `chysto.media/signal/...` |
| MySQL DB | Hostinger | внутрішня, не публічна |
| Telegram bot (нотифікації) | Telegram Cloud | через API з backend |

Static і backend на різних доменах → треба CORS (вже налаштовано у `_db.php`).

---

## Перший деплой (one-time setup)

### 1. Створити Telegram bot для нотифікацій

Якщо є старий "Biz Digest Bot" і ти його **відкликав** через @BotFather `/revoke` —
користуйся тим самим бот ID, тільки з новим токеном.

Якщо стартуєш з нуля:
1. Telegram → @BotFather → `/newbot`
2. Назва: `Pointrade Notifications`
3. Username: `signal_notify_bot` (або інший вільний)
4. Збережи токен у password manager — НЕ в git, НЕ в чат

### 2. Дізнатись свій Telegram chat_id

1. У Telegram знайди `@userinfobot` → напиши йому будь-що → отримай `Id: 123456789`
2. **АБО** створи приватну групу "Pointrade leads", додай туди бота, відкрий
   `https://api.telegram.org/bot<TOKEN>/getUpdates` → знайди `"chat":{"id":-100...}` (для групи з `-100`)
3. **Дай боту дозвіл писати тобі**: відкрий бота → натисни `/start`

### 3. Налити Hostinger backend

1. Через File Manager або SFTP створити папку: `~/public_html/signal/`
2. Скопіювати з GitHub clone:
   - `orbit/_db.php` → `~/public_html/signal/orbit/_db.php`
   - `orbit/save_lead.php` → `~/public_html/signal/orbit/save_lead.php`
   - (пізніше) `orbit/save_profile.php` → `~/public_html/signal/orbit/save_profile.php`

### 4. Створити config.php ВИЩЕ public_html (важливо!)

1. У Hostinger File Manager перейди у `/home/u227106289/` (тут де лежить `.chysto_env`)
2. Створи новий файл `signal_config.php`
3. Скопіюй вміст з `orbit/config.example.php` (з GitHub)
4. Заміни placeholders:
   - `'pass' => 'CHANGE_ME'` → реальний MySQL пароль
   - `'bot_token' => 'CHANGE_ME'` → новий токен від BotFather
   - `'chat_id' => 'CHANGE_ME'` → твій chat_id з кроку 2
5. Збережи

Перевір що шлях працює — `_db.php` шукає у:
- `getenv('SIGNAL_CONFIG')` — для override
- `__DIR__ . '/../../../signal_config.php'` — це і є `~/signal_config.php`
- `__DIR__ . '/../../signal_config.php'` — fallback
- `__DIR__ . '/config.php'` — dev only

### 5. Запустити SQL міграцію

1. hPanel → Бази даних → phpMyAdmin → відкрити `u227106289_mixzu`
2. Вкладка SQL → вставити вміст `migrations/001_create_leads.sql`
3. Виконати
4. Перевірити що таблиця `leads` з'явилась і має правильні поля

### 6. Smoke test

1. Відкрий локально (або задеплоєний GitHub Pages) `partner.html`
2. Пройди квіз → step 3
3. Заповни форму:
   - Імʼя: Test
   - Email: test@example.com
   - Що шукаєш: "Test після деплою — ігноруй"
   - Канали: будь-які
   - Galochka GDPR consent
4. Натисни "Надіслати запит"
5. Має статись:
   - У Telegram прийде повідомлення "Новий лід SIGNAL #1 ..."
   - У БД `leads` з'явиться рядок
   - На сторінці зміниться текст на "Заявку прийнято"
6. Видалити test row з БД руками: `DELETE FROM leads WHERE email = 'test@example.com';`

### 7. Якщо щось не працює — де дивитись

| Симптом | Що перевірити |
|---|---|
| 500 на save_lead.php | Hostinger error_log: hPanel → Аналітика → Логи помилок |
| `server_misconfigured` | `signal_config.php` не на правильному шляху або синтаксична помилка PHP |
| `db_unavailable` | MySQL креди в config.php неправильні |
| Лід зберігається але Telegram не приходить | bot_token або chat_id неправильні; бот не /start-нутий |
| CORS error у browser console | Origin не у `cors_origins` allowlist у config.php |
| 429 too_many_requests | Rate limit спрацював, почекай годину або підкрути ліміт у config |

---

## Регулярний деплой нових змін

### Frontend (статичні HTML/CSS/JS/img)
```
git checkout main
git merge merge-may7-design   # або інша гілка
git push
```
GitHub Pages автоматично перебудує за 1-2 хв.

### Backend (PHP)
Hostinger не має auto-deploy з git за замовчуванням. Два варіанти:

**A) Через File Manager (простіше, для small changes)**
1. Відкрий змінений файл локально
2. Скопіюй вміст
3. У File Manager відкрий той же файл на проді → встав → зберегти

**B) Git pull на сервері (краще для multi-file changes)**
1. SSH у Hostinger (якщо план дозволяє)
2. `cd ~/public_html/signal && git pull origin main`
3. Якщо репо ще не клоновано: `cd ~/public_html && git clone https://github.com/kinetics1998-prog/signal.git`

**C) FTP / SFTP**
- FileZilla, Cyberduck, etc.
- Хост: `srv2078-files.hstgr.io` (або з твого Hostinger панелі)

---

## Безпека — checkist перед публікацією

- [ ] `signal_config.php` НЕ у public_html (вище web root)
- [ ] `orbit/config.php` НЕ існує на проді (тільки `signal_config.php` у home)
- [ ] `.gitignore` містить `orbit/config.php` (вже є)
- [ ] Bot token — НЕ у git, НЕ у чат з AI, НЕ у Slack/Telegram чужих
- [ ] MySQL пароль складний (мінімум 16 символів, генератор)
- [ ] `cors_origins` обмежений тільки твоїми доменами
- [ ] Rate-limit активний (5/IP/година, 10/email/день за замовч.)
- [ ] HTTPS працює на chysto.media (Hostinger дає Let's Encrypt безкоштовно)
- [ ] `privacy.html` доступний з partner.html consent checkbox

---

## Контакти

- Власник: Ruslan (kinetics1998@gmail.com)
- Hostinger account: u227106289
- DB: u227106289_mixzu
