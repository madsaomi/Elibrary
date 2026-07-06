# 📋 Лог задач проекта / Project Tasks Log

> **Этот файл — главный источник контекста для любого агента, работающего с проектом.**
> Прочитай его полностью перед тем, как приступать к любой задаче.

---

## 🏗️ О проекте

**Название:** Школьная библиотечная система для Каракалпакстана (v2)
**Расположение:** `c:\Users\~\Desktop\123`
**Стек:** Python 3.13, Django 6.x, DRF, HTMX 2.x, Celery + Redis, SQLite (dev) / PostgreSQL (prod)
**Спецификация:** [план.md](file:///c:/Users/~/Desktop/123/план.md) (бэкенд, 286 строк) + [план_frontend.md](file:///c:/Users/~/Desktop/123/план_frontend.md) (фронтенд, 217 строк)

### Краткое описание
Мультитенантная CRM-система для школьных библиотек. Основные функции:
- **Управление пользователями:** 4 роли (суперадмин, школьный админ, учитель, ученик). Ученики 1-4 класс — без аккаунтов (только записи для учёта учебников). Ученики 5-11 — полноценные пользователи с геймификацией.
- **Каталог:** Учебники (общий справочник + школьный остаток `TextbookStock`) и обычные книги (принадлежат конкретной школе).
- **Выдача/возврат:** Учебники — вручную через админа (комплектами по классу). Обычные книги — самообслуживание через QR/HMAC-токены (TTL 2 мин).
- **Геймификация:** XP, 10 уровней (прогрессивная шкала), достижения, стрики, камбэк-бонусы.
- **Челленджи:** Еженедельные тесты (15 вопросов, 3 варианта, таймер 15 мин), генерируются через Gemini API.
- **i18n:** 4 языка (рус, узб, каракалп, англ).
- **Тема:** Светлая/тёмная (тёмная — контрастная, близкая к чёрной).

### Архитектура (ключевые файлы)
```
apps/
├── accounts/     # User модель, роли, JWT, сервисы создания/сброса паролей
│   ├── models.py      — User (login, role, school, grade, subject, transfer_status)
│   ├── managers.py    — UserManager (create_user, create_superuser)
│   └── services.py    — create_user(), reset_password(), activate_grade_access(), транслитерация
├── schools/      # District, School, Class, TransferLog
│   ├── models.py      — District, School (unique per district), Class (number+parallel+language+year)
│   └── transfer_service.py — initiate_departure(), complete_departure(), accept_transfer()
├── catalog/      # Textbook, TextbookStock, RegularBook, Category, SubjectTextbook
├── loans/        # TextbookLoan, RegularBookLoan, QR/HMAC сервис
│   └── services.py    — issue/return textbooks/books, generate/validate QR tokens, "корзина"
├── gamification/ # XP, Level, UserLevel, Achievement, Streak, Challenge, ChallengeAttempt
│   └── services.py    — add_xp(), update_user_level(), check_achievements(), update_streak()
├── notifications/# News (2 уровня видимости)
├── stats/        # ActionLog, логирование действий
└── core/         # SchoolScopedModel, SchoolScopedManager (мультитенантность), утилиты

api/v1/           # DRF ViewSets (тонкие обёртки над services)
dashboard/        # ЕДИНЫЙ UI-слой для всех ролей (Django Templates + HTMX)
│   ├── views.py       — 1058 строк, все view-функции для всех ролей
│   └── templates/dashboard/ — base_dashboard.html + подпапки по разделам
config/
│   ├── settings.py    — настройки проекта
│   ├── tasks.py       — Celery-задачи (генерация челленджей через Gemini, автоперевод классов)
│   └── urls.py        — главный роутинг
tests/
│   ├── test_models.py — 23 теста (модели, сервисы, геймификация)
│   └── test_api.py    — тесты API (auth, schools, catalog, loans)
```

### Принцип бизнес-логики
Вся логика — в `services.py` внутри каждого домена. Views (Django) и ViewSets (DRF) — только тонкие обёртки, вызывающие сервисы. Это исключает дублирование между HTMX-интерфейсом и API.

---

## 📅 Последнее обновление: 2026-07-07

---

## 🛠️ Текущий статус

### ✅ Завершённая задача #10 — Аудит кода и исправление критических багов
**Дата:** 2026-07-07
**Проблема:** В проекте были критические баги: сломанный функционал переводов между школами, нерабочие челленджи из-за несоответствия ключей, эскалация привилегий, race conditions, открытые ViewSet'ы без permission.

**Что было сделано:**
- `[x]` **TransferLog.to_school** — добавлено `null=True` (модель schools/models.py) — раньше `initiate_departure` падал с IntegrityError
- `[x]` **accept_transfer** — берёт `old_school` из `transfer.from_school` вместо `user.school` (который None после departure)
- `[x]` **cancel_transfer** — восстанавливает school/grade из TransferLog при отмене
- `[x]` **Челленджи** — исправлено несоответствие ключей `correct_index` vs `correct` в views.py start/finish
- `[x]` **auto_promote_classes** — исправлено: старые классы теперь помечаются GRADUATED вместо ACTIVE
- `[x]` **create_user** — блокирует `is_superuser`/`is_staff` в extra_fields (эскалация привилегий)
- `[x]` **ChallengeViewSet** — добавлен `permission_classes = [IsSchoolAdminOrSuperAdmin]`
- `[x]` **NewsViewSet** — добавлен `permission_classes = [IsSchoolAdminOrSuperAdmin]`
- `[x]` **ActionLogViewSet** — добавлен `permission_classes = [IsSchoolAdminOrSuperAdmin]`
- `[x]` **logout_form_view** — добавлен `@require_POST` (CSRF атака через GET)
- `[x]` **issue_textbooks_to_class** — добавлен `select_for_update()` (race condition)
- `[x]` **issue_books** — добавлен `select_for_update()` (race condition)

**Затронутые файлы:**
- `apps/schools/models.py` — TransferLog.to_school nullable
- `apps/schools/transfer_service.py` — accept_transfer + cancel_transfer
- `apps/schools/services.py` — auto_promote_classes
- `apps/gamification/views.py` — ChallengeViewSet permissions + correct_index fix
- `apps/accounts/managers.py` — create_user privilege escalation
- `apps/accounts/views.py` — logout CSRF
- `apps/notifications/views.py` — NewsViewSet permissions
- `apps/stats/views.py` — ActionLogViewSet permissions
- `apps/loans/services.py` — select_for_update on issue_textbooks_to_class + issue_books

**Не исправлено (требует тестирования):**
- `return_books` не проверяет due_date для обычных книг (всегда начисляет 30 XP)
- N+1 запросы в get_student_textbook_set
- `Streak` OneToOneField конфликтует со school FK при переводе ученика
- `update_streak` не обёрнут в @transaction.atomic
- Сервисные viewsets используют `fields = '__all__'` в сериализаторах

---

### 🔄 Запланированные этапы (Roadmap)
**Описание:** План дальнейшей реализации согласно технической спецификации проекта.

* **Очередь задач (`[ ]`):**
  * `[x]` **Этап 1: Интеграция ИИ (Еженедельные челленджи).** Celery-задача для генерации вопросов через API Gemini (1 раз в неделю).
  * `[x]` **Этап 2: Excel-экспорты и Безопасность.** Генерация Excel-отчётов с логинами/паролями при создании пользователей и сбросе паролей, списки должников.
  * `[x]` **Этап 3: Детализация геймификации.** Реализация формул прогрессии уровней, камбэк-бонусов, конкретный список и логика выдачи "Достижений".
  * `[x]` **Этап 4: Продвинутое управление школами.** Перевод учеников (срезание 50% XP), массовый автоперевод классов 1 сентября, активация 5-го класса.
  * `[ ]` **Этап 5: Инфраструктура (Docker).** Упаковка проекта в Docker/Docker Compose (PostgreSQL, Redis, Celery).

---

## ✅ Архив завершённых задач

### #9 — Внедрение дополнительных креативных улучшений (Часть 2)
**Дата:** 2026-07-06
**Проблема:** Многие внутренние экраны (корзина, новости, QR-сканер, профиль) всё ещё имели базовый дизайн. Хотелось расширить "WOW" эффект от предыдущего апдейта.

**Что было сделано:**
- `[x]` Добавлена 3D-иллюстрация "Пустая коробка" во все основные пустые состояния (`cart.html`, `news/list.html`, `challenges/leaderboard.html`) с анимацией парения.
- `[x]` Добавлен красивый 3D-бейджик уровня в карточку профиля ученика (`student_detail.html`).
- `[x]` Добавлена новая CSS-анимация `pulse-ring` в `style.css`.
- `[x]` Обновлён экран QR-сканера (`scanner.html`): вместо статичной иконки добавлена стильная пульсирующая кнопка-заглушка с подготовленным местом под будущее 3D-изображение робота.
- `[x]` Создан файл `docs/design/PROMPTS.md` с инструкциями и готовыми запросами для будущей генерации изображений.

**Затронутые файлы:**
- `static/css/style.css`
- `dashboard/templates/dashboard/qr/cart.html`
- `dashboard/templates/dashboard/news/list.html`
- `dashboard/templates/dashboard/challenges/leaderboard.html`
- `dashboard/templates/dashboard/qr/scanner.html`
- `dashboard/templates/dashboard/users/student_detail.html`

### #8 — Креативный редизайн страниц логина и ошибок (Этап 3+)
**Дата:** 2026-07-06
**Проблема:** Страницы входа и ошибок (404, 403, 500) выглядели скучно и использовали стандартные эмодзи. Требовался премиальный "WOW" дизайн с анимациями и креативными иллюстрациями.

**Что было сделано:**
- `[x]` Сгенерированы 4 уникальные 3D изометрические иллюстрации (cozy library, floating book, magical locked book, robot repairing books).
- `[x]` Обновлён `style.css` — добавлены анимации `floating` (парение объектов) и стили для сплит-экрана (`.login-split-image`).
- `[x]` Полностью переработан макет `login.html` на двухколоночный (иллюстрация слева, форма справа).
- `[x]` Переработаны `404.html`, `403.html`, `500.html` — внедрены 3D картинки и стильная типографика.
- `[x]` Написан и выполнен python-скрипт (`replace_emojis.py`) для массовой замены всех оставшихся эмодзи на Lucide SVG иконки во всех шаблонах (31 файл).

**Затронутые файлы:**
- `static/css/style.css`
- `apps/accounts/templates/accounts/login.html`
- `templates/404.html`, `templates/403.html`, `templates/500.html`
- 31 шаблон (массовая замена эмодзи)

### #7 — Продвинутое управление школами (Этап 4)
**Дата:** 2026-07-06
**Проблема:** Отсутствовал интерфейс для массового автоперевода классов (1 сентября), не было защиты от двойного срабатывания, а также не было UI для двухфазного перевода учеников между школами.

**Что было сделано:**
- `[x]` Создана модель `PromotionLog` (журнал переводов) с уникальным ограничением `(school, academic_year)` для защиты от повторного автоперевода. Создана и применена миграция.
- `[x]` Обновлена функция `auto_promote_classes` в `apps/schools/services.py`: теперь она проверяет журнал перед запуском и создаёт запись после завершения. Принимает параметр `initiated_by` для аудита.
- `[x]` Созданы 5 новых views: `school_settings`, `promote_classes_view`, `transfers_list`, `transfer_depart`, `transfer_accept`.
- `[x]` Создан шаблон `schools/settings.html` — красивая страница с двумя карточками (автоперевод + активация 5-го класса) и журналом.
- `[x]` Создан шаблон `schools/transfers.html` — формы ухода/приёма и таблицы с историей переводов (показывает XP до/после).
- `[x]` В сайдбар школьного админа добавлена новая группа "Школа" с ссылками ⚙️ Настройки и 🔄 Переводы.
- `[x]` Успешно прогнаны все тесты (24 теста).

**Затронутые файлы:**
- `apps/schools/models.py` (добавлена `PromotionLog`)
- `apps/schools/services.py` (обновлена `auto_promote_classes`)
- `apps/schools/migrations/0003_alter_class_number_promotionlog.py` (создана)
- `dashboard/views.py` (5 новых views)
- `dashboard/urls.py` (5 новых маршрутов)
- `dashboard/templates/dashboard/schools/settings.html` (создан)
- `dashboard/templates/dashboard/schools/transfers.html` (создан)
- `dashboard/templates/dashboard/base_dashboard.html` (сайдбар)

### #6 — Детализация геймификации (Этап 3)
**Дата:** 2026-07-06
**Проблема:** В системе отсутствовали точные конфигурации достижений (они были захардкожены на 50 XP), не было удобного механизма для их инициализации на новых серверах. Уровни также нуждались в ревизии.

**Что было сделано:**
- `[x]` В `apps/gamification/services.py` переписана функция `check_achievements`. Теперь каждое достижение даёт разное количество опыта (`xp_reward`), например: "Первый шаг" = 20 XP, "Книжный червь" (50 книг) = 200 XP, "Ветеран библиотеки" (10000 XP) = 500 XP.
- `[x]` Создана management-команда `init_achievements` для автоматического создания нужных записей о достижениях в базе данных.
- `[x]` Команда успешно отработала, достижения прописаны в базе.
- `[x]` Успешно прогнаны все тесты (24 теста).

**Затронутые файлы:**
- `apps/gamification/services.py`
- `apps/gamification/management/commands/init_achievements.py` (создан)### #5 — Excel-экспорты и Безопасность (Этап 2)
**Дата:** 2026-07-06
**Проблема:** Отсутствовал UI для массового импорта учеников через CSV, а также не было кнопок для скачивания обходных листов по должникам учебников. Логика генерации Excel-файлов уже существовала в коде, но не была интегрирована в интерфейс школьного админа.

**Что было сделано:**
- `[x]` В шаблон списка пользователей (`list.html`) добавлены кнопки "Импорт учеников", "Обходной (Май)" и "Должники", которые ведут на существующие, но ранее скрытые views.
- `[x]` Шаблон массового импорта (`import_csv.html`) обновлён: добавлен класс `fade-in-up` для соответствия новому UI-дизайну. 
- `[x]` Проверено наличие логики генерации Excel-паролей при создании школы суперадмином.
- `[x]` Успешно прогнаны все тесты (24 теста).

**Затронутые файлы:**
- `dashboard/templates/dashboard/users/list.html`
- `dashboard/templates/dashboard/users/import_csv.html`

### #4 — Интеграция ИИ для генерации челленджей (Этап 1)
**Дата:** 2026-07-06
**Проблема:** В интерфейсе был раздел геймификации с еженедельными челленджами (тестами), но сами вопросы отсутствовали. Требовалась автоматическая фоновая генерация с использованием Gemini.

**Что было сделано:**
- `[x]` Установлена официальная библиотека `google-genai` для обращения к Gemini API.
- `[x]` Добавлена функция `generate_challenge_questions` в `apps/gamification/services.py`, формирующая строгий JSON-запрос для ИИ с учётом возраста (класса) и языка обучения.
- `[x]` Написана Celery-задача `generate_weekly_challenges` в `apps/gamification/tasks.py`. Она находит все уникальные комбинации `(Школа, Класс, Язык)` для активных учеников и генерирует уникальные тесты на следующую неделю.
- `[x]` Настроено расписание в `config/celery.py` через `Celery Beat` для автоматического запуска задачи каждое воскресенье в 23:00.
- `[x]` Успешно прогнаны все тесты.

**Затронутые файлы:**
- `requirements.txt`
- `apps/gamification/services.py`
- `apps/gamification/tasks.py` (новый файл)
- `config/celery.py`

### #3 — Модернизация дизайна и UI-стилей проекта
**Дата:** 2026-07-06
**Проблема:** Интерфейс выглядел устаревшим — плоские карточки, слабые тени, отсутствие анимаций, невыразительная цветовая палитра. Шрифты Google (Manrope и Inter) из спецификации не применялись.

**Что было сделано:**
- `[x]` Подключены Google Fonts (Inter, Manrope) в CSS-переменные в `style.css`.
- `[x]` Полная переработка [style.css](file:///c:/Users/~/Desktop/123/static/css/style.css) (700 → 680 строк) — обновлённые цветовые токены (Teal/Slate/Amber), увеличенные скругления, ступенчатые тени, glassmorphism-эффект, интерактивные hover-эффекты.
- `[x]` Обновлён [login.html](file:///c:/Users/~/Desktop/123/apps/accounts/templates/accounts/login.html) — радиальные градиенты и анимация `fade-in-up`.
- `[x]` Обновлены ключевые экраны ролей: добавлены анимации `fade-in-up`, скруглённые `table-wrap` для таблиц, `card-hover` и улучшенная типографика:
  - Суперадмин: [superadmin.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/stats/superadmin.html)
  - Главная: [home.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/home.html)
  - Профиль: [student_detail.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/users/student_detail.html), [young_students.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/users/young_students.html), [list.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/users/list.html)
  - Каталог и корзина: [student_catalog.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/catalog/student_catalog.html), [cart.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/qr/cart.html)
  - Учебники и книги: [my_loans.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/loans/my_loans.html), [issue_set.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/loans/issue_set.html), [return_textbooks.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/loans/return_textbooks.html)
  - Учитель: [homeroom.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/teacher/homeroom.html)
  - Геймификация: [take.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/challenges/take.html), [leaderboard.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/challenges/leaderboard.html)
  - QR: [scanner.html](file:///c:/Users/~/Desktop/123/dashboard/templates/dashboard/qr/scanner.html)
- `[x]` Все 24 теста пройдены успешно.

**Затронутые файлы:**
- `static/css/style.css` 
- 13 HTML-шаблонов в `dashboard/templates/`

### #2 — Исправление багов после аудита кода
**Дата:** 2026-07-06
**Проблема:** Выявлено три несоответствия спецификации/бага:
1. `auto_promote_classes` падал с NameError: `users` is not defined.
2. Прогрессивный XP-бонус за уровень `bonus_percent` не начислялся.
3. XP начислялось всем подряд, включая учителей и младшеклассников, которые не должны участвовать в геймификации.

**Что было сделано:**
- `[x]` Добавлен запрос получения студентов для перевода классов в `auto_promote_classes()` в [services.py](file:///c:/Users/~/Desktop/123/apps/schools/services.py#L75).
- `[x]` Добавлено начисление бонусного XP за текущий уровень в `add_xp()` в [services.py](file:///c:/Users/~/Desktop/123/apps/gamification/services.py#L53).
- `[x]` Добавлены проверки `is_active_for_gamification` в `add_xp`, `award_comeback_bonus`, `check_achievements` и `update_streak` в [services.py](file:///c:/Users/~/Desktop/123/apps/gamification/services.py).
- `[x]` Добавлен юнит-тест `test_gamification_disabled` в [test_models.py](file:///c:/Users/~/Desktop/123/tests/test_models.py#L155).
- `[x]` Все 24 теста пройдены успешно.

**Затронутые файлы:**
- `apps/schools/services.py`
- `apps/gamification/services.py`
- `tests/test_models.py`

### #1 — Исправление бага: уровни геймификации не повышались
**Дата:** 2026-07-06
**Проблема:** Функция `add_xp()` в `apps/gamification/services.py` увеличивала поле `total_xp` в таблице `UserLevel`, но **никогда не пересчитывала** связь с таблицей `Level`. Из-за этого `UserLevel.level` навсегда оставался на уровне 1, независимо от накопленного XP.

**Что было сделано:**
- `[x]` Создана функция `update_user_level(user_level)` в [services.py](file:///c:/Users/~/Desktop/123/apps/gamification/services.py#L40) — находит максимальный `Level` где `xp_required <= total_xp` и обновляет FK.
- `[x]` Вызов `update_user_level()` добавлен в `add_xp()` (после обновления XP) и `award_comeback_bonus()` (после начисления бонуса).
- `[x]` Вызов `update_user_level()` добавлен в [transfer_service.py](file:///c:/Users/~/Desktop/123/apps/schools/transfer_service.py#L84) — пересчёт уровня после уменьшения XP на 50% при переводе ученика.
- `[x]` Написан unit-тест `test_level_up` в [test_models.py](file:///c:/Users/~/Desktop/123/tests/test_models.py#L129) — проверяет переход на уровни 4 и 5 при добавлении 500 и 1500 XP.
- `[x]` Все 23 теста пройдены успешно.

**Затронутые файлы:**
- `apps/gamification/services.py` — добавлена функция + 2 вызова
- `apps/schools/transfer_service.py` — добавлен 1 вызов
- `tests/test_models.py` — добавлен 1 тест
