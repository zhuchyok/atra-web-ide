#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест качества сигналов: сравнивает baseline vs VP фильтр
Проверяет, улучшает ли VP фильтр качество (Win Rate, Profit Factor), 
даже если блокирует мало сигналов
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_5coins_intelligent import (
    load_yearly_data, add_technical_indicators, 
    get_symbol_tp_sl_multipliers, START_BALANCE, FEE, RISK_PER_TRADE
)
from src.utils.shared_utils import get_dynamic_tp_levels
from src.signals.risk import get_dynamic_sl_level
import logging
import pandas as pd

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
PERIOD_DAYS = 7

def run_simple_backtest(df, symbol, use_vp_filter=False, use_vwap_filter=False):
    """Упрощенный бэктест для сравнения качества"""
    from src.signals.core import soft_entry_signal
    from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter
    from config import USE_VP_FILTER, USE_VWAP_FILTER
    
    # Настраиваем фильтры
    os.environ['USE_VP_FILTER'] = 'True' if use_vp_filter else 'False'
    os.environ['USE_VWAP_FILTER'] = 'True' if use_vwap_filter else 'False'
    os.environ['DISABLE_EXTRA_FILTERS'] = 'true'
    os.environ['volume_profile_threshold'] = '0.6'
    os.environ['vwap_threshold'] = '0.8'
    
    # Очищаем кэш
    if 'src.signals.core' in sys.modules:
        del sys.modules['src.signals.core']
    if 'src.signals' in sys.modules:
        del sys.modules['src.signals']
    if 'config' in sys.modules:
        del sys.modules['config']
    
    from src.signals.core import soft_entry_signal
    
    df = add_technical_indicators(df)
    start_idx = 25
    
    if len(df) < start_idx:
        return {'trades': 0, 'wins': 0, 'losses': 0, 'total_profit': 0.0, 'signals': 0}
    
    balance = START_BALANCE
    trades = []
    signals_checked = 0
    signals_blocked_by_vp = 0
    signals_blocked_by_vwap = 0
    
    tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)
    
    position = None
    
    for i in range(start_idx, len(df)):
        current_price = df["close"].iloc[i]
        current_time = df.index[i]
        
        # Проверяем выход из позиции
        if position:
            exit_price = None
            exit_reason = None
            
            if position['side'] == 'long':
                if current_price >= position['tp1']:
                    exit_price = position['tp1']
                    exit_reason = 'TP1'
                elif current_price <= position['sl']:
                    exit_price = position['sl']
                    exit_reason = 'SL'
            else:  # short
                if current_price <= position['tp1']:
                    exit_price = position['tp1']
                    exit_reason = 'TP1'
                elif current_price >= position['sl']:
                    exit_price = position['sl']
                    exit_reason = 'SL'
            
            if exit_price:
                profit = (exit_price - position['entry_price']) * position['size']
                if position['side'] == 'short':
                    profit = -profit
                
                profit_after_fee = profit * (1 - FEE)
                balance += profit_after_fee
                
                trades.append({
                    'entry': position['entry_price'],
                    'exit': exit_price,
                    'side': position['side'],
                    'profit': profit_after_fee,
                    'reason': exit_reason
                })
                position = None
        
        # Проверяем сигнал входа
        side, entry_price = soft_entry_signal(df, i)
        signals_checked += 1
        
        if side and entry_price:
            # Проверяем фильтры (если включены)
            vp_ok = True
            vwap_ok = True
            
            if use_vp_filter:
                vp_ok, vp_reason = check_volume_profile_filter(df, i, "long", strict_mode=False)
                if not vp_ok:
                    signals_blocked_by_vp += 1
                    continue  # Пропускаем сигнал
            
            if use_vwap_filter and vp_ok:
                vwap_ok, vwap_reason = check_vwap_filter(df, i, "long", strict_mode=False)
                if not vwap_ok:
                    signals_blocked_by_vwap += 1
                    continue  # Пропускаем сигнал
            
            # Если фильтры прошли (или не включены) - открываем позицию
            if vp_ok and vwap_ok:
                tp1_pct, tp2_pct = get_dynamic_tp_levels(df, i, side)
                tp1 = entry_price * (1 + tp1_pct / 100 * tp_mult)
                tp2 = entry_price * (1 + tp2_pct / 100 * tp_mult)
                
                sl_level_pct = get_dynamic_sl_level(df, i, side)
                if side == 'long':
                    sl_level = entry_price * (1 - sl_level_pct / 100 * sl_mult)
                else:
                    sl_level = entry_price * (1 + sl_level_pct / 100 * sl_mult)
                
                risk_amount = balance * RISK_PER_TRADE
                sl_distance = abs(entry_price - sl_level)
                
                if sl_distance > 0:
                    position_size = risk_amount / sl_distance
                    position = {
                        'side': side,
                        'entry_price': entry_price,
                        'size': position_size,
                        'tp1': tp1,
                        'tp2': tp2,
                        'sl': sl_level,
                        'entry_time': current_time
                    }
    
    # Закрываем последнюю позицию если есть
    if position and len(df) > 0:
        last_price = df["close"].iloc[-1]
        profit = (last_price - position['entry_price']) * position['size']
        if position['side'] == 'short':
            profit = -profit
        profit_after_fee = profit * (1 - FEE)
        balance += profit_after_fee
        trades.append({
            'entry': position['entry_price'],
            'exit': last_price,
            'side': position['side'],
            'profit': profit_after_fee,
            'reason': 'END'
        })
    
    wins = sum(1 for t in trades if t['profit'] > 0)
    losses = sum(1 for t in trades if t['profit'] <= 0)
    total_profit = sum(t['profit'] for t in trades)
    win_rate = (wins / len(trades) * 100) if trades else 0
    
    profit_factor = 0
    if losses > 0:
        total_wins = sum(t['profit'] for t in trades if t['profit'] > 0)
        total_losses = abs(sum(t['profit'] for t in trades if t['profit'] <= 0))
        if total_losses > 0:
            profit_factor = total_wins / total_losses
    
    total_return = ((balance - START_BALANCE) / START_BALANCE) * 100
    
    return {
        'trades': len(trades),
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_profit': total_profit,
        'total_return': total_return,
        'signals_checked': signals_checked,
        'signals_blocked_by_vp': signals_blocked_by_vp,
        'signals_blocked_by_vwap': signals_blocked_by_vwap
    }

