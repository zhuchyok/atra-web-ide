#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест исправленного Volume Profile фильтра
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Настройки для теста
os.environ['USE_VP_FILTER'] = 'True'
os.environ['DISABLE_EXTRA_FILTERS'] = 'true'
os.environ['volume_profile_threshold'] = '0.6'

from scripts.backtest_5coins_intelligent import load_yearly_data, run_backtest
from src.signals.indicators import add_technical_indicators

def test_vp_filter():
    """Тестирует исправленный VP фильтр"""
    print("="*80)
    print("🧪 ТЕСТ ИСПРАВЛЕННОГО VOLUME PROFILE ФИЛЬТРА")
    print("="*80)
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
    period_days = 7  # Быстрый тест на неделе
    
    print(f"\n📅 Период: {period_days} дней")
    print(f"🎯 Параметр: volume_profile_threshold = 0.6")
    print(f"📊 Символы: {', '.join(symbols)}")
    print("="*80)
    
    total_trades = 0
    total_return = 0.0
    
    for symbol in symbols:
        print(f"\n📊 Тестирование {symbol}...")
        df = load_yearly_data(symbol, limit_days=period_days)
        if df is None or len(df) < 100:
            print(f"   ❌ Недостаточно данных")
            continue
        
        stats = run_backtest(df, symbol=symbol, mode="soft")
        metrics = stats.get_metrics()
        
        trades = metrics.get('total_trades', 0)
        ret = metrics.get('total_return', 0)
        
        total_trades += trades
        total_return += ret
        
        print(f"   ✅ {symbol}: {ret:+.2f}% ({trades} сделок)")
    
    print("\n" + "="*80)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("="*80)
    print(f"📈 Общая доходность: {total_return:+.2f}%")
    print(f"📊 Всего сделок: {total_trades}")
    print(f"📈 Средняя доходность на сделку: {total_return / total_trades if total_trades > 0 else 0:.2f}%")
    print("="*80)
    
    # Сравнение с baseline
    baseline_return = 0.28  # Из предыдущих тестов на 7 днях
    improvement = total_return - baseline_return
    print(f"\n📈 vs Baseline (без фильтра): {improvement:+.2f}%")
    
    if improvement > 0:
        print("✅ Фильтр улучшает результаты!")
    elif improvement < -1.0:
        print("❌ Фильтр ухудшает результаты (отключить)")
    else:
        print("⚠️ Фильтр нейтрален (можно оставить)")
    
    print("="*80)

if __name__ == "__main__":
    test_vp_filter()

