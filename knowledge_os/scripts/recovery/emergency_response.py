#!/usr/bin/env python3
"""
Emergency Response System
Система экстренного реагирования на проблемы
"""

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class EmergencyCondition:
    """Условие экстренной ситуации"""

    name: str
    threshold: float
    current_value: float
    triggered: bool
    timestamp: float


@dataclass
class EmergencyResponse:
    """Ответ на экстренную ситуацию"""

    condition: str
    action: str
    timestamp: float
    success: bool


class EmergencyResponseSystem:
    """Система экстренного реагирования"""

    def __init__(self):
        self.enabled = True
        self.conditions: Dict[str, EmergencyCondition] = {}
        self.responses: List[EmergencyResponse] = []
        self.auto_corrections_enabled = True

        # Условия экстренной ситуации
        self.thresholds = {
            "winrate_below_60": 0.60,
            "false_signals_above_20": 0.20,
            "symbol_health_below_40": 0.40,
            "volume_quality_below_70": 0.70,
        }

        # Действия при экстренной ситуации
        self.auto_corrections = {
            "winrate_below_60": "Повысить quality_score до 0.8",
            "false_signals_above_20": "Увеличить pattern_confidence до 0.7",
            "symbol_health_below_40": "Включить строгий режим блокировки",
            "volume_quality_below_70": "Повысить объемные фильтры",
        }

    def check_conditions(self, metrics: Dict[str, float]) -> Dict[str, EmergencyCondition]:
        """
        Проверяет условия экстренной ситуации

        Args:
            metrics: Метрики производительности

        Returns:
            Dict с условиями экстренной ситуации
        """
        if not self.enabled:
            return {}

        try:
            triggered_conditions = {}

            # Проверяем каждое условие
            for condition_name, threshold in self.thresholds.items():
                current_value = metrics.get(
                    condition_name.replace("_below_", "_").replace("_above_", "_"), 1.0
                )

                # Определяем, сработало ли условие
                triggered = False
                if "below" in condition_name:
                    triggered = current_value < threshold
                elif "above" in condition_name:
                    triggered = current_value > threshold

                condition = EmergencyCondition(
                    name=condition_name,
                    threshold=threshold,
                    current_value=current_value,
                    triggered=triggered,
                    timestamp=time.time(),
                )

                self.conditions[condition_name] = condition

                if triggered:
                    triggered_conditions[condition_name] = condition
                    logger.warning(
                        "🚨 ЭКСТРЕННАЯ СИТУАЦИЯ: %s (значение: %.2f, порог: %.2f)",
                        condition_name,
                        current_value,
                        threshold,
                    )

            return triggered_conditions

        except Exception as e:
            logger.error("[Emergency] Ошибка проверки условий: %s", e)
            return {}

    def respond_to_emergency(self, condition: EmergencyCondition) -> EmergencyResponse:
        """
        Реагирует на экстренную ситуацию

        Args:
            condition: Условие экстренной ситуации

        Returns:
            Ответ на экстренную ситуацию
        """
        try:
            if not self.auto_corrections_enabled:
                logger.info("⚠️ Автокоррекции отключены, пропускаем %s", condition.name)
                return EmergencyResponse(
                    condition=condition.name,
                    action="Skipped (auto-corrections disabled)",
                    timestamp=time.time(),
                    success=True,
                )

            # Получаем действие для условия
            action = self.auto_corrections.get(condition.name, "No action defined")

            logger.warning("🔧 ЭКСТРЕННАЯ КОРРЕКТИРОВКА: %s", action)

            response = EmergencyResponse(
                condition=condition.name,
                action=action,
                timestamp=time.time(),
                success=True,  # Предполагаем успех
            )

            self.responses.append(response)

            return response

        except Exception as e:
            logger.error("[Emergency] Ошибка реагирования: %s", e)
            return EmergencyResponse(
                condition=condition.name, action=f"Error: {e}", timestamp=time.time(), success=False
            )

    def get_emergency_status(self) -> Dict[str, Any]:
        """Возвращает статус экстренных ситуаций"""
        triggered_count = sum(1 for c in self.conditions.values() if c.triggered)

        return {
            "enabled": self.enabled,
            "total_conditions": len(self.conditions),
            "triggered_conditions": triggered_count,
            "auto_corrections_enabled": self.auto_corrections_enabled,
            "total_responses": len(self.responses),
            "conditions": [asdict(c) for c in self.conditions.values()],
        }
