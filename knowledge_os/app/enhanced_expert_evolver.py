"""
Enhanced Expert Evolver: Автоматическая эволюция экспертов на основе метрик эффективности

Функционал:
- Метрики эффективности экспертов (success_rate, response_time, knowledge_quality)
- Автоматическая эволюция на основе метрик
- Удаление неэффективных экспертов
- Специализация экспертов (углубление в узкие области)
"""

import argparse
import asyncio
import hashlib
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
EVOLUTION_FORCE_MINIMUM_MUTATION = os.getenv(
    "EVOLUTION_FORCE_MINIMUM_MUTATION", "true"
).lower() in (
    "true",
    "1",
    "yes",
)
EVOLUTION_ENABLE_EXPERT_REMOVAL = os.getenv("EVOLUTION_ENABLE_EXPERT_REMOVAL", "false").lower() in (
    "true",
    "1",
    "yes",
)
EVOLUTION_MIN_USAGE_FOR_REMOVAL = int(os.getenv("EVOLUTION_MIN_USAGE_FOR_REMOVAL", "20"))
EVOLUTION_ROLLOUT_MODE = os.getenv("EVOLUTION_ROLLOUT_MODE", "direct").lower()
EVOLUTION_HYBRID_SHADOW_RATIO = float(os.getenv("EVOLUTION_HYBRID_SHADOW_RATIO", "0.70"))
EVOLUTION_HYBRID_MIN_USAGE_FOR_DIRECT = int(
    os.getenv("EVOLUTION_HYBRID_MIN_USAGE_FOR_DIRECT", "25")
)
EVOLUTION_HYBRID_MIN_SUCCESS_FOR_DIRECT = float(
    os.getenv("EVOLUTION_HYBRID_MIN_SUCCESS_FOR_DIRECT", "0.60")
)
EVOLUTION_HYBRID_MIN_COMPLETION_FOR_DIRECT = float(
    os.getenv("EVOLUTION_HYBRID_MIN_COMPLETION_FOR_DIRECT", "0.60")
)


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


