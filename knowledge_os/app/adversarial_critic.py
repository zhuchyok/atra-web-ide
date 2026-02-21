import asyncio
import os
import json
import asyncpg
import subprocess
import sys
from datetime import datetime, timezone

# Используем get_pool из evaluator для консистентности
sys.path.insert(0, os.path.dirname(__file__))
from evaluator import get_pool

def run_cursor_agent(prompt: str):
    """Run cursor-agent CLI to process a prompt and return output."""
    try:
        env = os.environ.copy()
        result = subprocess.run(
            ["/root/.local/bin/cursor-agent", "--print", prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=600,
            env=env
        )
        return result.stdout
    except Exception as e:
        print(f"Error running cursor-agent for adversarial attack: {e}")
        return None

async def run_adversarial_cycle(limit: int = 5):
    print(f"🛡️ Starting Adversarial Critic (Corporate Immunity) cycle for {limit} nodes...")
    pool = await get_pool()
    conn = await pool.acquire()
    
    # 1. Находим недавно верифицированные знания или новые SOP для стресс-теста
    nodes = await conn.fetch("""
        SELECT id, content, quality_report, metadata
        FROM knowledge_nodes 
        WHERE is_verified = TRUE 
        AND (metadata->>'adversarial_tested' IS NULL OR metadata->>'adversarial_tested' = 'false')
        AND (confidence_score > 0.7 OR metadata->>'type' = 'sop_document')
        ORDER BY created_at DESC LIMIT $1
    """, limit)
    
    if not nodes:
        print("✅ No new nodes for adversarial testing.")
        await pool.release(conn)
        return

    for node in nodes:
        metadata = node['metadata']
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        
        is_sop = (metadata or {}).get('type') == 'sop_document'
        print(f"⚔️ Stress-testing {'SOP' if is_sop else 'node'} {node['id']}...")
        
        role_name = "БЕЗЖАЛОСТНЫЙ КРИТИК И АДВОКАТ ДЬЯВОЛА"
        if is_sop:
            role_name = "ГЛАВНЫЙ ИНСПЕКТОР ПО КАЧЕСТВУ И БЕЗОПАСНОСТИ"

        attack_prompt = f"""
        ТЫ - {role_name}.
        ТВОЯ ЗАДАЧА: Найти критические изъяны, ошибки в логике, угрозы безопасности или неэффективные инструкции в предоставленном контенте.
        
        ТИП КОНТЕНТА: {'Standard Operating Procedure (SOP)' if is_sop else 'Knowledge Insight'}
        КОНТЕНТ: {node['content']}
        {f"ОТЧЕТ ПРЕДЫДУЩЕГО СУДЬИ: {node['quality_report']}" if node['quality_report'] else ""}
        
        ИНСТРУКЦИЯ:
        1. Проведи поиск потенциальных проблем (security, performance, logic).
        2. Если это SOP - проверь, не приведет ли выполнение этих шагов к сбою системы.
        3. Найди 3 причины, почему это может не сработать в реальных условиях.
        4. Если контент выдержал атаку - подтверди его исключительную надежность.
        
        ВЕРНИ JSON:
        {{
            "survived": true/false,
            "attack_report": "Текст твоей атаки и выводов",
            "new_confidence_score": 0.0-1.0
        }}
        ВЕРНИ ТОЛЬКО ЧИСТЫЙ JSON.
        """
        
        from ai_core import run_smart_agent_async
        output = await run_smart_agent_async(attack_prompt, expert_name="Критик", category="reasoning")
        
        if output:
            try:
                clean_json = output.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0]
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0]
                
                result = json.loads(clean_json)
                
                # Обновляем знание результатами атаки
                await conn.execute("""
                    UPDATE knowledge_nodes 
                    SET confidence_score = $1, 
                        expert_consensus = COALESCE(expert_consensus, '{}'::jsonb) || $2::jsonb,
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('adversarial_tested', 'true', 'survived', $3::boolean)
                    WHERE id = $4
                """, result['new_confidence_score'], json.dumps({"adversarial_attack": result['attack_report']}), 
                result['survived'], node['id'])
                
                status = "SURVIVED" if result['survived'] else "DESTROYED"
                print(f"🛡️ Node {node['id']} {status}. New Score: {result['new_confidence_score']}")
                
                # Если знание уничтожено - уведомляем через радар
                if not result['survived']:
                    await conn.execute("""
                        INSERT INTO notifications (message, type)
                        VALUES ($1, 'adversarial_alert')
                    """, f"💀 KNOWLEDGE DESTROYED: Утверждение '{node['content'][:50]}...' не прошло стресс-тест. Аргумент: {result['attack_report'][:100]}")
            
            except Exception as e:
                print(f"❌ Error parsing adversarial output: {e}")

    await pool.release(conn)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Adversarial Critic Stress-Test Cycle')
    parser.add_argument('--limit', type=int, default=5, help='Number of nodes to test')
    args = parser.parse_args()
    
    asyncio.run(run_adversarial_cycle(limit=args.limit))

