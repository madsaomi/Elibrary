<div align="center">

# Elibrary — Школьная библиотечная система

### Мультитенантная CRM-система для школьных библиотек

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.x-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.17-092E20?style=for-the-badge)](https://www.django-rest-framework.org)
[![HTMX](https://img.shields.io/badge/HTMX-2.x-3366CC?style=for-the-badge)](https://htmx.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

</div>

---

## О проекте

**Elibrary** — это комплексная система управления школьными библиотеками. Система поддерживает мультитенантность (много школ), ролевую модель доступа и включает элементы геймификации для стимулирования чтения среди учеников.

### Ключевые возможности

| Возможность | Описание |
|-------------|----------|
| **Мультитенантность** | Одна система — множество школ. Данные изолированы по школам |
| **5 ролей** | Суперадмин, школьный админ, учитель, классный руководитель, ученик |
| **Каталог книг** | Учебники (общий справочник + школьный остаток) и обычные книги |
| **QR/HMAC выдача** | Самообслуживание учеников и учителей через QR-коды (TTL 2 мин) |
| **Геймификация** | XP, 10 уровней, достижения, стрики, камбэк-бонусы |
| **Челленджи** | Еженедельные тесты (15 вопросов), генерируются через Gemini API |
| **i18n** | 4 языка: узбекский, русский, каракалпакский, английский |
| **Адаптивный UI** | Desktop / Tablet / Mobile + Тёмная/светлая тема |

---

## Технологический стек

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend                           │
│  Django Templates + HTMX 2.x + CSS Custom Properties   │
│  Адаптивная вёрстка • Тёмная/светлая тема • Lucide icons│
├─────────────────────────────────────────────────────────┤
│                      Backend                            │
│  Python 3.13 • Django 5.x • DRF + SimpleJWT            │
│  Services Layer • SchoolScopedModel (мультитенантность) │
├─────────────────────────────────────────────────────────┤
│                    Background Tasks                     │
│  Celery + Redis • Celery Beat (периодические задачи)    │
│  Генерация челленджей через Gemini API                  │
├─────────────────────────────────────────────────────────┤
│                    Data Layer                           │
│  PostgreSQL (prod) / SQLite (dev) • Redis (кэш/очередь)│
├─────────────────────────────────────────────────────────┤
│                    Infrastructure                       │
│  Docker + Docker Compose • Daphne (ASGI) • Whitenoise   │
└─────────────────────────────────────────────────────────┘
```

---

## Архитектура

```
Elibrary/
├── apps/                       # Домены (бизнес-логика в services.py)
│   ├── accounts/               # Пользователи, роли, JWT, пароли
│   ├── schools/                # Районы, школы, классы, переводы
│   ├── catalog/                # Учебники, обычные книги, категории
│   ├── loans/                  # Выдача/возврат, QR/HMAC токены
│   ├── gamification/           # XP, уровни, достижения, стрики, челленджи
│   ├── notifications/          # Новости (2 уровня видимости)
│   ├── stats/                  # Логи действий, аналитика
│   └── core/                   # SchoolScopedModel, утилиты, Excel экспорт
├── api/v1/                     # REST API (DRF ViewSets)
├── dashboard/                  # ЕДИНЫЙ UI-слой для всех ролей (HTMX)
├── config/                     # Settings, URLs, Celery, ASGI
├── templates/                  # Глобальные шаблоны (ошибки)
├── static/                     # CSS, JS, изображения
├── locale/                     # Переводы (uz, ru, kaa, en)
└── tests/                      # Тесты
```

### Принцип: Services Layer

Вся бизнес-логика lives в `services.py` внутри каждого домена. Views и ViewSets — только тонкие обёртки:

```python
# ❌ Плохо: логика во view
class BookViewSet(ViewSet):
    def create(self, request):
        # 50 строк бизнес-логики...

# ✅ Хорошо: логика в сервисе
class BookViewSet(ViewSet):
    def create(self, request):
        book = create_book(**request.data)  # вся логика в services.py
        return Response(BookSerializer(book).data)
```

---

## Роли и права

| Роль | Возможности |
|------|-------------|
| **Суперадмин** | Управление районами/школами, рейтинг школ, статистика |
| **Школьный админ** | Ученики/учителя/классы/книги, выдача/возврат, QR-сканер, новости |
| **Учитель** | Каталог книг своего предмета, QR-выдача, лидерборд |
| **Классный руководитель** | + Read-only: ученики своего класса, рейтинг класса |
| **Ученик (5-11)** | Каталог, корзина, QR-возврат, геймификация, челленджи |
| **Ученик (1-4)** | Только запись для учёта учебников (нет аккаунта) |

---

## Быстрый старт

### 1. Клонирование

```bash
git clone https://github.com/madsaomi/Elibrary.git
cd Elibrary
```

### 2. Настройка окружения

```bash
# Создайте .env файл
cp .env.example .env

# Отредактируйте .env
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://user:pass@localhost:5432/library
REDIS_URL=redis://localhost:6379/0
GEMINI_API_KEY=your-gemini-api-key  # Для челленджей (опционально)
```

### 3. Docker (рекомендуется)

```bash
# Запустите PostgreSQL и Redis
docker compose up -d

# Установите зависимости
pip install -r requirements.txt

# Миграции
python manage.py migrate

# Создайте суперадмина
python manage.py createsuperuser

# Инициализируйте достижения
python manage.py init_achievements

# Запустите сервер
python manage.py runserver
```

### 4. Без Docker

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py init_achievements
python manage.py runserver
```

---

## Окружение

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `SECRET_KEY` | Django secret key | insecure-dev-key |
| `DEBUG` | Режим отладки | `True` |
| `DATABASE_URL` | URL базы данных | SQLite |
| `REDIS_URL` | URL Redis | `redis://localhost:6379/0` |
| `GEMINI_API_KEY` | API ключ Gemini | — |
| `GEMINI_MODEL` | Модель Gemini | `gemini-2.0-flash` |
| `USE_S3` | Использовать S3 хранилище | `False` |
| `CORS_ALLOWED_ORIGINS` | Разрешённые домены | — |

---

## API Endpoints

### Аутентификация
| Method | Endpoint | Описание |
|--------|----------|----------|
| POST | `/api/v1/auth/login/` | Вход (JWT) |
| POST | `/api/v1/auth/refresh/` | Обновление токена |
| POST | `/api/v1/auth/me/` | Текущий пользователь |

### Основные ресурсы
| Method | Endpoint | Описание |
|--------|----------|----------|
| GET | `/api/v1/textbooks/` | Учебники |
| GET | `/api/v1/regular-books/` | Обычные книги |
| GET | `/api/v1/textbook-loans/` | Выдачи учебников |
| GET | `/api/v1/regular-book-loans/` | Выдачи книг |
| GET | `/api/v1/challenges/` | Челленджи |
| GET | `/api/v1/news/` | Новости |

### Геймификация
| Method | Endpoint | Описание |
|--------|----------|----------|
| GET | `/api/v1/user-levels/leaderboard/` | Лидерборд школы |
| POST | `/api/v1/streaks/checkin/` | Пометка активности |
| POST | `/api/v1/challenge-attempts/start/` | Начать челлендж |
| POST | `/api/v1/challenge-attempts/{id}/answer/` | Ответить на вопрос |

---

## Тесты

```bash
# Запуск всех тестов
python manage.py test

# Конкретный модуль
python manage.py test tests.test_models
python manage.py test tests.test_api
```

---

## Деплой

### Render.com (рекомендуется)

1. Fork репозиторий
2. Создайте Web Service на Render
3. Подключите репозиторий
4. Настройте environment variables
5. Render автоматически создаст PostgreSQL и Redis

### Railway / Fly.io / VPS

Смотрите `Procfile` для конфигурации процессов:

```
web: daphne config.asgi:application --port $PORT --bind 0.0.0.0
worker: celery -A config worker --loglevel=info
beat: celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Лицензия

MIT License — см. файл [LICENSE](LICENSE)

---

<div align="center">

**Сделано с ❤️ для школьных библиотек**

</div>
