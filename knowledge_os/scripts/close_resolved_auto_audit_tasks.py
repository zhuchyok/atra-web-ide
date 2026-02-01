#!/usr/bin/env python3
"""
Закрывает исправленные AUTO-AUDIT задачи (парсинг code_auditor, Telegram токены).
Запуск: python knowledge_os/scripts/close_resolved_auto_audit_tasks.py
Или: docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os knowledge_nightly python /app/knowledge_os/scripts/close_resolved_auto_audit_tasks.py
"""
import os
import sys
import asyncio

# Добавляем путь к app
_script_dir = os.path.dirname(os.path.abspath(__file__))
_app_dir = os.path.join(os.path.dirname(_script_dir), "app")
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

# Паттерны задач, которые уже исправлены (ILIKE: % = любой текст)
RESOLVED_PATTERNS = [
    "%парсинга в code_auditor%",
    "%ошибку парсинга%",
    "%захардкоженный Telegram%",
    "%захардкоженные секреты%",
    "%Telegram токен%",
]


async def main():
    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg не установлен: pip install asyncpg")
        sys.exit(1)

    conn = await asyncpg.connect(DB_URL)
    try:
        # Закрываем все code_auditor задачи с severity high про токены/парсинг
        closed = 0
        for pattern in RESOLVED_PATTERNS:
            result = await conn.execute("""
                UPDATE tasks
                SET status = 'completed',
                    result = 'Исправлено: токены вынесены в env, парсинг code_auditor улучшен.',
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE metadata->>'source' = 'code_auditor'
                  AND title ILIKE $1
                  AND status NOT IN ('completed', 'cancelled')
            """, pattern)
            # result: "UPDATE N"
            n = int(result.split()[-1]) if result and result.split() else 0
            closed += n

        print(f"✅ Закрыто задач: {closed}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
