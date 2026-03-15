"""
[KNOWLEDGE OS] Multi-Cluster Bridge v1.0.
Handles Gossip synchronization and Task Tunneling between autonomous nodes.
Part of Singularity 21.24.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import asyncpg
import httpx

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
CLUSTER_NAME = os.getenv("CLUSTER_NAME", "mac-studio-primary")
HEARTBEAT_INTERVAL = 30  # seconds
GOSSIP_INTERVAL = 60  # seconds


class MultiClusterBridge:
    def __init__(self, cert_path=None, key_path=None, ca_path=None):
        self.cluster_id = None

        # [SINGULARITY 21.24] mTLS — приоритет: переданные аргументы > переменные окружения
        cert_path = cert_path or os.getenv("BRIDGE_CERT_PATH")
        key_path = key_path or os.getenv("BRIDGE_KEY_PATH")
        ca_path = ca_path or os.getenv("BRIDGE_CA_PATH")

        if cert_path and key_path:
            logger.info(f"🔐 MultiClusterBridge с mTLS: {cert_path}")
            self.client = httpx.AsyncClient(
                timeout=10.0, cert=(cert_path, key_path), verify=ca_path if ca_path else True
            )
        else:
            logger.warning("⚠️ MultiClusterBridge initialized without mTLS (insecure mode)")
            self.client = httpx.AsyncClient(timeout=10.0)

    async def initialize(self, conn):
        """Регистрация текущего узла и получение cluster_id."""
        row = await conn.fetchrow("SELECT id FROM clusters WHERE name = $1", CLUSTER_NAME)
        if row:
            self.cluster_id = row["id"]
            logger.info(
                f"🌐 MultiClusterBridge initialized. Cluster: {CLUSTER_NAME} ({self.cluster_id})"
            )
        else:
            # Если Insert в миграции не сработал или имя сменилось
            self.cluster_id = await conn.fetchval(
                "INSERT INTO clusters (name, url, is_local) VALUES ($1, $2, true) RETURNING id",
                CLUSTER_NAME,
                "http://localhost:8081",
            )
            logger.info(f"🌐 MultiClusterBridge registered new cluster: {CLUSTER_NAME}")

    async def send_heartbeat(self):
        """Обновление статуса текущего узла в БД."""
        conn = await asyncpg.connect(DB_URL)
        try:
            await conn.execute(
                "UPDATE clusters SET last_heartbeat = CURRENT_TIMESTAMP, status = 'active' WHERE id = $1",
                self.cluster_id,
            )
        finally:
            await conn.close()

    async def gossip_sync(self):
        """Gossip-протокол: обмен метаданными с другими узлами."""
        conn = await asyncpg.connect(DB_URL)
        try:
            # Находим другие активные узлы
            others = await conn.fetch(
                "SELECT id, name, url FROM clusters WHERE status = 'active' AND id != $1",
                self.cluster_id,
            )

            for other in others:
                try:
                    # В реальности здесь был бы вызов /api/cluster/sync
                    logger.debug(f"📡 Gossiping with {other['name']} at {other['url']}...")
                    # Эмуляция: проверяем доступность
                    resp = await self.client.get(f"{other['url']}/health")
                    if resp.status_code != 200:
                        raise Exception("Node unreachable")
                except Exception as e:
                    logger.warning(f"⚠️ Node {other['name']} is unreachable: {e}")
                    # Если узел молчит долго, помечаем как inactive
                    await conn.execute(
                        "UPDATE clusters SET status = 'inactive' WHERE id = $1 AND last_heartbeat < NOW() - INTERVAL '2 minutes'",
                        other["id"],
                    )
        finally:
            await conn.close()

    async def task_tunneling(self):
        """Перехват задач "упавших" узлов с использованием распределенной блокировки."""
        conn = await asyncpg.connect(DB_URL)
        redis_conn = None
        try:
            # Находим задачи неактивных узлов
            stale_tasks = await conn.fetch(
                """
                SELECT t.id, t.title, c.name as original_cluster
                FROM tasks t
                JOIN clusters c ON t.cluster_id = c.id
                WHERE c.status = 'inactive' AND t.status = 'pending'
                LIMIT 10
                """
            )

            if stale_tasks and os.getenv("REDIS_URL"):
                try:
                    import redis.asyncio as redis

                    redis_conn = await redis.from_url(os.getenv("REDIS_URL"))
                except ImportError:
                    logger.warning("Redis not available for distributed locking")

            for task in stale_tasks:
                # Пытаемся захватить блокировку на задачу на 60 секунд
                lock_key = f"lock:task_tunnel:{task['id']}"
                locked = False
                if redis_conn:
                    locked = await redis_conn.set(lock_key, str(self.cluster_id), ex=60, nx=True)
                else:
                    locked = True  # Fallback if no redis, but risky in multi-node

                if locked:
                    logger.info(
                        f"🚀 [TUNNELING] Intercepting task {task['id']} from failed cluster {task['original_cluster']}"
                    )
                    meta_update = json.dumps({"tunneled_from": task["original_cluster"]})
                    await conn.execute(
                        "UPDATE tasks SET cluster_id = $1, metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb WHERE id = $3",
                        self.cluster_id,
                        meta_update,
                        task["id"],
                    )
        finally:
            await conn.close()
            if redis_conn:
                await redis_conn.close()


async def run_bridge_daemon():
    bridge = MultiClusterBridge()
    conn = await asyncpg.connect(DB_URL)
    await bridge.initialize(conn)
    await conn.close()

    while True:
        try:
            await bridge.send_heartbeat()
            await bridge.gossip_sync()
            await bridge.task_tunneling()
        except Exception as e:
            logger.error(f"❌ Bridge error: {e}")

        await asyncio.sleep(HEARTBEAT_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_bridge_daemon())
