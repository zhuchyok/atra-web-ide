#!/usr/bin/env python3
"""
Загрузка исторических данных для 9 оставшихся монет
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.download_data_for_50new_coins import fetch_binance_data

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "backtest_data_yearly"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REMAINING_COINS = [
    "EOSUSDT",
    "FTMUSDT",
    "KEEPUSDT",
    "KLAYUSDT",
    "MKRUSDT",
    "ONTUSDT",
    "RNDRUSDT",
    "XMRUSDT",
    "ZILUSDT",
]

if __name__ == "__main__":
    print("=" * 80)
    print("📥 Загрузка данных для 9 оставшихся монет")
    print("=" * 80)
    print()

    for i, symbol in enumerate(REMAINING_COINS, 1):
        output_file = OUTPUT_DIR / f"{symbol}.csv"

        if output_file.exists():
            print(f"[{i}/9] ⏭️  {symbol} - уже загружено")
            continue

        print(f"[{i}/9] 📥 Загрузка {symbol}...", end=" ")
        try:
            df = fetch_binance_data(symbol, days=365)
            if df is not None and len(df) > 0:
                df.to_csv(output_file, index=False)
                print(f"✅ Загружено {len(df)} свечей")
            else:
                print("❌ Нет данных")
        except Exception as e:
            print(f"❌ Ошибка: {e}")

        time.sleep(1)  # Пауза между запросами

    print()
    print("✅ Загрузка завершена!")
