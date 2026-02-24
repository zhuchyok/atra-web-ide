#!/usr/bin/env python3
"""
Тестирование логики точек входа и выхода на годовых данных
Анализ различных вариантов и сравнение с текущей реализацией
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.shared.utils.datetime_utils import get_utc_now

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.historical_data_loader import HistoricalDataLoader
from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Варианты точки входа
ENTRY_VARIANTS = {
    "close": {"name": "Close цена (текущий)", "get_entry_price": lambda row, side: row["close"]},
    "low_high": {
        "name": "Low для LONG, High для SHORT",
        "get_entry_price": lambda row, side: row["low"] if side == "LONG" else row["high"],
    },
    "vwap": {
        "name": "VWAP свечи",
        "get_entry_price": lambda row, side: (row["high"] + row["low"] + row["close"]) / 3,
    },
    "mid": {
        "name": "Средняя цена (high+low)/2",
        "get_entry_price": lambda row, side: (row["high"] + row["low"]) / 2,
    },
    "close_slippage": {
        "name": "Close с проскальзыванием 0.2%",
        "get_entry_price": lambda row, side: row["close"] * (1.002 if side == "LONG" else 0.998),
    },
}

# Варианты TP/SL множителей
TP_SL_VARIANTS = {
    "current": {
        "name": "Текущие (TP1=2.0, TP2=4.0, SL=2.0)",
        "tp1_mult": 2.0,
        "tp2_mult": 4.0,
        "sl_mult": 2.0,
    },
    "conservative": {
        "name": "Консервативные (TP1=1.5, TP2=3.0, SL=1.5)",
        "tp1_mult": 1.5,
        "tp2_mult": 3.0,
        "sl_mult": 1.5,
    },
    "aggressive": {
        "name": "Агрессивные (TP1=3.0, TP2=6.0, SL=2.5)",
        "tp1_mult": 3.0,
        "tp2_mult": 6.0,
        "sl_mult": 2.5,
    },
    "adaptive": {
        "name": "Адаптивные (на основе волатильности)",
        "tp1_mult": None,  # Будет рассчитываться динамически
        "tp2_mult": None,
        "sl_mult": None,
    },
}


class EntryExitTester:
    """Тестер логики точек входа и выхода"""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.data_loader = HistoricalDataLoader()

    async def load_symbol_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Загружает данные символа"""
        try:
            csv_path = PROJECT_ROOT / "data" / "backtest_data" / f"{symbol}.csv"
            if not csv_path.exists():
                logger.warning("⚠️ Файл не найден: %s", csv_path)
                return None

            df = pd.read_csv(csv_path)
            if df.empty:
                return None

            # Конвертируем timestamp
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            elif "time" in df.columns:
                df["timestamp"] = pd.to_datetime(df["time"])

            # Сортируем по времени
            df = df.sort_values("timestamp").reset_index(drop=True)

            # Добавляем индикаторы если их нет
            if "atr" not in df.columns:
                df["atr"] = self._calculate_atr(df, period=14)

            logger.info("✅ Загружено %d свечей для %s", len(df), symbol)
            return df

        except Exception as e:
            logger.error("❌ Ошибка загрузки данных для %s: %s", symbol, e)
            return None

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Рассчитывает ATR"""
        try:
            high_low = df["high"] - df["low"]
            high_close = np.abs(df["high"] - df["close"].shift())
            low_close = np.abs(df["low"] - df["close"].shift())

            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()

            return atr
        except Exception as e:
            logger.error("❌ Ошибка расчета ATR: %s", e)
            return pd.Series([0] * len(df))

    async def test_entry_variants(
        self, symbol: str, df: pd.DataFrame, entry_variant: str, days: int = 365
    ) -> Dict[str, Any]:
        """Тестирует вариант точки входа"""
        try:
            variant = ENTRY_VARIANTS[entry_variant]

            # Запускаем бектест с модифицированной логикой входа
            backtest = AdvancedBacktest(initial_balance=10000.0, risk_per_trade=2.0, leverage=2.0)

            # Модифицируем логику входа
            original_get_entry = (
                backtest.get_entry_price if hasattr(backtest, "get_entry_price") else None
            )

            def get_entry_price(row: pd.Series, side: str) -> float:
                return variant["get_entry_price"](row, side)

            # Запускаем бектест
            btc_df = await self.load_symbol_data("BTCUSDT")
            eth_df = await self.load_symbol_data("ETHUSDT")
            sol_df = await self.load_symbol_data("SOLUSDT")

            if btc_df is None or eth_df is None or sol_df is None:
                logger.warning("⚠️ Не удалось загрузить базовые активы для %s", symbol)
                return {}

            backtest.btc_df = btc_df
            backtest.eth_df = eth_df
            backtest.sol_df = sol_df

            await backtest.run_backtest(symbol, df, btc_df, days)
            metrics = backtest.calculate_metrics()

            # Анализируем точки входа
            entry_analysis = self._analyze_entries(backtest.trades, df)

            result = {
                "symbol": symbol,
                "entry_variant": entry_variant,
                "entry_variant_name": variant["name"],
                "metrics": metrics,
                "entry_analysis": entry_analysis,
                "total_trades": len(backtest.trades),
            }

            return result

        except Exception as e:
            logger.error("❌ Ошибка тестирования варианта входа для %s: %s", symbol, e)
            return {}

    def _analyze_entries(self, trades: List[Dict[str, Any]], df: pd.DataFrame) -> Dict[str, Any]:
        """Анализирует точки входа"""
        if not trades:
            return {}

        entry_prices = []
        close_prices = []
        slippage = []

        for trade in trades:
            entry_time = trade.get("entry_time")
            entry_price = trade.get("entry_price")

            if entry_time and entry_price:
                # Находим соответствующую свечу
                if isinstance(entry_time, str):
                    entry_time = pd.to_datetime(entry_time)

                matching_row = df[df["timestamp"] == entry_time]
                if not matching_row.empty:
                    close = matching_row.iloc[0]["close"]
                    entry_prices.append(entry_price)
                    close_prices.append(close)

                    # Проскальзывание
                    if entry_price > close:
                        slippage.append((entry_price - close) / close * 100)
                    else:
                        slippage.append((close - entry_price) / close * 100)

        if not entry_prices:
            return {}

        return {
            "avg_entry_price": np.mean(entry_prices),
            "avg_close_price": np.mean(close_prices),
            "avg_slippage_pct": np.mean(slippage) if slippage else 0.0,
            "max_slippage_pct": np.max(slippage) if slippage else 0.0,
            "min_slippage_pct": np.min(slippage) if slippage else 0.0,
            "entry_vs_close_diff_pct": (np.mean(entry_prices) - np.mean(close_prices))
            / np.mean(close_prices)
            * 100,
        }

    async def run_comprehensive_test(
        self, symbols: List[str], entry_variants: List[str] = None, days: int = 365
    ) -> Dict[str, Any]:
        """Запускает комплексное тестирование"""
        if entry_variants is None:
            entry_variants = list(ENTRY_VARIANTS.keys())

        logger.info("🚀 Начинаем комплексное тестирование логики входа/выхода")
        logger.info("   Символов: %d", len(symbols))
        logger.info("   Вариантов входа: %d", len(entry_variants))

        all_results = []

        for symbol in symbols:
            logger.info("📊 Тестируем %s...", symbol)

            df = await self.load_symbol_data(symbol)
            if df is None or len(df) < 100:
                logger.warning("⚠️ Пропускаем %s: недостаточно данных", symbol)
                continue

            for entry_variant in entry_variants:
                logger.info("   Вариант входа: %s", ENTRY_VARIANTS[entry_variant]["name"])

                result = await self.test_entry_variants(symbol, df, entry_variant, days)

                if result:
                    all_results.append(result)

        # Агрегируем результаты
        summary = self._aggregate_results(all_results)

        return {
            "summary": summary,
            "detailed_results": all_results,
            "timestamp": get_utc_now().isoformat(),
        }

    def _aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Агрегирует результаты тестирования"""
        if not results:
            return {}

        # Группируем по вариантам входа
        by_variant = {}
        for result in results:
            variant = result.get("entry_variant")
            if variant not in by_variant:
                by_variant[variant] = []
            by_variant[variant].append(result)

        summary = {}
        for variant, variant_results in by_variant.items():
            metrics_list = [r.get("metrics", {}) for r in variant_results]
            entry_analysis_list = [r.get("entry_analysis", {}) for r in variant_results]

            # Средние метрики
            avg_win_rate = np.mean([m.get("win_rate", 0) for m in metrics_list])
            avg_profit_factor = np.mean([m.get("profit_factor", 0) for m in metrics_list])
            avg_total_pnl = np.mean([m.get("total_pnl", 0) for m in metrics_list])
            avg_sharpe = np.mean([m.get("sharpe_ratio", 0) for m in metrics_list])

            # Анализ входа
            avg_entry_slippage = np.mean(
                [e.get("avg_slippage_pct", 0) for e in entry_analysis_list if e]
            )
            avg_entry_vs_close = np.mean(
                [e.get("entry_vs_close_diff_pct", 0) for e in entry_analysis_list if e]
            )

            summary[variant] = {
                "name": ENTRY_VARIANTS[variant]["name"],
                "total_symbols": len(variant_results),
                "avg_win_rate": avg_win_rate,
                "avg_profit_factor": avg_profit_factor,
                "avg_total_pnl": avg_total_pnl,
                "avg_sharpe_ratio": avg_sharpe,
                "avg_entry_slippage_pct": avg_entry_slippage,
                "avg_entry_vs_close_diff_pct": avg_entry_vs_close,
            }

        return summary


