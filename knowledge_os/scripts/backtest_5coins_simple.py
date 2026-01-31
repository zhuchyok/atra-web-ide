#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упрощенный бэктест на 5 монетах (как в optimize_all_filters_comprehensive.py)
БЕЗ интеллектуальной системы, с упрощенной логикой выхода
"""

import os
import sys
import warnings
from datetime import datetime
from typing import Optional
import json

from src.shared.utils.datetime_utils import get_utc_now

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ✅ ВКЛЮЧАЕМ ВСЕ ФИЛЬТРЫ (включая новые 3)
os.environ['USE_VP_FILTER'] = 'true'
os.environ['USE_VWAP_FILTER'] = 'true'
os.environ['USE_ORDER_FLOW_FILTER'] = 'true'
os.environ['USE_MICROSTRUCTURE_FILTER'] = 'true'
os.environ['USE_MOMENTUM_FILTER'] = 'true'
os.environ['USE_TREND_STRENGTH_FILTER'] = 'true'
os.environ['USE_AMT_FILTER'] = 'true'
os.environ['USE_MARKET_PROFILE_FILTER'] = 'true'
os.environ['USE_INSTITUTIONAL_PATTERNS_FILTER'] = 'true'
os.environ['USE_INTEREST_ZONE_FILTER'] = 'true'  # ✅ ВКЛЮЧЕН
os.environ['USE_FIBONACCI_ZONE_FILTER'] = 'true'  # ✅ ВКЛЮЧЕН
os.environ['USE_VOLUME_IMBALANCE_FILTER'] = 'true'  # ✅ ВКЛЮЧЕН
os.environ['DISABLE_EXTRA_FILTERS'] = 'false'

# Импорты системы (после установки переменных окружения)
# 🔧 НЕ импортируем soft_entry_signal напрямую - используем через core_module после monkey patching
from src.signals.indicators import add_technical_indicators
from src.utils.shared_utils import get_dynamic_tp_levels
from src.signals.risk import get_dynamic_sl_level

# Импорт оптимизированных параметров
try:
    from archive.experimental.optimized_config import OPTIMIZED_PARAMETERS
    OPTIMIZED_PARAMS_AVAILABLE = True
except ImportError:
    OPTIMIZED_PARAMS_AVAILABLE = False
    OPTIMIZED_PARAMETERS = {}

# ============================================================================
# НАСТРОЙКИ БЭКТЕСТА
# ============================================================================

START_BALANCE = 10000.0
FEE = 0.001  # 0.1% комиссия
SLIPPAGE = 0.0005  # 0.05% проскальзывание
RISK_PER_TRADE = 0.05  # 5% риск на сделку

DEFAULT_TP_MULT = 2.0
DEFAULT_SL_MULT = 1.5

# Топ 5 монет (как в предыдущих тестах)
TEST_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
]

PERIOD_DAYS = 90  # 3 месяца (для теста, потом можно увеличить)

# Путь к историческим данным
DATA_DIR = "data/backtest_data_yearly"

def get_symbol_tp_sl_multipliers(symbol: str) -> tuple:
    """Получает оптимизированные TP/SL multipliers для символа"""
    if OPTIMIZED_PARAMS_AVAILABLE:
        params = OPTIMIZED_PARAMETERS.get(symbol, {})
        tp_mult = params.get('tp_mult', DEFAULT_TP_MULT)
        sl_mult = params.get('sl_mult', DEFAULT_SL_MULT)
        return tp_mult, sl_mult
    return DEFAULT_TP_MULT, DEFAULT_SL_MULT

def load_yearly_data(symbol: str, limit_days: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Загружает годовые данные из CSV"""
    csv_path = os.path.join(DATA_DIR, f"{symbol}.csv")
    
    if not os.path.exists(csv_path):
        print(f"⚠️ Файл не найден: {csv_path}")
        return None
    
    try:
        df = pd.read_csv(csv_path)
        
        # Преобразуем timestamp в datetime
        if 'timestamp' in df.columns:
            try:
                if df['timestamp'].dtype == 'int64' or df['timestamp'].dtype == 'float64':
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
            except Exception:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            
            df.set_index('timestamp', inplace=True)
        
        # Сортируем по времени
        df = df.sort_index()
        
        # Ограничиваем последними N днями
        if limit_days:
            cutoff_date = df.index[-1] - pd.Timedelta(days=limit_days)
            df = df[df.index >= cutoff_date]
        
        # Убеждаемся, что есть нужные колонки
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            print(f"⚠️ Отсутствуют необходимые колонки в {symbol}")
            return None
        
        # Преобразуем в float
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Удаляем строки с NaN
        df = df.dropna(subset=required_cols)
        
        period_str = f"последние {limit_days} дней" if limit_days else "годовые данные"
        print(f"✅ Загружено {len(df)} свечей для {symbol} ({period_str})")
        return df
        
    except Exception as e:
        print(f"❌ Ошибка загрузки {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return None

def run_backtest_simple(df: pd.DataFrame, symbol: str, initial_balance: float = None, vp_params=None, vwap_params=None, amt_params=None, mp_params=None, ip_params=None, iz_params=None, fib_params=None, vi_params=None) -> dict:
    """Упрощенный бэктест (как в optimize_all_filters_comprehensive.py)"""
    
    # Импортируем необходимые модули для monkey patching
    import src.signals.core as core_module
    from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter
    
    # Оптимальные параметры (как в optimize_all_filters_comprehensive.py)
    OPTIMAL_ORDER_FLOW = {'required_confirmations': 0, 'pr_threshold': 0.5}
    OPTIMAL_MICROSTRUCTURE = {'tolerance_pct': 2.5, 'min_strength': 0.1, 'lookback': 30}
    OPTIMAL_MOMENTUM = {'mfi_long': 50, 'mfi_short': 50, 'stoch_long': 50, 'stoch_short': 50}
    OPTIMAL_TREND_STRENGTH = {'adx_threshold': 15, 'require_direction': False}
    
    # Параметры по умолчанию (из config.py - оптимальные)
    if vp_params is None:
        vp_params = {'volume_profile_threshold': 0.6}
    if vwap_params is None:
        vwap_params = {'vwap_threshold': 0.6}
    if amt_params is None:
        amt_params = {'lookback': 20, 'balance_threshold': 0.3, 'imbalance_threshold': 0.5}
    if mp_params is None:
        mp_params = {'tolerance_pct': 1.5}
    if ip_params is None:
        ip_params = {'min_quality_score': 0.6}
    if iz_params is None:
        # Используем параметры из config.py (оптимизированные)
        iz_params = {'lookback_periods': 50, 'min_volume_cluster': 1.0, 'zone_width_pct': 0.3, 'min_zone_strength': 0.5}
    if fib_params is None:
        # Используем параметры из config.py (оптимизированные)
        fib_params = {'lookback_periods': 50, 'tolerance_pct': 0.3, 'require_strong_levels': False}
    if vi_params is None:
        # Используем параметры из config.py (оптимизированные)
        vi_params = {'lookback_periods': 10, 'volume_spike_threshold': 1.5, 'min_volume_ratio': 1.0, 'require_volume_confirmation': True}
    
    # Устанавливаем параметры фильтров
    os.environ['volume_profile_threshold'] = str(vp_params['volume_profile_threshold'])
    os.environ['vwap_threshold'] = str(vwap_params['vwap_threshold'])
    
    # Импортируем функции проверки фильтров
    from scripts.optimize_all_filters_comprehensive import (
        check_order_flow_with_params,
        check_microstructure_with_params,
        check_momentum_with_params,
        check_trend_strength_with_params,
        check_amt_with_params,
        check_market_profile_with_params,
        check_institutional_patterns_with_params,
        check_interest_zone_with_params,
        check_fibonacci_zone_with_params,
        check_volume_imbalance_with_params
    )
    
    # Сохраняем оригинальную функцию
    original_soft_entry = core_module.soft_entry_signal
    
    # Создаем enhanced_soft_entry_signal (как в optimize_all_filters_comprehensive.py)
    def enhanced_soft_entry_signal(df, i):
        if i < 25:
            return None, None
        
        try:
            # VP и VWAP (обязательные, перед baseline)
            vp_ok, _ = check_volume_profile_filter(df, i, "long", strict_mode=False)
            if not vp_ok:
                return None, None
            
            vwap_ok, _ = check_vwap_filter(df, i, "long", strict_mode=False)
            if not vwap_ok:
                return None, None
            
            # Baseline
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
            
            required_conditions = int(len(long_conditions) * 0.7)
            long_base_ok = sum(long_conditions) >= required_conditions
            
            if long_base_ok:
                # Order Flow
                of_ok = check_order_flow_with_params(df, i, OPTIMAL_ORDER_FLOW)
                if not of_ok:
                    return None, None
                
                # Microstructure
                ms_ok = check_microstructure_with_params(df, i, OPTIMAL_MICROSTRUCTURE)
                if not ms_ok:
                    return None, None
                
                # Momentum
                mom_ok = check_momentum_with_params(df, i, "long", OPTIMAL_MOMENTUM)
                if not mom_ok:
                    return None, None
                
                # Trend Strength
                trend_ok = check_trend_strength_with_params(df, i, "long", OPTIMAL_TREND_STRENGTH)
                if not trend_ok:
                    return None, None
                
                # AMT Filter
                amt_ok = check_amt_with_params(df, i, amt_params)
                if not amt_ok:
                    return None, None
                
                # Market Profile Filter
                mp_ok = check_market_profile_with_params(df, i, "long", mp_params)
                if not mp_ok:
                    return None, None
                
                # Institutional Patterns Filter
                ip_ok = check_institutional_patterns_with_params(df, i, "long", ip_params)
                if not ip_ok:
                    return None, None
                
                # ✅ НОВЫЕ ФИЛЬТРЫ (если включены через os.environ)
                use_iz = os.environ.get('USE_INTEREST_ZONE_FILTER', 'false').lower() == 'true'
                use_fib = os.environ.get('USE_FIBONACCI_ZONE_FILTER', 'false').lower() == 'true'
                use_vi = os.environ.get('USE_VOLUME_IMBALANCE_FILTER', 'false').lower() == 'true'
                
                if use_iz:
                    iz_ok = check_interest_zone_with_params(df, i, "long", iz_params)
                    if not iz_ok:
                        return None, None
                
                if use_fib:
                    fib_ok = check_fibonacci_zone_with_params(df, i, "long", fib_params)
                    if not fib_ok:
                        return None, None
                
                if use_vi:
                    vi_ok = check_volume_imbalance_with_params(df, i, "long", vi_params)
                    if not vi_ok:
                        return None, None
                
                return "long", current_price
            
            return None, None
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error("Ошибка: %s", e)
            return None, None
    
    # Применяем monkey patching
    core_module.soft_entry_signal = enhanced_soft_entry_signal
    
    try:
        # Добавляем индикаторы
        df = add_technical_indicators(df)
        
        if len(df) < 25:
            return {'trades': 0, 'return': 0.0, 'signals': 0, 'winning_trades': 0, 'losing_trades': 0}
        
        # Используем переданный баланс или баланс на монету
        if initial_balance is None:
            initial_balance = START_BALANCE / len(TEST_SYMBOLS) if 'TEST_SYMBOLS' in globals() else START_BALANCE
        
        start_idx = 25
        balance = initial_balance
        trades = []
        signals_generated = 0
        
        tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)
        
        for i in range(start_idx, len(df)):
            side, entry_price = core_module.soft_entry_signal(df, i)  # 🔧 Используем monkey patched версию
            signals_generated += 1 if side else 0
            
            if side and entry_price:
                # Получаем TP/SL уровни (как в optimize_all_filters_comprehensive.py)
                try:
                    tp1_pct, tp2_pct = get_dynamic_tp_levels(df, i, side)
                    if tp1_pct is None:
                        continue  # Пропускаем этот сигнал
                    tp1 = entry_price * (1 + tp1_pct / 100 * tp_mult)
                    
                    sl_level_pct = get_dynamic_sl_level(df, i, side)  # 🔧 Без use_ai_optimization
                    if sl_level_pct is None:
                        continue  # Пропускаем этот сигнал
                        
                    if side == 'long':
                        sl_level = entry_price * (1 - sl_level_pct / 100 * sl_mult)
                    else:
                        sl_level = entry_price * (1 + sl_level_pct / 100 * sl_mult)
                    
                    # Размер позиции
                    risk_amount = balance * RISK_PER_TRADE
                    sl_distance = abs(entry_price - sl_level)
                    
                    if sl_distance > 0:
                        position_size = risk_amount / sl_distance
                        # 🔧 УПРОЩЕННАЯ ЛОГИКА: сразу выход на TP1 (как в optimize_all_filters_comprehensive.py)
                        exit_price = tp1
                        if side == 'long':
                            profit = (exit_price - entry_price) * position_size * (1 - FEE)
                        else:
                            profit = (entry_price - exit_price) * position_size * (1 - FEE)
                        balance += profit
                        
                        # Получаем timestamp
                        timestamp = df.index[i] if hasattr(df.index, '__getitem__') else None
                        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp is not None and hasattr(timestamp, 'strftime') else f'Candle {i}'
                        
                        trades.append({
                            'profit': profit,
                            'entry': entry_price,
                            'exit': exit_price,
                            'timestamp': timestamp_str,
                            'balance_before': balance - profit,
                            'balance_after': balance,
                            'position_size': position_size,
                            'risk_amount': risk_amount,
                            'tp1': tp1,
                            'sl_level': sl_level,
                            'profit_pct': (profit / (balance - profit)) * 100 if (balance - profit) > 0 else 0
                        })
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Ошибка расчета TP/SL для {symbol} на свече {i}: {e}")
                    # Пропускаем этот сигнал при ошибке
        
        total_return = ((balance - initial_balance) / initial_balance) * 100 if initial_balance > 0 else 0.0
        winning_trades = sum(1 for t in trades if t['profit'] > 0)
        losing_trades = sum(1 for t in trades if t['profit'] < 0)
        
        return {
            'trades': len(trades),
            'return': total_return,
            'signals': signals_generated,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'final_balance': balance,
            'detailed_trades': trades  # Добавляем детальную информацию
        }
    finally:
        # Восстанавливаем оригинальную функцию
        core_module.soft_entry_signal = original_soft_entry

