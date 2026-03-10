# Runbook: Setki21 — белый экран

## Симптом

При открытии https://www.setki21.ru или дилерского сайта (например сеткимоскитки.рф) — белый экран.

**Единый источник истины по NPM и стеку:** **docs/SETKI21_NPM_SOURCE_OF_TRUTH.md** — перед любым изменением NPM или деплоем читать его, чтобы белые экраны не возвращались. После изменений запускать **`./scripts/verify_setki21_all_sites.sh`**.

## Какой стек используется

На VDS в `/home/atra/app/setki21_src` развёрнуты контейнеры **setki21-web-new** (Nuxt :3000) и **setki21-api-new** (Rust API :8080). NPM должен направлять:
- **/** → `setki21-web-new:3000`
- **/api**, **/health**, **/uploads** → `setki21-api-new:8080`

Если NPM направляет корень на `setki21-site:80` (статика) — это другой стек; см. **docs/SETKI21_SITE_DEPLOY_VDS.md** и **docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md**.

---

## Шаг 0. Сеть: NPM должен видеть setki21-api-new

Контейнер **atra-nginx-proxy** должен быть в **двух сетях**: **atra-network** (для других сервисов на VDS) и **setki21_src_default** (для setki21-api-new и setki21-web-new).

**Правильно (docker-compose.vds.yml):**
```yaml
nginx-proxy:
  networks:
    - atra-net
    - setki21_src_default

networks:
  atra-net:
    name: atra-network
  setki21_src_default:
    external: true
```

**Если NPM запущен без сети setki21_src_default:**
- Health API возвращает 000 или таймаут
- Tenant config через HTTPS → 502 Bad Gateway
- Nuxt SSR падает с `FetchError: 502`
- Белый экран (сайт мелькает, затем пропадает)

**Исправление (если NPM уже запущен без этой сети):**
```bash
docker network connect setki21_src_default atra-nginx-proxy
docker restart atra-nginx-proxy
docker network connect setki21_src_default atra-nginx-proxy  # повторно после перезапуска
```

**Проверка:** `curl https://www.setki21.ru/api/v1/tenant/config` должен возвращать 200 и JSON.

---

## Шаг 0.5. API не стартует: «password authentication failed for user moskit»

Если контейнер **setki21-api-new** в статусе Up, но в логах цикл:
```text
psql: error: connection to server at "postgres" (172.18.0.5), port 5432 failed: FATAL: password authentication failed for user "moskit"
Postgres (postgres) is unavailable - sleeping
```
причина: API подключён к **двум сетям** (default + atra-network). Имя **postgres** резолвится в **atra-postgres** (172.18.0.5), а не в Postgres стека setki21_src (172.19.0.5). У atra-postgres другие учётные данные.

**Исправление:** в **docker-compose.vds.yml** (репо setki-21) для сервиса **api** задать явный хост БД:
```yaml
services:
  api:
    environment:
      - DATABASE_URL=postgres://moskit:password@setki21_src-postgres-1:5432/moskit
```
Затем на VDS: скопировать обновлённый `docker-compose.vds.yml` в `/home/atra/app/setki21_src/`, выполнить `docker compose -f docker-compose.yml -f docker-compose.vds.yml up -d api --force-recreate`. Убедиться, что контейнер Postgres стека (**setki21_src-postgres-1**) запущен: `docker compose up -d postgres`.

---

## Шаг 0.6. Мерцание и белый экран: в бандле прописан localhost

**Симптом:** Сайт мелькает и пропадает; в DevTools (F12) → Network видно запросы к **http://localhost:8081** или **http://localhost:8083** вместо текущего домена (https://www.setki21.ru и т.д.). Контейнеры и API при этом в порядке.

**Причина:** Образ **web** (setki21-web-new) был собран без `NUXT_PUBLIC_API_URL` или с дефолтом localhost. В клиентский бандл Nuxt зашивается `apiUrl` на этапе сборки; если не задать продакшен-URL, в браузере запросы уходят на localhost пользователя → ошибки → белый экран/мерцание.

