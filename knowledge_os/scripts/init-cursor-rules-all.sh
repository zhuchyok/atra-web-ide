#!/bin/bash

# Скрипт для массовой инициализации .cursorrules во всех существующих проектах
# Использование: ./init-cursor-rules-all.sh [base-directory]

set -e

BASE_DIR="${1:-$HOME}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INIT_SCRIPT="$SCRIPT_DIR/init-cursor-rules.sh"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔍 Поиск проектов без .cursorrules в: $BASE_DIR${NC}"
echo ""

# Счетчики
TOTAL_PROJECTS=0
INITIALIZED=0
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

# Функция для обработки проекта
process_project() {
    local project_path="$1"
    local project_name=$(basename "$project_path")
    
    TOTAL_PROJECTS=$((TOTAL_PROJECTS + 1))
    
    # Проверяем, есть ли уже .cursorrules
    if [ -f "$project_path/.cursorrules" ]; then
        # Проверяем, содержит ли универсальные правила
        if grep -q "КОМАНДА ЭКСПЕРТОВ\|Команда экспертов\|команда экспертов" "$project_path/.cursorrules" 2>/dev/null; then
            echo -e "${GREEN}✅ $project_name - правила уже применены${NC}"
            SKIPPED=$((SKIPPED + 1))
            return 0
        else
            echo -e "${YELLOW}⚠️  $project_name - есть .cursorrules, но без универсальных правил${NC}"
        fi
    else
        echo -e "${BLUE}📝 $project_name - создаем .cursorrules...${NC}"
    fi
    
    # Запускаем инициализацию (неинтерактивно)
    if "$INIT_SCRIPT" "$project_path" < /dev/null > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Инициализирован${NC}"
        INITIALIZED=$((INITIALIZED + 1))
        return 0
    else
        echo -e "${RED}   ❌ Ошибка инициализации${NC}"
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
        process_project "$dir"
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
echo -e "${BLUE}🚀 Начинаем поиск проектов...${NC}"
echo ""

# Ищем проекты
find_projects "$BASE_DIR"

# Итоговая статистика
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📊 Итоговая статистика:${NC}"
echo -e "   Всего проектов найдено: ${TOTAL_PROJECTS}"
echo -e "   ✅ Инициализировано: ${INITIALIZED}"
echo -e "   ⏭️  Пропущено (уже есть правила): ${SKIPPED}"
echo -e "   ❌ Ошибок: ${ERRORS}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ $INITIALIZED -gt 0 ]; then
    echo -e "${GREEN}✅ Успешно инициализировано ${INITIALIZED} проектов!${NC}"
fi

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}⚠️  Произошло ${ERRORS} ошибок${NC}"
    exit 1
fi

exit 0

