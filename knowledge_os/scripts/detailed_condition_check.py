#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Детальная проверка каждого условия отдельно
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from src.signals.indicators import add_technical_indicators

df = pd.read_csv('data/backtest_data_yearly/BTCUSDT.csv')
if 'timestamp' in df.columns:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

df = add_technical_indicators(df)

print("🔍 ДЕТАЛЬНАЯ ПРОВЕРКА УСЛОВИЙ")
print("="*80)

# Статистика по каждому условию
conditions_stats = {
    'bb_lower_zone': 0,
    'ema_trend_up': 0,
    'rsi_oversold': 0,
    'volume_ok': 0,
    'volatility_ok': 0,
    'momentum_ok': 0,
    'trend_ok': 0,
    'all_except_bb': 0,
    'all_except_volume': 0,
    'all_except_volatility': 0,
    'all_conditions': 0,
}

total = 0

for i in range(200, min(5000, len(df))):
    if i >= len(df):
        break
    
    total += 1
    
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
        
        # Проверяем каждое условие
        bb_lower_zone = current_price <= bb_lower + (bb_upper - bb_lower) * 0.2
        ema_trend_up = ema7 > ema25
        rsi_oversold = rsi < 45
        volume_ok = volume_ratio > 1.1
        volatility_ok = volatility > 0.5
        momentum_ok = momentum > -0.5
        trend_ok = trend_strength > 0.4
        
        if bb_lower_zone:
            conditions_stats['bb_lower_zone'] += 1
        if ema_trend_up:
            conditions_stats['ema_trend_up'] += 1
        if rsi_oversold:
            conditions_stats['rsi_oversold'] += 1
        if volume_ok:
            conditions_stats['volume_ok'] += 1
        if volatility_ok:
            conditions_stats['volatility_ok'] += 1
        if momentum_ok:
            conditions_stats['momentum_ok'] += 1
        if trend_ok:
            conditions_stats['trend_ok'] += 1
        
        # Комбинации
        all_except_bb = all([ema_trend_up, rsi_oversold, volume_ok, volatility_ok, momentum_ok, trend_ok])
        all_except_volume = all([bb_lower_zone, ema_trend_up, rsi_oversold, volatility_ok, momentum_ok, trend_ok])
        all_except_volatility = all([bb_lower_zone, ema_trend_up, rsi_oversold, volume_ok, momentum_ok, trend_ok])
        all_conditions = all([bb_lower_zone, ema_trend_up, rsi_oversold, volume_ok, volatility_ok, momentum_ok, trend_ok])
        
        if all_except_bb:
            conditions_stats['all_except_bb'] += 1
        if all_except_volume:
            conditions_stats['all_except_volume'] += 1
        if all_except_volatility:
            conditions_stats['all_except_volatility'] += 1
        if all_conditions:
            conditions_stats['all_conditions'] += 1
        
    except Exception as e:
        continue

print(f"\n📊 СТАТИСТИКА ПО УСЛОВИЯМ (из {total} свечей):")
print("="*80)

for condition, count in conditions_stats.items():
    pct = (count / total * 100) if total > 0 else 0
    print(f"   {condition}: {count} ({pct:.2f}%)")

print("\n💡 АНАЛИЗ:")
if conditions_stats['all_except_bb'] > 0:
    print(f"   ✅ Без BB условия: {conditions_stats['all_except_bb']} раз - BB условие слишком строгое")
if conditions_stats['all_except_volume'] > 0:
    print(f"   ✅ Без Volume условия: {conditions_stats['all_except_volume']} раз - Volume условие слишком строгое")
if conditions_stats['all_except_volatility'] > 0:
    print(f"   ✅ Без Volatility условия: {conditions_stats['all_except_volatility']} раз - Volatility условие слишком строгое")
if conditions_stats['all_conditions'] == 0:
    print("   ⚠️ Все условия одновременно не выполняются - нужно ослабить несколько условий")

