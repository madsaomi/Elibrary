# Elibrary — Agent Guide

School library management system. Multi-tenant Django 6 + DRF + HTMX app for Uzbek school libraries.

## Quick commands

```bash
python manage.py test                           # all tests
python manage.py test tests.test_models         # models only
python manage.py test tests.test_api            # API only
python manage.py makemigrations                 # generate migrations
python manage.py migrate                        # apply migrations
python manage.py init_achievements              # seed gamification levels/achievements
python manage.py seed_dev_data                  # create test users + school
python scripts/compile_messages.py              # compile .po → .mo (no gettext needed)
```

## Architecture

- **Settings**: `config/settings.py` (env via `python-decouple`, `.env` file)
- **ASGI**: Daphne (`config/asgi`), served behind Whitenoise
- **DB**: PostgreSQL in prod, SQLite in dev (auto-selected when `DATABASE_URL` is unset)
- **Cache + broker**: Redis (3 databases: 0=channels, 1=celery, 2=cache)
- **Celery**: `config/celery.py`, beat uses `django_celery_beat` DB scheduler
- **i18n**: 4 languages — uz, ru, kaa, en. Locale files in `locale/`. Compile with `scripts/compile_messages.py`

### Apps (`apps/`)

| App | Domain |
|-----|--------|
| `core` | `SchoolScopedModel`, `UUIDPrimaryKeyMixin`, `TimestampMixin`, managers |
| `accounts` | Custom User (auth by `login` field, not email), roles, JWT, transliteration |
| `schools` | Districts, Schools, Classes |
| `catalog` | Textbooks (shared reference + per-school stock), RegularBooks |
| `loans` | Textbook/RegularBook loans, QR/HMAC self-service tokens (2-min TTL) |
| `gamification` | XP, levels (10), achievements, streaks, challenges (Gemini API) |
| `notifications` | News with 2-tier visibility |
| `stats` | Audit logs, analytics |
| `dashboard` | Unified HTMX UI layer (`dashboard/views/`, `dashboard/templates/`) |
| `api/v1` | DRF REST API |

### Key architectural rules

- **Services layer**: all business logic goes in `apps/<domain>/services.py`. Views and ViewSets are thin wrappers only.
- **Multi-tenancy**: models that belong to a school inherit `SchoolScopedModel`. Filter via `Model.for_user(user)` or `Model.objects.for_user(user)`. Superadmins see all schools.
- **Models**: use `UUIDPrimaryKeyMixin` (UUID PK) and `TimestampMixin` (`created_at`, `updated_at`). Unique constraints via `UniqueConstraint` in `Meta`.
- **Transliteration**: logins/passwords are strictly Latin. `to_latin()` in `apps/accounts/services.py` auto-converts Cyrillic.
- **User model**: `AUTH_USER_MODEL = 'accounts.User'`, authenticates by `login` field (not username/email).

## Testing

- Tests live in `tests/` (not per-app).
- All tests use `django.test.TestCase` with `APIClient` for API tests.
- Setup creates District + School as prerequisites for most models.
- `init_achievements` must be called before gamification tests that use Level objects.
- Axes (login lockout) is auto-disabled during testing.

## Dev setup

1. `cp .env.example .env` and fill values (or leave defaults for SQLite dev)
2. `pip install -r requirements.txt`
3. `python manage.py migrate`
4. `python manage.py init_achievements`
5. `python manage.py seed_dev_data` (creates admin/admin123, student1, teacher1)
6. `python manage.py runserver`

Docker: `docker compose up -d` starts Postgres + Redis + web (Daphne) + Celery worker + beat.

## Gotchas

- `SECRET_KEY` env var is `DJANGO_SECRET_KEY` (not `SECRET_KEY`) — see `config/settings.py:8`
- `DEBUG` env var is `DJANGO_DEBUG` — see `config/settings.py:9`
- JWT `USER_ID_FIELD` is `login` (not `id`) — `config/settings.py:176`
- Axes lockout is off in DEBUG and TESTING modes automatically
- `DATABASE_URL` format: `postgres://user:pass@host:5432/dbname` — if unset, falls back to SQLite
- Celery broker URL defaults to `redis://localhost:6379/1` (separate from cache on db 2)
- Static files served by Whitenoise; `collectstatic` needed for production
- ASGI application entry: `config.asgi:application`
- Admin URL is configurable via `DJANGO_ADMIN_URL` env var (default `admin/`)
