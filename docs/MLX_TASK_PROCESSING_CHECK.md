# Почему не видно работу MLX при обработке задач

Кратко: **MLX API Server** — это **отдельный процесс** на порту **11435**. Если он не запущен, все задачи обрабатываются только через **Ollama** (11434). В Activity Monitor MLX отображается как **Python** (uvicorn), а не как «MLX» или «ollama».

**Важно:** В PLAN.md и статус-доках написано «MLX API Server работает на порту 11435» — это **целевая конфигурация** (как должно быть), а не гарантия, что процесс сейчас запущен на вашей машине. Фактически запущен ли MLX, проверяется командой `bash scripts/check_local_models.sh` или `curl -s http://localhost:11435/health`.

---

## 1. Как устроена маршрутизация

- **LocalAIRouter** при каждом запросе вызывает `check_health()`: опрашивает узлы **MLX (11435)** и **Ollama (11434)** по `/health` или `/api/tags`.
- В список **healthy_nodes** попадают только узлы, ответившие 200. Результат кэшируется на 2 минуты.
- Если MLX API Server **не запущен** — узел 11435 не отвечает, в `healthy_nodes` только Ollama → **все задачи идут в Ollama**.
- В Activity Monitor при этом видно только процессы **ollama**; отдельного процесса с именем «MLX» нет — MLX API Server это **Python (uvicorn)**.

---

## 2. Проверка: работает ли MLX

На **хосте** (Mac Studio):

```bash
# Быстрая проверка порта 11435
curl -s -o /dev/null -w "%{http_code}" http://localhost:11435/health
# Ожидается: 200

# Список моделей MLX (если сервер поднят)
curl -s http://localhost:11435/api/tags
```

Если порт не слушается или соединение отклоняется — MLX не используется, воркер и Victoria обрабатывают задачи только через Ollama.

**Из контейнера** (Docker):

```bash
curl -s http://host.docker.internal:11435/health
```

---

## 3. Запуск MLX API Server

На хосте (один раз или после перезагрузки):

```bash
# Из корня репозитория
bash scripts/start_mlx_api_server.sh
```

Скрипт запускает `knowledge_os/app/mlx_api_server.py` (uvicorn) на порту **11435** (или `MLX_API_PORT` из env). В мониторе процессов этот процесс будет отображаться как **Python**, не как «MLX».

Автозапуск после перезагрузки (опционально):

- `scripts/system_auto_recovery.sh` (launchd, каждые 5 мин) при необходимости поднимает MLX (вызов `start_mlx_api_server.sh`).
- Или настройте launchd/cron по образцу из `docs/mac-studio/SELF_RECOVERY_AFTER_REBOOT.md`.

---

## 4. Что смотреть в логах

Если MLX недоступен, **LocalAIRouter** раз в 5 минут пишет в лог:

```
⚠️ [ROUTER] MLX API Server (порт 11435) недоступен — все задачи обрабатываются через Ollama.
Запуск: scripts/start_mlx_api_server.sh; проверка: curl -s http://localhost:11435/health
```

Логи воркера (knowledge_os_worker) или Victoria — там же будет видно, что используется только Ollama.

---

## 5. Итог

| Вопрос | Ответ |
|--------|--------|
| Почему в Activity Monitor не видно «MLX»? | MLX API Server — это процесс **Python (uvicorn)** на порту 11435, в списке процессов он идёт как Python. |
| Почему задачи не идут в MLX? | Скорее всего не запущен MLX API Server: порт 11435 не отвечает, в healthy_nodes только Ollama. |
| Как проверить? | `curl -s http://localhost:11435/health` (на хосте) или `curl -s http://host.docker.internal:11435/health` из контейнера. |
| Как включить MLX? | Запустить на хосте: `bash scripts/start_mlx_api_server.sh`. |

---

## 7. Почему «В работе» больше 15 (например 28) при лимите 15

Если в дашборде «В работе» отображается **больше 15** задач при настройке **SMART_WORKER_MAX_CONCURRENT=15**, значит одновременно работают **несколько воркеров** (каждый держит до 15 задач). Например: 28 ≈ два контейнера (15+13).

Возможные контейнеры:
- **knowledge_os_worker** — из `knowledge_os/docker-compose.yml` (основной воркер).
- **knowledge_worker** — образ `atra-knowledge_worker` (старый); если запущен вместе с knowledge_os_worker, в сумме будет до 30 задач «в работе».

Проверка: `docker ps -a | grep worker` — смотреть, сколько контейнеров с воркером в статусе **Up**. Чтобы было не больше 15 «в работе», должен быть запущен только **один** воркер (рекомендуется **knowledge_os_worker**). В `knowledge_os/docker-compose.yml` задано `SMART_WORKER_MAX_CONCURRENT: "15"`.

---

## 6. Почему задачи не шли в MLX при работающем сервере (исправлено)

Воркер назначал задачам `preferred_source='mlx'` и передавал роутер с `_preferred_source` в `ai_core._current_router`, но **run_smart_agent_async** всегда создавал новый `LocalAIRouter()` и не использовал переданный роутер. В результате предпочтение MLX игнорировалось, все запросы шли по умолчанию (часто в Ollama). Исправление: в `run_smart_agent_async` сначала берётся `_current_router`, если он задан — используется он (с `_preferred_source`/`_preferred_model`), иначе создаётся новый роутер.

---

Связанные документы: [CURRENT_STATE_WORKER_AND_LLM.md](CURRENT_STATE_WORKER_AND_LLM.md), [MASTER_REFERENCE.md](MASTER_REFERENCE.md), [MLX_API_SERVER_TROUBLESHOOTING.md](MLX_API_SERVER_TROUBLESHOOTING.md).
