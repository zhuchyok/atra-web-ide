#!/usr/bin/env python3
"""
Мониторинг pipeline фильтрации сигналов
"""

import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)


class PipelineMonitor:
    """Мониторинг pipeline фильтрации сигналов"""

    def __init__(self):
        self.stats = {
            "total_attempts": 0,
            "validation_passed": 0,
            "ai_score_passed": 0,
            "volume_passed": 0,
            "volatility_passed": 0,
            "ema_pattern_passed": 0,
            "final_signals": 0,
            "pattern_types": {
                "classic_ema": 0,
                "alternative_1": 0,
                "alternative_2": 0,
                "alternative_3": 0,
                "short_classic_ema": 0,
                "short_alternative_1": 0,
                "short_alternative_2": 0,
                "short_alternative_3": 0,
            },
        }
        self.start_time = time.time()

    def log_stage(self, stage: str, symbol: str, passed: bool, details: str = ""):
        """Логирование прохождения этапа pipeline"""
        self.stats["total_attempts"] += 1

        if passed:
            if stage == "validation":
                self.stats["validation_passed"] += 1
            elif stage == "ai_score":
                self.stats["ai_score_passed"] += 1
            elif stage == "volume":
                self.stats["volume_passed"] += 1
            elif stage == "volatility":
                self.stats["volatility_passed"] += 1
            elif stage == "ema_pattern":
                self.stats["ema_pattern_passed"] += 1
            elif stage == "final_signal":
                self.stats["final_signals"] += 1

        logger.debug(
            "📊 [%s] %s: %s %s", symbol, stage, "✅ ПРОЙДЕН" if passed else "❌ ОТКЛОНЕН", details
        )

    def log_pattern_type(self, pattern_type: str):
        """Логирование типа паттерна"""
        if pattern_type in self.stats["pattern_types"]:
            self.stats["pattern_types"][pattern_type] += 1

    def get_success_rates(self) -> Dict[str, float]:
        """Получение коэффициентов успешности по этапам"""
        if self.stats["total_attempts"] == 0:
            return {}

        rates = {
            "validation_rate": self.stats["validation_passed"] / self.stats["total_attempts"],
            "ai_score_rate": self.stats["ai_score_passed"]
            / max(self.stats["validation_passed"], 1),
            "volume_rate": self.stats["volume_passed"] / max(self.stats["ai_score_passed"], 1),
            "volatility_rate": self.stats["volatility_passed"]
            / max(self.stats["volume_passed"], 1),
            "ema_pattern_rate": self.stats["ema_pattern_passed"]
            / max(self.stats["volatility_passed"], 1),
            "final_rate": self.stats["final_signals"] / max(self.stats["ema_pattern_passed"], 1),
            "overall_rate": self.stats["final_signals"] / self.stats["total_attempts"],
        }
        return rates

    def get_pattern_distribution(self) -> Dict[str, float]:
        """Получение распределения паттернов"""
        total_patterns = sum(self.stats["pattern_types"].values())
        if total_patterns == 0:
            return {}

        return {
            pattern: count / total_patterns
            for pattern, count in self.stats["pattern_types"].items()
        }

    def print_stats(self):
        """Вывод статистики pipeline"""
        rates = self.get_success_rates()
        patterns = self.get_pattern_distribution()

        logger.info("📊 PIPELINE STATISTICS:")
        logger.info("  🔍 Всего попыток: %d", self.stats["total_attempts"])
        logger.info(
            "  ✅ Валидация: %.1f%% (%d/%d)",
            rates.get("validation_rate", 0) * 100,
            self.stats["validation_passed"],
            self.stats["total_attempts"],
        )
        logger.info(
            "  🤖 ИИ-скор: %.1f%% (%d/%d)",
            rates.get("ai_score_rate", 0) * 100,
            self.stats["ai_score_passed"],
            self.stats["validation_passed"],
        )
        logger.info(
            "  📈 Объем: %.1f%% (%d/%d)",
            rates.get("volume_rate", 0) * 100,
            self.stats["volume_passed"],
            self.stats["ai_score_passed"],
        )
        logger.info(
            "  📊 Волатильность: %.1f%% (%d/%d)",
            rates.get("volatility_rate", 0) * 100,
            self.stats["volatility_passed"],
            self.stats["volume_passed"],
        )
        logger.info(
            "  🎯 EMA паттерны: %.1f%% (%d/%d)",
            rates.get("ema_pattern_rate", 0) * 100,
            self.stats["ema_pattern_passed"],
            self.stats["volatility_passed"],
        )
        logger.info(
            "  🚀 Финальные сигналы: %.1f%% (%d/%d)",
            rates.get("final_rate", 0) * 100,
            self.stats["final_signals"],
            self.stats["ema_pattern_passed"],
        )
        logger.info(
            "  📈 ОБЩАЯ ПРОХОДИМОСТЬ: %.1f%% (%d/%d)",
            rates.get("overall_rate", 0) * 100,
            self.stats["final_signals"],
            self.stats["total_attempts"],
        )

        if patterns:
            logger.info("  🎨 РАСПРЕДЕЛЕНИЕ ПАТТЕРНОВ:")
            for pattern, rate in patterns.items():
                logger.info(
                    "    • %s: %.1f%% (%d)",
                    pattern.replace("_", " ").title(),
                    rate * 100,
                    self.stats["pattern_types"][pattern],
                )
