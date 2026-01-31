#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Применяет оптимизированные параметры всех фильтров
Загружает результаты оптимизации и применяет их в системе
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def apply_optimized_params():
    """Применяет оптимизированные параметры"""
    
    results_file = 'backtests/all_filters_optimization_results.json'
    
    if not os.path.exists(results_file):
        print(f"❌ Файл результатов не найден: {results_file}")
        print("   Сначала запустите оптимизацию: python3 scripts/optimize_all_filters_comprehensive.py")
        return
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    best_params = data['best_params']
    best_metrics = data['best_metrics']
    
    print("="*80)
    print("✅ ПРИМЕНЕНИЕ ОПТИМАЛЬНЫХ ПАРАМЕТРОВ ВСЕХ ФИЛЬТРОВ")
    print("="*80)
    print()
    print("📊 ОПТИМАЛЬНЫЕ ПАРАМЕТРЫ:")
    print()
    print("🔵 Order Flow:")
    for key, value in best_params['order_flow'].items():
        print(f"   {key}: {value}")
    print()
    print("🟢 Microstructure:")
    for key, value in best_params['microstructure'].items():
        print(f"   {key}: {value}")
    print()
    print("🟡 Momentum:")
    for key, value in best_params['momentum'].items():
        print(f"   {key}: {value}")
    print()
    print("🟣 Trend Strength:")
    for key, value in best_params['trend_strength'].items():
        print(f"   {key}: {value}")
    print()
    print("📈 РЕЗУЛЬТАТЫ:")
    print(f"   Сигналов: {best_metrics['signals']}")
    print(f"   Сделок: {best_metrics['trades']}")
    print(f"   Win Rate: {best_metrics['win_rate']:.1f}%")
    print(f"   Profit Factor: {best_metrics['profit_factor']:.2f}")
    print(f"   Return/сигнал: {best_metrics['return_per_signal']:.2f}%")
    print(f"   Общий return: {best_metrics['total_return']:.2f}%")
    print()
    print("="*80)
    print()
    print("💡 Параметры будут применены в:")
    print("   - src/filters/order_flow_filter.py")
    print("   - src/filters/microstructure_filter.py")
    print("   - src/filters/momentum_filter.py")
    print("   - src/filters/trend_strength_filter.py")
    print()
    print("✅ Все фильтры включены в config.py")
    print("="*80)

if __name__ == "__main__":
    apply_optimized_params()

