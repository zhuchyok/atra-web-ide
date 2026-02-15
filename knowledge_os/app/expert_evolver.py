import asyncio
import os
import json
import asyncpg
import subprocess
import argparse
from datetime import datetime
from typing import Optional

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

def run_cursor_agent(prompt: str):
    try:
        env = os.environ.copy()
        result = subprocess.run(
            ['/root/.local/bin/cursor-agent', '--print', prompt],
            capture_output=True, text=True, check=True, timeout=400, env=env
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Evolution Agent error: {e}")
        return None

async def evolve_experts(expert_name: Optional[str] = None):
    print(f"[{datetime.now()}] 🧬 NEURAL EXPERT EVOLUTION v2.2 (Autonomous Skill Allocation) starting...")
    conn = await asyncpg.connect(DB_URL)
    
    # 0. Получаем список доступных скиллов
    skills_dir = "/app/knowledge_os/app/skills"
    if not os.path.exists(skills_dir):
        skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    
    available_skills = []
    if os.path.exists(skills_dir):
        available_skills = [d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d))]
    
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
        feedback = await conn.fetch("""
            SELECT user_query, assistant_response, feedback_score, metadata->>'error' as error
            FROM interaction_logs 
            WHERE expert_id = $1 AND created_at > NOW() - INTERVAL '7 days'
        """, exp['id'])
        
        logs_text = "\n".join([f"Q: {f['user_query']}\nA: {f['assistant_response']}\nScore: {f['feedback_score']}\nError: {f['error']}" for f in feedback])

        # Генетическая мутация + Автономный подбор скиллов
        evolution_prompt = f"""
        ВЫ - ГЛАВНЫЙ АРХИТЕКТОР ТАЛАНТОВ (УРОВЕНЬ 5). 
        ЦЕЛЬ: Провести автономную оптимизацию личности и навыков эксперта.
        
        ЭКСПЕРТ: {exp['name']} ({exp['role']})
        ТЕКУЩИЙ ПРОМПТ: {exp['system_prompt']}
        
        ДОСТУПНЫЕ НАВЫКИ В БИБЛИОТЕКЕ:
        {', '.join(available_skills)}
        
        ЛОГИ РАБОТЫ:
        {logs_text if logs_text else "Активности не было."}
        
        ЗАДАЧА: 
        1. Проанализируйте ошибки и слабые места.
        2. Если эксперту не хватает конкретного навыка из библиотеки (например, Self-Verification при галлюцинациях), УКАЖИТЕ ЕГО.
        3. Сгенерируйте обновленный системный промпт, интегрировав нужные навыки и исправив ошибки.
        
        ОТВЕТЬТЕ В JSON:
        {{
            "new_prompt": "полный текст нового промпта",
            "assigned_skills": ["skill1", "skill2"],
            "reasoning": "почему приняты эти решения"
        }}
        """
        
        result_json = run_cursor_agent(evolution_prompt)
        try:
            if result_json:
                # Очистка JSON от markdown
                if '```' in result_json:
                    result_json = result_json.split('```')[1].replace('json', '').strip()
                
                data = json.loads(result_json)
                new_prompt = data.get("new_prompt")
                assigned_skills = data.get("assigned_skills", [])
                
                if new_prompt and len(new_prompt) > 100:
                    await conn.execute("""
                        UPDATE experts 
                        SET system_prompt = $1, version = version + 1, 
                            metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                                'last_evolution', NOW()::text, 
                                'assigned_skills', $2::jsonb,
                                'evolution_reasoning', $3::text
                            )
                        WHERE id = $4
                    """, new_prompt, json.dumps(assigned_skills), data.get("reasoning", ""), exp['id'])
                    
                    print(f"✨ Expert {exp['name']} evolved to v{exp['version'] + 1}. Skills: {assigned_skills}")
        except Exception as e:
            print(f"❌ Error parsing evolution result for {exp['name']}: {e}")
            
            # Сохраняем событие эволюции (по возможности с embedding — VERIFICATION §5)
            content_kn = f"🧬 ЭВОЛЮЦИЯ: {exp['name']} прошел когнитивную мутацию до v{exp['version'] + 1}."
            meta_kn = json.dumps({"type": "neural_mutation", "expert": exp['name']})
            embedding = None
            try:
                from semantic_cache import get_embedding
                embedding = await get_embedding(content_kn[:8000])
            except Exception:
                pass
            if embedding is not None:
                await conn.execute("""
                    INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                    VALUES ((SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1), $1, 1.0, $2, true, $3::vector)
                """, content_kn, meta_kn, str(embedding))
            else:
                await conn.execute("""
                    INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                    VALUES ((SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1), $1, 1.0, $2, true)
                """, content_kn, meta_kn)

    await conn.close()
    print(f"[{datetime.now()}] Evolution cycle finished.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Evolve experts prompts based on activity.")
    parser.add_argument("--expert_name", type=str, help="Specific expert name to evolve")
    args = parser.parse_args()
    
    asyncio.run(evolve_experts(args.expert_name))
