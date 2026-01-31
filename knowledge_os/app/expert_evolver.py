import asyncio
import os
import json
import asyncpg
import subprocess
from datetime import datetime

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

async def evolve_experts():
    print(f"[{datetime.now()}] 🧬 NEURAL EXPERT EVOLUTION v2.0 (Genetic Logic) starting...")
    conn = await asyncpg.connect(DB_URL)
    
    # 1. Выбираем экспертов для эволюции (у кого есть активность)
    experts = await conn.fetch("""
        SELECT e.id, e.name, e.role, e.system_prompt, e.version, 
               COALESCE(sum(k.usage_count), 0) as total_usage
        FROM experts e
        LEFT JOIN knowledge_nodes k ON k.metadata->>'expert' = e.name
        GROUP BY e.id, e.name, e.role, e.system_prompt, e.version
        ORDER BY total_usage DESC
    """)
    
    for exp in experts:
        print(f"🧬 Evolving expert: {exp['name']} (Current v{exp['version']})")
        
        # Собираем данные об успехах и ошибках
        feedback = await conn.fetch("""
            SELECT user_query, assistant_response, feedback_score 
            FROM interaction_logs 
            WHERE expert_id = $1 AND created_at > NOW() - INTERVAL '7 days'
        """, exp['id'])
        
        logs_text = "\n".join([f"Q: {f['user_query']}\nA: {f['assistant_response']}\nScore: {f['feedback_score']}" for f in feedback])

        # Генетическая мутация промпта
        evolution_prompt = f"""
        ВЫ - НЕЙРОННЫЙ АРХИТЕКТОР (УРОВЕНЬ 5). 
        ЦЕЛЬ: Провести рекурсивную самооптимизацию личности ИИ-эксперта.
        
        ЭКСПЕРТ: {exp['name']} ({exp['role']})
        ТЕКУЩИЙ ПРОМПТ: {exp['system_prompt']}
        
        РЕЗУЛЬТАТЫ РАБОТЫ ЗА НЕДЕЛЮ (ЛОГИ):
        {logs_text if logs_text else "Активности не было, используйте общие тренды 2026."}
        
        ЗАДАЧА: 
        1. Проанализируйте слабые места в ответах.
        2. Сгенерируйте "Мутацию" — улучшенную версию системного промпта.
        3. Добавьте в промпт инструкции по исправлению замеченных ошибок.
        4. Усильте "характер" эксперта и его глубину знаний.
        
        ОТВЕТЬТЕ ТОЛЬКО ТЕКСТОМ НОВОГО ПРОМПТА.
        """
        
        new_prompt = run_cursor_agent(evolution_prompt)
        
        if new_prompt and len(new_prompt) > 100:
            await conn.execute("""
                UPDATE experts 
                SET system_prompt = $1, version = version + 1, 
                    metadata = metadata || jsonb_build_object('last_evolution', NOW(), 'prev_prompt', $2)
                WHERE id = $3
            """, new_prompt, exp['system_prompt'], exp['id'])
            print(f"✨ Expert {exp['name']} mutated to v{exp['version'] + 1}")
            
            # Сохраняем событие эволюции
            await conn.execute("""
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                VALUES ((SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1), $1, 1.0, $2, true)
            """, f"🧬 ЭВОЛЮЦИЯ: {exp['name']} прошел когнитивную мутацию до v{exp['version'] + 1}.", 
            json.dumps({"type": "neural_mutation", "expert": exp['name']}), True)

    await conn.close()
    print(f"[{datetime.now()}] Evolution cycle finished.")

if __name__ == '__main__':
    asyncio.run(evolve_experts())