**Исправление:** Пересобрать образ **web** с явным продакшен-URL и перезапустить контейнер на VDS:
```bash
# На VDS в /home/atra/app/setki21_src
export NUXT_PUBLIC_API_URL=https://www.setki21.ru
docker compose -f docker-compose.yml -f docker-compose.vds.yml build --no-cache web
docker compose -f docker-compose.yml -f docker-compose.vds.yml up -d web
```
Либо в **.env** на VDS задать `NUXT_PUBLIC_API_URL=https://www.setki21.ru` и затем `docker compose build web && docker compose up -d web`.

В репо setki-21 дефолты уже исправлены: **docker-compose.yml** и **Dockerfile.web** по умолчанию используют `https://www.setki21.ru`; в **nuxt.config.ts** и во всех страницах/сторах fallback для apiUrl — пустая строка (same-origin), а не localhost. После обновления кода из репо и пересборки web проблема не должна возвращаться.

---

## Шаг 1. Контейнеры и health (на VDS)

```bash
ssh root@45.10.43.248 'docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "setki21|nginx-proxy"'
```

Ожидается: `setki21-api-new` и `setki21-web-new` в статусе **Up**.

```bash
ssh root@45.10.43.248 'docker exec atra-nginx-proxy curl -s -o /dev/null -w "%{http_code}" http://setki21-api-new:8080/health'
```

Ожидается: **200**.

---

## Шаг 2. Tenant config (главный сайт)

```bash
ssh root@45.10.43.248 'docker exec atra-nginx-proxy curl -s -H "Host: www.setki21.ru" http://setki21-api-new:8080/api/v1/tenant/config | head -c 300'
```

Ожидается: JSON (начинается с `{"dealer_id"` или аналог). Если пусто или HTML/ошибка — API не отдаёт конфиг → фронт не может отрисоваться → белый экран.

---

## Шаг 3. Tenant config (дилерский домен)

Для сеткимоскитки.рф (Punycode в Host):

```bash
ssh root@45.10.43.248 'docker exec atra-nginx-proxy curl -s -H "Host: xn--e1agaahbbnszfhh.xn--p1ai" http://setki21-api-new:8080/api/v1/tenant/config | head -c 300'
```

Ожидается: JSON дилера. Если 404 или «Tenant not found» — проверить в БД `dealers.domain = 'xn--e1agaahbbnszfhh.xn--p1ai'` и логи API.

---

## Шаг 4. Главная от Nuxt (HTML с title)

```bash
ssh root@45.10.43.248 'docker exec atra-nginx-proxy curl -s http://setki21-web-new:3000/ | grep -o "<title>.*</title>"'
```

Ожидается: непустая строка с тегом `<title>`. Если пусто или 502 — проблема с контейнером web.

---

## Шаг 5. NPM: куда смотрит корень

