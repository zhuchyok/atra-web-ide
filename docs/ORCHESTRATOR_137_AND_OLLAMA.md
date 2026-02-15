# knowledge_os_orchestrator: Restarting (137) и Ollama All connection attempts failed

**Назначение:** зафиксировать причины и меры по устранению падений оркестратора (exit 137) и ошибок подключения к Ollama.

---

## 1. Почему код выхода 137 (Restarting)

**Подтверждено по `docker events`:** контейнер завершается событием **`container oom`** (out of memory), затем **`container die`** с **exitCode=137**.

- **137 = 128 + 9** — процесс получил **SIGKILL** (9). В контексте Docker это типично при **OOM Kill**: менеджер ресурсов (Docker/ядро) завершает процесс при превышении лимита памяти.
- У контейнера **нет явного лимита** (`HostConfig.Memory == 0`), значит срабатывает либо лимит Docker Desktop по умолчанию, либо общая нехватка памяти на хосте.
- В логах видно, что контейнер падает через **1–3 секунды** после старта (`execDuration=1` или `3`). То есть пик потребления памяти приходится на **старт**: загрузка модулей и первый цикл (в т.ч. `update_all_agents_knowledge` с множеством вызовов эмбеддингов).

**Итог:** 137 у оркестратора — это **OOM**: контейнеру не хватает памяти при старте/первом цикле.

---

## 2. Почему «Ollama: All connection attempts failed»

**Проверка на хосте:**

- `curl http://localhost:11434/api/tags` — не отвечает (таймаут/ошибка).
- `pgrep -fl ollama` — есть только процесс **ollama-mcp** (npm/node), то есть **MCP-сервер для Ollama**, а не демон **Ollama API** (порт 11434).

**Вывод:** на хосте **не запущен демон Ollama** (`ollama serve`). Сервис на порту 11434 отсутствует, поэтому из контейнера запросы к `http://host.docker.internal:11434` падают с «All connection attempts failed».

**Почему MLX доступен, а Ollama нет:** MLX API Server запущен на хосте на порту 11435 и отвечает (в т.ч. 404 на `/v1/models`). Сеть из контейнера к хосту работает (`host.docker.internal`), проблема именно в том, что на 11434 ничего не слушает.

---

## 2.1. Почему падает Ollama (все известные в проекте причины)

Проверено по VERIFICATION_CHECKLIST_OPTIMIZATIONS §3 и MASTER_REFERENCE. Возможные причины:

| Причина | Симптом / как проверить | Что делать |
|--------|--------------------------|------------|
| **Демон не запущен** | На порту 11434 никто не слушает; в процессах только `ollama-mcp` (MCP), не `ollama serve`. | Запустить: `ollama serve` от пользователя с моделями (предпочтительно; иначе `brew services start ollama` может запустить от другого пользователя → models: []). |
| **Запущен от другого пользователя** | Ollama отвечает, но `models: []` или 404 `model not found`. Модели лежат в `~/.ollama/` у текущего пользователя. | `brew services stop ollama`; запускать `ollama serve` из терминала **под пользователем, у которого есть модели** (проверка: `ps aux \| grep ollama` — USER = владелец `~/.ollama/models/`). |
| **Sleep/wake Mac** | После сна ноутбука/станции Ollama перестаёт отвечать или отдаёт 500. Metal-контекст может инвалидироваться. | **system_auto_recovery.sh** уже проверяет Ollama (блок 4.5) и перезапускает при отсутствии ответа. Запускать recovery по расписанию (launchd каждые 300 с) или вручную после wake. |
| **Конкуренция за Metal с MLX** | Оба (Ollama 11434 и MLX 11435) используют Metal на одном Mac. В логах: «Reentrancy avoided», «compiler is no longer active», MTLCompilerService. | Снизить параллелизм: меньше **SMART_WORKER_MAX_CONCURRENT**; или временно отключить MLX и гнать только через Ollama. |
| **Metal OOM / failed to allocate context** | Ollama 500: «llama runner process has terminated», «failed to allocate context». Нехватка GPU-памяти при тяжёлых моделях или смене модели под нагрузкой. | Перезапуск: `pkill -f ollama`; через 2–3 с `ollama serve`. Уменьшить нагрузку (меньше одновременных запросов). Логи: `~/.ollama/logs/server.log`. |

**Итог:** если «Ollama падает» — сначала проверить, запущен ли вообще демон и от того ли пользователя; затем смотреть логи и при повторениях после sleep/wake или под нагрузкой — перезапуск через system_auto_recovery или вручную и снижение конкуренции с MLX.

---

## 3. Связь двух причин

- При **недоступном Ollama** оркестратор всё равно каждый цикл вызывает **update_all_agents_knowledge** и множество **get_embedding** (Ollama). Каждый вызов падает по таймауту (например 10 с в semantic_cache), при этом цепочка импортов и работа с памятью остаются тяжёлыми.
- Импорт **app.main** для get_embedding тянет за собой MCP, redis, пул БД и др. — это увеличивает потребление памяти при старте.
- В итоге: **тяжёлый старт + много неуспешных запросов к Ollama** способствуют быстрому выходу за доступную память и OOM (137).

