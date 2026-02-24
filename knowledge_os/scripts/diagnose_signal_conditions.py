#!/usr/bin/env python3
"""
Диагностика условий генерации сигналов

Проверяет, какие условия не выполняются и почему не генерируются сигналы
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from src.signals.core import soft_entry_signal, strict_entry_signal
from src.signals.indicators import add_technical_indicators

# Загружаем данные
df = pd.read_csv("data/backtest_data_yearly/BTCUSDT.csv")
if "timestamp" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)

df = add_technical_indicators(df)

print("🔍 ДИАГНОСТИКА УСЛОВИЙ ГЕНЕРАЦИИ СИГНАЛОВ")
print("=" * 80)

# Анализируем статистику условий
long_conditions_stats = {
    "bb_lower_zone": 0,
    "ema_trend_up": 0,
    "rsi_oversold": 0,
    "volume_high": 0,
    "volatility_ok": 0,
    "momentum_positive": 0,
    "trend_strength_ok": 0,
    "all_conditions": 0,
}

short_conditions_stats = {
    "bb_upper_zone": 0,
    "ema_trend_down": 0,
    "rsi_overbought": 0,
    "volume_high": 0,
    "volatility_ok": 0,
    "momentum_negative": 0,
    "trend_strength_ok": 0,
    "all_conditions": 0,
}

total_checked = 0
signals_found = 0

for i in range(200, min(5000, len(df))):
    if i >= len(df):
        break

    total_checked += 1

    try:
        current_price = df["close"].iloc[i]
        bb_lower = df["bb_lower"].iloc[i] if "bb_lower" in df.columns else None
        bb_upper = df["bb_upper"].iloc[i] if "bb_upper" in df.columns else None
        ema7 = df["ema7"].iloc[i] if "ema7" in df.columns else None
        ema25 = df["ema25"].iloc[i] if "ema25" in df.columns else None
        rsi = df["rsi"].iloc[i] if "rsi" in df.columns else None
        volume_ratio = df["volume_ratio"].iloc[i] if "volume_ratio" in df.columns else None
        volatility = df["volatility"].iloc[i] if "volatility" in df.columns else None
        momentum = df["momentum"].iloc[i] if "momentum" in df.columns else None
        trend_strength = df["trend_strength"].iloc[i] if "trend_strength" in df.columns else None

        # Проверяем NaN
        if (
            pd.isna(current_price)
            or pd.isna(bb_lower)
            or pd.isna(bb_upper)
            or pd.isna(ema7)
            or pd.isna(ema25)
        ):
            continue

        # Безопасные значения
        rsi = rsi if not pd.isna(rsi) else 50
        volume_ratio = volume_ratio if not pd.isna(volume_ratio) else 1.0
        volatility = volatility if not pd.isna(volatility) else 2.0
        momentum = momentum if not pd.isna(momentum) else 0.0
        trend_strength = trend_strength if not pd.isna(trend_strength) else 1.0

        # Проверяем условия для LONG
        bb_lower_zone = current_price <= bb_lower + (bb_upper - bb_lower) * 0.1
        ema_trend_up = ema7 > ema25
        rsi_oversold = rsi < 35
        volume_high = volume_ratio > 1.5
        volatility_ok = volatility > 1.5
        momentum_positive = momentum > 0
        trend_strength_ok = trend_strength > 0.6

        if bb_lower_zone:
            long_conditions_stats["bb_lower_zone"] += 1
        if ema_trend_up:
            long_conditions_stats["ema_trend_up"] += 1
        if rsi_oversold:
            long_conditions_stats["rsi_oversold"] += 1
        if volume_high:
            long_conditions_stats["volume_high"] += 1
        if volatility_ok:
            long_conditions_stats["volatility_ok"] += 1
        if momentum_positive:
            long_conditions_stats["momentum_positive"] += 1
        if trend_strength_ok:
            long_conditions_stats["trend_strength_ok"] += 1

        all_long = all(
            [
                bb_lower_zone,
                ema_trend_up,
                rsi_oversold,
                volume_high,
                volatility_ok,
                momentum_positive,
                trend_strength_ok,
            ]
        )
        if all_long:
            long_conditions_stats["all_conditions"] += 1

        # Проверяем условия для SHORT
        bb_upper_zone = current_price >= bb_upper - (bb_upper - bb_lower) * 0.1
        ema_trend_down = ema7 < ema25
        rsi_overbought = rsi > 65
        momentum_negative = momentum < 0

        if bb_upper_zone:
            short_conditions_stats["bb_upper_zone"] += 1
        if ema_trend_down:
            short_conditions_stats["ema_trend_down"] += 1
        if rsi_overbought:
            short_conditions_stats["rsi_overbought"] += 1
        if volume_high:
            short_conditions_stats["volume_high"] += 1
        if volatility_ok:
            short_conditions_stats["volatility_ok"] += 1
        if momentum_negative:
            short_conditions_stats["momentum_negative"] += 1
        if trend_strength_ok:
            short_conditions_stats["trend_strength_ok"] += 1

        all_short = all(
            [
                bb_upper_zone,
                ema_trend_down,
                rsi_overbought,
                volume_high,
                volatility_ok,
                momentum_negative,
                trend_strength_ok,
            ]
        )
        if all_short:
            short_conditions_stats["all_conditions"] += 1

        # Проверяем реальные сигналы
        signal, _ = soft_entry_signal(df, i)
        if signal:
            signals_found += 1

    except Exception as e:
        continue

print(f"\n📊 АНАЛИЗ {total_checked} СВЕЧЕЙ:")
print("=" * 80)

print("\n🔵 УСЛОВИЯ ДЛЯ LONG:")
for condition, count in long_conditions_stats.items():
    pct = (count / total_checked * 100) if total_checked > 0 else 0
    print(f"   {condition}: {count} ({pct:.2f}%)")

print("\n🔴 УСЛОВИЯ ДЛЯ SHORT:")
for condition, count in short_conditions_stats.items():
    pct = (count / total_checked * 100) if total_checked > 0 else 0
    print(f"   {condition}: {count} ({pct:.2f}%)")

print("\n🎯 РЕЗУЛЬТАТЫ:")
print(f"   Всего проверено: {total_checked}")
print(f"   Сигналов найдено: {signals_found} ({signals_found / total_checked * 100:.2f}%)")
print(f"   LONG: все условия выполнены {long_conditions_stats['all_conditions']} раз")
print(f"   SHORT: все условия выполнены {short_conditions_stats['all_conditions']} раз")

print("\n💡 РЕКОМЕНДАЦИИ:")
if long_conditions_stats["all_conditions"] == 0 and short_conditions_stats["all_conditions"] == 0:
    print("   ⚠️ Условия слишком строгие - ни разу не выполнены все условия одновременно")
    print("   💡 Рекомендуется:")
    print("      - Ослабить требования к RSI (например, < 40 вместо < 35)")
    print("      - Снизить требование к объему (например, > 1.2 вместо > 1.5)")
    print("      - Использовать soft режим вместо strict")
