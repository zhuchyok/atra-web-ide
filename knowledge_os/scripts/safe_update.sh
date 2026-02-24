#!/bin/bash
# 🔒 БЕЗОПАСНОЕ ОБНОВЛЕНИЕ КОДА
# Использование: ./safe_update.sh

set -e  # Остановка при ошибке

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔒 БЕЗОПАСНОЕ ОБНОВЛЕНИЕ ATRA"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Проверка Git статуса
echo "📊 Проверяем текущие изменения..."
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  Обнаружены несохраненные изменения!"
    echo ""
    git status --short
    echo ""
    read -p "💾 Закоммитить изменения? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "💬 Введите сообщение коммита:"
        read commit_msg
        git add .
        git commit -m "$commit_msg"
        echo "✅ Изменения закоммичены"
    else
        echo "📦 Сохраняем изменения в stash..."
        git stash push -m "Auto stash: $(date +%Y-%m-%d_%H:%M:%S)"
        STASHED=true
        echo "✅ Изменения сохранены во временное хранилище"
    fi
else
    echo "✅ Рабочая директория чиста"
fi

echo ""

# 2. Создание backup ветки
BACKUP_BRANCH="backup-$(date +%Y%m%d-%H%M%S)"
echo "💾 Создаем backup ветку: $BACKUP_BRANCH"
git branch "$BACKUP_BRANCH"
echo "✅ Backup создан"
echo ""

# 3. Тянем изменения
echo "⬇️  Тянем обновления с GitHub..."
CURRENT_BRANCH=$(git branch --show-current)
if git pull origin "$CURRENT_BRANCH"; then
    echo "✅ Обновления загружены успешно"
else
    echo "❌ Ошибка при pull!"
    echo "🔧 Возможно есть конфликты. Варианты:"
    echo "   1. Решить вручную: git status -> исправить -> git add . -> git commit"
    echo "   2. Использовать наши изменения: git checkout --ours <файл>"
    echo "   3. Использовать remote изменения: git checkout --theirs <файл>"
    echo "   4. Откатиться к backup: git reset --hard $BACKUP_BRANCH"
    exit 1
fi

echo ""

# 4. Восстановление из stash если нужно
if [ "$STASHED" = true ]; then
    echo "📦 Возвращаем сохраненные изменения..."
    if git stash pop; then
        echo "✅ Изменения восстановлены"
    else
        echo "⚠️  Конфликты при восстановлении stash!"
        echo "🔧 Решите конфликты вручную и выполните:"
        echo "   git add . && git commit -m 'Merged stash'"
        exit 1
    fi
fi

echo ""

# 5. Проверка критичных файлов
echo "🔍 Проверяем критичные исправления..."
if [ -f "verify_all_fixes.py" ]; then
    python3 verify_all_fixes.py
    if [ $? -eq 0 ]; then
        echo "✅ Все исправления на месте!"
    else
        echo "⚠️  Некоторые исправления отсутствуют!"
        echo "🔧 Проверьте файлы вручную или откатитесь:"
        echo "   git reset --hard $BACKUP_BRANCH"
        exit 1
    fi
else
    echo "⚠️  verify_all_fixes.py не найден, пропускаем проверку"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 ОБНОВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Backup ветка: $BACKUP_BRANCH"
echo "   (Можно удалить через неделю: git branch -D $BACKUP_BRANCH)"
echo ""
echo "🔄 Не забудьте перезапустить бота:"
echo "   pkill -9 -f main.py && nohup python3 main.py > main.log 2>&1 &"
echo ""
