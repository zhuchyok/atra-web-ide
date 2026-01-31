# 🚀 Деплой оптимизаций БД на сервер

## Дата: 2025-01-09

## Статус: ✅ Скрипт деплоя готов

---

## 📋 Файлы для деплоя

### Модули оптимизаций (8):
- `src/database/archive_manager.py`
- `src/database/index_auditor.py`
- `src/database/query_optimizer.py`
- `src/database/table_maintenance.py`
- `src/database/materialized_views.py`
- `src/database/column_order_optimizer.py`
- `src/database/temp_tables_optimizer.py`
- `src/database/optimization_manager.py`

### Вспомогательные модули (2):
- `src/database/fetch_optimizer.py`
- `src/database/query_profiler.py`

### Обновленные файлы (1):
- `src/database/db.py` (с интеграцией всех оптимизаций)

### Скрипты (4):
- `scripts/archive_old_data.py`
- `scripts/optimize_database.py`
- `scripts/apply_all_optimizations.py`
- `scripts/monitor_database_performance.py`

---

## 🚀 Автоматический деплой

### Вариант 1: Использование скрипта (рекомендуется)

```bash
# Запустить деплой
./scripts/deploy_optimizations_to_server.sh
```

Скрипт автоматически:
1. Проверит наличие всех файлов
2. Загрузит их на сервер
3. Установит права на выполнение

---

## 🔧 Ручной деплой

### Вариант 2: Через git (если используется)

```bash
# На сервере
ssh root@185.177.216.15
cd /root/atra
git pull origin worker  # или main, в зависимости от ветки
```

### Вариант 3: Через scp (по одному файлу)

```bash
# Загрузить модули
scp src/database/archive_manager.py root@185.177.216.15:/root/atra/src/database/
scp src/database/index_auditor.py root@185.177.216.15:/root/atra/src/database/
# ... и так далее для всех файлов

# Загрузить скрипты
scp scripts/apply_all_optimizations.py root@185.177.216.15:/root/atra/scripts/
# ... и так далее
```

### Вариант 4: Через rsync (для всех файлов сразу)

```bash
# Загрузить все модули оптимизаций
rsync -avz --progress \
    src/database/archive_manager.py \
    src/database/index_auditor.py \
    src/database/query_optimizer.py \
    src/database/table_maintenance.py \
    src/database/materialized_views.py \
    src/database/column_order_optimizer.py \
    src/database/temp_tables_optimizer.py \
    src/database/optimization_manager.py \
    src/database/fetch_optimizer.py \
    src/database/query_profiler.py \
    src/database/db.py \
    root@185.177.216.15:/root/atra/src/database/

# Загрузить все скрипты
rsync -avz --progress \
    scripts/archive_old_data.py \
    scripts/optimize_database.py \
    scripts/apply_all_optimizations.py \
    scripts/monitor_database_performance.py \
    root@185.177.216.15:/root/atra/scripts/
```

---

## ✅ Проверка после деплоя

### На сервере выполните:

```bash
# 1. Проверить наличие файлов
ls -la src/database/*.py | grep -E "(archive_manager|index_auditor|optimization_manager)"
ls -la scripts/*.py | grep -E "(apply_all_optimizations|monitor_database)"

# 2. Применить оптимизации
python3 scripts/apply_all_optimizations.py

# 3. Проверить статус
python3 scripts/apply_all_optimizations.py --report

# 4. Мониторинг производительности
python3 scripts/monitor_database_performance.py
```

---

## 🔄 Интеграция с существующей системой

### Автоматическое применение оптимизаций

Оптимизации применяются автоматически при инициализации БД (если `AUTO_APPLY_OPTIMIZATIONS=true`).

Для отключения автоматического применения:
```bash
export AUTO_APPLY_OPTIMIZATIONS=false
```

### Регулярное обслуживание

Рекомендуется настроить cron для регулярного обслуживания:

```bash
# Добавить в crontab на сервере
crontab -e

# Еженедельно (каждый понедельник в 3:00)
0 3 * * 1 cd /root/atra && python3 scripts/archive_old_data.py
0 4 * * 1 cd /root/atra && python3 scripts/optimize_database.py --all

# Ежемесячно (1-го числа в 2:00)
0 2 1 * * cd /root/atra && python3 scripts/optimize_database.py --vacuum
```

---

## 📊 Мониторинг после деплоя

### Проверка работы оптимизаций:

```bash
# На сервере
cd /root/atra

# Полный отчет
python3 scripts/monitor_database_performance.py

# Сохранить отчет в файл
python3 scripts/monitor_database_performance.py --output /tmp/db_performance_report.txt

# Непрерывный мониторинг
python3 scripts/monitor_database_performance.py --watch
```

---

## ⚠️ Важные замечания

1. **Резервное копирование**: Перед применением оптимизаций рекомендуется создать резервную копию БД:
   ```bash
   cp trading.db trading.db.backup_$(date +%Y%m%d_%H%M%S)
   ```

2. **Тестирование**: Рекомендуется сначала протестировать на тестовой БД или в dev окружении.

3. **Мониторинг**: После деплоя следите за логами и метриками производительности.

---

## 🎯 Результат

После успешного деплоя:
- ✅ Все 13 модулей оптимизации доступны на сервере
- ✅ Автоматическое применение оптимизаций при инициализации БД
- ✅ Скрипты для ручного управления и мониторинга
- ✅ Регулярное обслуживание через cron (опционально)

---

## 📚 Дополнительная документация

- `docs/DATABASE_OPTIMIZATION_GUIDE.md` - полное руководство по использованию
- `docs/FINAL_ALL_OPTIMIZATIONS_REPORT.md` - отчет о реализованных оптимизациях
- `docs/COMPLETE_OPTIMIZATION_SYSTEM.md` - описание полной системы

