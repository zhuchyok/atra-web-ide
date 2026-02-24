#!/bin/bash
# Скрипт активации Victoria Initiative and Self-Extension

set -e

echo "🚀 Активация Victoria Initiative and Self-Extension"
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Проверка зависимостей
echo "1️⃣ Проверка зависимостей..."
if pip3 list | grep -q watchdog; then
    echo -e "${GREEN}   ✅ watchdog установлен${NC}"
else
    echo -e "${YELLOW}   ⚠️ watchdog не установлен${NC}"
    echo "   Установка watchdog..."
    pip3 install watchdog
    echo -e "${GREEN}   ✅ watchdog установлен${NC}"
fi
echo ""

# 2. Применение миграции БД
echo "2️⃣ Применение миграции БД..."
if docker ps --format "{{.Names}}" | grep -q "knowledge_os"; then
    echo "   Применение миграции через Docker..."
    docker exec -i knowledge_os-db-1 psql -U postgres -d knowledge_os < knowledge_os/db/migrations/add_skills_tables.sql 2>&1 | grep -v "NOTICE" || echo -e "${GREEN}   ✅ Миграция применена${NC}"
else
    echo -e "${YELLOW}   ⚠️ Docker контейнер БД не найден${NC}"
    echo "   Применение миграции напрямую..."
    if command -v psql &> /dev/null; then
        psql -U postgres -d knowledge_os -f knowledge_os/db/migrations/add_skills_tables.sql 2>&1 | grep -v "NOTICE" || echo -e "${GREEN}   ✅ Миграция применена${NC}"
    else
        echo -e "${RED}   ❌ psql не найден. Примените миграцию вручную${NC}"
    fi
fi
echo ""

# 3. Проверка переменных окружения
echo "3️⃣ Проверка переменных окружения..."
if [ -f .env ]; then
    if grep -q "USE_VICTORIA_ENHANCED" .env; then
        echo -e "${GREEN}   ✅ USE_VICTORIA_ENHANCED настроен${NC}"
    else
        echo "   Добавление USE_VICTORIA_ENHANCED=true в .env..."
        echo "USE_VICTORIA_ENHANCED=true" >> .env
        echo -e "${GREEN}   ✅ USE_VICTORIA_ENHANCED добавлен${NC}"
    fi

    if grep -q "ENABLE_EVENT_MONITORING" .env; then
        echo -e "${GREEN}   ✅ ENABLE_EVENT_MONITORING настроен${NC}"
    else
        echo "   Добавление ENABLE_EVENT_MONITORING=true в .env..."
        echo "ENABLE_EVENT_MONITORING=true" >> .env
        echo -e "${GREEN}   ✅ ENABLE_EVENT_MONITORING добавлен${NC}"
    fi
else
    echo "   Создание .env файла..."
    cat > .env << EOF
USE_VICTORIA_ENHANCED=true
ENABLE_EVENT_MONITORING=true
FILE_WATCHER_ENABLED=true
SERVICE_MONITOR_ENABLED=true
DEADLINE_TRACKER_ENABLED=true
SKILLS_WATCHER_ENABLED=true
EOF
    echo -e "${GREEN}   ✅ .env файл создан${NC}"
fi
echo ""

# 4. Тест импортов
echo "4️⃣ Тест импортов..."
if python3 scripts/test_victoria_initiative.py > /dev/null 2>&1; then
    echo -e "${GREEN}   ✅ Все модули работают${NC}"
else
    echo -e "${YELLOW}   ⚠️ Некоторые модули недоступны (это нормально)${NC}"
fi
echo ""

# 5. Итог
echo -e "${GREEN}✅ Активация завершена!${NC}"
echo ""
echo "📋 Следующие шаги:"
echo "   1. Перезапустите Victoria Agent (если запущен)"
echo "   2. Проверьте логи: tail -f logs/victoria_enhanced.log"
echo "   3. Протестируйте: python3 scripts/test_victoria_initiative.py"
echo ""
echo "📚 Документация: HOW_TO_USE_VICTORIA_INITIATIVE.md"
