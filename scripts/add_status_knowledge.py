import asyncio
import asyncpg
import os
import json

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def add_knowledge_node():
    conn = await asyncpg.connect(DB_URL)

    content = """Как узнать статус проекта:
1. Проверьте дашборд корпорации (Corporation Dashboard, порт 8501).
2. Изучите актуальный список задач в базе данных Knowledge OS (таблица tasks).
3. Обратитесь к MASTER_REFERENCE.md для понимания текущего фокуса и стратегических приоритетов.
4. Если данных недостаточно, запросите отчет у экспертов (Игорь, Роман, Дмитрий)."""

    metadata = {
        "type": "corporate_standard",
        "category": "management",
        "tags": ["status", "project", "dashboard"]
    }

    await conn.execute("""
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
        VALUES ((SELECT id FROM domains WHERE name = 'Management' LIMIT 1), $1, 1.0, $2::jsonb, true)
    """, content, json.dumps(metadata))

    print("✅ Knowledge node for project status added.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(add_knowledge_node())
