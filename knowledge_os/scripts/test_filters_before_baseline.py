#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест логики "Фильтры как УСИЛЕНИЕ" (фильтры ПЕРЕД baseline)
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

from scripts.backtest_5coins_intelligent import load_yearly_data, run_backtest
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Тестовые символы
TEST_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"
]

# Период для теста
PERIOD_DAYS = 3

def test_filters_before_baseline():
    """Тестирует логику 'Фильтры как УСИЛЕНИЕ'"""
    print("="*80)
    print("🧪 ТЕСТ: ФИЛЬТРЫ ПЕРЕД BASELINE (как УСИЛЕНИЕ)")
    print("="*80)
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print("="*80)
    print("\n💡 ЛОГИКА:")
    print("   - Фильтры проверяются ПЕРЕД baseline")
    print("   - Если фильтры прошли → ослабленный baseline (70% условий)")
    print("   - Если фильтры НЕ прошли → строгий baseline (100% условий)")
    print("="*80)
    print()
    
    # Импортируем и модифицируем soft_entry_signal
    from src.signals.core import soft_entry_signal
    import src.signals.core as core_module
    
    # Сохраняем оригинальную функцию
    original_soft_entry = core_module.soft_entry_signal
    
    # Создаем модифицированную версию с фильтрами ПЕРЕД baseline
    def enhanced_soft_entry_signal(df, i):
        """Модифицированная версия: фильтры ПЕРЕД baseline как УСИЛЕНИЕ"""
        from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter
        from config import USE_VP_FILTER, USE_VWAP_FILTER
        import pandas as pd
        
        if i < 25:
            return None, None
        
        try:
            # 1. ПРОВЕРЯЕМ ФИЛЬТРЫ ПЕРЕД BASELINE
            vp_ok = True
            vwap_ok = True
            
            if USE_VP_FILTER:
                vp_ok, _ = check_volume_profile_filter(df, i, "long", strict_mode=False)
            
            if USE_VWAP_FILTER:
                vwap_ok, _ = check_vwap_filter(df, i, "long", strict_mode=False)
            
            filters_passed = vp_ok and vwap_ok
            
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
            if filters_passed:
                # Фильтры прошли → ослабленный baseline (70% условий)
                required_conditions = int(len(long_conditions) * 0.7)
                long_base_ok = sum(long_conditions) >= required_conditions
            else:
                # Фильтры НЕ прошли → строгий baseline (100% условий)
                long_base_ok = all(long_conditions)
            
            if long_base_ok:
                return "long", current_price
            
            return None, None
        except Exception as e:
            logger.error("Ошибка в enhanced_soft_entry_signal: %s", e)
            return None, None
    
    
    # Заменяем функцию временно
    core_module.soft_entry_signal = enhanced_soft_entry_signal
    
    try:
        total_trades = 0
        total_return = 0.0
        
        for symbol in TEST_SYMBOLS:
            print(f"\n📊 Тестирование {symbol}...")
            try:
                df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
                if df is None or len(df) < 25:  # Минимум для индикаторов
                    print(f"   ❌ Недостаточно данных (нужно минимум 25 свечей)")
                    continue
                
                # Используем упрощенный бэктест для короткого периода
                # Модифицируем start_idx через monkey patching
                import scripts.backtest_5coins_intelligent as bt_module
                
                # Сохраняем оригинальную функцию
                original_run_backtest = bt_module.run_backtest
                
                # Создаем патч-версию с уменьшенным start_idx
                def patched_run_backtest(df, symbol=None, mode="soft", intelligent_system=None):
                    # Импортируем все необходимое
                    from scripts.backtest_5coins_intelligent import (
                        BacktestStats, add_technical_indicators, 
                        get_symbol_tp_sl_multipliers, START_BALANCE, FEE, SLIPPAGE, RISK_PER_TRADE
                    )
                    from src.signals.core import soft_entry_signal
                    from src.utils.shared_utils import get_dynamic_tp_levels
                    from src.signals.risk import get_dynamic_sl_level
                    import pandas as pd
                    
                    stats = BacktestStats(f"{symbol} тест (soft, фильтры перед baseline)")
                    
                    # Добавляем индикаторы
                    df = add_technical_indicators(df)
                    
                    # Уменьшенный start_idx для короткого теста
                    start_idx = 25
                    
                    if len(df) < start_idx:
                        return stats
                    
                    balance = START_BALANCE
                    position = None
                    
                    # Получаем TP/SL multipliers
                    tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)
                    
                    # Проходим по свечам
                    for i in range(start_idx, len(df)):
                        current_price = df["close"].iloc[i]
                        
                        # Если есть открытая позиция - проверяем выход
                        if position:
                            # Логика выхода (упрощенно)
                            if position['side'] == 'long':
                                if current_price >= position['tp1']:
                                    # TP1 достигнут
                                    profit = (position['tp1'] - position['entry_price']) * position['size']
                                    balance += profit * (1 - FEE)
                                    stats.add_trade(
                                        position['entry_price'], position['tp1'], 'long',
                                        profit, position['entry_time'], df.index[i]
                                    )
                                    position = None
                                elif current_price <= position['sl']:
                                    # SL достигнут
                                    loss = (position['sl'] - position['entry_price']) * position['size']
                                    balance += loss * (1 - FEE)
                                    stats.add_trade(
                                        position['entry_price'], position['sl'], 'long',
                                        loss, position['entry_time'], df.index[i]
                                    )
                                    position = None
                        else:
                            # Проверяем сигнал входа
                            side, entry_price = soft_entry_signal(df, i)
                            
                            if side and entry_price:
                                # Рассчитываем TP/SL
                                tp_levels = get_dynamic_tp_levels(
                                    df, i, side, entry_price, tp_mult=tp_mult
                                )
                                sl_level = get_dynamic_sl_level(
                                    df, i, side, entry_price, sl_mult=sl_mult
                                )
                                
                                if tp_levels and sl_level:
                                    # Открываем позицию
                                    risk_amount = balance * RISK_PER_TRADE
                                    sl_distance = abs(entry_price - sl_level)
                                    if sl_distance > 0:
                                        position_size = risk_amount / sl_distance
                                        position = {
                                            'side': side,
                                            'entry_price': entry_price,
                                            'size': position_size,
                                            'tp1': tp_levels.get('tp1', entry_price * 1.02),
                                            'sl': sl_level,
                                            'entry_time': df.index[i]
                                        }
                    
                    return stats
                
                # Заменяем функцию временно
                bt_module.run_backtest = patched_run_backtest
                try:
                    stats = run_backtest(df, symbol=symbol, mode="soft")
                finally:
                    # Восстанавливаем оригинальную функцию
                    bt_module.run_backtest = original_run_backtest
                metrics = stats.get_metrics()
                
                trades = metrics.get('total_trades', 0)
                ret = metrics.get('total_return', 0)
                
                if trades > 0:
                    total_trades += trades
                    total_return += ret
                    print(f"   ✅ {symbol}: {ret:+.2f}% ({trades} сделок)")
                else:
                    print(f"   ⚠️ {symbol}: Нет сделок")
            except Exception as e:
                print(f"   ❌ Ошибка для {symbol}: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "="*80)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТА (Фильтры ПЕРЕД baseline)")
        print("="*80)
        print(f"📈 Общая доходность: {total_return:+.2f}%")
        print(f"📊 Всего сделок: {total_trades}")
        print("="*80)
        
        return {
            'total_return': total_return,
            'total_trades': total_trades
        }
    finally:
        # Восстанавливаем оригинальную функцию
        core_module.soft_entry_signal = original_soft_entry

if __name__ == "__main__":
    import pandas as pd
    test_filters_before_baseline()

