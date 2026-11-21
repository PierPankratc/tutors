# Tutors Marketplace — Backend

Production-ready backend маркетплейса репетиторов (Россия, 152-ФЗ).
Модульный монолит: `api → services → repositories → models`.

## Стек

| Слой | Технологии |
|------|-----------|
| API | FastAPI, Pydantic v2, uvicorn |
| БД | PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic |
| Кэш/сессии | Redis 7 |
| Auth | JWT access (15 мин) + refresh (httpOnly cookie, ротация), Argon2id, TOTP 2FA |
| Файлы | Yandex Object Storage (S3), только pre-signed URL (TTL ≤ 5 мин) |
| Инфра | Docker Compose, Nginx (TLS, rate limiting) |
| Тесты | pytest + httpx (ASGITransport), покрытие критичных путей ≥ 80% |

## Структура

```
backend/
├── alembic/                 # миграции (0001_initial_schema)
├── src/tutors/
│   ├── api/                 # композиция роутов /api/v1
│   ├── core/                # config, database, crypto, security, storage, rate limiting
│   └── modules/
│       ├── audit/           # append-only audit_log (152-ФЗ)
│       ├── auth_users/      # регистрация, логин, refresh, 2FA, обезличивание
│       ├── profiles/        # tutor/student профили, предметы, заявки на контакт
│       ├── reviews/         # отзывы
│       └── verification/    # документы об образовании (S3)
├── tests/
infra/nginx/nginx.conf
docker-compose.yml
```

## Быстрый старт

```bash
cp .env.example .env          # заполнить секреты (openssl rand -base64 32)
docker compose up --build -d
docker compose exec backend alembic upgrade head
```

Локальные тесты:

```bash
uv pip install -e "backend[dev]"
.venv/Scripts/pytest backend/tests --cov=backend/src/tutors
```

## API (v1)

| Метод | Путь | Доступ |
|-------|------|--------|
| POST | `/api/v1/auth/register` | public, rate limit 5/час |
| POST | `/api/v1/auth/login` | public, rate limit 10/мин |
| POST | `/api/v1/auth/refresh` | cookie + CSRF |
| POST | `/api/v1/auth/logout` | cookie + CSRF |
| POST | `/api/v1/auth/2fa/setup` | auth |
| POST | `/api/v1/auth/2fa/confirm` | auth |
| GET | `/api/v1/users/me` | auth (аудит чтения ПДн) |
| DELETE | `/api/v1/users/me` | auth + пароль (каскадное обезличивание) |
| GET | `/api/v1/audit/events` | moderator/admin |

## Безопасность (152-ФЗ)

- Пароли — Argon2id; значения секретов и email маскируются в логах.
- ПДн (`email`, контакты, TOTP-секрет) шифруются AES-256-GCM; поиск по email — HMAC-SHA256 blind index.
- `audit_log` хранит только метаданные доступа (без значений ПДн) и защищён триггером append-only в PostgreSQL.
- Refresh-токены ротируются, повторное использование токена рвёт все сессии пользователя.
- CSRF: подписанный double-submit cookie + заголовок `X-CSRF-Token`.
- Удаление аккаунта: обезличивание ПДн, удаление профилей, очистка текстов отзывов, удаление файлов из S3.
- Секреты — только из `.env` (pydantic-settings), `.env` в `.gitignore`.

## Миграции

```bash
cd backend
alembic upgrade head
alembic downgrade base
alembic upgrade head --sql   # offline DDL для review
```
