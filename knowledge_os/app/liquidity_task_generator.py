#!/usr/bin/env python3
"""
Автоматическое создание задач на основе высоколиквидных знаний.
Анализирует популярные знания и создает задачи для их внедрения/улучшения.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

# Пороги для создания задач
MIN_LIQUIDITY_FOR_TASK = 2.0  # Минимальный liquidity_score для создания задачи
MIN_USAGE_COUNT = 3  # Минимальное количество использований
TOP_N_FOR_ANALYSIS = 20  # Топ-N узлов для анализа

# Приоритеты на основе ликвидности
LIQUIDITY_PRIORITY_THRESHOLDS = {
    "urgent": 10.0,  # Очень высокая ликвидность
    "high": 5.0,  # Высокая ликвидность
    "medium": 2.0,  # Средняя ликвидность
    "low": 1.0,  # Низкая ликвидность (но выше минимума)
}


class LiquidityTaskGenerator:
    """Генератор задач на основе ликвидности знаний"""

    def __init__(self, db_url: str = None):
        self.db_url = db_url

    async def get_pool(self):
        """Получить пул подключений к БД"""
        if self.db_url:
            return await asyncpg.create_pool(self.db_url, min_size=1, max_size=5)
        else:
            from evaluator import get_pool

            return await get_pool()

    def calculate_priority(self, liquidity_score: float, usage_count: int) -> str:
        """
        Определяет приоритет задачи на основе ликвидности.

        Args:
            liquidity_score: Ликвидность знания
            usage_count: Количество использований

        Returns:
            Приоритет: urgent, high, medium, low
        """
        if liquidity_score >= LIQUIDITY_PRIORITY_THRESHOLDS["urgent"] or usage_count >= 50:
            return "urgent"
        elif liquidity_score >= LIQUIDITY_PRIORITY_THRESHOLDS["high"] or usage_count >= 20:
            return "high"
        elif liquidity_score >= LIQUIDITY_PRIORITY_THRESHOLDS["medium"] or usage_count >= 10:
            return "medium"
        else:
            return "low"

    def generate_actionable_insights(
        self, content: str, usage_count: int, domain: str
    ) -> List[str]:
        """
        Генерирует actionable insights из популярного знания.

        Args:
            content: Содержимое узла знаний
            usage_count: Количество использований
            domain: Домен знания

        Returns:
            Список actionable insights
        """
        insights = []

        # Если знание используется часто, оно требует внедрения
        if usage_count >= 20:
            insights.append(
                f"Популярное знание используется {usage_count} раз - требует внедрения в процессы"
            )

        # Анализируем содержание на наличие инструкций/практик
        action_keywords = [
            "реализовать",
            "внедрить",
            "создать",
            "использовать",
            "применить",
            "оптимизировать",
        ]
        if any(keyword in content.lower() for keyword in action_keywords):
            insights.append(f"Содержит инструкции для внедрения в домене {domain}")

        # Если высокий usage_count, знание ценно и его нужно развивать
        if usage_count >= 10:
            insights.append(
                f"Высокая ценность ({usage_count} использований) - рассмотреть расширение и улучшение"
            )

        # Если нет insights, создаем базовый
        if not insights:
            insights.append("Популярное знание требует анализа возможности внедрения в процессы")

        return insights

    async def analyze_high_liquidity_knowledge(self) -> List[Dict]:
        """
        Анализирует высоколиквидные знания и возвращает кандидатов для создания задач.

        Returns:
            Список знаний с метриками ликвидности
        """
        try:
            pool = await self.get_pool()
        except Exception as e:
            logger.error(f"Error getting pool: {e}")
            return []

        async with pool.acquire() as conn:
            # Находим высоколиквидные знания
            knowledge_candidates = await conn.fetch(
                """
                SELECT
                    k.id,
                    k.content,
                    k.usage_count,
                    k.confidence_score,
                    d.name as domain,
                    (k.usage_count * k.confidence_score) as liquidity_score,
                    k.metadata->>'expert' as expert,
                    k.metadata->>'implemented' as implemented,
                    k.created_at
                FROM knowledge_nodes k
                JOIN domains d ON k.domain_id = d.id
                WHERE k.usage_count >= $1
                AND (k.metadata->>'implemented' IS NULL OR k.metadata->>'implemented' = 'false')
                ORDER BY (k.usage_count * k.confidence_score) DESC, k.usage_count DESC
                LIMIT $2
            """,
                MIN_USAGE_COUNT,
                TOP_N_FOR_ANALYSIS,
            )

            candidates = []
            for kn in knowledge_candidates:
                liquidity_score = float(kn["liquidity_score"] or 0)
                if liquidity_score >= MIN_LIQUIDITY_FOR_TASK:
                    candidates.append(
                        {
                            "id": str(kn["id"]),
                            "content": kn["content"],
                            "usage_count": kn["usage_count"],
                            "confidence_score": kn["confidence_score"],
                            "domain": kn["domain"],
                            "liquidity_score": liquidity_score,
                            "expert": kn["expert"],
                            "created_at": kn["created_at"],
                        }
                    )

        try:
            await pool.close()
        except:
            pass
        return candidates

    async def create_task_for_knowledge(self, knowledge: Dict) -> Optional[str]:
        """
        Создает задачу для внедрения/улучшения знания.

        Args:
            knowledge: Данные знания с метриками

        Returns:
            ID созданной задачи или None
        """
        try:
            pool = await self.get_pool()
        except Exception as e:
            logger.error(f"Error getting pool: {e}")
            return None

        async with pool.acquire() as conn:
            # Проверяем, не создана ли уже задача для этого знания
            existing_task = await conn.fetchval(
                """
                SELECT id FROM tasks
                WHERE metadata->>'knowledge_node_id' = $1
                AND status IN ('pending', 'in_progress')
                LIMIT 1
            """,
                knowledge["id"],
            )

            if existing_task:
                logger.debug(f"Task already exists for knowledge {knowledge['id']}")
                try:
                    await pool.close()
                except:
                    pass
                return None

            # Определяем домен
            domain_id = await conn.fetchval(
                "SELECT id FROM domains WHERE name = $1", knowledge["domain"]
            )
            if not domain_id:
                domain_id = await conn.fetchval("SELECT id FROM domains ORDER BY id LIMIT 1")

            # Определяем эксперта для назначения задачи
            assignee_id = None
            if knowledge["expert"]:
                assignee_id = await conn.fetchval(
                    "SELECT id FROM experts WHERE name = $1", knowledge["expert"]
                )

            if not assignee_id:
                # Берем эксперта домена
                assignee = await conn.fetchrow(
                    """
                    SELECT id FROM experts
                    WHERE department = $1
                    ORDER BY RANDOM()
                    LIMIT 1
                """,
                    knowledge["domain"],
                )
                assignee_id = assignee["id"] if assignee else None

            if not assignee_id:
                # Берем Викторияию как последний вариант
                assignee_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")

            # Находим создателя задачи
            creator_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
            if not creator_id:
                creator_id = assignee_id

            # Определяем приоритет
            priority = self.calculate_priority(
                knowledge["liquidity_score"], knowledge["usage_count"]
            )

            # Генерируем actionable insights
            insights = self.generate_actionable_insights(
                knowledge["content"], knowledge["usage_count"], knowledge["domain"]
            )

            # Формируем заголовок и описание задачи
            task_title = f"💎 Внедрить: {knowledge['content'][:60]}..."

            actionable_text = "\n".join([f"- {insight}" for insight in insights])
            task_description = f"""Популярное знание требует внедрения/улучшения

