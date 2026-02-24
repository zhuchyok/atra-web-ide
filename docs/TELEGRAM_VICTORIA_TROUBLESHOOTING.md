# Victoria в Telegram — диагностика «не доступна»

## Отчёты и уведомления не приходят

**С февраля 2026** отчёты и уведомления в Telegram отправляет сервис **telegram-notifications** в Docker (Knowledge OS).

1. **Проверьте, что сервис запущен:**

   ```bash
   docker ps | grep telegram-notifications
   ```

   Если контейнера нет: `docker-compose -f knowledge_os/docker-compose.yml up -d telegram-notifications`

2. **Проверьте переменные в .env (или в docker-compose):**
   - `TELEGRAM_BOT_TOKEN` (или `TG_TOKEN`) — токен бота, который будет слать сообщения.
   - `TELEGRAM_USER_ID` (или `CHAT_ID`) — **ваш** Telegram user id (для личного чата = chat_id). Узнать: написать @userinfobot в Telegram.

   Если не заданы или заданы неверно — воркер в логах пишет предупреждение и ничего не шлёт.

3. **Что шлёт воркер:**
   - Записи из таблицы `notifications` (каждые 60 с): новые эксперты, события дебатов, онбординг и т.д.
   - Ежедневный отчёт в **8:00** и еженедельный (понедельник **9:00**) — если включено `TELEGRAM_REPORTS_ENABLED=true`.

4. **Логи воркера:**
   ```bash
   docker logs telegram-notifications --tail 50
   ```

Раньше уведомления из БД отправлял только процесс `telegram_gateway` (getUpdates + check_notifications), а отчёты — скрипт `singularity_autonomous`; они не были сервисами в Docker, поэтому по умолчанию ничего не приходило. Теперь один контейнер **telegram-notifications** делает и то, и другое.

**Важно:** для получения отчётов и уведомлений в личку задайте в `.env` **свой** `TELEGRAM_USER_ID` (узнать: @userinfobot). В docker-compose по умолчанию подставлен пример 556251171 — замените на свой ID и перезапустите: `docker-compose -f knowledge_os/docker-compose.yml up -d telegram-notifications`.

---

## Быстрая проверка (чат с Victoria)

### 1. Бот запущен?

```bash
pgrep -fl victoria_telegram_bot
```

Должен показать процесс. Если пусто — запустите (рекомендуется из .venv — тогда Pillow и pypdf уже есть):

```bash
cd /Users/bikos/Documents/atra-web-ide
.venv/bin/python -m src.agents.bridge.victoria_telegram_bot
```

Или: `python3 -m src.agents.bridge.victoria_telegram_bot` (если пакеты установлены в этом Python).

### 2. Victoria Agent отвечает?

```bash
curl http://localhost:8010/health
```

Должен вернуть `200`. Если нет — поднимите Knowledge OS: `docker-compose -f knowledge_os/docker-compose.yml up -d`

### 3. Ваш Telegram ID совпадает с TELEGRAM_USER_ID?

Бот **игнорирует** сообщения от пользователей с ID ≠ `TELEGRAM_USER_ID`.

Проверка:

1. Напишите @userinfobot в Telegram
2. Ваш ID должен совпадать с `TELEGRAM_USER_ID` в .env (сейчас: 556251171)

Если ID другой — обновите .env:

```env
TELEGRAM_USER_ID=ВАШ_РЕАЛЬНЫЙ_ID
```

И перезапустите бота.

### 4. Пишете нужному боту?

Токен в .env привязан к конкретному боту. Убедитесь, что пишете именно ему (имя можно узнать в @BotFather).

### 5. Логи бота

Если бот запущен в фоне:

```bash
tail -f victoria_bot.log
```

Или смотрите вывод в терминале при запуске в foreground.

### 6. «PIL (Pillow) не установлен» / «pypdf не установлен»

Бот запускается **тем же Python**, что в команде. **Рекомендуемый способ:** запускать из venv проекта, где пакеты уже есть:

```bash
cd /Users/bikos/Documents/atra-web-ide && .venv/bin/python -m src.agents.bridge.victoria_telegram_bot
```

