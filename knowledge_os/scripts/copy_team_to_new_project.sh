#!/bin/bash
# Автоматическое копирование команды экспертов в новый проект

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 КОПИРОВАНИЕ КОМАНДЫ ЭКСПЕРТОВ В НОВЫЙ ПРОЕКТ${NC}"
echo ""

# Проверка аргументов
if [ -z "$1" ]; then
    echo -e "${RED}❌ Ошибка: Укажите путь к новому проекту${NC}"
    echo ""
    echo "Использование:"
    echo "  bash scripts/copy_team_to_new_project.sh /path/to/new-project"
    echo ""
    echo "Пример:"
    echo "  bash scripts/copy_team_to_new_project.sh ~/projects/new-website"
    exit 1
fi

NEW_PROJECT_PATH="$1"
ATRA_PROJECT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Проверка существования нового проекта
if [ ! -d "$NEW_PROJECT_PATH" ]; then
    echo -e "${YELLOW}⚠️  Директория не существует. Создать? (y/n):${NC}"
    read -r CREATE_DIR
    if [ "$CREATE_DIR" = "y" ] || [ "$CREATE_DIR" = "Y" ]; then
        mkdir -p "$NEW_PROJECT_PATH"
        echo -e "${GREEN}✅ Директория создана${NC}"
    else
        echo -e "${RED}❌ Отменено${NC}"
        exit 1
    fi
fi

cd "$NEW_PROJECT_PATH"

echo -e "${GREEN}📋 ШАГ 1: Копирование .cursorrules${NC}"
if [ -f "$ATRA_PROJECT_PATH/.cursorrules" ]; then
    cp "$ATRA_PROJECT_PATH/.cursorrules" .cursorrules
    echo -e "${GREEN}  ✅ .cursorrules скопирован${NC}"
else
    echo -e "${RED}  ❌ Файл .cursorrules не найден в проекте ATRA${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}📋 ШАГ 2: Создание директории scripts${NC}"
mkdir -p scripts
echo -e "${GREEN}  ✅ Директория scripts создана${NC}"

echo ""
echo -e "${GREEN}📋 ШАГ 3: Копирование скриптов синхронизации${NC}"
if [ -f "$ATRA_PROJECT_PATH/scripts/sync_team_data.py" ]; then
    cp "$ATRA_PROJECT_PATH/scripts/sync_team_data.py" scripts/
    chmod +x scripts/sync_team_data.py
    echo -e "${GREEN}  ✅ sync_team_data.py скопирован${NC}"
fi

if [ -f "$ATRA_PROJECT_PATH/scripts/setup_team_sync.sh" ]; then
    cp "$ATRA_PROJECT_PATH/scripts/setup_team_sync.sh" scripts/
    chmod +x scripts/setup_team_sync.sh
    echo -e "${GREEN}  ✅ setup_team_sync.sh скопирован${NC}"
fi

if [ -f "$ATRA_PROJECT_PATH/scripts/auto_sync_team_data.sh" ]; then
    cp "$ATRA_PROJECT_PATH/scripts/auto_sync_team_data.sh" scripts/
    chmod +x scripts/auto_sync_team_data.sh
    echo -e "${GREEN}  ✅ auto_sync_team_data.sh скопирован${NC}"
fi

echo ""
echo -e "${GREEN}📋 ШАГ 4: Настройка синхронизации данных (опционально)${NC}"
echo -e "${YELLOW}Настроить синхронизацию данных команды? (y/n):${NC}"
read -r SETUP_SYNC

if [ "$SETUP_SYNC" = "y" ] || [ "$SETUP_SYNC" = "Y" ]; then
    if [ -d "$ATRA_PROJECT_PATH/.team_data" ]; then
        echo -e "${GREEN}  📦 Копирование данных команды...${NC}"
        mkdir -p .team_data
        cp -r "$ATRA_PROJECT_PATH/.team_data"/* .team_data/ 2>/dev/null || true
        echo -e "${GREEN}  ✅ Данные команды скопированы${NC}"
        
        # Инициализация Git если нужно
        if [ ! -d ".team_data/.git" ]; then
            echo -e "${GREEN}  🔧 Инициализация Git репозитория...${NC}"
            cd .team_data
            git init > /dev/null 2>&1
            git add -A > /dev/null 2>&1
            git commit -m "Initial team data sync" > /dev/null 2>&1 || true
            cd ..
            echo -e "${GREEN}  ✅ Git репозиторий инициализирован${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠️  Данные команды не найдены в проекте ATRA${NC}"
        echo -e "${YELLOW}  💡 Вы можете настроить синхронизацию позже:${NC}"
        echo -e "${YELLOW}     bash scripts/setup_team_sync.sh${NC}"
    fi
else
    echo -e "${YELLOW}  ⏭️  Пропущено (можно настроить позже)${NC}"
fi

echo ""
echo -e "${GREEN}📋 ШАГ 5: Проверка настройки${NC}"
if [ -f ".cursorrules" ]; then
    echo -e "${GREEN}  ✅ .cursorrules найден${NC}"
else
    echo -e "${RED}  ❌ .cursorrules не найден${NC}"
fi

if [ -d ".team_data" ]; then
    FILE_COUNT=$(find .team_data -type f | wc -l | tr -d ' ')
    echo -e "${GREEN}  ✅ Данные команды: $FILE_COUNT файлов${NC}"
fi

echo ""
echo -e "${GREEN}======================================================================${NC}"
echo -e "${GREEN}✅ НАСТРОЙКА ЗАВЕРШЕНА!${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo ""
echo -e "${GREEN}📋 СЛЕДУЮЩИЕ ШАГИ:${NC}"
echo ""
echo "1. Откройте проект в Cursor IDE:"
echo "   cd $NEW_PROJECT_PATH"
echo "   cursor ."
echo ""
echo "2. Откройте новый чат в Cursor"
echo ""
echo "3. Опишите любую задачу - Виктория автоматически активирует команду!"
echo ""
echo "4. (Опционально) Настроить синхронизацию с центральным репозиторием:"
echo "   bash scripts/setup_team_sync.sh"
echo ""
echo -e "${GREEN}🎉 ГОТОВО! Команда из 22 экспертов готова к работе!${NC}"
echo ""

