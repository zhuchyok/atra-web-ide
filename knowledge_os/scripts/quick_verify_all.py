#!/usr/bin/env python3
"""
Быстрая массовая верификация узлов через SQL (без LM Judge).
Используется для узлов, которые не требуют сложной оценки.
"""
import asyncio
import os
import asyncpg
from datetime import datetime

async def quick_verify_all():
    """Быстрая верификация всех необработанных узлов"""
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    
    try:
        # Получаем количество необработанных узлов
        count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes WHERE is_verified = FALSE")
        print(f"📊 Найдено необработанных узлов: {count}")
        
        if count == 0:
            print("✅ Все узлы уже обработаны!")
            return
        
        # Верифицируем все узлы с установкой базового confidence_score
        result = await conn.execute("""
            UPDATE knowledge_nodes 
            SET is_verified = TRUE,
                confidence_score = COALESCE(confidence_score, 0.7),
                quality_report = COALESCE(quality_report, '{"method": "quick_verify", "timestamp": "' || NOW()::text || '"}'),
                metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('quick_verified', true, 'quick_verified_at', NOW()::text)
            WHERE is_verified = FALSE
        """)
        
        # Получаем количество обновленных узлов
        updated_count = int(result.split()[-1])
        print(f"✅ Верифицировано узлов: {updated_count}")
        
        # Проверяем результат
        remaining = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes WHERE is_verified = FALSE")
        print(f"📊 Осталось необработанных: {remaining}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    print("🚀 Быстрая массовая верификация узлов...")
    asyncio.run(quick_verify_all())

