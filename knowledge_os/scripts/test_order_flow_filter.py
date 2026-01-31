#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест Order Flow фильтра (третий фильтр)
Сравнение: после baseline vs перед baseline
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

def run_backtest_with_order_flow(df, symbol, order_flow_before_baseline=False):
    """Бэктест с Order Flow фильтром"""
    from src.signals.core import soft_entry_signal
    import src.signals.core as core_module
    
    # Настраиваем фильтры: VP и VWAP включены, Order Flow тоже
    os.environ['USE_VP_FILTER'] = 'True'
    os.environ['USE_VWAP_FILTER'] = 'True'
    os.environ['USE_ORDER_FLOW_FILTER'] = 'True'
    os.environ['DISABLE_EXTRA_FILTERS'] = 'false'  # Разрешаем Order Flow и другие
    
    # Для теста "перед baseline" - отключаем Order Flow из обычного потока
    if order_flow_before_baseline:
        os.environ['USE_ORDER_FLOW_FILTER'] = 'False'  # Отключаем в обычном потоке
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
    
    # Проверяем, есть ли функция check_order_flow_filter
    try:
        from src.filters.order_flow_filter import check_order_flow_filter
        order_flow_available = True
    except ImportError:
        try:
            from src.signals.filters import check_order_flow_filter
            order_flow_available = True
        except ImportError:
            try:
                from src.signals.filters_internal import check_order_flow_filter
                order_flow_available = True
            except ImportError:
                logger.warning("Order Flow фильтр не найден")
                order_flow_available = False
    
    df = add_technical_indicators(df)
    start_idx = 25
    
    if len(df) < start_idx:
        return {'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 
                'profit_factor': 0, 'total_return': 0, 'signals': 0, 
                'blocked_by_of': 0}
    
    balance = START_BALANCE
    trades = []
    signals_checked = 0
    signals_blocked_by_of = 0
    
    tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)
    
    # Сохраняем оригинальную функцию
    original_soft_entry = core_module.soft_entry_signal
    
    # Создаем модифицированную версию для "перед baseline"
    if order_flow_before_baseline and order_flow_available:
        def enhanced_soft_entry_signal(df, i):
            """Order Flow ПЕРЕД baseline"""
            if i < 25:
                return None, None
            
            try:
                # 1. VP фильтр
                from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter
                from config import USE_VP_FILTER, USE_VWAP_FILTER
                
                vp_ok = True
                if USE_VP_FILTER:
                    vp_ok, _ = check_volume_profile_filter(df, i, "long", strict_mode=False)
                    if not vp_ok:
                        return None, None
                
                # 2. VWAP фильтр
                vwap_ok = True
                if USE_VWAP_FILTER:
                    vwap_ok, _ = check_vwap_filter(df, i, "long", strict_mode=False)
                    if not vwap_ok:
                        return None, None
                
                # 3. Order Flow фильтр (ПЕРЕД baseline)
                of_ok = True
                if order_flow_available:
                    try:
                        from src.filters.order_flow_filter import check_order_flow_filter
                        of_ok, _ = check_order_flow_filter(df, i, "long", strict_mode=False)
                        if not of_ok:
                            return None, None
                    except Exception as e:
                        logger.debug("Order Flow фильтр ошибка: %s", e)
                        # Если фильтр не работает, пропускаем его
                        pass
                
                # 4. Baseline (ослабленный, так как все фильтры прошли)
                side, price = original_soft_entry(df, i)
                
                if side is None:
                    # Baseline не прошел - проверяем ослабленный baseline
                    current_price = df["close"].iloc[i]
                    bb_lower = df["bb_lower"].iloc[i]
                    bb_upper = df["bb_upper"].iloc[i]
                    ema7 = df["ema7"].iloc[i]
                    ema25 = df["ema25"].iloc[i]
                    rsi = df["rsi"].iloc[i]
                    volume_ratio = df["volume_ratio"].iloc[i]
                    volatility = df["volatility"].iloc[i]
                    momentum = df["momentum"].iloc[i]
                    trend_strength = df["trend_strength"].iloc[i]
                    
                    if (pd.isna(current_price) or pd.isna(bb_lower) or pd.isna(bb_upper) or 
                        pd.isna(ema7) or pd.isna(ema25)):
                        return None, None
                    
                    rsi = rsi if not pd.isna(rsi) else 50
                    volume_ratio = volume_ratio if not pd.isna(volume_ratio) else 1.0
                    volatility = volatility if not pd.isna(volatility) else 2.0
                    momentum = momentum if not pd.isna(momentum) else 0.0
                    trend_strength = trend_strength if not pd.isna(trend_strength) else 1.0
                    
                    adaptive_rsi_oversold = float(os.environ.get('ADAPTIVE_RSI_OVERSOLD', '60'))
                    adaptive_trend_strength = float(os.environ.get('ADAPTIVE_TREND_STRENGTH', '0.05'))
                    adaptive_momentum = float(os.environ.get('ADAPTIVE_MOMENTUM', '-10.0'))
                    
                    long_conditions = [
                        current_price <= bb_lower + (bb_upper - bb_lower) * 0.9,
                        ema7 >= ema25 * 0.85,
                        rsi < adaptive_rsi_oversold,
                        volume_ratio >= 0.3 * 0.8,
                        volatility > 0.05,
                        momentum >= adaptive_momentum,
                        trend_strength > adaptive_trend_strength,
                        True, True
                    ]
                    
                    # Ослабленный baseline (70% условий)
                    required_conditions = int(len(long_conditions) * 0.7)
                    long_base_ok = sum(long_conditions) >= required_conditions
                    
                    if long_base_ok:
                        return "long", current_price
                
                return side, price
            except Exception as e:
                logger.error("Ошибка в enhanced_soft_entry_signal: %s", e)
                return None, None
        
        # Заменяем функцию временно
        core_module.soft_entry_signal = enhanced_soft_entry_signal
    
    position = None
    
    try:
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
                
                if exit_price:
                    profit = (exit_price - position['entry_price']) * position['size']
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
                # Если Order Flow после baseline - проверяем его здесь
                if not order_flow_before_baseline and order_flow_available:
                    try:
                        from src.filters.order_flow_filter import check_order_flow_filter
                        of_ok, _ = check_order_flow_filter(df, i, "long", strict_mode=False)
                        if not of_ok:
                            signals_blocked_by_of += 1
                            continue
                    except Exception as e:
                        logger.debug("Order Flow фильтр ошибка: %s", e)
                        # Если фильтр не работает, пропускаем его
                        pass
            
            if side and entry_price:
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
        
        # Закрываем последнюю позицию
        if position and len(df) > 0:
            last_price = df["close"].iloc[-1]
            profit = (last_price - position['entry_price']) * position['size']
            profit_after_fee = profit * (1 - FEE)
            balance += profit_after_fee
            trades.append({
                'entry': position['entry_price'],
                'exit': last_price,
                'side': position['side'],
                'profit': profit_after_fee,
                'reason': 'END'
            })
    finally:
        # Восстанавливаем оригинальную функцию
        core_module.soft_entry_signal = original_soft_entry
    
    wins = sum(1 for t in trades if t['profit'] > 0)
    losses = sum(1 for t in trades if t['profit'] <= 0)
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
        'total_return': total_return,
        'signals_checked': signals_checked,
        'blocked_by_of': signals_blocked_by_of
    }

