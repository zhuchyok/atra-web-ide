#!/usr/bin/env python3
"""Генерация качественных паттернов для обучения ML через глубокий бэктест."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict

import pandas as pd

# Добавляем корневую директорию в путь
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.historical_data_loader import HistoricalDataLoader
from scripts.run_advanced_backtest import AdvancedBacktest
from src.ai.learning import AILearningSystem, TradingPattern

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PatternGeneratorBacktest(AdvancedBacktest):
    """Расширенный бектест для генерации обучающих данных."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai_learning = AILearningSystem()
        logger.info(
            "🤖 PatternGeneratorBacktest инициализирован. Текущих паттернов: %d",
            len(self.ai_learning.patterns),
        )

    def close_position(
        self, position: Dict[str, Any], exit_price: float, exit_reason: str, timestamp: pd.Timestamp
    ) -> None:
        """Закрывает позицию и сохраняет её как паттерн для обучения."""
        # Вызываем базовый метод для статистики
        super().close_position(position, exit_price, exit_reason, timestamp)

        # Находим последний закрытый трейд (это тот, который мы только что добавили в self.trades)
        if not self.trades:
            return

        trade = self.trades[-1]

        # Создаем паттерн для обучения
        try:
            # Нам нужны индикаторы на момент ВХОДА в сделку
            # Мы сохранили rsi, macd, volume_ratio в объекте position при открытии

            # Определяем результат (WIN/LOSS/NEUTRAL)
            if trade["pnl_percent"] > 0.5:  # Минимум 0.5% прибыли для WIN
                result = "WIN"
            elif trade["pnl_percent"] < -0.5:  # Минимум 0.5% убытка для LOSS
                result = "LOSS"
            else:
                result = "NEUTRAL"

            # Собираем индикаторы
            bb_upper = position.get("bb_upper", 1)
            bb_lower = position.get("bb_lower", 0)
            bb_pos = (
                (position.get("entry_price", 0) - bb_lower) / (bb_upper - bb_lower)
                if "bb_upper" in position
                else 0.5
            )

            indicators = {
                "rsi": position.get("rsi", 50.0),
                "macd": position.get("macd", 0.0),
                "volume_ratio": position.get("volume_ratio", 1.0),
                "volatility": position.get("volatility", 0.0),
                "trend_strength": position.get("trend_strength", 0.0),
                "bb_position": bb_pos,
            }

            # Добавляем в систему обучения
            entry_time = trade["entry_time"]
            if hasattr(entry_time, "to_pydatetime"):
                pattern_timestamp = entry_time.to_pydatetime()
            else:
                pattern_timestamp = entry_time

            pattern = TradingPattern(
                symbol=trade["symbol"],
                timestamp=pattern_timestamp,
                signal_type=trade["direction"],
                entry_price=trade["entry_price"],
                tp1=position.get("tp1_price", trade["entry_price"] * 1.02),
                tp2=position.get("tp2_price", trade["entry_price"] * 1.04),
                risk_pct=self.risk_per_trade,
                leverage=position.get("leverage_used", self.leverage),
                indicators=indicators,
                market_conditions={
                    "btc_trend": position.get("btc_trend"),
                    "exit_reason": exit_reason,
                },
                result=result,
                profit_pct=trade["pnl_percent"],
            )

            self.ai_learning.add_pattern(pattern)
            logger.debug(
                "📥 Паттерн добавлен: %s %s (PnL: %.2f%%)",
                trade["symbol"],
                result,
                trade["pnl_percent"],
            )

        except Exception as e:
            logger.error("⚠️ Ошибка при создании паттерна: %s", e)


async def main():
    """Основная функция запуска генерации паттернов."""
    parser = argparse_setup()
    args = parser.parse_args()

    # 1. Загрузка данных
    async with HistoricalDataLoader(exchange="binance") as loader:
        if args.symbols:
            symbols = args.symbols
        else:
            logger.info("📊 Получение топ %d монет...", args.top_n)
            symbols = await loader.get_top_symbols(limit=args.top_n)

        logger.info("📈 Символы для генерации: %s", ", ".join(symbols))

        # Загружаем BTC для проверки тренда
        logger.info("📥 Загрузка данных BTC за %d дней...", args.days)
        btc_df = await loader.fetch_ohlcv("BTCUSDT", interval="1h", days=args.days)

        # Загружаем данные для всех символов
        logger.info("📥 Загрузка исторических данных...")
        data_dict = await loader.load_multiple_symbols(symbols, interval="1h", days=args.days)

    # 2. Запуск бектеста-генератора
    backtest = PatternGeneratorBacktest(initial_balance=10000.0, risk_per_trade=2.0, leverage=2.0)

    for symbol in symbols:
        if symbol not in data_dict or data_dict[symbol].empty:
            continue
        await backtest.run_backtest(symbol, data_dict[symbol], btc_df, days=args.days)

    # 3. Сохранение паттернов
    logger.info("💾 Сохранение накопленных паттернов...")
    backtest.ai_learning.save_patterns()

    # 4. Вывод статистики
    metrics = backtest.calculate_metrics()
    logger.info("✅ Генерация завершена!")
    logger.info("📊 Всего сделок: %d", metrics.get("total_trades", 0))
    logger.info("📊 Всего паттернов в системе теперь: %d", len(backtest.ai_learning.patterns))


def argparse_setup():
    """Настройка аргументов командной строки."""
    parser = argparse.ArgumentParser(description="Генерация паттернов через бэктест")
    parser.add_argument("--symbols", nargs="+", help="Список символов")
    parser.add_argument("--top-n", type=int, default=50, help="Количество топ монет")
    parser.add_argument("--days", type=int, default=90, help="Количество дней")
    return parser


if __name__ == "__main__":
    asyncio.run(main())
