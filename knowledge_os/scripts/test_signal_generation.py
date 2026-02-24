#!/usr/bin/env python3
"""
Тестовый скрипт для проверки генерации сигналов

Проверяет, почему не генерируются сигналы в бэктесте
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from src.signals.core import soft_entry_signal, strict_entry_signal
from src.signals.indicators import add_technical_indicators

# Загружаем данные
df = pd.read_csv("data/backtest_data_yearly/BTCUSDT.csv")
if "timestamp" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)

print(f"✅ Загружено {len(df)} свечей")

# Добавляем индикаторы
df = add_technical_indicators(df)
print("✅ Индикаторы добавлены")

# Проверяем несколько свечей
print("\n🔍 Проверка генерации сигналов:")
print("=" * 80)

for i in [200, 500, 1000, 2000, 3000, 4000, 5000]:
    if i >= len(df):
        continue

    # Проверяем базовые условия
    current_price = df["close"].iloc[i]
    bb_lower = df["bb_lower"].iloc[i] if "bb_lower" in df.columns else None
    bb_upper = df["bb_upper"].iloc[i] if "bb_upper" in df.columns else None
    ema7 = df["ema7"].iloc[i] if "ema7" in df.columns else None
    ema25 = df["ema25"].iloc[i] if "ema25" in df.columns else None
    rsi = df["rsi"].iloc[i] if "rsi" in df.columns else None
    volume_ratio = df["volume_ratio"].iloc[i] if "volume_ratio" in df.columns else None

    # Проверяем условия для LONG
    long_conditions = []
    if bb_lower and not pd.isna(bb_lower) and bb_upper and not pd.isna(bb_upper):
        long_conditions.append(f"BB: {current_price <= bb_lower + (bb_upper - bb_lower) * 0.1}")
    if ema7 and ema25 and not pd.isna(ema7) and not pd.isna(ema25):
        long_conditions.append(f"EMA: {ema7 > ema25}")
    if rsi and not pd.isna(rsi):
        long_conditions.append(f"RSI: {rsi < 35}")
    if volume_ratio and not pd.isna(volume_ratio):
        long_conditions.append(f"Volume: {volume_ratio > 1.5}")

    # Проверяем сигналы
    strict_signal, _ = strict_entry_signal(df, i)
    soft_signal, _ = soft_entry_signal(df, i)

    print(f"\nСвеча {i}:")
    print(f"  Цена: {current_price:.2f}")
    rsi_str = f"{rsi:.2f}" if rsi and not pd.isna(rsi) else "N/A"
    vol_str = f"{volume_ratio:.2f}" if volume_ratio and not pd.isna(volume_ratio) else "N/A"
    ema_str = (
        f"{ema7 > ema25}" if ema7 and ema25 and not pd.isna(ema7) and not pd.isna(ema25) else "N/A"
    )
    print(f"  RSI: {rsi_str}")
    print(f"  Volume Ratio: {vol_str}")
    print(f"  EMA7 > EMA25: {ema_str}")
    print(f"  Strict Signal: {strict_signal}")
    print(f"  Soft Signal: {soft_signal}")

    if strict_signal or soft_signal:
        print("  ✅ НАЙДЕН СИГНАЛ!")
        break

print("\n" + "=" * 80)
print("✅ Проверка завершена")
