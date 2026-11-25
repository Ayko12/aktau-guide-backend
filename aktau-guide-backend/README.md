# Aktau Guide — бэкенд на FastAPI

API для React-фронтенда Aktau Guide. Поля ответов совпадают с данными фронтенда
(`ll`, `t1`, `sub`, `onHome`, `effectivePlan`…), поэтому подключение сводится к замене
демо-данных на запросы.

**Стек:** FastAPI, SQLAlchemy 2.0, Pydantic v2, JWT (PyJWT), пароли — PBKDF2-SHA256.
SQLite по умолчанию, PostgreSQL — через `AG_DATABASE_URL`.

## Запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload          # http://localhost:8000/docs — Swagger
pytest                                 # тесты
```

При первом запуске база создаётся и заполняется демо-данными фронтенда. Пароль у всех
демо-пользователей — `demo1234` (`user@demo.kz`, `owner@demo.kz`, `aidana@demo.kz`,
`content@demo.kz`, `admin@demo.kz`…). Быстрый вход по роли: `POST /api/auth/demo/{user|business|manager|admin}`.

Docker: `docker build -t aktau-api . && docker run -p 8000:8000 -v aktau:/data aktau-api`.

## Настройки (.env)

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `AG_DATABASE_URL` | `sqlite:///./aktau_guide.db` | для Postgres: `postgresql+psycopg://…` (+ `psycopg[binary]`) |
| `AG_SECRET_KEY` | `dev-secret-change-me` | ключ JWT; при `AG_DEMO_MODE=false` стандартный ключ запрещён |
| `AG_TOKEN_TTL_MINUTES` | 10080 (7 дней) | срок жизни токена |
| `AG_CORS_ORIGINS` | `http://localhost:5173` | адреса фронтенда через запятую |
| `AG_DEMO_MODE` | `true` | вход по роли, демо-пароли |
| `AG_SEED_ON_STARTUP` | `true` | сиды при пустой БД |
| `AG_TODAY` | `2026-11-22` | «сегодня» под демо-данные; пусто — реальная дата |

## Структура

```
app/
  main.py            create_app(): CORS, роутеры, создание таблиц и сиды
  config.py          настройки из окружения / .env
  db.py, models.py   SQLAlchemy: пользователи, места, Hidden, события, организации,
                     статистика по дням, платежи, реклама, избранное, маршруты, настройки
  schemas.py         Pydantic: вход/выход, camelCase наружу
  deps.py            текущий пользователь, проверка ролей
  security.py        пароли и JWT
  domain/            чистая логика без БД: планировщик (порт lib/planner.js), тарифы, справочники
  services/          организации и подписки, статистика, платёжный провайдер (демо), сериализация
  routers/           auth, catalog, businesses, me, planner, cabinet, admin
  seed/              демо-данные фронтенда (seed_data.json) и загрузчик
tests/
  test_domain.py     планировщик сверяется с JS-версией фронтенда на 144 комбинациях входных данных
  test_api.py        сквозные сценарии всех ролей
```

## Эндпоинты (префикс `/api`)

Авторизация — заголовок `Authorization: Bearer <token>`.

**Авторизация**

| Метод | Путь | Описание |
|---|---|---|
| POST | `/auth/register` | `{name, email, password, isBiz?, orgName?, orgCat?}` → `{token, user, org?}`; с организацией — Trial 30 дней |
| POST | `/auth/login` | `{email, password}` → `{token, user}` |
| POST | `/auth/demo/{role}` | демо-вход (только `AG_DEMO_MODE`) |
| GET / PATCH | `/auth/me` | профиль / смена имени |

**Публичный каталог**

