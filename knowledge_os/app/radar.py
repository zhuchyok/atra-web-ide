import asyncio
import json
import os
from datetime import datetime, timezone

import asyncpg


async def detect_anomalies():
    print("📡 Monitoring Knowledge Radar for Anomalies...")
    pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
    )

    async with pool.acquire() as conn:
        # 1. Ищем новые знания за последние 24 часа
        new_nodes = await conn.fetch("""
            SELECT id, content, domain_id, metadata
            FROM knowledge_nodes
            WHERE created_at > NOW() - INTERVAL '24 hours'
            AND metadata->>'source' = 'web_research'
        """)

        for node in new_nodes:
            # Сравниваем с историческими данными в том же домене
            historical_context = await conn.fetchval(
                """
                SELECT string_agg(content, ' | ')
                FROM (
                    SELECT content FROM knowledge_nodes
                    WHERE domain_id = $1 AND id != $2
                    ORDER BY created_at DESC LIMIT 5
                ) sub
            """,
                node["domain_id"],
                node["id"],
            )

            if historical_context:
                # В идеале здесь мы бы использовали LLM для сравнения на противоречия.
                # Пока сделаем упрощенную логику: если в новом знании есть слова "breaking", "urgent", "change",
                # или если оно значительно отличается по смыслу (заглушка).

                trigger_words = [
                    "change",
                    "deprecated",
                    "critical",
                    "new standard",
                    "shift",
                    "crash",
                ]
                found_triggers = [w for w in trigger_words if w in node["content"].lower()]

                if found_triggers:
                    description = f"Potential Anomaly in {node['domain_id']}: New info suggests significant shift ({', '.join(found_triggers)}). Content: {node['content'][:200]}..."

                    # Сохраняем аномалию
                    await conn.execute(
                        """
                        INSERT INTO anomalies (description, severity)
                        VALUES ($1, $2)
                    """,
                        description,
                        "high" if "critical" in found_triggers else "medium",
                    )

                    print(f"⚠️ Anomaly detected: {description}")

                    # Отправка в Телеграм (через таблицу notifications, которую обрабатывает gateway)
                    await conn.execute(
                        """
                        INSERT INTO notifications (message, type)
                        VALUES ($1, 'anomaly_alert')
                    """,
                        f"🚨 RADAR ALERT: {description}",
                    )

    print("✅ Radar scan completed.")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(detect_anomalies())
