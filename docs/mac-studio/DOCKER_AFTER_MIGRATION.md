# Docker после миграции — чек-лист

## Выполнено

1. **Импорт БД** — дамп `~/migration/server1/knowledge_os.sql` импортирован в `knowledge_os_db` (часть ошибок «already exists» нормальна).
2. **restore_only** — при импорте приоритет у контейнеров `*_db` (избегаем импорта в API).
3. **Compose агентов** — `context: ..`, volumes `../data`, `../logs`, `../src`. Victoria → `victoria_server`, Veronica → `bridge.server`, порты 8010/8011, `OLLAMA_BASE_URL`.
4. **.dockerignore** — добавлен для сборки агентов (исключены data, logs, archive, ai_learning_data, *.jsonl, **/venv и т.п.).

## Важно: место на диске

Сборка агентов падала с **«No space left on device»** / **input-output error**: диск был заполнен на **~98%** (свободно ~346 МБ). Перед пересборкой нужно освободить место:

```bash
# Очистка Docker
docker system prune -af
docker builder prune -af

# Удаление старых образов/контейнеров
docker image prune -a
```

Также удалите или перенесите тяжёлые каталоги (например `data/`, `system_cache/`, `knowledge_os/ai_learning_data/`, логи, бэкапы).

## Дальнейшие шаги

1. **Запустить Docker Desktop** (скрипт ждёт до ~30 с).
2. Освободить место при нехватке (см. выше).
3. Одной командой — сборка, подъём стека, запуск агентов, проверка:
   ```bash
   cd /path/to/atra
   bash scripts/migration/up_agents_after_docker.sh
   ```
   Либо вручную:
   ```bash
   docker-compose -f knowledge_os/docker-compose.yml up -d knowledge-os-db knowledge-os-api knowledge-os-worker
   docker-compose -f knowledge_os/docker-compose.yml build victoria-agent veronica-agent
   docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent veronica-agent
   bash scripts/migration/verify_agents.sh
   ```

Убедитесь, что MLX API (или Ollama) слушает на `localhost:11434` — агенты ходят туда через `host.docker.internal:11434`.
