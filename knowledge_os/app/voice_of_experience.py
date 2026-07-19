# knowledge_os/app/voice_of_experience.py
"""
[SINGULARITY 20.0] Voice of Experience.
Predictive self-correction based on historical failures and mistakes.
"""

import asyncio
import json
import logging
import os
from datetime import datetime

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


class VoiceOfExperience:
    def __init__(self):
        self.failure_keywords = [
            "error",
            "failed",
            "timeout",
            "crash",
            "broken",
            "bug",
            "issue",
            "down",
        ]

    async def get_warnings(self, task_description: str) -> str:
        """
        Analyzes the task and returns warnings based on past similar failures.
        """
        logger.info(
            f"🔍 [EXPERIENCE] Analyzing task for potential pitfalls: {task_description[:50]}..."
        )

        try:
            conn = await asyncpg.connect(DB_URL)

            # Ищем в базе знаний узлы с низким скором или помеченные как ошибки/уроки
            # Используем семантический поиск (через pgvector, если доступен, или просто по ключевым словам)
            lessons = await conn.fetch(
                """
                SELECT content, metadata
                FROM knowledge_nodes
                WHERE (content ILIKE $1 OR metadata->>'type' = 'lesson_learned' OR confidence_score < 0.5)
                AND (content ILIKE ANY($2))
                ORDER BY created_at DESC LIMIT 3
            """,
                f"%{task_description[:30]}%",
                [f"%{k}%" for k in self.failure_keywords],
            )

            await conn.close()

            if not lessons:
                return ""

            warning_text = "\n⚠️ [ГОЛОС ОПЫТА: ПРЕДУПРЕЖДЕНИЯ]\n"
            for i, lesson in enumerate(lessons):
                warning_text += f"{i + 1}. {lesson['content']}\n"

            return warning_text

        except Exception as e:
            logger.error(f"❌ [EXPERIENCE] Error retrieving experience: {e}")
            return ""

    async def log_failure(self, task_title: str, error_msg: str, context: dict = None):
        """
        Logs a new failure to the Knowledge OS as a 'Lesson Learned'.
        """
        logger.warning(f"📝 [EXPERIENCE] Logging new failure for future avoidance: {task_title}")

        try:
            conn = await asyncpg.connect(DB_URL)
            content = f"ОШИБКА В ПРОШЛОМ: При выполнении '{task_title}' возникла проблема: {error_msg}. ИЗБЕГАТЬ В БУДУЩЕМ."

            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                VALUES (
                    (SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1),
                    $1, 0.3, $2, true
                )
            """,
                content,
                json.dumps(
                    {
                        "type": "lesson_learned",
                        "original_task": task_title,
                        "error": error_msg,
                        "context": context or {},
                    }
                ),
            )

            await conn.close()
            logger.info("✅ [EXPERIENCE] Failure logged successfully.")
        except Exception as e:
            logger.error(f"❌ [EXPERIENCE] Error logging failure: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test():
        exp = VoiceOfExperience()
        # Тестовый лог ошибки
        await exp.log_failure("Update Docker Tunnels", "SSH Connection timed out on port 5900")
        # Тестовый запрос предупреждения
        warn = await exp.get_warnings("Restarting tunnels for VNC")
        print(warn)

    asyncio.run(test())
