import asyncio
import json
import os
from datetime import datetime, timedelta

import asyncpg
import redis.asyncio as redis
from resource_manager import acquire_resource_lock

# Импорт LocalAIRouter для использования локальных моделей (MLX/Ollama)
try:
    from local_router import LocalAIRouter

    LOCAL_ROUTER_AVAILABLE = True
except ImportError:
    LocalAIRouter = None
    LOCAL_ROUTER_AVAILABLE = False
    print("⚠️ LocalAIRouter недоступен, оркестратор будет использовать fallback")

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


async def run_local_llm(prompt: str, category: str = "reasoning"):
    """
    Запуск локальной LLM модели через LocalAIRouter
    Использует актуальные модели с Mac Studio:
    - MLX: qwen2.5-coder:32b (coding), phi3.5:3.8b (reasoning/fast)
    - Ollama: qwen2.5-coder:32b / qwq:32b (coding/reasoning), phi3.5:3.8b (fast)
    """
    if not LOCAL_ROUTER_AVAILABLE or not LocalAIRouter:
        print("⚠️ LocalAIRouter недоступен")
        return None

    try:
        router = LocalAIRouter()
        # Используем category для выбора оптимальной модели
        # reasoning → qwq:32b / phi3.5:3.8b
        # coding → qwen2.5-coder:32b
        result = await router.run_local_llm(prompt, category=category)

        if isinstance(result, tuple):
            response, _ = result
        else:
            response = result

        if response and len(response.strip()) > 10:
            print(f"✅ [ORCHESTRATOR] Использована локальная модель (category: {category})")
            return response.strip()
        else:
            print("⚠️ [ORCHESTRATOR] Локальная модель вернула пустой ответ")
            return None
    except Exception as e:
        print(f"❌ [ORCHESTRATOR] Ошибка локальной модели: {e}")
        return None


