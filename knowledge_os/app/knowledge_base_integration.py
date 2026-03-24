"""
Интеграция базы знаний для всех агентов
Обеспечивает автоматический доступ к знаниям корпорации через knowledge_nodes
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False


async def get_corporation_knowledge_context(query: str, limit: int = 5) -> str:
    """
    Получить релевантный контекст из базы знаний корпорации

    Args:
        query: Поисковый запрос
        limit: Количество результатов

    Returns:
        Форматированный контекст для использования в промптах
    """
    if not ASYNCPG_AVAILABLE:
        return ""

    try:
        # Импортируем get_embedding
        try:
            from app.main import get_embedding
        except ImportError:
            try:
                from app.enhanced_search import get_embedding
            except ImportError:
                logger.debug("get_embedding недоступен")
                return ""

        # Получаем эмбеддинг запроса
        embedding = await get_embedding(query)
        if not embedding:
            return ""

        # Подключаемся к БД
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
        conn = await asyncpg.connect(db_url)

        try:
            # Ищем релевантные знания корпорации
            rows = await conn.fetch(
                """
                SELECT content, metadata, (1 - (embedding <=> $1::vector)) as similarity
                FROM knowledge_nodes
                WHERE embedding IS NOT NULL
                AND metadata->>'source' = 'corporation_knowledge_system'
                AND confidence_score >= 0.8
                ORDER BY similarity DESC
                LIMIT $2
            """,
                str(embedding),
                limit,
            )

            if not rows:
                return ""

            # Форматируем контекст
            context_parts = ["📚 ЗНАНИЯ КОРПОРАЦИИ:"]
            for row in rows:
                if row["similarity"] >= 0.5:  # Минимальный порог релевантности
                    metadata = row["metadata"] or {}
                    knowledge_type = metadata.get("type", "unknown")
                    context_parts.append(
                        f"\n[{knowledge_type}] (релевантность: {row['similarity']:.2f}):"
                    )
                    context_parts.append(row["content"])

            return "\n".join(context_parts)
        finally:
            await conn.close()
    except Exception as e:
        logger.debug(f"Ошибка получения контекста знаний корпорации: {e}")
        return ""


async def ensure_knowledge_base_accessible():
    """
    Проверить доступность базы знаний для всех агентов
    """
    if not ASYNCPG_AVAILABLE:
        logger.warning("⚠️ asyncpg недоступен, база знаний не будет использоваться")
        return False

    try:
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
        conn = await asyncpg.connect(db_url, timeout=3.0)
        try:
            # Проверяем наличие таблицы knowledge_nodes
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'knowledge_nodes'
                )
            """)

            if not exists:
                logger.error("❌ Таблица knowledge_nodes не существует!")
                return False

            # Проверяем наличие знаний корпорации
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM knowledge_nodes
                WHERE metadata->>'source' = 'corporation_knowledge_system'
            """)

            logger.info(f"✅ База знаний доступна. Узлов знаний корпорации: {count}")
            return True
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"❌ База знаний недоступна: {e}")
        return False


def add_knowledge_context_to_prompt(base_prompt: str, query: str = None) -> str:
    """
    Добавить контекст знаний к промпту (синхронная версия для использования в async функциях)

    Args:
        base_prompt: Базовый промпт
        query: Запрос для поиска релевантных знаний

    Returns:
        Промпт с добавленным контекстом знаний
    """
    # Добавляем инструкцию об использовании базы знаний
    knowledge_instruction = """

📚 ДОСТУП К БАЗЕ ЗНАНИЙ:
- Используй search_knowledge(query) для поиска информации в базе знаний
- Все знания корпорации (модели, скрипты, изменения) доступны через базу знаний
- База знаний автоматически обновляется и содержит актуальную информацию
"""

    return base_prompt + knowledge_instruction
