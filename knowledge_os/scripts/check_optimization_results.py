#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Быстрая проверка результатов оптимизации
"""

import sys
import os
import json

# Временно отключаем фильтры
os.environ['USE_VP_FILTER'] = 'false'
os.environ['USE_VWAP_FILTER'] = 'false'
os.environ['USE_ORDER_FLOW_FILTER'] = 'false'
os.environ['USE_MICROSTRUCTURE_FILTER'] = 'false'
os.environ['USE_MOMENTUM_FILTER'] = 'false'
os.environ['USE_TREND_STRENGTH_FILTER'] = 'false'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.optimize_symbol_params_with_ai import (
    run_backtest_with_params, 
    load_historical_data, 
    add_technical_indicators_with_rust
)

def main():
    symbol = "BTCUSDT"
    
    print("="*70)
    print(f"📊 ПРОВЕРКА РЕЗУЛЬТАТОВ ОПТИМИЗАЦИИ ДЛЯ {symbol}")
    print("="*70)
    
    # Загружаем оптимизированные параметры
    try:
        from archive.experimental.optimized_config import OPTIMIZED_PARAMETERS
        params = OPTIMIZED_PARAMETERS.get(symbol, {})
        tp_mult = params.get('tp_mult', 2.0)
        sl_mult = params.get('sl_mult', 1.5)
        print(f"\n✅ Оптимизированные параметры:")
        print(f"   TP_MULT: {tp_mult:.2f}x")
        print(f"   SL_MULT: {sl_mult:.2f}x")
    except ImportError:
        print("⚠️ Оптимизированные параметры не найдены, используем дефолтные")
        tp_mult = 2.0
        sl_mult = 1.5
    
    # Загружаем данные (годовые)
    print(f"\n📥 Загрузка данных для {symbol}...")
    df = load_historical_data(symbol, limit_days=None)
    
    if df is None or len(df) < 100:
        print(f"❌ Недостаточно данных для {symbol}")
        return
    
    print(f"✅ Загружено {len(df)} свечей")
    
    # Добавляем индикаторы
    print("🔧 Добавление индикаторов...")
    df = add_technical_indicators_with_rust(df)
    print("✅ Индикаторы добавлены")
    
    # Запускаем бэктест
    print(f"\n🚀 Запуск бэктеста с параметрами TP={tp_mult:.2f}x, SL={sl_mult:.2f}x...")
    metrics = run_backtest_with_params(
        df.copy(),
        tp_mult=tp_mult,
        sl_mult=sl_mult,
        use_ai=True,
        symbol=symbol
    )
    
    # Выводим результаты
    print("\n" + "="*70)
    print("📈 РЕЗУЛЬТАТЫ БЭКТЕСТА:")
    print("="*70)
    print(f"   Сделок: {metrics['total_trades']}")
    print(f"   Сигналов: {metrics.get('signals_count', 'N/A')}")
    print(f"   Win Rate: {metrics['win_rate']:.2f}%")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"   Доходность: {metrics['total_return']:.2f}%")
    print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"   Max Drawdown: {metrics['max_drawdown']:.2f}%")
    print(f"   Начальный баланс: $10,000.00")
    print(f"   Финальный баланс: ${metrics['final_balance']:.2f}")
    profit = metrics['final_balance'] - 10000
    print(f"   Прибыль: ${profit:.2f} ({metrics['total_return']:.2f}%)")
    print("="*70)
    
    # Сохраняем метрики в optimized_config.py
    if metrics['total_trades'] > 0:
        print("\n💾 Обновление метрик в optimized_config.py...")
        try:
            config_path = "archive/experimental/optimized_config.py"
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Добавляем метрики как комментарии
            if f"# Score:" not in content:
                new_content = content.replace(
                    f"    '{symbol}': {{\n        'tp_mult': {tp_mult:.2f},\n        'sl_mult': {sl_mult:.2f},\n    }},\n",
                    f"    '{symbol}': {{\n        'tp_mult': {tp_mult:.2f},\n        'sl_mult': {sl_mult:.2f},\n        # Метрики:\n        # Сделок: {metrics['total_trades']}\n        # Win Rate: {metrics['win_rate']:.2f}%\n        # Profit Factor: {metrics['profit_factor']:.2f}\n        # Доходность: {metrics['total_return']:.2f}%\n        # Sharpe Ratio: {metrics['sharpe_ratio']:.2f}\n        # Max Drawdown: {metrics['max_drawdown']:.2f}%\n    }},\n"
                )
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print("✅ Метрики обновлены")
        except Exception as e:
            print(f"⚠️ Не удалось обновить метрики: {e}")

if __name__ == "__main__":
    main()

