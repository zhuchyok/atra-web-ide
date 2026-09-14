"""
Feedback Loop — система обучения Victoria на собственных ошибках.

Запоминает:
- Какую ошибку нашла
- Как её исправила
- Помогло ли исправление
- Как избежать в будущем

Хранит в PostgreSQL + LanceDB для быстрого поиска.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

# Database URL
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os",
)

# Feedback retention days
FEEDBACK_RETENTION_DAYS = int(os.getenv("FEEDBACK_RETENTION_DAYS", "90"))


class FeedbackLoop:
    """
    Система обратной связи для Victoria.

    Цикл:
    1. Ошибка обнаружена → запись в feedback_log
    2. Исправление применено → запись в feedback_log
    3. Через N минут проверяем: повторялась ли ошибка?
    4. Если нет → исправление помогло → сохраняем паттерн
    5. Если да → исправление не помогло → пробуем другое
    """

    def __init__(self):
        self.conn: Optional[asyncpg.Connection] = None
        self._initialized = False

    async def initialize(self):
        """Инициализация таблиц в PostgreSQL."""
        if self._initialized:
            return

        try:
            self.conn = await asyncpg.connect(DB_URL)

            # Таблица логов обратной связи
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_log (
                    id SERIAL PRIMARY KEY,
                    error_id VARCHAR(64) NOT NULL,
                    container VARCHAR(128) NOT NULL,
                    error_type VARCHAR(128) NOT NULL,
                    error_message TEXT NOT NULL,
                    error_hash VARCHAR(64) NOT NULL,
                    action_taken TEXT,
                    action_result VARCHAR(32) DEFAULT 'pending',
                    resolution_time_seconds FLOAT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    resolved_at TIMESTAMP,
                    verified_at TIMESTAMP,
                    was_successful BOOLEAN,
                    pattern_id VARCHAR(64)
                )
            """)

            # Таблица паттернов ошибок
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS error_patterns (
                    id SERIAL PRIMARY KEY,
                    pattern_id VARCHAR(64) UNIQUE NOT NULL,
                    container VARCHAR(128),
                    error_type VARCHAR(128) NOT NULL,
                    error_signature TEXT NOT NULL,
                    error_hash VARCHAR(64),
                    count INTEGER DEFAULT 1,
                    last_seen TIMESTAMP DEFAULT NOW(),
                    first_seen TIMESTAMP DEFAULT NOW(),
                    successful_fixes INTEGER DEFAULT 0,
                    failed_fixes INTEGER DEFAULT 0,
                    best_fix TEXT,
                    avg_resolution_time FLOAT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Таблица aprendizaje (что Victoria выучила)
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS victoria_lessons (
                    id SERIAL PRIMARY KEY,
                    lesson_type VARCHAR(64) NOT NULL,
                    pattern_id VARCHAR(64),
                    lesson TEXT NOT NULL,
                    confidence FLOAT DEFAULT 0.5,
                    times_applied INTEGER DEFAULT 0,
                    times_successful INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_applied TIMESTAMP
                )
            """)

            # Индексы
            await self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_error_hash
                ON feedback_log(error_hash)
            """)
            await self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_container
                ON feedback_log(container, created_at)
            """)
            await self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_container
                ON error_patterns(container, error_type)
            """)

            self._initialized = True
            logger.info("✅ [FEEDBACK] Инициализирована feedback loop система")

        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Ошибка инициализации: {e}")
            self._initialized = False

    def _make_error_hash(self, container: str, error_type: str, message: str) -> str:
        """Создать хеш ошибки для дедупликации и поиска паттернов."""
        import hashlib
        key = f"{container}:{error_type}:{message[:200]}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    async def log_error(
        self,
        container: str,
        error_type: str,
        error_message: str,
        context: Optional[Dict] = None,
    ) -> str:
        """
        Записать обнаруженную ошибку.
        Возвращает error_id для отслеживания.
        """
        if not self._initialized:
            await self.initialize()
        if not self.conn:
            return ""

        error_hash = self._make_error_hash(container, error_type, error_message)

        try:
            # Проверяем есть ли уже такой паттерн
            existing = await self.conn.fetchrow(
                "SELECT pattern_id, count FROM error_patterns WHERE error_hash = $1",
                error_hash,
            )

            if existing:
                # Увеличиваем счетчик
                await self.conn.execute(
                    "UPDATE error_patterns SET count = count + 1, last_seen = NOW() WHERE error_hash = $1",
                    error_hash,
                )
                pattern_id = existing["pattern_id"]
            else:
                # Создаем новый паттерн
                pattern_id = f"pat_{error_hash}"
                await self.conn.execute(
                    """
                    INSERT INTO error_patterns (pattern_id, container, error_type, error_signature, error_hash)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    pattern_id,
                    container,
                    error_type,
                    error_message[:500],
                    error_hash,
                )

            # Записываем в лог
            error_id = f"err_{int(time.time())}_{error_hash[:8]}"
            await self.conn.execute(
                """
                INSERT INTO feedback_log (error_id, container, error_type, error_message, error_hash, pattern_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                error_id,
                container,
                error_type,
                error_message[:1000],
                error_hash,
                pattern_id,
            )

            logger.info(
                f"📝 [FEEDBACK] Ошибка записана: {error_id} | {container}/{error_type} | pattern={pattern_id}"
            )
            return error_id

        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Ошибка записи: {e}")
            return ""

    async def log_fix(
        self,
        error_id: str,
        action_taken: str,
        action_result: str = "applied",
    ):
        """Записать примененное исправление."""
        if not self._initialized or not self.conn:
            return

        try:
            await self.conn.execute(
                """
                UPDATE feedback_log
                SET action_taken = $1, action_result = $2, resolved_at = NOW()
                WHERE error_id = $3
                """,
                action_taken,
                action_result,
                error_id,
            )
            logger.info(f"🔧 [FEEDBACK] Исправление записано: {error_id} → {action_result}")

        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Ошибка записи fix: {e}")

    async def verify_fix(self, error_id: str, wait_minutes: int = 5) -> bool:
        """
        Проверить помогло ли исправление.
        Ждет wait_minutes и проверяет повторялась ли ошибка.
        """
        if not self._initialized or not self.conn:
            return False

        try:
            # Получаем информацию об ошибке
            error_info = await self.conn.fetchrow(
                "SELECT error_hash, container FROM feedback_log WHERE error_id = $1",
                error_id,
            )
            if not error_info:
                return False

            # Ждем
            await asyncio.sleep(wait_minutes * 60)

            # Проверяем повторялась ли ошибка после исправления
            repeats = await self.conn.fetchval(
                """
                SELECT COUNT(*) FROM feedback_log
                WHERE error_hash = $1
                AND created_at > (SELECT resolved_at FROM feedback_log WHERE error_id = $2)
                """,
                error_info["error_hash"],
                error_id,
            )

            success = repeats == 0

            # Обновляем запись
            await self.conn.execute(
                """
                UPDATE feedback_log
                SET was_successful = $1, verified_at = NOW()
                WHERE error_id = $2
                """,
                success,
                error_id,
            )

            # Обновляем статистику паттерна
            if success:
                await self.conn.execute(
                    """
                    UPDATE error_patterns
                    SET successful_fixes = successful_fixes + 1
                    WHERE error_hash = $1
                    """,
                    error_info["error_hash"],
                )
            else:
                await self.conn.execute(
                    """
                    UPDATE error_patterns
                    SET failed_fixes = failed_fixes + 1
                    WHERE error_hash = $1
                    """,
                    error_info["error_hash"],
                )

            logger.info(
                f"{'✅' if success else '❌'} [FEEDBACK] Верификация {error_id}: "
                f"{'помогло' if success else 'не помогло'} (повторений: {repeats})"
            )
            return success

        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Ошибка верификации: {e}")
            return False

    async def get_best_fix(self, container: str, error_type: str) -> Optional[Dict]:
        """Получить лучшее известное исправление для типа ошибки."""
        if not self._initialized or not self.conn:
            return None

        try:
            pattern = await self.conn.fetchrow(
                """
                SELECT * FROM error_patterns
                WHERE container = $1 AND error_type = $2
                AND successful_fixes > 0
                ORDER BY successful_fixes DESC, count DESC
                LIMIT 1
                """,
                container,
                error_type,
            )
            return dict(pattern) if pattern else None

        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Ошибка поиска fix: {e}")
            return None

    async def get_stats(self) -> Dict:
        """Получить статистику feedback loop."""
        if not self._initialized or not self.conn:
            return {}

        try:
            total_errors = await self.conn.fetchval("SELECT COUNT(*) FROM feedback_log")
            total_fixes = await self.conn.fetchval(
                "SELECT COUNT(*) FROM feedback_log WHERE action_taken IS NOT NULL"
            )
            successful_fixes = await self.conn.fetchval(
                "SELECT COUNT(*) FROM feedback_log WHERE was_successful = TRUE"
            )
            total_patterns = await self.conn.fetchval("SELECT COUNT(*) FROM error_patterns")

            return {
                "total_errors": total_errors,
                "total_fixes": total_fixes,
                "successful_fixes": successful_fixes,
                "fix_success_rate": round(successful_fixes / max(total_fixes, 1) * 100, 1),
                "total_patterns": total_patterns,
            }

        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Ошибка получения stats: {e}")
            return {}

    async def learn_from_fix(self, pattern_id: str, lesson: str, confidence: float = 0.7):
        """Записать урок из исправления."""
        if not self._initialized or not self.conn:
            return

        try:
            await self.conn.execute(
                """
                INSERT INTO victoria_lessons (lesson_type, pattern_id, lesson, confidence)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
                """,
                "fix_lesson",
                pattern_id,
                lesson,
                confidence,
            )
            logger.info(f"📚 [FEEDBACK] Урок записан: {lesson[:50]}...")

        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Ошибка записи урока: {e}")

    async def get_lessons_for_error(self, container: str, error_type: str) -> List[Dict]:
        """Получить уроки для конкретного типа ошибки."""
        if not self._initialized or not self.conn:
            return []

        try:
            lessons = await self.conn.fetch(
                """
                SELECT * FROM victoria_lessons vl
                JOIN error_patterns ep ON vl.pattern_id = ep.pattern_id
                WHERE ep.container = $1 AND ep.error_type = $2
                ORDER BY vl.confidence DESC, vl.times_successful DESC
                LIMIT 5
                """,
                container,
                error_type,
            )
            return [dict(l) for l in lessons]

        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Ошибка получения уроков: {e}")
            return []

    async def cleanup_old_data(self):
        """Очистить старые данные."""
        if not self._initialized or not self.conn:
            return

        try:
            deleted = await self.conn.execute(
                """
                DELETE FROM feedback_log
                WHERE created_at < NOW() - INTERVAL '%s days'
                """,
                FEEDBACK_RETENTION_DAYS,
            )
            logger.info(f"🧹 [FEEDBACK] Очищено старых записей: {deleted}")

        except Exception as e:
            logger.error(f"❌ [FEEDBACK] Ошибка очистки: {e}")


# Singleton
_feedback_loop: Optional[FeedbackLoop] = None


def get_feedback_loop() -> FeedbackLoop:
    """Получить singleton FeedbackLoop."""
    global _feedback_loop
    if _feedback_loop is None:
        _feedback_loop = FeedbackLoop()
    return _feedback_loop