| Метод | Путь | Параметры |
|---|---|---|
| GET | `/meta` | категории, подборки, тарифы, включённые языки, `trialDays`, `today` |
| GET | `/locations` | `q`, `cat`, `free`, `onHome` |
| GET | `/locations/{id}`, `/locations/{id}/nearby` | `limit` |
| GET | `/hidden`, `/hidden/{id}` | `col` |
| GET | `/events`, `/events/{id}` | `when=all|today|week|month|free`, `cat`, `archive` |
| GET | `/businesses`, `/businesses/{id}` | `q`, `cat`, `sort=rec|name|new` (Premium/Pro выше) |
| POST | `/businesses/{id}/view`, `/businesses/{id}/contact/{phone|wa|ig|site}` | учёт статистики |
| POST | `/planner/plan` | `{interests, duration, budget, kids}` → маршрут со временем, днями, суммой |
| POST | `/planner/candidates` | что можно добавить в маршрут |
| POST | `/planner/schedule` | `{w, stops}` → пересчёт времени после перестановки точек |

**Пользователь** (после входа)

| Метод | Путь | Описание |
|---|---|---|
| GET | `/me/favorites` | избранное |
| PUT / DELETE | `/me/favorites/{id}` | добавить / убрать место (`l…`) или организацию (`b…`) |
| GET / POST | `/me/routes` | сохранённые маршруты |
| DELETE | `/me/routes/{id}` | удалить маршрут |

**Кабинет бизнеса** (роль business или admin)

| Метод | Путь | Описание |
|---|---|---|
| GET / POST | `/cabinet/orgs` | мои организации / новая (Trial) |
| GET / PATCH | `/cabinet/orgs/{id}` | карточка / профиль |
| GET | `/cabinet/orgs/{id}/stats` | просмотры и переходы за 30 дней + 14-дневный график (Pro/Premium) |
| POST / DELETE | `/cabinet/orgs/{id}/offers[/{index}]` | акции (Pro/Premium) |
| POST | `/cabinet/orgs/{id}/subscription` | `{plan: free|pro|premium}` — смена тарифа, демо-оплата |
| GET | `/cabinet/orgs/{id}/payments` | история платежей |

**Админ-панель**

| Доступ | Пути |
|---|---|
| менеджер и админ | `GET /admin/dashboard`; `GET/PATCH /admin/businesses` (модерация, верификация); CRUD `/admin/locations`, `/admin/hidden`, `/admin/events`; `GET/DELETE /admin/routes` |
| только админ | `GET/PATCH /admin/users`; `POST /admin/subscriptions/expire`; `POST /admin/businesses/{id}/extend`; `GET /admin/payments`; `GET/POST/PATCH /admin/ads`; `GET /admin/reports`; `GET/PATCH /admin/settings` |

Ошибки приходят как `{"detail": "текст на русском"}`, ошибки валидации — стандартным списком FastAPI.

## Правила, перенесённые из прототипа

- Trial = функции Pro. Истёкшая подписка считается Free сразу (`effectivePlan`), а
  `POST /admin/subscriptions/expire` переводит её на Free в базе. Его стоит запускать
  по расписанию (cron).
- Акции и статистика доступны только на Pro и Premium; в публичной карточке Free-организации
  `offers` пустой.
- Новая организация уходит на модерацию (`pending`) и не видна в каталоге до одобрения.
- Заблокированный пользователь не может войти, его токены перестают работать.
- Планировщик даёт те же маршруты, что и фронтенд (проверено тестом).

## Подключение фронтенда

```js
// src/api/client.js
const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';
export async function api(path, { method = 'GET', body, token } = {}) {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }) },
    body: body && JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? r.statusText);
  return r.status === 204 ? null : r.json();
}
```

Дальше в `AppStore.jsx` начальные данные берутся из `/locations`, `/events`, `/hidden`,
`/businesses`, а действия (`toggleFav`, `buildPlan`, `submitAuth`, `confirmModal`…) вызывают
соответствующие эндпоинты.

## Что дальше

- Миграции через Alembic вместо `create_all` перед первым production-деплоем.
- Реальная оплата: реализовать `services/payments.py` (Kaspi / Freedom Pay) и обработчик вебхука.
- Ограничение частоты запросов на `/auth/*` и учёт статистики.
- Полнотекстовый поиск PostgreSQL вместо фильтрации в Python, когда каталог вырастет.
- Загрузка фото (S3-совместимое хранилище) для мест и организаций.
