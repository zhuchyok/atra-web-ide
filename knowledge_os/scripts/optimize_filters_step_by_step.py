#!/usr/bin/env python3
"""
ПОЭТАПНАЯ ОПТИМИЗАЦИЯ ФИЛЬТРОВ
Оптимизирует фильтры по одному, применяя оптимальные параметры после каждого этапа
"""

import json
import os
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from tqdm import tqdm

warnings.filterwarnings("ignore")

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.signals.indicators import add_technical_indicators
from src.signals.risk import get_dynamic_sl_level
from src.utils.shared_utils import get_dynamic_tp_levels

# ============================================================================
# НАСТРОЙКИ
# ============================================================================

START_BALANCE = 10000.0
FEE = 0.001
SLIPPAGE = 0.0005
RISK_PER_TRADE = 0.05

TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
PERIOD_DAYS = 30
MAX_WORKERS = 20

# ✅ УЖЕ ОПТИМИЗИРОВАННЫЕ ПАРАМЕТРЫ (используем как базу)
OPTIMAL_ORDER_FLOW = {"required_confirmations": 0, "pr_threshold": 0.5}
OPTIMAL_MICROSTRUCTURE = {"tolerance_pct": 2.5, "min_strength": 0.1, "lookback": 30}
OPTIMAL_MOMENTUM = {"mfi_long": 50, "mfi_short": 50, "stoch_long": 50, "stoch_short": 50}
OPTIMAL_TREND_STRENGTH = {"adx_threshold": 15, "require_direction": False}
OPTIMAL_VP = {"volume_profile_threshold": 0.6}
OPTIMAL_VWAP = {"vwap_threshold": 0.6}
OPTIMAL_AMT = {"lookback": 20, "balance_threshold": 0.3, "imbalance_threshold": 0.5}
OPTIMAL_MP = {"tolerance_pct": 1.5}
OPTIMAL_IP = {"min_quality_score": 0.6}

# Параметры для поэтапной оптимизации
INTEREST_ZONE_PARAMS = [
    {
        "lookback_periods": 50,
        "min_volume_cluster": 1.0,
        "zone_width_pct": 0.3,
        "min_zone_strength": 0.5,
    },
    {
        "lookback_periods": 100,
        "min_volume_cluster": 1.5,
        "zone_width_pct": 0.5,
        "min_zone_strength": 0.6,
    },
    {
        "lookback_periods": 200,
        "min_volume_cluster": 2.0,
        "zone_width_pct": 0.7,
        "min_zone_strength": 0.7,
    },
]

FIBONACCI_ZONE_PARAMS = [
    {"lookback_periods": 50, "tolerance_pct": 0.3, "require_strong_levels": False},
    {"lookback_periods": 100, "tolerance_pct": 0.5, "require_strong_levels": False},
    {"lookback_periods": 200, "tolerance_pct": 0.7, "require_strong_levels": True},
]

VOLUME_IMBALANCE_PARAMS = [
    {
        "lookback_periods": 10,
        "volume_spike_threshold": 1.5,
        "min_volume_ratio": 1.0,
        "require_volume_confirmation": True,
    },
    {
        "lookback_periods": 20,
        "volume_spike_threshold": 2.0,
        "min_volume_ratio": 1.2,
        "require_volume_confirmation": True,
    },
    {
        "lookback_periods": 30,
        "volume_spike_threshold": 2.5,
        "min_volume_ratio": 1.5,
        "require_volume_confirmation": False,
    },
]

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================


