#!/bin/bash
# Скрипт для обновления бота с git и проверки работы

set -e

echo "=================================================================================="
echo "👥 КОМАНДА ИЗ 13 ЭКСПЕРТОВ - ОБНОВЛЕНИЕ И ПРОВЕРКА БОТА"
echo "=================================================================================="
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Переменные
BOT_DIR="/root/atra"
SERVICE_NAME="myproject.service"

echo -e "${YELLOW}📋 ШАГ 1: Проверка текущего статуса${NC}"
echo ""

# Проверяем, запущен ли бот
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✅ Бот запущен через systemd${NC}"
    BOT_RUNNING=true
else
    echo -e "${YELLOW}⚠️  Бот не запущен через systemd${NC}"
    BOT_RUNNING=false
fi

# Проверяем процессы Python
PYTHON_PROCESSES=$(ps aux | grep -E "(signal_live|main\.py)" | grep -v grep | wc -l)
if [ $PYTHON_PROCESSES -gt 0 ]; then
    echo -e "${GREEN}✅ Найдено процессов Python: $PYTHON_PROCESSES${NC}"
    ps aux | grep -E "(signal_live|main\.py)" | grep -v grep
else
    echo -e "${YELLOW}⚠️  Процессы Python не найдены${NC}"
fi

echo ""
echo -e "${YELLOW}📋 ШАГ 2: Остановка бота${NC}"
echo ""

# Останавливаем systemd сервис
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "Останавливаем systemd сервис..."
    systemctl stop $SERVICE_NAME
    sleep 2
fi

# Останавливаем все процессы Python
echo "Останавливаем процессы Python..."
pkill -f "signal_live.py" || true
pkill -f "main.py" || true
sleep 2

# Проверяем, что все остановлено
REMAINING=$(ps aux | grep -E "(signal_live|main\.py)" | grep -v grep | wc -l)
if [ $REMAINING -eq 0 ]; then
    echo -e "${GREEN}✅ Все процессы остановлены${NC}"
else
    echo -e "${RED}⚠️  Остались процессы, принудительно завершаем...${NC}"
    pkill -9 -f "signal_live.py" || true
    pkill -9 -f "main.py" || true
    sleep 1
fi

echo ""
echo -e "${YELLOW}📋 ШАГ 3: Обновление кода с git${NC}"
echo ""

cd $BOT_DIR

# Проверяем статус git
echo "Проверяем статус git..."
git status --short

# Обновляем код
echo "Обновляем код с git..."
git pull origin main || git pull origin master || git pull

echo -e "${GREEN}✅ Код обновлен${NC}"

echo ""
echo -e "${YELLOW}📋 ШАГ 4: Проверка изменений${NC}"
echo ""

# Показываем последние коммиты
echo "Последние 5 коммитов:"
git log --oneline -5

echo ""
echo -e "${YELLOW}📋 ШАГ 5: Проверка конфигурации${NC}"
echo ""

# Проверяем config.py
if [ -f "config.py" ]; then
    echo -e "${GREEN}✅ config.py найден${NC}"

    # Проверяем включенные фильтры
    echo ""
    echo "Проверка включенных фильтров:"
    python3 << 'PYEOF'
import sys
sys.path.insert(0, '/root/atra')
try:
    from config import (
        USE_VP_FILTER, USE_VWAP_FILTER, USE_ORDER_FLOW_FILTER,
        USE_MICROSTRUCTURE_FILTER, USE_MOMENTUM_FILTER, USE_TREND_STRENGTH_FILTER,
        USE_AMT_FILTER, USE_MARKET_PROFILE_FILTER, USE_INSTITUTIONAL_PATTERNS_FILTER
    )
    print(f"  VP Filter: {'✅' if USE_VP_FILTER else '❌'}")
    print(f"  VWAP Filter: {'✅' if USE_VWAP_FILTER else '❌'}")
    print(f"  Order Flow: {'✅' if USE_ORDER_FLOW_FILTER else '❌'}")
    print(f"  Microstructure: {'✅' if USE_MICROSTRUCTURE_FILTER else '❌'}")
    print(f"  Momentum: {'✅' if USE_MOMENTUM_FILTER else '❌'}")
    print(f"  Trend Strength: {'✅' if USE_TREND_STRENGTH_FILTER else '❌'}")
    print(f"  AMT: {'✅' if USE_AMT_FILTER else '❌'}")
    print(f"  Market Profile: {'✅' if USE_MARKET_PROFILE_FILTER else '❌'}")
    print(f"  Institutional Patterns: {'✅' if USE_INSTITUTIONAL_PATTERNS_FILTER else '❌'}")
except Exception as e:
    print(f"  ❌ Ошибка проверки: {e}")
PYEOF
else
    echo -e "${RED}❌ config.py не найден${NC}"
fi