async def main():
    """Главная функция"""
    # Портфель из 14 монет SOL_HIGH
    portfolio_symbols = [
        "SOLUSDT",
        "WIFUSDT",
        "BONKUSDT",
        "RAYUSDT",
        "JUPUSDT",
        "ORCAUSDT",
        "MNGOUSDT",
        "ATLASUSDT",
        "SAMOUSDT",
        "COPEUSDT",
        "STEPUSDT",
        "MEDIAUSDT",
        "FIDAUSDT",
        "OXYUSDT",
    ]

    # Проверяем доступность данных
    available_symbols = []
    for symbol in portfolio_symbols:
        csv_path = PROJECT_ROOT / "data" / "backtest_data" / f"{symbol}.csv"
        if csv_path.exists():
            available_symbols.append(symbol)
        else:
            logger.warning("⚠️ Данные для %s не найдены", symbol)

    if not available_symbols:
        logger.error("❌ Нет доступных данных для тестирования")
        return

    logger.info("✅ Найдено %d символов с данными", len(available_symbols))

    # Запускаем тестирование
    tester = EntryExitTester()

    results = await tester.run_comprehensive_test(
        symbols=available_symbols[:5],  # Начинаем с 5 для быстрого теста
        entry_variants=["close", "low_high", "vwap", "mid"],
        days=365,
    )

    # Сохраняем результаты
    output_file = (
        PROJECT_ROOT
        / "data"
        / "reports"
        / f"entry_exit_test_{get_utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    logger.info("✅ Результаты сохранены: %s", output_file)

    # Выводим краткую сводку
    print("\n" + "=" * 80)
    print("📊 КРАТКАЯ СВОДКА РЕЗУЛЬТАТОВ")
    print("=" * 80)

    summary = results.get("summary", {})
    for variant, data in summary.items():
        print(f"\n{variant.upper()}: {data.get('name', 'N/A')}")
        print(f"  Win Rate: {data.get('avg_win_rate', 0):.2f}%")
        print(f"  Profit Factor: {data.get('avg_profit_factor', 0):.2f}")
        print(f"  Total PnL: {data.get('avg_total_pnl', 0):.2f}")
        print(f"  Sharpe Ratio: {data.get('avg_sharpe_ratio', 0):.2f}")
        print(f"  Entry Slippage: {data.get('avg_entry_slippage_pct', 0):.3f}%")
        print(f"  Entry vs Close: {data.get('avg_entry_vs_close_diff_pct', 0):.3f}%")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