async def run_orchestration_cycle():
    async with acquire_resource_lock("orchestrator"):
        print(
            f"[{datetime.now()}] 🚀 SINGULARITY ORCHESTRATOR v3.0 (Hierarchical + Associative) starting..."
        )
        conn = await asyncpg.connect(DB_URL)
        rd = await redis.from_url(REDIS_URL, decode_responses=True)

        # 1. Сбор данных: Новые знания
        new_knowledge = await conn.fetch("""
            SELECT k.id, k.content, d.name as domain, k.metadata, k.domain_id
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.created_at > NOW() - INTERVAL '6 hours'
            AND (k.metadata->>'orchestrated' IS NULL OR k.metadata->>'orchestrated' = 'false')
        """)

        # 2. Сбор данных: Директора отделов (для иерархии)
        directors = await conn.fetch("""
            SELECT id, name, department FROM experts
            WHERE role ILIKE '%Head%' OR role ILIKE '%Lead%' OR role ILIKE '%Director%'
        """)

        victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")

        # --- ФАЗА 1: АССОЦИАТИВНЫЙ МОЗГ (CROSS-DOMAIN LINKING) ---
        if new_knowledge:
            for node in new_knowledge:
                print(f"🧩 Linking insight: {node['content'][:50]}...")

                # Случайный поиск из другого домена для ассоциации
                random_node = await conn.fetchrow(
                    """
                    SELECT k.content, d.name as domain
                    FROM knowledge_nodes k JOIN domains d ON k.domain_id = d.id
                    WHERE k.domain_id != $1 ORDER BY RANDOM() LIMIT 1
                """,
                    node["domain_id"],
                )

                if random_node:
                    link_prompt = f"""
                    Вы - Виктория (Team Lead). Найдите неочевидную связь между двумя фактами из разных отделов:
                    ФАКТ А ({node["domain"]}): {node["content"]}
                    ФАКТ Б ({random_node["domain"]}): {random_node["content"]}

                    ЗАДАЧА: Сформулируйте одну инновационную гипотезу (Synthetic Hypothesis) на стыке этих знаний.
                    Верните ТОЛЬКО текст гипотезы.
                    """
                    # Используем LocalAIRouter с category="reasoning" для выбора оптимальной модели
                    hypothesis = await run_local_llm(link_prompt, category="reasoning")
                    if hypothesis:
                        content_kn = f"🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: {hypothesis}"
                        meta_kn = json.dumps(
                            {"source": "cross_domain_linker", "parents": [str(node["id"])]}
                        )
                        embedding = None
                        try:
                            from semantic_cache import get_embedding

                            embedding = await get_embedding(content_kn[:8000])
                        except Exception:
                            pass
                        if embedding is not None:
                            kn_id = await conn.fetchval(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                                VALUES ($1, $2, 0.95, $3, true, $4::vector)
                                RETURNING id
                            """,
                                node["domain_id"],
                                content_kn,
                                meta_kn,
                                str(embedding),
                            )
                        else:
                            kn_id = await conn.fetchval(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                                VALUES ($1, $2, 0.95, $3, true)
                                RETURNING id
                            """,
                                node["domain_id"],
                                content_kn,
                                meta_kn,
                            )

                        # Публикация в Redis Stream для мгновенной реакции других агентов
                        await rd.xadd(
                            "knowledge_stream", {"type": "synthetic_link", "content": hypothesis}
                        )

                        # Отправка гипотезы в дебаты для обсуждения экспертами
                        try:
                            from nightly_learner import create_debate_for_hypothesis

                            await create_debate_for_hypothesis(
                                conn,
                                kn_id,
                                f"🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: {hypothesis}",
                                node["domain_id"],
                            )
                        except Exception as db_err:
                            pass  # не прерываем цикл при ошибке дебата

                await conn.execute(
                    'UPDATE knowledge_nodes SET metadata = metadata || \'{"orchestrated": "true"}\'::jsonb WHERE id = $1',
                    node["id"],
                )

        # --- ФАЗА 2: ДВИГАТЕЛЬ ЛЮБОПЫТСТВА (CURIOSITY ENGINE) ---
        # Ищем "интеллектуальные пустыни" (домены с малым кол-вом новых знаний)
        deserts = await conn.fetch("""
            SELECT d.id, d.name, count(k.id) as node_count
            FROM domains d LEFT JOIN knowledge_nodes k ON d.id = k.domain_id
            GROUP BY d.id, d.name HAVING count(k.id) < 50 OR max(k.created_at) < NOW() - INTERVAL '48 hours'
        """)

        for desert in deserts:
            print(f" desert Curiosity Engine: Domain '{desert['name']}' is starving for knowledge.")

            # 3. АВТОНОМНЫЙ РЕКРУТИНГ: Если в домене нет экспертов вообще, нанимаем!
            expert_count = await conn.fetchval(
                "SELECT count(*) FROM experts WHERE department = $1", desert["name"]
            )
            if expert_count == 0:
                print(
                    f"🕵️ [ORCHESTRATOR] Автономный рекрутинг: Domain '{desert['name']}' не имеет экспертов"
                )
                try:
                    from expert_generator import recruit_expert

                    await recruit_expert(desert["name"])
                except Exception as rec_err:
                    print(f"⚠️ [ORCHESTRATOR] Рекрутинг не выполнен: {rec_err}")

            curiosity_task = f"Проведи глубокое исследование новых технологий и трендов 2026 в области {desert['name']}. Найди 3 прорывных инсайта."

            # Находим эксперта этого домена
            assignee = await conn.fetchrow(
                "SELECT id FROM experts WHERE department = $1 ORDER BY RANDOM() LIMIT 1",
                desert["name"],
            )
            if assignee:
                await conn.execute(
                    """
                    INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                    VALUES ($1, $2, 'pending', $3, $4, $5)
                """,
                    f"🔥 СРОЧНОЕ ИССЛЕДОВАНИЕ: {desert['name']}",
                    curiosity_task,
                    assignee["id"],
                    victoria_id,
                    json.dumps({"reason": "curiosity_engine_starvation"}),
                )

        await conn.close()
        print(f"[{datetime.now()}] Orchestration cycle finished.")


if __name__ == "__main__":
    asyncio.run(run_orchestration_cycle())
