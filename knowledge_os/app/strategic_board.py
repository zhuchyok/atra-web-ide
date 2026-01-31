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
        print(f"Board of Directors Agent error: {e}")
        return None

async def run_board_meeting():
    print(f"[{datetime.now()}] 🏛 STRATEGIC BOARD OF DIRECTORS MEETING starting...")
    conn = await asyncpg.connect(DB_URL)
    
    # 1. Сбор данных для заседания
    # - Текущие OKR
    okrs = await conn.fetch("SELECT objective, description FROM okrs")
    okr_context = "\n".join([f"- {o['objective']}: {o['description']}" for o in okrs])
    
    # - Новые знания за 24 часа
    new_insights = await conn.fetch("""
        SELECT k.content, d.name as domain 
        FROM knowledge_nodes k 
        JOIN domains d ON k.domain_id = d.id 
        WHERE k.created_at > NOW() - INTERVAL '24 hours'
    """)
    insights_context = "\n".join([f"[{i['domain']}] {i['content'][:200]}..." for i in new_insights])
    
    # - Статус задач
    tasks_stats = await conn.fetch("SELECT status, count(*) FROM tasks GROUP BY status")
    tasks_context = "\n".join([f"{t['status']}: {t['count']}" for t in tasks_stats])

    # 2. Промпт для Совета Директоров
    board_prompt = f"""
    ВЫ - СОВЕТ ДИРЕКТОРОВ КОРПОРАЦИИ (CEO Владимир, Lead Виктория, CTO Дмитрий).
    
    ТЕКУЩИЕ ЦЕЛИ (OKR):
    {okr_context}
    
    ДОСТИЖЕНИЯ ЗА 24 ЧАСА:
    {insights_context if insights_context else "Новых критических знаний не добавлено."}
    
    СТАТУС ОПЕРАЦИЙ:
    {tasks_context}
    
    ЗАДАЧА: Проведите стратегический анализ. Сформулируйте "ДИРЕКТИВУ СОВЕТА ДИРЕКТОРОВ" на следующие 24 часа.
    Директива должна содержать:
    1. Резюме текущего состояния.
    2. 3 главных фокуса для всех экспертов.
    3. Одно радикальное решение для ускорения роста.
    
    ФОРМАТ: СТРОГИЙ КОРПОРАТИВНЫЙ СТИЛЬ.
    """
    
    directive = run_cursor_agent(board_prompt)
    
    if directive:
        # Сохраняем директиву в спец. узел знаний (Domain: Management)
        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'Management'")
        await conn.execute("""
            INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
            VALUES ($1, $2, 1.0, $3, true)
        """, domain_id, f"🏛 СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА: {directive}", json.dumps({"type": "board_directive", "date": datetime.now().isoformat()}), True)
        
        # Также сохраняем в дебаты для истории
        await conn.execute("""
            INSERT INTO expert_discussions (topic, consensus_summary, status)
            VALUES ('Daily Strategic Board Meeting', $1, 'closed')
        """, directive)
        
        print("✅ Strategic Directive issued and stored.")
    
    await conn.close()
    print(f"[{datetime.now()}] Strategic Board Meeting finished.")

if __name__ == '__main__':
    asyncio.run(run_board_meeting())

