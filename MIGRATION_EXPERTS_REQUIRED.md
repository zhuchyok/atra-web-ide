# ⚠️ ТРЕБУЕТСЯ МИГРАЦИЯ ЭКСПЕРТОВ

## Проблема

В системе используется fallback структура с **только 7-22 экспертами**, когда должно быть **58 экспертов**.

**Текущий статус:**
- ❌ В БД: **0 экспертов** (данные не мигрированы)
- ❌ Fallback структура: **22 эксперта** (расширена, но неполная)
- ✅ Должно быть: **58 экспертов** из сервера 46.149.66.170

## Решение

### Вариант 1: Импорт из дампа (рекомендуется)

```bash
# 1. Убедитесь, что БД запущена
docker-compose -f knowledge_os/docker-compose.yml up -d db

# 2. Импортируйте дамп
docker exec -i knowledge_os_db psql -U admin -d knowledge_os < ~/migration/server2/knowledge_os_dump.sql

# 3. Проверьте количество
docker exec -it knowledge_os_db psql -U admin -d knowledge_os -c "SELECT COUNT(*) FROM experts;"
# Должно быть: 58
```

### Вариант 2: Миграция через скрипт

```bash
# Запустите полную миграцию
python3 scripts/migration/corporation_full_migration.py
```

### Вариант 3: Импорт из CSV

```bash
# Если есть файл experts.csv
python3 knowledge_os/scripts/import_experts_from_csv.py ~/migration/server2/experts.csv
```

## Проверка

После миграции проверьте:

```bash
# Количество экспертов
python3 -c "
import asyncio
import sys
sys.path.insert(0, 'knowledge_os/app')
from expert_validator import get_db_expert_count
print(f'Экспертов в БД: {asyncio.run(get_db_expert_count())}')
"

# Структура организации
python3 -c "
import asyncio
import sys
sys.path.insert(0, 'knowledge_os/app')
from organizational_structure import OrganizationalStructure
structure = OrganizationalStructure()
result = asyncio.run(structure.get_full_structure())
print(f'Отделов: {result[\"total_departments\"]}')
print(f'Сотрудников: {result[\"total_employees\"]}')
"
```

## Ожидаемый результат

После миграции:
- ✅ **58 экспертов** в БД
- ✅ **27 отделов** (из PLAN.md)
- ✅ Полная структура организации
- ✅ Fallback структура не используется (БД доступна)

## Дата создания

2026-01-27