async def run_mutation_agent(prompt: str) -> Optional[str]:
    """Try cursor-agent first, then fallback to local router model."""
    result = run_cursor_agent(prompt)
    if result:
        return result

    try:
        from local_router import LocalAIRouter

        router = LocalAIRouter()
        local_result = await router.run_local_llm(prompt, category="reasoning")
        return local_result[0] if isinstance(local_result, tuple) else local_result
    except Exception as e:
        logger.error("Local mutation fallback error: %s", e)
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

    async def _record_mutation_event(
        self,
        conn: asyncpg.Connection,
        expert_id: str,
        mutated_prompt: str,
        base_version: int,
        source: str,
        metrics: Optional[Dict] = None,
        status: str = "promoted",
    ) -> None:
        """Persist mutation event for dashboard/status tracking."""
        try:
            await conn.execute(
                """
                INSERT INTO expert_mutations (
                    expert_id, mutated_prompt, base_version, status, metrics
                )
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                expert_id,
                mutated_prompt,
                int(base_version),
                status,
                json.dumps(
                    {
                        "source": source,
                        "applied_directly": status == "promoted",
                        **(metrics or {}),
                    },
                    ensure_ascii=False,
                ),
            )
        except Exception as e:
            logger.warning("Failed to record mutation event for expert %s: %s", expert_id, e)

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

                new_prompt = await run_mutation_agent(evolution_prompt)

                if new_prompt and len(new_prompt) > 100:
                    base_version = expert["version"] or 0
                    new_version = (expert["version"] or 0) + 1
                    use_shadow = _use_shadow_rollout(expert_id, metrics)
                    mutation_metrics = {
                        "new_version": new_version,
                        "success_rate": metrics.success_rate,
                        "response_time": metrics.response_time_avg,
                        "knowledge_quality": metrics.knowledge_quality,
                        "task_completion_rate": metrics.task_completion_rate,
                        "usage_count": metrics.usage_count,
                        "feedback_avg": metrics.feedback_avg,
                        "rollout_mode": EVOLUTION_ROLLOUT_MODE,
                        "rollout_shadow": use_shadow,
                    }

                    if use_shadow:
                        await self._record_mutation_event(
                            conn=conn,
                            expert_id=expert_id,
                            mutated_prompt=new_prompt,
                            base_version=base_version,
                            source="enhanced_metrics_evolution",
                            metrics=mutation_metrics,
                            status="shadow",
                        )
                        logger.info(
                            "👻 Expert %s generated shadow mutation from metrics (v%s candidate, mode=%s)",
                            expert["name"],
                            new_version,
                            EVOLUTION_ROLLOUT_MODE,
                        )
                        return True

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
                    await self._record_mutation_event(
                        conn=conn,
                        expert_id=expert_id,
                        mutated_prompt=new_prompt,
                        base_version=base_version,
                        source="enhanced_metrics_evolution",
                        metrics=mutation_metrics,
                        status="promoted",
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
            new_prompt = await run_mutation_agent(evolution_prompt)
            if not new_prompt or len(new_prompt.strip()) < 100:
                return False
            base_version = expert["version"] or 0
            new_version = (expert["version"] or 0) + 1
            use_shadow = _use_shadow_rollout(expert_id, metrics=None)
            if use_shadow:
                await self._record_mutation_event(
                    conn=conn,
                    expert_id=expert_id,
                    mutated_prompt=new_prompt.strip(),
                    base_version=base_version,
                    source="insights_task",
                    metrics={
                        "new_version": new_version,
                        "task_id": task_id,
                        "rollout_mode": EVOLUTION_ROLLOUT_MODE,
                        "rollout_shadow": use_shadow,
                    },
                    status="shadow",
                )
                logger.info(
                    "👻 Expert %s generated shadow mutation from insights task (mode=%s)",
                    expert["name"],
                    EVOLUTION_ROLLOUT_MODE,
                )
                return True
            await conn.execute(
                """
                UPDATE experts
                SET system_prompt = $1, version = $2,
                    metadata = metadata || jsonb_build_object(
                        'last_evolution', NOW(),
                        'evolution_source', 'insights_task',
                        'evolution_task_id', $3::text
                    )
                WHERE id = $4
            """,
                new_prompt.strip(),
                new_version,
                task_id,
                expert_id,
            )
            await self._record_mutation_event(
                conn=conn,
                expert_id=expert_id,
                mutated_prompt=new_prompt.strip(),
                base_version=base_version,
                source="insights_task",
                metrics={
                    "new_version": new_version,
                    "task_id": task_id,
                    "rollout_mode": EVOLUTION_ROLLOUT_MODE,
                    "rollout_shadow": use_shadow,
                },
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

        if not EVOLUTION_ENABLE_EXPERT_REMOVAL:
            logger.info("ℹ️ Expert removal disabled by EVOLUTION_ENABLE_EXPERT_REMOVAL=false")
            return removed

        for metrics in metrics_list:
            # Критерии удаления:
            # 1. Низкий success_rate (< REMOVAL_THRESHOLD)
            # 2. Низкая активность (< 5 использований за 30 дней)
            # 3. Нет активности более 60 дней
            enough_signal = metrics.usage_count >= EVOLUTION_MIN_USAGE_FOR_REMOVAL
            stale_long_enough = (
                metrics.last_activity and (datetime.now() - metrics.last_activity).days > 60
            )
            should_remove = (enough_signal and metrics.success_rate < REMOVAL_THRESHOLD) or (
                stale_long_enough and metrics.usage_count >= 5
            )

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
                                'removal_metrics', $1::jsonb
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

                new_prompt = await run_mutation_agent(specialization_prompt)

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


def _resolve_expert_name_for_db(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    try:
        from app.expert_aliases import resolve_expert_name_for_db

        return resolve_expert_name_for_db(name)
    except Exception:
        return name


def _clamp_ratio(val: float) -> float:
    return max(0.0, min(1.0, val))


def _stable_rollout_bucket(expert_id: str) -> float:
    digest = hashlib.sha1((expert_id or "").encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _use_shadow_rollout(expert_id: str, metrics: Optional[ExpertMetrics]) -> bool:
    """
    Canary/Shadow rollout policy (world practice):
    - direct: apply immediately
    - shadow: evaluate in production shadow lane first
    - hybrid: deterministic expert split + safety guards
    """
    mode = (EVOLUTION_ROLLOUT_MODE or "direct").lower()
    if mode == "shadow":
        return True
    if mode == "direct":
        return False
    if mode != "hybrid":
        logger.warning("Unknown EVOLUTION_ROLLOUT_MODE=%s, fallback to direct.", mode)
        return False

    shadow_ratio = _clamp_ratio(EVOLUTION_HYBRID_SHADOW_RATIO)
    if metrics:
        has_enough_signal = metrics.usage_count >= EVOLUTION_HYBRID_MIN_USAGE_FOR_DIRECT
        strong_quality = (
            metrics.success_rate >= EVOLUTION_HYBRID_MIN_SUCCESS_FOR_DIRECT
            and metrics.task_completion_rate >= EVOLUTION_HYBRID_MIN_COMPLETION_FOR_DIRECT
        )
        if not (has_enough_signal and strong_quality):
            return True

    return _stable_rollout_bucket(expert_id) < shadow_ratio


async def run_enhanced_evolution_cycle(expert_name: Optional[str] = None):
    """Основной цикл автоматической эволюции экспертов"""
    logger.info("🧬 Starting Enhanced Expert Evolution cycle...")
    target_expert_name = _resolve_expert_name_for_db(expert_name)

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
            if target_expert_name:
                experts = await conn.fetch(
                    """
                    SELECT id
                    FROM experts
                    WHERE (is_active IS NULL OR is_active = TRUE)
                      AND system_prompt IS NOT NULL
                      AND LENGTH(TRIM(system_prompt)) > 50
                      AND name = $1
                    LIMIT 1
                    """,
                    target_expert_name,
                )
            else:
                experts = await conn.fetch(
                    """
                    SELECT id FROM experts
                    WHERE (is_active IS NULL OR is_active = TRUE)
                      AND system_prompt IS NOT NULL AND LENGTH(TRIM(system_prompt)) > 50
                    ORDER BY RANDOM()
                    LIMIT 3
                    """
                )
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
    if target_expert_name:
        metrics_list = [m for m in metrics_list if (m.name or "").strip() == target_expert_name]

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

    # 4. Fail-safe: если не найдено кандидатов по строгим порогам,
    # пробуем минимум одну эволюцию наиболее активного эксперта.
    if EVOLUTION_FORCE_MINIMUM_MUTATION and evolved_count == 0 and insights_evolved == 0:
        fallback_done = False
        fallback_candidates = [
            m for m in metrics_list if (m.usage_count > 0 or m.knowledge_created > 0)
        ]
        if fallback_candidates:
            fallback_candidates.sort(
                key=lambda m: (m.usage_count, m.knowledge_created, m.task_completion_rate),
                reverse=True,
            )
            candidate = fallback_candidates[0]
            logger.info(
                "🛟 No strict evolution candidates, trying fallback mutation for expert %s",
                candidate.name,
            )
            if await evolver.evolve_expert(candidate.expert_id, candidate):
                evolved_count += 1
                fallback_done = True

        if not fallback_done:
            logger.info("🛟 No metrics candidates available, trying insights fallback mutation")
            conn = await asyncpg.connect(DB_URL)
            try:
                if target_expert_name:
                    expert = await conn.fetchrow(
                        """
                        SELECT id
                        FROM experts
                        WHERE (is_active IS NULL OR is_active = TRUE)
                          AND system_prompt IS NOT NULL
                          AND LENGTH(TRIM(system_prompt)) > 50
                          AND name = $1
                        LIMIT 1
                        """,
                        target_expert_name,
                    )
                else:
                    expert = await conn.fetchrow(
                        """
                        SELECT id
                        FROM experts
                        WHERE (is_active IS NULL OR is_active = TRUE)
                          AND system_prompt IS NOT NULL
                          AND LENGTH(TRIM(system_prompt)) > 50
                        ORDER BY RANDOM()
                        LIMIT 1
                        """
                    )
                if expert:
                    recent_insights = await conn.fetch(
                        """
                        SELECT content
                        FROM knowledge_nodes
                        WHERE is_verified = TRUE
                        ORDER BY COALESCE(updated_at, created_at) DESC
                        LIMIT 5
                        """
                    )
                    insight_text = "\n\n".join(
                        (row["content"] or "")[:600] for row in recent_insights if row["content"]
                    )
                    if not insight_text:
                        insight_text = (
                            "Оптимизируй системный промпт для более точной аргументации, "
                            "структурированных ответов и устойчивой самопроверки."
                        )
                    if await evolver.evolve_expert_from_insights(
                        conn,
                        str(expert["id"]),
                        insight_text,
                        task_id=None,
                    ):
                        evolved_count += 1
                        insights_evolved += 1
                        fallback_done = True
            finally:
                await conn.close()

    logger.info("✅ Evolution cycle completed:")
    logger.info(f"   - Evolved: {evolved_count}")
    logger.info(f"   - Specialized: {specialized_count}")
    logger.info(f"   - Removed: {removed_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run enhanced expert evolution cycle.")
    parser.add_argument("--expert_name", type=str, help="Run evolution for one expert only")
    args = parser.parse_args()
    asyncio.run(run_enhanced_evolution_cycle(expert_name=args.expert_name))