def test_order_flow_filter():
    """Тестирует Order Flow фильтр"""
    print("="*80)
    print("🔍 ТЕСТ ORDER FLOW ФИЛЬТРА (третий фильтр)")
    print("="*80)
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print("="*80)
    print()
    print("💡 ТЕСТИРУЕМ:")
    print("   1. Order Flow ПОСЛЕ baseline (VP+VWAP+baseline+OF)")
    print("   2. Order Flow ПЕРЕД baseline (VP+VWAP+OF+baseline)")
    print("="*80)
    print()
    
    total_after = {'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0,
                   'profit_factor': 0, 'total_return': 0, 'blocked': 0}
    total_before = {'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0,
                    'profit_factor': 0, 'total_return': 0, 'blocked': 0}
    
    for symbol in TEST_SYMBOLS:
        print(f"\n📊 Анализ {symbol}...")
        try:
            df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
            if df is None or len(df) < 25:
                print(f"   ❌ Недостаточно данных")
                continue
            
            # 1. Order Flow ПОСЛЕ baseline
            after_result = run_backtest_with_order_flow(df, symbol, order_flow_before_baseline=False)
            
            # 2. Order Flow ПЕРЕД baseline
            before_result = run_backtest_with_order_flow(df, symbol, order_flow_before_baseline=True)
            
            # Суммируем
            for key in total_after:
                if key in after_result:
                    total_after[key] += after_result[key]
            
            for key in total_before:
                if key in before_result:
                    total_before[key] += before_result[key]
            
            print(f"   📈 ПОСЛЕ baseline: {after_result['trades']} сделок, "
                  f"WR={after_result['win_rate']:.1f}%, PF={after_result['profit_factor']:.2f}, "
                  f"Return={after_result['total_return']:+.2f}% (заблокировано: {after_result['blocked_by_of']})")
            print(f"   🔵 ПЕРЕД baseline: {before_result['trades']} сделок, "
                  f"WR={before_result['win_rate']:.1f}%, PF={before_result['profit_factor']:.2f}, "
                  f"Return={before_result['total_return']:+.2f}%")
            
        except Exception as e:
            print(f"   ❌ Ошибка для {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Рассчитываем средние метрики
    after_win_rate = (total_after['wins'] / total_after['trades'] * 100) if total_after['trades'] > 0 else 0
    before_win_rate = (total_before['wins'] / total_before['trades'] * 100) if total_before['trades'] > 0 else 0
    
    print("\n" + "="*80)
    print("📊 ИТОГОВОЕ СРАВНЕНИЕ")
    print("="*80)
    print(f"📈 ORDER FLOW ПОСЛЕ baseline:")
    print(f"   Сделок: {total_after['trades']} (заблокировано: {total_after['blocked']})")
    print(f"   Win Rate: {after_win_rate:.1f}%")
    print(f"   Profit Factor: {total_after['profit_factor']:.2f}")
    print(f"   Total Return: {total_after['total_return']:+.2f}%")
    print()
    print(f"🔵 ORDER FLOW ПЕРЕД baseline:")
    print(f"   Сделок: {total_before['trades']}")
    print(f"   Win Rate: {before_win_rate:.1f}%")
    print(f"   Profit Factor: {total_before['profit_factor']:.2f}")
    print(f"   Total Return: {total_before['total_return']:+.2f}%")
    print("="*80)
    print()
    
    # Анализ
    return_diff = total_before['total_return'] - total_after['total_return']
    wr_diff = before_win_rate - after_win_rate
    trades_diff = total_before['trades'] - total_after['trades']
    
    print(f"💡 АНАЛИЗ:")
    print(f"   Разница в Return: {return_diff:+.2f}%")
    print(f"   Разница в Win Rate: {wr_diff:+.1f}%")
    print(f"   Разница в сделках: {trades_diff:+d}")
    print()
    
    if return_diff > 0 and wr_diff > 0:
        print("   ✅ Order Flow ПЕРЕД baseline ЛУЧШЕ!")
    elif return_diff < 0 and wr_diff < 0:
        print("   ✅ Order Flow ПОСЛЕ baseline ЛУЧШЕ!")
    else:
        print("   ⚠️ Результаты смешанные")
    
    return {
        'after_baseline': total_after,
        'before_baseline': total_before
    }

if __name__ == "__main__":
    test_order_flow_filter()

