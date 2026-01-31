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
            capture_output=True, text=True, check=True, timeout=300, env=env
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Agent error: {e}")
        return None

async def generate_ad_campaign(product_description: str):
    print(f"🚀 Generating marketing campaign for: {product_description[:50]}...")
    conn = await asyncpg.connect(DB_URL)
    
    # 1. Получаем экспертов отдела маркетинга
    marketing_experts = await conn.fetch("SELECT name, role, system_prompt FROM experts WHERE department = 'Marketing'")
    
    campaign_results = {}
    
    for expert in marketing_experts:
        print(f"  - Expert {expert['name']} is working...")
        prompt = f"""
        {expert['system_prompt']}
        ЗАДАЧА: Разработай свою часть рекламной кампании для следующего продукта/услуги:
        "{product_description}"
        
        Верни структурированный ответ с конкретными рекомендациями, текстами или настройками.
        """
        response = run_cursor_agent(prompt)
        campaign_results[expert['name']] = response
    
    # 2. Виктория синтезирует финальный план
    victoria = await conn.fetchrow("SELECT system_prompt FROM experts WHERE name = 'Виктория'")
    summary_prompt = f"""
    {victoria['system_prompt']}
    Вы Виктория, Team Lead. Перед вами отчеты отдела маркетинга по продукту: "{product_description}"
    
    ОТЧЕТЫ:
    {json.dumps(campaign_results, ensure_ascii=False, indent=2)}
    
    ЗАДАЧА: Сформируй единый стратегический план запуска рекламы. Выдели самое важное.
    """
    final_plan = run_cursor_agent(summary_prompt)
    
    # 3. Сохраняем в базу знаний как "Маркетинговая стратегия"
    domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'Marketing'")
    if not domain_id:
        domain_id = await conn.fetchval("INSERT INTO domains (name) VALUES ('Marketing') RETURNING id")
        
    await conn.execute("""
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
        VALUES ($1, $2, 0.98, $3, true)
    """, domain_id, f"🎯 РЕКЛАМНАЯ КАМПАНИЯ: {product_description[:100]}\n\n{final_plan}", 
    json.dumps({"source": "ad_generator", "product": product_description}))
    
    await conn.close()
    return final_plan

if __name__ == "__main__":
    # Тестовый запуск если запущен как скрипт
    import sys
    product = sys.argv[1] if len(sys.argv) > 1 else "Сервис по аренде ИИ-агентов для бизнеса"
    asyncio.run(generate_ad_campaign(product))

