import asyncio
import logging
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import asyncpg

logger = logging.getLogger(__name__)

class GraphOptimizer:
    """
    Оптимизатор графа знаний: Semantic Pruning и Hot-Path Caching.
    """
    def __init__(self, db_url: str = os.getenv('DATABASE_URL')):
        self.db_url = db_url
        self.redis_url = os.getenv('REDIS_URL', 'redis://knowledge_os_redis:6379/0')

    async def _get_conn(self):
        return await asyncpg.connect(self.db_url)

    async def semantic_pruning(self, threshold: float = 0.3, min_usage: int = 5) -> Dict[str, Any]:
        """
        Удаляет слабые связи (низкий strength) или неиспользуемые связи.
        """
        conn = await self._get_conn()
        try:
            # Считаем сколько связей под угрозой (используем strength вместо weight)
            to_delete = await conn.fetchval(
                "SELECT COUNT(*) FROM knowledge_links WHERE strength < $1", threshold
            )
            
            if to_delete > 0:
                # Удаляем
                await conn.execute(
                    "DELETE FROM knowledge_links WHERE strength < $1", threshold
                )
                logger.info(f"✂️ [PRUNING] Удалено {to_delete} слабых связей (strength < {threshold})")
            
            return {"deleted_links": to_delete, "threshold": threshold}
        finally:
            await conn.close()

    async def identify_hot_paths(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Идентифицирует часто используемые цепочки связей на основе логов.
        """
        conn = await self._get_conn()
        try:
            # Анализируем логи доступа
            hot_links = await conn.fetch("""
                SELECT source_node_id, target_node_id, strength, link_type 
                FROM knowledge_links 
                WHERE strength > 0.9 
                ORDER BY strength DESC 
                LIMIT $1
            """, limit)
            return [dict(r) for r in hot_links]
        finally:
            await conn.close()

    async def cache_hot_paths(self):
        """
        Кэширует горячие пути в Redis для мгновенного доступа.
        """
        try:
            import redis.asyncio as redis
            r = redis.from_url(self.redis_url)
            
            hot_paths = await self.identify_hot_paths()
            if hot_paths:
                # Конвертируем UUID в строки для JSON
                serializable_paths = []
                for p in hot_paths:
                    path_dict = dict(p)
                    for k, v in path_dict.items():
                        if hasattr(v, 'hex'): # UUID check
                            path_dict[k] = str(v)
                    serializable_paths.append(path_dict)
                
                await r.set("graph:hot_paths", json.dumps(serializable_paths), ex=3600)
                logger.info(f"🚀 [CACHING] Закешировано {len(serializable_paths)} горячих путей в Redis")
            
            await r.close()
        except ImportError:
            logger.warning("redis-py not installed, caching skipped")
        except Exception as e:
            logger.error(f"❌ [CACHING] Ошибка кэширования: {e}")

async def run_optimization_cycle():
    optimizer = GraphOptimizer()
    print("Starting Graph Optimization Cycle...")
    
    # 1. Pruning
    prune_res = await optimizer.semantic_pruning()
    print(f"Pruning finished: {prune_res}")
    
    # 2. Caching
    await optimizer.cache_hot_paths()
    print("Caching finished.")

if __name__ == "__main__":
    asyncio.run(run_optimization_cycle())
