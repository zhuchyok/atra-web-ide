# Деплой сайта Сетки 21 на www.setki21.ru (VDS)

Чтобы по **https://www.setki21.ru** открывался сайт проекта Сетки 21, а не только API.

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
4. **Custom Locations** → добавь два правила:
   - **Location:** `/api` → **Forward** `moskit-api:8080`.
   - **Location:** `/health` → **Forward** `moskit-api:8080`.
5. Сохрани.

Образец конфига NPM: **scripts/npm_proxy_setki21.conf**. В итоге: запросы к **/** идут в setki21-site (сайт), к **/api** и **/health** — в moskit-api (вход, цены, админка).

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
