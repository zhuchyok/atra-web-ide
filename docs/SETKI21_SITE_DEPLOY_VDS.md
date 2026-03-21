# Деплой сайта Сетки 21 на www.setki21.ru (VDS)

Чтобы по **https://www.setki21.ru** открывался сайт проекта Сетки 21, а не только API.

> **Важно:** В продакшене используется стек **setki21_src** (контейнеры **setki21-web-new:3000** и **setki21-api-new:8080**). NPM должен направлять все домены Setki21 на этот стек. **Единый источник истины по NPM и маршрутизации:** **docs/SETKI21_NPM_SOURCE_OF_TRUTH.md**. При белом экране на всех сайтах — **docs/runbooks/SETKI21_WHITE_SCREEN.md**. Ниже описан альтернативный вариант со статикой (**setki21-site**); не переключайте NPM на setki21-site:80 без явной цели — иначе белые экраны вернутся.

> **Цены в админке:** сейчас API на VDS — это только atra-core (вход без БД). Разделы «Цены», «Дилеры», «Заказы» и загрузка цен в калькуляторе работают через **moskit-api** (проект setki-21) и PostgreSQL. Как их развернуть — см. **docs/SETKI21_ADMIN_PRICING_VDS.md**.

**На VDS в docker-compose уже добавлен сервис `setki21-site`.** Если compose на сервере старый, обнови его из репо (файл `docker-compose.vds.yml` → скопировать в `/home/atra/app/docker-compose.yml` на VDS).

Для корректной выдачи главной при первом заходе на **/** используется кастомный nginx-конфиг (`setki21_nginx/default.conf`): `index index.html 200.html` и `try_files $uri $uri/ $uri.html /200.html =404` для SPA. Конфиг лежит в репо в `setki21_nginx/` и при деплое скриптом копируется на VDS вместе со статикой.

## 1. Где лежит проект сайта

Код проекта Сетки 21: **`/Users/bikos/Documents/dev/setki-21`**.  
Проект на **Nuxt 4**; для деплоя нужна статическая сборка в `.output/public`.

## 2. Сборка сайта локально (Nuxt)

Для продакшена (админка, калькулятор, цены) API должен быть с того же домена — при сборке задаётся `NUXT_PUBLIC_API_URL`:

```bash
cd /Users/bikos/Documents/dev/setki-21
npm ci
NUXT_PUBLIC_API_URL=https://www.setki21.ru npm run generate
```

Скрипт деплоя `deploy_setki21_site_vds.sh` по умолчанию сам выставляет `NUXT_PUBLIC_API_URL=https://www.setki21.ru`.

После сборки статика будет в **`.output/public/`**.

## 3. Создание папки на VDS и заливка файлов

На VDS уже добавлен сервис **setki21-site** (nginx раздаёт статику из папки `setki21_site/`).

```bash
# Создать папки на VDS (один раз)
ssh root@45.10.43.248 "mkdir -p /home/atra/app/setki21_site /home/atra/app/setki21_nginx"

# Залить статику Nuxt (.output/public)
rsync -az --delete /Users/bikos/Documents/dev/setki-21/.output/public/ root@45.10.43.248:/home/atra/app/setki21_site/

# Залить nginx-конфиг для SPA (устраняет 404 при первом открытии /). Из корня репо atra-web-ide:
rsync -az setki21_nginx/ root@45.10.43.248:/home/atra/app/setki21_nginx/
```

## 4. Запуск контейнера сайта на VDS

```bash
ssh root@45.10.43.248 "cd /home/atra/app && docker-compose up -d setki21-site"
```

(Или через полный путь к compose, если используешь другой файл.)

## 5. Nginx Proxy Manager: www.setki21.ru → сайт + API

Чтобы **www.setki21.ru** показывал сайт, а **/health** и **/api** шли в **moskit-api** (единый API Сетки 21):

1. Открой NPM: http://45.10.43.248:81
2. **Proxy Hosts** → открой хост с доменом **www.setki21.ru**.
3. **Details:**
   - **Forward Hostname / IP:** `setki21-site`
   - **Forward Port:** `80`
   - Остальное без изменений → **Save**.
