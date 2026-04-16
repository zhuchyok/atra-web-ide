import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
# Дедуп-lock при push в stream: не короче таймаута задачи (expert_worker)
_TASK_DEDUP_LOCK_TTL = int(os.getenv("WORKER_TASK_TOTAL_TIMEOUT", "3600"))


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

    def __init__(self, url: str = None):
        if not hasattr(self, "initialized"):
            # [SINGULARITY 24.3] ВАЖНО: В Docker REDIS_URL может быть задан через окружение
            # Мы отдаем приоритет переданному url, затем окружению, затем дефолту.
            self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379")
            self.initialized = True
            import os as system_os
            # [SINGULARITY 24.3] Логируем всегда для отладки
            print(f"DEBUG: [REDIS_MANAGER] Initialized with URL: {self.url} (PID: {system_os.getpid()})")
            # [SINGULARITY 24.3] Сбрасываем пул при инициализации, если он был
            self._pool = None
        else:
            # [SINGULARITY 24.3] Если уже инициализирован, но передан новый URL - обновляем
            if url and url != self.url:
                import os as system_os
                print(f"DEBUG: [REDIS_MANAGER] Updating URL from {self.url} to {url} (PID: {system_os.getpid()})")
                self.url = url
                self._pool = None
            elif os.getenv("REDIS_URL") and os.getenv("REDIS_URL") != self.url:
                # Также проверяем окружение, если url не передан явно
                import os as system_os
                new_url = os.getenv("REDIS_URL")
                print(f"DEBUG: [REDIS_MANAGER] Updating URL from {self.url} to {new_url} from ENV (PID: {system_os.getpid()})")
                self.url = new_url
                self._pool = None
        
        # [SINGULARITY 24.3] Глобальная переменная модуля тоже должна быть актуальной
        import redis_manager as rm_module
        rm_module.REDIS_URL = self.url
        print(f"DEBUG: [REDIS_MANAGER] Module REDIS_URL is now: {rm_module.REDIS_URL}")

    async def get_client(self) -> redis.Redis:
        """Получает или создает клиент Redis из пула."""
        # [SINGULARITY 24.3] Если пул устарел (URL изменился), пересоздаем его
        if self._pool is not None:
            # Проверим, соответствует ли пул текущему URL
            # В redis-py пул не хранит URL напрямую в доступном виде, 
            # но мы сбрасываем self._pool при обновлении self.url
            pass

        if self._pool is None:
            try:
                # [SINGULARITY 24.3] Используем self.url, который мы обновили
                self._pool = redis.ConnectionPool.from_url(
                    self.url, max_connections=20, decode_responses=True
                )
                logger.info(f"✅ [REDIS] Пул соединений создан: {self.url}")
                print(f"DEBUG: [REDIS_MANAGER] ConnectionPool created for {self.url}")
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
            # Приведение ttl к int для предотвращения ошибок Redis (ex must be int)
            ttl_int = int(float(ttl)) if ttl is not None else 3600
            await client.set(f"cache:{key}", val, ex=ttl_int)
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
    async def update_task_status(
        self, task_id: str, status: str, result: Any = None, metadata: Dict = None
    ):
        """Обновляет состояние задачи в Redis (для мгновенного доступа Gateway)."""
        try:
            client = await self.get_client()
            data = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
            if result is not None:
                data["result"] = result
            if metadata:
                data["metadata"] = metadata

            await client.hset(
                f"task:{task_id}", mapping={k: json.dumps(v) for k, v in data.items()}
            )
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
                is_locked = await client.set(
                    lock_key, "processing", ex=_TASK_DEDUP_LOCK_TTL, nx=True
                )
                if not is_locked:
                    logger.warning(f"🚫 [REDIS] Дубликат задачи {task_id} проигнорирован")
                    return False

            # Сингулярность 10.0: Добавляем время создания и метаданные для RAG
            data["created_at"] = datetime.now(timezone.utc).isoformat()

            # Если в данных есть ключевые слова AI, помечаем для воркера
            goal = data.get("description", "").lower()
            if any(
                kw in goal
                for kw in ["anthropic", "google", "openai", "deepseek", "claude", "gemini"]
            ):
                data["rag_domain"] = "AI Research"

            # Ограничиваем длину потока 10000 записей (мировая практика)
            await client.xadd(f"stream:{stream_name}", {"payload": json.dumps(data)}, maxlen=10000)
            logger.info(f"📥 [REDIS] Задача {task_id} добавлена в поток {stream_name}")
            return True
        except Exception as e:
            logger.error(f"❌ [REDIS] Ошибка записи в поток {stream_name}: {e}")
            return False

    async def autoclaim_tasks(
        self, stream_name: str, group_name: str, consumer_name: str, min_idle_time_ms: int = 60000
    ):
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
                count=5,
            )
            if res and res[1]:
                logger.info(
                    f"🔄 [REDIS] Перехвачено {len(res[1])} зависших задач из потока {stream_name}"
                )
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

    # --- GLOBAL OLLAMA SEMAPHORE ---
    # Limits concurrent Ollama requests across ALL containers to prevent 503 overload.
    # Pattern: Redis INCR/DECR counter with safety TTL (used by knowledge_os_worker via local_router.py).
    # If Redis is unavailable, falls back to True (allow request) for graceful degradation.
    _OLLAMA_SEM_KEY = "ollama:global_slots"
    _OLLAMA_MAX_SLOTS = int(os.getenv("OLLAMA_GLOBAL_MAX_SLOTS", "5"))  # 6 NUM_PARALLEL − 1 buffer

    async def reset_ollama_slots(self) -> None:
        """
        Reset the global Ollama semaphore counter to 0 on worker startup.
        Анна (QA): prevents stale counters after kill-9 (slots not released) from blocking new requests.
        Call this once during worker initialization — safe only if a single worker process initialises.
        """
        try:
            client = await self.get_client()
            await client.set(self._OLLAMA_SEM_KEY, 0)
            logger.info("🔄 [REDIS] Ollama global slots counter reset to 0 on startup")
        except Exception as e:
            logger.warning("[REDIS] reset_ollama_slots failed (%s), continuing without reset", e)

    async def acquire_ollama_slot(self) -> bool:
        """
        Claim one of _OLLAMA_MAX_SLOTS globally shared Ollama request slots.
        Returns True if slot acquired, False if all slots are taken.
        Redis unavailable → returns True (fail-open for graceful degradation).
        """
        try:
            client = await self.get_client()
            count = await client.incr(self._OLLAMA_SEM_KEY)
            await client.expire(self._OLLAMA_SEM_KEY, 60)  # safety TTL in case of crashes
            if count <= self._OLLAMA_MAX_SLOTS:
                return True
            await client.decr(self._OLLAMA_SEM_KEY)  # over limit — release immediately
            return False
        except Exception as e:
            logger.debug("[REDIS] acquire_ollama_slot failed (%s), allowing request", e)
            return True  # Redis down → degrade gracefully

    async def release_ollama_slot(self) -> None:
        """Release a previously acquired Ollama slot."""
        try:
            client = await self.get_client()
            val = await client.decr(self._OLLAMA_SEM_KEY)
            if val < 0:
                await client.set(self._OLLAMA_SEM_KEY, 0)  # guard against negative counter
        except Exception as e:
            logger.debug("[REDIS] release_ollama_slot failed (%s), ignoring", e)

    async def close(self):
        """Закрывает пул соединений."""
        if self._pool:
            await self._pool.disconnect()
            logger.info("🛑 [REDIS] Пул соединений закрыт")


# Синглтон для удобного импорта
redis_manager = RedisManager()
