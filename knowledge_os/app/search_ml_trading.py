#!/usr/bin/env python3
"""
Скрипт для поиска информации о торговой ML модели в базе знаний
"""
import asyncio
import asyncpg
import os
import httpx

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
VECTOR_CORE_URL = "http://localhost:8001"

async def get_embedding(text: str) -> list:
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{VECTOR_CORE_URL}/encode", json={"text": text}, timeout=30.0)
        response.raise_for_status()
        return response.json()["embedding"]

async def search_ml_trading_info():
    queries = [
        "ML модель обучение факторы входы выходы tp sl take profit stop loss",
        "торговая ML модель фильтр входы выходы",
        "машинное обучение торговля факторы обучения"
    ]
    
    conn = await asyncpg.connect(DB_URL)
    
    print("🔍 Поиск информации о торговой ML модели в базе знаний через VectorCore...\n")
    
    for query in queries:
        print(f"\n📋 Запрос: {query}")
        embedding = await get_embedding(query)
        
        results = await conn.fetch("""
            SELECT k.id, k.content, k.confidence_score, d.name as domain_name,
                   (1 - (k.embedding <=> $1::vector)) as similarity
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.confidence_score > 0.3
            ORDER BY similarity DESC LIMIT 5
        """, str(embedding))

        
        if results:
            for r in results:
                print(f"\n  [{r['domain_name']}] Сходство: {r['similarity']:.3f}, Уверенность: {r['confidence_score']:.2f}")
                print(f"  {r['content'][:300]}...")
        else:
            print("  ❌ Релевантной информации не найдено")
    
    # Также поиск по текстовым паттернам
    print("\n\n🔍 Поиск по текстовым паттернам...\n")
    text_results = await conn.fetch("""
        SELECT k.id, k.content, k.confidence_score, d.name as domain_name
        FROM knowledge_nodes k
        JOIN domains d ON k.domain_id = d.id
        WHERE (
            k.content ILIKE '%ml%' OR
            k.content ILIKE '%модель%' OR
            k.content ILIKE '%обучен%' OR
            k.content ILIKE '%фактор%' OR
            k.content ILIKE '%tp%' OR
            k.content ILIKE '%sl%' OR
            k.content ILIKE '%take profit%' OR
            k.content ILIKE '%stop loss%' OR
            k.content ILIKE '%фильтр%' OR
            k.content ILIKE '%вход%' OR
            k.content ILIKE '%выход%' OR
            k.content ILIKE '%торгов%'
        )
        AND k.confidence_score > 0.3
        ORDER BY k.confidence_score DESC, k.usage_count DESC
        LIMIT 10
    """)
    
    if text_results:
        print(f"Найдено {len(text_results)} записей:\n")
        for r in text_results:
            print(f"\n[{r['domain_name']}] Уверенность: {r['confidence_score']:.2f}")
            print(f"{r['content'][:400]}...")
    else:
        print("❌ По текстовым паттернам ничего не найдено")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(search_ml_trading_info())
