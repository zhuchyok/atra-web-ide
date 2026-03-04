# Цены в админке Сетки 21 на VDS

> **Кто за что отвечает:** см. **docs/SETKI21_API_RAZBOR.md**. Рекомендуемая схема: **один API = moskit-api** (вход, цены, дилеры, заказы).

## Текущая схема (после настройки)

- **Единый API для www.setki21.ru** — **moskit-api** (порт 8080).
- NPM направляет `/api` и `/health` на **moskit-api:8080**.
- Вход в админку: **admin@setki21.ru** и пароль из `.env.atra` (тот же, что был для atra-core). Миграция `004_admin_setki21.sql` приводит пользователя в БД к этому логину/паролю.

## Как развернуть moskit-api (один раз)

1. **Создать БД и пользователя** на существующем PostgreSQL (atra-postgres):

   ```bash
   # На VDS в /home/atra/app (или через ssh с хоста)
   export MOSKIT_DB_PASSWORD=секрет_для_пользователя_moskit  # опционально, иначе moskit_secret
   bash scripts/create_moskit_db_vds.sh
   ```

2. **Собрать образ и запустить сервис:**

   ```bash
   # С хоста (из репо atra-web-ide)
   ./scripts/deploy_moskit_api_vds.sh
   ```

   Скрипт синхронизирует исходники setki-21 на VDS, собирает образ `moskit-api:latest`, при необходимости создаёт БД и поднимает контейнер `moskit-api`.

3. **Настроить NPM:** для www.setki21.ru в Custom Locations указать `/api` и `/health` → **moskit-api:8080**. Образец конфига: `scripts/npm_proxy_setki21.conf`.

4. В **.env** на VDS при необходимости задать `MOSKIT_DB_PASSWORD` и `JWT_SECRET` (см. `.env.example`).

После этого разделы «Цены», «Дилеры», «Заказы» и калькулятор работают; логин/пароль админки не меняются.

## Логотип и загрузки в админке (чтобы не слетали)

Загрузки (логотип тенанта и др.) хранятся в каталоге **uploads** внутри контейнера moskit-api. Чтобы они не пропадали при пересоздании контейнера, в `docker-compose.vds.yml` для moskit-api добавлен том:

- `./moskit_uploads:/app/uploads`

При деплое через `deploy_moskit_api_vds.sh` на VDS копируется актуальный compose; на сервере нужна папка `moskit_uploads`. После первого применения один раз заново загрузите логотип в админке — дальше он будет храниться в `moskit_uploads` и переживёт перезапуски.
