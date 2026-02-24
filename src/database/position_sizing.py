"""
🤖 ИИ-ОПТИМИЗАТОР РАЗМЕРА ПОЗИЦИИ И ПЛЕЧА
Интеллектуальный расчет суммы входа и плеча на основе рыночных условий
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class AIPositionSizing:
    """ИИ-система для оптимизации размера позиции и плеча"""

    def __init__(self, data_dir: str = "ai_position_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # Загружаем исторические данные эффективности
        self.position_effectiveness = self._load_position_effectiveness()

        # Веса для различных факторов
        self.factor_weights = {
            "volatility": 0.25,  # Волатильность рынка
            "trend_strength": 0.20,  # Сила тренда
            "volume_profile": 0.15,  # Профиль объема
            "market_sentiment": 0.15,  # Рыночный сентимент
            "account_health": 0.25,  # Здоровье аккаунта
        }

        logger.info("🤖 ИИ-оптимизатор размера позиции инициализирован")

    def _load_position_effectiveness(self) -> Dict[str, Any]:
        """Загружает историческую эффективность позиций"""
        file_path = os.path.join(self.data_dir, "position_effectiveness.json")

        if os.path.exists(file_path):
            try:
                with open(file_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Ошибка загрузки эффективности позиций: %s", e)
        return {}

    def _save_position_effectiveness(self):
        """Сохраняет эффективность позиций"""
        file_path = os.path.join(self.data_dir, "position_effectiveness.json")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.position_effectiveness, f, indent=2, ensure_ascii=False)
            logger.debug("💾 Эффективность позиций сохранена")
        except (OSError, TypeError) as e:
            logger.error("Ошибка сохранения эффективности позиций: %s", e)

    def calculate_volatility_factor(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает фактор волатильности для размера позиции"""
        try:
            if current_index < 20:
                return 1.0

            # Анализируем волатильность за последние 20 свечей
            closes = df["close"].iloc[current_index - 20 : current_index]
            volatility = closes.std() / closes.mean()

            # Высокая волатильность = уменьшаем размер позиции
            volatility_factor = np.clip(1.0 - volatility * 2, 0.5, 1.2)

            logger.debug("📊 Фактор волатильности для позиции: %.2f", volatility_factor)
            return volatility_factor

        except (IndexError, KeyError, ValueError, ZeroDivisionError) as e:
            logger.error("Ошибка расчета фактора волатильности: %s", e)
            return 1.0

    def calculate_trend_strength_factor(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает фактор силы тренда для плеча"""
        try:
            if current_index < 50:
                return 1.0

            # Анализируем EMA (используем доступные колонки или рассчитываем на лету)
            ema_fast_col = "ema_fast" if "ema_fast" in df.columns else "ema_7"
            ema_slow_col = "ema_slow" if "ema_slow" in df.columns else "ema_25"

            if ema_fast_col in df.columns and ema_slow_col in df.columns:
                ema_fast = df[ema_fast_col].iloc[current_index]
                ema_slow = df[ema_slow_col].iloc[current_index]
                current_price = df["close"].iloc[current_index]

                # Расстояние между EMA
                ema_distance = abs(ema_fast - ema_slow) / current_price

                # Сильный тренд = можно увеличить плечо
                trend_factor = np.clip(0.8 + ema_distance * 100, 0.8, 1.5)

                logger.debug("📈 Фактор силы тренда для плеча: %.2f", trend_factor)
                return trend_factor
            else:
                return 1.0

        except (IndexError, KeyError, ValueError, ZeroDivisionError) as e:
            logger.error("Ошибка расчета фактора силы тренда: %s", e)
            return 1.0

    def calculate_volume_profile_factor(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает фактор профиля объема"""
        try:
            if current_index < 20:
                return 1.0

            # Анализируем объем за последние 20 свечей
            volumes = df["volume"].iloc[current_index - 20 : current_index]
            current_volume = df["volume"].iloc[current_index]

            avg_volume = volumes.mean()
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Высокий объем = можно увеличить размер позиции
            volume_factor = np.clip(0.8 + volume_ratio * 0.4, 0.8, 1.3)

            logger.debug("📊 Фактор объема для позиции: %.2f", volume_factor)
            return volume_factor

        except (IndexError, KeyError, ValueError, ZeroDivisionError) as e:
            logger.error("Ошибка расчета фактора объема: %s", e)
            return 1.0

    def calculate_market_sentiment_factor(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает фактор рыночного сентимента"""
        try:
            sentiment_factors = []

            # RSI сентимент
            if "rsi" in df.columns:
                rsi = df["rsi"].iloc[current_index]
                if rsi > 70:  # Перекупленность - уменьшаем позицию
                    sentiment_factors.append(0.8)
                elif rsi < 30:  # Перепроданность - можно увеличить
                    sentiment_factors.append(1.2)
                else:
                    sentiment_factors.append(1.0)

            # ADX сентимент
            if "adx" in df.columns:
                adx = df["adx"].iloc[current_index]
                if adx > 30:  # Сильный тренд - можно увеличить плечо
                    sentiment_factors.append(1.1)
                elif adx < 20:  # Слабый тренд - уменьшаем плечо
                    sentiment_factors.append(0.9)
                else:
                    sentiment_factors.append(1.0)

            # Средний сентимент
            if sentiment_factors:
                sentiment_factor = np.mean(sentiment_factors)
            else:
                sentiment_factor = 1.0

            logger.debug("😊 Фактор сентимента: %.2f", sentiment_factor)
            return sentiment_factor

        except (IndexError, KeyError, ValueError) as e:
            logger.error("Ошибка расчета фактора сентимента: %s", e)
            return 1.0

    def calculate_account_health_factor(self, user_data: Dict[str, Any]) -> float:
        """Рассчитывает фактор здоровья аккаунта"""
        try:
            deposit = user_data.get("deposit", 1000)
            total_profit = user_data.get("total_profit", 0)
            open_positions = user_data.get("open_positions", [])

            # Процент прибыли от депозита
            profit_ratio = total_profit / deposit if deposit > 0 else 0

            # Количество открытых позиций
            position_count = len([p for p in open_positions if p.get("status") == "open"])

            # Фактор прибыли (положительная прибыль = увеличиваем позицию)
            profit_factor = np.clip(0.8 + profit_ratio * 2, 0.7, 1.3)

            # Фактор диверсификации (много позиций = уменьшаем размер)
            diversification_factor = np.clip(1.0 - position_count * 0.05, 0.7, 1.0)

            # Итоговый фактор здоровья аккаунта
            health_factor = (profit_factor + diversification_factor) / 2

            logger.debug("💪 Фактор здоровья аккаунта: %.2f", health_factor)
            return health_factor

        except (KeyError, ValueError, ZeroDivisionError, TypeError) as e:
            logger.error("Ошибка расчета фактора здоровья аккаунта: %s", e)
            return 1.0

    def get_symbol_effectiveness(self, symbol: str, side: str) -> Dict[str, float]:
        """Получает историческую эффективность позиций для символа"""
        key = f"{symbol}_{side}"

        if key in self.position_effectiveness:
            return self.position_effectiveness[key]

        # Дефолтные значения для новых символов (БЕЗ ЖЕСТКОЙ ПРИВЯЗКИ К 1.0)
        return {"avg_profit_pct": 0.0, "success_rate": 0.5, "avg_position_size": 0.0}

    def calculate_ai_optimized_position_size(
        self,
        symbol: str,
        side: str,
        df: pd.DataFrame,
        current_index: int,
        user_data: Dict[str, Any],
        base_risk_pct: float = 2.0,
        base_leverage: float = 1.0,
    ) -> Tuple[float, float, float]:
        """
        Рассчитывает ИИ-оптимизированные параметры позиции
        """
        try:
            logger.info(
                "🤖 Рассчитываем ИИ-оптимизированные параметры позиции для %s %s", symbol, side
            )

            # 1. Получаем историческую эффективность символа
            effectiveness = self.get_symbol_effectiveness(symbol, side)

            # 2. Рассчитываем все факторы
            volatility_factor = self.calculate_volatility_factor(df, current_index)
            trend_strength_factor = self.calculate_trend_strength_factor(df, current_index)
            volume_factor = self.calculate_volume_profile_factor(df, current_index)
            sentiment_factor = self.calculate_market_sentiment_factor(df, current_index)
            account_health_factor = self.calculate_account_health_factor(user_data)

            # 3. Комбинированный фактор для риска (нормализованный)
            risk_total_weight = (
                self.factor_weights["volatility"]
                + self.factor_weights["volume_profile"]
                + self.factor_weights["market_sentiment"]
                + self.factor_weights["account_health"]
            )
            risk_combined_factor = (
                (
                    volatility_factor * self.factor_weights["volatility"]
                    + volume_factor * self.factor_weights["volume_profile"]
                    + sentiment_factor * self.factor_weights["market_sentiment"]
                    + account_health_factor * self.factor_weights["account_health"]
                )
                / risk_total_weight
                if risk_total_weight > 0
                else 1.0
            )

            # 4. Комбинированный фактор для плеча (нормализованный)
            leverage_total_weight = (
                self.factor_weights["trend_strength"]
                + self.factor_weights["market_sentiment"]
                + self.factor_weights["account_health"]
            )
            leverage_combined_factor = (
                (
                    trend_strength_factor * self.factor_weights["trend_strength"]
                    + sentiment_factor * self.factor_weights["market_sentiment"]
                    + account_health_factor * self.factor_weights["account_health"]
                )
                / leverage_total_weight
                if leverage_total_weight > 0
                else 1.0
            )

            # 5. Учитываем историческую эффективность (если есть)
            historical_risk = effectiveness.get("optimal_risk_pct", base_risk_pct)
            historical_leverage = effectiveness.get("optimal_leverage", base_leverage)

            # 6. Финальный расчет
            # Если данных мало, больше веса даем текущим факторам
            ai_risk_pct = historical_risk * 0.5 + base_risk_pct * risk_combined_factor * 0.5
            ai_leverage = historical_leverage * 0.5 + base_leverage * leverage_combined_factor * 0.5

            # 7. Ограничиваем разумными пределами
            ai_risk_pct = np.clip(ai_risk_pct, 0.5, 8.0)
            ai_leverage = np.clip(ai_leverage, 1.0, 20.0)

            # 8. Рассчитываем сумму входа (НОМИНАЛ)
            deposit = user_data.get("deposit", 1000)
            free_deposit = user_data.get("free_deposit", deposit)
            trade_mode = user_data.get("trade_mode", "spot")

            # ВАЖНО: Возвращаем динамическое плечо (float)
            if trade_mode == "futures":
                entry_amount = free_deposit * (ai_risk_pct / 100.0) * ai_leverage
            else:
                entry_amount = free_deposit * (ai_risk_pct / 100.0)
                ai_leverage = 1.0

            return float(ai_risk_pct), float(ai_leverage), float(entry_amount)

        except Exception as e:
            logger.error("Ошибка ИИ-оптимизации размера позиции: %s", e)
            return (
                base_risk_pct,
                base_leverage,
                user_data.get("deposit", 1000) * (base_risk_pct / 100.0),
            )