def load_yearly_data(symbol: str, limit_days: int = 30) -> Optional[pd.DataFrame]:
    """Загружает данные для символа"""
    try:
        data_dir = "data/backtest_data_yearly"
        file_path = os.path.join(data_dir, f"{symbol}_1h.csv")

        if not os.path.exists(file_path):
            return None

        df = pd.read_csv(file_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        if limit_days:
            cutoff_date = df["timestamp"].max() - pd.Timedelta(days=limit_days)
            df = df[df["timestamp"] >= cutoff_date].reset_index(drop=True)

        return df
    except Exception as e:
        print(f"❌ Ошибка загрузки данных для {symbol}: {e}")
        return None


def get_symbol_tp_sl_multipliers(symbol: str) -> Tuple[float, float]:
    """Получает TP/SL multipliers для символа"""
    try:
        from archive.experimental.optimized_config import OPTIMIZED_PARAMETERS

        params = OPTIMIZED_PARAMETERS.get(symbol, {})
        return params.get("tp_mult", 2.0), params.get("sl_mult", 1.5)
    except ImportError:
        return 2.0, 1.5


# Импортируем функции проверки фильтров
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

        if params["required_confirmations"] == 0:
            if pr_value is not None:
                return pr_value > params["pr_threshold"]
            return True

        cdv_ok = cdv_signal == "long" or (
            cdv_signal is None and cdv_value is not None and cdv_value > 0
        )
        vd_ok = vd_signal == "long" or vd_signal is None
        pr_ok = pr_value is not None and pr_value > params["pr_threshold"]

        confirmations = sum([cdv_ok, vd_ok, pr_ok])
        return confirmations >= params["required_confirmations"]
    except Exception:
        return True


def check_microstructure_with_params(df, i, params):
    """Проверяет Microstructure с параметрами"""
    try:
        from src.analysis.microstructure import AbsorptionLevels
        from src.analysis.volume_profile import VolumeProfileAnalyzer

        current_price = df["close"].iloc[i]

        vp_analyzer = VolumeProfileAnalyzer()
        absorption = AbsorptionLevels()

        liquidity_zones = vp_analyzer.get_liquidity_zones(
            df.iloc[: i + 1], lookback_periods=params["lookback"]
        )

        absorption_levels = absorption.detect_absorption_levels(df, i)

        support_zones = [z for z in liquidity_zones if z["type"] == "support"]
        for zone in support_zones:
            distance_pct = abs(current_price - zone["price"]) / current_price * 100
            if (
                distance_pct <= params["tolerance_pct"]
                and zone["strength"] >= params["min_strength"]
            ):
                return True

        support_absorption = [l for l in absorption_levels if l["type"] == "support"]
        for level in support_absorption:
            distance_pct = abs(current_price - level["price"]) / current_price * 100
            if (
                distance_pct <= params["tolerance_pct"]
                and level["strength"] >= params["min_strength"]
            ):
                return True

        return False
    except Exception:
        return True


def check_momentum_with_params(df, i, side, params):
    """Проверяет Momentum с параметрами"""
    try:
        from src.filters.momentum_filter import check_momentum_filter

        # Временно устанавливаем параметры через os.environ
        os.environ["MFI_LONG"] = str(params["mfi_long"])
        os.environ["MFI_SHORT"] = str(params["mfi_short"])
        os.environ["STOCH_LONG"] = str(params["stoch_long"])
        os.environ["STOCH_SHORT"] = str(params["stoch_short"])
        return check_momentum_filter(df, i, side, strict_mode=False)[0]
    except Exception:
        return True


def check_trend_strength_with_params(df, i, side, params):
    """Проверяет Trend Strength с параметрами"""
    try:
        from src.filters.trend_strength_filter import check_trend_strength_filter

        os.environ["ADX_THRESHOLD"] = str(params["adx_threshold"])
        os.environ["REQUIRE_DIRECTION"] = str(params["require_direction"])
        return check_trend_strength_filter(df, i, side, strict_mode=False)[0]
    except Exception:
        return True


def check_interest_zone_with_params(df, i, side, params):
    """Проверяет Interest Zone с параметрами"""
    try:
        from src.filters.filters_sync_for_backtest import check_interest_zone_filter_sync

        return check_interest_zone_filter_sync(
            df,
            i,
            side,
            strict_mode=False,
            lookback_periods=params["lookback_periods"],
            min_volume_cluster=params["min_volume_cluster"],
            zone_width_pct=params["zone_width_pct"],
            min_zone_strength=params["min_zone_strength"],
        )[0]
    except Exception:
        return True


def check_fibonacci_zone_with_params(df, i, side, params):
    """Проверяет Fibonacci Zone с параметрами"""
    try:
        from src.filters.filters_sync_for_backtest import check_fibonacci_zone_filter_sync

        return check_fibonacci_zone_filter_sync(
            df,
            i,
            side,
            strict_mode=False,
            lookback_periods=params["lookback_periods"],
            tolerance_pct=params["tolerance_pct"],
            require_strong_levels=params["require_strong_levels"],
        )[0]
    except Exception:
        return True


def check_volume_imbalance_with_params(df, i, side, params):
    """Проверяет Volume Imbalance с параметрами"""
    try:
        from src.filters.filters_sync_for_backtest import check_volume_imbalance_filter_sync

        return check_volume_imbalance_filter_sync(
            df,
            i,
            side,
            strict_mode=False,
            lookback_periods=params["lookback_periods"],
            volume_spike_threshold=params["volume_spike_threshold"],
            min_volume_ratio=params["min_volume_ratio"],
            require_volume_confirmation=params["require_volume_confirmation"],
        )[0]
    except Exception:
        return True


# ============================================================================
# БЭКТЕСТ С ОДНИМ ФИЛЬТРОМ
# ============================================================================


def run_backtest_with_filter(
    symbol: str, filter_name: str, filter_params: Dict, check_filter_func
) -> Dict:
    """Запускает бэктест с одним фильтром"""
    try:
        # Включаем все базовые фильтры
        os.environ["USE_VP_FILTER"] = "True"
        os.environ["USE_VWAP_FILTER"] = "True"
        os.environ["USE_ORDER_FLOW_FILTER"] = "True"
        os.environ["USE_MICROSTRUCTURE_FILTER"] = "True"
        os.environ["USE_MOMENTUM_FILTER"] = "True"
        os.environ["USE_TREND_STRENGTH_FILTER"] = "True"
        os.environ["USE_AMT_FILTER"] = "True"
        os.environ["USE_MARKET_PROFILE_FILTER"] = "True"
        os.environ["USE_INSTITUTIONAL_PATTERNS_FILTER"] = "True"
        os.environ["USE_RUST"] = "true"

        # Устанавливаем параметры базовых фильтров
        os.environ["volume_profile_threshold"] = str(OPTIMAL_VP["volume_profile_threshold"])
        os.environ["vwap_threshold"] = str(OPTIMAL_VWAP["vwap_threshold"])

        # Очищаем кэш модулей
        modules_to_clear = ["src.signals.core", "src.signals", "config"]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]

        import src.signals.core as core_module
        from src.signals.core import soft_entry_signal
        from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter

        original_soft_entry = core_module.soft_entry_signal

        def enhanced_soft_entry_signal(df, i):
            if i < 25:
                return None, None

            try:
                # VP и VWAP (обязательные)
                vp_ok, _ = check_volume_profile_filter(df, i, "long", strict_mode=False)
                if not vp_ok:
                    return None, None

                vwap_ok, _ = check_vwap_filter(df, i, "long", strict_mode=False)
                if not vwap_ok:
                    return None, None

                # Baseline (70%)
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

                long_conditions = [
                    current_price <= bb_lower + (bb_upper - bb_lower) * 0.9,
                    ema7 >= ema25 * 0.85,
                    rsi < 60.0,
                    volume_ratio >= 0.3 * 0.8,
                    volatility > 0.05,
                    momentum >= -10.0,
                    trend_strength > 0.05,
                    True,
                    True,
                ]

                required_conditions = int(len(long_conditions) * 0.7)
                long_base_ok = sum(long_conditions) >= required_conditions

                if long_base_ok:
                    # Базовые фильтры (уже оптимизированы)
                    of_ok = check_order_flow_with_params(df, i, OPTIMAL_ORDER_FLOW)
                    if not of_ok:
                        return None, None

                    ms_ok = check_microstructure_with_params(df, i, OPTIMAL_MICROSTRUCTURE)
                    if not ms_ok:
                        return None, None

                    mom_ok = check_momentum_with_params(df, i, "long", OPTIMAL_MOMENTUM)
                    if not mom_ok:
                        return None, None

                    trend_ok = check_trend_strength_with_params(
                        df, i, "long", OPTIMAL_TREND_STRENGTH
                    )
                    if not trend_ok:
                        return None, None

                    # Новый фильтр для оптимизации
                    new_filter_ok = check_filter_func(df, i, "long", filter_params)
                    if not new_filter_ok:
                        return None, None

                    return "long", current_price

                return None, None
            except Exception as e:
                return None, None

        core_module.soft_entry_signal = enhanced_soft_entry_signal

        # Загружаем данные
        df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
        if df is None or len(df) < 25:
            return {
                "trades": 0,
                "return": 0.0,
                "signals": 0,
                "winning_trades": 0,
                "losing_trades": 0,
            }

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
                    trades.append({"profit": profit, "entry": entry_price, "exit": exit_price})

        core_module.soft_entry_signal = original_soft_entry

        total_return = ((balance - START_BALANCE) / START_BALANCE) * 100
        winning_trades = sum(1 for t in trades if t["profit"] > 0)
        losing_trades = sum(1 for t in trades if t["profit"] <= 0)

        return {
            "trades": len(trades),
            "return": total_return,
            "signals": signals_generated,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "trades_list": trades,
        }
    except Exception as e:
        print(f"❌ Ошибка для {symbol}: {e}")
        return {"trades": 0, "return": 0.0, "signals": 0, "winning_trades": 0, "losing_trades": 0}


