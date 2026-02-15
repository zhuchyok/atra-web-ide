import psycopg2
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_indexes():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            logger.info("Applying indexes to 'tasks' table...")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assignee_expert_id ON tasks(assignee_expert_id);")
            
            logger.info("Applying indexes to 'knowledge_nodes' table...")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_domain_id ON knowledge_nodes(domain_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_is_verified ON knowledge_nodes(is_verified);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_created_at ON knowledge_nodes(created_at);")
            
            logger.info("Applying indexes to 'experts' table...")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_experts_name ON experts(name);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_experts_department ON experts(department);")
            
            logger.info("✅ All indexes applied successfully.")
        conn.close()
    except Exception as e:
        logger.error(f"❌ Error applying indexes: {e}")

if __name__ == "__main__":
    apply_indexes()