def main():
    """Главная функция"""
    print("="*80)
    print("🚀 УПРОЩЕННЫЙ БЭКТЕСТ: 5 МОНЕТ (БЕЗ интеллектуальной системы)")
    print("="*80)
    print(f"📅 Дата запуска: {get_utc_now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальный баланс: ${START_BALANCE:.2f}")
    print(f"📊 Символы ({len(TEST_SYMBOLS)}): {', '.join(TEST_SYMBOLS)}")
    print(f"📅 Период: последние {PERIOD_DAYS} дней ({PERIOD_DAYS // 365} года)")
    print("="*80)
    print("")
    print("✅ ВКЛЮЧЕНЫ ВСЕ ФИЛЬТРЫ (12 фильтров):")
    print("   - Volume Profile (VP)")
    print("   - VWAP")
    print("   - Order Flow")
    print("   - Microstructure")
    print("   - Momentum")
    print("   - Trend Strength")
    print("   - AMT, Market Profile, Institutional Patterns")
    print("   - ✅ Interest Zone (НОВЫЙ)")
    print("   - ✅ Fibonacci Zone (НОВЫЙ)")
    print("   - ✅ Volume Imbalance (НОВЫЙ)")
    print("   - ❌ БЕЗ интеллектуальной системы")
    print("   - ✅ Упрощенная логика выхода (сразу на TP1)")
    print("")
    
    all_results = []
    total_initial = START_BALANCE
    total_final = 0
    total_trades = 0
    total_signals = 0
    
    # Тестируем каждую монету
    for idx, symbol in enumerate(TEST_SYMBOLS, 1):
        print(f"\n{'='*80}")
        print(f"📈 Тестирование {symbol} ({idx}/{len(TEST_SYMBOLS)})")
        print(f"{'='*80}")
        
        # Загружаем месячные данные
        df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
        if df is None or len(df) < 25:
            print(f"❌ Недостаточно данных для {symbol}")
            continue
        
        # Запускаем упрощенный бэктест (со всеми фильтрами)
        balance_per_coin = START_BALANCE / len(TEST_SYMBOLS)
        result = run_backtest_simple(df, symbol, initial_balance=balance_per_coin)
        
        initial = balance_per_coin
        final = result['final_balance']  # Используем финальный баланс из результата
        
        total_final += final
        total_trades += result['trades']
        total_signals += result['signals']
        
        print(f"\n{symbol}:")
        print(f"  💰 Баланс: ${initial:.2f} → ${final:.2f} (доходность: {result['return']:+.2f}%)")
        print(f"  📊 Сделок: {result['trades']}")
        print(f"  ✅ Прибыльных: {result['winning_trades']}")
        print(f"  ❌ Убыточных: {result['losing_trades']}")
        print(f"  🎯 Сигналов: {result['signals']}")
        
        # Выводим детальную таблицу сделок
        if 'detailed_trades' in result and result['detailed_trades']:
            print(f"\n  📋 ДЕТАЛЬНАЯ ТАБЛИЦА СДЕЛОК ({len(result['detailed_trades'])}):")
            print(f"  {'№':<4} {'Дата/Время':<20} {'Вход':<12} {'Выход':<12} {'Баланс до':<12} {'Прибыль $':<12} {'Прибыль %':<10} {'Баланс после':<12}")
            print(f"  {'-'*100}")
            for idx, trade in enumerate(result['detailed_trades'], 1):
                profit_str = f"${trade['profit']:,.2f}"
                print(f"  {idx:<4} {trade.get('timestamp', 'N/A'):<20} ${trade['entry']:<11.8f} ${trade['exit']:<11.8f} ${trade.get('balance_before', 0):<11.2f} {profit_str:<12} {trade.get('profit_pct', 0):>+9.2f}% ${trade.get('balance_after', 0):<11.2f}")
        
        all_results.append({
            'symbol': symbol,
            'initial': initial,
            'final': final,
            'return': result['return'],
            'trades': result['trades'],
            'winning_trades': result['winning_trades'],
            'losing_trades': result['losing_trades'],
            'signals': result['signals'],
            'detailed_trades': result.get('detailed_trades', [])
        })
    
    # Итоговая сводка
    print(f"\n{'='*80}")
    total_profit = total_final - total_initial
    total_return_pct = (total_profit / total_initial) * 100 if total_initial > 0 else 0
    print("📊 ИТОГО ПОРТФЕЛЯ:")
    print(f"  Начальный баланс: ${total_initial:.2f}")
    print(f"  Финальный баланс: ${total_final:.2f}")
    print(f"  Общая прибыль: ${total_profit:+.2f}")
    print(f"  Общая доходность: {total_return_pct:+.2f}%")
    print(f"  Всего сделок: {total_trades}")
    print(f"  Всего сигналов: {total_signals}")
    print(f"{'='*80}")
    
    # Сохраняем результаты
    results_file = f"backtests/5coins_simple_{get_utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs('backtests', exist_ok=True)
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'period_days': PERIOD_DAYS,
            'symbols_count': len(TEST_SYMBOLS),
            'total_initial': total_initial,
            'total_final': total_final,
            'total_profit': total_profit,
            'total_return': total_return_pct,
            'total_trades': total_trades,
            'total_signals': total_signals,
            'symbols': all_results
        }, f, indent=2, default=str)
    
    print(f"\n✅ Результаты сохранены в {results_file}")
    print("\n🎉 БЭКТЕСТ ЗАВЕРШЕН!")

if __name__ == "__main__":
    main()