В панели NPM (http://45.10.43.248:81) для Proxy Host **www.setki21.ru** (и при необходимости для дилерских доменов) на вкладке **Details** должно быть:

- **Forward Hostname / IP:** `setki21-web-new`
- **Forward Port:** `3000`

Если указано `setki21-site` и порт 80 — трафик идёт на старую статику; при новом стеке нужны именно web-new и 3000.

---

## Шаг 6. Логи

```bash
ssh root@45.10.43.248 'docker logs setki21-api-new --tail 30'
ssh root@45.10.43.248 'docker logs setki21-web-new --tail 30'
```

Искать: 502, FetchError, «Tenant not found», panic, connection refused.

---

## Шаг 7. Браузер

- Жёсткое обновление: **Ctrl+F5** (или Cmd+Shift+R).
- Очистить кэш сайта или открыть в режиме инкогнито.
- В DevTools (F12) → Console — есть ли красные ошибки (например Failed to fetch, 404 на `/api/v1/tenant/config`)?

---

## Краткий чеклист

| Проверка              | Команда/действие |
|-----------------------|------------------|
| Контейнеры Up         | `docker ps \| grep setki21` |
| Health 200            | `curl … setki21-api-new:8080/health` |
| Tenant config JSON    | `curl -H "Host: www.setki21.ru" …/api/v1/tenant/config` |
| Nuxt отдаёт HTML      | `curl http://setki21-web-new:3000/` → есть `<title>` |
| NPM Forward           | setki21-web-new:3000 для / |
| Логи без критических  | `docker logs setki21-api-new setki21-web-new --tail 30` |
| Кэш браузера          | Ctrl+F5 / инкогнито |

---

## Проверка по всем сайтам (единый чеклист)

Белый экран может быть на **главном** или на **дилерских** доменах. Для каждого сайта должны выполняться: контейнеры Up, NPM ведёт **/** на `setki21-web-new:3000`, а запрос к `/api/v1/tenant/config` с соответствующим **Host** возвращает JSON.

| Сайт | URL для проверки | Host для tenant config | Ожидание |
|------|------------------|------------------------|----------|
| **Главный** | https://www.setki21.ru | `www.setki21.ru` | JSON головного tenant |
| **Главный (без www)** | https://setki21.ru | `setki21.ru` | редирект на www или тот же JSON |
| **Сетки Москитки (Йошкар-Ола)** | https://сеткимоскитки.рф или https://xn--e1agaahbbnszfhh.xn--p1ai | `xn--e1agaahbbnszfhh.xn--p1ai` или `www.xn--e1agaahbbnszfhh.xn--p1ai` | JSON дилера |
| **Сетки Москитки НН** | https://setkimoskitki.ru | `setkimoskitki.ru` или `www.setkimoskitki.ru` | JSON дилера |

### Команды для проверки tenant config по каждому хосту (на VDS)

```bash
# Главный
docker exec atra-nginx-proxy curl -s -H "Host: www.setki21.ru" http://setki21-api-new:8080/api/v1/tenant/config | head -c 200

# setki21.ru без www (если отдельный Proxy Host)
docker exec atra-nginx-proxy curl -s -H "Host: setki21.ru" http://setki21-api-new:8080/api/v1/tenant/config | head -c 200

# Сетки Москитки (кириллица → в браузере приходит Punycode)
docker exec atra-nginx-proxy curl -s -H "Host: xn--e1agaahbbnszfhh.xn--p1ai" http://setki21-api-new:8080/api/v1/tenant/config | head -c 200
docker exec atra-nginx-proxy curl -s -H "Host: www.xn--e1agaahbbnszfhh.xn--p1ai" http://setki21-api-new:8080/api/v1/tenant/config | head -c 200

# setkimoskitki.ru
docker exec atra-nginx-proxy curl -s -H "Host: setkimoskitki.ru" http://setki21-api-new:8080/api/v1/tenant/config | head -c 200
docker exec atra-nginx-proxy curl -s -H "Host: www.setkimoskitki.ru" http://setki21-api-new:8080/api/v1/tenant/config | head -c 200
```

Если для какого-то Host возвращается пусто, 404 или «Tenant not found» — на этом сайте будет белый экран. Проверить в БД: `SELECT id, domain FROM dealers;` — домены должны быть в том виде, в каком приходят в заголовке (Punycode для кириллицы; API срезает `www.` сам).

---

## Заявки (обратный звонок) не приходят

**Симптом:** Пользователь отправляет форму «Заказать обратный звонок», в интерфейсе может быть успех или ошибка, но письмо на email не приходит.

**Цепочка:** Браузер → NPM → **setki21-api-new:8080** (Rust) → прокси `POST /api/callback` → **setki21-web-new:3000** (Nuxt `server/api/callback.post.ts`) → nodemailer → SMTP → почта.

**Что проверить:**

1. **Прокси API → Web:** API по умолчанию шлёт запрос на `http://web:3000/api/callback` (сервис `web` в том же compose). Убедиться, что оба контейнера в одной сети (setki21_src_default). При необходимости задать на VDS в env контейнера **api**: `CALLBACK_PROXY_URL=http://setki21-web-new:3000`.

2. **SMTP в контейнере web (частая причина):** Заявки (обратный звонок, контакт, заказ сеток) отправляются через **один и тот же SMTP** из env. В каталоге деплоя (`/home/atra/app/setki21_src`) в **.env** задать те же переменные, что и для оформления заказов:
   ```bash
   SMTP_HOST=smtp.timeweb.ru
   SMTP_PORT=465
   SMTP_USER=info@setki21.ru
   SMTP_PASS=пароль_от_ящика
   CONTACT_EMAIL=info@setki21.ru
   ```
   Если используете **Timeweb** (как для заказов сеток) — в .env задать `SMTP_HOST=smtp.timeweb.ru`, `SMTP_PORT=465`. Если остаётесь на **Mail.ru** — нужен пароль приложения в `SMTP_PASS` и `SMTP_PORT=587`. После правки .env перезапустить web: `docker compose -f docker-compose.yml -f docker-compose.vds.yml up -d web`.

3. **Логи:** При ошибке отправки смотреть логи Nuxt: `docker logs setki21-web-new --tail 50` (ошибки nodemailer, 503). Логи API: `docker logs setki21-api-new --tail 30` (если прокси возвращает 502 — до Web не доходит).

**Заявки с сайта дилера уходят на info@setki21.ru, а не на email дилера:** Фронт отправляет получателя в теле запроса (`toEmail`). Получатель берётся из конфига тенанта: сначала `contacts.emails[0]`, при отсутствии — поле `email` дилера. Нужно, чтобы у дилера в админке был заполнен **Email** (основной) и/или **Контакты → emails**. Проверка: открыть сайт дилера (например www.setkimoskitki.ru), в консоли браузера выполнить запрос к `/api/v1/tenant/config` (тот же origin) — в ответе должны быть `email` или `contacts.emails` с нужным адресом. После правок в коде (layout, CallbackModal, tenant store) обязательно **пересобрать образ web** и перезапустить контейнер.

**Текст после отправки заявки («рабочее время»):** Сообщение «Перезвоним в рабочее время: …» берётся из конфига тенанта (`branding.working_hours`). Если отображается дефолт «Пн–Пт 10:00–18:00» — в админке у дилера/филиала заполнить поле «Режим работы» и сохранить.

---

### NPM: все Proxy Host для этих доменов

В NPM (http://45.10.43.248:81) для **каждого** Proxy Host, отвечающего за www.setki21.ru, setki21.ru, сеткимоскитки.рф, setkimoskitki.ru:

- **Details** → **Forward Hostname:** `setki21-web-new`, **Forward Port:** `3000`
- **Custom Locations**: `/api`, `/health`, `/uploads` → `setki21-api-new:8080`

Иначе трафик уходит не туда и на части сайтов будет белый экран.

---

## Если только www-версия даёт белый экран (без www — норм)

**Симптом:** https://www.setki21.ru — белый экран, https://setki21.ru — открывается.

**Причина:** API искал tenant только по точному Host; в БД у головного дилера записан домен `setki21.ru` без www, поэтому для `Host: www.setki21.ru` возвращался 400 «Tenant not found».

**Исправление (в коде moskit-api, уже внедрено):** В `handlers/content.rs` для `/api/v1/tenant/config` и фавикона добавлен fallback: если по точному Host дилер не найден и Host начинается с `www.`, повторный поиск по домену без префикса (www.setki21.ru → setki21.ru). После обновления кода setki-21 и пересборки образа API на VDS www-версии работают без отдельной записи в БД.

---

## Если API возвращает «Tenant not found for this domain»

1. **Проверить, что NPM подключён к сети setki21** (Шаг 0) — иначе до API запросы не доходят и может отдаваться кэш/ошибка.
2. **Проверить БД moskit:** домены должны быть в таблице **dealers** (поле `domain`) и/или в **dealer_domains** (связка `dealer_id` + `domain`). Логика определения tenant в коде **moskit-api** (репо setki-21). Пример проверки:
   ```bash
   docker exec setki21_src-postgres-1 psql -U moskit -d moskit -t -c "SELECT domain, name FROM dealers; SELECT dd.domain, d.name FROM dealer_domains dd JOIN dealers d ON d.id = dd.dealer_id;"
   ```
3. Если в БД домены есть, а API всё равно возвращает 400 — проверить в коде moskit-api (setki-21), по какому заголовку определяется хост (Host / X-Forwarded-Host) и по какой таблице идёт поиск (dealers.domain или dealer_domains.domain).

---

Связанные документы: **docs/CHANGES_FROM_OTHER_CHATS.md** (§49, §53), **docs/tasks/VICTORIA_TASK_SETKI21_FULL_VERIFICATION.md**.
