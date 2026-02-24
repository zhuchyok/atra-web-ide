"""
🤖 ИИ-ОПТИМИЗАТОР РАЗМЕРА ПОЗИЦИИ И ПЛЕЧА
Интеллектуальный расчет суммы входа и плеча на основе рыночных условий
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class AIPositionSizing:
    """ИИ-система для оптимизации размера позиции и плеча"""

    def __init__(self, data_dir: str = "ai_position_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.position_effectiveness = self._load_position_effectiveness()

    def _load_position_effectiveness(self) -> Dict[str, Any]:
        file_path = os.path.join(self.data_dir, "position_effectiveness.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def calculate_volatility_factor(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает фактор волатильности (0.5 - 1.5)"""
        try:
            if current_index < 20:
                return 1.0
            closes = df["close"].iloc[current_index - 20 : current_index]
            volatility = closes.std() / closes.mean()
            # Повышаем чувствительность: 0.002 (низкая) -> 1.4, 0.01 (высокая) -> 0.6
            factor = np.clip(1.4 - (volatility * 80), 0.5, 1.6)
            return float(factor)
        except Exception:
            return 1.0

    def calculate_trend_strength_factor(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает силу тренда для плеча"""
        try:
            if current_index < 50:
                return 1.0
            ema_fast = (
                df["ema_fast"].iloc[current_index]
                if "ema_fast" in df.columns
                else df["close"].ewm(span=7).mean().iloc[current_index]
            )
            ema_slow = (
                df["ema_slow"].iloc[current_index]
                if "ema_slow" in df.columns
                else df["close"].ewm(span=25).mean().iloc[current_index]
            )
            dist = abs(ema_fast - ema_slow) / df["close"].iloc[current_index]
            # Повышаем чувствительность к тренду
            return float(np.clip(0.7 + dist * 200, 0.7, 1.5))
        except Exception:
            return 1.0

    def calculate_ai_optimized_position_size(
        self,
        symbol: str,
        side: str,
        df: pd.DataFrame,
        current_index: int,
        user_data: Dict[str, Any],
        base_risk_pct: float = 2.0,
        base_leverage: float = 4.0,
    ) -> Tuple[float, float, float]:
        """
        ФИНАЛЬНЫЙ РАСЧЕТ:
        - риск от TOTAL DEPOSIT
        - плечо динамическое (float)
        """
        try:
            vol_f = self.calculate_volatility_factor(df, current_index)
            trend_f = self.calculate_trend_strength_factor(df, current_index)

            # Повышаем 'живость' плеча (более агрессивный множитель)
            ai_leverage = base_leverage * (vol_f * 0.5 + trend_f * 0.5)
            ai_leverage = np.clip(ai_leverage, 1.0, 20.0)

            # Риск
            ai_risk_pct = base_risk_pct

            # Берем общий баланс
            total_deposit = user_data.get("deposit", 1000.0)
            margin_usdt = total_deposit * (ai_risk_pct / 100.0)

            logger.info(
                "🤖 [%s] ИИ-Расчет: риск=%.2f%%, плечо=%.2fx, маржа=%.2f USDT",
                symbol,
                ai_risk_pct,
                ai_leverage,
                margin_usdt,
            )

            return float(ai_risk_pct), float(ai_leverage), float(margin_usdt)

        except Exception as e:
            logger.error("Ошибка ИИ-оптимизации: %s", e)
            margin = user_data.get("deposit", 1000.0) * (base_risk_pct / 100.0)
            return base_risk_pct, base_leverage, margin
