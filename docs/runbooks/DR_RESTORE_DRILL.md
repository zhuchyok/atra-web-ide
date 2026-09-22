# Runbook: DR — восстановление knowledge_postgres из дампа

**Проверено drill'ом 2026-09-22:** восстановление 758MB custom-дампа в scratch-БД занимает **~12 минут** (pg_restore --jobs=4). Счётчики таблиц сходятся с live (расхождение = дневной churn с момента дампа).

## Пошагово

```bash
# 1. Свежий дамп
LATEST=$(ls -t ~/atra_backups/knowledge_postgres/*.dump | head -1)

# 2. Scratch-БД (НЕ трогаем knowledge_os!)
docker exec knowledge_postgres psql -U admin -d postgres \
  -c "CREATE DATABASE dr_drill_scratch OWNER admin;"

# 3. Дамп в контейнер + восстановление
docker cp "$LATEST" knowledge_postgres:/tmp/dr.dump
time docker exec knowledge_postgres pg_restore -U admin -d dr_drill_scratch \
  --no-owner --jobs=4 /tmp/dr.dump
docker exec knowledge_postgres rm /tmp/dr.dump

# 4. Верификация (счётчики должны совпасть с live в пределах churn)
docker exec knowledge_postgres psql -U admin -d dr_drill_scratch -tAc \
  "SELECT 'experts', COUNT(*) FROM experts UNION ALL SELECT 'tasks', COUNT(*) FROM tasks;"

# 5. Уборка
docker exec knowledge_postgres psql -U admin -d postgres -c "DROP DATABASE dr_drill_scratch;"
```

## Полное восстановление вместо scratch

1. Остановить пишущие сервисы: `docker stop knowledge_os_orchestrator knowledge_os_worker knowledge_nightly performance-watchdog`.
2. Пересоздать БД: `DROP DATABASE knowledge_os; CREATE DATABASE knowledge_os OWNER admin;`
3. `pg_restore -U admin -d knowledge_os --no-owner --jobs=4 /tmp/dr.dump`
4. Поднять сервисы: `docker start ...`.

## Конвейер бэкапов (v143)

| Время | Что | Где |
|---|---|---|
| 03:00 | `pg_dump` → `~/atra_backups/knowledge_postgres/*.dump` | cron (`~/bin/atra_backup_knowledge_postgres.sh`) |
| 03:10 | rclone copy → gdrive, ретеншн remote 7 дней | cron (`~/bin/atra_sync_backups_to_gdrive.sh`, `KEEP_DAYS_REMOTE=7`) |
| 04:00 | health-check: дамп <25ч, >1MB, gdrive доступен; при проблеме — ntfy high | cron (`scripts/check_backups_health.sh`) |

## Уроки 2026-09-22 (обязательно к учёту)

1. **gdrive-синк молча падал 7 недель** (`storageQuotaExceeded` 403) — скрипт печатал «done» независимо от результата. Health-check теперь ловит отсутствие свежего remote-дампа.
2. **КвотаDrive съедается корзиной**: удалённые дампы лежат в trash и продолжают занимать квоту. Лечение: `rclone cleanup gdrive:`. Ретеншн 30д → 7д (5.3GB против 22GB).
3. Скрипт health-check из старого проекта (`~/Documents/dev/atra`) был синтаксически повреждён — источник истины теперь `scripts/check_backups_health.sh` этого репо.
