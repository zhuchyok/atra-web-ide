#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование эффективности фильтров Momentum и Trend Strength
Сравнивает: baseline vs baseline + Momentum vs baseline + Trend Strength vs baseline + оба
"""

import os
import sys
from pathlib import Path
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_5coins_intelligent import (
    load_yearly_data, add_technical_indicators, 
    get_symbol_tp_sl_multipliers, START_BALANCE, FEE, RISK_PER_TRADE
)
from src.utils.shared_utils import get_dynamic_tp_levels
from src.signals.risk import get_dynamic_sl_level
from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter
from config import USE_VP_FILTER, USE_VWAP_FILTER
import logging
import pandas as pd

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
PERIOD_DAYS = 30  # Увеличиваем период для более точной оценки
MAX_WORKERS = 10

def run_backtest_with_filters(symbol, use_momentum, use_trend_strength):
    """Запускает бэктест с указанными фильтрами"""
    try:
        os.environ['USE_VP_FILTER'] = 'True'
        os.environ['USE_VWAP_FILTER'] = 'True'
        os.environ['USE_ORDER_FLOW_FILTER'] = 'False'
        os.environ['USE_MICROSTRUCTURE_FILTER'] = 'False'
        os.environ['USE_MOMENTUM_FILTER'] = 'True' if use_momentum else 'False'
        os.environ['USE_TREND_STRENGTH_FILTER'] = 'True' if use_trend_strength else 'False'
        os.environ['DISABLE_EXTRA_FILTERS'] = 'false'
        os.environ['volume_profile_threshold'] = '0.6'
        os.environ['vwap_threshold'] = '0.8'
        
        if 'src.signals.core' in sys.modules:
            del sys.modules['src.signals.core']
        if 'src.signals' in sys.modules:
            del sys.modules['src.signals']
        if 'config' in sys.modules:
            del sys.modules['config']
        
        from src.signals.core import soft_entry_signal
        
        df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
        if df is None or len(df) < 25:
            return {'trades': 0, 'return': 0.0, 'signals': 0}
        
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
                        'entry': entry_price,
                        'exit': exit_price,
                        'profit': profit,
                        'side': side
                    })
        
        total_return = ((balance - START_BALANCE) / START_BALANCE) * 100
        
        # Анализ качества сигналов
        winning_trades = [t for t in trades if t['profit'] > 0]
        losing_trades = [t for t in trades if t['profit'] < 0]
        win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0
        
        total_profit = sum(t['profit'] for t in winning_trades) if winning_trades else 0
        total_loss = abs(sum(t['profit'] for t in losing_trades)) if losing_trades else 0
        profit_factor = (total_profit / total_loss) if total_loss > 0 else (float('inf') if total_profit > 0 else 0)
        
        avg_profit_per_trade = (total_profit / len(trades)) if trades else 0
        avg_return_per_signal = (total_return / signals_generated) if signals_generated > 0 else 0
        
        return {
            'trades': len(trades),
            'return': total_return,
            'signals': signals_generated,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_profit_per_trade': avg_profit_per_trade,
            'avg_return_per_signal': avg_return_per_signal,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades)
        }
    except Exception as e:
        logger.error(f"Ошибка для {symbol}: {e}")
        return {'trades': 0, 'return': 0.0, 'signals': 0}

def test_filters():
    """Тестирует эффективность фильтров"""
    print("="*80)
    print("🔍 ТЕСТИРОВАНИЕ ФИЛЬТРОВ MOMENTUM И TREND STRENGTH")
    print("="*80)
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print(f"🧵 Потоков: {MAX_WORKERS}")
    print("="*80)
    print()
    
    test_configs = [
        {'name': 'Baseline (VP+VWAP)', 'momentum': False, 'trend': False},
        {'name': 'Baseline + Momentum', 'momentum': True, 'trend': False},
        {'name': 'Baseline + Trend Strength', 'momentum': False, 'trend': True},
        {'name': 'Baseline + Momentum + Trend', 'momentum': True, 'trend': True},
    ]
    
    all_results = {}
    
    total_tasks = len(test_configs) * len(TEST_SYMBOLS)
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        
        for config in test_configs:
            for symbol in TEST_SYMBOLS:
                future = executor.submit(
                    run_backtest_with_filters,
                    symbol,
                    config['momentum'],
                    config['trend']
                )
                futures.append((future, config['name'], symbol))
        
        with tqdm(total=total_tasks, desc="Тестирование конфигураций") as pbar:
            for future, config_name, symbol in futures:
                result = future.result()
                
                if config_name not in all_results:
                    all_results[config_name] = {
                        'symbols': {},
                        'total_trades': 0,
                        'total_return': 0.0,
                        'total_signals': 0
                    }
                
                all_results[config_name]['symbols'][symbol] = result
                all_results[config_name]['total_trades'] += result['trades']
                all_results[config_name]['total_return'] += result['return']
                all_results[config_name]['total_signals'] += result['signals']
                
                pbar.update(1)
    
    # Выводим результаты
    print("\n" + "="*80)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*80)
    print()
    
    baseline_result = all_results['Baseline (VP+VWAP)']
    
    for config_name, result in all_results.items():
        avg_return = result['total_return'] / len(TEST_SYMBOLS)
        blocked_signals = baseline_result['total_signals'] - result['total_signals']
        block_pct = (blocked_signals / baseline_result['total_signals'] * 100) if baseline_result['total_signals'] > 0 else 0
        
        # Собираем метрики качества (агрегируем по всем сделкам)
        total_winning = 0
        total_losing = 0
        total_profit = 0
        total_loss = 0
        total_trades_count = 0
        total_signals_count = 0
        total_return_sum = 0
        
        for symbol_result in result['symbols'].values():
            total_winning += symbol_result.get('winning_trades', 0)
            total_losing += symbol_result.get('losing_trades', 0)
            total_trades_count += symbol_result.get('trades', 0)
            total_signals_count += symbol_result.get('signals', 0)
            total_return_sum += symbol_result.get('return', 0)
        
        # Рассчитываем агрегированные метрики
        win_rate = (total_winning / total_trades_count * 100) if total_trades_count > 0 else 0
        
        # Для profit factor нужно собрать прибыли и убытки
        # Пока используем средние значения по символам
        total_profit_factor_sum = 0
        total_avg_profit_sum = 0
        count = 0
        for symbol_result in result['symbols'].values():
            if symbol_result['trades'] > 0:
                total_profit_factor_sum += symbol_result.get('profit_factor', 0)
                total_avg_profit_sum += symbol_result.get('avg_profit_per_trade', 0)
                count += 1
        
        avg_profit_factor = (total_profit_factor_sum / count) if count > 0 else 0
        avg_profit_per_trade = (total_avg_profit_sum / count) if count > 0 else 0
        avg_return_per_signal = (total_return_sum / total_signals_count) if total_signals_count > 0 else 0
        
        print(f"📊 {config_name}:")
        print(f"   Сигналов: {result['total_signals']}")
        if config_name != 'Baseline (VP+VWAP)':
            print(f"   Заблокировано: {blocked_signals} ({block_pct:.1f}%)")
        print(f"   Сделок: {result['total_trades']}")
        print(f"   Win Rate: {win_rate:.1f}% ({total_winning}/{total_trades_count})")
        print(f"   Profit Factor: {avg_profit_factor:.2f}")
        print(f"   Средняя прибыль/сделка: {avg_profit_per_trade:.2f} USDT")
        print(f"   Return/сигнал: {avg_return_per_signal:.2f}%")
        print(f"   Общий return: {result['total_return']:.2f}%")
        
        # Сравнение с baseline
        if config_name != 'Baseline (VP+VWAP)':
            # Собираем метрики baseline
            baseline_winning = 0
            baseline_losing = 0
            baseline_trades_count = 0
            baseline_signals_count = 0
            baseline_return_sum = 0
            baseline_profit_factor_sum = 0
            baseline_avg_profit_sum = 0
            baseline_count = 0
            
            for symbol_result in baseline_result['symbols'].values():
                baseline_winning += symbol_result.get('winning_trades', 0)
                baseline_losing += symbol_result.get('losing_trades', 0)
                baseline_trades_count += symbol_result.get('trades', 0)
                baseline_signals_count += symbol_result.get('signals', 0)
                baseline_return_sum += symbol_result.get('return', 0)
                if symbol_result['trades'] > 0:
                    baseline_profit_factor_sum += symbol_result.get('profit_factor', 0)
                    baseline_avg_profit_sum += symbol_result.get('avg_profit_per_trade', 0)
                    baseline_count += 1
            
            baseline_win_rate = (baseline_winning / baseline_trades_count * 100) if baseline_trades_count > 0 else 0
            baseline_avg_profit_factor = (baseline_profit_factor_sum / baseline_count) if baseline_count > 0 else 0
            baseline_avg_profit_per_trade = (baseline_avg_profit_sum / baseline_count) if baseline_count > 0 else 0
            baseline_avg_return_per_signal = (baseline_return_sum / baseline_signals_count) if baseline_signals_count > 0 else 0
            
            win_rate_diff = win_rate - baseline_win_rate
            profit_factor_diff = avg_profit_factor - baseline_avg_profit_factor
            profit_diff = avg_profit_per_trade - baseline_avg_profit_per_trade
            return_per_signal_diff = avg_return_per_signal - baseline_avg_return_per_signal
            
            print(f"   Изменение Win Rate: {win_rate_diff:+.1f}%")
            print(f"   Изменение Profit Factor: {profit_factor_diff:+.2f}")
            print(f"   Изменение прибыль/сделка: {profit_diff:+.2f} USDT")
            print(f"   Изменение return/сигнал: {return_per_signal_diff:+.2f}%")
        print()
    
    # Анализ эффективности
    print("="*80)
    print("💡 АНАЛИЗ ЭФФЕКТИВНОСТИ")
    print("="*80)
    print()
    
    momentum_result = all_results['Baseline + Momentum']
    trend_result = all_results['Baseline + Trend Strength']
    both_result = all_results['Baseline + Momentum + Trend']
    
    momentum_blocked = baseline_result['total_signals'] - momentum_result['total_signals']
    trend_blocked = baseline_result['total_signals'] - trend_result['total_signals']
    both_blocked = baseline_result['total_signals'] - both_result['total_signals']
    
    momentum_return_diff = momentum_result['total_return'] - baseline_result['total_return']
    trend_return_diff = trend_result['total_return'] - baseline_result['total_return']
    both_return_diff = both_result['total_return'] - baseline_result['total_return']
    
    # Собираем метрики качества для анализа
    def get_quality_metrics(result_dict):
        total_winning = 0
        total_losing = 0
        total_trades_count = 0
        total_signals_count = 0
        total_return_sum = 0
        total_profit_factor_sum = 0
        total_avg_profit_sum = 0
        count = 0
        
        for symbol_result in result_dict['symbols'].values():
            total_winning += symbol_result.get('winning_trades', 0)
            total_losing += symbol_result.get('losing_trades', 0)
            total_trades_count += symbol_result.get('trades', 0)
            total_signals_count += symbol_result.get('signals', 0)
            total_return_sum += symbol_result.get('return', 0)
            if symbol_result['trades'] > 0:
                total_profit_factor_sum += symbol_result.get('profit_factor', 0)
                total_avg_profit_sum += symbol_result.get('avg_profit_per_trade', 0)
                count += 1
        
        return {
            'win_rate': (total_winning / total_trades_count * 100) if total_trades_count > 0 else 0,
            'profit_factor': (total_profit_factor_sum / count) if count > 0 else 0,
            'avg_profit': (total_avg_profit_sum / count) if count > 0 else 0,
            'return_per_signal': (total_return_sum / total_signals_count) if total_signals_count > 0 else 0,
            'winning_trades': total_winning,
            'losing_trades': total_losing,
            'total_trades': total_trades_count
        }
    
    baseline_metrics = get_quality_metrics(baseline_result)
    momentum_metrics = get_quality_metrics(momentum_result)
    trend_metrics = get_quality_metrics(trend_result)
    both_metrics = get_quality_metrics(both_result)
    
    print(f"🔵 MOMENTUM ФИЛЬТР:")
    print(f"   Блокирует: {momentum_blocked} сигналов ({(momentum_blocked/baseline_result['total_signals']*100) if baseline_result['total_signals'] > 0 else 0:.1f}%)")
    print(f"   Сделок: {baseline_metrics['total_trades']} → {momentum_metrics['total_trades']} ({momentum_metrics['total_trades'] - baseline_metrics['total_trades']:+d})")
    print(f"   Win Rate: {baseline_metrics['win_rate']:.1f}% → {momentum_metrics['win_rate']:.1f}% ({momentum_metrics['win_rate'] - baseline_metrics['win_rate']:+.1f}%)")
    print(f"   Прибыльных/Убыточных: {baseline_metrics['winning_trades']}/{baseline_metrics['losing_trades']} → {momentum_metrics['winning_trades']}/{momentum_metrics['losing_trades']}")
    print(f"   Profit Factor: {baseline_metrics['profit_factor']:.2f} → {momentum_metrics['profit_factor']:.2f} ({momentum_metrics['profit_factor'] - baseline_metrics['profit_factor']:+.2f})")
    print(f"   Return/сигнал: {baseline_metrics['return_per_signal']:.2f}% → {momentum_metrics['return_per_signal']:.2f}% ({momentum_metrics['return_per_signal'] - baseline_metrics['return_per_signal']:+.2f}%)")
    
    # Правильная оценка: фильтр хорош, если улучшает качество (Win Rate, Profit Factor, Return/сигнал)
    improvements = []
    if momentum_metrics['win_rate'] > baseline_metrics['win_rate']:
        improvements.append(f"Win Rate +{momentum_metrics['win_rate'] - baseline_metrics['win_rate']:.1f}%")
    if momentum_metrics['profit_factor'] > baseline_metrics['profit_factor']:
        improvements.append(f"Profit Factor +{momentum_metrics['profit_factor'] - baseline_metrics['profit_factor']:.2f}")
    if momentum_metrics['return_per_signal'] > baseline_metrics['return_per_signal']:
        improvements.append(f"Return/сигнал +{momentum_metrics['return_per_signal'] - baseline_metrics['return_per_signal']:.2f}%")
    
    if improvements:
        print(f"   ✅ Улучшает качество: {', '.join(improvements)}")
    elif momentum_blocked > 0:
        print(f"   ⚠️ Блокирует сигналы, но не улучшает качество (возможно, блокирует прибыльные)")
    else:
        print(f"   ⚠️ Не блокирует сигналы (слишком мягкий)")
    print()
    
    print(f"🟢 TREND STRENGTH ФИЛЬТР:")
    print(f"   Блокирует: {trend_blocked} сигналов ({(trend_blocked/baseline_result['total_signals']*100) if baseline_result['total_signals'] > 0 else 0:.1f}%)")
    print(f"   Сделок: {baseline_metrics['total_trades']} → {trend_metrics['total_trades']} ({trend_metrics['total_trades'] - baseline_metrics['total_trades']:+d})")
    print(f"   Win Rate: {baseline_metrics['win_rate']:.1f}% → {trend_metrics['win_rate']:.1f}% ({trend_metrics['win_rate'] - baseline_metrics['win_rate']:+.1f}%)")
    print(f"   Прибыльных/Убыточных: {baseline_metrics['winning_trades']}/{baseline_metrics['losing_trades']} → {trend_metrics['winning_trades']}/{trend_metrics['losing_trades']}")
    print(f"   Profit Factor: {baseline_metrics['profit_factor']:.2f} → {trend_metrics['profit_factor']:.2f} ({trend_metrics['profit_factor'] - baseline_metrics['profit_factor']:+.2f})")
    print(f"   Return/сигнал: {baseline_metrics['return_per_signal']:.2f}% → {trend_metrics['return_per_signal']:.2f}% ({trend_metrics['return_per_signal'] - baseline_metrics['return_per_signal']:+.2f}%)")
    
    improvements = []
    if trend_metrics['win_rate'] > baseline_metrics['win_rate']:
        improvements.append(f"Win Rate +{trend_metrics['win_rate'] - baseline_metrics['win_rate']:.1f}%")
    if trend_metrics['profit_factor'] > baseline_metrics['profit_factor']:
        improvements.append(f"Profit Factor +{trend_metrics['profit_factor'] - baseline_metrics['profit_factor']:.2f}")
    if trend_metrics['return_per_signal'] > baseline_metrics['return_per_signal']:
        improvements.append(f"Return/сигнал +{trend_metrics['return_per_signal'] - baseline_metrics['return_per_signal']:.2f}%")
    
    if improvements:
        print(f"   ✅ Улучшает качество: {', '.join(improvements)}")
        print(f"   💡 Фильтр работает: отсекает убыточные сделки!")
    elif trend_blocked > 0:
        print(f"   ⚠️ Блокирует сигналы, но не улучшает качество (возможно, блокирует прибыльные)")
    else:
        print(f"   ⚠️ Не блокирует сигналы (слишком мягкий)")
    print()
    
    print(f"🟣 ОБА ФИЛЬТРА:")
    print(f"   Блокируют: {both_blocked} сигналов ({(both_blocked/baseline_result['total_signals']*100) if baseline_result['total_signals'] > 0 else 0:.1f}%)")
    print(f"   Сделок: {baseline_metrics['total_trades']} → {both_metrics['total_trades']} ({both_metrics['total_trades'] - baseline_metrics['total_trades']:+d})")
    print(f"   Win Rate: {baseline_metrics['win_rate']:.1f}% → {both_metrics['win_rate']:.1f}% ({both_metrics['win_rate'] - baseline_metrics['win_rate']:+.1f}%)")
    print(f"   Прибыльных/Убыточных: {baseline_metrics['winning_trades']}/{baseline_metrics['losing_trades']} → {both_metrics['winning_trades']}/{both_metrics['losing_trades']}")
    print(f"   Profit Factor: {baseline_metrics['profit_factor']:.2f} → {both_metrics['profit_factor']:.2f} ({both_metrics['profit_factor'] - baseline_metrics['profit_factor']:+.2f})")
    print(f"   Return/сигнал: {baseline_metrics['return_per_signal']:.2f}% → {both_metrics['return_per_signal']:.2f}% ({both_metrics['return_per_signal'] - baseline_metrics['return_per_signal']:+.2f}%)")
    
    improvements = []
    if both_metrics['win_rate'] > baseline_metrics['win_rate']:
        improvements.append(f"Win Rate +{both_metrics['win_rate'] - baseline_metrics['win_rate']:.1f}%")
    if both_metrics['profit_factor'] > baseline_metrics['profit_factor']:
        improvements.append(f"Profit Factor +{both_metrics['profit_factor'] - baseline_metrics['profit_factor']:.2f}")
    if both_metrics['return_per_signal'] > baseline_metrics['return_per_signal']:
        improvements.append(f"Return/сигнал +{both_metrics['return_per_signal'] - baseline_metrics['return_per_signal']:.2f}%")
    
    if improvements:
        print(f"   ✅ Улучшают качество: {', '.join(improvements)}")
        print(f"   💡 Фильтры работают: отсекают убыточные сделки!")
    elif both_blocked > 0:
        print(f"   ⚠️ Блокируют сигналы, но не улучшают качество (возможно, блокируют прибыльные)")
    else:
        print(f"   ⚠️ Не блокируют сигналы (слишком мягкие)")
    print()
    
    # Сохраняем результаты
    output_file = 'backtests/momentum_trend_strength_test_results.json'
    os.makedirs('backtests', exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Результаты сохранены в: {output_file}")
    print("="*80)

if __name__ == "__main__":
    test_filters()

