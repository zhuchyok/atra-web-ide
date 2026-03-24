import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wisdom_injection")

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


class WisdomInjectionEngine:
    """
    [SINGULARITY 24.0] Wisdom Injection Engine.
    Автоматически превращает успешные инсайты и логи эволюции в навыки (SOP).
    """

    def __init__(self):
        self.db_url = DB_URL

    async def scan_and_inject(self):
        """Сканирует новые инсайты и создает SOP для лучших из них."""
        logger.info("🔍 [WISDOM] Scanning for new injection candidates...")

        try:
            conn = await asyncpg.connect(self.db_url)
            # Ищем логи эволюции или верифицированные инсайты за последние 24 часа
            # [SINGULARITY 24.0] Filter out already injected nodes
            nodes = await conn.fetch("""
                SELECT id, content, metadata
                FROM knowledge_nodes
                WHERE is_verified = true
                AND created_at > NOW() - INTERVAL '24 hours'
                AND (metadata->>'type' = 'evolution_log' OR content ILIKE '%✅%')
                AND (metadata->>'injected_as_sop' IS NULL OR metadata->>'injected_as_sop' = 'false')
            """)

            if not nodes:
                logger.info("😴 [WISDOM] No new candidates found.")
                await conn.close()
                return

            from knowledge_os.app.skill_registry import get_skill_registry
            from knowledge_os.src.agents.tools.system_tools import SystemTools

            registry = get_skill_registry()

            for node in nodes:
                meta = node["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)

                content = node["content"]
                # Извлекаем название из контента или метаданных
                title = (
                    meta.get("task", {}).get("title")
                    or content.split("\n")[0].replace("✅", "").strip()
                )

                # Проверяем, нет ли уже такого навыка
                if registry.get_skill(title):
                    # Помечаем как уже существующий, чтобы не сканировать снова
                    await conn.execute(
                        """
                        UPDATE knowledge_nodes
                        SET metadata = metadata || '{"injected_as_sop": "exists"}'::jsonb
                        WHERE id = $1
                    """,
                        node["id"],
                    )
                    continue

                logger.info(f"💡 [WISDOM] Injecting new SOP: {title}")

                # Формируем процедуру на основе контента
                procedure = meta.get("task", {}).get("implementation_plan") or content

                # [SINGULARITY 24.0] Generate Unit Test for the new SOP
                test_scenario = (
                    meta.get("task", {}).get("test_scenario") or "Проверить логи выполнения."
                )
                try:
                    # Временно отключено из-за циклических импортов
                    # from ai_core import run_smart_agent_async
                    # test_gen_prompt = f"### ЗАДАЧА: ГЕНЕРАЦИЯ ТЕСТА ДЛЯ SOP\nНазвание: {title}\nПроцедура: {procedure}\n\nНапиши краткий, но эффективный тест-кейс или команду для проверки этого навыка."
                    # test_case = await run_smart_agent_async(test_gen_prompt, model="lfm2.5-thinking:1.2b")
                    # if test_case:
                    #    test_scenario = f"{test_scenario}\n\n### [АВТО-ТЕСТ]\n{test_case}"
                    pass
                except Exception as te:
                    logger.debug(f"Test generation failed: {te}")

                await SystemTools.generate_sop_skill(
                    name=title,
                    description=meta.get("task", {}).get("reasoning")
                    or f"Автоматически извлеченный навык из инсайта {node['id']}",
                    category=meta.get("category", "general"),
                    procedure=procedure,
                    verification=test_scenario,
                )

                # Помечаем узел как 'injected'
                await conn.execute(
                    """
                    UPDATE knowledge_nodes
                    SET metadata = metadata || '{"injected_as_sop": true}'::jsonb
                    WHERE id = $1
                """,
                    node["id"],
                )

            await conn.close()
            logger.info("✅ [WISDOM] Injection cycle completed.")

        except Exception as e:
            logger.error(f"❌ [WISDOM] Injection failed: {e}")


if __name__ == "__main__":
    engine = WisdomInjectionEngine()
    asyncio.run(engine.scan_and_inject())
