# Настройка Nginx Proxy Manager для Atra OS Kernel

VDS: **45.10.43.248**  
atra-core слушает порт **8081** (контейнер `atra-kernel`).

## Шаги в NPM (веб-интерфейс)

1. **Открой панель NPM**  
   http://45.10.43.248:81

2. **Войди** (логин/пароль, которые задавал при первом заходе).

3. **Proxy Hosts → Add Proxy Host**
   - **Domain Names:**
     - Если есть домен: `api.твой-домен.ru`
     - Пока без домена: оставь `45.10.43.248` или добавь запись типа `atra-api.local` и в хосте пропиши в `/etc/hosts` или используй IP.
   - **Scheme:** `http`
   - **Forward Hostname / IP:** `atra-kernel` (имя контейнера в одной сети с NPM)
   - **Forward Port:** `8081`
   - **Cache Assets:** по желанию
   - **Block Common Exploits:** включено
   - **Websockets Support:** включи, если позже появятся WS.

4. **Save** — после сохранения запросы на выбранный домен (или IP через NPM) будут проксироваться на `http://atra-kernel:8081`.

5. **(Опционально) SSL**
   - В карточке Proxy Host нажми **Edit** → вкладка **SSL**.
   - **SSL Certificate:** Request a new SSL Certificate (Let's Encrypt).
   - Включи **Force SSL**.
   - Нужен реальный домен, указывающий на 45.10.43.248 (A-запись).

## Проверка без домена (прямо по IP)

Если прокси не настраивать, API доступен напрямую:

- Health: http://45.10.43.248:8081/health
- Info: http://45.10.43.248:8081/api/v1/info

После настройки Proxy Host в NPM (например, на домен `api.example.com`):

- http://api.example.com/health
- https://api.example.com/health (если включён SSL)

## Сеть Docker

Контейнеры `atra-nginx-proxy` и `atra-kernel` в одной сети `atra-network`, поэтому в NPM в качестве Forward Hostname указывается **atra-kernel**, порт **8081**.

## Оба домена: setki21.ru и www.setki21.ru

Чтобы работали и **https://setki21.ru/health**, и **https://www.setki21.ru/health**:

1. **Proxy Hosts** → открой нужный хост (тот, где сейчас **www.setki21.ru**).
2. Вкладка **Details** → в поле **Domain Names** добавь второй домен: **setki21.ru** (должны быть оба: `www.setki21.ru` и `setki21.ru`).
3. Сохрани (**Save**).
4. Вкладка **SSL** → если появится «Internal Error» или сертификат только для www, выбери снова **Request a new Certificate** (NPM запросит серт на оба имени) и сохрани.
5. Подожди 1–2 минуты, проверь: `curl -sL https://setki21.ru/health` — должен вернуть `OK`.

## Если Let's Encrypt выдаёт «Internal Error» или «Some challenges have failed»

- **Rate limit:** после 5 неудачных проверок для одного домена Let's Encrypt блокирует запросы на **1 час**. Подожди час и запроси сертификат снова.
- **Почему падала проверка для setki21.ru:** у отдельного Proxy Host для setki21.ru в NPM не было блока для `/.well-known/acme-challenge/`, запросы уходили в atra-core и возвращали 404. На VDS в конфиг для этого хоста добавлен `include conf.d/include/letsencrypt-acme-challenge.conf;` (если правишь хост в NPM и сохраняешь, конфиг может перезаписаться — тогда после снятия rate limit снова запроси сертификат; NPM при запросе серта может сам добавить этот блок).

## Вход в личный кабинет (Сетки 21)

Сайт www.setki21.ru отправляет запросы входа на `POST /api/v1/auth/login`. Сейчас их обрабатывает **atra-core** (без БД, проверка по файлу).

1. **На VDS** в каталоге приложения нужен файл **`.env.atra`** (именно он передаётся в контейнер atra-core):
   ```bash
   AUTH_ADMIN_EMAIL=admin@setki21.ru
   AUTH_ADMIN_PASSWORD=твой_надёжный_пароль
   ```
2. В `docker-compose` для atra-core задано `env_file: .env.atra`.
3. После изменения `.env.atra` перезапусти:  
   `cd /home/atra/app && docker-compose up -d atra-core`
4. Вход на https://www.setki21.ru/dealers тогда проверяет email/пароль и редиректит в `/admin`.

**Важно:** цены, дилеры и заказы в админке при этом **не появятся** — они отдаются другим бэкендом (moskit-api + БД). Чтобы развести роли и убрать путаницу, см. **docs/SETKI21_API_RAZBOR.md** и **docs/SETKI21_ADMIN_PRICING_VDS.md**.
