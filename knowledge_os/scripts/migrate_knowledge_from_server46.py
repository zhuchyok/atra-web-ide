#!/usr/bin/env python3
"""
Миграция узлов знаний с сервера 46
Подключается к базе на сервере 46 и мигрирует недостающие узлы
"""
import asyncio
import os
import sys
import asyncpg
from datetime import datetime
from typing import List, Dict, Any
import json

# Добавляем пути
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../knowledge_os'))

# Настройки подключения
# После миграции всё в локальной БД; источник только если нужен повторный подтяг (SERVER_46_HOST=...)
SERVER_46_HOST = os.getenv('SERVER_46_HOST', 'localhost')
SERVER_46_PORT = int(os.getenv('SERVER_46_PORT', '5432'))
SERVER_46_USER = os.getenv('SERVER_46_USER', 'admin')
SERVER_46_PASSWORD = os.getenv('SERVER_46_PASSWORD', 'secret')
SERVER_46_DB = os.getenv('SERVER_46_DB', 'knowledge_os')

LOCAL_DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

async def get_server46_connection():
    """Подключиться к базе на сервере 46"""
    try:
        conn = await asyncpg.connect(
            host=SERVER_46_HOST,
            port=SERVER_46_PORT,
            user=SERVER_46_USER,
            password=SERVER_46_PASSWORD,
            database=SERVER_46_DB,
            timeout=10
        )
        print(f"✅ Подключено к серверу 46: {SERVER_46_HOST}:{SERVER_46_PORT}")
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к серверу 46: {e}")
        return None

async def get_local_connection():
    """Подключиться к локальной базе"""
    try:
        conn = await asyncpg.connect(LOCAL_DB_URL)
        print(f"✅ Подключено к локальной базе")
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к локальной базе: {e}")
        return None

async def get_existing_node_ids(local_conn):
    """Получить ID всех существующих узлов в локальной базе"""
    rows = await local_conn.fetch("SELECT id FROM knowledge_nodes")
    return {row['id'] for row in rows}

async def get_server46_nodes(server46_conn, limit=None):
    """Получить узлы знаний с сервера 46"""
    query = """
        SELECT 
            id, domain_id, content, embedding, metadata, 
            confidence_score, is_verified, source_ref, created_at, updated_at
        FROM knowledge_nodes
        ORDER BY created_at DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    
    rows = await server46_conn.fetch(query)
    return rows

async def get_or_create_domain(local_conn, domain_id, server46_conn):
    """Получить или создать домен в локальной базе"""
    # Получаем домен с сервера 46
    domain = await server46_conn.fetchrow(
        "SELECT id, name, description, created_at FROM domains WHERE id = $1",
        domain_id
    )
    
    if not domain:
        return None
    
    # Проверяем, существует ли домен в локальной базе
    local_domain = await local_conn.fetchrow(
        "SELECT id FROM domains WHERE name = $1",
        domain['name']
    )
    
    if local_domain:
        return local_domain['id']
    
    # Создаем домен
    new_domain_id = await local_conn.fetchval("""
        INSERT INTO domains (name, description, created_at)
        VALUES ($1, $2, $3)
        RETURNING id
    """, domain['name'], domain['description'], domain['created_at'])
    
    print(f"  ✅ Создан домен: {domain['name']}")
    return new_domain_id

async def migrate_node(local_conn, node, domain_id_map):
    """Мигрировать один узел знаний"""
    # Получаем локальный domain_id
    local_domain_id = domain_id_map.get(node['domain_id'])
    
    # Проверяем, существует ли уже узел
    existing = await local_conn.fetchrow(
        "SELECT id FROM knowledge_nodes WHERE id = $1",
        node['id']
    )
    
    if existing:
        return False  # Уже существует
    
    # Вставляем узел
    await local_conn.execute("""
        INSERT INTO knowledge_nodes (
            id, domain_id, content, embedding, metadata,
            confidence_score, is_verified, source_ref, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    """, 
        node['id'],
        local_domain_id,
        node['content'],
        node['embedding'],
        node['metadata'],
        node['confidence_score'],
        node['is_verified'],
        node['source_ref'],
        node['created_at'],
        node['updated_at']
    )
    
    return True

async def migrate_knowledge_nodes():
    """Основная функция миграции"""
    print(f"\n🚀 Начало миграции узлов знаний с сервера 46")
    print(f"   Сервер: {SERVER_46_HOST}:{SERVER_46_PORT}")
    print(f"   Время: {datetime.now()}\n")
    
    # Подключаемся
    server46_conn = await get_server46_connection()
    if not server46_conn:
        return
    
    local_conn = await get_local_connection()
    if not local_conn:
        await server46_conn.close()
        return
    
    try:
        # Получаем статистику с сервера 46
        server46_count = await server46_conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
        print(f"📊 Узлов на сервере 46: {server46_count}")
        
        # Получаем существующие узлы в локальной базе
        existing_ids = await get_existing_node_ids(local_conn)
        local_count = len(existing_ids)
        print(f"📊 Узлов в локальной базе: {local_count}")
        print(f"📊 Недостает: {server46_count - local_count}\n")
        
        # Получаем узлы с сервера 46
        print("📥 Загрузка узлов с сервера 46...")
        server46_nodes = await get_server46_nodes(server46_conn)
        print(f"   Загружено: {len(server46_nodes)} узлов\n")
        
        # Создаем маппинг доменов
        print("🏷️  Создание маппинга доменов...")
        domain_id_map = {}
        unique_domain_ids = {node['domain_id'] for node in server46_nodes if node['domain_id']}
        
        for domain_id in unique_domain_ids:
            local_domain_id = await get_or_create_domain(local_conn, domain_id, server46_conn)
            if local_domain_id:
                domain_id_map[domain_id] = local_domain_id
        
        print(f"   Обработано доменов: {len(domain_id_map)}\n")
        
        # Мигрируем узлы
        print("💾 Миграция узлов...")
        migrated_count = 0
        skipped_count = 0
        
        async with local_conn.transaction():
            for i, node in enumerate(server46_nodes):
                if node['id'] in existing_ids:
                    skipped_count += 1
                    continue
                
                migrated = await migrate_node(local_conn, node, domain_id_map)
                if migrated:
                    migrated_count += 1
                
                if (i + 1) % 100 == 0:
                    print(f"   Обработано: {i + 1}/{len(server46_nodes)} (мигрировано: {migrated_count}, пропущено: {skipped_count})")
        
        print(f"\n✅ Миграция завершена!")
        print(f"   Мигрировано: {migrated_count} узлов")
        print(f"   Пропущено (уже есть): {skipped_count} узлов")
        print(f"   Всего обработано: {len(server46_nodes)} узлов")
        
        # Финальная статистика
        final_count = await local_conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
        print(f"\n📊 Финальная статистика:")
        print(f"   Узлов в локальной базе: {final_count}")
        
    except Exception as e:
        print(f"\n❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await server46_conn.close()
        await local_conn.close()

if __name__ == "__main__":
    asyncio.run(migrate_knowledge_nodes())
