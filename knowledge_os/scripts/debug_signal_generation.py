#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Детальная диагностика генерации сигналов

Проверяет каждый шаг генерации сигнала и находит, где именно блокируется
"""

import importlib
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.signals.indicators import add_technical_indicators
import src.signals.core as core_module

# Загружаем данные
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
data_file = os.path.join(project_root, 'data', 'backtest_data_yearly', 'BTCUSDT.csv')

if not os.path.exists(data_file):
    print(f"❌ ОШИБКА: Файл данных не найден: {data_file}")
    sys.exit(1)

try:
    df = pd.read_csv(data_file)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    df = add_technical_indicators(df)
except Exception as e:
    print(f"❌ ОШИБКА при загрузке данных: {e}")
    sys.exit(1)

print("🔍 ДЕТАЛЬНАЯ ДИАГНОСТИКА ГЕНЕРАЦИИ СИГНАЛОВ")
print("="*80)

# Отключаем все новые фильтры для теста
os.environ['USE_ORDER_FLOW_FILTER'] = 'false'
os.environ['USE_MICROSTRUCTURE_FILTER'] = 'false'
os.environ['USE_MOMENTUM_FILTER'] = 'false'
os.environ['USE_TREND_STRENGTH_FILTER'] = 'false'
os.environ['USE_VP_FILTER'] = 'false'
os.environ['USE_VWAP_FILTER'] = 'false'

# Перезагружаем модуль
importlib.reload(core_module)

# Ищем свечи, где выполняются базовые условия
print("\n🔍 Поиск свечей с выполненными базовыми условиями...")

# pylint: disable=invalid-name
found_candidates = 0
checked = 0

max_index = min(2000, len(df))
for i in range(200, max_index):
    checked += 1

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

        if pd.isna(current_price) or pd.isna(bb_lower) or pd.isna(bb_upper) or pd.isna(ema7) or pd.isna(ema25):
            continue

        rsi = rsi if not pd.isna(rsi) else 50
        volume_ratio = volume_ratio if not pd.isna(volume_ratio) else 1.0
        volatility = volatility if not pd.isna(volatility) else 2.0
        momentum = momentum if not pd.isna(momentum) else 0.0
        trend_strength = trend_strength if not pd.isna(trend_strength) else 1.0

        # Мягкие условия для LONG (обновленные)
        bb_lower_zone = current_price <= bb_lower + (bb_upper - bb_lower) * 0.2
        ema_trend_up = ema7 > ema25
        rsi_oversold = rsi < 45
        volume_ok = volume_ratio > 1.1  # Обновлено
        volatility_ok = volatility > 0.5  # Обновлено
        momentum_ok = momentum > -0.5
        trend_ok = trend_strength > 0.4

        # Проверяем базовые условия (без фильтров)
        base_conditions_long = [
            bb_lower_zone,
            ema_trend_up,
            rsi_oversold,
            volume_ok,
            volatility_ok,
            momentum_ok,
            trend_ok,
        ]

        if all(base_conditions_long):
            found_candidates += 1
            print(f"\n✅ НАЙДЕНА СВЕЧА {i} С ВЫПОЛНЕННЫМИ БАЗОВЫМИ УСЛОВИЯМИ ДЛЯ LONG:")
            print(f"   Цена: {current_price:.2f}")
            print(f"   RSI: {rsi:.2f}")
            print(f"   Volume Ratio: {volume_ratio:.2f}")
            print(f"   Volatility: {volatility:.2f}")
            print(f"   Momentum: {momentum:.2f}")
            print(f"   Trend Strength: {trend_strength:.2f}")

            # Проверяем реальный сигнал
            signal, signal_price = core_module.soft_entry_signal(df, i)
            print(f"   Реальный сигнал: {signal}")
            if signal_price:
                print(f"   Цена сигнала: {signal_price:.2f}")

            if signal:
                print("   ✅ СИГНАЛ СГЕНЕРИРОВАН!")
                break
            else:
                print("   ❌ Сигнал НЕ сгенерирован (блокируется фильтрами)")

            if found_candidates >= 5:
                break
        
    except Exception as e:
        if i % 500 == 0:
            print(f"⚠️ Ошибка на свече {i}: {type(e).__name__}: {e}")
        continue

print("\n📊 ИТОГО:")
print(f"   Проверено свечей: {checked}")
print(f"   Найдено кандидатов: {found_candidates}")

if found_candidates == 0:
    print("\n⚠️ ПРОБЛЕМА: Базовые условия слишком строгие!")
    print("💡 Рекомендация: Ослабить условия volatility и volume")
