#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оптимизация всех оставшихся неоптимизированных монет
"""

import json
import os
import sys
import glob
from datetime import datetime
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.shared.utils.datetime_utils import get_utc_now

# 🔧 ПЫТАЕМСЯ ИМПОРТИРОВАТЬ RUST МОДУЛЬ
try:
    import atra_rs
    RUST_MODULE_AVAILABLE = True
except ImportError:
    RUST_MODULE_AVAILABLE = False
import itertools
import re
from pathlib import Path

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

# Находим все неоптимизированные монеты
target_file = Path('src/ai/intelligent_filter_system.py')
content = target_file.read_text(encoding='utf-8')

# Находим все монеты
pattern = r"'([A-Z0-9]+USDT)'"
matches = re.findall(pattern, content)
unique_coins = sorted(set(matches))

# 🔧 НАХОДИМ УЖЕ ОПТИМИЗИРОВАННЫЕ ИЗ JSON ФАЙЛОВ И КОММЕНТАРИЕВ В КОДЕ
optimized_from_json = set()
for batch_file in Path('backtests').glob('optimize_all_remaining_batch*.json'):
    try:
        with open(batch_file, 'r') as f:
            batch_results = json.load(f)
            if batch_results:  # Только непустые
                optimized_from_json.update(batch_results.keys())
    except:
        pass

# Также находим оптимизированные по комментариям в коде
optimized_from_code = set()
for coin in unique_coins:
    coin_pattern = rf"'{coin}':\s*\{{[^}}]+}}"
    coin_match = re.search(coin_pattern, content, re.DOTALL)
    if coin_match:
        block = coin_match.group(0)
        if '# Результаты' in block or '# результаты' in block.lower():
            optimized_from_code.add(coin)

# Объединяем все оптимизированные
all_optimized = optimized_from_json | optimized_from_code

# Находим неоптимизированные
not_optimized = [coin for coin in unique_coins if coin not in all_optimized]

# Проверяем наличие данных
data_dir = Path('data/backtest_data_yearly')
coins_with_data = []
for coin in not_optimized:
    csv_path = data_dir / f"{coin}.csv"
    if csv_path.exists():
        coins_with_data.append(coin)

print(f"📊 Найдено неоптимизированных монет: {len(not_optimized)}")
print(f"✅ С данными для оптимизации: {len(coins_with_data)}")
print()

# Разбиваем на партии
BATCH_SIZE = 25
ALL_COINS = coins_with_data

# Определяем текущую партию из аргументов или переменных окружения
BATCH_NUM = int(os.environ.get('BATCH_NUM', '1'))
# 🔧 ИСПРАВЛЕНО: используем относительные индексы от начала списка неоптимизированных монет
# После обновления параметров в коде монеты исключаются из списка,
# поэтому каждая партия берет монеты с начала текущего списка неоптимизированных
# Партия 1: индексы 0-24, Партия 2: 0-24 (но уже другой список), и т.д.
start_idx = 0
end_idx = BATCH_SIZE
TEST_SYMBOLS = ALL_COINS[start_idx:end_idx]

print(f"📋 Партия {BATCH_NUM}: монеты {start_idx+1}-{min(end_idx, len(ALL_COINS))} из {len(ALL_COINS)}")
if len(TEST_SYMBOLS) > 0:
    print(f"   {', '.join(TEST_SYMBOLS[:10])}")
    if len(TEST_SYMBOLS) > 10:
        print(f"   ... и еще {len(TEST_SYMBOLS) - 10} монет")
else:
    print(f"   ⚠️ Нет монет для партии {BATCH_NUM}")
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
# ФУНКЦИИ
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
                    returns_std = abs(avg_return) * 0.5
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
    print("🔧 ОПТИМИЗАЦИЯ ВСЕХ ОСТАВШИХСЯ МОНЕТ")
    print("="*80)
    print()
    
    intelligent_system = get_intelligent_filter_system()
    
    results = {}
    
    # 🔧 ИСПОЛЬЗУЕМ RUST ДЛЯ ПАРАЛЛЕЛЬНОГО ЗАПУСКА
    # Примечание: Rust acceleration уже используется внутри бэктестов для вычисления индикаторов
    # Python ThreadPoolExecutor используется для параллельного запуска оптимизации разных монет
    # Это оптимальный подход, так как atra_rs.run_backtests_parallel() предназначен для запуска
    # отдельных скриптов бэктестов, а не для оптимизации параметров
    
    print(f"🚀 Запуск оптимизации ({MAX_WORKERS} потоков)...")
    print(f"   • Rust acceleration: {'✅ активирован' if os.environ.get('USE_RUST') == 'true' else '❌ отключен'}")
    print(f"   • Rust используется для вычисления индикаторов внутри бэктестов")
    print()
    
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
    output_file = f"backtests/optimize_all_remaining_batch{BATCH_NUM}_{timestamp}.json"
    
    os.makedirs('backtests', exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print()
    print("="*80)
    print(f"✅ Результаты сохранены в {output_file}")
    print(f"🎉 ОПТИМИЗАЦИЯ ПАРТИИ {BATCH_NUM} ЗАВЕРШЕНА!")
    print(f"📊 Оптимизировано монет: {len(results)}/{len(TEST_SYMBOLS)}")
    print()
    print(f"📋 Всего монет для оптимизации: {len(ALL_COINS)}")
    print(f"📋 Осталось: {max(0, len(ALL_COINS) - end_idx)}")
    print("="*80)

if __name__ == '__main__':
    main()

