"""
Фаза 4, День 1: Пайплайн регулярной валидации качества RAG.

Запуск полной валидации на тестовых запросах, оценка метрик (faithfulness, relevance, coherence),
сохранение результатов в validation_results/.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from datetime import datetime

logger = logging.getLogger(__name__)


def _resolve_validation_path(validation_path: str) -> Path:
    """Разрешает путь к validation set: абсолютный, относительно cwd или repo root."""
    p = Path(validation_path)
    if p.is_absolute() and p.exists():
        return p
    if p.exists():
        return p.resolve()
    # backend/app/services -> parent*3 = backend; repo root = parent of backend
    backend = Path(__file__).resolve().parent.parent.parent
    repo_root = backend.parent
    candidate = repo_root / validation_path
    if candidate.exists():
        return candidate
    return Path(validation_path)


class ValidationPipeline:
    """Пайплайн для регулярной валидации качества RAG."""

    def __init__(self, validation_path: str, rag_service: Any, evaluator: Any):
        self.validation_path = _resolve_validation_path(validation_path)
        self.rag_service = rag_service
        self.evaluator = evaluator
        self.results: List[Dict] = []
        self.metrics_history: List[Dict] = []

    def load_validation_queries(self) -> List[Dict]:
        """Загружает тестовые запросы из JSON."""
        if not self.validation_path.exists():
            logger.warning("Validation path does not exist: %s", self.validation_path)
            return []
        with open(self.validation_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        queries = data.get("queries", data) if isinstance(data, dict) else data
        return [q if isinstance(q, dict) else {"query": str(q)} for q in queries]

    async def run_validation(self, sample_size: Optional[int] = None) -> Dict:
        """Запуск полной валидации."""
        logger.info("Starting validation pipeline from %s", self.validation_path)

        test_queries = self.load_validation_queries()
        if not test_queries:
            return {
                "avg_metrics": {},
                "total_processed": 0,
                "sample_size": 0,
                "error": "No validation queries found",
            }

        if sample_size and sample_size < len(test_queries):
            import random
            test_queries = random.sample(test_queries, sample_size)

        results: List[Dict] = []
        total_metrics: Dict[str, float] = {
            "faithfulness": 0.0,
            "relevance": 0.0,
            "coherence": 0.0,
            "count": 0.0,
        }

        for i, test_case in enumerate(test_queries):
            query = test_case.get("query", "")
            if not query:
                continue
            logger.debug(
                "Processing test case %s/%s: %s...",
                i + 1,
                len(test_queries),
                query[:50],
            )

            try:
                answer = await self.rag_service.fast_fact_answer(
                    query,
                    timeout_ms=5000,
                )

                context = await self._get_context_for_query(query)

                evaluation = await self.evaluator.evaluate_response(
                    query=query,
                    response=answer or "",
                    context=context,
                    reference=test_case.get("reference"),
                )

                result = {
                    "query": query,
                    "answer": answer,
                    "evaluation": evaluation,
                    "context": context,
                    "timestamp": datetime.now().isoformat(),
                }
                results.append(result)

                for metric in ("faithfulness", "relevance", "coherence"):
                    if metric in evaluation:
                        total_metrics[metric] += evaluation[metric]
                total_metrics["count"] += 1

                if (i + 1) % 10 == 0:
                    logger.info("Processed %s/%s queries", i + 1, len(test_queries))

            except Exception as e:
                logger.error(
                    "Error processing query '%s...': %s",
                    query[:50],
                    e,
                    exc_info=True,
                )

        avg_metrics: Dict[str, float] = {}
        if total_metrics["count"] > 0:
            for metric in ("faithfulness", "relevance", "coherence"):
                avg_metrics[metric] = total_metrics[metric] / total_metrics["count"]

        self.results = results
        self.metrics_history.append({
            "timestamp": datetime.now().isoformat(),
            "metrics": avg_metrics,
            "total_queries": int(total_metrics["count"]),
        })

        await self.save_results(results, avg_metrics)

        return {
            "avg_metrics": avg_metrics,
            "total_processed": int(total_metrics["count"]),
            "sample_size": len(test_queries),
        }

    async def save_results(self, results: List[Dict], avg_metrics: Dict[str, float]) -> None:
        """Сохранение результатов валидации в validation_results/."""
        backend = Path(__file__).resolve().parent.parent.parent
        output_dir = backend / "validation_results"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"validation_{timestamp}.json"

        data = {
            "timestamp": datetime.now().isoformat(),
            "avg_metrics": avg_metrics,
            "results": results,
            "summary": {
                "total_queries": len(results),
                "avg_faithfulness": avg_metrics.get("faithfulness", 0),
                "avg_relevance": avg_metrics.get("relevance", 0),
                "avg_coherence": avg_metrics.get("coherence", 0),
            },
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("Validation results saved to %s", output_file)

    async def _get_context_for_query(self, query: str) -> List[str]:
        """Получение контекста для запроса (для оценки faithfulness)."""
        try:
            if hasattr(self.rag_service, "get_chunks_for_query"):
                return await self.rag_service.get_chunks_for_query(query, limit=5)
            if hasattr(self.rag_service, "get_last_context"):
                return await self.rag_service.get_last_context()
        except Exception as e:
            logger.warning("Could not get context for evaluation: %s", e)
        return []