Если venv нет: `python3 -m venv .venv && .venv/bin/pip install Pillow pypdf` (или `pip install -r requirements.txt`).

Если бот запускаете системным `python3` или из Launchd — в логе при старте выводится команда вида:

```
Установите в окружении бота: /путь/к/python -m pip install Pillow pypdf
```

Скопируйте и выполните её (для системного Homebrew Python может понадобиться `--user` или отдельный venv).

### 7. Бот не отвечает после перезагрузки Mac

Victoria Telegram Bot — **процесс на хосте**, не в Docker. После перезагрузки его нужно запускать вручную или через LaunchAgent.

**Запуск вручную (из .venv — с Pillow/pypdf):**

```bash
cd /path/to/atra-web-ide && .venv/bin/python -m src.agents.bridge.victoria_telegram_bot
```

**Автозапуск при загрузке (опционально):**

```bash
bash scripts/setup_victoria_telegram_bot_autostart.sh
```

Скрипт создаёт `~/Library/LaunchAgents/com.atra.victoria-telegram-bot.plist` и загружает его в launchd. Бот будет запускаться при входе в систему и перезапускаться при падении.

**Проверка после перезагрузки:** `bash scripts/verify_mac_studio_self_recovery.sh` — в блоке 4 выводится статус Victoria Telegram Bot (⚠️ если не запущен).

---

## Найденные причины (victoria_bot.log)

### 1. DNS/сеть: `[Errno 8] nodename nor servname provided, or not known`

Бот не может разрешить `api.telegram.org`. Бывает при:

- потере сети / смене Wi‑Fi / VPN
- выходе Mac из сна
- временном сбое DNS

**Решение:** Бот теперь делает 3 попытки с backoff. Если часто повторяется — проверьте DNS (`scutil --dns`), отключите VPN на время теста.

### 2. Таймаут Victoria (сложные задачи)

Сложные запросы (проверка RAM, анализ кода и т.п.) обрабатываются долго. По умолчанию бот ждёт **15 минут** (`VICTORIA_POLL_TIMEOUT_SEC=900`). Для ещё более долгих задач добавьте в `.env`:

```env
VICTORIA_POLL_TIMEOUT_SEC=1200
```

(20 мин). Затем перезапустите бота.

**Обновление:** Бот теперь поддерживает:

- **Fallback sync**: если Victoria не вернул 202 (async), бот пробует sync-запрос
- **Ответ 200**: если Victoria вернул sync-ответ (200), он сразу отправляется в Telegram
- **Лимит вывода** увеличен до 8000 символов (раньше 2000 — обрезало сложные ответы)

### 3. Telegram 400: `Can't parse entities: Can't find end of the entity`

Ответ Victoria с кодом (`_`, `*`, `` ` ``) вызывал ошибку парсинга. Исправлено: ответы отправляются только как plain text, без Markdown.

---

## Типичные причины

| Симптом                                        | Причина                                | Решение                                                  |
| ---------------------------------------------- | -------------------------------------- | -------------------------------------------------------- |
| Бот не отвечает                                | Процесс не запущен                     | `python3 -m src.agents.bridge.victoria_telegram_bot`     |
| Бот молчит                                     | ID не совпадает                        | Проверить TELEGRAM_USER_ID через @userinfobot            |
| «Victoria недоступна»                          | Victoria (8010) не отвечает            | Запустить Docker, проверить `curl localhost:8010/health` |
| «TELEGRAM_BOT_TOKEN не установлен»             | .env не загружен                       | Запускать из корня проекта, проверить путь к .env        |
| `nodename nor servname` в логах                | DNS/сеть                               | Проверить интернет, DNS, VPN                             |
| `Can't parse entities` при отправке            | Markdown в ответе                      | Обновлено: plain text                                    |
| Таймаут на сложных задачах                     | Ожидание 15 мин по умолчанию           | Увеличить `VICTORIA_POLL_TIMEOUT_SEC` в .env             |
| Pillow/pypdf «не установлен» после перезапуска | Другой Python у бота и у `pip install` | Выполнить команду из лога бота (тот же Python)           |
