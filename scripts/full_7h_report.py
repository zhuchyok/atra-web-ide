import asyncio
import json
import asyncpg
import os
from datetime import datetime, timedelta, timezone

async def get_full_report():
    db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os')
    conn = await asyncpg.connect(db_url)

    # 1. Общая статистика за 7 часов
    seven_hours_ago = datetime.now(timezone.utc) - timedelta(hours=7)

    completed_7h = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'completed' AND completed_at > $1", seven_hours_ago)
    failed_7h = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'failed' AND updated_at > $1", seven_hours_ago)
    pending_now = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'pending'")
    in_progress_now = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'in_progress'")

    # 2. Анализ мутаций (Self-Repair)
    mutations = await conn.fetch("""
        SELECT event_type, description, created_at
        FROM evolution_log
        WHERE created_at > $1
        ORDER BY created_at DESC
    """, seven_hours_ago)

    # 3. Анализ R&D предложений на Blackboard
    try:
        from redis_manager import redis_manager
        client = await redis_manager.get_client()
        all_goals = await client.hgetall("blackboard:goals")
        rd_proposals = []
        for raw_data in all_goals.values():
            data = json.loads(raw_data)
            if data.get('metadata', {}).get('is_rd'):
                rd_proposals.append(data)
    except:
        rd_proposals = []

    # 4. Последние важные события (Trust Gate, Swarm)
    recent_events = await conn.fetch("""
        SELECT actor_name, event_type, payload, created_at
        FROM actor_events
        WHERE created_at > $1 AND event_type IN ('task_completed', 'task_failed', 'trust_gate_passed', 'adversarial_rejection', 'mutation_applied')
        ORDER BY created_at DESC LIMIT 10
    """, seven_hours_ago)

    report = {
        "stats": {
            "completed_7h": completed_7h,
            "failed_7h": failed_7h,
            "pending_now": pending_now,
            "in_progress_now": in_progress_now
        },
        "mutations": [dict(m) for m in mutations],
        "rd_proposals_count": len(rd_proposals),
        "recent_events": [{**dict(e), "created_at": e['created_at'].isoformat()} for e in recent_events]
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))
    await conn.close()

if __name__ == "__main__":
    asyncio.run(get_full_report())
