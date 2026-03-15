import asyncio
import httpx
import logging
import uuid
import asyncpg
import os
import ssl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QuantumClusterVerify")

# Автоопределение: если Gateway запущен с TLS — используем https
CERTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "certs"))
CA_CERT = os.path.join(CERTS_DIR, "ca.crt")
CLIENT_CERT = os.path.join(CERTS_DIR, "mac-studio.crt")
CLIENT_KEY = os.path.join(CERTS_DIR, "mac-studio.key")

USE_TLS = os.path.exists(CA_CERT)
RUST_URL = "https://localhost:8081" if USE_TLS else "http://localhost:8081"
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

def get_http_client():
    """Возвращает httpx клиент с mTLS если сертификаты доступны, иначе обычный."""
    if USE_TLS:
        ssl_ctx = ssl.create_default_context(cafile=CA_CERT)
        ssl_ctx.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
        return httpx.AsyncClient(verify=ssl_ctx, timeout=30.0)
    return httpx.AsyncClient(timeout=30.0)

async def verify_quantum_rag():
    logger.info(f"🧪 [VERIFY] Testing Quantum-Inspired RAG ({'HTTPS/mTLS' if USE_TLS else 'HTTP'})...")
    async with get_http_client() as client:
        # Mock embedding
        mock_embedding = [0.1] * 768
        payload = {
            "embedding": mock_embedding,
            "limit": 5,
            "use_quantum": True
        }

        resp = await client.post(f"{RUST_URL}/api/knowledge/search_v2", json=payload)
        if resp.status_code == 200:
            results = resp.json()
            logger.info(f"✅ Quantum RAG returned {len(results)} nodes.")
            return True
        else:
            logger.error(f"❌ Quantum RAG failed: {resp.status_code} {resp.text}")
            return False

async def verify_cluster_tunneling():
    logger.info("🧪 [VERIFY] Testing Cluster Task Tunneling...")
    conn = await asyncpg.connect(DB_URL)
    try:
        # 1. Создаем "мертвый" кластер
        dead_cluster_id = await conn.fetchval(
            "INSERT INTO clusters (name, url, status) VALUES ($1, $2, 'inactive') RETURNING id",
            "dead-node-sim", "http://127.0.0.1:9999"
        )

        # 2. Создаем задачу для этого кластера
        task_id = await conn.fetchval(
            "INSERT INTO tasks (title, description, status, cluster_id) VALUES ($1, $2, 'pending', $3) RETURNING id",
            "Simulated Orphan Task", "This task should be tunneled", dead_cluster_id
        )

        logger.info(f"📡 Created orphan task {task_id} for dead cluster {dead_cluster_id}")

        # 3. Запускаем один цикл MultiClusterBridge (через импорт)
        from knowledge_os.app.core.cluster_bridge import MultiClusterBridge
        # Передаём сертификаты если доступны
        bridge = MultiClusterBridge(
            cert_path=CLIENT_CERT if USE_TLS else None,
            key_path=CLIENT_KEY if USE_TLS else None,
            ca_path=CA_CERT if USE_TLS else None,
        )
        await bridge.initialize(conn)
        await bridge.task_tunneling()

        # 4. Проверяем, перехвачена ли задача
        new_cluster_id = await conn.fetchval("SELECT cluster_id FROM tasks WHERE id = $1", task_id)

        if new_cluster_id != dead_cluster_id:
            logger.info(f"✅ Task {task_id} successfully tunneled to cluster {new_cluster_id}")
            return True
        else:
            logger.error(f"❌ Task tunneling failed. Task still assigned to dead cluster.")
            return False

    finally:
        # Cleanup
        await conn.execute("DELETE FROM tasks WHERE title = 'Simulated Orphan Task'")
        await conn.execute("DELETE FROM clusters WHERE name = 'dead-node-sim'")
        await conn.close()

async def run_verification():
    rag_ok = await verify_quantum_rag()
    tunnel_ok = await verify_cluster_tunneling()

    if rag_ok and tunnel_ok:
        logger.info("🚀 [SUCCESS] Singularity 21.24 Quantum & Multi-Cluster verification PASSED!")
    else:
        logger.error("💥 [FAILURE] Verification failed.")

if __name__ == "__main__":
    import sys
    # Add project root to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    asyncio.run(run_verification())
