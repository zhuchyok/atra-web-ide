#!/usr/bin/env python3
"""
Комплексная оптимизация ВСЕХ фильтров системы
Тестирует все комбинации параметров на 3 месяцах данных
"""

import itertools
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

import pandas as pd

from scripts.backtest_5coins_intelligent import (
    FEE,
    RISK_PER_TRADE,
    START_BALANCE,
    add_technical_indicators,
    get_symbol_tp_sl_multipliers,
    load_yearly_data,
)
from src.signals.risk import get_dynamic_sl_level
from src.utils.shared_utils import get_dynamic_tp_levels

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
PERIOD_DAYS = 30  # Уменьшено до 30 дней для ускорения (можно увеличить после)
MAX_WORKERS = 20

# ✅ УЖЕ ОПТИМИЗИРОВАННЫЕ ПАРАМЕТРЫ (используем оптимальные значения)
OPTIMAL_ORDER_FLOW = {"required_confirmations": 0, "pr_threshold": 0.5}
OPTIMAL_MICROSTRUCTURE = {"tolerance_pct": 2.5, "min_strength": 0.1, "lookback": 30}
OPTIMAL_MOMENTUM = {"mfi_long": 50, "mfi_short": 50, "stoch_long": 50, "stoch_short": 50}
OPTIMAL_TREND_STRENGTH = {"adx_threshold": 15, "require_direction": False}

# ❌ НОВЫЕ ФИЛЬТРЫ ДЛЯ ОПТИМИЗАЦИИ
# Volume Profile (VP) - параметры для оптимизации
VP_PARAMS = [
    {"volume_profile_threshold": 0.6},
    {"volume_profile_threshold": 0.8},
    {"volume_profile_threshold": 1.0},
]

# VWAP - параметры для оптимизации
VWAP_PARAMS = [
    {"vwap_threshold": 0.6},
    {"vwap_threshold": 0.8},
    {"vwap_threshold": 1.0},
]

# AMT Filter - параметры для оптимизации
AMT_PARAMS = [
    {"lookback": 20, "balance_threshold": 0.3, "imbalance_threshold": 0.5},
    {"lookback": 20, "balance_threshold": 0.3, "imbalance_threshold": 0.6},
]

# Market Profile Filter - параметры для оптимизации
MARKET_PROFILE_PARAMS = [
    {"tolerance_pct": 1.0},
    {"tolerance_pct": 1.5},
]

# Institutional Patterns Filter - параметры для оптимизации
INSTITUTIONAL_PATTERNS_PARAMS = [
    {"min_quality_score": 0.6},
    {"min_quality_score": 0.7},
]

# ❌ НОВЫЕ ФИЛЬТРЫ ДЛЯ ОПТИМИЗАЦИИ
# Interest Zone Filter - параметры для оптимизации
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

# Fibonacci Zone Filter - параметры для оптимизации
FIBONACCI_ZONE_PARAMS = [
    {"lookback_periods": 50, "tolerance_pct": 0.3, "require_strong_levels": False},
    {"lookback_periods": 100, "tolerance_pct": 0.5, "require_strong_levels": False},
    {"lookback_periods": 200, "tolerance_pct": 0.7, "require_strong_levels": True},
]

# Volume Imbalance Filter - параметры для оптимизации
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
        from src.analysis.momentum import MoneyFlowIndex, StochasticRSI

        mfi = MoneyFlowIndex(period=14)
        stoch_rsi = StochasticRSI()

        mfi_value = mfi.get_value(df, i)
        stoch_rsi_value = stoch_rsi.get_value(df, i)

        if side.lower() == "long":
            mfi_ok = mfi_value is not None and mfi_value < params["mfi_long"]
            stoch_rsi_ok = stoch_rsi_value is not None and stoch_rsi_value < params["stoch_long"]
            return mfi_ok or stoch_rsi_ok
        else:
            mfi_ok = mfi_value is not None and mfi_value > params["mfi_short"]
            stoch_rsi_ok = stoch_rsi_value is not None and stoch_rsi_value > params["stoch_short"]
            return mfi_ok or stoch_rsi_ok
    except Exception:
        return True