Метрики ликвидности:
- Использовано: {knowledge["usage_count"]} раз
- Ликвидность: {knowledge["liquidity_score"]:.2f}
- Confidence: {knowledge["confidence_score"]}

Домен: {knowledge["domain"]}

Знание:
{knowledge["content"][:500]}...

Действия:
{actionable_text}

Источник: Анализ ликвидности знаний (knowledge_node_id: {knowledge["id"]})"""

            # Создаем задачу
            task_id = await conn.fetchval(
                """
                INSERT INTO tasks (
                    title, description, status, priority,
                    assignee_expert_id, creator_expert_id, domain_id,
                    metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (title, COALESCE(project_context, 'default'::character varying))
                WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]))
                DO UPDATE SET updated_at = NOW()
                RETURNING id
            """,
                task_title,
                task_description,
                "pending",
                priority,
                assignee_id,
                creator_id,
                domain_id,
                json.dumps(
                    {
                        "source": "liquidity_task_generator",
                        "knowledge_node_id": knowledge["id"],
                        "liquidity_score": knowledge["liquidity_score"],
                        "usage_count": knowledge["usage_count"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
            )

            logger.info(
                f"✅ Created task {task_id} for knowledge {knowledge['id']} (priority: {priority}, liquidity: {knowledge['liquidity_score']:.2f})"
            )

            # Помечаем знание как имеющее задачу для внедрения
            try:
                await conn.execute(
                    """
                    UPDATE knowledge_nodes
                    SET metadata = metadata || jsonb_build_object(
                        'task_created_for_implementation', true,
                        'task_id', $1,
                        'task_created_at', $2
                    )
                    WHERE id = $3
                """,
                    str(task_id),
                    datetime.now(timezone.utc).isoformat(),
                    knowledge["id"],
                )
            except Exception as e:
                logger.debug(f"Could not update metadata for knowledge {knowledge['id']}: {e}")

        try:
            await pool.close()
        except:
            pass
        return str(task_id)

    async def process_high_liquidity_knowledge(self) -> Dict[str, int]:
        """
        Обрабатывает высоколиквидные знания и создает задачи.

        Returns:
            Статистика обработки
        """
        stats = {"analyzed": 0, "tasks_created": 0, "skipped": 0, "errors": 0}

        try:
            # Анализируем высоколиквидные знания
            candidates = await self.analyze_high_liquidity_knowledge()
            stats["analyzed"] = len(candidates)

            logger.info(f"📊 Found {len(candidates)} high-liquidity knowledge candidates")

            for knowledge in candidates:
                try:
                    task_id = await self.create_task_for_knowledge(knowledge)
                    if task_id:
                        stats["tasks_created"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    logger.error(f"❌ Error creating task for knowledge {knowledge['id']}: {e}")
                    stats["errors"] += 1
                    import traceback

                    traceback.print_exc()

        except Exception as e:
            logger.error(f"❌ Error processing high-liquidity knowledge: {e}")
            stats["errors"] += 1
            import traceback

            traceback.print_exc()

        return stats


async def process_liquidity_tasks():
    """Главная функция для обработки высоколиквидных знаний"""
    generator = LiquidityTaskGenerator()
    stats = await generator.process_high_liquidity_knowledge()

    print("\n📊 Статистика обработки ликвидности знаний:")
    print(f"   Проанализировано: {stats['analyzed']}")
    print(f"   Создано задач: {stats['tasks_created']}")
    print(f"   Пропущено: {stats['skipped']}")
    print(f"   Ошибок: {stats['errors']}")

    return stats


if __name__ == "__main__":
    asyncio.run(process_liquidity_tasks())