echo ""
echo -e "${YELLOW}📋 ШАГ 6: Запуск бота${NC}"
echo ""

# Запускаем через systemd
if systemctl list-unit-files | grep -q $SERVICE_NAME; then
    echo "Запускаем через systemd..."
    systemctl start $SERVICE_NAME
    sleep 3

    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${GREEN}✅ Бот запущен через systemd${NC}"
    else
        echo -e "${RED}❌ Ошибка запуска через systemd${NC}"
        systemctl status $SERVICE_NAME --no-pager -l
    fi
else
    echo "Systemd сервис не найден, запускаем напрямую..."
    cd $BOT_DIR
    nohup python3 signal_live.py > signal_live.log 2>&1 &
    sleep 3
fi

# Проверяем процессы
echo ""
echo "Проверка процессов:"
ps aux | grep -E "(signal_live|main\.py)" | grep -v grep || echo "Процессы не найдены"

echo ""
echo -e "${YELLOW}📋 ШАГ 7: Проверка работы бота${NC}"
echo ""

# Ждем немного для инициализации
sleep 5

# Проверяем логи
echo "Последние 20 строк логов:"
if [ -f "$BOT_DIR/signal_live.log" ]; then
    tail -20 $BOT_DIR/signal_live.log
elif [ -f "$BOT_DIR/logs/signal_live.log" ]; then
    tail -20 $BOT_DIR/logs/signal_live.log
else
    echo "Лог файл не найден"
fi

echo ""
echo "Проверка базы данных:"
python3 << 'PYEOF'
import sys
import sqlite3
import os
from datetime import datetime, timedelta

sys.path.insert(0, '/root/atra')

db_path = '/root/atra/trading.db'
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверяем сигналы за последние 24 часа
        cursor.execute("""
            SELECT COUNT(*) FROM signals
            WHERE datetime(ts) > datetime('now', '-24 hours')
        """)
        signals_24h = cursor.fetchone()[0]
        print(f"  📊 Сигналов за 24ч: {signals_24h}")

        # Проверяем активные сигналы
        cursor.execute("""
            SELECT COUNT(*) FROM active_signals
            WHERE status = 'active'
        """)
        active_signals = cursor.fetchone()[0]
        print(f"  📊 Активных сигналов: {active_signals}")

        # Проверяем последние сигналы
        cursor.execute("""
            SELECT symbol, side, ts FROM signals
            ORDER BY ts DESC LIMIT 5
        """)
        recent = cursor.fetchall()
        if recent:
            print(f"  📊 Последние 5 сигналов:")
            for symbol, side, ts in recent:
                print(f"    - {symbol} {side} ({ts})")
        else:
            print(f"  ⚠️  Нет сигналов в базе")

        conn.close()
    except Exception as e:
        print(f"  ❌ Ошибка проверки БД: {e}")
else:
    print(f"  ⚠️  База данных не найдена: {db_path}")
PYEOF

echo ""
echo -e "${YELLOW}📋 ШАГ 8: Проверка отбора монет${NC}"
echo ""

# Проверяем, как бот отбирает монеты
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/root/atra')

try:
    # Проверяем функцию отбора монет
    from src.execution.exchange_api import get_filtered_top_usdt_pairs_fast
    from src.strategies.pair_filtering import get_filtered_top_usdt_pairs_fast as get_filtered_pairs

    print("Проверка функции отбора монет...")

    # Пробуем получить список монет
    try:
        pairs = get_filtered_top_usdt_pairs_fast(limit=10)
        if pairs:
            print(f"  ✅ Найдено монет: {len(pairs)}")
            print(f"  📊 Топ-10 монет:")
            for i, pair in enumerate(pairs[:10], 1):
                print(f"    {i}. {pair}")
        else:
            print("  ⚠️  Список монет пуст")
    except Exception as e:
        print(f"  ❌ Ошибка получения монет: {e}")

except ImportError as e:
    print(f"  ⚠️  Модуль не найден: {e}")
except Exception as e:
    print(f"  ❌ Ошибка: {e}")
PYEOF

echo ""
echo "=================================================================================="
echo -e "${GREEN}✅ ОБНОВЛЕНИЕ И ПРОВЕРКА ЗАВЕРШЕНЫ${NC}"
echo "=================================================================================="
echo ""
echo "📋 СЛЕДУЮЩИЕ ШАГИ:"
echo "  1. Проверьте логи: tail -f $BOT_DIR/signal_live.log"
echo "  2. Проверьте статус: systemctl status $SERVICE_NAME"
echo "  3. Проверьте базу данных: python3 -c \"import sqlite3; conn = sqlite3.connect('$BOT_DIR/trading.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM signals WHERE datetime(ts) > datetime(\\\"now\\\", \\\"-1 hour\\\")'); print(f'Сигналов за час: {cursor.fetchone()[0]}')\""
echo ""
