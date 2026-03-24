"""
Translator: Система мультиязычности и переводов

Функционал:
- Автоматический перевод знаний
- Локализация интерфейса
- Мультиязычный поиск
- Определение языка
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

# Поддерживаемые языки
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ru": "Русский",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
    "pt": "Português",
    "it": "Italiano",
}

# API для перевода (можно использовать OpenAI, Google Translate, DeepL)
TRANSLATION_API_URL = os.getenv("TRANSLATION_API_URL", "")
TRANSLATION_API_KEY = os.getenv("TRANSLATION_API_KEY", "")


class LanguageDetector:
    """Определение языка текста"""

    @staticmethod
    def detect_language(text: str) -> str:
        """Простое определение языка по символам"""
        # Проверка на кириллицу (русский)
        if any("\u0400" <= char <= "\u04ff" for char in text):
            return "ru"

        # Проверка на китайские иероглифы
        if any("\u4e00" <= char <= "\u9fff" for char in text):
            return "zh"

        # Проверка на японские символы
        if any("\u3040" <= char <= "\u309f" or "\u30a0" <= char <= "\u30ff" for char in text):
            return "ja"

        # Проверка на корейские символы
        if any("\uac00" <= char <= "\ud7a3" for char in text):
            return "ko"

        # По умолчанию английский
        return "en"


class KnowledgeTranslator:
    """Класс для перевода знаний"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.language_detector = LanguageDetector()

    async def translate_knowledge(
        self, knowledge_id: str, target_language: str, source_language: Optional[str] = None
    ) -> Optional[str]:
        """Перевод знания на целевой язык"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Получаем оригинальное знание
                knowledge = await conn.fetchrow(
                    """
                    SELECT id, content
                    FROM knowledge_nodes
                    WHERE id = $1
                """,
                    knowledge_id,
                )

                if not knowledge:
                    return None

                # Определяем исходный язык, если не указан
                if not source_language:
                    source_language = self.language_detector.detect_language(knowledge["content"])

                # Если языки совпадают, возвращаем оригинал
                if source_language == target_language:
                    return knowledge["content"]

                # Проверяем, есть ли уже перевод
                existing = await conn.fetchrow(
                    """
                    SELECT translated_content
                    FROM knowledge_translations
                    WHERE knowledge_node_id = $1 AND language_code = $2
                """,
                    knowledge_id,
                    target_language,
                )

                if existing:
                    return existing["translated_content"]

                # Выполняем перевод
                translated_text = await self._translate_text(
                    knowledge["content"], source_language, target_language
                )

                if not translated_text:
                    return None

                # Сохраняем перевод
                await conn.execute(
                    """
                    INSERT INTO knowledge_translations
                    (knowledge_node_id, language_code, translated_content, translation_source, translation_confidence)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (knowledge_node_id, language_code)
                    DO UPDATE SET
                        translated_content = EXCLUDED.translated_content,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    knowledge_id,
                    target_language,
                    translated_text,
                    "auto",
                    0.9,
                )

                logger.info(f"✅ Translated knowledge {knowledge_id} to {target_language}")
                return translated_text
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error translating knowledge: {e}")
            return None

    async def _translate_text(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """Перевод текста через API"""
        # Если нет API, используем простую заглушку
        if not TRANSLATION_API_URL:
            logger.warning("Translation API not configured, using placeholder")
            return f"[{target_lang}] {text}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    TRANSLATION_API_URL,
                    json={
                        "text": text,
                        "source_language": source_lang,
                        "target_language": target_lang,
                    },
                    headers={"Authorization": f"Bearer {TRANSLATION_API_KEY}"},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    return response.json().get("translated_text")
                else:
                    logger.error(f"Translation API error: {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return None

    async def translate_batch(
        self, knowledge_ids: List[str], target_language: str
    ) -> Dict[str, str]:
        """Пакетный перевод знаний"""
        results = {}

        for knowledge_id in knowledge_ids:
            translated = await self.translate_knowledge(knowledge_id, target_language)
            if translated:
                results[knowledge_id] = translated
            await asyncio.sleep(0.1)  # Rate limiting

        return results

    async def get_translation(self, knowledge_id: str, language: str) -> Optional[str]:
        """Получение перевода знания"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                translated = await conn.fetchval(
                    """
                    SELECT get_knowledge_translation($1, $2)
                """,
                    knowledge_id,
                    language,
                )
                return translated
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error getting translation: {e}")
            return None


class UILocalizer:
    """Класс для локализации интерфейса"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self._cache: Dict[str, Dict[str, str]] = {}

    async def get_translation(
        self, key: str, language: str = "en", context: Optional[str] = None
    ) -> str:
        """Получение перевода для ключа интерфейса"""
        try:
            # Проверяем кэш
            cache_key = f"{language}:{context or 'default'}:{key}"
            if cache_key in self._cache:
                return self._cache[cache_key].get(key, key)

            conn = await asyncpg.connect(self.db_url)
            try:
                query = """
                    SELECT translation_value
                    FROM ui_translations
                    WHERE language_code = $1 AND translation_key = $2
                """
                params = [language, key]

                if context:
                    query += " AND context = $3"
                    params.append(context)
                else:
                    query += " AND context IS NULL"

                translated = await conn.fetchval(query, *params)

                if translated:
                    # Кэшируем
                    if language not in self._cache:
                        self._cache[language] = {}
                    self._cache[language][key] = translated
                    return translated

                # Если перевода нет, возвращаем ключ
                return key
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error getting UI translation: {e}")
            return key

    async def set_translation(
        self, key: str, value: str, language: str, context: Optional[str] = None
    ) -> bool:
        """Установка перевода для ключа"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute(
                    """
                    INSERT INTO ui_translations (language_code, translation_key, translation_value, context)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (language_code, translation_key, context)
                    DO UPDATE SET translation_value = EXCLUDED.translation_value
                """,
                    language,
                    key,
                    value,
                    context,
                )

                # Инвалидируем кэш
                if language in self._cache:
                    self._cache[language].pop(key, None)

                return True
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error setting UI translation: {e}")
            return False


class MultilingualSearch:
    """Мультиязычный поиск"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.language_detector = LanguageDetector()

    async def search(
        self, query: str, language: str = "auto", domain: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Мультиязычный поиск знаний"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Определяем язык, если auto
                if language == "auto":
                    language = self.language_detector.detect_language(query)

                # Выполняем поиск
                if domain:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM search_knowledge_multilang($1, $2, $3)
                        WHERE domain_name = $4
                    """,
                        query,
                        language,
                        limit,
                        domain,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM search_knowledge_multilang($1, $2, $3)
                    """,
                        query,
                        language,
                        limit,
                    )

                return [dict(row) for row in rows]
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error in multilingual search: {e}")
            return []


async def run_auto_translation_cycle():
    """Автоматический цикл перевода знаний"""
    logger.info("🌍 Starting auto-translation cycle...")

    translator = KnowledgeTranslator()
    conn = await asyncpg.connect(DB_URL)

    try:
        # Получаем знания без переводов на популярные языки
        target_languages = ["en", "ru", "es", "fr", "de"]

        for lang in target_languages:
            # Находим знания без переводов на этот язык
            knowledge_to_translate = await conn.fetch(
                """
                SELECT k.id, k.content
                FROM knowledge_nodes k
                LEFT JOIN knowledge_translations kt ON k.id = kt.knowledge_node_id
                    AND kt.language_code = $1
                WHERE kt.id IS NULL
                ORDER BY k.confidence_score DESC
                LIMIT 10
            """,
                lang,
            )

            logger.info(f"Translating {len(knowledge_to_translate)} knowledge nodes to {lang}")

            for knowledge in knowledge_to_translate:
                await translator.translate_knowledge(str(knowledge["id"]), lang)
                await asyncio.sleep(0.5)  # Rate limiting

        logger.info("✅ Auto-translation cycle completed")
    except Exception as e:
        logger.error(f"Auto-translation error: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_auto_translation_cycle())
