# Падение MLX (мозг): причина, ответственные, исправления

**Дата разбора:** 2026-02-23. **Правило:** такого не должно повторяться — мониторинг обязан обнаружить падение и перезапустить, либо дефибриллятор (webhook) запускает восстановление на хосте.

---

## 1. Что произошло в этот раз

- **Лог MLX** (`~/Library/Logs/atra/mlx_api_server.log`): последний запуск в 15:17 — сервер поднялся, предзагрузил phi3.5:3.8b, затем **ERROR: [Errno 48] address already in use** при привязке к `0.0.0.0:11435`. Процесс завершился. То есть при попытке перезапуска порт 11435 был ещё занят (предыдущий процесс не освободил порт или запустились два экземпляра).
- **Раньше** типичная причина падения MLX — **Metal assertion** (`addCompletedHandler: failed assertion`) или **OOM** при перегрузке (см. docs/MLX_PYTHON_CRASH_CAUSE.md, VERIFICATION_CHECKLIST_OPTIMIZATIONS). После такого краша процесс исчезает; при следующем старте нужна проверка порта.

---

## 2. Кто отвечает за контроль и перезапуск

| Звено | Ответственность | Что было не так |
|-------|-----------------|------------------|
| **com.atra.mlx-monitor** (LaunchAgent) | Каждые 30 с проверять процесс и GET :11435/health; при падении вызывать `start_mlx_api_server.sh` (освобождает порт и запускает MLX). | **Не сработал:** `launchctl list` показывает **exit code 126** (программа не выполняется — часто нет PATH или скрипт не запускается под launchd). Монитор не работал → падение не обнаружено, перезапуск не выполнен. |
| **com.atra.mlx-api-server** (LaunchAgent) | Запуск при входе в систему; wrapper `start_mlx_server.sh` перезапускает uvicorn при падении; KeepAlive Crashed=true. | **Не сработал:** **exit code 126** — тот же диагноз (PATH/окружение в plist). Плюс wrapper **не освобождал порт** перед перезапуском → при краше и повторном старте получали «address already in use». |
| **Оркестратор** (Docker, knowledge_os) | Каждые 300 с проверка Ollama/MLX; при недоступности MLX — POST на RECOVERY_WEBHOOK_URL (дефибриллятор). | Обнаруживает падение с задержкой до 5 мин; восстановление возможно только если на хосте слушает **recovery listener** (порт 9099). |
| **Recovery listener** (порт 9099) | Принять webhook от оркестратора и запустить `system_auto_recovery.sh` (в т.ч. запуск MLX). | **com.atra.recovery-listener** в launchd имеет **exit 2** — либо не запущен, либо падает. Webhook с контейнера не обрабатывается. |

**Итог:** ни монитор MLX, ни автозапуск MLX под launchd не работали (126); recovery listener тоже не в порядке (2). В результате после падения MLX никто не перезапустил мозг автоматически.

---

## 3. Что исправлено в коде

1. **start_mlx_server.sh (wrapper):** перед каждым запуском uvicorn добавлено **освобождение порта 11435** (kill процесса, занимающего порт, пауза 2 с). Устраняет «address already in use» при перезапуске после краша.
2. **setup_mlx_autostart.sh:** в plist **com.atra.mlx-api-server** добавлен блок **EnvironmentVariables** с **PATH** (`/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`), чтобы под launchd находились `python3` и `uvicorn` (устранение 126).
3. **Launcher-прослойка:** в `~/Library/Application Support/Atra/launch_mlx.sh` создан скрипт-посредник, который находится вне папки `Documents`. Это позволяет `launchd` запускать его без блокировки TCC, а прослойка уже вызывает основной код.
4. **WorkingDirectory:** в plist рабочая директория изменена на `/tmp`, чтобы избежать ошибки `getcwd: Operation not permitted` при старте процесса.

---

## 4. Что сделать на хосте (обязательно)

1. **Пересоздать и загрузить LaunchAgents** (чтобы применились PATH, логика освобождения порта и launcher):
   ```bash
   cd /Users/bikos/Documents/atra-web-ide
   bash scripts/setup_mlx_autostart.sh
   bash scripts/setup_system_auto_recovery.sh
   ```
   После этого проверить:
   ```bash
   launchctl list | grep -E "mlx|recovery"
   ```
   У **com.atra.mlx-api-server** и **com.atra.mlx-monitor** не должно быть кода 126; у **com.atra.recovery-listener** — не 2.

