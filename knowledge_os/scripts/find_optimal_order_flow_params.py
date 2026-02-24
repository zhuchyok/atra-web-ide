#!/usr/bin/env python3
"""
Поиск оптимальных параметров Order Flow фильтра
с реальной фильтрацией сигналов
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

import pandas as pd

from config import USE_VP_FILTER, USE_VWAP_FILTER
from scripts.backtest_5coins_intelligent import (
    FEE,
    RISK_PER_TRADE,
    START_BALANCE,
    add_technical_indicators,
    get_symbol_tp_sl_multipliers,
    load_yearly_data,
)
from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter
from src.signals.risk import get_dynamic_sl_level
from src.utils.shared_utils import get_dynamic_tp_levels

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
PERIOD_DAYS = 7
MAX_WORKERS = 10

# Параметры для тестирования (ослабленные варианты)
ORDER_FLOW_PARAMS = [
    # Ослабленные варианты с required_confirmations=0 (только PR)
    {"required_confirmations": 0, "pr_threshold": 0.5},
    {"required_confirmations": 0, "pr_threshold": 0.6},
    {"required_confirmations": 0, "pr_threshold": 0.65},
    {"required_confirmations": 0, "pr_threshold": 0.7},
    {"required_confirmations": 0, "pr_threshold": 0.75},
    # Мягкие варианты с required_confirmations=1 (CDV/VD/PR)
    {"required_confirmations": 1, "pr_threshold": 0.5},
    {"required_confirmations": 1, "pr_threshold": 0.55},
    {"required_confirmations": 1, "pr_threshold": 0.6},
    {"required_confirmations": 1, "pr_threshold": 0.65},
    {"required_confirmations": 1, "pr_threshold": 0.7},
]


def check_order_flow_with_params(df, i, params):
    """Проверяет Order Flow с параметрами"""
    try:
        from src.analysis.order_flow import CumulativeDeltaVolume, PressureRatio, VolumeDelta

        cdv = CumulativeDeltaVolume(lookback=20)
        vd = VolumeDelta()
        pr = PressureRatio(lookback=5)

        cdv_signal = cdv.get_signal(df, i)
        vd_signal = vd.get_signal(df, i)
        pr_value = pr.get_value(df, i)
        cdv_value = cdv.get_value(df, i)

        # Если required_confirmations = 0, проверяем только pr_threshold
        if params["required_confirmations"] == 0:
            if pr_value is not None:
                return pr_value > params["pr_threshold"]
            return True  # Если данных нет, пропускаем

        # Если required_confirmations > 0, используем стандартную логику
        cdv_ok = cdv_signal == "long" or (
            cdv_signal is None and cdv_value is not None and cdv_value > 0
        )
        vd_ok = vd_signal == "long" or vd_signal is None
        pr_ok = pr_value is not None and pr_value > params["pr_threshold"]

        confirmations = sum([cdv_ok, vd_ok, pr_ok])
        required = params["required_confirmations"]

        return confirmations >= required
    except Exception:
        return True  # Если ошибка, пропускаем


def test_params_after_baseline(symbol, params):
    """Тестирует параметры ПОСЛЕ baseline"""
    try:
        os.environ["USE_VP_FILTER"] = "True"
        os.environ["USE_VWAP_FILTER"] = "True"
        os.environ["USE_ORDER_FLOW_FILTER"] = "True"
        os.environ["USE_MICROSTRUCTURE_FILTER"] = "False"
        os.environ["DISABLE_EXTRA_FILTERS"] = "false"
        os.environ["volume_profile_threshold"] = "0.6"
        os.environ["vwap_threshold"] = "0.8"

        if "src.signals.core" in sys.modules:
            del sys.modules["src.signals.core"]
        if "src.signals" in sys.modules:
            del sys.modules["src.signals"]
        if "config" in sys.modules:
            del sys.modules["config"]

        import src.signals.core as core_module
        from src.signals.core import soft_entry_signal

        original_soft_entry = core_module.soft_entry_signal

        def enhanced_soft_entry_signal(df, i):
            if i < 25:
                return None, None

            try:
                # VP и VWAP
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

                if (
                    pd.isna(current_price)
                    or pd.isna(bb_lower)
                    or pd.isna(bb_upper)
                    or pd.isna(ema7)
                    or pd.isna(ema25)
                ):
                    return None, None

                rsi = rsi if not pd.isna(rsi) else 50
                volume_ratio = volume_ratio if not pd.isna(volume_ratio) else 1.0
                volatility = volatility if not pd.isna(volatility) else 2.0
                momentum = momentum if not pd.isna(momentum) else 0.0
                trend_strength = trend_strength if not pd.isna(trend_strength) else 1.0

                adaptive_rsi_oversold = float(os.environ.get("ADAPTIVE_RSI_OVERSOLD", "60"))
                adaptive_trend_strength = float(os.environ.get("ADAPTIVE_TREND_STRENGTH", "0.05"))
                adaptive_momentum = float(os.environ.get("ADAPTIVE_MOMENTUM", "-10.0"))

                long_conditions = [
                    current_price <= bb_lower + (bb_upper - bb_lower) * 0.9,
                    ema7 >= ema25 * 0.85,
                    rsi < adaptive_rsi_oversold,
                    volume_ratio >= 0.3 * 0.8,
                    volatility > 0.05,
                    momentum >= adaptive_momentum,
                    trend_strength > adaptive_trend_strength,
                    True,
                    True,
                ]

                required_conditions = int(len(long_conditions) * 0.7)
                long_base_ok = sum(long_conditions) >= required_conditions

                if long_base_ok:
                    # Order Flow ПОСЛЕ baseline
                    of_ok = check_order_flow_with_params(df, i, params)
                    if not of_ok:
                        return None, None

                    return "long", current_price

                return None, None
            except Exception as e:
                logger.error("Ошибка: %s", e)
                return None, None

        core_module.soft_entry_signal = enhanced_soft_entry_signal

        df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
        if df is None or len(df) < 25:
            return {"trades": 0, "return": 0.0, "signals": 0}

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
                if side == "long":
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
                    trades.append({"entry": entry_price, "exit": exit_price, "profit": profit})

        core_module.soft_entry_signal = original_soft_entry

        total_return = ((balance - START_BALANCE) / START_BALANCE) * 100

        return {"trades": len(trades), "return": total_return, "signals": signals_generated}
    except Exception as e:
        logger.error(f"Ошибка для {symbol}: {e}")
        return {"trades": 0, "return": 0.0, "signals": 0}


def find_optimal_params():
    """Находит оптимальные параметры"""
    print("=" * 80)
    print("🔍 ПОИСК ОПТИМАЛЬНЫХ ПАРАМЕТРОВ ORDER FLOW")
    print("=" * 80)
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print(f"🧵 Потоков: {MAX_WORKERS}")
    print("=" * 80)
    print()

    all_results = {}

    # Тестируем все комбинации параметров
    total_tasks = len(ORDER_FLOW_PARAMS) * len(TEST_SYMBOLS)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []

        for params in ORDER_FLOW_PARAMS:
            for symbol in TEST_SYMBOLS:
                future = executor.submit(test_params_after_baseline, symbol, params)
                futures.append((future, params, symbol))

        with tqdm(total=total_tasks, desc="Тестирование параметров") as pbar:
            for future, params, symbol in futures:
                result = future.result()
                params_key = str(params)

                if params_key not in all_results:
                    all_results[params_key] = {
                        "params": params,
                        "symbols": {},
                        "total_trades": 0,
                        "total_return": 0.0,
                        "total_signals": 0,
                    }

                all_results[params_key]["symbols"][symbol] = result
                all_results[params_key]["total_trades"] += result["trades"]
                all_results[params_key]["total_return"] += result["return"]
                all_results[params_key]["total_signals"] += result["signals"]

                pbar.update(1)

    # Сортируем по return (убывание)
    sorted_results = sorted(all_results.items(), key=lambda x: x[1]["total_return"], reverse=True)

    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ")
    print("=" * 80)
    print()

    print("Топ-10 комбинаций параметров:")
    print()

    for i, (params_key, result) in enumerate(sorted_results[:10], 1):
        params = result["params"]
        avg_return = result["total_return"] / len(TEST_SYMBOLS)

        print(f"{i}. Параметры: {params}")
        print(f"   Сигналов: {result['total_signals']}")
        print(f"   Сделок: {result['total_trades']}")
        print(f"   Средний return: {avg_return:.2f}%")
        print(f"   Общий return: {result['total_return']:.2f}%")
        print()

    # Находим лучшие параметры (баланс между количеством и качеством)
    best_params = None
    best_score = -float("inf")

    for params_key, result in sorted_results:
        params = result["params"]
        avg_return = result["total_return"] / len(TEST_SYMBOLS)
        signals = result["total_signals"]
        trades = result["total_trades"]

        # Оценка: return * (количество сигналов / 100) - штраф за слишком мало сигналов
        if signals > 0 and trades > 0:
            # Предпочитаем параметры с required_confirmations > 0 (реальная фильтрация)
            filter_bonus = 1.5 if params["required_confirmations"] > 0 else 1.0
            score = avg_return * (signals / 100) * filter_bonus

            if score > best_score:
                best_score = score
                best_params = params

    print("=" * 80)
    print("✅ РЕКОМЕНДУЕМЫЕ ПАРАМЕТРЫ")
    print("=" * 80)
    print(f"Параметры: {best_params}")
    if best_params:
        best_result = all_results[str(best_params)]
        print(f"Сигналов: {best_result['total_signals']}")
        print(f"Сделок: {best_result['total_trades']}")
        print(f"Средний return: {best_result['total_return'] / len(TEST_SYMBOLS):.2f}%")
        print(f"Общий return: {best_result['total_return']:.2f}%")
    print("=" * 80)

    # Сохраняем результаты
    output_file = "backtests/order_flow_optimal_params.json"
    os.makedirs("backtests", exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(
            {
                "best_params": best_params,
                "all_results": {
                    k: {
                        "params": v["params"],
                        "total_trades": v["total_trades"],
                        "total_return": v["total_return"],
                        "total_signals": v["total_signals"],
                        "symbols": v["symbols"],
                    }
                    for k, v in all_results.items()
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n💾 Результаты сохранены в: {output_file}")


if __name__ == "__main__":
    find_optimal_params()
