import os
import psycopg2
from psycopg2.extras import RealDictCursor

def check_db():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    try:
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        with conn.cursor() as cur:
            # 1. Считаем узлы по доменам
            cur.execute("""
                SELECT d.name, COUNT(k.id) as node_count 
                FROM domains d 
                LEFT JOIN knowledge_nodes k ON d.id = k.domain_id 
                GROUP BY d.name 
                ORDER BY node_count DESC;
            """)
            counts = cur.fetchall()
            print("--- Узлы по доменам ---")
            for row in counts:
                print(f"{row['name']}: {row['node_count']}")
            
            # 2. Проверяем связи между доменами
            cur.execute("""
                SELECT 
                    d1.name as source_domain, 
                    d2.name as target_domain, 
                    COUNT(*) as link_count
                FROM knowledge_links l
                JOIN knowledge_nodes k1 ON l.source_node_id = k1.id
                JOIN knowledge_nodes k2 ON l.target_node_id = k2.id
                JOIN domains d1 ON k1.domain_id = d1.id
                JOIN domains d2 ON k2.domain_id = d2.id
                GROUP BY d1.name, d2.name
                ORDER BY link_count DESC
                LIMIT 10;
            """)
            links = cur.fetchall()
            print("\n--- Топ связей между доменами ---")
            for row in links:
                print(f"{row['source_domain']} -> {row['target_domain']}: {row['link_count']}")
                
        conn.close()
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    check_db()
