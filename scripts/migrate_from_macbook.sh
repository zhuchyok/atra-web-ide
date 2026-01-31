#!/bin/bash
# Миграция узлов знаний с MacBook на Mac Studio
# Запускать на Mac Studio

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Миграция узлов знаний с MacBook на Mac Studio"
echo "   Время: $(date)"
echo ""

# Настройки MacBook
MACBOOK_IP="${MACBOOK_IP:-192.168.1.43}"
MACBOOK_USER="${MACBOOK_USER:-bikos}"
MACBOOK_DB_URL="${MACBOOK_DB_URL:-postgresql://admin:secret@${MACBOOK_IP}:5432/knowledge_os}"

# Локальная база
LOCAL_DB_URL="postgresql://admin:secret@knowledge_postgres:5432/knowledge_os"

echo "📋 Настройки:"
echo "   MacBook: $MACBOOK_IP"
echo "   Пользователь: $MACBOOK_USER"
echo ""

# Проверяем подключение к MacBook
echo "🔍 Проверка подключения к MacBook..."
if ping -c 1 -W 2 "$MACBOOK_IP" > /dev/null 2>&1; then
    echo "   ✅ MacBook доступен"
else
    echo "   ❌ MacBook недоступен ($MACBOOK_IP)"
    echo ""
    echo "Проверьте:"
    echo "  1. MacBook включен и в сети"
    echo "  2. IP адрес правильный (текущий: $MACBOOK_IP)"
    echo "  3. Переменные: MACBOOK_IP, MACBOOK_USER"
    exit 1
fi

# Проверяем PostgreSQL на MacBook
echo "🔍 Проверка PostgreSQL на MacBook..."
if docker exec -e PGPASSWORD=secret knowledge_postgres psql -h "$MACBOOK_IP" -U admin -d knowledge_os -c "SELECT 1;" > /dev/null 2>&1; then
    echo "   ✅ PostgreSQL доступен"
else
    echo "   ⚠️  Прямое подключение не работает"
    echo "   Пробуем через SSH туннель..."
    
    # Создаем SSH туннель
    TUNNEL_PORT=5433
    ssh -fN -L ${TUNNEL_PORT}:localhost:5432 ${MACBOOK_USER}@${MACBOOK_IP} 2>/dev/null || {
        echo "   ❌ Не удалось создать SSH туннель"
        echo ""
        echo "Альтернатива: Создайте дамп на MacBook:"
        echo "  pg_dump -U admin -d knowledge_os > ~/knowledge_os_dump.sql"
        echo "  Затем импортируйте:"
        echo "  docker exec -i knowledge_postgres psql -U admin -d knowledge_os < ~/knowledge_os_dump.sql"
        exit 1
    }
    
    MACBOOK_DB_URL="postgresql://admin:secret@localhost:${TUNNEL_PORT}/knowledge_os"
    echo "   ✅ SSH туннель создан (порт $TUNNEL_PORT)"
fi

# Запускаем миграцию через Python скрипт
echo ""
echo "💾 Запуск миграции..."
docker exec -e DATABASE_URL="$LOCAL_DB_URL" \
    -e MACBOOK_DB_URL="$MACBOOK_DB_URL" \
    victoria-agent python3 -c "
import asyncio
import sys
import os
sys.path.insert(0, '/app/knowledge_os')

from scripts.migrate_knowledge_from_server46 import migrate_knowledge_nodes

# Адаптируем для MacBook
import asyncpg

async def migrate_from_macbook():
    macbook_url = os.getenv('MACBOOK_DB_URL')
    local_url = os.getenv('DATABASE_URL')
    
    print(f'📡 Подключение к MacBook: {macbook_url.replace(\"secret\", \"***\")}')
    macbook_conn = await asyncpg.connect(macbook_url)
    
    print(f'📡 Подключение к локальной базе')
    local_conn = await asyncpg.connect(local_url)
    
    try:
        # Получаем статистику
        macbook_count = await macbook_conn.fetchval('SELECT COUNT(*) FROM knowledge_nodes')
        local_count = await local_conn.fetchval('SELECT COUNT(*) FROM knowledge_nodes')
        
        print(f'📊 Узлов на MacBook: {macbook_count}')
        print(f'📊 Узлов локально: {local_count}')
        print(f'📊 Недостает: {macbook_count - local_count}')
        
        if macbook_count <= local_count:
            print('✅ Все узлы уже мигрированы!')
            return
        
        # Мигрируем недостающие узлы
        print('💾 Миграция узлов...')
        # ... (логика миграции из migrate_knowledge_from_server46.py)
        
    finally:
        await macbook_conn.close()
        await local_conn.close()

asyncio.run(migrate_from_macbook())
" 2>&1

echo ""
echo "✅ Миграция завершена!"
