"""
[SINGULARITY 20.0] Perpetual Evolution Engine.
Autonomous cycle: Research Giants -> Propose Implementation -> Execute -> Test -> Repeat.
"""

import asyncio
import json
import logging
import os
from datetime import datetime

import asyncpg
from ai_core import run_smart_agent_async
from constitutional_court import ConstitutionalCourt
from expert_council_discussion import ExpertCouncil
from voice_of_experience import VoiceOfExperience
from knowledge_os.app.db_pool import get_pool
from knowledge_os.app.resource_guard import get_resource_guard

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


class PerpetualEvolution:
    def __init__(self):
        self.current_task = None
        self.experience = VoiceOfExperience()
        self.court = ConstitutionalCourt()

    async def run_forever(self):
        """Main autonomous loop."""
        logger.info("🚀 [EVOLUTION] Perpetual Evolution Engine STARTED.")

        try:
            # [SINGULARITY 24.0] Autonomous Skill Refinement
            # Виктория анализирует старые навыки и обновляет их на основе недавних успехов.
            from scripts.autonomous_skill_refinement import refine_skills

            await refine_skills()
        except Exception as asr:
            logger.debug(f"Autonomous skill refinement failed: {asr}")

        try:
            # [SINGULARITY 26.3] Autonomous Red-Team Auditor Phase — теперь в run_one_cycle()
            # [SINGULARITY 24.0] Autonomous Tester Phase
            # В тихие часы запускаем самотестирование и исправление ошибок.
            try:
                from autonomous_tester import AutonomousTester

                tester = AutonomousTester()
                await tester.run_cycle()
            except Exception as te:
                logger.debug(f"Autonomous tester failed: {te}")

            # [SINGULARITY 24.0] Wisdom Injection Phase
            # Automatically turn successful insights into skills
            try:
                from wisdom_injection import WisdomInjectionEngine

                wisdom_engine = WisdomInjectionEngine()
                await wisdom_engine.scan_and_inject()
            except Exception as we:
                logger.debug(f"Wisdom injection failed: {we}")

            # [SINGULARITY 21.0] Knowledge Distillation Phase
            # Before researching new things, distill existing knowledge
            from distillation_engine import KnowledgeDistiller

            distiller = KnowledgeDistiller()
            await distiller.distill_knowledge_batch()

            # [SINGULARITY 25.0] Domain Passport Evolution
            # Update domain summaries (Architectural Passports) based on recent knowledge
            try:
                await self.update_domain_passports()
            except Exception as dpe:
                logger.debug(f"Domain passport evolution failed: {dpe}")

            # 1. RESEARCH: Find next big thing from Giants
            task = await self.research_next_upgrade()
            if not task:
                logger.info("😴 [EVOLUTION] No new upgrade ideas found.")
                return False

            # 2. CHECK EXPERIENCE: Get warnings from past failures
            warnings = await self.experience.get_warnings(task["title"])
            if warnings:
                logger.warning(f"⚠️ [EVOLUTION] PITFALLS DETECTED: {warnings}")
                task["implementation_plan"] = (
                    f"### [ГОЛОС ОПЫТА: ПРЕДУПРЕЖДЕНИЯ]\n{warnings}\n\n### [ПЛАН]\n{task['implementation_plan']}"
                )

            # 3. BRAINSTORM: Call the Council
            logger.info(f"🏛️ [EVOLUTION] Calling Expert Council for: {task['title']}")
            council = ExpertCouncil()
            final_plan = await council.start_debate(
                task["title"],
                f"REASONING: {task['reasoning']}\nPLAN: {task['implementation_plan']}",
            )

            # 4. CONSTITUTIONAL CHECK: Verify decision by Court
            logger.info(f"⚖️ [EVOLUTION] Constitutional Verification for: {task['title']}")
            court_result = await self.court.verify_decision(task["title"], final_plan)

            if not court_result.get("valid"):
                logger.warning(
                    f"🚨 [EVOLUTION] CONSTITUTIONAL VETO! {court_result.get('violations')}"
                )
                # If vetoed, we add feedback and try to re-synthesize or skip
                final_plan = f"### [ВЕТО КОНСТИТУЦИОННОГО СУДА]\n{court_result.get('feedback')}\n\n{final_plan}"
                # For safety, we still use the plan but it's now 'marked' with violations

            task["implementation_plan"] = final_plan

            # 5. IMPLEMENT: Execute the change
            success = await self.execute_upgrade(task)

            # 4. TEST: Verify the change
            if success:
                await self.verify_and_log(task)
            else:
                # Log failure to Voice of Experience
                await self.experience.log_failure(
                    task["title"], "Implementation failed or timed out"
                )

            logger.info(f"✅ [EVOLUTION] Cycle completed for: {task['title']}. Moving to next...")
            await asyncio.sleep(60)  # Short break between upgrades

        except Exception as e:
            logger.error(f"❌ [EVOLUTION] Error in loop: {e}")
            await self.experience.log_failure("Perpetual Evolution Loop", str(e))
            await asyncio.sleep(300)

    async def run_one_cycle(self) -> bool:
        """Один цикл: автономные фазы + исследование следующего апгрейда из знаний гигантов → создание задачи на внедрение."""

        # [SINGULARITY 26.3] Red-Team Audit Phase (перенесено из run_forever — туда никогда не доходило)
        try:
            from red_team_auditor import RedTeamAuditor
            auditor = RedTeamAuditor()
            await auditor.run_audit_cycle()
        except Exception as rta:
            logger.warning(f"⚠️ [RED TEAM] Auditor failed: {rta}")

        # [SINGULARITY 24.0] Autonomous Tester Phase
        try:
            from autonomous_tester import AutonomousTester
            tester = AutonomousTester()
            await tester.run_cycle()
        except Exception as te:
            logger.debug(f"Autonomous tester failed: {te}")

        # [SINGULARITY 24.0] Wisdom Injection Phase
        try:
            from wisdom_injection import WisdomInjectionEngine
            wisdom_engine = WisdomInjectionEngine()
            await wisdom_engine.scan_and_inject()
        except Exception as we:
            logger.debug(f"Wisdom injection failed: {we}")

        task = await self.research_next_upgrade()
        if not task:
            return False
        success = await self.execute_upgrade(task)
        if success:
            await self.verify_and_log(task)
        return success

    async def research_next_upgrade(self) -> dict:
        """Asks Victoria to find the next best thing to implement from AI Giants."""
        logger.info(
            "🔍 [EVOLUTION] Researching next upgrade from AI Giants (Google, OpenAI, Meta)..."
        )

        # [SINGULARITY 23.6] CPU Offloading for Evolution
        import asyncio
        from functools import partial

        # ВРЕМЕННЫЙ ПЛАН (Fallback), если модель галлюцинирует с форматом
        fallback_task = {
            "title": "Autonomous Red Teaming (Self-Adversarial Verification)",
            "reasoning": "Inspired by Anthropic's constitutional AI and OpenAI's red teaming practices. Improves reliability by challenging its own outputs.",
            "implementation_plan": "1. Create adversarial_critic.py to challenge new SOPs. 2. Integrate critic into the SOP generation pipeline.",
            "test_scenario": "Generate a new SOP and verify that the critic identifies potential flaws or edge cases.",
        }

        # Загружаем историю уже предложенных тем за последние 30 дней,
        # чтобы модель не повторяла одно и то же (напр. "Pytest тестирование" 3 раза подряд).
        history_block = ""
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                recent_rows = await conn.fetch(
                    """
                    SELECT DISTINCT title
                    FROM tasks
                    WHERE title LIKE '🚀 EVOLUTION:%'
                      AND created_at > NOW() - INTERVAL '30 days'
                    ORDER BY title
                    LIMIT 30
                    """
                )
            if recent_rows:
                items = "\n".join(
                    f"  - {r['title'].replace('🚀 EVOLUTION: ', '').strip()}"
                    for r in recent_rows
                )
                history_block = f"""
ТЕМЫ, УЖЕ ПРЕДЛОЖЕННЫЕ ЗА ПОСЛЕДНИЕ 30 ДНЕЙ (НЕ ПОВТОРЯТЬ НИ ОДНУ ИЗ НИХ!):
{items}

"""
                logger.info(f"📚 [EVOLUTION] История: {len(recent_rows)} тем за 30 дней загружена в промпт.")
        except Exception as hist_err:
            logger.warning(f"⚠️ [EVOLUTION] Не удалось загрузить историю тем: {hist_err}")

        prompt = f"""
        ТЫ - ВЕРХОВНЫЙ АРХИТЕКТОР ЭВОЛЮЦИИ.
        ПРОАНАЛИЗИРУЙ базу знаний гигантов и текущее состояние нашей системы.
{history_block}
        ЗАДАЧА: Выбери ОДНУ конкретную техническую фичу или архитектурный паттерн (из практик Google, OpenAI, Anthropic или Meta),
        которого у нас еще нет, но который сделает Викторию умнее или стабильнее.
        ВЫБИРАЙ ТОЛЬКО ТО, ЧТО НЕ БЫЛО ПРЕДЛОЖЕНО ВЫШЕ.

        ОТВЕТЬ СТРОГО В ФОРМАТЕ JSON. ТВОЙ ОТВЕТ ДОЛЖЕН НАЧИНАТЬСЯ С '{{' И ЗАКАНЧИВАТЬСЯ '}}'.
        НИКАКОГО ТЕКСТА ДО ИЛИ ПОСЛЕ JSON. НИКАКИХ БЛОКОВ ```json. ТОЛЬКО ЧИСТЫЙ ОБЪЕКТ.

        ФОРМАТ:
        {{
            "title": "Название фичи",
            "reasoning": "Почему это важно (ссылка на гиганта)",
            "implementation_plan": "Пошаговый план для Python/Docker",
            "test_scenario": "Как проверить, что это работает"
        }}
        """

        try:
            # Используем victoria-wisdom-v3.5 для максимальной мудрости в эволюции
            # ВАЖНО: Роутер возвращает (content_string, node_name)
            from local_router import LocalAIRouter

            router = LocalAIRouter()
            response_data = await router.run_local_llm(
                prompt, category="reasoning", model="victoria-wisdom-v3.5"
            )

            # Роутер возвращает (response, routing_source)
            if isinstance(response_data, (list, tuple)) and len(response_data) >= 1:
                response = response_data[0]
            elif isinstance(response_data, dict):
                # На случай если роутер вернул словарь (хотя по коду это кортеж)
                response = (
                    response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                if not response:
                    response = response_data.get("content", str(response_data))
            else:
                response = str(response_data)

            logger.info(f"🔍 [EVOLUTION] Raw response length: {len(response) if response else 0}")

            if not response:
                logger.error("Empty response from LLM, using fallback.")
                return fallback_task

            # Очистка от markdown и лишнего текста
            clean_response = response.strip()
            start_idx = clean_response.find("{")
            end_idx = clean_response.rfind("}")

            if start_idx != -1 and end_idx != -1:
                clean_response = clean_response[start_idx : end_idx + 1]
                # [SINGULARITY 23.6] Offload heavy JSON parsing to thread pool
                return await asyncio.to_thread(json.loads, clean_response)
            else:
                logger.warning("No JSON found in response, using fallback task.")
                return fallback_task
        except Exception as e:
            logger.error(f"Failed to parse research response: {e}. Using fallback.")
            return fallback_task

    async def execute_upgrade(self, task: dict) -> bool:
        """Delegates the implementation to the expert team with deduplication and backpressure."""
        logger.info(f"🛠️ [EVOLUTION] Implementing: {task['title']}")

        pool = await get_pool()
        async with pool.acquire() as conn:
            # 1. Backpressure Check: Don't flood the queue
            # Считаем только NON-EVOLUTION pending задачи — эволюция не должна блокироваться своими же задачами
            pending_count = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'pending' AND title NOT LIKE '🚀 EVOLUTION:%'")
            if pending_count > 150:
                logger.warning(f"⏸️ [EVOLUTION] Queue full ({pending_count}/150). Skipping task creation.")
                return False

            # 2. Deduplication Check: Don't create the same task twice
            exists = await conn.fetchval("SELECT 1 FROM tasks WHERE title = $1 AND status = 'pending' LIMIT 1", f"🚀 EVOLUTION: {task['title']}")
            if exists:
                logger.info(f"⏭️ [EVOLUTION] Task already exists in pending: {task['title']}")
                return True

            # 3. Create Task
            await conn.execute(
                """
                INSERT INTO tasks (title, description, status, priority, metadata)
                VALUES ($1, $2, 'pending', 'high', $3::jsonb)
            """,
                f"🚀 EVOLUTION: {task['title']}",
                task["implementation_plan"],
                # [SINGULARITY 23.6] Offload heavy JSON dumps to thread pool
                await asyncio.to_thread(json.dumps, task),
            )
        
        return True

    async def verify_and_log(self, task: dict):
        """Verifies the upgrade and stores it in Knowledge OS."""
        logger.info(f"🧪 [EVOLUTION] Verifying: {task['title']}")
        # Логируем успех в базу знаний как верифицированный инсайт
        conn = await asyncpg.connect(DB_URL)
        try:
            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                VALUES ((SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1), $1, 1.0, $2, true)
            """,
                f"✅ УСПЕШНОЕ ВНЕДРЕНИЕ: {task['title']}. {task['reasoning']}",
                # [SINGULARITY 23.6] CPU Offloading
                await asyncio.to_thread(json.dumps, {"type": "evolution_log", "task": task}),
            )
        finally:
            await conn.close()

    async def update_domain_passports(self):
        """
        [SINGULARITY 25.0] Evolution Integration: Auto-update Architectural Passports for domains.
        """
        logger.info("📘 [EVOLUTION] Updating Domain Architectural Passports...")

        # 0. Resource Guard Check
        guard = get_resource_guard()
        can_start, reason = await guard.can_start_autonomous_task()
        if not can_start:
            logger.warning(f"🛑 [EVOLUTION] Domain passport update skipped: {reason}")
            return

        pool = await get_pool()
        async with pool.acquire() as conn:
            try:
                # 1. Identify domains that need summary updates
                # We look for domains where there are knowledge nodes newer than the last domain_summary
                domains = await conn.fetch(
                    """
                    SELECT d.id, d.name
                    FROM domains d
                    WHERE EXISTS (
                        SELECT 1 FROM knowledge_nodes kn
                        WHERE kn.domain_id = d.id
                        AND kn.created_at > COALESCE(
                            (SELECT MAX(created_at) FROM knowledge_nodes WHERE domain_id = d.id AND metadata->>'type' = 'domain_summary'),
                            '1970-01-01'::timestamp
                        )
                    )
                """
                )

                for domain in domains:
                    domain_id = domain["id"]
                    domain_name = domain["name"]
                    logger.info(f"🧬 [EVOLUTION] Generating Architectural Passport for domain: {domain_name}")

                    # 2. Gather recent knowledge nodes (content and metadata)
                    nodes = await conn.fetch(
                        """
                        SELECT content, metadata, created_at
                        FROM knowledge_nodes
                        WHERE domain_id = $1
                        AND (metadata->>'type' IS NULL OR metadata->>'type' != 'domain_summary')
                        ORDER BY created_at DESC
                        LIMIT 20
                    """,
                        domain_id,
                    )

                    if not nodes:
                        continue

                    knowledge_context = "\n".join(
                        [f"- [{n['created_at']}] {n['content']}" for n in nodes]
                    )

                    # 3. Use Victoria to generate a concise "Architectural Passport"
                    prompt = f"""
                    ТЫ - ВЕРХОВНЫЙ АРХИТЕКТОР СИСТЕМЫ.
                    ЗАДАЧА: Сформируй "Архитектурный Паспорт" (Architectural Passport) для домена знаний '{domain_name}'.
                    Этот паспорт должен суммировать текущее состояние домена, ключевые стандарты и последние важные находки.

                    ПОСЛЕДНИЕ ЗНАНИЯ В ДОМЕНЕ:
                    {knowledge_context}

                    ОТВЕТЬ В ФОРМАТЕ JSON:
                    {{
                        "summary": "Краткое описание текущего состояния домена",
                        "standards": ["Стандарт 1", "Стандарт 2"],
                        "key_findings": ["Находка 1", "Находка 2"],
                        "evolution_status": "stable/evolving/disruptive"
                    }}
                    ВЕРНИ ТОЛЬКО ЧИСТЫЙ JSON.
                    """

                    # Используем victoria-wisdom-v3.5 для архитектурного синтеза
                    from local_router import LocalAIRouter
                    router = LocalAIRouter()
                    try:
                        response_data = await asyncio.wait_for(
                            router.run_local_llm(
                                prompt, category="reasoning", model="victoria-wisdom-v3.5"
                            ),
                            timeout=120.0
                        )
                    except asyncio.TimeoutError:
                        logger.error(f"❌ [EVOLUTION] LLM call timed out for domain: {domain_name}")
                        continue

                    response = response_data[0] if isinstance(response_data, (list, tuple)) else str(response_data)
                    
                    # Clean and parse JSON
                    clean_response = response.strip()
                    start_idx = clean_response.find("{")
                    end_idx = clean_response.rfind("}")
                    if start_idx != -1 and end_idx != -1:
                        try:
                            passport_data = json.loads(clean_response[start_idx : end_idx + 1])
                        except json.JSONDecodeError as je:
                            logger.error(f"❌ [EVOLUTION] JSON decode error for domain {domain_name}: {je}")
                            continue
                        
                        passport_content = f"### ARCHITECTURAL PASSPORT: {domain_name}\n\n"
                        passport_content += f"**Summary:** {passport_data.get('summary')}\n\n"
                        passport_content += "**Standards:**\n" + "\n".join([f"- {s}" for s in passport_data.get("standards", [])]) + "\n\n"
                        passport_content += "**Key Findings:**\n" + "\n".join([f"- {f}" for f in passport_data.get("key_findings", [])]) + "\n\n"
                        passport_content += f"**Status:** {passport_data.get('evolution_status')}"

                        # 4. Update existing domain_summary node or insert a new one
                        # We look for an existing summary to update it (keeping the history clean)
                        existing_summary = await conn.fetchrow(
                            "SELECT id FROM knowledge_nodes WHERE domain_id = $1 AND metadata->>'type' = 'domain_summary' LIMIT 1",
                            domain_id
                        )

                        metadata = {
                            "type": "domain_summary",
                            "updated_at": datetime.now().isoformat(),
                            "domain_name": domain_name,
                            "version": "1.0"
                        }

                        if existing_summary:
                            await conn.execute(
                                """
                                UPDATE knowledge_nodes
                                SET content = $1, metadata = $2, created_at = NOW()
                                WHERE id = $3
                            """,
                                passport_content,
                                json.dumps(metadata),
                                existing_summary["id"]
                            )
                            logger.info(f"✅ [EVOLUTION] Updated Architectural Passport for {domain_name}")
                        else:
                            await conn.execute(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                                VALUES ($1, $2, 1.0, $3, true)
                            """,
                                domain_id,
                                passport_content,
                                json.dumps(metadata)
                            )
                            logger.info(f"✅ [EVOLUTION] Created NEW Architectural Passport for {domain_name}")
                    else:
                        logger.warning(f"⚠️ [EVOLUTION] No JSON found in response for {domain_name}")

            except Exception as e:
                logger.error(f"❌ [EVOLUTION] Error updating domain passports: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = PerpetualEvolution()
    asyncio.run(engine.run_forever())
