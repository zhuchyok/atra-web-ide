"""
Enhanced Expert Evolver: Автоматическая эволюция экспертов на основе метрик эффективности

Функционал:
- Метрики эффективности экспертов (success_rate, response_time, knowledge_quality)
- Автоматическая эволюция на основе метрик
- Удаление неэффективных экспертов
- Специализация экспертов (углубление в узкие области)
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import (  # noqa: F401 - Optional used in evolve_expert_from_insights
    Dict,
    List,
    Optional,
    Tuple,
)

import asyncpg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

# Пороги для принятия решений
EVOLUTION_THRESHOLD = 0.7  # Минимальный success_rate для эволюции
REMOVAL_THRESHOLD = 0.3  # Минимальный success_rate для удаления
SPECIALIZATION_THRESHOLD = 0.8  # Минимальный success_rate для специализации


@dataclass
class ExpertMetrics:
    """Метрики эффективности эксперта"""

    expert_id: str
    name: str
    role: str
    success_rate: float  # Процент успешных взаимодействий
    response_time_avg: float  # Среднее время ответа (мс)
    knowledge_quality: float  # Качество созданных знаний (avg confidence)
    task_completion_rate: float  # Процент завершенных задач
    usage_count: int  # Количество использований
    feedback_avg: float  # Средний feedback score
    knowledge_created: int  # Количество созданных знаний
    last_activity: Optional[datetime]  # Последняя активность


def run_cursor_agent(prompt: str) -> Optional[str]:
    """Запуск Cursor Agent для генерации контента"""
    try:
        env = os.environ.copy()
        result = subprocess.run(
            ["/root/.local/bin/cursor-agent", "--print", prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=400,
            env=env,
        )
        return result.stdout.strip()
    except Exception as e:
        logger.error(f"Cursor Agent error: {e}")
        return None


class ExpertMetricsCollector:
    """Класс для сбора метрик эффективности экспертов"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def collect_metrics(self, expert_id: str) -> Optional[ExpertMetrics]:
        """Сбор всех метрик для эксперта"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Базовая информация об эксперте
                expert = await conn.fetchrow(
                    """
                    SELECT id, name, role, system_prompt, department
                    FROM experts
                    WHERE id = $1
                """,
                    expert_id,
                )

                if not expert:
                    return None

                # Success rate (процент положительных feedback)
                success_rate = (
                    await conn.fetchval(
                        """
                    SELECT
                        CASE
                            WHEN count(*) = 0 THEN 0.0
                            ELSE count(*) FILTER (WHERE feedback_score > 0)::float / count(*)::float
                        END
                    FROM interaction_logs
                    WHERE expert_id = $1
                      AND feedback_score IS NOT NULL
                      AND created_at > NOW() - INTERVAL '30 days'
                """,
                        expert_id,
                    )
                    or 0.0
                )

                # Среднее время ответа (из metadata)
                response_time_avg = (
                    await conn.fetchval(
                        """
                    SELECT AVG((metadata->>'response_time_ms')::float)
                    FROM interaction_logs
                    WHERE expert_id = $1
                      AND metadata->>'response_time_ms' IS NOT NULL
                      AND created_at > NOW() - INTERVAL '30 days'
                """,
                        expert_id,
                    )
                    or 0.0
                )

                # Качество знаний (средний confidence созданных знаний)
                knowledge_quality = (
                    await conn.fetchval(
                        """
                    SELECT AVG(confidence_score)
                    FROM knowledge_nodes
                    WHERE metadata->>'expert' = $1
                      AND created_at > NOW() - INTERVAL '30 days'
                """,
                        expert["name"],
                    )
                    or 0.0
                )

                # Task completion rate
                task_completion_rate = (
                    await conn.fetchval(
                        """
                    SELECT
                        CASE
                            WHEN count(*) = 0 THEN 0.0
                            ELSE count(*) FILTER (WHERE status = 'completed')::float / count(*)::float
                        END
                    FROM tasks
                    WHERE assignee_expert_id = $1
                      AND created_at > NOW() - INTERVAL '30 days'
                """,
                        expert_id,
                    )
                    or 0.0
                )

                # Usage count
                usage_count = (
                    await conn.fetchval(
                        """
                    SELECT count(*)
                    FROM interaction_logs
                    WHERE expert_id = $1
                      AND created_at > NOW() - INTERVAL '30 days'
                """,
                        expert_id,
                    )
                    or 0
                )

                # Средний feedback
                feedback_avg = (
                    await conn.fetchval(
                        """
                    SELECT AVG(feedback_score)
                    FROM interaction_logs
                    WHERE expert_id = $1
                      AND feedback_score IS NOT NULL
                      AND created_at > NOW() - INTERVAL '30 days'
                """,
                        expert_id,
                    )
                    or 0.0
                )

                # Количество созданных знаний
                knowledge_created = (
                    await conn.fetchval(
                        """
                    SELECT count(*)
                    FROM knowledge_nodes
                    WHERE metadata->>'expert' = $1
                      AND created_at > NOW() - INTERVAL '30 days'
                """,
                        expert["name"],
                    )
                    or 0
                )

                # Последняя активность
                last_activity = await conn.fetchval(
                    """
                    SELECT MAX(created_at)
                    FROM interaction_logs
                    WHERE expert_id = $1
                """,
                    expert_id,
                )

                return ExpertMetrics(
                    expert_id=str(expert_id),
                    name=expert["name"],
                    role=expert["role"],
                    success_rate=float(success_rate),
                    response_time_avg=float(response_time_avg),
                    knowledge_quality=float(knowledge_quality),
                    task_completion_rate=float(task_completion_rate),
                    usage_count=int(usage_count),
                    feedback_avg=float(feedback_avg),
                    knowledge_created=int(knowledge_created),
                    last_activity=last_activity,
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error collecting metrics for expert {expert_id}: {e}")
            return None

    async def get_all_experts_metrics(self) -> List[ExpertMetrics]:
        """Сбор метрик для всех экспертов"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                expert_ids = await conn.fetch("SELECT id FROM experts")

                metrics_list = []
                for expert_id in expert_ids:
                    metrics = await self.collect_metrics(expert_id["id"])
                    if metrics:
                        metrics_list.append(metrics)

                return metrics_list
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error collecting all metrics: {e}")
            return []


