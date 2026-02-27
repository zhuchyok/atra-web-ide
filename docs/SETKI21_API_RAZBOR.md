# Разбор: кто за что отвечает на www.setki21.ru

## В чём путаница

Для одного сайта **www.setki21.ru** оказались задействованы **два разных бэкенда**:

| Кто            | Откуда                                   | Что умеет                                                                                                           | Где крутится                    |
| -------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| **atra-core**  | репо atra-web-ide (rust_core/atra-core)  | Только `/health`, `/api/v1/info`, `POST /api/v1/auth/login`. Вход по email/паролю из файла `.env.atra`, **без БД**. | VDS, контейнер atra-kernel:8081 |
| **moskit-api** | репо setki-21 (moskit-api + moskit-core) | Полный API: тот же auth (из БД), **цены**, дилеры, заказы, tenant. **Нужна PostgreSQL.**                            | Сейчас на VDS **не запущен**    |

Сайт (Nuxt) шлёт все запросы на `https://www.setki21.ru/api/...` → NPM отправляет их на **atra-kernel:8081**. Поэтому:

- **Вход работает** — мы добавили auth в atra-core и завели `.env.atra`.
- **Цен в админке нет** — эндпоинты цен живут в moskit-api, его на VDS нет, базу к atra-core не подключали.

Итого: логин «прикрутили» к одному бэкенду (atra-core), а цены/дилеры/заказы — в другом (moskit-api), который не развёрнут. Отсюда и путаница.

---

## Как сделано (один бэкенд)

**Один бэкенд для Сетки 21 = moskit-api.**

- Один сервис, одна БД `moskit` на существующем PostgreSQL (atra-postgres).
- Вход, цены, дилеры, заказы, tenant — всё из moskit-api.
- Логин/пароль админки: **admin@setki21.ru** и тот же пароль, что в `.env.atra` (миграция `004_admin_setki21.sql`).

**Что есть в репо:**

- **docker-compose.vds.yml** — сервис `moskit-api` (образ `moskit-api:latest`, собирается на VDS из setki-21).
- **scripts/create_moskit_db_vds.sh** — создание пользователя и БД `moskit` на atra-postgres.
- **scripts/deploy_moskit_api_vds.sh** — деплой: rsync setki-21, сборка образа, запуск moskit-api.
- **scripts/npm_proxy_setki21.conf** — образец конфига NPM: `/api` и `/health` → moskit-api:8080.

После переключения NPM на moskit-api atra-core для setki21 не используется (оставить только если нужен для других проектов на VDS).

---

## Где что описано

- **Текущая схема (NPM, SSL, вход через atra-core):** `docs/ATRA_CORE_NPM_SETUP.md`
- **Почему нет цен и что такое moskit-api:** `docs/SETKI21_ADMIN_PRICING_VDS.md`
- **Деплой статики сайта:** `docs/SETKI21_SITE_DEPLOY_VDS.md`

Рекомендация: довести до конца развёртывание **moskit-api** и переключить весь `/api` на него — тогда и путаница исчезнет, и цены в админке появятся.
