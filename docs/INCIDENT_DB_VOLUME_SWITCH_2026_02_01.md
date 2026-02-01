# Инцидент: переключение volume БД (1 февраля 2026)

**Документ для экспертов:** анализ причин, восстановление, рекомендации.

---

## Сводка

| Параметр | До инцидента | Во время инцидента | После восстановления |
|----------|--------------|--------------------|----------------------|
| Экспертов | 85 | 1 | 85 |
| Узлов знаний | 26 337 | 27 | 26 337 |
| Volume | atra_knowledge_postgres_data | knowledge_os_postgres_data | atra_knowledge_postgres_data |

**Симптомы:** На дашборде и в API — «1 эксперт», «27 узлов», ошибки «column» на всех страницах.

---

## Причина

PostgreSQL (`knowledge_postgres`) использовал **другой Docker volume**:

- **Ожидаемый:** `atra_knowledge_postgres_data` (общая БД atra + atra-web-ide, 85 экспертов, 26k+ узлов)
- **Фактический:** `knowledge_os_postgres_data` (почти пустая БД: 1 эксперт, 27 узлов)

### Почему так произошло

1. **Разные проекты docker-compose:**
   - `atra` → volume `atra_knowledge_postgres_data` (project: atra)
   - `knowledge_os` → volume `knowledge_os_postgres_data` (project: knowledge_os)

2. **Разные точки запуска:**
   - Запуск из `atra` с `docker-compose up` → контейнер `knowledge_postgres` может использовать volume из atra.
   - Запуск из `knowledge_os` или `atra-web-ide` → создаётся/подключается `knowledge_os_postgres_data`.

3. **Возможный сценарий:**
   - `docker-compose down -v` (с удалением volumes) в проекте atra или knowledge_os.
   - Перезапуск из другого каталога/проекта.
   - Инициализация PostgreSQL с пустой директорией данных → создаётся новая БД.

4. **Два volume на диске:**
   - `atra_knowledge_postgres_data` (создан 2026-01-19) — с полными данными.
   - `knowledge_os_postgres_data` (создан 2026-01-21) — с пустой/минимальной БД.

---

## Восстановление (выполнено)

1. **Определено:** данные в volume `atra_knowledge_postgres_data`.

2. **Изменение `knowledge_os/docker-compose.yml`:**
   ```yaml
   volumes:
     postgres_data:
       external: true
       name: atra_knowledge_postgres_data
   ```

3. **Действия:**
   - Остановка контейнера `knowledge_postgres`
   - Удаление контейнера
   - Запуск с новым volume
   - Проверка: 85 экспертов, 26 337 узлов

4. **Перезапуск:** corporation-dashboard, victoria-agent, veronica-agent, knowledge_os_worker.

---

## Рекомендации экспертов

### Краткосрочные

1. **Единый volume:**
   - Использовать один volume для atra и atra-web-ide.
   - Текущее состояние: `postgres_data` → `atra_knowledge_postgres_data`.

2. **Проверка после перезапуска:**
   ```bash
   docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "SELECT COUNT(*) FROM experts; SELECT COUNT(*) FROM knowledge_nodes;"
   ```
   Ожидаемо: 85, 26337.

3. **Дашборд:** после восстановления БД ошибки «column» должны исчезнуть (схема соответствует данным).

### Среднесрочные

4. **Резервное копирование:**
   - `./scripts/backup_knowledge_os.sh` — работает на Mac и Linux, с Docker
   - Хранение: `~/Documents/dev/atra/backups/` или `./backups/`
   - Cron: `0 2 * * *` (ежедневно в 2:00)

5. **Документация:**
   - `DOCKER_START_INSTRUCTIONS.md` — обновлён (volume, safe_docker_down)
   - `./scripts/safe_docker_down.sh` — защита от случайного `down -v` (требует подтверждения)

6. **Скрипт проверки:**
   - `./scripts/verify_db_health.sh` — проверка experts >= 80, knowledge_nodes >= 10000
   - Интегрирован в `start_full_corporation.sh`
   - API: `GET /api/system-metrics` → `db.healthy`, `db.experts`, `db.knowledge_nodes`

### Долгосрочные

7. **Единый docker-compose:**
   - Рассмотреть единый compose для atra и atra-web-ide с общим сервисом PostgreSQL.

8. **Мониторинг:**
   - `GET /api/system-metrics` → `db.experts`, `db.knowledge_nodes`, `db.healthy`
   - Cron бэкап: `infrastructure/cron/backup_knowledge_os.cron`

---

## Контакты для вопросов

- **DevOps/инфраструктура:** проверка volume и compose.
- **Backend:** проверка DATABASE_URL и подключения к БД.
- **Дашборд:** проверка запросов после восстановления схемы.

---

*Документ создан 2026-02-01. Обновить при изменении архитектуры volumes.*
