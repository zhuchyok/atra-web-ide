# Улучшения надёжности (1 февраля 2026)

Внедрены рекомендации экспертов после инцидента переключения volume БД. Соответствие мировым практикам Docker persistence.

---

## Выполненные изменения

### 1. Проверка здоровья БД
- **`scripts/verify_db_health.sh`** — проверка experts >= 80, knowledge_nodes >= 10000
- Интегрирован в `start_full_corporation.sh`
- Опция `--fail-on-warning` для CI/автоматизации

### 2. Защита от потери данных
- **`scripts/safe_docker_down.sh`** — обёртка над `docker-compose down`
- `-v` только с `--force` и явным подтверждением «DELETE VOLUMES»

### 3. Резервное копирование
- **`scripts/backup_knowledge_os_full.sh`** — полный бэкап: локально + Google Drive
- **`scripts/backup_knowledge_os.sh`** — только локально
- См. `docs/BACKUP_SETUP.md`

### 4. Проверка volume при старте
- `start_full_corporation.sh` проверяет наличие `atra_knowledge_postgres_data`
- Ошибка с подсказкой, если volume не найден

### 5. API для мониторинга
- **`GET /api/system-metrics`** — добавлено поле `db`:
  - `experts`, `knowledge_nodes`, `healthy`
  - Пороги: experts >= 80, knowledge_nodes >= 10000
- **`tasks_24h`** — метрики выполнения задач (completed_by_ai, completed_by_rule, deferred_to_human, failed)
- **Telegram-алерты** — при высоком deferred/failed ratio (>30% / >20%) отправка уведомления (cooldown 1 ч)

#### Telegram-алерты (переменные окружения)
Использует те же переменные, что и Victoria Telegram Bot — достаточно `.env` в корне:
| Переменная | Описание |
|------------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен бота (или `TG_TOKEN`) |
| `TELEGRAM_CHAT_ID` | Chat ID для алертов (тот же чат, что у Victoria) |
| `TELEGRAM_USER_ID` | Fallback, если нет TELEGRAM_CHAT_ID (личный чат) |
| `TELEGRAM_ALERT_COOLDOWN_SEC` | Пауза между алертами (по умолчанию 3600) |

### 6. Документация
- `DOCKER_START_INSTRUCTIONS.md` — предупреждения о volume и `down -v`
- `docs/INCIDENT_DB_VOLUME_SWITCH_2026_02_01.md` — обновлён список выполненных рекомендаций
- `infrastructure/cron/backup_knowledge_os.cron` — шаблон для cron

---

## Мировые практики (Docker persistence)

- **Named volumes** — рекомендуемый способ (используем)
- **External volume** — для общей БД между проектами (atra + atra-web-ide)
- **Проверка volume** перед стартом — избегание пустой БД
- **Регулярный pg_dump** — восстановление после сбоев
- **Защита от down -v** — подтверждение при удалении данных

---

## Команды для проверки

```bash
# Проверка БД
./scripts/verify_db_health.sh

# Бэкап (полный: local + GDrive)
./scripts/backup_knowledge_os_full.sh

# Безопасная остановка (без -v)
./scripts/safe_docker_down.sh
```

---

*Документ создан 2026-02-01*