def test_vp_filter_quality():
    """Тестирует качество сигналов с VP фильтром"""
    print("="*80)
    print("🔍 АНАЛИЗ КАЧЕСТВА СИГНАЛОВ: Baseline vs VP фильтр")
    print("="*80)
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print("="*80)
    print()
    
    total_baseline = {'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 
                      'profit_factor': 0, 'total_return': 0, 'signals': 0}
    total_vp = {'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0,
                'profit_factor': 0, 'total_return': 0, 'signals': 0, 'blocked': 0}
    
    for symbol in TEST_SYMBOLS:
        print(f"\n📊 Анализ {symbol}...")
        try:
            df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
            if df is None or len(df) < 25:
                print(f"   ❌ Недостаточно данных")
                continue
            
            # Baseline (без фильтров)
            baseline = run_simple_backtest(df, symbol, use_vp_filter=False, use_vwap_filter=False)
            
            # С VP фильтром
            vp_result = run_simple_backtest(df, symbol, use_vp_filter=True, use_vwap_filter=False)
            
            # Суммируем
            for key in total_baseline:
                if key in baseline:
                    total_baseline[key] += baseline[key]
            
            for key in total_vp:
                if key in vp_result:
                    total_vp[key] += vp_result[key]
            
            print(f"   📈 Baseline: {baseline['trades']} сделок, WR={baseline['win_rate']:.1f}%, "
                  f"PF={baseline['profit_factor']:.2f}, Return={baseline['total_return']:+.2f}%")
            print(f"   🔵 С VP: {vp_result['trades']} сделок, WR={vp_result['win_rate']:.1f}%, "
                  f"PF={vp_result['profit_factor']:.2f}, Return={vp_result['total_return']:+.2f}% "
                  f"(заблокировано: {vp_result['signals_blocked_by_vp']})")
            
        except Exception as e:
            print(f"   ❌ Ошибка для {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Рассчитываем средние метрики
    baseline_win_rate = (total_baseline['wins'] / total_baseline['trades'] * 100) if total_baseline['trades'] > 0 else 0
    vp_win_rate = (total_vp['wins'] / total_vp['trades'] * 100) if total_vp['trades'] > 0 else 0
    
    baseline_pf = 0
    if total_baseline['losses'] > 0:
        total_wins = sum(1 for _ in range(total_baseline['wins']))
        # Упрощенно - используем средний PF
        baseline_pf = total_baseline['profit_factor'] / len(TEST_SYMBOLS) if len(TEST_SYMBOLS) > 0 else 0
    
    vp_pf = total_vp['profit_factor'] / len(TEST_SYMBOLS) if len(TEST_SYMBOLS) > 0 else 0
    
    print("\n" + "="*80)
    print("📊 ИТОГОВОЕ СРАВНЕНИЕ")
    print("="*80)
    print(f"📈 BASELINE (без фильтров):")
    print(f"   Сделок: {total_baseline['trades']}")
    print(f"   Win Rate: {baseline_win_rate:.1f}%")
    print(f"   Profit Factor: {baseline_pf:.2f}")
    print(f"   Total Return: {total_baseline['total_return']:+.2f}%")
    print()
    print(f"🔵 С VOLUME PROFILE ФИЛЬТРОМ:")
    print(f"   Сделок: {total_vp['trades']} (заблокировано: {total_vp['blocked']})")
    print(f"   Win Rate: {vp_win_rate:.1f}%")
    print(f"   Profit Factor: {vp_pf:.2f}")
    print(f"   Total Return: {total_vp['total_return']:+.2f}%")
    print("="*80)
    print()
    
    # Анализ улучшения
    win_rate_improvement = vp_win_rate - baseline_win_rate
    pf_improvement = vp_pf - baseline_pf
    return_improvement = total_vp['total_return'] - total_baseline['total_return']
    
    print(f"💡 АНАЛИЗ УЛУЧШЕНИЯ:")
    print(f"   Win Rate: {win_rate_improvement:+.1f}%")
    print(f"   Profit Factor: {pf_improvement:+.2f}")
    print(f"   Total Return: {return_improvement:+.2f}%")
    print()
    
    if win_rate_improvement > 0 or pf_improvement > 0 or return_improvement > 0:
        print("   ✅ VP фильтр УЛУЧШАЕТ качество сигналов!")
        print(f"   💡 Даже блокируя {total_vp['blocked']} сигналов, фильтр отсекает убыточные сделки")
    else:
        print("   ⚠️ VP фильтр НЕ улучшает качество сигналов")
        print("   💡 Заблокированные сигналы были не хуже остальных")
    
    return {
        'baseline': total_baseline,
        'vp': total_vp,
        'improvements': {
            'win_rate': win_rate_improvement,
            'profit_factor': pf_improvement,
            'return': return_improvement
        }
    }

if __name__ == "__main__":
    test_vp_filter_quality()

