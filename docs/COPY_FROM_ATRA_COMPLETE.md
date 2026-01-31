# Копирование из atra — завершено

Скопировано всё, что связано с **Mac Studio, серверами, Victoria, Veronica, MCP, миграцией и экспертами** из `GITHUB/atra/atra` в `atra-web-ide`.

## Что скопировано

### Документация
- `docs/mac-studio/` — VICTORIA_*, MIGRATION_*, MAC_STUDIO_*, MLX_*, DOCKER_AFTER_MIGRATION, MIGRATION_PROBLEM_AGENTS
- `docs/MAC_STUDIO_INDEX.md` — индекс серверов, скриптов, конфигов

### Скрипты
- `scripts/victoria/` — quick_victoria_autostart, do_all_victoria_setup, setup_cursor_mcp_global, victoria_auto_connect, init_victoria_for_new_project, setup_victoria_cursor, auto_setup_victoria_global, final_victoria_setup, setup_victoria_autostart
- `scripts/migration/` — continue_agents, verify_agents, check_migration_status, restore_only, corporation_full_migration, fetch_s2_only, up_agents_after_docker, do_all_and_verify, docker_debug, README_CORPORATION_MIGRATION, migrate_to_mac_studio

### Агенты и инфраструктура
- `src/agents/bridge/` — victoria_mcp_server, victoria_server, server (Veronica)
- `src/agents/core/` — base_agent, executor, memory
- `src/agents/tools/` — system_tools, web_tools и др.
- `knowledge_os/docker-compose.yml` — db, victoria-agent, veronica-agent
- `infrastructure/docker/agents/Dockerfile`

### Конфиги и эксперты
- `configs/experts/team.md` — команда 40+, алиасы
- `configs/agents/veronica.yaml` (если был в atra)

### Правила и окружение
- `.cursorrules` — обновлён: Mac Studio индекс, эксперты, структура, запуск
- `.env.mac-studio` — дополнен VICTORIA_URL, VERONICA_URL, MAC_STUDIO_IP
- `requirements.txt` — fastapi, uvicorn, httpx, fastmcp для агентов

## Где что искать

| Тема | Путь |
|------|------|
| Индекс Mac Studio | `docs/MAC_STUDIO_INDEX.md` |
| Victoria / MCP | `docs/mac-studio/VICTORIA_*` |
| Миграция / Docker | `docs/mac-studio/MIGRATION_*`, `DOCKER_AFTER_MIGRATION` |
| Скрипты Victoria | `scripts/victoria/` |
| Скрипты миграции | `scripts/migration/` |
| Эксперты | `configs/experts/team.md` |
| Агенты | `src/agents/bridge/`, `src/agents/core/` |
| Docker | `knowledge_os/docker-compose.yml` |

## Запуск

```bash
# Victoria / MCP автозапуск
bash scripts/victoria/quick_victoria_autostart.sh

# Агенты (Docker)
docker-compose -f knowledge_os/docker-compose.yml up -d

# Проверка
bash scripts/migration/continue_agents.sh
bash scripts/migration/verify_agents.sh
```

---

*Скопировано из atra. Полные знания по Knowledge OS, экспертам и миграции — в репо atra.*
