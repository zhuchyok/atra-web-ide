#!/bin/bash
# Скрипт для запуска обработки задач корпорации
# Назначает задачи экспертам и запускает worker

set -e

echo "=============================================="
echo "🚀 Запуск обработки задач корпорации ATRA"
echo "=============================================="
echo ""

# 1. Назначение задач экспертам через orchestrator
echo "[1/3] Назначение задач экспертам..."
docker exec knowledge_os_api python /app/enhanced_orchestrator.py 2>&1 | head -20
echo ""

# 2. Проверка назначенных задач
echo "[2/3] Проверка назначенных задач..."
UNASSIGNED=$(docker exec -i atra-knowledge-os-db psql -U admin -d knowledge_os -tAc "SELECT COUNT(*) FROM tasks WHERE assignee_expert_id IS NULL AND status = 'pending';" 2>/dev/null)
ASSIGNED=$(docker exec -i atra-knowledge-os-db psql -U admin -d knowledge_os -tAc "SELECT COUNT(*) FROM tasks WHERE assignee_expert_id IS NOT NULL AND status = 'pending';" 2>/dev/null)
echo "  Неназначенных задач: $UNASSIGNED"
echo "  Назначенных задач: $ASSIGNED"
echo ""

# 3. Проверка worker
echo "[3/3] Проверка Knowledge OS Worker..."
if docker ps | grep -q knowledge_os_worker; then
    echo "  ✅ Worker запущен"
    echo "  Проверка подключения к БД..."
    docker exec knowledge_os_worker python -c "
import asyncio
import asyncpg
import os

async def test():
    try:
        pool = await asyncpg.create_pool(os.getenv('DATABASE_URL'))
        conn = await pool.acquire()
        result = await conn.fetchval('SELECT COUNT(*) FROM experts')
        print(f'  ✅ Worker подключен к БД (найдено {result} экспертов)')
        await pool.release(conn)
        await pool.close()
    except Exception as e:
        print(f'  ❌ Ошибка подключения: {e}')

asyncio.run(test())
" 2>&1
else
    echo "  ❌ Worker не запущен"
    echo "  Запуск: docker start knowledge_os_worker"
fi

echo ""
echo "=============================================="
echo "✅ Готово!"
echo "=============================================="
echo ""
echo "Статус задач:"
docker exec -i atra-knowledge-os-db psql -U admin -d knowledge_os -c "SELECT status, COUNT(*) as count FROM tasks GROUP BY status ORDER BY count DESC;" 2>&1
