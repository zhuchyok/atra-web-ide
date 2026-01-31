"""
A/B тестирование оптимизаций (День 6–7, Фаза 3).
Сравнение вариантов параметров: RAG threshold, agent suggestion, batch size.
"""
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Конфигурация эксперимента A/B теста."""

    name: str
    description: str
    enabled: bool = True
    variants: Dict[str, float] = field(default_factory=lambda: {"control": 50, "variant_a": 50})
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.start_date is None:
            self.start_date = datetime.now()
        if self.end_date is None:
            self.end_date = self.start_date + timedelta(days=7)
        if not self.parameters:
            self.parameters = {}


class ABTestingService:
    """Сервис управления A/B тестами."""

    def __init__(self, experiments_file: Optional[str] = None) -> None:
        self.experiments: Dict[str, ExperimentConfig] = {}
        self.user_variants: Dict[str, Dict[str, str]] = {}
        self.metrics: Dict[str, Dict[str, Any]] = {}

        if experiments_file:
            self.load_experiments(experiments_file)

        self._init_default_experiments()

    def _init_default_experiments(self) -> None:
        """Инициализация дефолтных экспериментов."""
        default_experiments = [
            ExperimentConfig(
                name="rag_light_threshold",
                description="Оптимальный порог similarity для RAG-light",
                variants={"control": 33, "low": 34, "high": 33},
                parameters={
                    "control": {"threshold": 0.75},
                    "low": {"threshold": 0.65},
                    "high": {"threshold": 0.85},
                },
            ),
            ExperimentConfig(
                name="agent_suggestion_threshold",
                description="Порог для рекомендации перехода в Agent",
                variants={"control": 50, "aggressive": 50},
                parameters={
                    "control": {"threshold": 0.6},
                    "aggressive": {"threshold": 0.5},
                },
            ),
            ExperimentConfig(
                name="embedding_batch_size",
                description="Оптимальный размер батча для эмбеддингов",
                variants={"control": 50, "batch_5": 25, "batch_20": 25},
                parameters={
                    "control": {"batch_size": 10},
                    "batch_5": {"batch_size": 5},
                    "batch_20": {"batch_size": 20},
                },
            ),
        ]
        for exp in default_experiments:
            self.experiments[exp.name] = exp

    def get_variant(self, user_id: str, experiment_name: str) -> Optional[str]:
        """Определение варианта для пользователя (детерминировано по хэшу)."""
        if experiment_name not in self.experiments:
            return None

        exp = self.experiments[experiment_name]
        if not exp.enabled:
            return "control"

        if user_id in self.user_variants and experiment_name in self.user_variants[user_id]:
            return self.user_variants[user_id][experiment_name]

        hash_input = f"{user_id}:{experiment_name}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
        variant_num = hash_value % 100

        cumulative = 0
        for variant_name, percentage in exp.variants.items():
            cumulative += percentage
            if variant_num < cumulative:
                if user_id not in self.user_variants:
                    self.user_variants[user_id] = {}
                self.user_variants[user_id][experiment_name] = variant_name
                return variant_name

        return "control"

    def get_experiment_parameter(
        self, user_id: str, experiment_name: str, param_name: str
    ) -> Any:
        """Получение значения параметра для пользователя в эксперименте."""
        variant = self.get_variant(user_id, experiment_name)
        if not variant:
            return None

        exp = self.experiments.get(experiment_name)
        if not exp:
            return None

        if variant in exp.parameters and param_name in exp.parameters[variant]:
            return exp.parameters[variant][param_name]
        if "control" in exp.parameters and param_name in exp.parameters["control"]:
            return exp.parameters["control"][param_name]
        return None

    def track_event(
        self,
        user_id: str,
        experiment_name: str,
        event_name: str,
        value: float = 1.0,
    ) -> None:
        """Трекинг события в эксперименте."""
        variant = self.get_variant(user_id, experiment_name)
        if not variant:
            return

        key = f"{experiment_name}:{variant}:{event_name}"
        if key not in self.metrics:
            self.metrics[key] = {
                "count": 0,
                "total": 0.0,
                "min": float("inf"),
                "max": float("-inf"),
            }
        self.metrics[key]["count"] += 1
        self.metrics[key]["total"] += value
        self.metrics[key]["min"] = min(self.metrics[key]["min"], value)
        self.metrics[key]["max"] = max(self.metrics[key]["max"], value)

    def get_experiment_stats(self, experiment_name: str) -> Dict[str, Any]:
        """Статистика по эксперименту."""
        if experiment_name not in self.experiments:
            return {}

        stats: Dict[str, Any] = {}
        exp = self.experiments[experiment_name]

        for variant in exp.variants.keys():
            variant_stats: Dict[str, Any] = {"user_count": 0, "events": {}}
            for user_id, variants in self.user_variants.items():
                if experiment_name in variants and variants[experiment_name] == variant:
                    variant_stats["user_count"] += 1

            prefix = f"{experiment_name}:{variant}:"
            for key, metric in self.metrics.items():
                if key.startswith(prefix):
                    event_name = key[len(prefix) :]
                    variant_stats["events"][event_name] = {
                        "count": metric["count"],
                        "avg": (
                            metric["total"] / metric["count"]
                            if metric["count"] > 0
                            else 0
                        ),
                        "min": metric["min"] if metric["min"] != float("inf") else None,
                        "max": metric["max"] if metric["max"] != float("-inf") else None,
                    }
            stats[variant] = variant_stats

        return stats

    def load_experiments(self, filepath: str) -> None:
        """Загрузка экспериментов из JSON файла."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            for exp_data in data:
                name = exp_data.get("name")
                if not name:
                    continue
                for key in ("start_date", "end_date"):
                    if key in exp_data and isinstance(exp_data[key], str):
                        try:
                            exp_data[key] = datetime.fromisoformat(
                                exp_data[key].replace("Z", "+00:00")
                            )
                        except Exception:
                            exp_data[key] = None
                exp = ExperimentConfig(**{k: v for k, v in exp_data.items() if k in ("name", "description", "enabled", "variants", "parameters", "start_date", "end_date")})
                self.experiments[exp.name] = exp
            logger.info("Loaded %d experiments from %s", len(data), filepath)
        except Exception as e:
            logger.error("Error loading experiments: %s", e)

    def save_experiments(self, filepath: str) -> None:
        """Сохранение экспериментов в файл."""
        try:
            data = [
                asdict(exp)
                for exp in self.experiments.values()
            ]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, default=str, indent=2, ensure_ascii=False)
            logger.info("Saved %d experiments to %s", len(data), filepath)
        except Exception as e:
            logger.error("Error saving experiments: %s", e)


_ab_testing_instance: Optional[ABTestingService] = None


def get_ab_testing_service(experiments_file: Optional[str] = None) -> ABTestingService:
    """Синглтон сервиса A/B тестирования."""
    global _ab_testing_instance
    if _ab_testing_instance is None:
        _ab_testing_instance = ABTestingService(experiments_file=experiments_file)
    return _ab_testing_instance
