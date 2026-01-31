#!/usr/bin/env python3
"""
Проверка финансовых логов
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from evaluator import get_pool

async def check_finance():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Всего записей
        total = await conn.fetchval("SELECT COUNT(*) FROM interaction_logs")
        print(f"📊 Всего записей в interaction_logs: {total}")
        
        if total > 0:
            # Последняя запись
            last = await conn.fetchrow("""
                SELECT token_usage, cost_usd, created_at, metadata->>'source' as source
                FROM interaction_logs 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            print(f"\n📝 Последняя запись:")
            print(f"   Токены: {last['token_usage']}")
            print(f"   Затраты: ${last['cost_usd'] or 0:.4f}")
            print(f"   Источник: {last['source']}")
            print(f"   Дата: {last['created_at']}")
        
        # За 24 часа
        last_24h = await conn.fetchrow("""
            SELECT 
                COUNT(*) as cnt,
                COALESCE(SUM(token_usage), 0) as tokens,
                COALESCE(SUM(cost_usd), 0) as cost
            FROM interaction_logs 
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        print(f"\n💰 За 24 часа:")
        print(f"   Записей: {last_24h['cnt']}")
        print(f"   Токены: {last_24h['tokens']}")
        print(f"   Затраты: ${last_24h['cost']:.4f}")
        
        # За 7 дней
        last_7d = await conn.fetchrow("""
            SELECT 
                COUNT(*) as cnt,
                COALESCE(SUM(token_usage), 0) as tokens,
                COALESCE(SUM(cost_usd), 0) as cost
            FROM interaction_logs 
            WHERE created_at > NOW() - INTERVAL '7 days'
        """)
        print(f"\n📅 За 7 дней:")
        print(f"   Записей: {last_7d['cnt']}")
        print(f"   Токены: {last_7d['tokens']}")
        print(f"   Затраты: ${last_7d['cost']:.4f}")
        
        # Статистика по источникам
        sources = await conn.fetch("""
            SELECT 
                metadata->>'source' as source,
                COUNT(*) as cnt,
                SUM(token_usage) as tokens,
                SUM(cost_usd) as cost
            FROM interaction_logs
            GROUP BY metadata->>'source'
            ORDER BY cnt DESC
        """)
        if sources:
            print(f"\n📊 По источникам:")
            for s in sources:
                print(f"   {s['source'] or 'NULL'}: {s['cnt']} записей, {s['tokens'] or 0} токенов, ${s['cost'] or 0:.4f}")
    await pool.close()

if __name__ == '__main__':
    asyncio.run(check_finance())

