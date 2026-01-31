#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упрощенный тест Order Flow фильтра (третий фильтр)
Использует ту же логику, что и test_filters_before_baseline_simple.py
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

def simple_backtest_with_order_flow(df, symbol, order_flow_before_baseline=False):
    """Упрощенный бэктест с Order Flow фильтром"""
    from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter
    from config import USE_VP_FILTER, USE_VWAP_FILTER
    
    # Настраиваем фильтры
    os.environ['USE_VP_FILTER'] = 'True'
    os.environ['USE_VWAP_FILTER'] = 'True'
    os.environ['USE_ORDER_FLOW_FILTER'] = 'True'
    os.environ['DISABLE_EXTRA_FILTERS'] = 'false'
    os.environ['volume_profile_threshold'] = '0.6'
    os.environ['vwap_threshold'] = '0.8'
    
    # Проверяем Order Flow фильтр
    try:
        from src.filters.order_flow_filter import check_order_flow_filter
        order_flow_available = True
    except ImportError:
        order_flow_available = False
        logger.warning("Order Flow фильтр недоступен")
    
    df = add_technical_indicators(df)
    start_idx = 25
    
    if len(df) < start_idx:
        return {'trades': 0, 'return': 0.0, 'signals': 0}
    
    balance = START_BALANCE
    trades = []
    signals_generated = 0
    
    tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)
    
    from src.signals.core import soft_entry_signal
    import src.signals.core as core_module
    
    original_soft_entry = core_module.soft_entry_signal
    
    def enhanced_soft_entry_signal(df, i):
        """Модифицированная версия с Order Flow"""
        if i < 25:
            return None, None
        
        try:
            # 1. VP фильтр
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
            
            # 3. Order Flow фильтр (если перед baseline)
            if order_flow_before_baseline and order_flow_available:
                try:
                    of_ok, _ = check_order_flow_filter(df, i, "long", strict_mode=False)
                    if not of_ok:
                        return None, None
                except Exception as e:
                    logger.debug("Order Flow ошибка: %s", e)
                    # Если фильтр не работает, пропускаем его
                    pass
            
            # 4. Baseline условия
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
                # Если Order Flow после baseline - проверяем его здесь
                if not order_flow_before_baseline and order_flow_available:
                    try:
                        of_ok, _ = check_order_flow_filter(df, i, "long", strict_mode=False)
                        if not of_ok:
                            return None, None
                    except Exception as e:
                        logger.debug("Order Flow ошибка: %s", e)
                        # Если фильтр не работает, пропускаем его
                        pass
                
                return "long", current_price
            
            return None, None
        except Exception as e:
            logger.error("Ошибка: %s", e)
            return None, None
    
    core_module.soft_entry_signal = enhanced_soft_entry_signal
    
    try:
        for i in range(start_idx, len(df)):
            side, entry_price = soft_entry_signal(df, i)
            signals_generated += 1 if side else 0
            
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
                    exit_price = tp1
                    profit = (exit_price - entry_price) * position_size * (1 - FEE)
                    balance += profit
                    trades.append({
                        'entry': entry_price,
                        'exit': exit_price,
                        'side': side,
                        'profit': profit
                    })
    
        core_module.soft_entry_signal = original_soft_entry
        
        total_return = ((balance - START_BALANCE) / START_BALANCE) * 100
        
        return {
            'trades': len(trades),
            'return': total_return,
            'signals': signals_generated
        }
    except Exception as e:
        core_module.soft_entry_signal = original_soft_entry
        raise

def test_order_flow():
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
    
    total_after = {'trades': 0, 'return': 0.0, 'signals': 0}
    total_before = {'trades': 0, 'return': 0.0, 'signals': 0}
    
    for symbol in TEST_SYMBOLS:
        print(f"\n📊 Анализ {symbol}...")
        try:
            df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
            if df is None or len(df) < 25:
                print(f"   ❌ Недостаточно данных")
                continue
            
            after_result = simple_backtest_with_order_flow(df, symbol, order_flow_before_baseline=False)
            before_result = simple_backtest_with_order_flow(df, symbol, order_flow_before_baseline=True)
            
            for key in total_after:
                total_after[key] += after_result[key]
            
            for key in total_before:
                total_before[key] += before_result[key]
            
            print(f"   📈 ПОСЛЕ: {after_result['trades']} сделок, "
                  f"Return={after_result['return']:+.2f}% ({after_result['signals']} сигналов)")
            print(f"   🔵 ПЕРЕД: {before_result['trades']} сделок, "
                  f"Return={before_result['return']:+.2f}% ({before_result['signals']} сигналов)")
            
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("📊 ИТОГОВОЕ СРАВНЕНИЕ")
    print("="*80)
    print(f"📈 ORDER FLOW ПОСЛЕ baseline:")
    print(f"   Сделок: {total_after['trades']}, Return: {total_after['return']:+.2f}%")
    print(f"🔵 ORDER FLOW ПЕРЕД baseline:")
    print(f"   Сделок: {total_before['trades']}, Return: {total_before['return']:+.2f}%")
    print("="*80)
    
    return_diff = total_before['return'] - total_after['return']
    trades_diff = total_before['trades'] - total_after['trades']
    
    print(f"\n💡 АНАЛИЗ:")
    print(f"   Разница в Return: {return_diff:+.2f}%")
    print(f"   Разница в сделках: {trades_diff:+d}")
    
    if return_diff > 0:
        print("   ✅ Order Flow ПЕРЕД baseline ЛУЧШЕ!")
    elif return_diff < 0:
        print("   ✅ Order Flow ПОСЛЕ baseline ЛУЧШЕ!")
    else:
        print("   ⚠️ Результаты одинаковые")

if __name__ == "__main__":
    test_order_flow()

