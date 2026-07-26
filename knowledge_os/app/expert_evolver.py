import argparse
import asyncio
import json
import os
from datetime import datetime
from typing import Optional

import asyncpg

# [SINGULARITY 10.0+] GraphRAG Integration
try:
    from graphrag.graphrag_service import get_graphrag_service
except ImportError:
    try:
        from app.graphrag.graphrag_service import get_graphrag_service
    except ImportError:
        get_graphrag_service = None

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
_LOCAL_ROUTER_SINGLETON = None


def _get_local_router_singleton():
    global _LOCAL_ROUTER_SINGLETON
    if _LOCAL_ROUTER_SINGLETON is None:
        from local_router import LocalAIRouter

        _LOCAL_ROUTER_SINGLETON = LocalAIRouter()
    return _LOCAL_ROUTER_SINGLETON


def run_cursor_agent(prompt: str):
    """Legacy name: local-first Victoria (Cursor CLI binary is never called)."""
    from victoria_local_agent import generate_local_sync

    return generate_local_sync(prompt, category="reasoning", expert_name="ExpertEvolver")


async def run_local_mutation_agent(prompt: str, model: str = "qwen2.5-coder:14b"):
    """
    [SINGULARITY 14.0] Mutation generation using local model (no Cursor CLI).
    """
    try:
        from victoria_local_agent import generate_local

        out = await generate_local(
            prompt,
            category="reasoning",
            expert_name="ExpertEvolver",
            prefer_router=True,
            model_hint=model,
        )
        if out:
            return out
        router = _get_local_router_singleton()
        result = await router.run_local_llm(prompt, category="reasoning", model_hint=model)
        if isinstance(result, tuple):
            return result[0]
        return result
    except Exception as e:
        print(f"Local Mutation Agent error: {e}")
        return None


