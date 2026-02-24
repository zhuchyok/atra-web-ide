# Автоматическая синхронизация .cursor/rules/

Система автоматического обновления правил Cursor при изменениях в команде.

## 🎯 Что синхронизируется

При любых изменениях в `configs/experts/employees.json`:

- ➕ **Найм** — создается новый файл
- 🔄 **Изменение** — обновляется существующий файл
- ➖ **Увольнение** — удаляется файл
- 🔀 **Объединение** — обновляются связанные файлы

## 🚀 Варианты использования

### 1. Ручной запуск

```bash
# Синхронизация по требованию
python scripts/sync_cursor_rules.py
```

### 2. Git Hook (автоматически при commit)

При изменении `employees.json` автоматически:

1. Запускается `sync_cursor_rules.py`
2. Обновляются файлы в `.cursor/rules/`
3. Изменения добавляются в коммит

```bash
# Hook уже установлен в .git/hooks/pre-commit
# Активируется автоматически
```

### 3. Database Trigger (real-time)

При изменениях в таблице `experts`:

1. Триггер логирует изменение в `experts_changelog`
2. Worker `cursor_rules_autosync.py` обнаруживает изменение
3. Автоматически запускается синхронизация

```bash
# Запуск worker (в фоне)
python knowledge_os/app/cursor_rules_autosync.py

# Или через systemd/supervisor
```

### 4. Добавить в docker-compose.yml

```yaml
cursor-rules-sync:
  build: .
  command: python knowledge_os/app/cursor_rules_autosync.py
  environment:
    - DATABASE_URL=${DATABASE_URL}
    - AUTO_COMMIT_CURSOR_RULES=false # true для auto-commit
  volumes:
    - ./.cursor:/app/.cursor
  restart: unless-stopped
```

## 📊 Мониторинг изменений

### Посмотреть недавние изменения

```sql
-- Последние изменения экспертов
SELECT * FROM expert_changes_summary;

-- Детали за последнюю неделю
SELECT
    event_type,
    expert_name,
    expert_role,
    changed_at,
    sync_status
FROM experts_changelog
WHERE changed_at >= NOW() - INTERVAL '7 days'
ORDER BY changed_at DESC;
```

### Проверить pending синхронизации

```sql
SELECT * FROM get_pending_expert_changes();
```

## 🔧 Конфигурация

### Переменные окружения

```bash
# .env
DATABASE_URL=postgresql://...
AUTO_COMMIT_CURSOR_RULES=false  # Автоматический git commit
```

### Настройки worker

```python
# knowledge_os/app/cursor_rules_autosync.py
CHECK_INTERVAL = 30  # секунд между проверками
```

## 📝 Шаблоны ролей

Скрипт использует умные шаблоны для разных ролей:

- Backend Developer
- Frontend Developer
- DevOps Engineer
- ML Engineer
- QA Engineer
- Data Analyst
- Product Manager
- UI/UX Designer
- И другие...

Для неизвестных ролей используется универсальный шаблон.

## 🎨 Формат файлов

Каждый файл содержит:

- YAML frontmatter (description, priority)
- Emoji индикатор роли
- Обязанности
- Технический стек
- Процессы работы
- Взаимодействие
- Примеры промптов
- Критерии качества
- Timestamp автогенерации

## 🔄 Жизненный цикл

```
employees.json изменен
         ↓
    Git Hook / DB Trigger
         ↓
  sync_cursor_rules.py
         ↓
    .cursor/rules/*.md
         ↓
    (опционально) Git Commit
```

## ⚡ Производительность

- Генерация 85 файлов: ~1-2 секунды
- Проверка изменений: ~100ms
- Worker overhead: минимальный (30s sleep)

## 🎯 Use Cases

### Найм нового сотрудника

```bash
# 1. Добавить в employees.json
# 2. Sync автоматически создаст файл при commit/worker cycle
# 3. Файл готов для копирования в другие проекты
```

### Изменение роли

```bash
# 1. Обновить роль в employees.json
# 2. Файл автоматически обновится
# 3. Новый шаблон применится если роль изменилась
```

### Увольнение

```bash
# 1. Удалить из employees.json
# 2. Файл автоматически удалится из .cursor/rules/
```

## 🚨 Troubleshooting

### Worker не запускается

```bash
# Проверить подключение к БД
python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('$DATABASE_URL'))"

# Проверить миграции
psql $DATABASE_URL -f knowledge_os/db/migrations/create_experts_changelog.sql
```

### Файлы не обновляются

```bash
# Проверить права
ls -la .cursor/rules/

# Проверить pending changes
python -c "
import asyncio, asyncpg, os
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    changes = await conn.fetch('SELECT * FROM get_pending_expert_changes()')
    print(f'Pending: {len(changes)}')
asyncio.run(check())
"
```

## 📚 Связанные файлы

- `scripts/sync_cursor_rules.py` — основной скрипт синхронизации
- `.git/hooks/pre-commit` — git hook
- `knowledge_os/db/migrations/create_experts_changelog.sql` — DB trigger
- `knowledge_os/app/cursor_rules_autosync.py` — background worker
- `configs/experts/employees.json` — источник данных
