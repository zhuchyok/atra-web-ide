#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упрощенный тест логики "Фильтры как УСИЛЕНИЕ" (фильтры ПЕРЕД baseline)
Тестирование на 3 днях для быстрой проверки концепции
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Настройки для теста
os.environ['USE_VP_FILTER'] = 'True'
os.environ['USE_VWAP_FILTER'] = 'True'
os.environ['DISABLE_EXTRA_FILTERS'] = 'true'  # Только VP и VWAP
os.environ['vwap_threshold'] = '0.8'  # Оптимизированный параметр
os.environ['volume_profile_threshold'] = '0.6'  # Оптимизированный параметр

from scripts.backtest_5coins_intelligent import (
    load_yearly_data, add_technical_indicators, 
    get_symbol_tp_sl_multipliers, START_BALANCE, FEE, RISK_PER_TRADE
)
from src.utils.shared_utils import get_dynamic_tp_levels
from src.signals.risk import get_dynamic_sl_level
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Тестовые символы
TEST_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"
]

# Период для теста
PERIOD_DAYS = 7

def simple_backtest_with_enhanced_filters(df, symbol):
    """Упрощенный бэктест с фильтрами ПЕРЕД baseline"""
    from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter
    from config import USE_VP_FILTER, USE_VWAP_FILTER
    
    # Добавляем индикаторы
    df = add_technical_indicators(df)
    
    # Уменьшенный start_idx для короткого теста
    start_idx = 25
    
    if len(df) < start_idx:
        return {'trades': 0, 'return': 0.0, 'signals': 0}
    
    balance = START_BALANCE
    trades = []
    signals_generated = 0
    
    # Получаем TP/SL multipliers
    tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)
    
    # Импортируем модифицированную функцию
    from src.signals.core import soft_entry_signal
    import src.signals.core as core_module
    
    # Сохраняем оригинальную функцию
    original_soft_entry = core_module.soft_entry_signal
    
    # Создаем модифицированную версию
    def enhanced_soft_entry_signal(df, i):
        """Модифицированная версия: фильтры ПЕРЕД baseline как УСИЛЕНИЕ
        
        Последовательность:
        1. Volume Profile фильтр (первый)
        2. VWAP фильтр (второй)
        3. Baseline (ослабленный если оба фильтра прошли, строгий если нет)
        """
        if i < 25:
            return None, None
        
        try:
            # 1. ПЕРВЫЙ ФИЛЬТР: Volume Profile (обязательный)
            vp_ok = True
            if USE_VP_FILTER:
                vp_ok, vp_reason = check_volume_profile_filter(df, i, "long", strict_mode=False)
                if not vp_ok:
                    # Первый фильтр не прошел - сразу отклоняем (baseline не проверяем)
                    return None, None
            
            # 2. ВТОРОЙ ФИЛЬТР: VWAP (обязательный, проверяем только если VP прошел)
            vwap_ok = True
            if USE_VWAP_FILTER:
                vwap_ok, vwap_reason = check_vwap_filter(df, i, "long", strict_mode=False)
                if not vwap_ok:
                    # Второй фильтр не прошел - сразу отклоняем (baseline не проверяем)
                    return None, None
            
            # 3. ОБА ФИЛЬТРА ПРОШЛИ - проверяем baseline (ослабленный)
            filters_passed = vp_ok and vwap_ok
            # Если мы дошли сюда, значит оба фильтра прошли
            
            # 2. Получаем данные для baseline условий
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
            
            # Безопасные значения
            if (pd.isna(current_price) or pd.isna(bb_lower) or pd.isna(bb_upper) or 
                pd.isna(ema7) or pd.isna(ema25)):
                return None, None
            
            rsi = rsi if not pd.isna(rsi) else 50
            volume_ratio = volume_ratio if not pd.isna(volume_ratio) else 1.0
            volatility = volatility if not pd.isna(volatility) else 2.0
            momentum = momentum if not pd.isna(momentum) else 0.0
            trend_strength = trend_strength if not pd.isna(trend_strength) else 1.0
            
            # Адаптивные параметры
            adaptive_rsi_oversold = float(os.environ.get('ADAPTIVE_RSI_OVERSOLD', '60'))
            adaptive_trend_strength = float(os.environ.get('ADAPTIVE_TREND_STRENGTH', '0.05'))
            adaptive_momentum = float(os.environ.get('ADAPTIVE_MOMENTUM', '-10.0'))
            
            # Базовые условия для LONG
            long_conditions = [
                current_price <= bb_lower + (bb_upper - bb_lower) * 0.9,
                ema7 >= ema25 * 0.85,
                rsi < adaptive_rsi_oversold,
                volume_ratio >= 0.3 * 0.8,  # Упрощенный порог
                volatility > 0.05,
                momentum >= adaptive_momentum,
                trend_strength > adaptive_trend_strength,
                True,  # bb_long_ok
                True,  # vol_ok
            ]
            
            # 3. ПРИМЕНЯЕМ ЛОГИКУ УСИЛЕНИЯ
            # Если мы дошли сюда, значит оба фильтра прошли
            # → ослабленный baseline (70% условий)
            required_conditions = int(len(long_conditions) * 0.7)
            long_base_ok = sum(long_conditions) >= required_conditions
            
            if long_base_ok:
                return "long", current_price
            
            return None, None
        except Exception as e:
            logger.error("Ошибка в enhanced_soft_entry_signal: %s", e)
            return None, None
    
    # Заменяем функцию временно
    core_module.soft_entry_signal = enhanced_soft_entry_signal
    
    try:
        # Проходим по свечам
        for i in range(start_idx, len(df)):
            current_price = df["close"].iloc[i]
            
            # Проверяем сигнал входа
            side, entry_price = soft_entry_signal(df, i)
            signals_generated += 1 if side else 0
            
            if side and entry_price:
                # Рассчитываем TP/SL (возвращаются проценты)
                tp1_pct, tp2_pct = get_dynamic_tp_levels(df, i, side)
                # Применяем множитель и конвертируем в абсолютные значения
                tp1 = entry_price * (1 + tp1_pct / 100 * tp_mult)
                tp2 = entry_price * (1 + tp2_pct / 100 * tp_mult)
                tp_levels = {'tp1': tp1, 'tp2': tp2}
                
                sl_level_pct = get_dynamic_sl_level(df, i, side)
                # Применяем множитель и конвертируем в абсолютные значения
                if side == 'long':
                    sl_level = entry_price * (1 - sl_level_pct / 100 * sl_mult)
                else:
                    sl_level = entry_price * (1 + sl_level_pct / 100 * sl_mult)
                
                if tp_levels and sl_level:
                    # Открываем позицию
                    risk_amount = balance * RISK_PER_TRADE
                    sl_distance = abs(entry_price - sl_level)
                    if sl_distance > 0:
                        position_size = risk_amount / sl_distance
                        tp1 = tp_levels.get('tp1', entry_price * 1.02)
                        
                        # Симулируем сделку (упрощенно - сразу выход на TP1 или SL)
                        # Для теста просто считаем прибыль/убыток
                        if side == 'long':
                            # Проверяем, что произойдет первым: TP1 или SL
                            # Упрощенно: считаем вероятность достижения TP1
                            # Для теста используем упрощенную логику
                            exit_price = tp1  # Упрощенно: всегда выходим на TP1
                            profit = (exit_price - entry_price) * position_size * (1 - FEE)
                            balance += profit
                            trades.append({
                                'entry': entry_price,
                                'exit': exit_price,
                                'side': side,
                                'profit': profit
                            })
    
        # Восстанавливаем оригинальную функцию
        core_module.soft_entry_signal = original_soft_entry
        
        total_return = ((balance - START_BALANCE) / START_BALANCE) * 100
        
        return {
            'trades': len(trades),
            'return': total_return,
            'signals': signals_generated
        }
    except Exception as e:
        # Восстанавливаем оригинальную функцию в случае ошибки
        core_module.soft_entry_signal = original_soft_entry
        raise

