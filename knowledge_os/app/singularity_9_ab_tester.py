"""
Singularity 9.0 A/B Tester: Централизованное A/B тестирование всех 4 гипотез

Функционал:
- Централизованное A/B тестирование всех 4 гипотез
- Сбор метрик из всех компонентов
- Автоматический выбор победителя (на основе целевых метрик)
"""

import asyncio
import importlib.util
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# evaluator загружаем через importlib из этого каталога или используем уже загруженный (дашборд предзагружает).
_this_dir = os.path.dirname(os.path.abspath(__file__))
get_pool = None
try:
    if "evaluator" in sys.modules:
        get_pool = getattr(sys.modules["evaluator"], "get_pool", None)
    if get_pool is None:
        _evaluator_path = os.path.join(_this_dir, "evaluator.py")
        if os.path.isfile(_evaluator_path):
            _spec = importlib.util.spec_from_file_location("evaluator", _evaluator_path)
            if _spec and _spec.loader:
                _evaluator = importlib.util.module_from_spec(_spec)
                sys.modules["evaluator"] = _evaluator
                _spec.loader.exec_module(_evaluator)
                get_pool = getattr(_evaluator, "get_pool", None)
except Exception as e:
    get_pool = None  # type: ignore
    logging.warning("[SINGULARITY_9] evaluator not loaded: %s. Метрики будут пустыми.", e)

# Import A/B testing infrastructure
try:
    from prompt_ab_testing import PromptABTesting

    AB_TESTING_AVAILABLE = True
except ImportError:
    AB_TESTING_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

# Целевые метрики для каждой гипотезы
TARGET_METRICS = {
    "tacit_knowledge": {
        "metric_name": "style_similarity_score",
        "target_value": 0.85,
        "comparison": ">=",
    },
    "emotion_modulation": {
        "metric_name": "satisfaction_delta",
        "target_value": 0.15,  # 15% увеличение
        "comparison": ">=",
    },
    "code_smell_predictor": {"metric_name": "precision", "target_value": 0.70, "comparison": ">="},
    "predictive_compression": {
        "metric_name": "latency_reduction",
        "target_value": 0.30,  # 30% снижение
        "comparison": ">=",
    },
}


@dataclass
class HypothesisMetrics:
    """Метрики для гипотезы Singularity 9.0"""

    hypothesis_name: (
        str  # tacit_knowledge, emotion_modulation, code_smell_predictor, predictive_compression
    )
    variant: str  # A (с гипотезой) или B (без гипотезы)
    metric_value: float
    sample_size: int
    created_at: datetime


