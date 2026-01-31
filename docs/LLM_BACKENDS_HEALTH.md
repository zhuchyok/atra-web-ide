# Доступность Ollama и MLX: проверка и автоподъём

## Режимы чата и используемые бэкенды

| Режим   | Вкладка | Кто отвечает | Fallback |
|--------|---------|----------------|----------|
| **Ask**   | Чат     | MLX → Ollama → Victoria | При недоступности MLX и Ollama — Victoria |
| **Agent** | Агент   | Victoria (/run)        | При ошибке Victoria — MLX → Ollama |
| **Plan**  | План    | Только Victoria (/plan) | Нет (только план, без выполнения) |

- **Ask** — быстрый ответ: сначала MLX, затем Ollama, при недоступности обоих — Victoria.
- **Agent** — полный агент: запрос в Victoria; при ошибке Victoria — MLX → Ollama.
- **Plan** — только план (без выполнения): всегда Victoria.plan(); MLX/Ollama не используются.

Цепочка для быстрого ответа и fallback: **MLX** (11435) → **Ollama** (11434) → **Victoria**.

## Проверка доступности в бэкенде

- **Старт**: при запуске бэкенда проверяются Victoria, Ollama и MLX; результат пишется в лог.
- **Периодическая проверка**: каждые `HEALTH_CHECK_INTERVAL` сек (по умолчанию 30) бэкенд проверяет Ollama и MLX и при недоступности пишет в лог:
  - `[Health] Ollama недоступна — запустите Ollama или проверьте OLLAMA_URL`
  - `[Health] MLX недоступен — запустите MLX API Server или проверьте MLX_API_URL`
- **HTTP**: `GET /health` возвращает статусы `victoria`, `ollama`, `mlx`.
- **Режимы**: `GET /api/chat/mode/health` — доступность бэкендов по режимам (ask / agent / plan). См. также `docs/CHAT_MODES_ARCHITECTURE_ANALYSIS.md`.

## Автоподъём при недоступности

Сам бэкенд Web IDE **не перезапускает** Ollama/MLX — только проверяет и логирует.

Подъём при недоступности делается:

1. **Knowledge OS (Victoria Enhanced)**  
   При вызове `solve()` в Victoria Enhanced вызывается `ensure_llm_backends_available()` (см. `knowledge_os/app/llm_backends_ensure.py`):  
   проверяются MLX и Ollama, при необходимости запускаются `ollama serve` и MLX через `mlx_server_supervisor`.

2. **Скрипты на хосте**  
   - `scripts/AUTO_START_MLX.sh` — запуск MLX  
   - `scripts/start_mlx_with_supervisor.py` — MLX под супервизором  
   - `knowledge_os/app/mlx_server_supervisor.py` — перезапуск MLX при падении  
   - Системный сервис/cron для `ollama serve` при необходимости

3. **Переменные окружения**  
   - `OLLAMA_URL` / `OLLAMA_BASE_URL` — URL Ollama (по умолчанию `http://localhost:11434`)  
   - `MLX_API_URL` — URL MLX API Server (по умолчанию `http://localhost:11435`)  
   **Docker:** если бэкенд в контейнере, а Ollama и MLX на хосте — задайте в `docker-compose` для backend:
   - `OLLAMA_URL=http://host.docker.internal:11434`
   - `MLX_API_URL=http://host.docker.internal:11435`  
   Иначе режимы **Ask** и fallback **Agent** не увидят MLX/Ollama.

## Итог

- В чате всегда используется цепочка **MLX → Ollama → Victoria**; не только MLX.
- Бэкенд постоянно проверяет Ollama и MLX и пишет в лог при недоступности.
- Автоподъём выполняют Knowledge OS (при работе с Victoria) и скрипты/supervisor на хосте.