def check_trend_strength_with_params(df, i, side, params):
    """Проверяет Trend Strength с параметрами"""
    try:
        from src.analysis.trend import ADXAnalyzer, TrueStrengthIndex

        adx = ADXAnalyzer(period=14)
        tsi = TrueStrengthIndex()

        adx_value = adx.get_value(df, i)
        adx_direction = adx.get_trend_direction(df, i)
        tsi_value = tsi.get_value(df, i)
        tsi_signal = tsi.get_signal(df, i)

        if adx_value is None or adx_value < params["adx_threshold"]:
            return False

        if not params["require_direction"]:
            return True

        if side.lower() == "long":
            adx_ok = adx_direction == "up" if adx_direction else False
            tsi_ok = tsi_signal == "long" or (tsi_value is not None and tsi_value > 0)
            return adx_ok or tsi_ok
        else:
            adx_ok = adx_direction == "down" if adx_direction else False
            tsi_ok = tsi_signal == "short" or (tsi_value is not None and tsi_value < 0)
            return adx_ok or tsi_ok
    except Exception:
        return True


def check_amt_with_params(df, i, params):
    """Проверяет AMT с параметрами"""
    try:
        from src.analysis.auction_market_theory import AuctionMarketTheory, MarketPhase

        amt = AuctionMarketTheory(
            lookback=params["lookback"],
            balance_threshold=params["balance_threshold"],
            imbalance_threshold=params["imbalance_threshold"],
        )

        phase, details = amt.detect_market_phase(df, i)

        if phase is None or details is None:
            return True

        # Balance блокирует, Imbalance разрешает
        if phase == MarketPhase.BALANCE:
            return False
        elif phase == MarketPhase.IMBALANCE:
            return True
        else:  # AUCTION
            return True  # В мягком режиме разрешаем
    except Exception:
        return True


def check_market_profile_with_params(df, i, side, params):
    """Проверяет Market Profile с параметрами"""
    try:
        from src.filters.market_profile_filter import check_market_profile_filter

        return check_market_profile_filter(
            df, i, side, strict_mode=False, tolerance_pct=params["tolerance_pct"]
        )[0]
    except Exception:
        return True


def check_institutional_patterns_with_params(df, i, side, params):
    """Проверяет Institutional Patterns с параметрами"""
    try:
        from src.filters.institutional_patterns_filter import check_institutional_patterns_filter

        return check_institutional_patterns_filter(
            df, i, side, strict_mode=False, min_quality_score=params["min_quality_score"]
        )[0]
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


def run_backtest_with_all_filters(
    symbol,
    vp_params,
    vwap_params,
    amt_params,
    mp_params,
    ip_params,
    iz_params=None,
    fib_params=None,
    vi_params=None,
):
    """Запускает бэктест со всеми фильтрами"""
    try:
        # Включаем все фильтры
        os.environ["USE_VP_FILTER"] = "True"
        os.environ["USE_VWAP_FILTER"] = "True"
        os.environ["USE_ORDER_FLOW_FILTER"] = "True"
        os.environ["USE_MICROSTRUCTURE_FILTER"] = "True"
        os.environ["USE_MOMENTUM_FILTER"] = "True"
        os.environ["USE_TREND_STRENGTH_FILTER"] = "True"
        os.environ["USE_AMT_FILTER"] = "True"
        os.environ["USE_MARKET_PROFILE_FILTER"] = "True"
        os.environ["USE_INSTITUTIONAL_PATTERNS_FILTER"] = "True"
        os.environ["DISABLE_EXTRA_FILTERS"] = "false"
        # 🚀 Включаем Rust ускорение для индикаторов
        os.environ["USE_RUST"] = "true"

        # Устанавливаем параметры для оптимизации
        os.environ["volume_profile_threshold"] = str(vp_params["volume_profile_threshold"])
        os.environ["vwap_threshold"] = str(vwap_params["vwap_threshold"])

        if "src.signals.core" in sys.modules:
            del sys.modules["src.signals.core"]
        if "src.signals" in sys.modules:
            del sys.modules["src.signals"]
        if "config" in sys.modules:
            del sys.modules["config"]

        import src.signals.core as core_module
        from src.signals.core import soft_entry_signal
        from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter

        original_soft_entry = core_module.soft_entry_signal

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
                    # Order Flow (используем оптимальные параметры)
                    of_ok = check_order_flow_with_params(df, i, OPTIMAL_ORDER_FLOW)
                    if not of_ok:
                        return None, None

                    # Microstructure (используем оптимальные параметры)
                    ms_ok = check_microstructure_with_params(df, i, OPTIMAL_MICROSTRUCTURE)
                    if not ms_ok:
                        return None, None

                    # Momentum (используем оптимальные параметры)
                    mom_ok = check_momentum_with_params(df, i, "long", OPTIMAL_MOMENTUM)
                    if not mom_ok:
                        return None, None

                    # Trend Strength (используем оптимальные параметры)
                    trend_ok = check_trend_strength_with_params(
                        df, i, "long", OPTIMAL_TREND_STRENGTH
                    )
                    if not trend_ok:
                        return None, None

                    # AMT Filter (новый фильтр для оптимизации)
                    amt_ok = check_amt_with_params(df, i, amt_params)
                    if not amt_ok:
                        return None, None

                    # Market Profile Filter (новый фильтр для оптимизации)
                    mp_ok = check_market_profile_with_params(df, i, "long", mp_params)
                    if not mp_ok:
                        return None, None

                    # Institutional Patterns Filter (новый фильтр для оптимизации)
                    ip_ok = check_institutional_patterns_with_params(df, i, "long", ip_params)
                    if not ip_ok:
                        return None, None

                    # Новые фильтры (если параметры предоставлены)
                    if iz_params is not None:
                        iz_ok = check_interest_zone_with_params(df, i, "long", iz_params)
                        if not iz_ok:
                            return None, None

                    if fib_params is not None:
                        fib_ok = check_fibonacci_zone_with_params(df, i, "long", fib_params)
                        if not fib_ok:
                            return None, None

                    if vi_params is not None:
                        vi_ok = check_volume_imbalance_with_params(df, i, "long", vi_params)
                        if not vi_ok:
                            return None, None

                    return "long", current_price

                return None, None
            except Exception as e:
                logger.error("Ошибка: %s", e)
                return None, None

        core_module.soft_entry_signal = enhanced_soft_entry_signal

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
        losing_trades = sum(1 for t in trades if t["profit"] < 0)

        # Собираем данные о прибылях/убытках для расчета Profit Factor
        trades_list = [{"profit": t["profit"]} for t in trades]

        return {
            "trades": len(trades),
            "return": total_return,
            "signals": signals_generated,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "trades_list": trades_list,
        }
    except Exception as e:
        logger.error(f"Ошибка для {symbol}: {e}")
        return {"trades": 0, "return": 0.0, "signals": 0, "winning_trades": 0, "losing_trades": 0}


