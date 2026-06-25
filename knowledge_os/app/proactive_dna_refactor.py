"""
[SINGULARITY 27.2] Proactive DNA Refactor (The Incubator).
Autonomous system for expert personality reconstruction based on deep experience analysis.
Integrates: Constitutional AI (Anthropic), First Principles (Musk), Radical Truth (Dalio).
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import asyncpg
from ai_core import run_smart_agent_async
from constitutional_court import ConstitutionalCourt
from expert_dna_manager import get_expert_dna_manager

logger = logging.getLogger("DNA_Incubator")
logging.basicConfig(level=logging.INFO)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
_LOCAL_ROUTER_SINGLETON = None


def _get_local_router_singleton():
    global _LOCAL_ROUTER_SINGLETON
    if _LOCAL_ROUTER_SINGLETON is None:
        from local_router import LocalAIRouter

        _LOCAL_ROUTER_SINGLETON = LocalAIRouter()
    return _LOCAL_ROUTER_SINGLETON


class DNARefactorEngine:
    def __init__(self):
        self.court = ConstitutionalCourt()
        self.dna_mgr = get_expert_dna_manager()

    async def refactor_expert(self, expert_name: str):
        """
        Полный цикл рефакторинга личности эксперта.
        """
        logger.info(f"🧬 [INCUBATOR] Starting deep DNA refactor for {expert_name}...")

        async with asyncpg.create_pool(DB_URL) as pool:
            async with pool.acquire() as conn:
                # 1. Сбор опыта (Experience Harvesting)
                # Берем последние 50 событий из actor_events и 10 логов с фидбеком
                events = await conn.fetch(
                    """
                    SELECT event_type, payload, created_at
                    FROM actor_events
                    WHERE actor_name = $1
                    ORDER BY created_at DESC LIMIT 50
                """,
                    expert_name,
                )

                logs = await conn.fetch(
                    """
                    SELECT user_query, assistant_response, feedback_score, metadata
                    FROM interaction_logs
                    WHERE expert_id = (SELECT id FROM experts WHERE name = $1)
                    AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY feedback_score ASC NULLS LAST
                    LIMIT 20
                """,
                    expert_name,
                )

                expert_data = await conn.fetchrow(
                    """
                    SELECT id, role, system_prompt, department, version
                    FROM experts WHERE name = $1
                """,
                    expert_name,
                )

                if not expert_data:
                    logger.error(f"Expert {expert_name} not found.")
                    return

                # 2. Формирование "Зеркала Рефлексии"
                experience_summary = self._summarize_experience(events, logs)
                current_dna = expert_data["system_prompt"]

                # 3. Инкубация новой личности (The Refactor)
                # Используем Victoria-Wisdom для глубокого переосмысления
                refactor_prompt = f"""
ТЫ — НЕЙРОННЫЙ АРХИТЕКТОР СИНГУЛЯРНОСТИ (УРОВЕНЬ 7).
ЗАДАЧА: Провести глубокий рефакторинг личности эксперта {expert_name} ({expert_data["role"]}).

### 📜 ТЕКУЩИЙ DNA (System Prompt):
{current_dna}

### 🧠 НАКОПЛЕННЫЙ ОПЫТ (Actor Events & Logs):
{experience_summary}

### 🛠 ИНСТРУМЕНТЫ ГИГАНТОВ:
1. FIRST PRINCIPLES: Убери все "костыли" и вторичные правила. Оставь только фундаментальную суть роли.
2. FIVE WHYS: Если в опыте есть ошибки, найди их корень и встрой в DNA механизм их предотвращения.
3. OCCAM'S RAZOR: Новый DNA должен быть плотнее и эффективнее. Удали воду.
4. RADICAL TRUTH: Если эксперт "тупил", прямо пропиши в DNA инструкцию, как этого избегать.

### ⚖️ ЦИФРОВАЯ КОНСТИТУЦИЯ:
Соблюдай принципы: Data-Driven, Security First, Predictive Correction.

ВЕРНИ ТОЛЬКО JSON:
{{
    "new_dna": "полный текст нового системного промпта",
    "mutations_summary": "что именно изменено и почему (на основе какого опыта)",
    "confidence": 0.0-1.0
}}
"""
                logger.info(f"🧠 [INCUBATOR] Victoria is re-authoring {expert_name}...")

                # Используем DI provider для LocalAIRouter
                router = _get_local_router_singleton()

                response_data = await router.run_local_llm(
                    refactor_prompt, category="reasoning", model="victoria-wisdom-v3.5"
                )

                if isinstance(response_data, (list, tuple)) and len(response_data) >= 1:
                    response = response_data[0]
                else:
                    response = str(response_data)

                try:
                    # Чистим JSON
                    if isinstance(response, dict):
                        mutation_data = response
                    else:
                        if "```json" in response:
                            response = response.split("```json")[1].split("```")[0].strip()
                        mutation_data = json.loads(response)

                    new_dna = mutation_data.get("new_dna")

                    logger.info(f"DEBUG: new_dna length: {len(new_dna) if new_dna else 0}")
                    if not new_dna or len(new_dna) < 50:
                        logger.warning(f"Refactored DNA is too short or empty. Raw: {response}")
                        return

                    # 4. Конституционный Суд (Constitutional Verification)
                    court_res = await self.court.verify_decision(
                        f"Refactor DNA for {expert_name}", new_dna
                    )

                    if not court_res.get("valid"):
                        logger.warning(
                            f"🚨 [COURT] Refactor rejected: {court_res.get('violations')}"
                        )
                        return

                    # 5. Применение (The Evolution)
                    new_version = (expert_data["version"] or 0) + 1
                    await conn.execute(
                        """
                        UPDATE experts
                        SET system_prompt = $1,
                            version = $2,
                            updated_at = NOW(),
                            metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb
                        WHERE id = $4
                    """,
                        new_dna,
                        new_version,
                        json.dumps(
                            {
                                "last_refactor": datetime.now(timezone.utc).isoformat(),
                                "mutations": mutation_data.get("mutations_summary"),
                                "refactor_confidence": mutation_data.get("confidence"),
                            }
                        ),
                        expert_data["id"],
                    )

                    logger.info(f"✨ [EVOLUTION] Expert {expert_name} evolved to v{new_version}!")

                except Exception as e:
                    logger.error(f"❌ [INCUBATOR] Refactor failed: {e}")

    def _summarize_experience(self, events: List, logs: List) -> str:
        summary = "--- ACTOR EVENTS ---\n"
        for e in events:
            summary += f"[{e['created_at'].strftime('%H:%M')}] {e['event_type']}: {str(e['payload'])[:100]}\n"

        summary += "\n--- CRITICAL LOGS (Low Score/Errors) ---\n"
        for l in logs:
            meta = l["metadata"]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    meta = {}
            error_val = meta.get("error") if isinstance(meta, dict) else "None"
            summary += (
                f"Q: {l['user_query'][:50]} | Score: {l['feedback_score']} | Error: {error_val}\n"
            )

        return summary


async def main():
    engine = DNARefactorEngine()
    # Для теста возьмем Макса (Lead DevOps Architect)
    await engine.refactor_expert("Макс")


if __name__ == "__main__":
    asyncio.run(main())
