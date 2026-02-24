# Итоги аудита Эры Мудрости (Mac Studio, 02.2026)

**Дата:** 2026-02-24. **Контекст:** Singularity 20.0, Mirror Wisdom (MLX + Ollama), оптимизация под 128 GB.

## 1. Состояние инфраструктуры

- **Docker:** Контейнеры (Victoria, Veronica, PostgreSQL, Redis, оркестратор, воркеры) с политикой `restart: always` / `unless-stopped`. Сеть `atra-network` создаётся при первом запуске.
- **PostgreSQL (knowledge_os):** Доступна, данные актуальны. Таблицы `strategy_sessions`, `board_decisions`, `knowledge_nodes`, `tasks` в работе.
- **Ресурсы:** Ограничение нагрузки на Victoria (семафор), OLLAMA_KEEP_ALIVE=-1 для модели victoria-wisdom-30b, OLLAMA_NUM_PARALLEL=2, OLLAMA_MAX_LOADED_MODELS=2. Иерархия моделей: основная — victoria-wisdom-30b; быстрые — tinyllama; тяжёлые (qwq, deepseek-r1:32b) — только fallback.

## 2. Выявленные и устранённые проблемы

- **Падение MLX (мозг):** В логах `~/Library/Logs/atra/mlx_api_server.log` — ошибка Metal `addCompletedHandler: failed assertion`. Введён дефибриллятор: `scripts/host_recovery_listener.py` (порт 9099), RECOVERY_WEBHOOK_URL в оркестраторе. Рекомендация: MLX_MAX_CACHED_MODELS=1, при сбое — `./scripts/start_mlx_api_server.sh`.
- **Тишина Совета Директоров:** 170 висящих сессий (status=active) блокировали очередь. Выполнено закрытие (status=cancelled), запущен run_board_meeting(); новые директивы снова пишутся в board_decisions и на дашборд.
- **Автозапуск после перезагрузки:** Проверка — `./scripts/verify_full_recovery_readiness.sh`. MLX и Telegram Bot — через LaunchAgents. **Recovery listener (дефибриллятор):** после входа в систему выполнить `nohup python3 scripts/host_recovery_listener.py &` (скрипт в корне проекта). Так оркестратор сможет снова вызывать автовосстановление при падении MLX/Ollama. См. MASTER_REFERENCE § Wisdom Era Status.

## 3. Рекомендации

- Держать слушатель восстановления запущенным или добавить его в автозагрузку с корректными разрешениями.
- После длительного простоя проверять MLX: `curl -s http://localhost:11435/api/tags`.
- Новый чат Cursor: использовать `@docs/SESSION_HANDOFF_2026_02_24.md` для переноса контекста.
