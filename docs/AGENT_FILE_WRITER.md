# SafeFileWriter — безопасная запись файлов агентом

## Описание

`SafeFileWriter` используется ReActAgent при `create_file` и `write_file`. Обеспечивает:
- **Бэкап** перед перезаписью (в `.agent_backups/`)
- **Проверку путей** — запись только внутри workspace
- **Блокировку** системных путей (`/etc/`, `/root/`, `/var/`, `/bin/`, …)

## Конфигурация

```bash
# .env или docker-compose
WORKSPACE_ROOT=/app          # Корень workspace (в Docker — /app)
AGENT_BACKUP_ENABLED=true    # Включить бэкапы (по умолчанию true)
AGENT_APPROVAL_REQUIRED=false # true = отказ в записи в package.json, .env, Dockerfile
```

## Approval (Фаза 2)

При `AGENT_APPROVAL_REQUIRED=true` запись в критичные файлы блокируется:
package.json, .env, Dockerfile, docker-compose*.yml, nginx*.conf, config/, requirements.txt, pyproject.toml.

## Terminal + Victoria (Фаза 4)

**Web IDE** (встроенный терминал): `v "задача"` — запрос к Victoria Agent.  
Примеры: `v "список файлов"`, `v создай test.py`

**Системный терминал**: `bash scripts/chat_victoria.sh` — интерактивный чат с Victoria (локально или `VICTORIA_REMOTE_URL`).

## Файлы

- `knowledge_os/app/file_writer.py` — SafeFileWriter
- Интеграция: `knowledge_os/app/react_agent.py` (create_file, write_file)

## Формат бэкапа

`{filename}.{YYYYMMDD_HHMMSS}.{hash8}.bak` в `.agent_backups/`

## Очистка старых бэкапов (опционально)

```bash
# crontab: удалять бэкапы старше 7 дней
0 2 * * * find /app/.agent_backups -name "*.bak" -mtime +7 -delete
```