class ExpertEvolver:
    """Класс для автоматической эволюции экспертов"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.metrics_collector = ExpertMetricsCollector(db_url)

    async def evolve_expert(self, expert_id: str, metrics: ExpertMetrics) -> bool:
        """Эволюция эксперта на основе метрик"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Получаем текущий промпт
                expert = await conn.fetchrow(
                    """
                    SELECT name, role, system_prompt, version, department
                    FROM experts
                    WHERE id = $1
                """,
                    expert_id,
                )

                if not expert:
                    return False

                # Собираем данные для эволюции
                feedback_data = await conn.fetch(
                    """
                    SELECT user_query, assistant_response, feedback_score, feedback_text
                    FROM interaction_logs
                    WHERE expert_id = $1
                      AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY feedback_score DESC NULLS LAST
                    LIMIT 10
                """,
                    expert_id,
                )

                # Формируем промпт для эволюции
                evolution_prompt = f"""
                ВЫ - НЕЙРОННЫЙ АРХИТЕКТОР (УРОВЕНЬ 5).
                ЦЕЛЬ: Провести рекурсивную самооптимизацию личности ИИ-эксперта на основе метрик эффективности.

                ЭКСПЕРТ: {expert["name"]} ({expert["role"]})
                ТЕКУЩИЙ ПРОМПТ: {expert["system_prompt"]}

                МЕТРИКИ ЭФФЕКТИВНОСТИ:
                - Success Rate: {metrics.success_rate:.2%}
                - Response Time: {metrics.response_time_avg:.0f}ms
                - Knowledge Quality: {metrics.knowledge_quality:.2f}
                - Task Completion: {metrics.task_completion_rate:.2%}
                - Usage Count: {metrics.usage_count}
                - Avg Feedback: {metrics.feedback_avg:.2f}

                РЕЗУЛЬТАТЫ РАБОТЫ ЗА НЕДЕЛЮ:
                {self._format_feedback_data(feedback_data)}

                ЗАДАЧА:
                1. Проанализируйте метрики и определите слабые места.
                2. Сгенерируйте улучшенную версию системного промпта.
                3. Усильте области, где метрики низкие.
                4. Сохраните сильные стороны эксперта.

                ОТВЕТЬТЕ ТОЛЬКО ТЕКСТОМ НОВОГО ПРОМПТА.
                """

                new_prompt = run_cursor_agent(evolution_prompt)

                if new_prompt and len(new_prompt) > 100:
                    new_version = (expert["version"] or 0) + 1

                    await conn.execute(
                        """
                        UPDATE experts
                        SET system_prompt = $1,
                            version = $2,
                            metadata = metadata || jsonb_build_object(
                                'last_evolution', NOW(),
                                'prev_prompt', $3,
                                'evolution_metrics', $4
                            )
                        WHERE id = $5
                    """,
                        new_prompt,
                        new_version,
                        expert["system_prompt"],
                        json.dumps(
                            {
                                "success_rate": metrics.success_rate,
                                "response_time": metrics.response_time_avg,
                                "knowledge_quality": metrics.knowledge_quality,
                            }
                        ),
                        expert_id,
                    )

                    logger.info(f"✨ Expert {expert['name']} evolved to v{new_version}")

                    # Сохраняем событие эволюции (по возможности с embedding — VERIFICATION §5, WHATS_NOT_DONE §4)
                    domain_id = await conn.fetchval(
                        "SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1"
                    )
                    if not domain_id:
                        domain_id = await conn.fetchval(
                            "INSERT INTO domains (name) VALUES ('Strategy') RETURNING id"
                        )
                    content_kn = f"🧬 ЭВОЛЮЦИЯ: {expert['name']} прошел автоматическую эволюцию до v{new_version} на основе метрик (success_rate: {metrics.success_rate:.2%})."
                    meta_kn = json.dumps(
                        {
                            "type": "expert_evolution",
                            "expert": expert["name"],
                            "version": new_version,
                            "metrics": {
                                "success_rate": metrics.success_rate,
                                "response_time": metrics.response_time_avg,
                                "knowledge_quality": metrics.knowledge_quality,
                            },
                        }
                    )
                    embedding = None
                    try:
                        from semantic_cache import get_embedding

                        embedding = await get_embedding(content_kn[:8000])
                    except Exception:
                        pass
                    if embedding is not None:
                        await conn.execute(
                            """
                            INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                            VALUES ($1, $2, 1.0, $3, true, $4::vector)
                        """,
                            domain_id,
                            content_kn,
                            meta_kn,
                            str(embedding),
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                            VALUES ($1, $2, 1.0, $3, true)
                        """,
                            domain_id,
                            content_kn,
                            meta_kn,
                        )

                    return True

                return False
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error evolving expert {expert_id}: {e}")
            return False

    async def evolve_expert_from_insights(
        self, conn, expert_id: str, insights_text: str, task_id: Optional[int] = None
    ) -> bool:
        """
        Эволюция промпта эксперта на основе инсайтов из Knowledge Applicator (без метрик).
        Вызывается при обработке задач «Prompt evolution from top insights».
        """
        try:
            expert = await conn.fetchrow(
                """
                SELECT id, name, role, system_prompt, version, department
                FROM experts
                WHERE id = $1
            """,
                expert_id,
            )
            if not expert or not (expert["system_prompt"] or "").strip():
                return False
            evolution_prompt = f"""
ВЫ - НЕЙРОННЫЙ АРХИТЕКТОР. ЦЕЛЬ: дополнить системный промпт эксперта верифицированными инсайтами из базы знаний.

ЭКСПЕРТ: {expert["name"]} ({expert["role"]}), отдел: {expert["department"] or "General"}.

ТЕКУЩИЙ SYSTEM PROMPT:
{expert["system_prompt"]}

ВЕРИФИЦИРОВАННЫЕ ИНСАЙТЫ (включи релевантные в промпт):
{insights_text[:2500]}

ЗАДАЧА: Сгенерируй ОБНОВЛЁННЫЙ system_prompt, который сохраняет личность эксперта и добавляет/учитывает инсайты выше. Не удаляй существующие сильные формулировки. Ответь ТОЛЬКО текстом нового промпта, без пояснений.
"""
            new_prompt = run_cursor_agent(evolution_prompt)
            if not new_prompt or len(new_prompt.strip()) < 100:
                return False
            new_version = (expert["version"] or 0) + 1
            await conn.execute(
                """
                UPDATE experts
                SET system_prompt = $1, version = $2,
                    metadata = metadata || jsonb_build_object(
                        'last_evolution', NOW(),
                        'evolution_source', 'insights_task',
                        'evolution_task_id', $3
                    )
                WHERE id = $4
            """,
                new_prompt.strip(),
                new_version,
                task_id,
                expert_id,
            )
            logger.info(
                "✨ Expert %s evolved to v%s from insights task", expert["name"], new_version
            )
            return True
        except Exception as e:
            logger.warning("evolve_expert_from_insights failed for %s: %s", expert_id, e)
            return False

    def _format_feedback_data(self, feedback_data: List) -> str:
        """Форматирование данных feedback для промпта"""
        if not feedback_data:
            return "Активности не было, используйте общие тренды 2026."

        formatted = []
        for f in feedback_data:
            score = f.get("feedback_score", "N/A")
            text = f.get("feedback_text", "")
            formatted.append(
                f"Q: {f['user_query'][:200]}\nA: {f['assistant_response'][:200]}\nScore: {score} {text}"
            )

        return "\n\n".join(formatted)

    async def remove_ineffective_experts(self, metrics_list: List[ExpertMetrics]) -> List[str]:
        """Удаление неэффективных экспертов"""
        removed = []

        for metrics in metrics_list:
            # Критерии удаления:
            # 1. Низкий success_rate (< REMOVAL_THRESHOLD)
            # 2. Низкая активность (< 5 использований за 30 дней)
            # 3. Нет активности более 60 дней
            should_remove = (
                metrics.success_rate < REMOVAL_THRESHOLD and metrics.usage_count < 5
            ) or (metrics.last_activity and (datetime.now() - metrics.last_activity).days > 60)

            if should_remove:
                try:
                    conn = await asyncpg.connect(self.db_url)
                    try:
                        # Помечаем как неактивного вместо удаления
                        await conn.execute(
                            """
                            UPDATE experts
                            SET metadata = metadata || jsonb_build_object(
                                'removed_at', NOW(),
                                'removal_reason', 'low_effectiveness',
                                'removal_metrics', $1
                            )
                            WHERE id = $2
                        """,
                            json.dumps(
                                {
                                    "success_rate": metrics.success_rate,
                                    "usage_count": metrics.usage_count,
                                    "last_activity": metrics.last_activity.isoformat()
                                    if metrics.last_activity
                                    else None,
                                }
                            ),
                            metrics.expert_id,
                        )

                        logger.info(
                            f"🗑️ Marked expert {metrics.name} as inactive (success_rate: {metrics.success_rate:.2%})"
                        )
                        removed.append(metrics.expert_id)
                    finally:
                        await conn.close()
                except Exception as e:
                    logger.error(f"Error removing expert {metrics.expert_id}: {e}")

        return removed

    async def specialize_expert(self, expert_id: str, metrics: ExpertMetrics) -> bool:
        """Специализация эксперта в узкой области"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Находим домен, где эксперт наиболее эффективен
                domain_performance = await conn.fetch(
                    """
                    SELECT
                        d.name as domain,
                        count(*) as usage_count,
                        avg(il.feedback_score) as avg_feedback
                    FROM interaction_logs il
                    JOIN knowledge_nodes k ON (il.metadata->>'knowledge_id')::uuid = k.id
                    JOIN domains d ON k.domain_id = d.id
                    WHERE il.expert_id = $1
                      AND il.created_at > NOW() - INTERVAL '30 days'
                    GROUP BY d.name
                    ORDER BY avg_feedback DESC, usage_count DESC
                    LIMIT 1
                """,
                    expert_id,
                )

                if not domain_performance:
                    return False

                best_domain = domain_performance[0]["domain"]

                # Обновляем промпт для специализации
                expert = await conn.fetchrow(
                    """
                    SELECT name, role, system_prompt, department
                    FROM experts
                    WHERE id = $1
                """,
                    expert_id,
                )

                specialization_prompt = f"""
                ВЫ - НЕЙРОННЫЙ АРХИТЕКТОР.
                ЦЕЛЬ: Специализировать эксперта в узкой области для максимальной эффективности.

                ЭКСПЕРТ: {expert["name"]} ({expert["role"]})
                ТЕКУЩИЙ ПРОМПТ: {expert["system_prompt"]}
                ОБЛАСТЬ СПЕЦИАЛИЗАЦИИ: {best_domain}

                МЕТРИКИ В ЭТОЙ ОБЛАСТИ:
                - Usage Count: {domain_performance[0]["usage_count"]}
                - Avg Feedback: {domain_performance[0]["avg_feedback"]:.2f}

                ЗАДАЧА:
                1. Углубить экспертизу в области {best_domain}
                2. Добавить специфичные знания и методологии
                3. Сохранить общую компетентность

                ОТВЕТЬТЕ ТОЛЬКО ТЕКСТОМ НОВОГО ПРОМПТА.
                """

                new_prompt = run_cursor_agent(specialization_prompt)

                if new_prompt and len(new_prompt) > 100:
                    await conn.execute(
                        """
                        UPDATE experts
                        SET system_prompt = $1,
                            department = $2,
                            metadata = metadata || jsonb_build_object(
                                'specialized_at', NOW(),
                                'specialization_domain', $3
                            )
                        WHERE id = $4
                    """,
                        new_prompt,
                        best_domain,
                        best_domain,
                        expert_id,
                    )

                    logger.info(f"🎯 Expert {expert['name']} specialized in {best_domain}")
                    return True

                return False
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error specializing expert {expert_id}: {e}")
            return False


async def run_enhanced_evolution_cycle():
    """Основной цикл автоматической эволюции экспертов"""
    logger.info("🧬 Starting Enhanced Expert Evolution cycle...")

    conn = await asyncpg.connect(DB_URL)
    evolver = ExpertEvolver()
    insights_evolved = 0

    try:
        # 0. Обработка задач «Prompt evolution from top insights» (Knowledge Applicator → автоматическая эволюция)
        insight_tasks = await conn.fetch(
            """
            SELECT id, title, description, metadata
            FROM tasks
            WHERE status = 'pending'
              AND metadata->>'source' = 'knowledge_applicator'
              AND (title ILIKE $1 OR title ILIKE $2)
            ORDER BY created_at ASC
            LIMIT 5
        """,
            "%Prompt evolution%",
            "%эволюция промптов%",
        )
        if insight_tasks:
            logger.info(
                "📥 Processing %d insight-driven prompt evolution task(s)...", len(insight_tasks)
            )
        for task in insight_tasks:
            task_id = task["id"]
            description = (task["description"] or "").strip()
            if len(description) < 50:
                await conn.execute(
                    "UPDATE tasks SET status = 'cancelled', updated_at = NOW() WHERE id = $1",
                    task_id,
                )
                continue
            # Выбираем до 3 экспертов (разные отделы, активные)
            experts = await conn.fetch("""
                SELECT id FROM experts
                WHERE (is_active IS NULL OR is_active = TRUE)
                  AND system_prompt IS NOT NULL AND LENGTH(TRIM(system_prompt)) > 50
                ORDER BY RANDOM()
                LIMIT 3
            """)
            task_evolved = False
            for row in experts:
                if await evolver.evolve_expert_from_insights(
                    conn, str(row["id"]), description, task_id=task_id
                ):
                    insights_evolved += 1
                    task_evolved = True
                    break
            await conn.execute(
                "UPDATE tasks SET status = 'completed', updated_at = NOW(), result = $2 WHERE id = $1",
                task_id,
                "Insights applied to expert prompt (auto-evolution)."
                if task_evolved
                else "No expert updated (LLM unavailable or skip).",
            )
        if insights_evolved:
            logger.info("   Insights → prompts: %d expert(s) evolved", insights_evolved)
    finally:
        await conn.close()

    collector = ExpertMetricsCollector()

    # Собираем метрики всех экспертов
    metrics_list = await collector.get_all_experts_metrics()

    if not metrics_list:
        logger.warning("No experts found for evolution")
        return

    logger.info(f"Collected metrics for {len(metrics_list)} experts")

    evolved_count = 0
    specialized_count = 0
    removed_count = 0

    # 1. Эволюция эффективных экспертов
    for metrics in metrics_list:
        if metrics.success_rate >= EVOLUTION_THRESHOLD and metrics.usage_count >= 10:
            if await evolver.evolve_expert(metrics.expert_id, metrics):
                evolved_count += 1

    # 2. Специализация высокоэффективных экспертов
    for metrics in metrics_list:
        if metrics.success_rate >= SPECIALIZATION_THRESHOLD and metrics.usage_count >= 20:
            if await evolver.specialize_expert(metrics.expert_id, metrics):
                specialized_count += 1

    # 3. Удаление неэффективных экспертов
    removed = await evolver.remove_ineffective_experts(metrics_list)
    removed_count = len(removed)

    logger.info("✅ Evolution cycle completed:")
    logger.info(f"   - Evolved: {evolved_count}")
    logger.info(f"   - Specialized: {specialized_count}")
    logger.info(f"   - Removed: {removed_count}")


if __name__ == "__main__":
    asyncio.run(run_enhanced_evolution_cycle())