4. **Custom Locations** → добавь три правила (порядок важен: более специфичные выше):
   - **Location:** `/uploads` → **Forward** `setki21-api-new:8080` (логотипы дилеров из volume setki21_uploads).
   - **Location:** `/api` → **Forward** `moskit-api:8080` (tenant, цены, админка — БД с дилерами).
   - **Location:** `/health` → **Forward** `moskit-api:8080`.
5. Сохрани.

**Почему так:** Контейнер **moskit-api** подключён к БД с tenant/дилерами — без него главная даёт белый экран (нет `/api/v1/tenant/config`). Контейнер **setki21-api-new** отдаёт файлы из `/home/atra/setki21_uploads` — для логотипов нужен именно он. Образец конфига: **scripts/npm_proxy_setki21.conf**.

> **⚠️ DNS-кэш nginx (важно при пересоздании контейнеров):**
> Nginx кэширует IP контейнеров при старте. Если `setki21-api-new` пересоздать — получит новый IP, а nginx будет слать запросы на старый → `502 Bad Gateway`.
> **Решение уже применено:** в `/home/atra/app/nginx_proxy/data/nginx/proxy_host/1.conf` добавлена строка `resolver 127.0.0.11 valid=10s ipv6=off;` — nginx переспрашивает Docker DNS каждые 10 сек.
> **Если всё же 502 после пересоздания контейнера:** `docker exec atra-nginx-proxy nginx -s reload` (занимает ~1 сек, без даунтайма).

## 6. Проверка

- https://www.setki21.ru — открывается главная страница сайта Сетки 21.
- https://www.setki21.ru/health — ответ от moskit-api (OK).
- Вход в админку: admin@setki21.ru и пароль из .env.atra; после входа доступны разделы «Цены», «Дилеры», «Заказы».

## Обновление сайта

После изменений в проекте Сетки 21 заново собери и залей статику:

```bash
cd /Users/bikos/Documents/dev/setki-21 && npm run generate
rsync -az --delete /Users/bikos/Documents/dev/setki-21/.output/public/ root@45.10.43.248:/home/atra/app/setki21_site/
ssh root@45.10.43.248 "cd /home/atra/app && docker-compose restart setki21-site"
```

## 7. Диагностика: «деплой прошёл, но сайт не обновился»

Если после деплоя на сайте по-прежнему старая версия (например, старые стили кнопок в админке):

1. **Проверить, что отдаёт VDS:** на сервере в `index.html` должен быть актуальный хэш CSS, например `entry.Bc_fN7v_.css`. Проверка:
   ```bash
   ssh root@45.10.43.248 "grep -o 'entry\.[^\"]*\.css' /home/atra/app/setki21_site/index.html"
   ```
2. **Проверить, что отдаёт живой сайт:** запрос к https://www.setki21.ru/ не должен возвращать другой хэш (старый `entry.D-omT3Kw.css` и т.п.):

   ```bash
   curl -sS "https://www.setki21.ru/" | grep -o 'entry\.[^"]*\.css'
   ```

   Если на VDS — новый хэш, а с живого URL — старый, **трафик www.setki21.ru не идёт на setki21-site** на этом VDS.

3. **Что проверить дальше:**
   - **DNS:** `www.setki21.ru` должен указывать на IP VDS (45.10.43.248). Проверка: `dig +short www.setki21.ru`.
   - **NPM:** в панели http://45.10.43.248:81 для Proxy Host с доменом **www.setki21.ru** в Details должно быть **Forward Hostname: setki21-site**, **Forward Port: 80**. Не moskit-api и не другой хост.
   - **CDN:** если перед сервером стоит Cloudflare или другой CDN — сделать Purge Cache для www.setki21.ru после деплоя, иначе отдаётся закэшированный старый HTML/CSS.
   - **Другой сервер:** если есть ещё один хост (например, setki21.ru без www или другой IP), убедиться, что пользователь заходит именно на www.setki21.ru и что этот домен ведёт на наш VDS и NPM.

Пошаговый runbook при падении автоматической верификации деплоя: **`docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md`**.
