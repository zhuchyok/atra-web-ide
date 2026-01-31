# Отчёт о миграции корпорации на Mac Studio

## Текущий статус

### Загружено (Server 1 — 185.177.216.15)
| Файл | Размер | Статус |
|------|--------|--------|
| knowledge_os.sql | 16 МБ | OK |
| s1_logic.tar.gz | 777 МБ | OK |
| atra.sql | — | не создан на S1 |
| redis.rdb | — | не скопирован |

### Server 2 (46.149.66.170)
| Файл | Размер | Статус |
|------|--------|--------|
| knowledge_os.sql | 71 МБ | OK |
| s2_brain.tar.gz | 42 МБ | OK |
При необходимости повторной загрузки только S2: `python3 scripts/migration/fetch_s2_only.py` (таймаут 30 мин, лог: `~/migration/fetch_s2.log`).

### Следующие шаги

1. **Проверка**  
   `bash scripts/migration/check_migration_status.sh`

2. **Загрузка S2** (если server2 пуст):  
   `python3 scripts/migration/fetch_s2_only.py`  
   Лог: `tail -f ~/migration/fetch_s2.log`. Тар ~30 мин.

3. **Запуск Docker → агенты (рекомендуется)**  
   - **Сначала запустите Docker Desktop.**  
   - В корне репо:
     ```bash
     bash scripts/migration/up_agents_after_docker.sh
     ```
   Скрипт ждёт Docker до 60 с, поднимает db/api/worker, собирает и запускает Victoria и Veronica, запускает проверку. MLX/Ollama — на `localhost:11434`.  
   Если Docker уже запущен: `SKIP_DOCKER_WAIT=1 bash scripts/migration/up_agents_after_docker.sh` — без ожидания.

4. **Восстановление (если ещё не делали)**  
   - Docker запущен, стек поднят:  
     `docker-compose -f knowledge_os/docker-compose.yml up -d db api worker`  
   - Выполнить:  
     `python3 scripts/migration/restore_only.py`  
   - Если скрипт «висит» на Docker:  
     `RESTORE_SKIP_DOCKER=1 python3 scripts/migration/restore_only.py`  
     затем импорт вручную (п. 5).

5. **Ручной импорт БД**:
   ```bash
   docker exec -i knowledge_os_db psql -U admin -d knowledge_os < ~/migration/server1/knowledge_os.sql
   ```

6. **Проверка Victoria и Veronica**:
   ```bash
   bash scripts/migration/verify_agents.sh
   ```
   См. также `docs/VICTORIA_FIX.md` (исправления агентов).

## Скрипты

- `scripts/migration/up_agents_after_docker.sh` — **старт после Docker**: db/api/worker + сборка и запуск Victoria/Veronica + verify
- `scripts/migration/corporation_full_migration.py` — полная миграция (бэкап + scp + restore)
- `scripts/migration/corporation_full_migration.py --fetch-only` — только загрузка
- `scripts/migration/fetch_s2_only.py` — повторная загрузка только S2 (таймаут 30 мин)
- `scripts/migration/restore_only.py` — только восстановление БД и распаковка
- `scripts/migration/run_migration_background.sh` — запуск в фоне
- `scripts/migration/check_migration_status.sh` — проверка статуса
- `scripts/migration/verify_agents.sh` — проверка Victoria и Veronica (8010/8011)