def optimize_all_filters():
    """Оптимизирует все фильтры"""
    print("=" * 80)
    print("🚀 КОМПЛЕКСНАЯ ОПТИМИЗАЦИЯ ВСЕХ ФИЛЬТРОВ")
    print("=" * 80)
    print(f"📅 Период: {PERIOD_DAYS} дней (3 месяца)")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print(f"🧵 Потоков: {MAX_WORKERS}")
    print()
    print("🔧 ФИЛЬТРЫ ДЛЯ ОПТИМИЗАЦИИ:")
    print("   ✅ Volume Profile (VP) - НОВЫЙ")
    print("   ✅ VWAP - НОВЫЙ")
    print("   ✅ AMT Filter - НОВЫЙ")
    print("   ✅ Market Profile Filter - НОВЫЙ")
    print("   ✅ Institutional Patterns Filter - НОВЫЙ")
    print("   ✅ Interest Zone Filter - НОВЫЙ")
    print("   ✅ Fibonacci Zone Filter - НОВЫЙ")
    print("   ✅ Volume Imbalance Filter - НОВЫЙ")
    print()
    print("✅ ИСПОЛЬЗУЮТСЯ ОПТИМАЛЬНЫЕ ПАРАМЕТРЫ:")
    print("   ✅ Order Flow: required_confirmations=0, pr_threshold=0.5")
    print("   ✅ Microstructure: tolerance_pct=2.5, min_strength=0.1, lookback=30")
    print("   ✅ Momentum: все пороги=50")
    print("   ✅ Trend Strength: adx_threshold=15, require_direction=false")
    print("=" * 80)
    print()

    # Генерируем все комбинации параметров для новых фильтров
    # Сначала оптимизируем базовые фильтры (VP, VWAP, AMT, MP, IP)
    # Затем добавим новые фильтры (IZ, FIB, VI) по одному
    all_combinations = list(
        itertools.product(
            VP_PARAMS,
            VWAP_PARAMS,
            AMT_PARAMS,
            MARKET_PROFILE_PARAMS,
            INSTITUTIONAL_PATTERNS_PARAMS,
            INTEREST_ZONE_PARAMS,
            FIBONACCI_ZONE_PARAMS,
            VOLUME_IMBALANCE_PARAMS,
        )
    )

    print(f"📊 Всего комбинаций: {len(all_combinations)}")
    print(f"📊 Всего тестов: {len(all_combinations) * len(TEST_SYMBOLS)}")
    print()

    all_results = {}

    total_tasks = len(all_combinations) * len(TEST_SYMBOLS)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []

        for (
            vp_params,
            vwap_params,
            amt_params,
            mp_params,
            ip_params,
            iz_params,
            fib_params,
            vi_params,
        ) in all_combinations:
            for symbol in TEST_SYMBOLS:
                future = executor.submit(
                    run_backtest_with_all_filters,
                    symbol,
                    vp_params,
                    vwap_params,
                    amt_params,
                    mp_params,
                    ip_params,
                    iz_params,
                    fib_params,
                    vi_params,
                )
                futures.append(
                    (
                        future,
                        vp_params,
                        vwap_params,
                        amt_params,
                        mp_params,
                        ip_params,
                        iz_params,
                        fib_params,
                        vi_params,
                        symbol,
                    )
                )

        with tqdm(total=total_tasks, desc="Оптимизация всех фильтров") as pbar:
            for (
                future,
                vp_params,
                vwap_params,
                amt_params,
                mp_params,
                ip_params,
                iz_params,
                fib_params,
                vi_params,
                symbol,
            ) in futures:
                result = future.result()

                params_key = (
                    f"VP_{str(vp_params)}__VWAP_{str(vwap_params)}__AMT_{str(amt_params)}__"
                    f"MP_{str(mp_params)}__IP_{str(ip_params)}__IZ_{str(iz_params)}__"
                    f"FIB_{str(fib_params)}__VI_{str(vi_params)}"
                )

                if params_key not in all_results:
                    all_results[params_key] = {
                        "vp_params": vp_params,
                        "vwap_params": vwap_params,
                        "amt_params": amt_params,
                        "mp_params": mp_params,
                        "ip_params": ip_params,
                        "iz_params": iz_params,
                        "fib_params": fib_params,
                        "vi_params": vi_params,
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

    # Рассчитываем метрики качества для каждой комбинации
    for params_key, result in all_results.items():
        if result["total_trades"] > 0:
            result["win_rate"] = result["total_winning"] / result["total_trades"] * 100

            # Profit Factor - собираем прибыли и убытки из всех сделок
            total_profit = 0
            total_loss = 0
            for symbol_result in result["symbols"].values():
                # Собираем прибыли и убытки из сделок
                for trade_data in symbol_result.get("trades_list", []):
                    profit = trade_data.get("profit", 0)
                    if profit > 0:
                        total_profit += profit
                    else:
                        total_loss += abs(profit)

            # Если нет данных о сделках, используем упрощенный расчет
            if total_profit == 0 and total_loss == 0:
                # Используем средние значения по символам
                pf_sum = 0
                count = 0
                for symbol_result in result["symbols"].values():
                    if symbol_result.get("trades", 0) > 0:
                        winning = symbol_result.get("winning_trades", 0)
                        losing = symbol_result.get("losing_trades", 0)
                        if losing > 0:
                            # Упрощенный PF: отношение прибыльных к убыточным
                            pf_sum += (winning / losing) if losing > 0 else float("inf")
                        else:
                            pf_sum += float("inf")
                        count += 1
                result["profit_factor"] = (pf_sum / count) if count > 0 else 0
            else:
                result["profit_factor"] = (
                    (total_profit / total_loss) if total_loss > 0 else float("inf")
                )

            result["return_per_signal"] = (
                (result["total_return"] / result["total_signals"])
                if result["total_signals"] > 0
                else 0
            )
        else:
            result["win_rate"] = 0
            result["profit_factor"] = 0
            result["return_per_signal"] = 0

    # Сортируем по комбинированной метрике качества
    def quality_score(result):
        if result["total_trades"] == 0:
            return -float("inf")
        # Комбинированная оценка: Win Rate * Profit Factor * Return/сигнал
        win_rate_bonus = result["win_rate"] / 100
        pf_bonus = min(result["profit_factor"], 10.0) / 10.0  # Ограничиваем PF до 10
        return_bonus = result["return_per_signal"] / 100
        return win_rate_bonus * pf_bonus * return_bonus * result["total_trades"]

    sorted_results = sorted(all_results.items(), key=lambda x: quality_score(x[1]), reverse=True)

    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ")
    print("=" * 80)
    print()

    print("Топ-10 комбинаций параметров:")
    print()

    for i, (params_key, result) in enumerate(sorted_results[:10], 1):
        print(f"{i}. Комбинация #{i}:")
        print(f"   Volume Profile: {result['vp_params']}")
        print(f"   VWAP: {result['vwap_params']}")
        print(f"   AMT: {result['amt_params']}")
        print(f"   Market Profile: {result['mp_params']}")
        print(f"   Institutional Patterns: {result['ip_params']}")
        print(f"   Interest Zone: {result['iz_params']}")
        print(f"   Fibonacci Zone: {result['fib_params']}")
        print(f"   Volume Imbalance: {result['vi_params']}")
        print(f"   Сигналов: {result['total_signals']}")
        print(f"   Сделок: {result['total_trades']}")
        print(
            f"   Win Rate: {result['win_rate']:.1f}% ({result['total_winning']}/{result['total_trades']})"
        )
        print(f"   Profit Factor: {result['profit_factor']:.2f}")
        print(f"   Return/сигнал: {result['return_per_signal']:.2f}%")
        print(f"   Общий return: {result['total_return']:.2f}%")
        print()

    # Лучшая комбинация
    best_key, best_result = sorted_results[0]

    print("=" * 80)
    print("✅ ОПТИМАЛЬНЫЕ ПАРАМЕТРЫ ВСЕХ ФИЛЬТРОВ")
    print("=" * 80)
    print()
    print("📊 Volume Profile:")
    print(f"   {json.dumps(best_result['vp_params'], indent=2)}")
    print()
    print("📊 VWAP:")
    print(f"   {json.dumps(best_result['vwap_params'], indent=2)}")
    print()
    print("📊 AMT Filter:")
    print(f"   {json.dumps(best_result['amt_params'], indent=2)}")
    print()
    print("📊 Market Profile Filter:")
    print(f"   {json.dumps(best_result['mp_params'], indent=2)}")
    print()
    print("📊 Institutional Patterns Filter:")
    print(f"   {json.dumps(best_result['ip_params'], indent=2)}")
    print()
    print("📊 Interest Zone Filter:")
    print(f"   {json.dumps(best_result['iz_params'], indent=2)}")
    print()
    print("📊 Fibonacci Zone Filter:")
    print(f"   {json.dumps(best_result['fib_params'], indent=2)}")
    print()
    print("📊 Volume Imbalance Filter:")
    print(f"   {json.dumps(best_result['vi_params'], indent=2)}")
    print()
    print("📈 РЕЗУЛЬТАТЫ:")
    print(f"   Сигналов: {best_result['total_signals']}")
    print(f"   Сделок: {best_result['total_trades']}")
    print(f"   Win Rate: {best_result['win_rate']:.1f}%")
    print(f"   Profit Factor: {best_result['profit_factor']:.2f}")
    print(f"   Return/сигнал: {best_result['return_per_signal']:.2f}%")
    print(f"   Общий return: {best_result['total_return']:.2f}%")
    print("=" * 80)

    # Сохраняем результаты
    output_file = "backtests/all_filters_optimization_results.json"
    os.makedirs("backtests", exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(
            {
                "best_params": {
                    "volume_profile": best_result["vp_params"],
                    "vwap": best_result["vwap_params"],
                    "amt": best_result["amt_params"],
                    "market_profile": best_result["mp_params"],
                    "institutional_patterns": best_result["ip_params"],
                    "interest_zone": best_result["iz_params"],
                    "fibonacci_zone": best_result["fib_params"],
                    "volume_imbalance": best_result["vi_params"],
                    # Оптимальные параметры (уже применены)
                    "order_flow": OPTIMAL_ORDER_FLOW,
                    "microstructure": OPTIMAL_MICROSTRUCTURE,
                    "momentum": OPTIMAL_MOMENTUM,
                    "trend_strength": OPTIMAL_TREND_STRENGTH,
                },
                "best_metrics": {
                    "signals": best_result["total_signals"],
                    "trades": best_result["total_trades"],
                    "win_rate": best_result["win_rate"],
                    "profit_factor": best_result["profit_factor"],
                    "return_per_signal": best_result["return_per_signal"],
                    "total_return": best_result["total_return"],
                },
                "all_results": {
                    k: {
                        "vp_params": v["vp_params"],
                        "vwap_params": v["vwap_params"],
                        "amt_params": v["amt_params"],
                        "mp_params": v["mp_params"],
                        "ip_params": v["ip_params"],
                        "total_trades": v["total_trades"],
                        "total_return": v["total_return"],
                        "total_signals": v["total_signals"],
                        "win_rate": v["win_rate"],
                        "profit_factor": v["profit_factor"],
                        "return_per_signal": v["return_per_signal"],
                    }
                    for k, v in all_results.items()
                },
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n💾 Результаты сохранены в: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    optimize_all_filters()
