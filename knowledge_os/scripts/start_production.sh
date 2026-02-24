#!/bin/bash
# Скрипт для запуска системы на продакшн сервере
# Выполните на сервере: bash scripts/start_production.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 ЗАПУСК СИСТЕМЫ НА ПРОДАКШН${NC}"
echo "=================================="

# Переход в директорию проекта
cd /root/atra || {
    echo -e "${RED}❌ Директория /root/atra не найдена!${NC}"
    exit 1
}

echo -e "\n${YELLOW}1. Проверка текущего процесса...${NC}"
PID=$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}')
if [ -n "$PID" ]; then
    echo -e "${YELLOW}⚠️  Найден запущенный процесс (PID: $PID)${NC}"
    read -p "Остановить и перезапустить? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Остановка процесса..."
        kill -SIGTERM "$PID" || true
        sleep 5
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Принудительное завершение..."
            kill -9 "$PID" || true
        fi
        echo -e "${GREEN}✅ Процесс остановлен${NC}"
    else
        echo -e "${YELLOW}ℹ️  Оставляем текущий процесс${NC}"
        exit 0
    fi
else
    echo -e "${GREEN}✅ Процесс не найден (можно запускать)${NC}"
fi

# Проверка конфигурации
echo -e "\n${YELLOW}2. Проверка конфигурации...${NC}"
if [ -f env ]; then
    ATRA_ENV=$(grep "^ATRA_ENV=" env | cut -d'=' -f2)
    echo "ATRA_ENV: $ATRA_ENV"
    if [ "$ATRA_ENV" != "prod" ]; then
        echo -e "${YELLOW}⚠️  ATRA_ENV не установлен в prod, обновляю...${NC}"
        sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env
        echo -e "${GREEN}✅ Обновлено${NC}"
    fi
else
    echo -e "${RED}⚠️  Файл env не найден!${NC}"
fi

# Проверка списка монет
echo -e "\n${YELLOW}3. Проверка списка монет...${NC}"
python3 -c "from config import COINS; print('COINS:', COINS)" 2>&1 | head -3

# Активация виртуального окружения
echo -e "\n${YELLOW}4. Активация виртуального окружения...${NC}"
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo -e "${GREEN}✅ Виртуальное окружение активировано${NC}"
elif [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✅ Виртуальное окружение активировано${NC}"
else
    echo -e "${YELLOW}ℹ️  Виртуальное окружение не найдено, используем системный Python${NC}"
fi

# Создание директории для логов
echo -e "\n${YELLOW}5. Подготовка логов...${NC}"
mkdir -p logs
echo -e "${GREEN}✅ Директория logs готова${NC}"

# Запуск системы
echo -e "\n${YELLOW}6. Запуск системы...${NC}"
nohup python3 main.py > logs/atra.log 2>&1 &
NEW_PID=$!

# Ожидание запуска и создания лог-файла
echo "Ожидание запуска системы..."
for i in {1..10}; do
    if ps -p $NEW_PID > /dev/null 2>&1; then
        if [ -f logs/atra.log ] && [ -s logs/atra.log ]; then
            break
        fi
    fi
    sleep 1
done

# Проверка запуска
if ps -p $NEW_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Система запущена успешно!${NC}"
    echo -e "${GREEN}   PID: $NEW_PID${NC}"
    echo -e "${GREEN}   Логи: logs/atra.log${NC}"
    echo ""
    if [ -f logs/atra.log ] && [ -s logs/atra.log ]; then
        echo -e "${YELLOW}Проверка логов (последние 20 строк):${NC}"
        tail -20 logs/atra.log
    else
        echo -e "${YELLOW}⚠️  Лог-файл еще создается, подождите несколько секунд${NC}"
    fi
    echo ""
    echo -e "${GREEN}Для мониторинга используйте:${NC}"
    echo "  tail -f logs/atra.log"
else
    echo -e "${RED}❌ Ошибка запуска!${NC}"
    if [ -f logs/atra.log ]; then
        echo -e "${RED}Последние строки лога:${NC}"
        tail -50 logs/atra.log
    else
        echo -e "${RED}Лог-файл не создан, проверьте ошибки запуска${NC}"
    fi
    exit 1
fi
