#!/bin/bash
# Тест Git Hook для автосинхронизации .cursor/rules/
# Этот тест симулирует изменение employees.json

set -e

echo "🧪 ТЕСТ GIT HOOK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Сохраняем текущее состояние
ORIGINAL_TIMESTAMP=$(grep "Автоматически сгенерировано" .cursor/rules/01_viktoriya.md | head -1)
echo "📝 Текущий timestamp: $ORIGINAL_TIMESTAMP"

# 2. Симулируем изменение employees.json (touch)
echo ""
echo "🔄 Симулируем изменение employees.json..."
touch configs/experts/employees.json

# 3. Добавляем в staging
echo "📦 Добавляем в git staging..."
git add configs/experts/employees.json

# 4. Проверяем, что pre-commit hook существует
if [ ! -f ".git/hooks/pre-commit" ]; then
    echo "❌ ОШИБКА: pre-commit hook не найден!"
    exit 1
fi

if [ ! -x ".git/hooks/pre-commit" ]; then
    echo "❌ ОШИБКА: pre-commit hook не исполняемый!"
    exit 1
fi

echo "✅ Hook найден и исполняемый"

# 5. Запускаем hook вручную
echo ""
echo "🚀 Запускаем pre-commit hook..."
.git/hooks/pre-commit

# 6. Проверяем, что файлы обновились
echo ""
echo "🔍 Проверяем результаты..."
NEW_TIMESTAMP=$(grep "Автоматически сгенерировано" .cursor/rules/01_viktoriya.md | head -1)
echo "📝 Новый timestamp: $NEW_TIMESTAMP"

# 7. Сброс staging
echo ""
echo "🔄 Сброс git staging..."
git reset HEAD configs/experts/employees.json 2>/dev/null || true

# 8. Результаты
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$ORIGINAL_TIMESTAMP" != "$NEW_TIMESTAMP" ]; then
    echo "✅ ТЕСТ ПРОЙДЕН: Файлы обновлены!"
else
    echo "⚠️  ПРЕДУПРЕЖДЕНИЕ: Файлы не изменились (возможно, нет изменений в employees.json)"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
