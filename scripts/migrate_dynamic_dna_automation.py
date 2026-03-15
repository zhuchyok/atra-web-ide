import asyncio
import asyncpg
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def migrate():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        logger.info("🚀 Starting Dynamic DNA Automation Migration...")

        # 1. Создаем таблицу для переопределений ДНК (Overrides)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS expert_dna_overrides (
                id SERIAL PRIMARY KEY,
                expert_id UUID REFERENCES experts(id) ON DELETE CASCADE,
                custom_instructions TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                version INTEGER DEFAULT 1,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_by VARCHAR(255) DEFAULT 'system'
            );
        """)
        logger.info("✅ Table 'expert_dna_overrides' created.")

        # 2. Добавляем индекс для быстрого поиска по эксперту
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expert_dna_overrides_expert_id ON expert_dna_overrides(expert_id) WHERE is_active = TRUE;
        """)
        logger.info("✅ Index created.")

        # 3. Добавляем колонку auto_dna_sync в таблицу experts для управления автоматизацией
        await conn.execute("""
            ALTER TABLE experts ADD COLUMN IF NOT EXISTS auto_dna_sync BOOLEAN DEFAULT TRUE;
            ALTER TABLE experts ADD COLUMN IF NOT EXISTS last_dna_sync TIMESTAMP WITH TIME ZONE;
        """)
        logger.info("✅ Experts table updated with automation flags.")

        # 4. Вставляем начальное переопределение для Михаила Гребенюка (пример автоматизации)
        grebenyuk_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Михаил'")
        if grebenyuk_id:
            await conn.execute("""
                INSERT INTO expert_dna_overrides (expert_id, custom_instructions, updated_by)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING;
            """, grebenyuk_id, "### ⚡️ DYNAMIC OVERRIDE: Focus on 100% automation of all manual processes. If you see a manual step - propose a script to automate it.", "Victoria_TL")
            logger.info(f"✅ Initial dynamic DNA injected for expert ID: {grebenyuk_id}")

        logger.info("🎉 Migration COMPLETED successfully!")
    except Exception as e:
        logger.error(f"❌ Migration FAILED: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
