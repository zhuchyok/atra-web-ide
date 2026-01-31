#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оптимизация новых фильтров по очереди
Использует рабочий baseline из core.py и добавляет новые фильтры через флаги
"""

import json
import os
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

import pandas as pd
from tqdm import tqdm

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.signals.indicators import add_technical_indicators
from src.utils.shared_utils import get_dynamic_tp_levels
from src.signals.risk import get_dynamic_sl_level

# ============================================================================
# НАСТРОЙКИ
# ============================================================================

START_BALANCE = 10000.0
FEE = 0.001
RISK_PER_TRADE = 0.05

TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
PERIOD_DAYS = 30
MAX_WORKERS = 20

# Параметры для оптимизации новых фильтров
INTEREST_ZONE_PARAMS = [
    {'lookback_periods': 50, 'min_volume_cluster': 1.0, 'zone_width_pct': 0.3, 'min_zone_strength': 0.5},
    {'lookback_periods': 100, 'min_volume_cluster': 1.5, 'zone_width_pct': 0.5, 'min_zone_strength': 0.6},
    {'lookback_periods': 200, 'min_volume_cluster': 2.0, 'zone_width_pct': 0.7, 'min_zone_strength': 0.7},
]

FIBONACCI_ZONE_PARAMS = [
    {'lookback_periods': 50, 'tolerance_pct': 0.3, 'require_strong_levels': False},
    {'lookback_periods': 100, 'tolerance_pct': 0.5, 'require_strong_levels': False},
    {'lookback_periods': 200, 'tolerance_pct': 0.7, 'require_strong_levels': True},
]

VOLUME_IMBALANCE_PARAMS = [
    {'lookback_periods': 10, 'volume_spike_threshold': 1.5, 'min_volume_ratio': 1.0, 'require_volume_confirmation': True},
    {'lookback_periods': 20, 'volume_spike_threshold': 2.0, 'min_volume_ratio': 1.2, 'require_volume_confirmation': True},
    {'lookback_periods': 30, 'volume_spike_threshold': 2.5, 'min_volume_ratio': 1.5, 'require_volume_confirmation': False},
]

def load_yearly_data(symbol: str, limit_days: int = 30):
    """Загружает данные для символа"""
    try:
        data_dir = "data/backtest_data_yearly"
        file_path = os.path.join(data_dir, f"{symbol}_1h.csv")
        
        if not os.path.exists(file_path):
            return None
        
        df = pd.read_csv(file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        if limit_days:
            cutoff_date = df['timestamp'].max() - pd.Timedelta(days=limit_days)
            df = df[df['timestamp'] >= cutoff_date].reset_index(drop=True)
        
        return df
    except Exception as e:
        print(f"❌ Ошибка загрузки данных для {symbol}: {e}")
        return None

def get_symbol_tp_sl_multipliers(symbol: str):
    """Получает TP/SL multipliers для символа"""
    try:
        from archive.experimental.optimized_config import OPTIMIZED_PARAMETERS
        params = OPTIMIZED_PARAMETERS.get(symbol, {})
        return params.get('tp_mult', 2.0), params.get('sl_mult', 1.5)
    except ImportError:
        return 2.0, 1.5

def run_backtest_with_filter_params(symbol: str, filter_name: str, filter_params: Dict):
    """Запускает бэктест с параметрами фильтра"""
    try:
        # Включаем все существующие фильтры (рабочий baseline)
        os.environ['USE_VP_FILTER'] = 'true'
        os.environ['USE_VWAP_FILTER'] = 'true'
        os.environ['USE_ORDER_FLOW_FILTER'] = 'true'
        os.environ['USE_MICROSTRUCTURE_FILTER'] = 'true'
        os.environ['USE_MOMENTUM_FILTER'] = 'true'
        os.environ['USE_TREND_STRENGTH_FILTER'] = 'true'
        os.environ['USE_AMT_FILTER'] = 'true'
        os.environ['USE_MARKET_PROFILE_FILTER'] = 'true'
        os.environ['USE_INSTITUTIONAL_PATTERNS_FILTER'] = 'true'
        os.environ['DISABLE_EXTRA_FILTERS'] = 'false'  # Включаем все фильтры
        
        # Включаем новый фильтр для оптимизации
        if filter_name == 'interest_zone':
            os.environ['USE_INTEREST_ZONE_FILTER'] = 'true'
            os.environ['USE_FIBONACCI_ZONE_FILTER'] = 'false'
            os.environ['USE_VOLUME_IMBALANCE_FILTER'] = 'false'
            # Устанавливаем параметры через переменные окружения
            os.environ['IZ_LOOKBACK_PERIODS'] = str(filter_params['lookback_periods'])
            os.environ['IZ_MIN_VOLUME_CLUSTER'] = str(filter_params['min_volume_cluster'])
            os.environ['IZ_ZONE_WIDTH_PCT'] = str(filter_params['zone_width_pct'])
            os.environ['IZ_MIN_ZONE_STRENGTH'] = str(filter_params['min_zone_strength'])
        elif filter_name == 'fibonacci_zone':
            os.environ['USE_INTEREST_ZONE_FILTER'] = 'false'
            os.environ['USE_FIBONACCI_ZONE_FILTER'] = 'true'
            os.environ['USE_VOLUME_IMBALANCE_FILTER'] = 'false'
            os.environ['FIB_LOOKBACK_PERIODS'] = str(filter_params['lookback_periods'])
            os.environ['FIB_TOLERANCE_PCT'] = str(filter_params['tolerance_pct'])
            os.environ['FIB_REQUIRE_STRONG_LEVELS'] = str(filter_params['require_strong_levels'])
        elif filter_name == 'volume_imbalance':
            os.environ['USE_INTEREST_ZONE_FILTER'] = 'false'
            os.environ['USE_FIBONACCI_ZONE_FILTER'] = 'false'
            os.environ['USE_VOLUME_IMBALANCE_FILTER'] = 'true'
            os.environ['VI_LOOKBACK_PERIODS'] = str(filter_params['lookback_periods'])
            os.environ['VI_VOLUME_SPIKE_THRESHOLD'] = str(filter_params['volume_spike_threshold'])
            os.environ['VI_MIN_VOLUME_RATIO'] = str(filter_params['min_volume_ratio'])
            os.environ['VI_REQUIRE_VOLUME_CONFIRMATION'] = str(filter_params['require_volume_confirmation'])
        
        # Очищаем кэш модулей
        modules_to_clear = ['src.signals.core', 'src.signals', 'config']
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]
        
        # Используем оригинальный soft_entry_signal из core.py
        from src.signals.core import soft_entry_signal
        
        # Загружаем данные
        df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
        if df is None or len(df) < 25:
            return {'trades': 0, 'return': 0.0, 'signals': 0, 'winning_trades': 0, 'losing_trades': 0}
        
        df = add_technical_indicators(df)
        start_idx = 25
        
        balance = START_BALANCE
        trades = []
        signals_generated = 0
        
        tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)
        
        for i in range(start_idx, len(df)):
            side, entry_price = soft_entry_signal(df, i)
            signals_generated += 1 if side else 0
            
            if side and entry_price:
                tp1_pct, tp2_pct = get_dynamic_tp_levels(df, i, side)
                tp1 = entry_price * (1 + tp1_pct / 100 * tp_mult)
                
                sl_level_pct = get_dynamic_sl_level(df, i, side)
                if side == 'long':
                    sl_level = entry_price * (1 - sl_level_pct / 100 * sl_mult)
                else:
                    sl_level = entry_price * (1 + sl_level_pct / 100 * sl_mult)
                
                risk_amount = balance * RISK_PER_TRADE
                sl_distance = abs(entry_price - sl_level)
                
                if sl_distance > 0:
                    position_size = risk_amount / sl_distance
                    exit_price = tp1
                    profit = (exit_price - entry_price) * position_size * (1 - FEE)
                    balance += profit
                    trades.append({
                        'profit': profit,
                        'entry': entry_price,
                        'exit': exit_price
                    })
        
        total_return = ((balance - START_BALANCE) / START_BALANCE) * 100
        winning_trades = sum(1 for t in trades if t['profit'] > 0)
        losing_trades = sum(1 for t in trades if t['profit'] <= 0)
        
        return {
            'trades': len(trades),
            'return': total_return,
            'signals': signals_generated,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'trades_list': trades
        }
    except Exception as e:
        print(f"❌ Ошибка для {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return {'trades': 0, 'return': 0.0, 'signals': 0, 'winning_trades': 0, 'losing_trades': 0}

def optimize_single_filter(filter_name: str, filter_params_list: List[Dict]):
    """Оптимизирует один фильтр"""
    print(f"\n{'='*80}")
    print(f"🚀 ОПТИМИЗАЦИЯ: {filter_name.upper()}")
    print(f"{'='*80}")
    print(f"📊 Параметров для тестирования: {len(filter_params_list)}")
    print(f"📊 Символов: {len(TEST_SYMBOLS)}")
    print(f"📊 Всего тестов: {len(filter_params_list) * len(TEST_SYMBOLS)}")
    print()
    
    all_results = {}
    total_tasks = len(filter_params_list) * len(TEST_SYMBOLS)
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        
        for params in filter_params_list:
            for symbol in TEST_SYMBOLS:
                future = executor.submit(
                    run_backtest_with_filter_params,
                    symbol,
                    filter_name,
                    params
                )
                futures.append((future, params, symbol))
        
        with tqdm(total=total_tasks, desc=f"Оптимизация {filter_name}") as pbar:
            for future, params, symbol in futures:
                result = future.result()
                
                params_key = str(params)
                if params_key not in all_results:
                    all_results[params_key] = {
                        'params': params,
                        'symbols': {},
                        'total_trades': 0,
                        'total_return': 0.0,
                        'total_signals': 0,
                        'total_winning': 0,
                        'total_losing': 0
                    }
                
                all_results[params_key]['symbols'][symbol] = result
                all_results[params_key]['total_trades'] += result['trades']
                all_results[params_key]['total_return'] += result['return']
                all_results[params_key]['total_signals'] += result['signals']
                all_results[params_key]['total_winning'] += result['winning_trades']
                all_results[params_key]['total_losing'] += result['losing_trades']
                
                pbar.update(1)
    
    # Рассчитываем метрики
    for params_key, result in all_results.items():
        if result['total_trades'] > 0:
            result['win_rate'] = (result['total_winning'] / result['total_trades'] * 100)
            
            total_profit = 0
            total_loss = 0
            for symbol_result in result['symbols'].values():
                for trade_data in symbol_result.get('trades_list', []):
                    profit = trade_data.get('profit', 0)
                    if profit > 0:
                        total_profit += profit
                    else:
                        total_loss += abs(profit)
            
            if total_loss > 0:
                result['profit_factor'] = total_profit / total_loss
            else:
                result['profit_factor'] = float('inf') if total_profit > 0 else 0
            
            result['return_per_signal'] = (result['total_return'] / result['total_signals']) if result['total_signals'] > 0 else 0
        else:
            result['win_rate'] = 0
            result['profit_factor'] = 0
            result['return_per_signal'] = 0
    
    # Сортируем по качеству
    def quality_score(result):
        if result['total_trades'] == 0:
            return -float('inf')
        win_rate_bonus = result['win_rate'] / 100
        pf_bonus = min(result['profit_factor'], 10.0) / 10.0
        return_bonus = result['return_per_signal'] / 100
        return win_rate_bonus * pf_bonus * return_bonus * result['total_trades']
    
    sorted_results = sorted(
        all_results.items(),
        key=lambda x: quality_score(x[1]),
        reverse=True
    )
    
    # Выводим результаты
    print(f"\n{'='*80}")
    print(f"📊 РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ: {filter_name.upper()}")
    print(f"{'='*80}\n")
    
    print("Топ-3 комбинации параметров:\n")
    for i, (params_key, result) in enumerate(sorted_results[:3], 1):
        print(f"{i}. Параметры: {result['params']}")
        print(f"   Сигналов: {result['total_signals']}")
        print(f"   Сделок: {result['total_trades']}")
        print(f"   Win Rate: {result['win_rate']:.1f}%")
        print(f"   Profit Factor: {result['profit_factor']:.2f}")
        print(f"   Return/сигнал: {result['return_per_signal']:.2f}%")
        print(f"   Общий return: {result['total_return']:.2f}%")
        print()
    
    # Возвращаем лучшие параметры
    if len(sorted_results) > 0:
        best_params = sorted_results[0][1]['params']
        best_metrics = {
            'signals': sorted_results[0][1]['total_signals'],
            'trades': sorted_results[0][1]['total_trades'],
            'win_rate': sorted_results[0][1]['win_rate'],
            'profit_factor': sorted_results[0][1]['profit_factor'],
            'return_per_signal': sorted_results[0][1]['return_per_signal'],
            'total_return': sorted_results[0][1]['total_return']
        }
        
        return {
            'filter_name': filter_name,
            'best_params': best_params,
            'best_metrics': best_metrics
        }
    else:
        return {
            'filter_name': filter_name,
            'best_params': None,
            'best_metrics': None
        }

def main():
    """Главная функция"""
    print("="*80)
    print("🚀 ОПТИМИЗАЦИЯ НОВЫХ ФИЛЬТРОВ ПО ОЧЕРЕДИ")
    print("="*80)
    print()
    print("📊 Используем рабочий baseline из core.py")
    print("📊 Добавляем новые фильтры по очереди")
    print()
    print("📊 Этапы:")
    print("   1. Interest Zone Filter")
    print("   2. Fibonacci Zone Filter")
    print("   3. Volume Imbalance Filter")
    print()
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print(f"🧵 Потоков: {MAX_WORKERS}")
    print("="*80)
    print()
    
    results = {}
    
    # Этап 1: Interest Zone Filter
    iz_result = optimize_single_filter('interest_zone', INTEREST_ZONE_PARAMS)
    results['interest_zone'] = iz_result
    if iz_result['best_params']:
        print(f"✅ Этап 1 завершен! Оптимальные параметры: {iz_result['best_params']}")
    else:
        print(f"⚠️  Этап 1: Нет результатов")
    print()
    
    # Этап 2: Fibonacci Zone Filter
    fib_result = optimize_single_filter('fibonacci_zone', FIBONACCI_ZONE_PARAMS)
    results['fibonacci_zone'] = fib_result
    if fib_result['best_params']:
        print(f"✅ Этап 2 завершен! Оптимальные параметры: {fib_result['best_params']}")
    else:
        print(f"⚠️  Этап 2: Нет результатов")
    print()
    
    # Этап 3: Volume Imbalance Filter
    vi_result = optimize_single_filter('volume_imbalance', VOLUME_IMBALANCE_PARAMS)
    results['volume_imbalance'] = vi_result
    if vi_result['best_params']:
        print(f"✅ Этап 3 завершен! Оптимальные параметры: {vi_result['best_params']}")
    else:
        print(f"⚠️  Этап 3: Нет результатов")
    print()
    
    # Сохраняем результаты
    output_file = 'backtests/new_filters_optimization_results.json'
    os.makedirs('backtests', exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("="*80)
    print("✅ ВСЕ ЭТАПЫ ЗАВЕРШЕНЫ!")
    print("="*80)
    print()
    print("📊 ИТОГОВЫЕ ОПТИМАЛЬНЫЕ ПАРАМЕТРЫ:")
    print()
    for key, value in results.items():
        if value['best_params']:
            print(f"   {key}: {value['best_params']}")
        else:
            print(f"   {key}: Нет результатов")
    print()
    print(f"📁 Результаты сохранены: {output_file}")
    print("="*80)

if __name__ == "__main__":
    main()

