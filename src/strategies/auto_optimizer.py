#!/usr/bin/env python3

import asyncio
import json
import logging
from datetime import datetime

import pandas as pd
import ta

from src.execution.exchange_api import get_ohlc_with_fallback
from src.shared.utils.datetime_utils import get_utc_now
from src.signals.core import soft_entry_signal, strict_entry_signal

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoOptimizer:
    """Автоматическая оптимизация параметров фильтров (🚀 STATELESS & DB-DRIVEN)"""

    def __init__(self):
        from src.database.db import DatabaseSingleton

        self.db = DatabaseSingleton()
        self.default_params = {
            "strict": {
                "bb_touch": 1.01,
                "ema_trend": 1.001,
                "rsi_long": 40,
                "rsi_short": 60,
                "volume_ratio": 1.2,
                "volatility": 2.0,
                "momentum": 0.0,
                "trend_strength": 0.5,
            },
            "soft": {
                "bb_touch": 1.05,
                "ema_trend": 0.998,
                "rsi_long": 55,
                "rsi_short": 45,
                "volume_ratio": 0.5,
                "volatility": 0.5,
                "momentum": -0.1,
                "trend_strength": 0.05,
            },
        }

    def get_current_params(self, symbol="GLOBAL"):
        """Получаем текущие параметры из БД или дефолтные (Stateless)"""
        cache_key = f"optimizer_params:{symbol}"
        params = self.db.cache_get("settings", cache_key)
        return params if params else self.default_params

    def save_params(self, params, symbol="GLOBAL"):
        """Сохраняем параметры в БД (Stateless)"""
        cache_key = f"optimizer_params:{symbol}"
        # Сохраняем без TTL (навсегда, до следующей оптимизации)
        self.db.cache_set("settings", cache_key, params, ttl_seconds=None)
        logger.info("✅ Параметры для %s сохранены в БД", symbol)

    def load_optimization_history(self, symbol="GLOBAL"):
        """Загружаем историю из БД"""
        cache_key = f"optimization_history:{symbol}"
        return self.db.cache_get("history", cache_key) or {}

    def save_optimization_history(self, history, symbol="GLOBAL"):
        """Сохраняем историю в БД"""
        cache_key = f"optimization_history:{symbol}"
        self.db.cache_set("history", cache_key, history, ttl_seconds=None)

    async def analyze_market_conditions(self, symbol="BTCUSDT"):
        """Анализируем текущие рыночные условия с кэшированием"""
        try:
            # Пытаемся получить данные из кэша через DatabaseSingleton (app_cache)
            from src.database.db import DatabaseSingleton

            db = DatabaseSingleton()
            cache_type = "market_analysis"
            cache_key = symbol
            cached_data = db.cache_get(cache_type, cache_key)
            if cached_data:
                logger.info("🚀 [OPTIMIZER] Используем кэшированные условия рынка для %s", symbol)
                return cached_data

            # Получаем данные за последние 7 дней
            ohlc_data = await get_ohlc_with_fallback(symbol, "1h", 168)
            if not ohlc_data:
                return None

            df = pd.DataFrame(ohlc_data)
            df["open_time"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("open_time")
            df = df[["close", "volume"]].copy()
            if "high" not in df.columns:
                # Нам нужны high/low для некоторых индикаторов
                temp_df = pd.DataFrame(ohlc_data)
                df["high"] = temp_df["high"].values
                df["low"] = temp_df["low"].values

            # Использование централизованного модуля индикаторов
            from src.signals.indicators import add_technical_indicators

            df = add_technical_indicators(df)

            # Анализируем условия
            analysis = {
                "avg_volatility": float(df["volatility"].mean()),
                "avg_trend_strength": float(df["trend_strength"].mean()),
                "avg_momentum": float(df["momentum"].mean()),
                "price_range": float(
                    (df["close"].max() - df["close"].min()) / df["close"].mean() * 100
                ),
                "signal_count": 0,
                "timestamp": get_utc_now().isoformat(),
            }

            # Подсчитываем количество сигналов (оптимизированный цикл)
            # Мы начинаем с 25, чтобы индикаторы успели прогреться
            for i in range(25, len(df)):
                # Используем упрощенную логику или основные функции
                strict_signal, _ = strict_entry_signal(df, i)
                if not strict_signal:
                    soft_signal, _ = soft_entry_signal(df, i)
                    if soft_signal:
                        analysis["signal_count"] += 1
                else:
                    analysis["signal_count"] += 1

            # Сохраняем в кэш на 30 минут
            db.cache_set(cache_type, cache_key, analysis, ttl_seconds=1800)
            return analysis

        except Exception as e:
            logger.error("❌ Ошибка анализа рыночных условий: %s", e)
            return None

    def optimize_parameters(self, market_analysis, symbol="GLOBAL"):
        """Оптимизируем параметры на основе анализа рынка (Stateless)"""
        if not market_analysis:
            return self.get_current_params(symbol)

        current_params = self.get_current_params(symbol)

        # ... (логика расчета new_params остается прежней, но использует current_params)
        volatility = market_analysis["avg_volatility"]
        trend_strength = market_analysis["avg_trend_strength"]
        signal_count = market_analysis["signal_count"]

        if volatility > 3.0:
            market_type = "high_volatility"
        elif volatility < 1.0:
            market_type = "low_volatility"
        else:
            market_type = "normal"

        if trend_strength > 2.0:
            trend_type = "strong_trend"
        elif trend_strength < 0.5:
            trend_type = "weak_trend"
        else:
            trend_type = "normal_trend"

        new_params = current_params.copy()

        # Адаптация к волатильности
        if market_type == "high_volatility":
            new_params["strict"]["volatility"] = max(
                1.0, current_params["strict"]["volatility"] * 0.8
            )
            new_params["strict"]["trend_strength"] = min(
                1.0, current_params["strict"]["trend_strength"] * 1.2
            )
        elif market_type == "low_volatility":
            new_params["strict"]["volatility"] = min(
                3.0, current_params["strict"]["volatility"] * 1.2
            )
            new_params["strict"]["trend_strength"] = max(
                0.3, current_params["strict"]["trend_strength"] * 0.8
            )

        # ... (прочая логика адаптации) ...
        if signal_count < 5:
            new_params["strict"]["rsi_long"] = min(45, current_params["strict"]["rsi_long"] + 2)
            new_params["strict"]["rsi_short"] = max(55, current_params["strict"]["rsi_short"] - 2)
        elif signal_count > 50:
            new_params["strict"]["rsi_long"] = max(35, current_params["strict"]["rsi_long"] - 2)
            new_params["strict"]["rsi_short"] = min(65, current_params["strict"]["rsi_short"] + 2)

        return new_params

    def apply_optimized_parameters(self, new_params, symbol="GLOBAL"):
        """Применяем оптимизированные параметры через БД (🚀 STATELESS)"""
        try:
            self.save_params(new_params, symbol)
            logger.info("✅ Параметры фильтров для %s обновлены в БД", symbol)
            return True
        except Exception as e:
            logger.error("❌ Ошибка применения параметров: %s", e)
            return False

    async def run_daily_optimization(self, symbol="BTCUSDT"):
        """Запускаем ежедневную оптимизацию (Stateless)"""
        logger.info("🚀 Запуск оптимизации для %s...", symbol)

        try:
            market_analysis = await self.analyze_market_conditions(symbol)
            if market_analysis:
                new_params = self.optimize_parameters(market_analysis, symbol)

                # Сохраняем историю в БД
                history = self.load_optimization_history(symbol)
                timestamp = get_utc_now().isoformat()
                history[timestamp] = {"market_analysis": market_analysis, "new_params": new_params}
                self.save_optimization_history(history, symbol)

                # Применяем новые параметры (в БД)
                return self.apply_optimized_parameters(new_params, symbol)
            return False
        except Exception as e:
            logger.error("❌ Ошибка оптимизации: %s", e)
            return False


async def run_optimization_loop():
    """Функция для запуска цикла оптимизации (для совместимости с main.py)"""
    optimizer = AutoOptimizer()

    while True:
        try:
            logger.info("🔄 Запуск цикла оптимизации...")
            success = await optimizer.run_daily_optimization()

            if success:
                logger.info("✅ Оптимизация завершена успешно")
            else:
                logger.warning("⚠️ Оптимизация завершена с предупреждениями")

            # Ждем 24 часа до следующей оптимизации
            logger.info("⏳ Ожидание 24 часа до следующей оптимизации...")
            await asyncio.sleep(24 * 60 * 60)  # 24 часа

        except (ValueError, KeyError, TypeError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка в цикле оптимизации: %s", e)
            await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой


async def main():
    """Основная функция"""
    optimizer = AutoOptimizer()

    # Запускаем оптимизацию
    success = await optimizer.run_daily_optimization()

    if success:
        print("🎉 Оптимизация завершена успешно!")
    else:
        print("❌ Ошибка оптимизации")


if __name__ == "__main__":
    asyncio.run(main())
