#!/bin/bash
# Комплексная очистка проекта

echo "🧹 НАЧАЛО ОЧИСТКИ ПРОЕКТА..."

# 1. Удалить логи
echo "1. Удаление логов..."
rm -f *.log bot*.log system*.log 2>/dev/null
echo "   ✅ Логи удалены"

# 2. Удалить backup файлы
echo "2. Удаление backup файлов..."
rm -f *.bak *.bak2 *.bak3 2>/dev/null
echo "   ✅ Backup файлы удалены"

# 3. Архивировать JSON отчеты
echo "3. Архивирование JSON отчетов..."
mkdir -p archive/reports
mv system_integration_report_*.json archive/reports/ 2>/dev/null
mv current_strategy_backtest_*.json archive/reports/ 2>/dev/null
mv *_backtest_*.json archive/reports/ 2>/dev/null
echo "   ✅ JSON отчеты архивированы"

# 4. Удалить старые архивы
echo "4. Удаление старых архивов..."
rm -rf archive/old_tests/ 2>/dev/null
rm -rf archive/old_scripts/ 2>/dev/null
echo "   ✅ Старые архивы удалены"

# 5. Переместить документацию
echo "5. Перемещение документации..."
mkdir -p docs/reports
# Сохраняем README если есть
if [ -f README.md ]; then
    cp README.md README.md.backup
fi
mv *.md docs/reports/ 2>/dev/null
# Возвращаем README
if [ -f README.md.backup ]; then
    mv README.md.backup README.md
fi
echo "   ✅ Документация перемещена"

# 6. Переместить shell скрипты
echo "6. Перемещение shell скриптов..."
mkdir -p scripts/shell
mv *.sh scripts/shell/ 2>/dev/null
echo "   ✅ Shell скрипты перемещены"

# 7. Удалить дубликаты
echo "7. Удаление дубликатов..."
rm -rf backup_20251019_203843/ 2>/dev/null
rm -rf backups/ 2>/dev/null
echo "   ✅ Дубликаты удалены"

# 8. Удалить пустые директории
echo "8. Удаление пустых директорий..."
rmdir metrics locales cache logs configs 2>/dev/null || true
rmdir ai_learning_data ai_tp_data ai_reports 2>/dev/null || true
rmdir htmlcov infrastructure system_cache test_reports 2>/dev/null || true
echo "   ✅ Пустые директории удалены"

echo ""
echo "✅ ОЧИСТКА ЗАВЕРШЕНА!"
echo ""
echo "📊 Результат:"
echo "   - Файлов в корне: $(find . -maxdepth 1 -type f | wc -l | tr -d ' ')"
