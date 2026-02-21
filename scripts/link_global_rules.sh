#!/bin/bash

# Скрипт для автоматической линковки глобальных правил и Библии в новые проекты
# Использование: bash scripts/link_global_rules.sh /path/to/new/project

TARGET_PROJECT=$1

if [ -z "$TARGET_PROJECT" ]; then
    echo "❌ Ошибка: Укажите путь к проекту."
    echo "Пример: bash scripts/link_global_rules.sh ../../dev/setki-21"
    exit 1
fi

# Путь к текущему корню (atra-web-ide)
BIBLE_ROOT=$(pwd)

echo "🔗 Линковка глобальных правил из $BIBLE_ROOT в $TARGET_PROJECT..."

# 1. Создаем папки если их нет
mkdir -p "$TARGET_PROJECT/.cursor/rules"
mkdir -p "$TARGET_PROJECT/docs"

# 2. Линкуем .cursorrules
if [ -L "$TARGET_PROJECT/.cursorrules" ]; then rm "$TARGET_PROJECT/.cursorrules"; fi
ln -s "$BIBLE_ROOT/.cursorrules" "$TARGET_PROJECT/.cursorrules"
echo "✅ .cursorrules -> Linked"

# 3. Линкуем MASTER_REFERENCE.md
if [ -L "$TARGET_PROJECT/docs/MASTER_REFERENCE.md" ]; then rm "$TARGET_PROJECT/docs/MASTER_REFERENCE.md"; fi
ln -s "$BIBLE_ROOT/docs/MASTER_REFERENCE.md" "$TARGET_PROJECT/docs/MASTER_REFERENCE.md"
echo "✅ docs/MASTER_REFERENCE.md -> Linked"

# 4. Линкуем папку с экспертами (опционально, но полезно для Cursor)
# Мы линкуем содержимое, чтобы не затирать локальные правила если они будут
for rule in "$BIBLE_ROOT/.cursor/rules/"*.md; do
    rule_name=$(basename "$rule")
    if [ ! -e "$TARGET_PROJECT/.cursor/rules/$rule_name" ]; then
        ln -s "$rule" "$TARGET_PROJECT/.cursor/rules/$rule_name"
    fi
done
echo "✅ .cursor/rules/* -> Linked (only missing ones)"

echo "🚀 Готово! Теперь проект $TARGET_PROJECT использует единую Библию и правила корпорации."
