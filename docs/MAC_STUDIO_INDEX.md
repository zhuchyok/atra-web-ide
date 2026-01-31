# Mac Studio — индекс настроек, серверов и знаний

Всё, что связано с Mac Studio, серверами, Victoria, Veronica, MCP и экспертами — в этом проекте.

## Серверы и порты

| Сервис | Порт | URL | Описание |
|--------|------|-----|----------|
| Victoria Agent | 8010 | http://192.168.1.64:8010 | Team Lead, /run, /health, /status |
| Veronica Agent | 8011 | http://192.168.1.64:8011 | Web Researcher |
| MCP (Victoria) | 8012 | http://localhost:8012/sse | Cursor MCP, victoria_run, victoria_status |
| Ollama/MLX | 11434 | http://192.168.1.64:11434 | Модели на Mac Studio |
| Knowledge OS API | 8000 | http://localhost:8000 | REST + MCP /sse |
| PostgreSQL | 5432 | localhost:5432 | knowledge_os |

## Документация

### Mac Studio
- `docs/mac-studio/MAC_STUDIO_*.md` — модели, миграция, setup
- `docs/mac-studio/MLX_*.md`, `OLLAMA_NEEDED_ANALYSIS.md`
- `docs/mac-studio/SSH_ENABLE_MAC_STUDIO.md` — включение SSH на Mac Studio
- `docs/mac-studio/REMOTE_ACCESS_SETUP.md` — удалённый доступ (Tailscale, Cloudflare, SSH туннели)

### Victoria / MCP
- `docs/mac-studio/VICTORIA_AUTOSTART.md`
- `docs/mac-studio/VICTORIA_AUTO_SETUP_COMPLETE.md`
- `docs/mac-studio/VICTORIA_CURSOR_SETUP.md`

### Миграция / Docker
- `docs/mac-studio/MIGRATION_*.md`
- `docs/mac-studio/DOCKER_AFTER_MIGRATION.md`

### Эксперты
- `configs/experts/team.md` — команда 40+ экспертов, алиасы
- В atra: `knowledge_os/app/expert_aliases.py`, `expert_validator.py`

## Скрипты

### Victoria / MCP
- `scripts/victoria/quick_victoria_autostart.sh` — автозапуск MCP
- `scripts/victoria/do_all_victoria_setup.sh` — полная настройка
- `scripts/victoria/setup_cursor_mcp_global.py` — MCP в Cursor settings
- `scripts/victoria/victoria_auto_connect.sh` — автоподключение при открытии проекта

### Миграция
- `scripts/migration/continue_agents.sh` — проверка и запуск агентов
- `scripts/migration/verify_agents.sh` — health Victoria/Veronica
- `scripts/migration/check_migration_status.sh`
- `scripts/migration/restore_only.py`, `corporation_full_migration.py`

### Запуск
- `scripts/start_mac_studio_full.sh`
- `docker-compose -f knowledge_os/docker-compose.yml up -d`

### Mac Studio / SSH
- `scripts/mac-studio/enable_ssh.sh` — включение SSH на Mac Studio

## Конфиги

- `configs/agents/veronica.yaml`
- `configs/experts/team.md`
- `.env`, `.env.mac-studio` — окружение

## Код агентов

- `src/agents/bridge/victoria_server.py` — Victoria HTTP API
- `src/agents/bridge/victoria_mcp_server.py` — MCP для Cursor (Victoria URL: 192.168.1.64:8010)
- `src/agents/bridge/server.py` — Veronica
- `src/agents/core/` — base_agent, executor, memory

## Docker

- `knowledge_os/docker-compose.yml` — db, victoria-agent, veronica-agent
- `infrastructure/docker/agents/Dockerfile`

## Cursor

- MCP: VictoriaATRA → `http://localhost:8012/sse`
- При открытии проекта: `victoria_auto_connect.sh` (через .vscode/tasks)

## Источник

Скопировано из `atra` (GITHUB/atra/atra). Полные знания по экспертам, Knowledge OS и миграции — в репозитории atra.
