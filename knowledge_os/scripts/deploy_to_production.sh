#!/bin/bash
# Скрипт для деплоя на продакшн сервер
# Использование: ./scripts/deploy_to_production.sh

set -e  # Остановка при ошибке

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Параметры сервера
SERVER="root@185.177.216.15"
SERVER_PASS="u44Ww9NmtQj,XG"
REMOTE_DIR="/root/atra"  # Измените на актуальный путь

echo -e "${GREEN}🚀 НАЧАЛО ДЕПЛОЯ НА ПРОДАКШН${NC}"
echo "=================================="

# 1. Проверка локальных изменений
echo -e "\n${YELLOW}1. Проверка локальных изменений...${NC}"
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${RED}⚠️  Есть незакоммиченные изменения!${NC}"
    read -p "Продолжить? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 2. Создание бэкапа на сервере
echo -e "\n${YELLOW}2. Создание бэкапа на сервере...${NC}"
sshpass -p "$SERVER_PASS" ssh "$SERVER" << 'ENDSSH'
    cd /root/atra || exit 1
    BACKUP_DIR="/root/atra.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Создание бэкапа в $BACKUP_DIR..."
    cp -r /root/atra "$BACKUP_DIR" || exit 1
    echo "✅ Бэкап создан: $BACKUP_DIR"
ENDSSH

# 3. Остановка текущего процесса
echo -e "\n${YELLOW}3. Остановка текущего процесса...${NC}"
sshpass -p "$SERVER_PASS" ssh "$SERVER" << 'ENDSSH'
    # Найти и остановить процесс
    PID=$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}')
    if [ -n "$PID" ]; then
        echo "Остановка процесса PID: $PID"
        kill -SIGTERM "$PID" || true
        sleep 5
        # Проверка, что процесс остановлен
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "⚠️  Процесс не остановился, принудительное завершение..."
            kill -9 "$PID" || true
        fi
        echo "✅ Процесс остановлен"
    else
        echo "ℹ️  Процесс не найден (возможно, уже остановлен)"
    fi
ENDSSH

# 4. Копирование файлов
echo -e "\n${YELLOW}4. Копирование файлов на сервер...${NC}"
sshpass -p "$SERVER_PASS" rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='data/backtest_data/*' \
    --exclude='logs/*' \
    ./ "$SERVER:$REMOTE_DIR/"

# 5. Обновление env файла на сервере
echo -e "\n${YELLOW}5. Обновление конфигурации на сервере...${NC}"
sshpass -p "$SERVER_PASS" ssh "$SERVER" << 'ENDSSH'
    cd /root/atra || exit 1

    # Убедиться, что ATRA_ENV=prod
    if [ -f env ]; then
        sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env
        echo "✅ ATRA_ENV установлен в prod"
    fi

    # Проверить TELEGRAM_TOKEN
    if ! grep -q "TELEGRAM_TOKEN=8156844481" env; then
        echo "⚠️  Проверьте TELEGRAM_TOKEN в env файле!"
    fi

    echo "✅ Конфигурация обновлена"
ENDSSH

# 6. Установка зависимостей (если нужно)
echo -e "\n${YELLOW}6. Проверка зависимостей...${NC}"
sshpass -p "$SERVER_PASS" ssh "$SERVER" << 'ENDSSH'
    cd /root/atra || exit 1

    # Активировать виртуальное окружение (если используется)
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    # Проверить основные зависимости
    python3 -c "import telegram; import pandas; import numpy" 2>/dev/null && \
        echo "✅ Основные зависимости установлены" || \
        echo "⚠️  Некоторые зависимости отсутствуют, запустите: pip install -r requirements.txt"
ENDSSH

# 7. Проверка конфигурации
echo -e "\n${YELLOW}7. Проверка конфигурации...${NC}"
sshpass -p "$SERVER_PASS" ssh "$SERVER" << 'ENDSSH'
    cd /root/atra || exit 1

    # Проверить COINS
    echo "Проверка списка монет:"
    python3 -c "from config import COINS; print('COINS:', COINS)" 2>&1 | head -5

    # Проверить SYMBOL_SPECIFIC_CONFIG
    echo "Проверка индивидуальных параметров:"
    python3 -c "from src.core.config import SYMBOL_SPECIFIC_CONFIG; print('Конфигурация для:', list(SYMBOL_SPECIFIC_CONFIG.keys()))" 2>&1 | head -10
ENDSSH

# 8. Запуск системы
echo -e "\n${YELLOW}8. Запуск системы...${NC}"
read -p "Запустить систему на сервере? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sshpass -p "$SERVER_PASS" ssh "$SERVER" << 'ENDSSH'
        cd /root/atra || exit 1

        # Активировать виртуальное окружение (если используется)
        if [ -d "venv" ]; then
            source venv/bin/activate
        fi

        # Создать директорию для логов, если не существует
        mkdir -p logs

        # Запустить систему в фоне
        nohup python3 main.py > logs/atra.log 2>&1 &

        # Подождать немного
        sleep 3

        # Проверить, что процесс запущен
        PID=$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}')
        if [ -n "$PID" ]; then
            echo "✅ Система запущена (PID: $PID)"
        else
            echo "❌ Ошибка запуска! Проверьте логи: tail -100 logs/atra.log"
            exit 1
        fi
ENDSSH
fi

# 9. Проверка логов
echo -e "\n${YELLOW}9. Проверка логов (первые 50 строк)...${NC}"
sshpass -p "$SERVER_PASS" ssh "$SERVER" << 'ENDSSH'
    cd /root/atra || exit 1
    if [ -f logs/atra.log ]; then
        echo "Последние строки лога:"
        tail -50 logs/atra.log
    else
        echo "⚠️  Файл логов не найден"
    fi
ENDSSH

echo -e "\n${GREEN}✅ ДЕПЛОЙ ЗАВЕРШЕН!${NC}"
echo -e "\n${YELLOW}Следующие шаги:${NC}"
echo "1. Проверьте логи: ssh $SERVER 'tail -f $REMOTE_DIR/logs/atra.log'"
echo "2. Проверьте Telegram бота"
echo "3. Мониторьте генерацию сигналов"
echo "4. Проверьте использование оптимального портфеля (AVAXUSDT, LINKUSDT, SOLUSDT, SUIUSDT, DOGEUSDT)"
