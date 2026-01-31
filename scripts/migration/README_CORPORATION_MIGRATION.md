# Миграция корпорации на Mac Studio

Полный перенос Knowledge OS, агентов и знаний с серверов **185.177.216.15** и **46.149.66.170** на Mac Studio. Без торгового бота.

## Требования

- **sshpass:** `brew install hudochenkov/sshpass/sshpass`
- **Docker** с запущенным стеком Knowledge OS (для восстановления БД)
- Репозиторий `atra` на Mac Studio (например, `~/Documents/dev/atra`)

## Запуск на Mac Studio

**Полная миграция (бэкап + scp + restore + распаковка):**
```bash
cd ~/Documents/dev/atra
python3 scripts/migration/corporation_full_migration.py
```

**Только загрузка данных** (без восстановления БД и распаковки; восстановить потом через `restore_only`):
```bash
python3 scripts/migration/corporation_full_migration.py --fetch-only
```

**Только восстановление** (данные уже в `~/migration`):
```bash
python3 scripts/migration/restore_only.py
```
Если скрипт «зависает» при проверке Docker: `RESTORE_SKIP_DOCKER=1 python3 scripts/migration/restore_only.py` — тогда только распаковка и вывод команды для ручного импорта.

**Повторная загрузка только S2** (если таймаут на `s2_brain`):
```bash
python3 scripts/migration/fetch_s2_only.py
```

**Фоновый запуск** (первый прогон может занять 20–30+ минут из‑за дампов и архивов):
```bash
bash scripts/migration/run_migration_background.sh
tail -f ~/migration/migration.log
```

Скрипт полной миграции:

1. Создаёт `~/migration/server1` и `~/migration/server2`
2. Подключается к обоим серверам, делает дампы БД и архивы (knowledge_os, atra, Redis, файлы знаний)
3. Скачивает всё в `~/migration/`
4. Восстанавливает БД в контейнер PostgreSQL (knowledge_os_db / knowledge_postgres)
5. Распаковывает архив «мозга» (research, knowledge_os) в корень репозитория

## После миграции

- Проверка: `docker-compose -f knowledge_os/docker-compose.yml ps`
- Логи: `docker-compose -f knowledge_os/docker-compose.yml logs -f`
- MLX API Server: `curl http://localhost:11434/`

## Проверка статуса

```bash
bash scripts/migration/check_migration_status.sh
```

## Агенты Victoria / Veronica — одна точка входа

```bash
bash scripts/migration/continue_agents.sh
```

Скрипт проверяет `/health` и `/status` на 8010/8011. Если всё ОК — ничего не делать. Если нет — выведет команды для ручного запуска (compose up и т.д.). Подробно: **`docs/MIGRATION_PROBLEM_AGENTS.md`**.

## Проверка агентов вручную

```bash
bash scripts/migration/verify_agents.sh
```

Проверяются `http://localhost:8010` (Victoria) и `http://localhost:8011` (Veronica). Свои URL: `./verify_agents.sh http://host:8010 http://host:8011`.

## Ручной импорт БД (если скрипт не нашёл контейнер)

```bash
docker exec -i knowledge_postgres psql -U admin -d knowledge_os < ~/migration/server2/knowledge_os.sql
# или (если дамп только с S1)
docker exec -i knowledge_os_db psql -U admin -d knowledge_os < ~/migration/server1/knowledge_os.sql
```

## Если Docker не запущен

1. Запустите Docker Desktop.
2. Поднимите стек: `docker-compose -f knowledge_os/docker-compose.yml up -d` (из корня репозитория).
3. Дождитесь `healthy` у `knowledge_os_db`, затем: `python3 scripts/migration/restore_only.py`.
