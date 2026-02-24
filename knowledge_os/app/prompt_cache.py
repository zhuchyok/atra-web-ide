"""
Prompt Cache - Кэширование промптов для ускорения работы моделей
Экономит до 90% времени и токенов на повторяющихся запросах
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
CACHE_TTL_HOURS = 24  # Время жизни кэша


class PromptCache:
    """Кэширование промптов для ускорения работы моделей"""

    def __init__(self, db_url: str = DB_URL, ttl_hours: int = CACHE_TTL_HOURS):
        self.db_url = db_url
        self.ttl_hours = ttl_hours
        self._memory_cache: Dict[str, Dict] = {}  # In-memory кэш
        self._cache_size = 1000  # Максимум записей в памяти

    def _get_prompt_hash(self, prompt: str, model_name: str) -> str:
        """Создать хеш промпта"""
        content = f"{model_name}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get_cached_response(self, prompt: str, model_name: str) -> Optional[str]:
        """
        Получить кэшированный ответ

        Args:
            prompt: Промпт
            model_name: Имя модели

        Returns:
            Кэшированный ответ или None
        """
        prompt_hash = self._get_prompt_hash(prompt, model_name)

        # Проверяем memory cache
        if prompt_hash in self._memory_cache:
            cached = self._memory_cache[prompt_hash]
            if datetime.now(timezone.utc) - cached["timestamp"] < timedelta(hours=self.ttl_hours):
                logger.debug(f"✅ [PROMPT CACHE] Memory hit: {prompt[:50]}...")
                return cached["response"]
            else:
                # Устарел, удаляем
                del self._memory_cache[prompt_hash]

        # Проверяем БД кэш
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'prompt_cache'
                    )
                """)

                if not table_exists:
                    await self._create_cache_table(conn)
                    return None

                row = await conn.fetchrow(
                    """
                    SELECT response, created_at
                    FROM prompt_cache
                    WHERE prompt_hash = $1
                    AND model_name = $2
                    AND created_at > NOW() - INTERVAL '1 hour' * $3
                """,
                    prompt_hash,
                    model_name,
                    self.ttl_hours,
                )

                if row:
                    response = row["response"]
                    # Сохраняем в memory cache
                    if len(self._memory_cache) >= self._cache_size:
                        # Удаляем старые (FIFO)
                        oldest_key = next(iter(self._memory_cache))
                        del self._memory_cache[oldest_key]

                    self._memory_cache[prompt_hash] = {
                        "response": response,
                        "timestamp": row["created_at"],
                    }

                    logger.info(f"✅ [PROMPT CACHE] DB hit: {prompt[:50]}...")
                    return response

            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ [PROMPT CACHE] Ошибка получения из БД: {e}")

        return None

    async def save_cached_response(self, prompt: str, model_name: str, response: str):
        """
        Сохранить ответ в кэш

        Args:
            prompt: Промпт
            model_name: Имя модели
            response: Ответ модели
        """
        prompt_hash = self._get_prompt_hash(prompt, model_name)

        # Сохраняем в memory cache
        if len(self._memory_cache) >= self._cache_size:
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]

        self._memory_cache[prompt_hash] = {
            "response": response,
            "timestamp": datetime.now(timezone.utc),
        }

        # Сохраняем в БД
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'prompt_cache'
                    )
                """)

                if not table_exists:
                    await self._create_cache_table(conn)

                await conn.execute(
                    """
                    INSERT INTO prompt_cache (prompt_hash, model_name, prompt, response, created_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (prompt_hash, model_name)
                    DO UPDATE SET
                        response = EXCLUDED.response,
                        created_at = NOW()
                """,
                    prompt_hash,
                    model_name,
                    prompt[:1000],
                    response[:10000],
                )  # Ограничиваем размер

                logger.debug(f"💾 [PROMPT CACHE] Сохранен: {prompt[:50]}...")

            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ [PROMPT CACHE] Ошибка сохранения в БД: {e}")

    async def _create_cache_table(self, conn: asyncpg.Connection):
        """Создать таблицу для кэша промптов"""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS prompt_cache (
                prompt_hash VARCHAR(64) NOT NULL,
                model_name VARCHAR(255) NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                PRIMARY KEY (prompt_hash, model_name)
            );

            CREATE INDEX IF NOT EXISTS idx_prompt_cache_created_at
            ON prompt_cache(created_at);

            CREATE INDEX IF NOT EXISTS idx_prompt_cache_model
            ON prompt_cache(model_name);
        """)
        logger.info("✅ Таблица prompt_cache создана")

    async def clear_old_cache(self, days: int = 7):
        """Очистить старый кэш"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                deleted = await conn.execute(
                    """
                    DELETE FROM prompt_cache
                    WHERE created_at < NOW() - INTERVAL '1 day' * $1
                """,
                    days,
                )

                logger.info(f"🗑️ [PROMPT CACHE] Удалено старых записей: {deleted.split()[-1]}")
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ [PROMPT CACHE] Ошибка очистки: {e}")


async def main():
    """Пример использования"""
    cache = PromptCache()

    # Проверяем кэш
    cached = await cache.get_cached_response("Как работает система?", "qwen2.5-coder:32b")

    if cached:
        print(f"✅ Найден в кэше: {cached[:100]}...")
    else:
        print("❌ Не найдено в кэше")
        # Сохраняем ответ
        await cache.save_cached_response(
            "Как работает система?", "qwen2.5-coder:32b", "Система работает следующим образом..."
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
