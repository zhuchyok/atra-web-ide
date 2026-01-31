import asyncio
import os
import asyncpg
import getpass
from datetime import datetime

async def show_dashboard():
    USER = getpass.getuser()
    DB_URL = os.getenv('DATABASE_URL_LOCAL', f'postgresql://{USER}@localhost:5432/knowledge_os')
    
    try:
        conn = await asyncpg.connect(DB_URL)
        
        # 1. Knowledge Stats
        nodes_count = await conn.fetchval("SELECT count(*) FROM knowledge_nodes")
        cache_hits = await conn.fetchval("SELECT sum(usage_count) FROM semantic_ai_cache") or 0
        distilled_count = 0
        dataset_path = "/Users/zhuchyok/Documents/GITHUB/atra/atra/ai_learning_data/distillation_dataset.jsonl"
        if os.path.exists(dataset_path):
            with open(dataset_path, 'r') as f:
                distilled_count = sum(1 for _ in f)

        # 2. Experts
        experts = await conn.fetch("SELECT name, department FROM experts")
        
        # 3. Tasks
        pending_tasks = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'pending'")
        
        print("\n" + "="*50)
        print(f"🚀 ATRA SINGULARITY v4.2 DASHBOARD")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)
        
        print(f"\n🧠 [ MIND STATE ]")
        print(f"- База знаний: {nodes_count} узлов")
        print(f"- Семантический кэш (хитов): {cache_hits}")
        print(f"- Дистилляция (эталонов): {distilled_count}/500 {'✅ ГОТОВ К АПГРЕЙДУ' if distilled_count >= 500 else ''}")
        
        print(f"\n🐝 [ SWARM STATE ]")
        print(f"- Активных экспертов: {len(experts)}")
        for e in experts[:5]:
            print(f"  • {e['name']} ({e['department']})")
        if len(experts) > 5: print(f"  ... и еще {len(experts)-5}")
        
        print(f"\n⚙️ [ OPERATIONS ]")
        print(f"- Очередь задач: {pending_tasks} ожидают")
        
        # 4. Token Savings (Conceptual estimation)
        saved_tokens = cache_hits * 1500 # Avg prompt size
        print(f"\n💎 [ ECONOMY ]")
        print(f"- Сэкономлено токенов (примерно): {saved_tokens:,}")
        
        print("\n" + "="*50)
        await conn.close()
    except Exception as e:
        print(f"❌ Dashboard error: {e}")

if __name__ == "__main__":
    asyncio.run(show_dashboard())