# ============================================================================
# ОПТИМИЗАЦИЯ ОДНОГО ФИЛЬТРА
# ============================================================================


def optimize_single_filter(
    filter_name: str, filter_params_list: List[Dict], check_filter_func
) -> Dict:
    """Оптимизирует один фильтр"""
    print(f"\n{'=' * 80}")
    print(f"🚀 ОПТИМИЗАЦИЯ: {filter_name}")
    print(f"{'=' * 80}")
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
                    run_backtest_with_filter, symbol, filter_name, params, check_filter_func
                )
                futures.append((future, params, symbol))

        with tqdm(total=total_tasks, desc=f"Оптимизация {filter_name}") as pbar:
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
                        "total_winning": 0,
                        "total_losing": 0,
                    }

                all_results[params_key]["symbols"][symbol] = result
                all_results[params_key]["total_trades"] += result["trades"]
                all_results[params_key]["total_return"] += result["return"]
                all_results[params_key]["total_signals"] += result["signals"]
                all_results[params_key]["total_winning"] += result["winning_trades"]
                all_results[params_key]["total_losing"] += result["losing_trades"]

                pbar.update(1)

    # Рассчитываем метрики
    for params_key, result in all_results.items():
        if result["total_trades"] > 0:
            result["win_rate"] = result["total_winning"] / result["total_trades"] * 100

            total_profit = 0
            total_loss = 0
            for symbol_result in result["symbols"].values():
                for trade_data in symbol_result.get("trades_list", []):
                    profit = trade_data.get("profit", 0)
                    if profit > 0:
                        total_profit += profit
                    else:
                        total_loss += abs(profit)

            if total_loss > 0:
                result["profit_factor"] = total_profit / total_loss
            else:
                result["profit_factor"] = float("inf") if total_profit > 0 else 0

            result["return_per_signal"] = (
                (result["total_return"] / result["total_signals"])
                if result["total_signals"] > 0
                else 0
            )
        else:
            result["win_rate"] = 0
            result["profit_factor"] = 0
            result["return_per_signal"] = 0

    # Сортируем по качеству
    def quality_score(result):
        if result["total_trades"] == 0:
            return -float("inf")
        win_rate_bonus = result["win_rate"] / 100
        pf_bonus = min(result["profit_factor"], 10.0) / 10.0
        return_bonus = result["return_per_signal"] / 100
        return win_rate_bonus * pf_bonus * return_bonus * result["total_trades"]

    sorted_results = sorted(all_results.items(), key=lambda x: quality_score(x[1]), reverse=True)

    # Выводим результаты
    print(f"\n{'=' * 80}")
    print(f"📊 РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ: {filter_name}")
    print(f"{'=' * 80}\n")

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
    best_params = sorted_results[0][1]["params"]
    best_metrics = {
        "signals": sorted_results[0][1]["total_signals"],
        "trades": sorted_results[0][1]["total_trades"],
        "win_rate": sorted_results[0][1]["win_rate"],
        "profit_factor": sorted_results[0][1]["profit_factor"],
        "return_per_signal": sorted_results[0][1]["return_per_signal"],
        "total_return": sorted_results[0][1]["total_return"],
    }

    return {"filter_name": filter_name, "best_params": best_params, "best_metrics": best_metrics}


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================


