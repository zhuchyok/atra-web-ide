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
            capture_output=True, text=True, check=True, timeout=600, env=env
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Synthesis Agent error: {e}")
        return None

async def synthesize_wisdom():
    print(f"[{datetime.now()}] 🧠 META-KNOWLEDGE SYNTHESIZER starting...")
    conn = await asyncpg.connect(DB_URL)
    
    # 1. Получаем 50 самых свежих и верифицированных узлов знаний
    nodes = await conn.fetch("""
        SELECT content, d.name as domain 
        FROM knowledge_nodes k JOIN domains d ON k.domain_id = d.id
        WHERE is_verified = TRUE AND created_at > NOW() - INTERVAL '30 days'
        ORDER BY confidence_score DESC LIMIT 50
    """)
    
    if not nodes:
        print("Not enough knowledge for synthesis.")
        await conn.close()
        return

    knowledge_base = "\n".join([f"[{n['domain']}] {n['content']}" for n in nodes])

    # 2. Промпт для синтеза "Мудрости"
    synthesis_prompt = f"""
    ТЫ - ВЕРХОВНЫЙ СТРАТЕГ КОРПОРАЦИИ (УРОВЕНЬ 5).
    ПЕРЕД ТОБОЙ 50 ПОСЛЕДНИХ ИНСАЙТОВ ИЗ БАЗЫ ЗНАНИЙ:
    {knowledge_base}
    
    ЗАДАЧА: 
    1. Проанализируй этот массив данных.
    2. Выяви глобальный паттерн или общую стратегию.
    3. Сформулируй ОДИН "Корпоративный Золотой Стандарт" (SOP) или "Генеральную Стратегию 2026" на основе этих данных.
    
    ФОРМАТ: СТРОГИЙ, СТРУКТУРИРОВАННЫЙ, ПРАКТИЧЕСКИЙ.
    ВЕРНИ ТОЛЬКО ТЕКСТ СТРАТЕГИИ.
    """
    
    wisdom = run_cursor_agent(synthesis_prompt)
    
    if wisdom:
        # Сохраняем Мета-Знание (по возможности с embedding — VERIFICATION §5)
        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'Strategy'")
        content_kn = f"🏛 META-STRATEGY: {wisdom}"
        meta_kn = json.dumps({"type": "meta_wisdom", "nodes_count": len(nodes)})
        embedding = None
        try:
            from semantic_cache import get_embedding
            embedding = await get_embedding(content_kn[:8000])
        except Exception:
            pass
        if embedding is not None:
            await conn.execute("""
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                VALUES ($1, $2, 1.0, $3, true, $4::vector)
            """, domain_id, content_kn, meta_kn, str(embedding))
        else:
            await conn.execute("""
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                VALUES ($1, $2, 1.0, $3, true)
            """, domain_id, content_kn, meta_kn)
        
        print(f"✅ Meta-Strategy synthesized and stored.")

    await conn.close()
    print(f"[{datetime.now()}] Synthesis cycle finished.")

if __name__ == '__main__':
    asyncio.run(synthesize_wisdom())