class Singularity9ABTester:
    """Класс для централизованного A/B тестирования гипотез Singularity 9.0"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.ab_tester = PromptABTesting(db_url) if AB_TESTING_AVAILABLE else None

    async def collect_tacit_knowledge_metrics(self, days: int = 7) -> Dict[str, float]:
        """
        Собирает метрики для Tacit Knowledge Extractor.

        Returns:
            Словарь с метриками {variant: metric_value}
        """
        if get_pool is None:
            logger.debug("[SINGULARITY_9] get_pool is None (evaluator not loaded); metrics empty")
            return {}
        pool = await get_pool()
        if pool is None:
            logger.debug(
                "[SINGULARITY_9] pool is None (asyncpg failed or evaluator get_pool returned None); metrics empty"
            )
            return {}
        async with pool.acquire() as conn:
            # Получаем style_similarity_score из interaction_logs.metadata
            rows = await conn.fetch(
                """
                SELECT
                    CASE
                        WHEN metadata->>'style_similarity' IS NOT NULL THEN 'A'  -- С гипотезой
                        ELSE 'B'  -- Без гипотезы
                    END as variant,
                    AVG((metadata->>'style_similarity')::float) as avg_similarity,
                    COUNT(*) as sample_size
                FROM interaction_logs
                WHERE created_at > NOW() - INTERVAL '1 day' * $1
                  AND (metadata->>'style_similarity' IS NOT NULL OR metadata->>'style_similarity' IS NULL)
                GROUP BY variant
            """,
                days,
            )

            metrics = {}
            for row in rows:
                variant = row["variant"]
                avg_similarity = float(row["avg_similarity"] or 0.0)
                sample_size = row["sample_size"]
                metrics[variant] = {"value": avg_similarity, "sample_size": sample_size}

            return metrics

    async def collect_emotion_modulation_metrics(self, days: int = 7) -> Dict[str, float]:
        """
        Собирает метрики для Emotional Response Modulation.

        Returns:
            Словарь с метриками {variant: satisfaction_delta}
        """
        if get_pool is None:
            logger.debug("[SINGULARITY_9] get_pool is None (evaluator not loaded); metrics empty")
            return {}
        pool = await get_pool()
        if pool is None:
            logger.debug(
                "[SINGULARITY_9] pool is None (asyncpg failed or evaluator get_pool returned None); metrics empty"
            )
            return {}
        async with pool.acquire() as conn:
            # Получаем feedback_score из interaction_logs с эмоциональной адаптацией
            rows = await conn.fetch(
                """
                SELECT
                    CASE
                        WHEN el.detected_emotion IS NOT NULL THEN 'A'  -- С гипотезой
                        ELSE 'B'  -- Без гипотезы
                    END as variant,
                    AVG(il.feedback_score::float) as avg_feedback,
                    COUNT(*) as sample_size
                FROM interaction_logs il
                LEFT JOIN emotion_logs el ON el.interaction_log_id = il.id::text
                WHERE il.created_at > NOW() - INTERVAL '1 day' * $1
                  AND il.feedback_score IS NOT NULL
                GROUP BY variant
            """,
                days,
            )

            metrics = {}
            baseline_feedback = 0.0
            emotion_feedback = 0.0

            for row in rows:
                variant = row["variant"]
                avg_feedback = float(row["avg_feedback"] or 0.0)

                if variant == "A":
                    emotion_feedback = avg_feedback
                else:
                    baseline_feedback = avg_feedback

            # Вычисляем satisfaction_delta
            if baseline_feedback > 0:
                satisfaction_delta = (emotion_feedback - baseline_feedback) / baseline_feedback
            else:
                satisfaction_delta = 0.0

            metrics["A"] = {
                "value": satisfaction_delta,
                "sample_size": sum(row["sample_size"] for row in rows if row["variant"] == "A"),
            }

            return metrics

    async def collect_code_smell_metrics(self, days: int = 30) -> Dict[str, float]:
        """
        Собирает метрики для Code-Smell Predictor.

        Returns:
            Словарь с метриками {precision, recall}
        """
        if get_pool is None:
            logger.debug("[SINGULARITY_9] get_pool is None (evaluator not loaded); metrics empty")
            return {}
        pool = await get_pool()
        if pool is None:
            logger.debug(
                "[SINGULARITY_9] pool is None (asyncpg failed or evaluator get_pool returned None); metrics empty"
            )
            return {}
        async with pool.acquire() as conn:
            # Получаем precision и recall из code_smell_predictions
            row = await conn.fetchrow(
                """
                SELECT
                    AVG(precision_score) as avg_precision,
                    AVG(recall_score) as avg_recall,
                    COUNT(*) as sample_size
                FROM code_smell_predictions
                WHERE created_at > NOW() - INTERVAL '1 day' * $1
                  AND precision_score IS NOT NULL
                  AND recall_score IS NOT NULL
            """,
                days,
            )

            if not row or row["sample_size"] == 0:
                return {}

            return {
                "precision": float(row["avg_precision"] or 0.0),
                "recall": float(row["avg_recall"] or 0.0),
                "sample_size": row["sample_size"],
            }

    async def collect_predictive_compression_metrics(self, days: int = 7) -> Dict[str, float]:
        """
        Собирает метрики для Predictive Compression.

        Returns:
            Словарь с метриками {variant: latency_reduction}
        """
        if get_pool is None:
            logger.debug("[SINGULARITY_9] get_pool is None (evaluator not loaded); metrics empty")
            return {}
        pool = await get_pool()
        if pool is None:
            logger.debug(
                "[SINGULARITY_9] pool is None (asyncpg failed or evaluator get_pool returned None); metrics empty"
            )
            return {}
        async with pool.acquire() as conn:
            # Получаем latency_reduction из interaction_logs.metadata
            rows = await conn.fetch(
                """
                SELECT
                    CASE
                        WHEN metadata->>'latency_reduction' IS NOT NULL THEN 'A'  -- С гипотезой
                        ELSE 'B'  -- Без гипотезы
                    END as variant,
                    AVG((metadata->>'latency_reduction')::float) as avg_latency_reduction,
                    COUNT(*) as sample_size
                FROM interaction_logs
                WHERE created_at > NOW() - INTERVAL '1 day' * $1
                  AND (metadata->>'latency_reduction' IS NOT NULL OR metadata->>'latency_reduction' IS NULL)
                GROUP BY variant
            """,
                days,
            )

            metrics = {}
            for row in rows:
                variant = row["variant"]
                avg_reduction = float(row["avg_latency_reduction"] or 0.0)
                sample_size = row["sample_size"]

                if variant == "A":
                    metrics[variant] = {"value": avg_reduction, "sample_size": sample_size}

            return metrics

    async def validate_metrics(self) -> Dict[str, Dict[str, any]]:
        """
        Валидирует целевые метрики для всех гипотез.

        Returns:
            Словарь с результатами валидации {hypothesis: {achieved, metric_value, target_value}}
        """
        results = {}

        try:
            # Tacit Knowledge
            tacit_metrics = await self.collect_tacit_knowledge_metrics()
            if "A" in tacit_metrics:
                target = TARGET_METRICS["tacit_knowledge"]
                value = tacit_metrics["A"]["value"]
                achieved = value >= target["target_value"]
                results["tacit_knowledge"] = {
                    "achieved": achieved,
                    "metric_value": value,
                    "target_value": target["target_value"],
                    "sample_size": tacit_metrics["A"]["sample_size"],
                }

            # Emotional Modulation
            emotion_metrics = await self.collect_emotion_modulation_metrics()
            if "A" in emotion_metrics:
                target = TARGET_METRICS["emotion_modulation"]
                value = emotion_metrics["A"]["value"]
                achieved = value >= target["target_value"]
                results["emotion_modulation"] = {
                    "achieved": achieved,
                    "metric_value": value,
                    "target_value": target["target_value"],
                    "sample_size": emotion_metrics["A"]["sample_size"],
                }

            # Code-Smell Predictor
            code_smell_metrics = await self.collect_code_smell_metrics()
            if "precision" in code_smell_metrics:
                target = TARGET_METRICS["code_smell_predictor"]
                value = code_smell_metrics["precision"]
                achieved = value >= target["target_value"]
                results["code_smell_predictor"] = {
                    "achieved": achieved,
                    "metric_value": value,
                    "target_value": target["target_value"],
                    "recall": code_smell_metrics.get("recall", 0.0),
                    "sample_size": code_smell_metrics.get("sample_size", 0),
                }

            # Predictive Compression
            compression_metrics = await self.collect_predictive_compression_metrics()
            if "A" in compression_metrics:
                target = TARGET_METRICS["predictive_compression"]
                value = compression_metrics["A"]["value"]
                achieved = value >= target["target_value"]
                results["predictive_compression"] = {
                    "achieved": achieved,
                    "metric_value": value,
                    "target_value": target["target_value"],
                    "sample_size": compression_metrics["A"]["sample_size"],
                }
        except Exception as e:
            logger.error(f"❌ [SINGULARITY 9 AB TEST] Error validating metrics: {e}")

        return results

    async def run_ab_test_cycle(self):
        """Запускает цикл A/B тестирования всех гипотез"""
        logger.info("🚀 [SINGULARITY 9 AB TEST] Starting A/B test cycle...")

        results = await self.validate_metrics()

        # Логируем результаты
        for hypothesis, result in results.items():
            status = "✅" if result["achieved"] else "⚠️"
            logger.info(
                f"{status} [SINGULARITY 9 AB TEST] {hypothesis}: {result['metric_value']:.2%} (target: {result['target_value']:.2%}, achieved: {result['achieved']})"
            )

        # Создаем уведомления для не достигнутых метрик
        if get_pool is None:
            logger.debug(
                "[SINGULARITY_9] get_pool is None (evaluator not loaded); skip notifications"
            )
            return
        pool = await get_pool()
        if pool is None:
            logger.debug(
                "[SINGULARITY_9] pool is None (asyncpg failed or evaluator get_pool returned None); skip notifications"
            )
            return
        async with pool.acquire() as conn:
            for hypothesis, result in results.items():
                if not result["achieved"]:
                    await conn.execute(
                        """
                        INSERT INTO notifications (message, type)
                        VALUES ($1, 'system_alert')
                    """,
                        f"⚠️ Singularity 9.0: {hypothesis} не достигнута целевая метрика ({result['metric_value']:.2%} < {result['target_value']:.2%})",
                    )


async def run_singularity_9_ab_test():
    """Обертка для запуска A/B тестирования"""
    tester = Singularity9ABTester()
    await tester.run_ab_test_cycle()


if __name__ == "__main__":
    asyncio.run(run_singularity_9_ab_test())