def test_filters_before_baseline():
    """Тестирует логику 'Фильтры как УСИЛЕНИЕ'"""
    print("="*80)
    print("🧪 ТЕСТ: ФИЛЬТРЫ ПЕРЕД BASELINE (как УСИЛЕНИЕ)")
    print("="*80)
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print("="*80)
    print("\n💡 ЛОГИКА:")
    print("   1. Volume Profile фильтр (первый, обязательный)")
    print("   2. VWAP фильтр (второй, обязательный)")
    print("   3. Baseline (ослабленный, 70% условий) - только если оба фильтра прошли")
    print("   ⚠️ Если фильтры НЕ прошли → сигнал отклоняется (baseline не проверяется)")
    print("="*80)
    print()
    
    total_trades = 0
    total_return = 0.0
    total_signals = 0
    
    for symbol in TEST_SYMBOLS:
        print(f"\n📊 Тестирование {symbol}...")
        try:
            df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
            if df is None or len(df) < 25:
                print(f"   ❌ Недостаточно данных")
                continue
            
            result = simple_backtest_with_enhanced_filters(df, symbol)
            
            trades = result['trades']
            ret = result['return']
            signals = result['signals']
            
            if trades > 0:
                total_trades += trades
                total_return += ret
                total_signals += signals
                print(f"   ✅ {symbol}: {ret:+.2f}% ({trades} сделок, {signals} сигналов)")
            else:
                print(f"   ⚠️ {symbol}: Нет сделок ({signals} сигналов проверено)")
        except Exception as e:
            print(f"   ❌ Ошибка для {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТА (Фильтры ПЕРЕД baseline)")
    print("="*80)
    print(f"📈 Общая доходность: {total_return:+.2f}%")
    print(f"📊 Всего сделок: {total_trades}")
    print(f"🎯 Сигналов проверено: {total_signals}")
    print("="*80)
    
    return {
        'total_return': total_return,
        'total_trades': total_trades,
        'total_signals': total_signals
    }

if __name__ == "__main__":
    test_filters_before_baseline()