---

## 4. Почему оркестратор за этим не следил и как стало (живой организм)

**Раньше:** оркестратор не проверял доступность Ollama/MLX перед циклом и не инициировал восстановление — это не входило в его изначальный контур (только задачи, знания, фазы). Восстановление хоста (Ollama, MLX) выполнялось только при загрузке системы (launchd) или вручную.

**Сейчас (живой организм — сам всё решает и восстанавливает):**

1. **В начале каждого цикла** оркестратор проверяет здоровье Ollama и MLX (`check_llm_services_health()`). Если Ollama недоступен — **не вызывает** `update_all_agents_knowledge()` (избегаем OOM и лавины таймаутов).
2. **При недоступности** любого из сервисов оркестратор отправляет **POST на RECOVERY_WEBHOOK_URL** (тело: `{"ollama": bool, "mlx": bool, "ts": ...}`). На хосте должен быть запущен **scripts/host_recovery_listener.py** (порт 9099 по умолчанию), который по этому запросу запускает **system_auto_recovery.sh** — перезапуск Ollama, MLX, контейнеров и т.д.
3. **В режиме continuous** дополнительно запускается **фоновый монитор** (`_health_monitor_loop`): раз в N минут (ORCHESTRATOR_HEALTH_MONITOR_INTERVAL, по умолчанию 300) проверяет Ollama/MLX и при сбое снова шлёт запрос на webhook.
4. **Периодическое самовосстановление на хосте** уже настроено в **setup_system_auto_recovery.sh**: launchd запускает **system_auto_recovery.sh** при загрузке и **каждые 300 с** (StartInterval). Таким образом, даже без webhook хост периодически сам проверяет и поднимает Ollama/MLX и контейнеры.

**Итог:** оркестратор следит за Ollama/MLX, при сбое не нагружает себя эмбеддингами и запрашивает восстановление; хост либо реагирует на webhook, либо восстанавливается по расписанию.

---

## 5. Что сделано в коде и конфигурации

1. **docker-compose (knowledge_os_orchestrator):** добавлены **OLLAMA_BASE_URL**, **MLX_API_URL**, **MAC_LLM_URL**, **extra_hosts**; **RECOVERY_WEBHOOK_URL** (по умолчанию `http://host.docker.internal:9099/recover`), **ORCHESTRATOR_HEALTH_MONITOR_INTERVAL** (300).
2. **enhanced_orchestrator.py:** проверка `check_llm_services_health()` в начале цикла; при недоступном Ollama — пропуск `update_all_agents_knowledge()` и вызов `trigger_recovery_webhook()`; в continuous — фоновый монитор с тем же webhook.
3. **corporation_knowledge_system:** сначала импорт **semantic_cache.get_embedding** (меньше памяти при старте оркестратора).
4. **scripts/host_recovery_listener.py:** HTTP-сервер на хосте (порт 9099); по POST /recover запускает **system_auto_recovery.sh**.
5. **Скрипты восстановления:** в `system_auto_recovery.sh` и `check_and_start_containers.sh` — **up -d** и явный подъём **knowledge_nightly** и **knowledge_os_orchestrator** (CHANGES §0.4k).

---

## 6. Что сделать на хосте

1. **Запустить слушатель восстановления** (чтобы оркестратор мог запросить перезапуск Ollama/MLX по webhook):
   ```bash
   python3 scripts/host_recovery_listener.py
   ```
   Или в фоне: `nohup python3 scripts/host_recovery_listener.py >> /tmp/host_recovery_listener.log 2>&1 &`  
   По умолчанию слушает порт 9099; в docker-compose оркестратору уже задан `RECOVERY_WEBHOOK_URL=http://host.docker.internal:9099/recover`.

2. **Запустить Ollama API** (порт 11434):
   ```bash
   ollama serve
   ```
   или, если установлен через Homebrew:
   ```bash
   brew services start ollama
   ```
   После этого запросы из контейнера к `http://host.docker.internal:11434` начнут доходить; эмбеддинги и обнаружение моделей Ollama заработают.

3. **При повторяющемся 137 (OOM):**
   - Увеличить память для контейнеров в Docker Desktop (Settings → Resources → Memory).
   - Либо задать лимит для оркестратора в `docker-compose` и при необходимости увеличить его, например:
     ```yaml
     knowledge_os_orchestrator:
       ...
       deploy:
         resources:
           limits:
             memory: 2G
     ```
   - Убедиться, что на хосте не исчерпана память другими процессами (браузер, другие контейнеры).

---

## 7. Проверка

- Оркестратор не уходит в Restarting (137):
  ```bash
  docker ps --format '{{.Names}}\t{{.Status}}' | grep knowledge_os_orchestrator
  ```
- Ollama на хосте отвечает:
  ```bash
  curl -s http://localhost:11434/api/tags
  ```
- События OOM по контейнеру (если снова падает):
  ```bash
  docker events --filter container=knowledge_os_orchestrator
  ```

Документ можно обновлять при появлении новых причин или изменений в конфигурации (CHANGES_FROM_OTHER_CHATS, MASTER_REFERENCE).
