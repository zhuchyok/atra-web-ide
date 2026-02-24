#!/bin/bash

# Скрипт синхронизации универсальных правил во все проекты
# Использование: ./sync-cursor-rules.sh [base-directory]

set -e

BASE_DIR="${1:-$HOME}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIVERSAL_RULES_PATH="$HOME/.cursor/universal-rules.md"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔄 Синхронизация универсальных правил во все проекты...${NC}"
echo ""

# Проверяем наличие универсальных правил
if [ ! -f "$UNIVERSAL_RULES_PATH" ]; then
    echo -e "${RED}❌ Универсальные правила не найдены в $UNIVERSAL_RULES_PATH${NC}"
    echo -e "${YELLOW}💡 Создайте их: cp docs/examples/universal-cursor-rules.md ~/.cursor/universal-rules.md${NC}"
    exit 1
fi

# Получаем хеш текущих универсальных правил для отслеживания изменений
UNIVERSAL_RULES_HASH=$(md5sum "$UNIVERSAL_RULES_PATH" 2>/dev/null | cut -d' ' -f1 || md5 -q "$UNIVERSAL_RULES_PATH" 2>/dev/null || echo "unknown")
CACHE_FILE="$HOME/.cursor/sync-cache.json"

# Загружаем кэш последней синхронизации
if [ -f "$CACHE_FILE" ]; then
    LAST_HASH=$(cat "$CACHE_FILE" | grep -o '"last_hash":"[^"]*"' | cut -d'"' -f4 || echo "")
else
    LAST_HASH=""
fi

# Проверяем, изменились ли универсальные правила
if [ "$UNIVERSAL_RULES_HASH" = "$LAST_HASH" ] && [ -n "$LAST_HASH" ]; then
    echo -e "${GREEN}ℹ️  Универсальные правила не изменились с последней синхронизации${NC}"
    read -p "Принудительно обновить все проекты? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Отменено${NC}"
        exit 0
    fi
fi

# Счетчики
TOTAL_PROJECTS=0
SYNCED=0
SKIPPED=0
ERRORS=0

# Функция для проверки, является ли директория проектом
is_project() {
    local dir="$1"

    # Пропускаем скрытые директории и системные
    if [[ "$(basename "$dir")" =~ ^\. ]]; then
        return 1
    fi

    # Пропускаем node_modules, venv, .git и т.д.
    if [[ "$(basename "$dir")" =~ ^(node_modules|venv|\.git|\.venv|__pycache__|\.cache|target|dist|build)$ ]]; then
        return 1
    fi

    # Проверяем признаки проекта
    if [ -f "$dir/.git/config" ] || \
       [ -f "$dir/package.json" ] || \
       [ -f "$dir/requirements.txt" ] || \
       [ -f "$dir/pyproject.toml" ] || \
       [ -f "$dir/Cargo.toml" ] || \
       [ -f "$dir/go.mod" ] || \
       [ -f "$dir/pom.xml" ] || \
       [ -f "$dir/Makefile" ] || \
       [ -f "$dir/README.md" ]; then
        return 0
    fi

    return 1
}

# Функция для извлечения универсальных правил из файла
extract_universal_rules() {
    local file="$1"

    # Ищем начало универсальных правил
    awk '/## 🌍 УНИВЕРСАЛЬНЫЕ ПРАВИЛА/,/^---$/' "$file" 2>/dev/null || echo ""
}

