#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Быстрое обновление метрик для оптимизированных параметров"""

import sys
import os
import json

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
    add_technical_indicators_with_rust,
    save_optimized_params
)

def main():
    symbol = "BTCUSDT"
    
    print("="*70)
    print(f"📊 ОБНОВЛЕНИЕ МЕТРИК ДЛЯ {symbol}")
    print("="*70)
    
    # Загружаем оптимизированные параметры
    try:
        from archive.experimental.optimized_config import OPTIMIZED_PARAMETERS
        params = OPTIMIZED_PARAMETERS.get(symbol, {})
        tp_mult = params.get('tp_mult', 2.25)
        sl_mult = params.get('sl_mult', 1.60)
        print(f"\n✅ Параметры: TP={tp_mult:.2f}x, SL={sl_mult:.2f}x")
    except ImportError:
        print("⚠️ Используем дефолтные параметры")
        tp_mult = 2.25
        sl_mult = 1.60
    
    # Загружаем данные (годовые)
    print(f"\n📥 Загрузка данных для {symbol}...")
    df = load_historical_data(symbol, limit_days=None)
    
    if df is None or len(df) < 100:
        print(f"❌ Недостаточно данных")
        return
    
    print(f"✅ Загружено {len(df)} свечей")
    
    # Добавляем индикаторы
    print("🔧 Добавление индикаторов...")
    df = add_technical_indicators_with_rust(df)
    print("✅ Индикаторы добавлены")
    
    # Запускаем бэктест
    print(f"\n🚀 Запуск бэктеста...")
    metrics = run_backtest_with_params(
        df.copy(),
        tp_mult=tp_mult,
        sl_mult=sl_mult,
        use_ai=True,
        symbol=symbol
    )
    
    # Выводим результаты
    print("\n📈 МЕТРИКИ:")
    print(f"   Сделок: {metrics['total_trades']}")
    print(f"   Win Rate: {metrics['win_rate']:.2f}%")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"   Доходность: {metrics['total_return']:.2f}%")
    print(f"   Sharpe: {metrics['sharpe_ratio']:.2f}")
    print(f"   Max DD: {metrics['max_drawdown']:.2f}%")
    
    # Сохраняем
    print("\n💾 Сохранение...")
    result = {
        'symbol': symbol,
        'tp_mult': tp_mult,
        'sl_mult': sl_mult,
        'metrics': metrics,
        'score': 1.5
    }
    
    save_optimized_params([result])
    
    # Проверяем
    print("\n✅ Проверка сохранения:")
    try:
        with open('archive/experimental/optimized_params.json', 'r') as f:
            saved = json.load(f)
        if 'BTCUSDT' in saved and 'metrics' in saved['BTCUSDT']:
            print("   ✅ Метрики сохранены в JSON")
        else:
            print("   ❌ Метрики не найдены в JSON")
    except Exception as e:
        print(f"   ⚠️ Ошибка проверки: {e}")
    
    print("\n✅ ГОТОВО!")

if __name__ == "__main__":
    main()

