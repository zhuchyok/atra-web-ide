"""
Auto Prompt Optimizer для автоматической оптимизации системных промптов.
Анализирует успешные диалоги и предлагает улучшения для system_prompt.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


@dataclass
class PromptImprovement:
    """Предложение по улучшению промпта"""

    original_prompt: str
    improved_prompt: str
    improvement_reason: str
    expected_impact: str  # 'high', 'medium', 'low'
    confidence: float  # 0.0 - 1.0


class AutoPromptOptimizer:
    """
    Автономный оптимизатор промптов.
    Анализирует успешные диалоги и предлагает улучшения.
    """

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.improvement_history: List[PromptImprovement] = []

    async def analyze_top_dialogues(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Анализирует топ-N успешных диалогов (из кэша и feedback)"""
        if not ASYNCPG_AVAILABLE:
            return []

        dialogues = []

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # 1. Получаем успешные диалоги из кэша
                rows = await conn.fetch(
                    """
                    SELECT
                        query_text,
                        response_text,
                        performance_score,
                        routing_source,
                        created_at
                    FROM semantic_ai_cache
                    WHERE performance_score >= 0.8
                    AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY performance_score DESC, last_used_at DESC
                    LIMIT $1
                """,
                    limit,
                )

                for row in rows:
                    dialogues.append(
                        {
                            "query": row["query_text"],
                            "response": row["response_text"],
                            "performance_score": float(row["performance_score"]),
                            "routing_source": row.get("routing_source", ""),
                            "created_at": row["created_at"].isoformat()
                            if row["created_at"]
                            else None,
                            "source": "cache",
                        }
                    )

                # 2. Получаем позитивный feedback от пользователей (Singularity 8.0)
                feedback_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'user_feedback'
                    )
                """)

                if feedback_exists:
                    feedback_rows = await conn.fetch(
                        """
                        SELECT
                            query_text,
                            response_text,
                            expert_name,
                            created_at
                        FROM user_feedback
                        WHERE feedback_type = 'positive'
                        AND created_at > NOW() - INTERVAL '7 days'
                        ORDER BY created_at DESC
                        LIMIT $1
                    """,
                        limit,
                    )

                    for row in feedback_rows:
                        dialogues.append(
                            {
                                "query": row["query_text"],
                                "response": row["response_text"],
                                "performance_score": 1.0,  # Позитивный feedback = высокий score
                                "routing_source": "user_feedback",
                                "expert_name": row["expert_name"],
                                "created_at": row["created_at"].isoformat()
                                if row["created_at"]
                                else None,
                                "source": "user_feedback",
                            }
                        )

                # Сортируем по performance_score
                dialogues.sort(key=lambda x: x.get("performance_score", 0), reverse=True)
                return dialogues[:limit]
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ Ошибка анализа диалогов: {e}")
            return []

    async def analyze_negative_feedback(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Анализирует негативный feedback для выявления проблем (Singularity 8.0)"""
        if not ASYNCPG_AVAILABLE:
            return []

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы user_feedback
                feedback_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'user_feedback'
                    )
                """)

                if not feedback_exists:
                    return []

                # Получаем негативный feedback
                rows = await conn.fetch(
                    """
                    SELECT
                        query_text,
                        response_text,
                        expert_name,
                        comment,
                        metadata,
                        created_at
                    FROM user_feedback
                    WHERE feedback_type = 'negative'
                    AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY created_at DESC
                    LIMIT $1
                """,
                    limit,
                )

                negative_feedback = []
                for row in rows:
                    negative_feedback.append(
                        {
                            "query": row["query_text"],
                            "response": row["response_text"],
                            "expert_name": row["expert_name"],
                            "comment": row.get("comment", ""),
                            "metadata": row.get("metadata", {}),
                            "created_at": row["created_at"].isoformat()
                            if row["created_at"]
                            else None,
                        }
                    )

                return negative_feedback
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ Ошибка анализа негативного feedback: {e}")
            return []

    def extract_patterns(self, dialogues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Извлекает паттерны из успешных диалогов"""
        patterns = {
            "common_phrases": {},
            "successful_structures": [],
            "effective_keywords": {},
            "response_patterns": [],
        }

        for dialogue in dialogues:
            query = dialogue.get("query", "").lower()
            response = dialogue.get("response", "")
            system_prompt = dialogue.get("system_prompt", "")

            # Анализируем структуру запросов
            if "как" in query or "почему" in query:
                patterns["common_phrases"]["how_why"] = (
                    patterns["common_phrases"].get("how_why", 0) + 1
                )

            if "пример" in query or "код" in query:
                patterns["common_phrases"]["example_code"] = (
                    patterns["common_phrases"].get("example_code", 0) + 1
                )

            # Анализируем успешные структуры ответов
            if response.startswith("✅") or response.startswith("🎯"):
                patterns["successful_structures"].append("emoji_start")

            if "```" in response:  # Код блоки
                patterns["successful_structures"].append("code_blocks")

            # Извлекаем ключевые слова из system_prompt
            if system_prompt:
                keywords = self._extract_keywords_from_prompt(system_prompt)
                for keyword in keywords:
                    patterns["effective_keywords"][keyword] = (
                        patterns["effective_keywords"].get(keyword, 0) + 1
                    )

        return patterns

    def _extract_keywords_from_prompt(self, prompt: str) -> List[str]:
        """Извлекает ключевые слова из промпта"""
        # Ищем важные инструкции
        keywords = []
        important_phrases = [
            "кратко",
            "лаконично",
            "по делу",
            "структурированно",
            "с примерами",
            "с кодом",
            "детально",
            "профессионально",
        ]

        prompt_lower = prompt.lower()
        for phrase in important_phrases:
            if phrase in prompt_lower:
                keywords.append(phrase)

        return keywords

    async def suggest_improvements(
        self, current_prompt: str, expert_name: str = "Виктория"
    ) -> List[PromptImprovement]:
        """Предлагает улучшения для системного промпта на основе успешных диалогов и feedback"""
        # Анализируем топ диалоги
        top_dialogues = await self.analyze_top_dialogues(limit=10)

        # Анализируем негативный feedback (Singularity 8.0)
        negative_feedback = await self.analyze_negative_feedback(limit=10)

        if not top_dialogues and not negative_feedback:
            logger.warning("⚠️ Нет данных для анализа")
            return []

        # Извлекаем паттерны
        patterns = self.extract_patterns(top_dialogues)

        improvements = []

        # Анализ негативного feedback для выявления проблем
        if negative_feedback:
            # Анализируем общие проблемы в негативном feedback
            common_issues = []
            for feedback in negative_feedback:
                comment = feedback.get("comment", "").lower()
                query = feedback.get("query", "").lower()

                if any(kw in comment or kw in query for kw in ["неправильно", "ошибка", "неверно"]):
                    common_issues.append("accuracy")
                elif any(
                    kw in comment or kw in query for kw in ["непонятно", "неясно", "запутанно"]
                ):
                    common_issues.append("clarity")
                elif any(kw in comment or kw in query for kw in ["долго", "медленно", "медленнее"]):
                    common_issues.append("speed")

            # Предложения на основе проблем
            if "accuracy" in common_issues and "точность" not in current_prompt.lower():
                improved = current_prompt + "\n\nВажно: Проверяй точность ответов перед отправкой."
                improvements.append(
                    PromptImprovement(
                        original_prompt=current_prompt,
                        improved_prompt=improved,
                        improvement_reason="Негативный feedback указывает на проблемы с точностью",
                        expected_impact="high",
                        confidence=0.8,
                    )
                )

            if "clarity" in common_issues and "ясно" not in current_prompt.lower():
                improved = (
                    current_prompt + "\n\nОтвечай ясно и понятно, избегай сложных формулировок."
                )
                improvements.append(
                    PromptImprovement(
                        original_prompt=current_prompt,
                        improved_prompt=improved,
                        improvement_reason="Негативный feedback указывает на проблемы с ясностью",
                        expected_impact="high",
                        confidence=0.75,
                    )
                )

        # Предложение 1: Добавить структурирование, если его нет
        if "структурированно" not in current_prompt.lower():
            if patterns["successful_structures"]:
                improved = (
                    current_prompt
                    + "\n\nОтвечай структурированно, используя списки и форматирование."
                )
                improvements.append(
                    PromptImprovement(
                        original_prompt=current_prompt,
                        improved_prompt=improved,
                        improvement_reason="Успешные ответы часто структурированы",
                        expected_impact="medium",
                        confidence=0.7,
                    )
                )

        # Предложение 2: Добавить примеры, если их часто запрашивают
        if patterns["common_phrases"].get("example_code", 0) > 3:
            if "пример" not in current_prompt.lower() and "код" not in current_prompt.lower():
                improved = current_prompt + "\n\nПри необходимости предоставляй примеры кода."
                improvements.append(
                    PromptImprovement(
                        original_prompt=current_prompt,
                        improved_prompt=improved,
                        improvement_reason="Часто запрашиваются примеры кода",
                        expected_impact="high",
                        confidence=0.8,
                    )
                )

        # Предложение 3: Добавить краткость, если ответы слишком длинные
        avg_response_length = (
            sum(len(d.get("response", "")) for d in top_dialogues) / len(top_dialogues)
            if top_dialogues
            else 0
        )
        if avg_response_length > 2000 and "кратко" not in current_prompt.lower():
            improved = current_prompt + "\n\nОтвечай кратко и по делу."
            improvements.append(
                PromptImprovement(
                    original_prompt=current_prompt,
                    improved_prompt=improved,
                    improvement_reason="Ответы слишком длинные, пользователи предпочитают краткость",
                    expected_impact="high",
                    confidence=0.75,
                )
            )

        return improvements

    async def log_improvement(
        self,
        improvement: PromptImprovement,
        expert_name: str,
        applied: bool = False,
        performance_before: Optional[float] = None,
        performance_after: Optional[float] = None,
    ):
        """Логирует предложение по улучшению в БД"""
        if not ASYNCPG_AVAILABLE:
            return

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute(
                    """
                    INSERT INTO prompt_optimization_logs
                    (expert_name, original_prompt, improved_prompt, improvement_reason,
                     expected_impact, confidence, applied, performance_before, performance_after,
                     created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                """,
                    expert_name,
                    improvement.original_prompt,
                    improvement.improved_prompt,
                    improvement.improvement_reason,
                    improvement.expected_impact,
                    improvement.confidence,
                    applied,
                    performance_before,
                    performance_after,
                )

                logger.info(f"✅ [PROMPT OPTIMIZER] Улучшение для {expert_name} сохранено в БД")
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ [PROMPT OPTIMIZER] Не удалось сохранить улучшение: {e}")


# Глобальный экземпляр
_auto_prompt_optimizer: Optional[AutoPromptOptimizer] = None


def get_auto_prompt_optimizer() -> AutoPromptOptimizer:
    """Получить глобальный экземпляр AutoPromptOptimizer"""
    global _auto_prompt_optimizer
    if _auto_prompt_optimizer is None:
        _auto_prompt_optimizer = AutoPromptOptimizer()
    return _auto_prompt_optimizer