# Функция для синхронизации правил в проект
sync_project_rules() {
    local project_path="$1"
    local project_name=$(basename "$project_path")
    local cursor_rules_file="$project_path/.cursorrules"

    TOTAL_PROJECTS=$((TOTAL_PROJECTS + 1))

    # Если нет .cursorrules, пропускаем (должен быть создан через init-cursor-rules.sh)
    if [ ! -f "$cursor_rules_file" ]; then
        echo -e "${YELLOW}⏭️  $project_name - нет .cursorrules, пропускаем${NC}"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    # Читаем универсальные правила
    UNIVERSAL_CONTENT=$(cat "$UNIVERSAL_RULES_PATH")

    # Определяем тип проекта
    detect_project_type() {
        local path="$1"
        if [ -f "$path/package.json" ]; then
            echo "javascript/typescript"
        elif [ -f "$path/requirements.txt" ] || [ -f "$path/pyproject.toml" ]; then
            echo "python"
        elif [ -f "$path/Cargo.toml" ]; then
            echo "rust"
        elif [ -f "$path/go.mod" ]; then
            echo "go"
        elif [ -f "$path/pom.xml" ] || [ -f "$path/build.gradle" ]; then
            echo "java"
        else
            echo "generic"
        fi
    }

    PROJECT_TYPE=$(detect_project_type "$project_path")
    PROJECT_NAME=$(basename "$project_path")

    # Создаем резервную копию
    BACKUP_FILE="${cursor_rules_file}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$cursor_rules_file" "$BACKUP_FILE" 2>/dev/null || true

    # Извлекаем специфичные правила из существующего файла (все что после "## 🎯 СПЕЦИФИЧНЫЕ")
    SPECIFIC_RULES=$(awk '/## 🎯 СПЕЦИФИЧНЫЕ/,0' "$cursor_rules_file" 2>/dev/null || echo "")

    # Если специфичных правил нет, создаем шаблон
    if [ -z "$SPECIFIC_RULES" ] || [ "$SPECIFIC_RULES" = "" ]; then
        SPECIFIC_RULES="# 🎯 СПЕЦИФИЧНЫЕ ДЛЯ ПРОЕКТА ПРАВИЛА

### Тип проекта: $PROJECT_TYPE

[Добавьте специфичные правила для вашего проекта]

---

## 📁 СТРУКТУРА ПРОЕКТА

[Опишите структуру вашего проекта здесь]

## 🔧 ТЕХНОЛОГИИ

[Перечисли используемые технологии и инструменты]

## 🧪 ТЕСТИРОВАНИЕ

- Фреймворк: [укажите фреймворк для тестов]
- Покрытие: > 80%
- Команда запуска: [make test / npm test / pytest / etc]

## 🚀 ДЕПЛОЙ

[Опишите процесс деплоя проекта]

---

**Обновлено:** $(date +"%Y-%m-%d %H:%M:%S")
**Версия универсальных правил:** $(md5sum "$UNIVERSAL_RULES_PATH" 2>/dev/null | cut -d' ' -f1 || md5 -q "$UNIVERSAL_RULES_PATH" 2>/dev/null || echo "unknown")
"
    fi

    # Создаем новый .cursorrules с обновленными универсальными правилами
    cat > "$cursor_rules_file" << EOF
---
description: "Rules for $PROJECT_NAME project"
alwaysApply: true
---

# ПРАВИЛА ПРОЕКТА: $PROJECT_NAME

## 🌍 УНИВЕРСАЛЬНЫЕ ПРАВИЛА

$UNIVERSAL_CONTENT

---

$SPECIFIC_RULES
EOF

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $project_name - правила синхронизированы${NC}"
        SYNCED=$((SYNCED + 1))
        # Удаляем резервную копию если успешно
        rm -f "$BACKUP_FILE" 2>/dev/null || true
        return 0
    else
        echo -e "${RED}❌ $project_name - ошибка синхронизации${NC}"
        # Восстанавливаем из резервной копии
        if [ -f "$BACKUP_FILE" ]; then
            mv "$BACKUP_FILE" "$cursor_rules_file" 2>/dev/null || true
        fi
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# Рекурсивный поиск проектов
find_projects() {
    local dir="$1"
    local depth="${2:-0}"
    local max_depth="${3:-3}"  # Максимальная глубина поиска

    # Ограничиваем глубину поиска
    if [ "$depth" -ge "$max_depth" ]; then
        return
    fi

    # Обрабатываем текущую директорию
    if is_project "$dir"; then
        sync_project_rules "$dir"
        # Если нашли проект, не идем глубже
        return
    fi

    # Рекурсивно ищем в поддиректориях
    if [ -d "$dir" ]; then
        for subdir in "$dir"/*; do
            if [ -d "$subdir" ] && [ ! -L "$subdir" ]; then
                find_projects "$subdir" $((depth + 1)) "$max_depth"
            fi
        done
    fi
}

# Основная логика
echo -e "${BLUE}🚀 Начинаем синхронизацию...${NC}"
echo -e "${BLUE}📄 Источник: $UNIVERSAL_RULES_PATH${NC}"
echo -e "${BLUE}📁 Базовая директория: $BASE_DIR${NC}"
echo ""

# Ищем и синхронизируем проекты
find_projects "$BASE_DIR"

# Сохраняем хеш в кэш
mkdir -p "$HOME/.cursor"
echo "{\"last_hash\":\"$UNIVERSAL_RULES_HASH\",\"last_sync\":\"$(date -Iseconds)\"}" > "$CACHE_FILE"

# Итоговая статистика
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📊 Итоговая статистика:${NC}"
echo -e "   Всего проектов найдено: ${TOTAL_PROJECTS}"
echo -e "   ✅ Синхронизировано: ${SYNCED}"
echo -e "   ⏭️  Пропущено (нет .cursorrules): ${SKIPPED}"
echo -e "   ❌ Ошибок: ${ERRORS}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ $SYNCED -gt 0 ]; then
    echo -e "${GREEN}✅ Успешно синхронизировано ${SYNCED} проектов!${NC}"
    echo -e "${BLUE}💾 Хеш правил сохранен: $UNIVERSAL_RULES_HASH${NC}"
fi

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}⚠️  Произошло ${ERRORS} ошибок${NC}"
    exit 1
fi

exit 0
