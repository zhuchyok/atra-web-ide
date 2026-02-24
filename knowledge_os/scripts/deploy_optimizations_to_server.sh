#!/bin/bash
# Скрипт для деплоя всех оптимизаций БД на сервер

set -e

SERVER="root@185.177.216.15"
PASSWORD="u44Ww9NmtQj,XG"
REMOTE_DIR="/root/atra"

echo "=================================================================================="
echo "🚀 ДЕПЛОЙ ОПТИМИЗАЦИЙ БАЗЫ ДАННЫХ НА СЕРВЕР"
echo "=================================================================================="
echo ""

# Список файлов для деплоя
FILES=(
    # Модули оптимизаций
    "src/database/archive_manager.py"
    "src/database/index_auditor.py"
    "src/database/query_optimizer.py"
    "src/database/table_maintenance.py"
    "src/database/materialized_views.py"
    "src/database/column_order_optimizer.py"
    "src/database/temp_tables_optimizer.py"
    "src/database/optimization_manager.py"
    "src/database/fetch_optimizer.py"
    "src/database/query_profiler.py"

    # Обновленный db.py
    "src/database/db.py"

    # Скрипты
    "scripts/archive_old_data.py"
    "scripts/optimize_database.py"
    "scripts/apply_all_optimizations.py"
    "scripts/monitor_database_performance.py"
)

echo "📦 Подготовка файлов для деплоя..."
echo ""

# Проверяем наличие файлов
MISSING_FILES=()
for file in "${FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
        echo "⚠️  Файл не найден: $file"
    else
        echo "✅ $file"
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo ""
    echo "❌ Некоторые файлы отсутствуют. Продолжить? (y/n)"
    read -r response
    if [ "$response" != "y" ]; then
        echo "Деплой отменен."
        exit 1
    fi
fi

echo ""
echo "📤 Загрузка файлов на сервер..."

# Создаем директории на сервере
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER" \
    "mkdir -p $REMOTE_DIR/src/database $REMOTE_DIR/scripts"

# Загружаем файлы
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  📤 $file"
        sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no "$file" "$SERVER:$REMOTE_DIR/$file"
    fi
done

echo ""
echo "🔧 Установка прав на скрипты..."
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER" \
    "cd $REMOTE_DIR && chmod +x scripts/*.py"

echo ""
echo "✅ Деплой завершен!"
echo ""
echo "📋 Следующие шаги на сервере:"
echo "   1. Применить оптимизации: python3 scripts/apply_all_optimizations.py"
echo "   2. Проверить статус: python3 scripts/apply_all_optimizations.py --report"
echo "   3. Мониторинг: python3 scripts/monitor_database_performance.py"
echo ""
echo "=================================================================================="
