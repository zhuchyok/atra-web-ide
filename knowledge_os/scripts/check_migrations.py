#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка статуса миграций"""

import asyncio
import asyncpg
import getpass
import os

USER_NAME = getpass.getuser()
db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

async def check():
    conn = await asyncpg.connect(db_url)
    try:
        count = await conn.fetchval('SELECT COUNT(*) FROM schema_migrations')
        print(f'✅ Применено миграций: {count}')
        
        # Проверяем критичные таблицы Singularity 8.0
        tables = [
            'semantic_ai_cache',
            'embedding_cache',
            'ml_routing_training_data',
            'session_context',
            'user_feedback',
            'rate_limits',
            'encrypted_secrets',
            'user_analytics',
            'expert_analytics',
            'model_analytics'
        ]
        
        print('\n📊 Проверка критичных таблиц:')
        for table in tables:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = $1
                )
            """, table)
            status = '✅' if exists else '❌'
            print(f'  {status} {table}')
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(check())

