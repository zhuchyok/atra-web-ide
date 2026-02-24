#!/bin/bash
# Запуск всех автономных систем корпорации ATRA

echo "🚀 ЗАПУСК ВСЕХ АВТОНОМНЫХ СИСТЕМ"
echo "================================================"
echo ""

# Переходим в корень проекта
cd "$(dirname "$0")/.." || exit 1

# Проверка Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Проверка БД
if ! docker exec atra-knowledge-os-db psql -U admin -d knowledge_os -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ База данных недоступна!"
    exit 1
fi

# Функция запуска системы
start_system() {
    local name=$1
    local script=$2
    local check_cmd=$3

    echo -n "Запуск $name... "

    # Проверяем, не запущен ли уже
    if eval "$check_cmd" > /dev/null 2>&1; then
        echo "✅ Уже запущен"
        return 0
    fi

    # Запускаем
    if [ -f "$script" ]; then
        nohup python3 "$script" > /dev/null 2>&1 &
        sleep 2
        if eval "$check_cmd" > /dev/null 2>&1; then
            echo "✅ Запущен"
            return 0
        else
            echo "❌ Ошибка запуска"
            return 1
        fi
    else
        echo "❌ Скрипт не найден: $script"
        return 1
    fi
}

# 1. Enhanced Orchestrator (каждые 5 минут)
echo "1️⃣ Enhanced Orchestrator..."
if ps aux | grep -E "enhanced_orchestrator" | grep -v grep > /dev/null; then
    echo "   ✅ Уже запущен"
else
    echo "   Запуск..."
    cd knowledge_os/app || exit 1
    nohup python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')
from enhanced_orchestrator import run_enhanced_orchestration_cycle
import time

async def main():
    while True:
        try:
            await run_enhanced_orchestration_cycle()
            await asyncio.sleep(300)  # 5 минут
        except Exception as e:
            print(f'Error: {e}')
            await asyncio.sleep(60)

asyncio.run(main())
" > /tmp/enhanced_orchestrator.log 2>&1 &
    echo "   ✅ Запущен (PID: $!)"
    cd ../..
fi

# 2. Curiosity Engine (каждые 6 часов)
echo ""
echo "2️⃣ Curiosity Engine..."
if ps aux | grep -E "curiosity_engine" | grep -v grep > /dev/null; then
    echo "   ✅ Уже запущен"
else
    echo "   Запуск..."
    cd knowledge_os/app || exit 1
    nohup python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')
from curiosity_engine import CuriosityEngine
import time

async def main():
    engine = CuriosityEngine()
    while True:
        try:
            await engine.scan_for_gaps()
            await asyncio.sleep(21600)  # 6 часов
        except Exception as e:
            print(f'Error: {e}')
            await asyncio.sleep(3600)

asyncio.run(main())
" > /tmp/curiosity_engine.log 2>&1 &
    echo "   ✅ Запущен (PID: $!)"
    cd ../..
fi

# 3. Smart Worker (постоянно)
echo ""
echo "3️⃣ Smart Worker..."
if ps aux | grep -E "smart_worker_autonomous" | grep -v grep > /dev/null; then
    echo "   ✅ Уже запущен"
else
    echo "   Запуск..."
    cd knowledge_os/app || exit 1
    nohup python3 smart_worker_autonomous.py > /tmp/smart_worker.log 2>&1 &
    echo "   ✅ Запущен (PID: $!)"
    cd ../..
fi

# 4. Nightly Learner (ежедневно в 6:00 MSK)
echo ""
echo "4️⃣ Nightly Learner..."
if ps aux | grep -E "nightly_learner" | grep -v grep > /dev/null; then
    echo "   ✅ Уже запущен"
else
    echo "   Запуск (проверка каждые 60 минут)..."
    cd knowledge_os/app || exit 1
    nohup python3 -c "
import asyncio
import sys
from datetime import datetime, time
sys.path.insert(0, '.')
from nightly_learner import nightly_learning_cycle

async def main():
    while True:
        try:
            now = datetime.now()
            # Проверяем, 6:00 MSK (3:00 UTC)
            if now.hour == 3 and now.minute < 5:
                await nightly_learning_cycle()
            await asyncio.sleep(300)  # Проверка каждые 5 минут
        except Exception as e:
            print(f'Error: {e}')
            await asyncio.sleep(60)

asyncio.run(main())
" > /tmp/nightly_learner.log 2>&1 &
    echo "   ✅ Запущен (PID: $!)"
    cd ../..
fi

echo ""
echo "✅ ВСЕ СИСТЕМЫ ЗАПУЩЕНЫ"
echo ""
echo "📝 Логи:"
echo "  - Enhanced Orchestrator: /tmp/enhanced_orchestrator.log"
echo "  - Curiosity Engine: /tmp/curiosity_engine.log"
echo "  - Smart Worker: /tmp/smart_worker.log"
echo "  - Nightly Learner: /tmp/nightly_learner.log"
echo ""
echo "🔍 Проверка: bash scripts/check_all_autonomous_systems.sh"
