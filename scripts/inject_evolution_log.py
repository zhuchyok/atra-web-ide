import asyncio
import asyncpg
import os
import json

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def inject_evolution_log():
    conn = await asyncpg.connect(DB_URL)

    content = "✅ УСПЕШНОЕ ВНЕДРЕНИЕ: Singularity 24.0 Speed & Intelligence. Внедрен Semantic Router, Rocket Speed RAG Cache и Pulse Warmup."
    metadata = {
        "type": "evolution_log",
        "category": "performance",
        "task": {
            "title": "Singularity 24.0 Speed & Intelligence",
            "reasoning": "Глобальное ускорение и интеллектуализация всех каналов связи для экономии токенов и времени.",
            "implementation_plan": "1. Внедрить SemanticRouter для классификации.\n2. Оптимизировать RAG кэш в Redis.\n3. Добавить Pulse Warmup для Metal.\n4. Внедрить Lean Identity (SOUL/USER).",
            "test_scenario": "Запустить стресс-тест и проверить время отклика и корректность стриминга."
        }
    }

    await conn.execute("""
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
        VALUES ((SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1), $1, 1.0, $2::jsonb, true)
    """, content, json.dumps(metadata))

    print("✅ Evolution log injected into knowledge_nodes.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(inject_evolution_log())
