#!/bin/bash
# Скрипт для проверки прогресса команды

echo "🔍 Проверка прогресса команды..."
echo ""

# Проверка логирования фильтров
echo "1. Проверка логирования фильтров..."
python3 -c "
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
since = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
cursor.execute('SELECT COUNT(*) FROM filter_checks WHERE created_at >= ?', (since,))
count = cursor.fetchone()[0]
print(f'   Записей в filter_checks за последний час: {count}')
if count > 0:
    print('   ✅ Логирование работает!')
else:
    print('   ❌ Логирование не работает')
conn.close()
" 2>/dev/null || echo "   ❌ Ошибка при проверке"

echo ""

# Проверка quality_score
echo "2. Проверка quality_score..."
python3 -c "
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
since = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
cursor.execute('''
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN quality_score > 0 THEN 1 END) as with_score,
        AVG(quality_score) as avg_score
    FROM signals_log
    WHERE created_at >= ? AND quality_score IS NOT NULL
''', (since,))
row = cursor.fetchone()
total, with_score, avg_score = row
if total > 0:
    score_rate = (with_score / total * 100) if total > 0 else 0
    print(f'   Всего сигналов: {total}')
    print(f'   С quality_score > 0: {with_score} ({score_rate:.1f}%)')
    print(f'   Средний score: {avg_score or 0:.2f}')
    if score_rate > 50 and avg_score and avg_score > 0:
        print('   ✅ quality_score работает!')
    else:
        print('   ❌ quality_score не работает')
else:
    print('   ⚠️ Нет данных')
conn.close()
" 2>/dev/null || echo "   ❌ Ошибка при проверке"

echo ""

# Проверка файлов
echo "3. Проверка файлов..."
if [ -f "src/utils/filter_logger.py" ]; then
    echo "   ✅ filter_logger.py существует"
else
    echo "   ❌ filter_logger.py не найден"
fi

if [ -f "tests/test_filter_logging.py" ] || [ -f "scripts/test_filter_logging.py" ]; then
    echo "   ✅ Тесты логирования найдены"
else
    echo "   ❌ Тесты логирования не найдены"
fi

echo ""
echo "✅ Проверка завершена"
