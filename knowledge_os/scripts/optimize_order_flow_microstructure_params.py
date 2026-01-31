#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оптимизация параметров Order Flow и Microstructure фильтров
Тестирует разные параметры и находит оптимальные
"""

import json
import logging
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_5coins_intelligent import (
    load_yearly_data, add_technical_indicators,
    get_symbol_tp_sl_multipliers, START_BALANCE, FEE, RISK_PER_TRADE
)
from src.signals.risk import get_dynamic_sl_level
from src.utils.shared_utils import get_dynamic_tp_levels

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
PERIOD_DAYS = 7
MAX_WORKERS = 10

# Параметры для оптимизации Order Flow (расширенный набор)
ORDER_FLOW_PARAMS = [
    {'required_confirmations': 0, 'pr_threshold': 0.5},  # Очень мягкий
    {'required_confirmations': 0, 'pr_threshold': 0.7},
    {'required_confirmations': 0, 'pr_threshold': 0.8},
    {'required_confirmations': 0, 'pr_threshold': 0.9},
    {'required_confirmations': 0, 'pr_threshold': 1.0},
    {'required_confirmations': 1, 'pr_threshold': 0.5},
    {'required_confirmations': 1, 'pr_threshold': 0.7},
    {'required_confirmations': 1, 'pr_threshold': 0.8},
    {'required_confirmations': 1, 'pr_threshold': 0.9},
    {'required_confirmations': 1, 'pr_threshold': 1.0},
]

# Параметры для оптимизации Microstructure (расширенный набор)
MICROSTRUCTURE_PARAMS = [
    {'tolerance_pct': 1.0, 'min_strength': 0.05, 'lookback': 20},
    {'tolerance_pct': 1.5, 'min_strength': 0.05, 'lookback': 20},
    {'tolerance_pct': 2.0, 'min_strength': 0.05, 'lookback': 20},
    {'tolerance_pct': 2.5, 'min_strength': 0.05, 'lookback': 20},
    {'tolerance_pct': 1.0, 'min_strength': 0.1, 'lookback': 30},
    {'tolerance_pct': 1.5, 'min_strength': 0.1, 'lookback': 30},
    {'tolerance_pct': 2.0, 'min_strength': 0.1, 'lookback': 30},
    {'tolerance_pct': 2.5, 'min_strength': 0.1, 'lookback': 30},
    {'tolerance_pct': 3.0, 'min_strength': 0.1, 'lookback': 30},
    {'tolerance_pct': 2.0, 'min_strength': 0.15, 'lookback': 40},
    {'tolerance_pct': 2.5, 'min_strength': 0.15, 'lookback': 40},
    {'tolerance_pct': 3.0, 'min_strength': 0.15, 'lookback': 40},
]

def run_backtest_with_params(df, symbol, filter_type, params, before_baseline=False):
    """Запускает бэктест с заданными параметрами фильтра

    Args:
        before_baseline: True - фильтр ПЕРЕД baseline, False - ПОСЛЕ baseline
    """
    from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter
    from config import USE_VP_FILTER, USE_VWAP_FILTER

    os.environ['USE_VP_FILTER'] = 'True'
    os.environ['USE_VWAP_FILTER'] = 'True'
    os.environ['volume_profile_threshold'] = '0.6'
    os.environ['vwap_threshold'] = '0.8'

    # Настраиваем фильтры
    if filter_type == 'order_flow':
        os.environ['USE_ORDER_FLOW_FILTER'] = 'True'
        os.environ['USE_MICROSTRUCTURE_FILTER'] = 'False'
        os.environ['order_flow_required_confirmations'] = str(params['required_confirmations'])
        os.environ['order_flow_pr_threshold'] = str(params['pr_threshold'])
    else:  # microstructure
        os.environ['USE_ORDER_FLOW_FILTER'] = 'False'
        os.environ['USE_MICROSTRUCTURE_FILTER'] = 'True'
        os.environ['microstructure_tolerance_pct'] = str(params['tolerance_pct'])
        os.environ['microstructure_min_strength'] = str(params['min_strength'])
        os.environ['microstructure_lookback'] = str(params['lookback'])

    os.environ['DISABLE_EXTRA_FILTERS'] = 'false'

    # Очищаем кэш
    if 'src.signals.core' in sys.modules:
        del sys.modules['src.signals.core']
    if 'src.signals' in sys.modules:
        del sys.modules['src.signals']
    if 'config' in sys.modules:
        del sys.modules['config']

    from src.signals.core import soft_entry_signal
    import src.signals.core as core_module

    original_soft_entry = core_module.soft_entry_signal

    # Создаем модифицированную версию с параметрами
    def enhanced_soft_entry_signal(df, i):
        if i < 25:
            return None, None

        try:
            # VP и VWAP фильтры
            vp_ok = True
            if USE_VP_FILTER:
                vp_ok, _ = check_volume_profile_filter(df, i, "long", strict_mode=False)
                if not vp_ok:
                    return None, None

            vwap_ok = True
            if USE_VWAP_FILTER:
                vwap_ok, _ = check_vwap_filter(df, i, "long", strict_mode=False)
                if not vwap_ok:
                    return None, None

            # Order Flow или Microstructure фильтр (перед baseline, если before_baseline=True)
            if before_baseline:
                if filter_type == 'order_flow':
                    try:
                        of_ok = check_order_flow_with_params(df, i, params)
                        if not of_ok:
                            return None, None
                    except Exception as exc:
                        logger.debug("Order Flow ошибка: %s", exc)
                else:  # microstructure
                    try:
                        ms_ok = check_microstructure_with_params(df, i, params)
                        if not ms_ok:
                            return None, None
                    except Exception as exc:
                        logger.debug("Microstructure ошибка: %s", exc)

            # Baseline (ослабленный)
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
                # Order Flow или Microstructure фильтр (после baseline, если before_baseline=False)
                if not before_baseline:
                    if filter_type == 'order_flow':
                        try:
                            of_ok = check_order_flow_with_params(df, i, params)
                            if not of_ok:
                                return None, None
                        except Exception as exc:
                            logger.debug("Order Flow ошибка: %s", exc)
                    else:  # microstructure
                        try:
                            ms_ok = check_microstructure_with_params(df, i, params)
                            if not ms_ok:
                                return None, None
                        except Exception as exc:
                            logger.debug("Microstructure ошибка: %s", exc)

                return "long", current_price

            return None, None
        except Exception as exc:
            logger.error("Ошибка: %s", exc)
            return None, None

    core_module.soft_entry_signal = enhanced_soft_entry_signal

    try:
        df = add_technical_indicators(df)
        start_idx = 25

        if len(df) < start_idx:
            return {'trades': 0, 'return': 0.0, 'signals': 0}

        balance = START_BALANCE
        trades = []
        signals_generated = 0

        tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)

        for i in range(start_idx, len(df)):
            side, entry_price = soft_entry_signal(df, i)
            signals_generated += 1 if side else 0

            if side and entry_price:
                tp1_pct, _ = get_dynamic_tp_levels(df, i, side)
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
                        'profit': profit
                    })

        core_module.soft_entry_signal = original_soft_entry

        total_return = ((balance - START_BALANCE) / START_BALANCE) * 100

        return {
            'trades': len(trades),
            'return': total_return,
            'signals': signals_generated
        }
    except Exception:
        core_module.soft_entry_signal = original_soft_entry
        raise

def check_order_flow_with_params(df, i, params):
    """Проверяет Order Flow с заданными параметрами"""
    try:
        from src.analysis.order_flow import CumulativeDeltaVolume, VolumeDelta, PressureRatio

        cdv = CumulativeDeltaVolume(lookback=20)
        vd = VolumeDelta()
        pr = PressureRatio(lookback=5)

        cdv_signal = cdv.get_signal(df, i)
        vd_signal = vd.get_signal(df, i)
        pr_value = pr.get_value(df, i)
        cdv_value = cdv.get_value(df, i)

        cdv_ok = cdv_signal == 'long' or (cdv_signal is None and cdv_value is not None and cdv_value > 0)
        vd_ok = vd_signal == 'long' or vd_signal is None
        pr_ok = pr_value is not None and pr_value > params['pr_threshold']

        confirmations = sum([cdv_ok, vd_ok, pr_ok])
        required = params['required_confirmations']

        return confirmations >= required
    except Exception:
        return True  # Если ошибка, пропускаем

def check_microstructure_with_params(df, i, params):
    """Проверяет Microstructure с заданными параметрами"""
    try:
        from src.analysis.volume_profile import VolumeProfileAnalyzer
        from src.analysis.microstructure import AbsorptionLevels

        current_price = df["close"].iloc[i]

        vp_analyzer = VolumeProfileAnalyzer()
        absorption = AbsorptionLevels()

        liquidity_zones = vp_analyzer.get_liquidity_zones(
            df.iloc[:i+1],
            lookback_periods=params['lookback']
        )

        absorption_levels = absorption.detect_absorption_levels(df, i)

        support_zones = [z for z in liquidity_zones if z['type'] == 'support']
        for zone in support_zones:
            distance_pct = abs(current_price - zone['price']) / current_price * 100
            if distance_pct <= params['tolerance_pct'] and zone['strength'] >= params['min_strength']:
                return True

        support_absorption = [l for l in absorption_levels if l['type'] == 'support']
        for level in support_absorption:
            distance_pct = abs(current_price - level['price']) / current_price * 100
            if distance_pct <= params['tolerance_pct'] and level['strength'] >= params['min_strength']:
                return True

        return False
    except Exception:
        return True  # Если ошибка, пропускаем

def test_symbol_backtest(symbol, filter_type, params, before_baseline):
    """Тестирует один символ с заданными параметрами

    Args:
        before_baseline: True - фильтр ПЕРЕД baseline, False - ПОСЛЕ baseline
    """
    try:
        df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
        if df is None or len(df) < 25:
            return None

        result = run_backtest_with_params(df, symbol, filter_type, params, before_baseline)
        return {
            'symbol': symbol,
            'params': params,
            'before_baseline': before_baseline,
            'result': result
        }
    except Exception as exc:
        logger.error("Ошибка для %s: %s", symbol, exc)
        return None

def optimize_filter(filter_type):
    """Оптимизирует параметры фильтра"""
    params_list = ORDER_FLOW_PARAMS if filter_type == 'order_flow' else MICROSTRUCTURE_PARAMS
    filter_name = 'Order Flow' if filter_type == 'order_flow' else 'Microstructure'

    print(f"\n{'='*80}")
    print(f"🔍 ОПТИМИЗАЦИЯ {filter_name.upper()} ФИЛЬТРА")
    print(f"{'='*80}")
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print(f"🔧 Параметров для теста: {len(params_list)}")
    print(f"{'='*80}\n")

    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for params in params_list:
            for symbol in TEST_SYMBOLS:
                # Тестируем оба варианта: до и после baseline
                for before_baseline in [True, False]:
                    future = executor.submit(test_symbol_backtest, symbol, filter_type, params, before_baseline)
                    futures.append((future, params, symbol, before_baseline))

        total_tests = len(futures)
        with tqdm(total=total_tests, desc=f"Тестирование {filter_name}") as pbar:
            for future, params, symbol, before_baseline in futures:
                result = future.result()
                if result:
                    results.append(result)
                pbar.update(1)

    # Группируем результаты по параметрам и позиции (до/после baseline)
    params_results = {}
    for r in results:
        params_key = str(r['params'])
        position_key = 'ПЕРЕД' if r['before_baseline'] else 'ПОСЛЕ'
        full_key = f"{params_key}__{position_key}"

        if full_key not in params_results:
            params_results[full_key] = {
                'params': r['params'],
                'before_baseline': r['before_baseline'],
                'trades': 0,
                'return': 0.0,
                'signals': 0
            }
        params_results[full_key]['trades'] += r['result']['trades']
        params_results[full_key]['return'] += r['result']['return']
        params_results[full_key]['signals'] += r['result']['signals']

    # Находим лучшие параметры
    best_params = None
    best_position = None
    best_return = float('-inf')

    print(f"\n{'='*80}")
    print(f"📊 РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ {filter_name.upper()}")
    print(f"{'='*80}\n")

    # Сортируем по return
    sorted_results = sorted(params_results.items(), key=lambda x: x[1]['return'], reverse=True)

    # Показываем топ-10 результатов
    for idx, (full_key, metrics) in enumerate(sorted_results[:10], 1):
        position = 'ПЕРЕД baseline' if metrics['before_baseline'] else 'ПОСЛЕ baseline'
        print(f"{idx}. Параметры: {metrics['params']}")
        print(f"   Позиция: {position}")
        print(f"   Сделок: {metrics['trades']}, Return: {metrics['return']:+.2f}%, Сигналов: {metrics['signals']}")
        print()

        if metrics['return'] > best_return and metrics['trades'] > 0:
            best_return = metrics['return']
            best_params = metrics['params']
            best_position = metrics['before_baseline']

    if best_params:
        position_str = 'ПЕРЕД baseline' if best_position else 'ПОСЛЕ baseline'
        print("="*80)
        print("✅ ЛУЧШИЕ ПАРАМЕТРЫ:")
        print(f"   Параметры: {best_params}")
        print(f"   Позиция: {position_str}")
        print(f"   Return: {best_return:+.2f}%")
        print("="*80 + "\n")

        # Сохраняем результаты
        output_file = f"backtests/{filter_type}_optimization_results.json"
        os.makedirs("backtests", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'best_params': best_params,
                'best_position': position_str,
                'best_before_baseline': best_position,
                'best_return': best_return,
                'all_results': {k: {
                    'params': v['params'],
                    'before_baseline': v['before_baseline'],
                    'trades': v['trades'],
                    'return': v['return'],
                    'signals': v['signals']
                } for k, v in params_results.items()}
            }, f, indent=2, default=str)

        print(f"💾 Результаты сохранены в {output_file}")

    return best_params, best_position, best_return

if __name__ == "__main__":
    print("🚀 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ ФИЛЬТРОВ")
    print("="*80)

    # Оптимизируем Order Flow
    of_params, of_position, of_return = optimize_filter('order_flow')

    # Оптимизируем Microstructure
    ms_params, ms_position, ms_return = optimize_filter('microstructure')

    print("\n" + "="*80)
    print("📊 ИТОГОВЫЕ РЕКОМЕНДАЦИИ")
    print("="*80)
    print("Order Flow:")
    print(f"   Параметры: {of_params}")
    print(f"   Позиция: {'ПЕРЕД baseline' if of_position else 'ПОСЛЕ baseline'}")
    print(f"   Return: {of_return:+.2f}%")
    print()
    print("Microstructure:")
    print(f"   Параметры: {ms_params}")
    print(f"   Позиция: {'ПЕРЕД baseline' if ms_position else 'ПОСЛЕ baseline'}")
    print(f"   Return: {ms_return:+.2f}%")
    print("="*80)