def main():
    """Главная функция поэтапной оптимизации"""
    print("=" * 80)
    print("🚀 ПОЭТАПНАЯ ОПТИМИЗАЦИЯ ФИЛЬТРОВ")
    print("=" * 80)
    print()
    print("📊 Этапы:")
    print("   1. Interest Zone Filter")
    print("   2. Fibonacci Zone Filter")
    print("   3. Volume Imbalance Filter")
    print()
    print("⏱️  Период: 30 дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print(f"🧵 Потоков: {MAX_WORKERS}")
    print("=" * 80)
    print()

    results = {}

    # Этап 1: Interest Zone Filter
    iz_result = optimize_single_filter(
        "Interest Zone Filter", INTEREST_ZONE_PARAMS, check_interest_zone_with_params
    )
    results["interest_zone"] = iz_result
    print(f"✅ Этап 1 завершен! Оптимальные параметры: {iz_result['best_params']}")
    print()

    # Этап 2: Fibonacci Zone Filter
    fib_result = optimize_single_filter(
        "Fibonacci Zone Filter", FIBONACCI_ZONE_PARAMS, check_fibonacci_zone_with_params
    )
    results["fibonacci_zone"] = fib_result
    print(f"✅ Этап 2 завершен! Оптимальные параметры: {fib_result['best_params']}")
    print()

    # Этап 3: Volume Imbalance Filter
    vi_result = optimize_single_filter(
        "Volume Imbalance Filter", VOLUME_IMBALANCE_PARAMS, check_volume_imbalance_with_params
    )
    results["volume_imbalance"] = vi_result
    print(f"✅ Этап 3 завершен! Оптимальные параметры: {vi_result['best_params']}")
    print()

    # Сохраняем результаты
    output_file = "backtests/step_by_step_optimization_results.json"
    os.makedirs("backtests", exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print("=" * 80)
    print("✅ ВСЕ ЭТАПЫ ЗАВЕРШЕНЫ!")
    print("=" * 80)
    print()
    print("📊 ИТОГОВЫЕ ОПТИМАЛЬНЫЕ ПАРАМЕТРЫ:")
    print()
    for key, value in results.items():
        print(f"   {key}: {value['best_params']}")
    print()
    print(f"📁 Результаты сохранены: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
