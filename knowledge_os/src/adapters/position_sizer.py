#!/usr/bin/env python3

"""
Adaptive Position Sizer - адаптивный расчет размера позиции
Увеличивает размер для качественных сетапов, уменьшает для слабых
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class AdaptivePositionSizer:
    """
    Адаптивный размер позиции на основе качества сетапа

    Учитывает:
    - Composite Signal (score + confidence)
    - Quality Score
    - Pattern Confidence
    - Market Regime
    - Volatility
    """

    def __init__(self):
        self.sizing_history = []

        # Настройки
        self.settings = {
            "enabled": True,
            "max_multiplier": 1.5,  # Макс +50%
            "min_multiplier": 0.5,  # Мин -50%
            "weights": {
                "composite": 0.40,  # 40% веса
                "quality": 0.30,  # 30% веса
                "regime": 0.20,  # 20% веса
                "volatility": 0.10,  # 10% веса
            },
        }

    def calculate_quality_multiplier(self, setup_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Рассчитывает множитель размера позиции

        Args:
            setup_data: {
                'composite_score': float,
                'composite_confidence': float,
                'quality_score': float,
                'pattern_confidence': float,
                'regime': str,
                'regime_confidence': float,
                'volatility_pct': float
            }

        Returns:
            {
                'multiplier': float (0.5-1.5),
                'components': dict,
                'reason': str
            }
        """
        try:
            if not self.settings["enabled"]:
                return {"multiplier": 1.0, "components": {}, "reason": "Disabled"}

            # 1. COMPOSITE SIGNAL FACTOR (40% веса)
            composite_factor = self._calculate_composite_factor(
                setup_data.get("composite_score", 0.5), setup_data.get("composite_confidence", 0.5)
            )

            # 2. QUALITY FACTOR (30% веса)
            quality_factor = self._calculate_quality_factor(
                setup_data.get("quality_score", 0.5), setup_data.get("pattern_confidence", 0.5)
            )

            # 3. REGIME FACTOR (20% веса)
            regime_factor = self._calculate_regime_factor(
                setup_data.get("regime", "NEUTRAL"), setup_data.get("regime_confidence", 0.5)
            )

            # 4. VOLATILITY FACTOR (10% веса)
            volatility_factor = self._calculate_volatility_factor(
                setup_data.get("volatility_pct", 0.03)
            )

            # Взвешенная комбинация
            weights = self.settings["weights"]
            combined_factor = (
                composite_factor * weights["composite"]
                + quality_factor * weights["quality"]
                + regime_factor * weights["regime"]
                + volatility_factor * weights["volatility"]
            )

            # Применяем ограничения
            final_multiplier = max(
                self.settings["min_multiplier"],
                min(self.settings["max_multiplier"], combined_factor),
            )

            # Логируем
            logger.info(
                "📊 [ADAPTIVE SIZE] %s: множитель=%.2f (composite=%.2f, quality=%.2f, regime=%.2f, vol=%.2f)",
                setup_data.get("symbol", "N/A"),
                final_multiplier,
                composite_factor,
                quality_factor,
                regime_factor,
                volatility_factor,
            )

            return {
                "multiplier": final_multiplier,
                "components": {
                    "composite_factor": composite_factor,
                    "quality_factor": quality_factor,
                    "regime_factor": regime_factor,
                    "volatility_factor": volatility_factor,
                },
                "reason": self._get_reason(final_multiplier),
            }

        except Exception as e:
            logger.error("❌ Ошибка расчета adaptive sizing: %s", e)
            return {"multiplier": 1.0, "components": {}, "reason": "Error"}

    def _calculate_composite_factor(self, score: float, confidence: float) -> float:
        """Фактор на основе composite signal"""
        # Комбинация score и confidence
        combined = (score + confidence) / 2

        if combined > 0.85:
            return 1.4  # +40%
        elif combined > 0.75:
            return 1.2  # +20%
        elif combined > 0.65:
            return 1.0  # Норма
        elif combined > 0.55:
            return 0.85  # -15%
        else:
            return 0.7  # -30%

    def _calculate_quality_factor(self, quality: float, confidence: float) -> float:
        """Фактор на основе качества сигнала"""
        # Берем минимум из двух (консервативный подход)
        min_quality = min(quality, confidence)

        if min_quality > 0.85:
            return 1.3  # +30%
        elif min_quality > 0.75:
            return 1.15  # +15%
        elif min_quality > 0.65:
            return 1.0  # Норма
        elif min_quality > 0.55:
            return 0.9  # -10%
        else:
            return 0.75  # -25%

    def _calculate_regime_factor(self, regime: str, confidence: float) -> float:
        """Фактор на основе рыночного режима"""
        base_factors = {
            "BULL_TREND": 1.2,  # +20%
            "BEAR_TREND": 0.85,  # -15%
            "HIGH_VOL_RANGE": 0.9,  # -10%
            "LOW_VOL_RANGE": 1.1,  # +10%
            "CRASH": 0.5,  # -50%
            "NEUTRAL": 1.0,
        }

        base = base_factors.get(regime, 1.0)

        # Корректируем по confidence
        # Если уверенность низкая - смягчаем эффект
        return 1.0 + (base - 1.0) * confidence

    def _calculate_volatility_factor(self, volatility_pct: float) -> float:
        """Фактор на основе волатильности"""
        # Низкая волатильность = больше позиция (меньше риск)
        # Высокая волатильность = меньше позиция (больше риск)

        if volatility_pct < 0.01:  # < 1%
            return 1.2  # +20%
        elif volatility_pct < 0.03:  # < 3%
            return 1.1  # +10%
        elif volatility_pct < 0.05:  # < 5%
            return 1.0  # Норма
        elif volatility_pct < 0.08:  # < 8%
            return 0.9  # -10%
        else:  # > 8%
            return 0.8  # -20%

    def _get_reason(self, multiplier: float) -> str:
        """Описание причины множителя"""
        if multiplier >= 1.3:
            return f"EXCELLENT_SETUP (увеличен на {(multiplier - 1) * 100:.0f}%)"
        elif multiplier >= 1.1:
            return f"GOOD_SETUP (увеличен на {(multiplier - 1) * 100:.0f}%)"
        elif multiplier >= 0.95:
            return "NORMAL_SETUP"
        elif multiplier >= 0.8:
            return f"WEAK_SETUP (уменьшен на {(1 - multiplier) * 100:.0f}%)"
        else:
            return f"POOR_SETUP (уменьшен на {(1 - multiplier) * 100:.0f}%)"

    def get_statistics(self) -> Dict[str, Any]:
        """Статистика по адаптивному sizing"""
        if not self.sizing_history:
            return {}

        multipliers = [h["multiplier"] for h in self.sizing_history[-100:]]  # Последние 100

        return {
            "total_calculations": len(self.sizing_history),
            "recent_avg_multiplier": sum(multipliers) / len(multipliers) if multipliers else 1.0,
            "recent_max_multiplier": max(multipliers) if multipliers else 1.0,
            "recent_min_multiplier": min(multipliers) if multipliers else 1.0,
        }


# Глобальный экземпляр
_adaptive_sizer = None


def get_adaptive_sizer() -> AdaptivePositionSizer:
    """Получение глобального экземпляра"""
    global _adaptive_sizer
    if _adaptive_sizer is None:
        _adaptive_sizer = AdaptivePositionSizer()
        logger.info("✅ AdaptivePositionSizer инициализирован")
    return _adaptive_sizer
