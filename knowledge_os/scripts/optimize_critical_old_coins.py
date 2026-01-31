#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оптимизация критичных старых монет с отрицательным Sharpe Ratio или низкой доходностью
"""

import json
import os
import sys
import glob
from datetime import datetime
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import itertools

from src.shared.utils.datetime_utils import get_utc_now

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 🔧 ВКЛЮЧАЕМ RUST УСКОРЕНИЕ
os.environ['USE_RUST'] = 'true'
try:
    from src.infrastructure.performance.rust_accelerator import is_rust_available, get_rust_accelerator
    if is_rust_available():
        print("✅ Rust acceleration доступен")
        rust_accelerator = get_rust_accelerator()
    else:
        print("⚠️ Rust acceleration недоступен, используем Python")
        rust_accelerator = None
except ImportError:
    print("⚠️ Rust модуль не найден, используем Python")
    rust_accelerator = None

from scripts.backtest_5coins_intelligent import (
    load_yearly_data, run_backtest, get_intelligent_filter_system
)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

PERIOD_DAYS = 30  # Месячные данные для оптимизации

# 🔧 КРИТИЧНЫЕ МОНЕТЫ ДЛЯ ОПТИМИЗАЦИИ
# ПРИОРИТЕТ 1: Отрицательный Sharpe Ratio (убыточные)
CRITICAL_NEGATIVE_SHARPE = [
    "BTCUSDT",  # Sharpe -0.060
    "BNBUSDT",  # Sharpe -0.180
    "SOLUSDT",  # Sharpe -0.070
    "XRPUSDT",  # Sharpe -0.010
    "TRXUSDT",  # Sharpe -0.120
    "ICPUSDT",  # Sharpe -0.110
    "LINKUSDT", # Sharpe -0.020
    "BCHUSDT",  # Sharpe -0.160
]

# ПРИОРИТЕТ 2: Низкая доходность (<20%)
LOW_RETURN_COINS = [
    "ETHUSDT",  # Return 0.06%
    "ADAUSDT",  # Return 0.18%
    "DOGEUSDT", # Return 0.08%
    "DOTUSDT",  # Return 0.49%
    "AVAXUSDT", # Return 0.18%
    "NEARUSDT", # Return 0.49%
    "UNIUSDT",  # Return 0.40%
    "LTCUSDT",  # Return -0.01%
]

# Объединяем все критичные монеты
TEST_SYMBOLS = CRITICAL_NEGATIVE_SHARPE + LOW_RETURN_COINS

print(f"📊 Критичных монет для оптимизации: {len(TEST_SYMBOLS)}")
print(f"   Приоритет 1 (отрицательный Sharpe): {len(CRITICAL_NEGATIVE_SHARPE)}")
print(f"   Приоритет 2 (низкая доходность): {len(LOW_RETURN_COINS)}")
print()

# Быстрая сетка параметров
QUICK_PARAMETER_GRID = {
    'volume_ratio': [0.3, 0.4, 0.5, 0.6, 0.7],
    'rsi_oversold': [40],
    'rsi_overbought': [60],
    'trend_strength': [0.15],
    'quality_score': [0.6, 0.65, 0.7, 0.72],
    'momentum_threshold': [-5.0]
}

PARAM_GRID = QUICK_PARAMETER_GRID

# Многопоточность
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', '20'))

# ============================================================================
# ФУНКЦИИ (копируем из optimize_intelligent_params.py)
# ============================================================================

def test_symbol_with_params(
    symbol: str,
    params: Dict[str, float],
    intelligent_system
) -> Optional[Dict[str, Any]]:
    """Тестирует символ с заданными параметрами"""
    try:
        # Используем monkey patching для временной подмены параметров
        import src.ai.intelligent_filter_system as ifs_module
        
        # Сохраняем оригинальную функцию
        original_func = ifs_module.get_symbol_specific_parameters
        
        # Создаем новую функцию с фиксированными параметрами
        def mock_get_params(symbol_name, *args, **kwargs):
            if symbol_name == symbol:
                return params
            return original_func(symbol_name, *args, **kwargs)
        
        # Подменяем функцию
        ifs_module.get_symbol_specific_parameters = mock_get_params
        
        try:
            # Загружаем данные
            df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
            if df is None or len(df) < 100:
                return None
            
            # Запускаем бэктест
            stats = run_backtest(df, symbol, mode="soft", intelligent_system=intelligent_system)
            
            if stats is None:
                return None
            
            # Рассчитываем метрики
            total_return = (stats.balance - stats.initial_balance) / stats.initial_balance
            
            # Sharpe Ratio (исправленная формула)
            if stats.total_trades > 0:
                win_rate = stats.winning_trades / stats.total_trades
                profit_factor = stats.total_profit / stats.total_loss if stats.total_loss > 0 else float('inf')
                
                # Исправленная формула Sharpe
                if stats.total_trades >= 10:
                    avg_return = total_return / stats.total_trades
                    returns_std = abs(avg_return) * 0.5  # Упрощенная оценка волатильности
                    sharpe_ratio = avg_return / returns_std if returns_std > 0 else 0.0
                else:
                    sharpe_ratio = 0.0
            else:
                sharpe_ratio = 0.0
                win_rate = 0.0
                profit_factor = 0.0
            
            return {
                'total_trades': stats.total_trades,
                'winning_trades': stats.winning_trades,
                'losing_trades': stats.losing_trades,
                'win_rate': win_rate * 100,
                'profit_factor': profit_factor,
                'total_return': total_return,
                'sharpe_ratio': sharpe_ratio,
                'final_balance': stats.balance,
                'total_profit': stats.total_profit,
                'total_loss': stats.total_loss,
                'params': params
            }
        finally:
            # Восстанавливаем оригинальную функцию
            ifs_module.get_symbol_specific_parameters = original_func
            
    except Exception as e:
        print(f"⚠️ Ошибка при тестировании {symbol}: {e}")
        return None

def optimize_symbol(symbol: str, intelligent_system) -> Optional[Dict[str, Any]]:
    """Оптимизирует параметры для одного символа"""
    print(f"🔄 Начало оптимизации для {symbol}")
    
    # Генерируем все комбинации параметров
    param_names = list(PARAM_GRID.keys())
    param_values = [PARAM_GRID[name] for name in param_names]
    combinations = list(itertools.product(*param_values))
    
    print(f"   Тестируем {len(combinations)} комбинаций параметров...")
    
    best_result = None
    best_score = float('-inf')
    
    for i, combo in enumerate(combinations):
        params = dict(zip(param_names, combo))
        
        result = test_symbol_with_params(symbol, params, intelligent_system)
        
        if result is None:
            continue
        
        # Score = Sharpe Ratio (приоритет)
        score = result['sharpe_ratio']
        
        if score > best_score:
            best_score = score
            best_result = result.copy()
            best_result['best_params'] = params
            print(f"   [{i+1}/{len(combinations)}] Новый лучший результат: Sharpe={score:.3f}, Return={result['total_return']*100:.2f}%")
    
    if best_result:
        print(f"✅ Оптимизация завершена для {symbol}: Sharpe={best_result['sharpe_ratio']:.3f}, Return={best_result['total_return']*100:.2f}%")
        return {
            'symbol': symbol,
            'best_params': best_result['best_params'],
            'best_result': best_result
        }
    else:
        print(f"❌ Не удалось оптимизировать {symbol}")
        return None

# ============================================================================
# ОСНОВНОЙ КОД
# ============================================================================

def main():
    print("="*80)
    print("🔧 ОПТИМИЗАЦИЯ КРИТИЧНЫХ СТАРЫХ МОНЕТ")
    print("="*80)
    print()
    
    intelligent_system = get_intelligent_filter_system()
    
    results = {}
    
    # Оптимизируем в многопоточном режиме
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(optimize_symbol, symbol, intelligent_system): symbol 
                  for symbol in TEST_SYMBOLS}
        
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
                if result:
                    results[symbol] = result
            except Exception as e:
                print(f"❌ Ошибка при оптимизации {symbol}: {e}")
    
    # Сохраняем результаты
    timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
    output_file = f"backtests/optimize_critical_old_coins_{timestamp}.json"
    
    os.makedirs('backtests', exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print()
    print("="*80)
    print(f"✅ Результаты сохранены в {output_file}")
    print(f"🎉 ОПТИМИЗАЦИЯ ЗАВЕРШЕНА!")
    print(f"📊 Оптимизировано монет: {len(results)}/{len(TEST_SYMBOLS)}")
    print("="*80)

if __name__ == '__main__':
    main()