---

## 5. Ошибка launchd exit 126 и как обойти

**Что такое 126:** В launchd код выхода **126** означает «Command invoked cannot execute». В логах при этом часто видно **«Operation not permitted»** при доступе к скрипту или к текущему каталогу — это ограничение доступа к папкам (в т.ч. в **Documents**) для процесса, запущенного launchd в пользовательском домене.

**Реальная причина:** запуск в **user-домене** без прав на каталог проекта (например `~/Documents/atra-web-ide`). Поэтому скрипт «не может быть выполнен» в смысле доступа к файлу/каталогу.

**Что сделано для обхода:**
1. **Launcher в Application Support:** создан скрипт `~/Library/Application Support/Atra/launch_mlx.sh`. Эта папка доступна `launchd` без дополнительных разрешений.
2. **Загрузка в GUI-домен** — в `setup_mlx_autostart.sh` используется **`launchctl bootstrap gui/$(id -u) plist`** вместо `launchctl load`. В GUI-домене процесс имеет тот же контекст доступа, что и сессия пользователя.
3. **start_mlx_server.sh** — явный PATH и выбор `python3` (на случай минимального окружения); вызов через `$PYTHON3 -m uvicorn`.
4. **WorkingDirectory=/tmp** — исключает ошибку доступа к родительским директориям при инициализации.

**После правок:** пересоздать и загрузить LaunchAgent (из **Терминала**, чтобы gui-домен был доступен):
```bash
bash scripts/setup_mlx_autostart.sh
launchctl kickstart -k gui/$(id -u)/com.atra.mlx-api-server
```
Проверка: `launchctl list gui/$(id -u) | grep mlx`, `curl -s http://localhost:11435/health`.

**Если 126 или «Operation not permitted» остаётся:**
- Убедиться, что скрипт запускался из **Терминала** (не из фонового процесса без доступа к GUI).
- **Системные настройки → Конфиденциальность и безопасность → Полный доступ к диску** — добавить **Терминал** (или iTerm), затем перезапустить Терминал и снова выполнить `setup_mlx_autostart.sh` и `launchctl bootstrap gui/$(id -u) ...`.
- Либо перенести репозиторий в каталог вне Documents (например `~/Projects/atra-web-ide`) и заново настроить plist.
- Временный вариант: запускать MLX вручную после входа: `bash scripts/start_mlx_api_server.sh` или добавить этот вызов в **Объекты входа** (Общие → Объекты входа).

---

## 5.1. Виктория сама поднимает MLX (без ваших действий)

**Recovery Listener** (порт 9099) при настройке через `bash scripts/setup_system_auto_recovery.sh` регистрируется в launchd и **запускается при загрузке Mac**. Оркестратор (Victoria в Docker) при обнаружении падения MLX шлёт **POST на host:9099/recover** → listener запускает `system_auto_recovery.sh` → поднимается MLX. **Запускать что-то вручную не нужно** — Виктория сама инициирует восстановление.

Если после перезагрузки listener не поднялся (проверка: `curl -s http://localhost:9099/recover` — должен ответить 200 или 405), один раз выполните из Терминала: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.atra.recovery-listener.plist` или запустите `python3 scripts/host_recovery_listener.py` в фоне. Ручной запуск MLX нужен только если и listener, и launchd MLX недоступны — см. §5 выше.

---

## 6. При следующих падениях MLX

- Смотреть **причину** в логах: `tail -100 ~/Library/Logs/atra/mlx_api_server.log` (Metal, OOM, address in use).
- Проверить **ответственных:** `launchctl list | grep mlx` — оба job должны быть без 126; иначе перезапустить настройку (п. 4).
- Если монитор и автозапуск в порядке, но MLX снова падает — держать **MLX_MAX_CACHED_MODELS=1**, **MLX_MAX_CONCURRENT=1** (уже в скриптах); при повторных Metal-крашах см. docs/MLX_PYTHON_CRASH_CAUSE.md и VERIFICATION_CHECKLIST_OPTIMIZATIONS.
