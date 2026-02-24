#!/usr/bin/env python3
"""
Исправление расчета корреляции - используем данные из CSV напрямую
"""

import asyncio
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.risk.correlation_risk import CorrelationRiskManager


def load_csv_data(symbol: str, data_dir: Path = None) -> pd.DataFrame:
    """Загружает данные из CSV файла"""
    if data_dir is None:
        data_dir = PROJECT_ROOT / "data" / "backtest_data"

    csv_file = data_dir / f"{symbol}.csv"

    if not csv_file.exists():
        return None

    try:
        df = pd.read_csv(csv_file)

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
        elif df.index.name == "timestamp" or df.index.dtype == "object":
            df.index = pd.to_datetime(df.index)

        return df
    except Exception as e:
        print(f"Ошибка загрузки {symbol}: {e}")
        return None


async def test_correlation_calculation():
    """Тестирует расчет корреляции для нескольких монет"""
    data_dir = PROJECT_ROOT / "data" / "backtest_data"
    correlation_manager = CorrelationRiskManager(db_path="trading.db")

    test_symbols = ["ETHUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT", "DOGEUSDT"]

    print("🔍 Тестирование расчета корреляции:\n")

    for symbol in test_symbols:
        df = load_csv_data(symbol, data_dir)
        if df is None:
            print(f"⚠️ {symbol}: нет данных")
            continue

        # Вычисляем корреляции
        btc_corr = await correlation_manager.calculate_correlation(symbol, "BTC", df)
        eth_corr = await correlation_manager.calculate_correlation(symbol, "ETH", df)
        sol_corr = await correlation_manager.calculate_correlation(symbol, "SOL", df)

        # Определяем группу
        group = await correlation_manager.get_symbol_group_async(symbol, df)

        print(
            f"{symbol:12s} | BTC: {btc_corr:6.3f} | ETH: {eth_corr:6.3f} | SOL: {sol_corr:6.3f} | → {group}"
        )


if __name__ == "__main__":
    asyncio.run(test_correlation_calculation())
