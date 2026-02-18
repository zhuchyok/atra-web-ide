#!/bin/bash

# ATRA Global Sync Script - Единый источник истины для Библии и .cursorrules
# Автор: Виктория (Team Lead Atra Core)

MAIN_PROJECT_PATH="/Users/bikos/Documents/atra-web-ide"
BIBLE_REL_PATH="docs/MASTER_REFERENCE.md"
CURSORRULES_REL_PATH=".cursorrules"

# Список проектов для синхронизации
PROJECTS=(
    "/Users/bikos/Documents/dev/setki-21"
    "/Users/bikos/Documents/dev/atra"
)

echo "🚀 Запуск глобальной синхронизации ATRA Core..."

# Функция создания симлинка
sync_file() {
    local src="$1"
    local dest_dir="$2"
    local filename="$3"
    local dest_path="${dest_dir}/${filename}"

    if [ ! -f "$src" ]; then
        echo "❌ Ошибка: Исходный файл $src не найден!"
        return 1
    fi

    # Создаем папку если её нет
    mkdir -p "$dest_dir"

    # Если файл существует и это не симлинк, делаем бэкап
    if [ -f "$dest_path" ] && [ ! -L "$dest_path" ]; then
        echo "📦 Бэкап существующего файла: ${dest_path}.bak"
        mv "$dest_path" "${dest_path}.bak"
    fi

    # Создаем симлинк (удаляем старый если был)
    rm -f "$dest_path"
    ln -s "$src" "$dest_path"
    echo "✅ Симлинк создан: $dest_path -> $src"
}

# 1. Синхронизация Библии
for project in "${PROJECTS[@]}"; do
    echo "📂 Обработка проекта: $project"
    
    # Библия
    sync_file "${MAIN_PROJECT_PATH}/${BIBLE_REL_PATH}" "${project}/docs" "MASTER_REFERENCE.md"
    
    # .cursorrules
    sync_file "${MAIN_PROJECT_PATH}/${CURSORRULES_REL_PATH}" "${project}" ".cursorrules"
done

echo "✨ Синхронизация завершена. Теперь все проекты используют единую Библию и правила!"
