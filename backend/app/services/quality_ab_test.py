"""
Фаза 4: A/B тестирование улучшений качества RAG.
Варианты: reranking method, query rewriting, similarity threshold.
"""
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _default_results_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "ab_test_quality_results.json"


class QualityABTest:
    """A/B тестирование улучшений качества RAG."""

    def __init__(self, results_path: Optional[str] = None):
        self.results_path = Path(results_path) if results_path else _default_results_path()
        self.experiments = {
            "reranking_method": {
                "variants": {
                    "control": {"method": None},
                    "text_similarity": {"method": "text_similarity"},
                    "hybrid": {"method": "hybrid"},
                },
                "weights": [0.34, 0.33, 0.33],
            },
            "query_rewriting": {
                "variants": {
                    "control": {"enabled": False},
                    "simple": {"enabled": True, "mode": "simple"},
                },
                "weights": [0.5, 0.5],
            },
            "similarity_threshold": {
                "variants": {
                    "control": {"threshold": 0.75},
                    "higher": {"threshold": 0.80},
                    "lower": {"threshold": 0.70},
                },
                "weights": [0.34, 0.33, 0.33],
            },
        }
        self.results: Dict[str, Dict] = {}
        self._load_results()

    def _load_results(self) -> None:
        if self.results_path.exists():
            try:
                with open(self.results_path, "r", encoding="utf-8") as f:
                    self.results = json.load(f)
            except Exception as e:
                logger.debug("Load AB results failed: %s", e)

    def _save_results(self) -> None:
        try:
            self.results_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.results_path, "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Save AB results failed: %s", e)

    def assign_variant(self, user_id: str, experiment: str) -> str:
        """Назначение варианта пользователю (детерминированно)."""
        if experiment not in self.experiments:
            return "control"
        hash_input = f"{user_id}_{experiment}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
        weights = self.experiments[experiment]["weights"]
        cumulative = 0.0
        variants = list(self.experiments[experiment]["variants"].keys())
        for variant, weight in zip(variants, weights):
            cumulative += weight
            if (hash_value % 100) < (cumulative * 100):
                return variant
        return "control"

    def track_result(
        self,
        experiment: str,
        variant: str,
        metrics: Dict[str, float],
        user_id: Optional[str] = None,
    ) -> None:
        """Запись результатов A/B теста."""
        key = f"{experiment}:{variant}"
        if key not in self.results:
            self.results[key] = {
                "count": 0,
                "metrics": {k: 0.0 for k in metrics.keys()},
                "users": [],
            }
        self.results[key]["count"] += 1
        for metric, value in metrics.items():
            self.results[key]["metrics"][metric] += value
        if user_id and user_id not in self.results[key]["users"]:
            self.results[key]["users"].append(user_id)
        self._save_results()

    def get_winner(self, experiment: str, primary_metric: str = "relevance") -> str:
        """Определение победившего варианта."""
        if experiment not in self.experiments:
            return "control"
        best_variant = None
        best_score = -1.0
        for variant in self.experiments[experiment]["variants"]:
            key = f"{experiment}:{variant}"
            if key in self.results and self.results[key]["count"] > 0:
                avg = self.results[key]["metrics"].get(primary_metric, 0) / self.results[key]["count"]
                if avg > best_score:
                    best_score = avg
                    best_variant = variant
        return best_variant or "control"

    def get_summary(self, experiment: str) -> Dict[str, Any]:
        """Сводка по эксперименту."""
        if experiment not in self.experiments:
            return {}
        variants = {}
        for variant in self.experiments[experiment]["variants"]:
            key = f"{experiment}:{variant}"
            if key in self.results and self.results[key]["count"] > 0:
                count = self.results[key]["count"]
                avg_metrics = {
                    m: v / count
                    for m, v in self.results[key]["metrics"].items()
                }
                variants[variant] = {
                    "count": count,
                    "avg_metrics": avg_metrics,
                    "users": len(self.results[key]["users"]),
                }
        return {"experiment": experiment, "variants": variants, "timestamp": datetime.now().isoformat()}
