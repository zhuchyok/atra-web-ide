#!/usr/bin/env python3
"""
Миграция: добавить usage_count и is_verified в knowledge_nodes, если отсутствуют.
Исправляет ошибку дашборда: column "usage_count" does not exist.

Запуск:
  python3 scripts/fix_dashboard_schema.py
  или: docker exec -i knowledge_postgres psql -U admin -d knowledge_os < scripts/fix_dashboard_schema.sql
"""
import os
import sys

def main():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    try:
        import psycopg2
    except ImportError:
        print("Установите psycopg2: pip install psycopg2-binary")
        sys.exit(1)

    print("Подключение к БД...")
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        # usage_count
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'knowledge_nodes' AND column_name = 'usage_count'
        """)
        if cur.fetchone() is None:
            print("Добавляю usage_count в knowledge_nodes...")
            cur.execute("ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS usage_count INTEGER DEFAULT 0")
            print("  ✅ usage_count добавлен")
        else:
            print("  ✓ usage_count уже есть")

        # is_verified
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'knowledge_nodes' AND column_name = 'is_verified'
        """)
        if cur.fetchone() is None:
            print("Добавляю is_verified в knowledge_nodes...")
            cur.execute("ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE")
            print("  ✅ is_verified добавлен")
        else:
            print("  ✓ is_verified уже есть")

        cur.close()
        conn.close()
        print("\nГотово. Обновите дашборд (F5).")
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
