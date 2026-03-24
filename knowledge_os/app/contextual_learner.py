"""
Contextual Learner: Контекстная память и адаптивное обучение

Функционал:
- Запоминание успешных паттернов
- Адаптивное обучение на основе обратной связи
- Персонализация (учет предпочтений пользователей)
- Прогнозирование потребностей
"""

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


@dataclass
class ContextualPattern:
    """Паттерн контекстной памяти"""

    pattern_type: str  # 'query_pattern', 'response_pattern', 'interaction_pattern'
    context_hash: str
    pattern_data: Dict[str, Any]
    success_score: float = 0.0
    usage_count: int = 0


class ContextualMemory:
    """Класс для работы с контекстной памятью"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    def _hash_context(
        self, query: str, domain: Optional[str] = None, expert: Optional[str] = None
    ) -> str:
        """Создание хеша контекста"""
        context_str = f"{query}|{domain or ''}|{expert or ''}"
        return hashlib.sha256(context_str.encode()).hexdigest()

    async def save_pattern(
        self,
        pattern_type: str,
        query: str,
        response: str,
        success_score: float,
        domain: Optional[str] = None,
        expert: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[str]:
        """Сохранение успешного паттерна"""
        context_hash = self._hash_context(query, domain, expert)

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                pattern_id = await conn.fetchval(
                    """
                    INSERT INTO contextual_patterns
                    (pattern_type, context_hash, pattern_data, success_score, usage_count, last_used_at)
                    VALUES ($1, $2, $3, $4, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (context_hash, pattern_type)
                    DO UPDATE SET
                        success_score = GREATEST(contextual_patterns.success_score, EXCLUDED.success_score),
                        usage_count = contextual_patterns.usage_count + 1,
                        pattern_data = EXCLUDED.pattern_data,
                        last_used_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """,
                    pattern_type,
                    context_hash,
                    json.dumps(
                        {
                            "query": query,
                            "response": response,
                            "domain": domain,
                            "expert": expert,
                            "metadata": metadata or {},
                        }
                    ),
                    success_score,
                )

                logger.info(f"✅ Saved pattern: {pattern_type} (score: {success_score:.2f})")
                return str(pattern_id)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error saving pattern: {e}")
            return None

    async def find_similar_patterns(
        self,
        query: str,
        pattern_type: str = "query_pattern",
        domain: Optional[str] = None,
        expert: Optional[str] = None,
        min_success: float = 0.7,
        limit: int = 5,
    ) -> List[Dict]:
        """Поиск похожих успешных паттернов"""
        context_hash = self._hash_context(query, domain, expert)

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                rows = await conn.fetch(
                    """
                    SELECT * FROM find_similar_patterns($1, $2, $3, $4)
                """,
                    context_hash,
                    pattern_type,
                    min_success,
                    limit,
                )

                return [dict(row) for row in rows]
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error finding patterns: {e}")
            return []


class AdaptiveLearner:
    """Класс для адаптивного обучения на основе обратной связи"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.memory = ContextualMemory(db_url)

    async def learn_from_feedback(
        self,
        interaction_log_id: str,
        expert_id: str,
        feedback_score: int,  # 1 for positive, -1 for negative
        feedback_text: Optional[str] = None,
    ) -> Optional[str]:
        """Обучение на основе обратной связи"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Привязка id: в части БД interaction_logs.id — integer
                _il_id = (
                    int(interaction_log_id)
                    if isinstance(interaction_log_id, str) and interaction_log_id.isdigit()
                    else interaction_log_id
                )
                # Получаем данные взаимодействия
                interaction = await conn.fetchrow(
                    """
                    SELECT il.user_query, il.assistant_response, il.metadata,
                           e.name as expert_name, d.name as domain_name
                    FROM interaction_logs il
                    LEFT JOIN experts e ON il.expert_id = e.id
                    LEFT JOIN knowledge_nodes k ON (il.metadata->>'knowledge_id')::text = k.id::text
                    LEFT JOIN domains d ON k.domain_id = d.id
                    WHERE il.id = $1
                """,
                    _il_id,
                )

                if not interaction:
                    return None

                # Определяем тип обучения
                if feedback_score > 0:
                    learning_type = "feedback_learning"
                    impact_score = 0.8
                    learned_insight = f"Успешный паттерн: {interaction['user_query'][:100]}"

                    # Сохраняем успешный паттерн
                    await self.memory.save_pattern(
                        pattern_type="interaction_pattern",
                        query=interaction["user_query"],
                        response=interaction["assistant_response"],
                        success_score=0.9,
                        domain=interaction.get("domain_name"),
                        expert=interaction.get("expert_name"),
                        metadata={"feedback": feedback_text},
                    )
                else:
                    learning_type = "feedback_learning"
                    impact_score = 0.3
                    learned_insight = f"Неудачный паттерн: {interaction['user_query'][:100]} - {feedback_text or 'negative feedback'}"

                # Сохраняем в лог обучения (interaction_log_id в таблице — UUID; при integer id из interaction_logs передаём NULL)
                _il_id_insert = None if isinstance(_il_id, int) else _il_id
                learning_id = await conn.fetchval(
                    """
                    INSERT INTO adaptive_learning_logs
                    (interaction_log_id, expert_id, learning_type, learned_insight, impact_score, applied_at)
                    VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
                    RETURNING id
                """,
                    _il_id_insert,
                    expert_id,
                    learning_type,
                    learned_insight,
                    impact_score,
                )

                logger.info(
                    f"✅ Learned from feedback: {learning_type} (impact: {impact_score:.2f})"
                )
                return str(learning_id)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error learning from feedback: {e}")
            return None

    async def get_learned_insights(
        self, expert_id: Optional[str] = None, learning_type: Optional[str] = None, limit: int = 10
    ) -> List[Dict]:
        """Получение изученных инсайтов"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                query = "SELECT * FROM adaptive_learning_logs WHERE 1=1"
                params = []

                if expert_id:
                    query += " AND expert_id = $" + str(len(params) + 1)
                    params.append(expert_id)

                if learning_type:
                    query += " AND learning_type = $" + str(len(params) + 1)
                    params.append(learning_type)

                query += " ORDER BY impact_score DESC, created_at DESC LIMIT $" + str(
                    len(params) + 1
                )
                params.append(limit)

                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error getting learned insights: {e}")
            return []


class PersonalizationEngine:
    """Класс для персонализации (учет предпочтений пользователей)"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def save_preference(
        self,
        user_identifier: str,
        preference_type: str,
        preference_key: str,
        preference_value: Any,
        confidence: float = 0.5,
    ) -> Optional[str]:
        """Сохранение предпочтения пользователя"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                pref_id = await conn.fetchval(
                    """
                    INSERT INTO user_preferences
                    (user_identifier, preference_type, preference_key, preference_value, confidence)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_identifier, preference_type, preference_key)
                    DO UPDATE SET
                        preference_value = EXCLUDED.preference_value,
                        confidence = GREATEST(user_preferences.confidence, EXCLUDED.confidence),
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """,
                    user_identifier,
                    preference_type,
                    preference_key,
                    json.dumps(preference_value),
                    confidence,
                )

                logger.info(f"✅ Saved preference: {preference_type}/{preference_key}")
                return str(pref_id)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error saving preference: {e}")
            return None

    async def get_preferences(
        self, user_identifier: str, preference_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение предпочтений пользователя"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                query = """
                    SELECT preference_type, preference_key, preference_value, confidence
                    FROM user_preferences
                    WHERE user_identifier = $1
                """
                params = [user_identifier]

                if preference_type:
                    query += " AND preference_type = $2"
                    params.append(preference_type)

                rows = await conn.fetch(query, *params)

                preferences = {}
                for row in rows:
                    pref_type = row["preference_type"]
                    if pref_type not in preferences:
                        preferences[pref_type] = {}
                    preferences[pref_type][row["preference_key"]] = {
                        "value": row["preference_value"],
                        "confidence": row["confidence"],
                    }

                return preferences
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error getting preferences: {e}")
            return {}

    async def infer_preferences_from_interactions(
        self, user_identifier: str, limit: int = 100
    ) -> Dict[str, Any]:
        """Вывод предпочтений из истории взаимодействий"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Анализируем домены, которые пользователь чаще использует
                domain_stats = await conn.fetch(
                    """
                    SELECT
                        d.name as domain,
                        count(*) as usage_count,
                        avg(il.feedback_score) as avg_feedback
                    FROM interaction_logs il
                    JOIN knowledge_nodes k ON (il.metadata->>'knowledge_id')::uuid = k.id
                    JOIN domains d ON k.domain_id = d.id
                    WHERE il.metadata->>'user_identifier' = $1
                    GROUP BY d.name
                    ORDER BY usage_count DESC
                    LIMIT 5
                """,
                    user_identifier,
                )

                preferences = {}
                if domain_stats:
                    domain_prefs = {}
                    for stat in domain_stats:
                        domain_prefs[stat["domain"]] = {
                            "usage_count": stat["usage_count"],
                            "avg_feedback": float(stat["avg_feedback"])
                            if stat["avg_feedback"]
                            else 0.0,
                        }
                    preferences["domain_preference"] = domain_prefs

                # Анализируем предпочтения по экспертам
                expert_stats = await conn.fetch(
                    """
                    SELECT
                        e.name as expert,
                        count(*) as usage_count,
                        avg(il.feedback_score) as avg_feedback
                    FROM interaction_logs il
                    JOIN experts e ON il.expert_id = e.id
                    WHERE il.metadata->>'user_identifier' = $1
                    GROUP BY e.name
                    ORDER BY usage_count DESC
                    LIMIT 5
                """,
                    user_identifier,
                )

                if expert_stats:
                    expert_prefs = {}
                    for stat in expert_stats:
                        expert_prefs[stat["expert"]] = {
                            "usage_count": stat["usage_count"],
                            "avg_feedback": float(stat["avg_feedback"])
                            if stat["avg_feedback"]
                            else 0.0,
                        }
                    preferences["expert_preference"] = expert_prefs

                # Сохраняем выведенные предпочтения
                for pref_type, pref_data in preferences.items():
                    for key, value in pref_data.items():
                        await self.save_preference(
                            user_identifier,
                            pref_type,
                            key,
                            value,
                            confidence=0.7,  # Средняя уверенность для выведенных предпочтений
                        )

                return preferences
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error inferring preferences: {e}")
            return {}


class NeedPredictor:
    """Класс для прогнозирования потребностей пользователей"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def predict_needs(
        self, user_identifier: str, recent_interactions: int = 10
    ) -> List[Dict]:
        """Прогнозирование потребностей на основе истории"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Анализируем последние взаимодействия
                recent = await conn.fetch(
                    """
                    SELECT
                        il.user_query,
                        d.name as domain,
                        il.created_at
                    FROM interaction_logs il
                    LEFT JOIN knowledge_nodes k ON (il.metadata->>'knowledge_id')::uuid = k.id
                    LEFT JOIN domains d ON k.domain_id = d.id
                    WHERE il.metadata->>'user_identifier' = $1
                    ORDER BY il.created_at DESC
                    LIMIT $2
                """,
                    user_identifier,
                    recent_interactions,
                )

                if not recent:
                    return []

                # Простой алгоритм: предсказываем следующий домен на основе тренда
                domain_counts = {}
                for interaction in recent:
                    domain = interaction.get("domain") or "general"
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1

                # Находим наиболее вероятный следующий домен
                most_likely_domain = max(domain_counts.items(), key=lambda x: x[1])[0]
                confidence = domain_counts[most_likely_domain] / len(recent)

                # Сохраняем предсказание
                prediction_id = await conn.fetchval(
                    """
                    INSERT INTO need_predictions
                    (user_identifier, predicted_domain, predicted_topic, confidence)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                """,
                    user_identifier,
                    most_likely_domain,
                    f"Следующий запрос в области {most_likely_domain}",
                    confidence,
                )

                return [
                    {
                        "prediction_id": str(prediction_id),
                        "predicted_domain": most_likely_domain,
                        "confidence": confidence,
                        "reason": f"На основе {len(recent)} последних взаимодействий",
                    }
                ]
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error predicting needs: {e}")
            return []

    async def validate_prediction(self, prediction_id: str, actual_domain: str) -> bool:
        """Валидация предсказания (когда оно сбылось)"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                prediction = await conn.fetchrow(
                    """
                    SELECT predicted_domain FROM need_predictions WHERE id = $1
                """,
                    prediction_id,
                )

                if not prediction:
                    return False

                is_correct = prediction["predicted_domain"] == actual_domain

                await conn.execute(
                    """
                    UPDATE need_predictions
                    SET is_validated = TRUE,
                        validated_at = CURRENT_TIMESTAMP,
                        prediction_metadata = jsonb_set(
                            COALESCE(prediction_metadata, '{}'),
                            '{is_correct}',
                            $1::text::jsonb
                        )
                    WHERE id = $2
                """,
                    json.dumps(is_correct),
                    prediction_id,
                )

                return is_correct
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error validating prediction: {e}")
            return False


async def run_contextual_learning_cycle():
    """Основной цикл контекстного обучения"""
    logger.info("🎓 Starting contextual learning cycle...")

    learner = AdaptiveLearner()
    personalizer = PersonalizationEngine()
    predictor = NeedPredictor()

    conn = await asyncpg.connect(DB_URL)

    try:
        # 1. Обучение на основе обратной связи
        logger.info("📚 Learning from feedback...")
        feedback_interactions = await conn.fetch("""
            SELECT il.id, il.expert_id, il.feedback_score, il.feedback_text
            FROM interaction_logs il
            WHERE il.feedback_score IS NOT NULL
              AND il.metadata->>'learned' IS NULL
            ORDER BY il.created_at DESC
            LIMIT 20
        """)

        for interaction in feedback_interactions:
            await learner.learn_from_feedback(
                str(interaction["id"]),
                str(interaction["expert_id"]),
                interaction["feedback_score"],
                interaction.get("feedback_text"),
            )

            # Помечаем как обработанное
            await conn.execute(
                """
                UPDATE interaction_logs
                SET metadata = jsonb_set(COALESCE(metadata, '{}'), '{learned}', 'true')
                WHERE id = $1
            """,
                interaction["id"],
            )

        # 2. Вывод предпочтений пользователей
        logger.info("👤 Inferring user preferences...")
        users = await conn.fetch("""
            SELECT DISTINCT metadata->>'user_identifier' as user_id
            FROM interaction_logs
            WHERE metadata->>'user_identifier' IS NOT NULL
            LIMIT 10
        """)

        for user in users:
            if user["user_id"]:
                await personalizer.infer_preferences_from_interactions(user["user_id"])

        # 3. Прогнозирование потребностей
        logger.info("🔮 Predicting user needs...")
        for user in users:
            if user["user_id"]:
                await predictor.predict_needs(user["user_id"])

        logger.info("✅ Contextual learning cycle completed")

    except Exception as e:
        logger.error(f"Contextual learning error: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_contextual_learning_cycle())
