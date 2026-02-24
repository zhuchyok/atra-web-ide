#!/usr/bin/env python3
"""Оптимизация параметров и тестирование гипотез для улучшения бектеста."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.historical_data_loader import HistoricalDataLoader
from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class HypothesisTester:
    """Тестирует гипотезы для улучшения бектеста."""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def analyze_patterns_for_tp_sl(self, symbol: str, ai_learning) -> Dict[str, Any]:
        """Анализирует паттерны для определения оптимальных TP/SL."""
        if not ai_learning or not ai_learning.patterns:
            return {}

        try:
            symbol_patterns = [
                p for p in ai_learning.patterns if hasattr(p, "symbol") and p.symbol == symbol
            ]

            if not symbol_patterns:
                return {}

            # Анализ успешных паттернов
            successful = [p for p in symbol_patterns if p.result == "WIN" and p.profit_pct]
            failed = [p for p in symbol_patterns if p.result == "LOSS" and p.profit_pct]

            if not successful:
                return {}

            # Оптимальные TP на основе успешных паттернов
            profits = [p.profit_pct for p in successful]
            tp1_profits = [p for p in profits if p <= 3.0]
            tp2_profits = [p for p in profits if p > 3.0]

            optimal_tp1 = np.percentile(tp1_profits, 75) if tp1_profits else 2.0
            optimal_tp2 = np.percentile(tp2_profits, 75) if tp2_profits else 4.0

            # Оптимальный SL на основе неудачных паттернов
            if failed:
                losses = [abs(p.profit_pct) for p in failed]
                optimal_sl = np.percentile(losses, 50)  # Медиана убытков
                optimal_sl = min(optimal_sl, 2.0)  # Максимум 2%
            else:
                optimal_sl = 2.0

            # Win rate для разных направлений
            long_patterns = [
                p for p in symbol_patterns if hasattr(p, "signal_type") and p.signal_type == "LONG"
            ]
            short_patterns = [
                p for p in symbol_patterns if hasattr(p, "signal_type") and p.signal_type == "SHORT"
            ]

            long_win_rate = (
                len([p for p in long_patterns if p.result == "WIN"]) / len(long_patterns) * 100
                if long_patterns
                else 0
            )
            short_win_rate = (
                len([p for p in short_patterns if p.result == "WIN"]) / len(short_patterns) * 100
                if short_patterns
                else 0
            )

            return {
                "optimal_tp1": float(optimal_tp1),
                "optimal_tp2": float(optimal_tp2),
                "optimal_sl": float(optimal_sl),
                "long_win_rate": float(long_win_rate),
                "short_win_rate": float(short_win_rate),
                "total_patterns": len(symbol_patterns),
                "successful_patterns": len(successful),
                "failed_patterns": len(failed),
            }
        except Exception as e:
            logger.debug("Ошибка анализа паттернов для %s: %s", symbol, e)
            return {}

    def analyze_volume_impact(self, trades_df: pd.DataFrame) -> Dict[str, Any]:
        """Анализирует влияние объёма на результаты."""
        if trades_df.empty or "volume_ratio" not in trades_df.columns:
            return {}

        # Группируем по диапазонам объёма
        trades_df["volume_category"] = pd.cut(
            trades_df["volume_ratio"],
            bins=[0, 0.8, 1.2, 1.5, float("inf")],
            labels=["low", "normal", "high", "very_high"],
        )

        volume_stats = trades_df.groupby("volume_category").agg(
            {
                "pnl": ["count", "sum", "mean"],
                "pnl_percent": "mean",
            }
        )

        # Win rate по категориям
        win_rates = {}
        for category in ["low", "normal", "high", "very_high"]:
            category_trades = trades_df[trades_df["volume_category"] == category]
            if len(category_trades) > 0:
                win_rates[category] = (
                    (category_trades["pnl"] > 0).sum() / len(category_trades) * 100
                )

        return {
            "win_rates": win_rates,
            "stats": volume_stats.to_dict(),
        }

    def analyze_rsi_impact(self, trades_df: pd.DataFrame) -> Dict[str, Any]:
        """Анализирует влияние RSI на результаты."""
        if trades_df.empty or "rsi" not in trades_df.columns:
            return {}

        # Группируем по диапазонам RSI
        winning = trades_df[trades_df["pnl"] > 0]
        losing = trades_df[trades_df["pnl"] < 0]

        # Оптимальные пороги
        if len(winning) > 0 and len(losing) > 0:
            # Находим порог, где win rate максимален
            best_long_rsi = None
            best_short_rsi = None
            best_long_win_rate = 0
            best_short_win_rate = 0

            for rsi_threshold in range(20, 80, 5):
                # LONG сигналы
                long_trades = trades_df[
                    (trades_df["direction"] == "LONG") & (trades_df["rsi"] < rsi_threshold)
                ]
                if len(long_trades) > 0:
                    long_wr = (long_trades["pnl"] > 0).sum() / len(long_trades) * 100
                    if long_wr > best_long_win_rate:
                        best_long_win_rate = long_wr
                        best_long_rsi = rsi_threshold

                # SHORT сигналы
                short_trades = trades_df[
                    (trades_df["direction"] == "SHORT") & (trades_df["rsi"] > rsi_threshold)
                ]
                if len(short_trades) > 0:
                    short_wr = (short_trades["pnl"] > 0).sum() / len(short_trades) * 100
                    if short_wr > best_short_win_rate:
                        best_short_win_rate = short_wr
                        best_short_rsi = rsi_threshold

            return {
                "best_long_rsi": best_long_rsi,
                "best_short_rsi": best_short_rsi,
                "best_long_win_rate": best_long_win_rate,
                "best_short_win_rate": best_short_win_rate,
                "avg_rsi_winning": float(winning["rsi"].mean()) if len(winning) > 0 else None,
                "avg_rsi_losing": float(losing["rsi"].mean()) if len(losing) > 0 else None,
            }

        return {}


class OptimizedBacktest(AdvancedBacktest):
    """Оптимизированная версия бектеста с улучшениями."""

    def __init__(
        self,
        initial_balance: float = 10000.0,
        risk_per_trade: float = 2.0,
        leverage: float = 2.0,
        optimizations: Dict[str, Any] = None,
    ):
        super().__init__(initial_balance, risk_per_trade, leverage)
        self.optimizations = optimizations or {}
        self.pattern_analysis_cache = {}

    def get_optimal_tp_sl(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        df: pd.DataFrame,
        current_index: int,
        symbol_params: Dict[str, Any],
    ) -> Tuple[float, float, float]:
        """Получает оптимальные TP/SL с улучшенной логикой."""
        # Анализируем паттерны для символа
        if symbol not in self.pattern_analysis_cache and self.ai_learning:
            tester = HypothesisTester()
            analysis = tester.analyze_patterns_for_tp_sl(symbol, self.ai_learning)
            self.pattern_analysis_cache[symbol] = analysis

        pattern_analysis = self.pattern_analysis_cache.get(symbol, {})

        # Используем оптимальные значения из паттернов если доступны
        if pattern_analysis:
            base_tp1_pct = pattern_analysis.get(
                "optimal_tp1", symbol_params.get("optimal_tp1", 2.0)
            )
            base_tp2_pct = pattern_analysis.get(
                "optimal_tp2", symbol_params.get("optimal_tp2", 4.0)
            )
            base_sl_pct = pattern_analysis.get(
                "optimal_sl", symbol_params.get("optimal_stop_loss_pct", 2.0)
            )
        else:
            base_tp1_pct = symbol_params.get("optimal_tp1", 2.0)
            base_tp2_pct = symbol_params.get("optimal_tp2", 4.0)
            base_sl_pct = symbol_params.get("optimal_stop_loss_pct", 2.0)

        # Применяем оптимизации
        if self.optimizations.get("improve_tp_sl_ratio"):
            # Улучшаем соотношение TP/SL (увеличиваем TP, уменьшаем SL)
            base_tp1_pct *= 1.2
            base_tp2_pct *= 1.2
            base_sl_pct *= 0.8

        # Используем AI TP Optimizer если доступен
        if self.tp_optimizer and df is not None and current_index is not None:
            try:
                tp1_pct, tp2_pct = self.tp_optimizer.calculate_ai_optimized_tp(
                    symbol=symbol,
                    side=direction,
                    df=df,
                    current_index=current_index,
                    base_tp1=base_tp1_pct,
                    base_tp2=base_tp2_pct,
                )
            except Exception:
                tp1_pct, tp2_pct = base_tp1_pct, base_tp2_pct
        else:
            tp1_pct, tp2_pct = base_tp1_pct, base_tp2_pct

        # Рассчитываем цены
        if direction == "LONG":
            tp1_price = entry_price * (1 + tp1_pct / 100)
            tp2_price = entry_price * (1 + tp2_pct / 100)
            sl_price = entry_price * (1 - base_sl_pct / 100)
        else:  # SHORT
            tp1_price = entry_price * (1 - tp1_pct / 100)
            tp2_price = entry_price * (1 - tp2_pct / 100)
            sl_price = entry_price * (1 + base_sl_pct / 100)

        return tp1_price, tp2_price, sl_price

    def generate_signal(
        self,
        row: pd.Series,
        btc_df: pd.DataFrame,
        symbol: str,
        df: pd.DataFrame,
        current_index: int,
    ) -> Optional[Dict[str, Any]]:
        """Генерирует сигнал с оптимизированными фильтрами."""
        symbol_params = self.get_symbol_params(symbol)

        # Оптимизированные пороги
        rsi_oversold = (
            self.optimizations.get("rsi_oversold", symbol_params.get("optimal_rsi_oversold", 30))
            if self.optimizations.get("optimize_rsi")
            else symbol_params.get("optimal_rsi_oversold", 30)
        )
        rsi_overbought = (
            self.optimizations.get(
                "rsi_overbought", symbol_params.get("optimal_rsi_overbought", 70)
            )
            if self.optimizations.get("optimize_rsi")
            else symbol_params.get("optimal_rsi_overbought", 70)
        )

        min_volume_ratio = (
            self.optimizations.get("min_volume_ratio", symbol_params.get("soft_volume_ratio", 1.2))
            if self.optimizations.get("optimize_volume")
            else symbol_params.get("soft_volume_ratio", 1.2)
        )
        max_volume_ratio = (
            self.optimizations.get("max_volume_ratio", 1.5)
            if self.optimizations.get("optimize_volume")
            else float("inf")
        )

        min_confidence = symbol_params.get("min_confidence", 60)

        # Проверка на NaN
        if pd.isna(row.get("rsi")) or pd.isna(row.get("macd")):
            return None

        direction = None
        confidence = 0.0
        filters_passed = []

        # 1. RSI фильтр (с оптимизированными порогами)
        rsi = row["rsi"]
        if rsi < rsi_oversold:
            direction = "LONG"
            confidence += 20
            filters_passed.append("rsi_oversold")
        elif rsi > rsi_overbought:
            direction = "SHORT"
            confidence += 20
            filters_passed.append("rsi_overbought")
        else:
            return None

        # 2. MACD фильтр
        macd = row["macd"]
        macd_signal = row["macd_signal"]
        macd_hist = row["macd_hist"]

        if direction == "LONG":
            if macd > macd_signal and macd_hist > 0:
                confidence += 20
                filters_passed.append("macd_bullish")
            else:
                return None
        else:  # SHORT
            if macd < macd_signal and macd_hist < 0:
                confidence += 20
                filters_passed.append("macd_bearish")
            else:
                return None

        # 3. Volume фильтр (с оптимизацией)
        volume_ratio = row.get("volume_ratio", 1.0)
        if volume_ratio < min_volume_ratio:
            return None
        if volume_ratio > max_volume_ratio:
            # Блокируем при слишком высоком объёме
            return None

        if volume_ratio > min_volume_ratio:
            confidence += 15
            filters_passed.append("high_volume")
        else:
            confidence += 10

        # 4. BTC тренд фильтр
        btc_trend = self.check_btc_trend(btc_df, row.name)
        if btc_trend is not None:
            if (direction == "LONG" and btc_trend) or (direction == "SHORT" and not btc_trend):
                confidence += 15
                filters_passed.append("btc_aligned")
            else:
                return None

        # 5. EMA фильтр
        ema_fast = row.get("ema_fast", row["close"])
        ema_slow = row.get("ema_slow", row["close"])

        if direction == "LONG":
            if ema_fast > ema_slow:
                confidence += 15
                filters_passed.append("ema_bullish")
            else:
                confidence += 5
        else:  # SHORT
            if ema_fast < ema_slow:
                confidence += 15
                filters_passed.append("ema_bearish")
            else:
                confidence += 5

        # 6. Bollinger Bands
        bb_position = (row["close"] - row["bb_lower"]) / (row["bb_upper"] - row["bb_lower"])
        if direction == "LONG" and bb_position < 0.2:
            confidence += 10
            filters_passed.append("bb_oversold")
        elif direction == "SHORT" and bb_position > 0.8:
            confidence += 10
            filters_passed.append("bb_overbought")

        # Минимальная уверенность
        if confidence < min_confidence:
            return None

        # Получаем оптимальные TP/SL
        entry_price = row["close"]
        tp1_price, tp2_price, sl_price = self.get_optimal_tp_sl(
            symbol, direction, entry_price, df, current_index, symbol_params
        )

        return {
            "symbol": symbol,
            "direction": direction,
            "entry_price": float(entry_price),
            "sl_price": float(sl_price),
            "tp1_price": float(tp1_price),
            "tp2_price": float(tp2_price),
            "confidence": confidence,
            "filters_passed": filters_passed,
            "timestamp": row.name,
            "rsi": float(rsi),
            "macd": float(macd),
            "volume_ratio": float(volume_ratio),
            "btc_trend": btc_trend,
            "symbol_params_used": bool(symbol_params),
            "patterns_analyzed": len(
                [
                    p
                    for p in (self.ai_learning.patterns if self.ai_learning else [])
                    if hasattr(p, "symbol") and p.symbol == symbol
                ]
            )
            if self.ai_learning
            else 0,
        }


async def test_hypothesis(
    hypothesis_name: str,
    optimizations: Dict[str, Any],
    symbols: List[str],
    data_dict: Dict[str, pd.DataFrame],
    btc_df: pd.DataFrame,
    initial_balance: float = 10000.0,
) -> Dict[str, Any]:
    """Тестирует гипотезу с оптимизациями."""
    logger.info("🧪 Тестирование гипотезы: %s", hypothesis_name)

    backtest = OptimizedBacktest(
        initial_balance=initial_balance,
        risk_per_trade=2.0,
        leverage=2.0,
        optimizations=optimizations,
    )

    results = []
    for symbol in symbols:
        if symbol not in data_dict or data_dict[symbol].empty:
            continue
        result = backtest.run_backtest(symbol, data_dict[symbol], btc_df)
        results.append(result)

    metrics = backtest.calculate_metrics()

    return {
        "hypothesis": hypothesis_name,
        "optimizations": optimizations,
        "metrics": metrics,
        "trades": backtest.trades,
    }


async def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description="Оптимизация и тестирование гипотез")
    parser.add_argument("--top-n", type=int, default=10, help="Количество топ монет")
    parser.add_argument("--days", type=int, default=30, help="Количество дней для анализа")
    parser.add_argument(
        "--output", default="data/optimization_results.json", help="Путь для сохранения результатов"
    )
    args = parser.parse_args()

    logger.info("🚀 Запуск оптимизации и тестирования гипотез...")

    # 1. Загрузка данных
    async with HistoricalDataLoader(exchange="binance") as loader:
        logger.info("📊 Получение топ %d монет...", args.top_n)
        symbols = await loader.get_top_symbols(limit=args.top_n)

        logger.info("📥 Загрузка данных BTC...")
        btc_df = await loader.fetch_ohlcv("BTCUSDT", interval="1h", days=args.days)

        logger.info("📥 Загрузка исторических данных...")
        data_dict = await loader.load_multiple_symbols(symbols, interval="1h", days=args.days)

    # 2. Анализ текущих результатов
    logger.info("📊 Анализ текущих результатов...")
    base_backtest = AdvancedBacktest(initial_balance=10000.0, risk_per_trade=2.0, leverage=2.0)

    for symbol in symbols:
        if symbol not in data_dict or data_dict[symbol].empty:
            continue
        base_backtest.run_backtest(symbol, data_dict[symbol], btc_df)

    base_metrics = base_backtest.calculate_metrics()
    base_trades_df = pd.DataFrame(base_backtest.trades)

    # 3. Анализ паттернов и проблем
    tester = HypothesisTester()
    volume_analysis = tester.analyze_volume_impact(base_trades_df)
    rsi_analysis = tester.analyze_rsi_impact(base_trades_df)

    logger.info("📊 Анализ завершён:")
    logger.info("   Volume analysis: %s", volume_analysis)
    logger.info("   RSI analysis: %s", rsi_analysis)

    # 4. Определение гипотез для тестирования
    hypotheses = []

    # Гипотеза 1: Улучшение TP/SL соотношения
    hypotheses.append(
        {
            "name": "Улучшение TP/SL соотношения",
            "optimizations": {
                "improve_tp_sl_ratio": True,
            },
        }
    )

    # Гипотеза 2: Оптимизация RSI порогов
    if rsi_analysis.get("best_long_rsi") and rsi_analysis.get("best_short_rsi"):
        hypotheses.append(
            {
                "name": "Оптимизация RSI порогов",
                "optimizations": {
                    "optimize_rsi": True,
                    "rsi_oversold": rsi_analysis["best_long_rsi"],
                    "rsi_overbought": rsi_analysis["best_short_rsi"],
                },
            }
        )

    # Гипотеза 3: Оптимизация фильтра объёма
    if volume_analysis.get("win_rates"):
        hypotheses.append(
            {
                "name": "Оптимизация фильтра объёма",
                "optimizations": {
                    "optimize_volume": True,
                    "min_volume_ratio": 1.0,
                    "max_volume_ratio": 1.5,  # Блокируем при volume_ratio > 1.5
                },
            }
        )

    # Гипотеза 4: Комбинированная оптимизация
    combined_optimizations = {}
    if rsi_analysis.get("best_long_rsi"):
        combined_optimizations.update(
            {
                "optimize_rsi": True,
                "rsi_oversold": rsi_analysis["best_long_rsi"],
                "rsi_overbought": rsi_analysis.get("best_short_rsi", 75),
            }
        )
    combined_optimizations.update(
        {
            "optimize_volume": True,
            "min_volume_ratio": 1.0,
            "max_volume_ratio": 1.5,
            "improve_tp_sl_ratio": True,
        }
    )
    hypotheses.append(
        {
            "name": "Комбинированная оптимизация (все улучшения)",
            "optimizations": combined_optimizations,
        }
    )

    # 5. Тестирование гипотез
    logger.info("🧪 Тестирование %d гипотез...", len(hypotheses))
    results = []

    for hypothesis in hypotheses:
        result = await test_hypothesis(
            hypothesis["name"],
            hypothesis["optimizations"],
            symbols,
            data_dict,
            btc_df,
        )
        results.append(result)

        logger.info(
            "✅ %s: Win Rate=%.2f%%, Return=%.2f%%, Sharpe=%.2f, PF=%.2f",
            hypothesis["name"],
            result["metrics"].get("win_rate", 0),
            result["metrics"].get("total_return", 0),
            result["metrics"].get("sharpe_ratio", 0),
            result["metrics"].get("profit_factor", 0),
        )

    # 6. Сравнение результатов
    logger.info("📊 Сравнение результатов...")

    comparison = {
        "base": {
            "name": "Базовый (текущий)",
            "metrics": base_metrics,
        },
        "hypotheses": [
            {
                "name": r["hypothesis"],
                "metrics": r["metrics"],
                "improvement": {
                    "win_rate": r["metrics"].get("win_rate", 0) - base_metrics.get("win_rate", 0),
                    "total_return": r["metrics"].get("total_return", 0)
                    - base_metrics.get("total_return", 0),
                    "sharpe_ratio": r["metrics"].get("sharpe_ratio", 0)
                    - base_metrics.get("sharpe_ratio", 0),
                    "profit_factor": r["metrics"].get("profit_factor", 0)
                    - base_metrics.get("profit_factor", 0),
                    "max_drawdown": base_metrics.get("max_drawdown", 0)
                    - r["metrics"].get("max_drawdown", 0),
                },
            }
            for r in results
        ],
    }

    # 7. Выбор лучшего решения
    best_hypothesis = max(
        comparison["hypotheses"],
        key=lambda x: (
            x["metrics"].get("profit_factor", 0) * 0.3
            + x["metrics"].get("win_rate", 0) / 100 * 0.2
            + x["metrics"].get("total_return", 0) / 100 * 0.2
            + x["metrics"].get("sharpe_ratio", 0) / 10 * 0.2
            - x["metrics"].get("max_drawdown", 0) / 100 * 0.1
        ),
    )

    logger.info("🏆 Лучшее решение: %s", best_hypothesis["name"])
    logger.info(
        "   Win Rate: %.2f%% (+%.2f%%)",
        best_hypothesis["metrics"].get("win_rate", 0),
        best_hypothesis["improvement"].get("win_rate", 0),
    )
    logger.info(
        "   Total Return: %.2f%% (+%.2f%%)",
        best_hypothesis["metrics"].get("total_return", 0),
        best_hypothesis["improvement"].get("total_return", 0),
    )
    logger.info(
        "   Sharpe Ratio: %.2f (+%.2f)",
        best_hypothesis["metrics"].get("sharpe_ratio", 0),
        best_hypothesis["improvement"].get("sharpe_ratio", 0),
    )
    logger.info(
        "   Profit Factor: %.2f (+%.2f)",
        best_hypothesis["metrics"].get("profit_factor", 0),
        best_hypothesis["improvement"].get("profit_factor", 0),
    )
    logger.info(
        "   Max Drawdown: %.2f%% (%.2f%%)",
        best_hypothesis["metrics"].get("max_drawdown", 0),
        best_hypothesis["improvement"].get("max_drawdown", 0),
    )

    # 8. Сохранение результатов
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Конвертируем volume_analysis для JSON (убираем tuple ключи)
    volume_analysis_json = {}
    if volume_analysis.get("stats"):
        volume_analysis_json["win_rates"] = volume_analysis.get("win_rates", {})
        # Конвертируем stats
        stats_dict = {}
        for key, value in volume_analysis["stats"].items():
            if isinstance(key, tuple):
                stats_dict[f"{key[0]}_{key[1]}"] = value
            else:
                stats_dict[str(key)] = value
        volume_analysis_json["stats"] = stats_dict

    final_report = {
        "base_metrics": base_metrics,
        "comparison": comparison,
        "best_solution": {
            "name": best_hypothesis["name"],
            "optimizations": next(
                (h["optimizations"] for h in hypotheses if h["name"] == best_hypothesis["name"]), {}
            ),
            "metrics": best_hypothesis["metrics"],
            "improvement": best_hypothesis["improvement"],
        },
        "all_results": [
            {
                "hypothesis": r["hypothesis"],
                "optimizations": r["optimizations"],
                "metrics": r["metrics"],
            }
            for r in results
        ],
        "analysis": {
            "volume_analysis": volume_analysis_json,
            "rsi_analysis": rsi_analysis,
        },
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(final_report, f, ensure_ascii=False, indent=2, default=str)

    logger.info("💾 Результаты сохранены: %s", output_path)

    return final_report


if __name__ == "__main__":
    asyncio.run(main())