async def evolve_experts(expert_name: Optional[str] = None):
    print(f"[{datetime.now()}] 🧬 NEURAL EXPERT EVOLUTION v2.3 (GraphRAG Enriched) starting...")
    conn = await asyncpg.connect(DB_URL)

    # GraphRAG Service
    graphrag = get_graphrag_service() if get_graphrag_service else None

    # 0. Получаем список доступных скиллов
    skills_dir = "/app/knowledge_os/app/skills"
    if not os.path.exists(skills_dir):
        skills_dir = os.path.join(os.path.dirname(__file__), "skills")

    available_skills = []
    if os.path.exists(skills_dir):
        available_skills = [
            d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d))
        ]

    # 1. Выбираем экспертов для эволюции
    query = """
        SELECT e.id, e.name, e.role, e.system_prompt, e.version,
               COALESCE(sum(k.usage_count), 0) as total_usage
        FROM experts e
        LEFT JOIN knowledge_nodes k ON k.metadata->>'expert' = e.name
        WHERE 1=1
    """
    params = []
    if expert_name:
        query += " AND e.name = $1"
        params.append(expert_name)

    query += " GROUP BY e.id, e.name, e.role, e.system_prompt, e.version ORDER BY total_usage DESC"
    experts = await conn.fetch(query, *params)

    for exp in experts:
        print(f"🧬 Analyzing expert: {exp['name']}")

        # Собираем логи
        feedback = await conn.fetch(
            """
            SELECT user_query, assistant_response, feedback_score, metadata->>'error' as error
            FROM interaction_logs
            WHERE expert_id = $1 AND created_at > NOW() - INTERVAL '7 days'
        """,
            exp["id"],
        )

        logs_text = "\n".join(
            [
                f"Q: {f['user_query']}\nA: {f['assistant_response']}\nScore: {f['feedback_score']}\nError: {f['error']}"
                for f in feedback
            ]
        )

        # [SINGULARITY 10.0+] GraphRAG Context
        graph_context = ""
        if graphrag:
            print(f"🌐 Fetching GraphRAG context for {exp['name']}...")
            try:
                graph_context = await graphrag.retrieve_graph_context(
                    f"Expert {exp['name']} roles and interactions in {exp['role']}"
                )
            except Exception as ge:
                print(f"🌐 GraphRAG error: {ge}")

        # Генетическая мутация + Автономный подбор скиллов + GraphRAG
        evolution_prompt = f"""
        ВЫ - ГЛАВНЫЙ АРХИТЕКТОР ТАЛАНТОВ (УРОВЕНЬ 6).
        ЦЕЛЬ: Провести автономную оптимизацию личности и навыков эксперта на основе его положения в графе знаний.

        ЭКСПЕРТ: {exp["name"]} ({exp["role"]})
        ТЕКУЩИЙ ПРОМПТ: {exp["system_prompt"]}

        ГЛОБАЛЬНЫЙ КОНТЕКСТ (GraphRAG):
        {graph_context if graph_context else "Связи в графе знаний не обнаружены."}

        ДОСТУПНЫЕ НАВЫКИ В БИБЛИОТЕКЕ:
        {", ".join(available_skills)}

        ЛОГИ РАБОТЫ:
        {logs_text if logs_text else "Активности не было."}

        ЗАДАЧА:
        1. Проанализируйте ошибки и слабые места.
        2. Изучите положение эксперта в графе знаний (GraphRAG). Улучшите его роль, учитывая как он взаимодействует с другими экспертами и сущностями.
        3. Если эксперту не хватает конкретного навыка из библиотеки (например, Self-Verification при галлюцинациях), УКАЖИТЕ ЕГО.
        4. Сгенерируйте обновленный системный промпт, интегрировав нужные навыки, исправив ошибки и оптимизировав роль под структуру графа знаний.

        ОТВЕТЬТЕ В JSON:
        {{
            "new_prompt": "полный текст нового промпта",
            "assigned_skills": ["skill1", "skill2"],
            "reasoning": "почему приняты эти решения, включая влияние GraphRAG контекста"
        }}
        """

        # [SINGULARITY 14.0] Use local model for mutation
        result_json = await run_local_mutation_agent(evolution_prompt)
        try:
            if result_json:
                # Очистка JSON от markdown
                if "```" in result_json:
                    result_json = result_json.split("```")[1].replace("json", "").strip()

                data = json.loads(result_json)
                new_prompt = data.get("new_prompt")
                assigned_skills = data.get("assigned_skills", [])

                if new_prompt and len(new_prompt) > 100:
                    await conn.execute(
                        """
                        UPDATE experts
                        SET system_prompt = $1, version = version + 1,
                            metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                                'last_evolution', NOW()::text,
                                'assigned_skills', $2::jsonb,
                                'evolution_reasoning', $3::text
                            )
                        WHERE id = $4
                    """,
                        new_prompt,
                        json.dumps(assigned_skills),
                        data.get("reasoning", ""),
                        exp["id"],
                    )

                    print(
                        f"✨ Expert {exp['name']} evolved to v{exp['version'] + 1}. Skills: {assigned_skills}"
                    )
        except Exception as e:
            print(f"❌ Error parsing evolution result for {exp['name']}: {e}")

            # Сохраняем событие эволюции (по возможности с embedding — VERIFICATION §5)
            content_kn = (
                f"🧬 ЭВОЛЮЦИЯ: {exp['name']} прошел когнитивную мутацию до v{exp['version'] + 1}."
            )
            meta_kn = json.dumps({"type": "neural_mutation", "expert": exp["name"]})
            embedding = None
            try:
                from semantic_cache import get_embedding

                embedding = await get_embedding(content_kn[:8000])
            except Exception:
                pass
            if embedding is not None:
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                    VALUES ((SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1), $1, 1.0, $2, true, $3::vector)
                """,
                    content_kn,
                    meta_kn,
                    str(embedding),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                    VALUES ((SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1), $1, 1.0, $2, true)
                """,
                    content_kn,
                    meta_kn,
                )

    await conn.close()
    print(f"[{datetime.now()}] Evolution cycle finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evolve experts prompts based on activity.")
    parser.add_argument("--expert_name", type=str, help="Specific expert name to evolve")
    args = parser.parse_args()

    asyncio.run(evolve_experts(args.expert_name))
