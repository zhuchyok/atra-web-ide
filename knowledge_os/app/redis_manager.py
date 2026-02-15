import os
import json
import logging
import asyncio
from typing import Any, Optional, Dict, List
import redis.asyncio as redis
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class RedisManager:
    """
    Централизованный менеджер для работы с Redis: кэш, состояние задач и очереди.
    Реализует лучшие мировые практики: пулинг соединений, асинхронность, JSON-сериализация.
    """
    _instance = None
    _pool = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RedisManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, url: str = REDIS_URL):
        if not hasattr(self, 'initialized'):
            self.url = url
            self.initialized = True

    async def get_client(self) -> redis.Redis:
        """Получает или создает клиент Redis из пула."""
        if self._pool is None:
            try:
                self._pool = redis.ConnectionPool.from_url(
                    self.url, 
                    max_connections=20, 
                    decode_responses=True
                )
                logger.info(f"✅ [REDIS] Пул соединений создан: {self.url}")
            except Exception as e:
                logger.error(f"❌ [REDIS] Ошибка создания пула: {e}")
                raise
        return redis.Redis(connection_pool=self._pool)

    # --- КЭШИРОВАНИЕ ---
    async def set_cache(self, key: str, value: Any, ttl: int = 3600):
        """Сохраняет значение в кэш (с сериализацией в JSON)."""
        try:
            client = await self.get_client()
            val = json.dumps(value)
            await client.set(f"cache:{key}", val, ex=ttl)
        except Exception as e:
            logger.warning(f"⚠️ [REDIS] Ошибка записи в кэш {key}: {e}")

    async def get_cache(self, key: str) -> Optional[Any]:
        """Получает значение из кэша."""
        try:
            client = await self.get_client()
            val = await client.get(f"cache:{key}")
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning(f"⚠️ [REDIS] Ошибка чтения кэша {key}: {e}")
            return None

    # --- СОСТОЯНИЕ ЗАДАЧ (Shared State) ---
    async def update_task_status(self, task_id: str, status: str, result: Any = None, metadata: Dict = None):
        """Обновляет состояние задачи в Redis (для мгновенного доступа Gateway)."""
        try:
            client = await self.get_client()
            data = {
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            if result is not None: data["result"] = result
            if metadata: data["metadata"] = metadata
            
            await client.hset(f"task:{task_id}", mapping={k: json.dumps(v) for k, v in data.items()})
            # TTL для статуса задачи - 24 часа
            await client.expire(f"task:{task_id}", 86400)
        except Exception as e:
            logger.error(f"❌ [REDIS] Ошибка обновления статуса задачи {task_id}: {e}")

    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Получает текущий статус задачи."""
        try:
            client = await self.get_client()
            data = await client.hgetall(f"task:{task_id}")
            return {k: json.loads(v) for k, v in data.items()} if data else None
        except Exception as e:
            logger.error(f"❌ [REDIS] Ошибка получения статуса задачи {task_id}: {e}")
            return None

    # --- ОЧЕРЕДИ (Redis Streams) ---
    async def push_to_stream(self, stream_name: str, data: Dict, deduplicate: bool = True):
        """
        Добавляет задачу в поток (Redis Stream) — промышленный стандарт.
        deduplicate: если True, проверяет наличие активной задачи с таким же ID или хэшем.
        """
        try:
            client = await self.get_client()
            task_id = data.get("task_id")
            
            if deduplicate and task_id:
                # Проверяем, не обрабатывается ли уже эта задача (идемпотентность)
                lock_key = f"lock:task:{task_id}"
                is_locked = await client.set(lock_key, "processing", ex=1800, nx=True) # Блокировка на 30 мин
                if not is_locked:
                    logger.warning(f"🚫 [REDIS] Дубликат задачи {task_id} проигнорирован")
                    return False

            # Сингулярность 10.0: Добавляем время создания и метаданные для RAG
            data["created_at"] = datetime.now(timezone.utc).isoformat()
            
            # Если в данных есть ключевые слова AI, помечаем для воркера
            goal = data.get("description", "").lower()
            if any(kw in goal for kw in ["anthropic", "google", "openai", "deepseek", "claude", "gemini"]):
                data["rag_domain"] = "AI Research"
            
            # Ограничиваем длину потока 10000 записей (мировая практика)
            await client.xadd(f"stream:{stream_name}", {"payload": json.dumps(data)}, maxlen=10000)
            logger.info(f"📥 [REDIS] Задача {task_id} добавлена в поток {stream_name}")
            return True
        except Exception as e:
            logger.error(f"❌ [REDIS] Ошибка записи в поток {stream_name}: {e}")
            return False

    async def autoclaim_tasks(self, stream_name: str, group_name: str, consumer_name: str, min_idle_time_ms: int = 60000):
        """
        Мировая практика (Reliable Queue): Перехватывает зависшие задачи других воркеров.
        Если воркер упал, задача через min_idle_time_ms будет переназначена текущему воркеру.
        """
        try:
            client = await self.get_client()
            # XAUTOCLAIM возвращает [next_start_id, [entries], [deleted_ids]]
            res = await client.xautoclaim(
                f"stream:{stream_name}", 
                group_name, 
                consumer_name, 
                min_idle_time_ms, 
                start_id="0-0", 
                count=5
            )
            if res and res[1]:
                logger.info(f"🔄 [REDIS] Перехвачено {len(res[1])} зависших задач из потока {stream_name}")
                return res[1]
            return []
        except Exception as e:
            logger.error(f"❌ [REDIS] Ошибка autoclaim в потоке {stream_name}: {e}")
            return []

    async def release_task_lock(self, task_id: str):
        """Снимает блокировку с задачи (после завершения или ошибки)."""
        try:
            client = await self.get_client()
            await client.delete(f"lock:task:{task_id}")
        except Exception as e:
            logger.warning(f"⚠️ [REDIS] Не удалось снять блокировку {task_id}: {e}")

    async def close(self):
        """Закрывает пул соединений."""
        if self._pool:
            await self._pool.disconnect()
            logger.info("🛑 [REDIS] Пул соединений закрыт")

# Синглтон для удобного импорта
redis_manager = RedisManager()
