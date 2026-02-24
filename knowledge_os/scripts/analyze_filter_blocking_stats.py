#!/usr/bin/env python3
"""
Анализ статистики блокировки сигналов фильтрами
Сравнивает: baseline vs фильтр ПЕРЕД baseline vs фильтр ПОСЛЕ baseline
"""

import json
import os
import sys
from pathlib import Path

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
PERIOD_DAYS = 7


def count_baseline_signals(df, symbol):
    """Подсчитывает сигналы baseline (VP+VWAP, без других фильтров)"""
    from config import USE_VP_FILTER, USE_VWAP_FILTER
    from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter

    os.environ["USE_VP_FILTER"] = "True"
    os.environ["USE_VWAP_FILTER"] = "True"
    os.environ["USE_ORDER_FLOW_FILTER"] = "False"
    os.environ["USE_MICROSTRUCTURE_FILTER"] = "False"
    os.environ["DISABLE_EXTRA_FILTERS"] = "true"
    os.environ["volume_profile_threshold"] = "0.6"
    os.environ["vwap_threshold"] = "0.8"

    if "src.signals.core" in sys.modules:
        del sys.modules["src.signals.core"]
    if "src.signals" in sys.modules:
        del sys.modules["src.signals"]
    if "config" in sys.modules:
        del sys.modules["config"]

    from src.signals.core import soft_entry_signal

    df = add_technical_indicators(df)
    start_idx = 25

    if len(df) < start_idx:
        return 0

    signals = 0
    for i in range(start_idx, len(df)):
        side, entry_price = soft_entry_signal(df, i)
        if side and entry_price:
            signals += 1

    return signals


def count_filter_signals(df, symbol, filter_type, params, before_baseline):
    """Подсчитывает сигналы с фильтром"""
    from config import USE_VP_FILTER, USE_VWAP_FILTER
    from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter

    os.environ["USE_VP_FILTER"] = "True"
    os.environ["USE_VWAP_FILTER"] = "True"
    os.environ["volume_profile_threshold"] = "0.6"
    os.environ["vwap_threshold"] = "0.8"

    if filter_type == "order_flow":
        os.environ["USE_ORDER_FLOW_FILTER"] = "True"
        os.environ["USE_MICROSTRUCTURE_FILTER"] = "False"
    else:
        os.environ["USE_ORDER_FLOW_FILTER"] = "False"
        os.environ["USE_MICROSTRUCTURE_FILTER"] = "True"

    os.environ["DISABLE_EXTRA_FILTERS"] = "false"

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

            # Фильтр ПЕРЕД baseline (проверяем до baseline условий)
            if before_baseline:
                if filter_type == "order_flow":
                    try:
                        of_ok = check_order_flow_with_params(df, i, params)
                        if not of_ok:
                            return None, None  # Фильтр заблокировал - baseline не проверяем
                    except Exception as e:
                        logger.debug("Order Flow ошибка: %s", e)
                        # Если ошибка, пропускаем фильтр
                        pass
                else:  # microstructure
                    try:
                        ms_ok = check_microstructure_with_params(df, i, params)
                        if not ms_ok:
                            return None, None  # Фильтр заблокировал - baseline не проверяем
                    except Exception as e:
                        logger.debug("Microstructure ошибка: %s", e)
                        # Если ошибка, пропускаем фильтр
                        pass

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

            # Ослабленный baseline (70% условий) - как в оптимизации
            required_conditions = int(len(long_conditions) * 0.7)
            long_base_ok = sum(long_conditions) >= required_conditions

            if long_base_ok:
                # Фильтр ПОСЛЕ baseline
                if not before_baseline:
                    if filter_type == "order_flow":
                        of_ok = check_order_flow_with_params(df, i, params)
                        if not of_ok:
                            return None, None
                    else:
                        ms_ok = check_microstructure_with_params(df, i, params)
                        if not ms_ok:
                            return None, None

                return "long", current_price

            return None, None
        except Exception as e:
            logger.error("Ошибка: %s", e)
            return None, None

    core_module.soft_entry_signal = enhanced_soft_entry_signal

    try:
        df = add_technical_indicators(df)
        start_idx = 25

        if len(df) < start_idx:
            return 0

        signals = 0
        for i in range(start_idx, len(df)):
            side, entry_price = soft_entry_signal(df, i)
            if side and entry_price:
                signals += 1

        core_module.soft_entry_signal = original_soft_entry
        return signals
    except Exception as e:
        core_module.soft_entry_signal = original_soft_entry
        raise


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

        # Если required_confirmations = 0, то фильтр очень мягкий
        if params["required_confirmations"] == 0:
            # Проверяем только pr_threshold (если он очень низкий, почти все проходит)
            if pr_value is not None:
                # pr_threshold = 0.5 означает, что пропускаем почти все (только очень слабые блокируем)
                return pr_value > params["pr_threshold"]
            # Если данных нет, пропускаем (очень мягкий режим)
            return True

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


def analyze_filter_blocking():
    """Анализирует статистику блокировки фильтров"""
    print("=" * 80)
    print("📊 АНАЛИЗ БЛОКИРОВКИ СИГНАЛОВ ФИЛЬТРАМИ")
    print("=" * 80)
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print("=" * 80)
    print()

    # Загружаем лучшие параметры из оптимизации
    try:
        with open("backtests/order_flow_optimization_results.json") as f:
            of_results = json.load(f)
            of_best_params = of_results["best_params"]
            print(f"✅ Загружены параметры Order Flow: {of_best_params}")
    except Exception as e:
        of_best_params = {"required_confirmations": 0, "pr_threshold": 0.5}
        print(f"⚠️ Используем параметры по умолчанию для Order Flow: {of_best_params}")

    try:
        with open("backtests/microstructure_optimization_results.json") as f:
            ms_results = json.load(f)
            ms_best_params = ms_results["best_params"]
            print(f"✅ Загружены параметры Microstructure: {ms_best_params}")
    except Exception as e:
        ms_best_params = {"tolerance_pct": 3.0, "min_strength": 0.15, "lookback": 40}
        print(f"⚠️ Используем параметры по умолчанию для Microstructure: {ms_best_params}")

    print()

    total_baseline = 0
    total_of_before = 0
    total_of_after = 0
    total_ms_before = 0
    total_ms_after = 0

    for symbol in TEST_SYMBOLS:
        print(f"\n📊 Анализ {symbol}...")
        try:
            df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
            if df is None or len(df) < 25:
                print("   ❌ Недостаточно данных")
                continue

            baseline = count_baseline_signals(df, symbol)
            of_before = count_filter_signals(
                df, symbol, "order_flow", of_best_params, before_baseline=True
            )
            of_after = count_filter_signals(
                df, symbol, "order_flow", of_best_params, before_baseline=False
            )
            ms_before = count_filter_signals(
                df, symbol, "microstructure", ms_best_params, before_baseline=True
            )
            ms_after = count_filter_signals(
                df, symbol, "microstructure", ms_best_params, before_baseline=False
            )

            total_baseline += baseline
            total_of_before += of_before
            total_of_after += of_after
            total_ms_before += ms_before
            total_ms_after += ms_after

            print(f"   📈 Baseline (VP+VWAP): {baseline} сигналов")
            print(
                f"   🔵 Order Flow ПЕРЕД: {of_before} сигналов (заблокировано: {baseline - of_before}, {((baseline - of_before) / baseline * 100) if baseline > 0 else 0:.1f}%)"
            )
            print(
                f"   🔵 Order Flow ПОСЛЕ: {of_after} сигналов (заблокировано: {baseline - of_after}, {((baseline - of_after) / baseline * 100) if baseline > 0 else 0:.1f}%)"
            )
            print(
                f"   🟢 Microstructure ПЕРЕД: {ms_before} сигналов (заблокировано: {baseline - ms_before}, {((baseline - ms_before) / baseline * 100) if baseline > 0 else 0:.1f}%)"
            )
            print(
                f"   🟢 Microstructure ПОСЛЕ: {ms_after} сигналов (заблокировано: {baseline - ms_after}, {((baseline - ms_after) / baseline * 100) if baseline > 0 else 0:.1f}%)"
            )

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 80)
    print("📊 ИТОГОВАЯ СТАТИСТИКА БЛОКИРОВКИ")
    print("=" * 80)
    print(f"📈 Baseline сигналов (VP+VWAP): {total_baseline}")
    print()
    print("🔵 ORDER FLOW ФИЛЬТР:")
    print(f"   ПЕРЕД baseline: {total_of_before} сигналов")
    print(
        f"   Заблокировано: {total_baseline - total_of_before} ({(total_baseline - total_of_before) / total_baseline * 100 if total_baseline > 0 else 0:.1f}%)"
    )
    print(f"   ПОСЛЕ baseline: {total_of_after} сигналов")
    print(
        f"   Заблокировано: {total_baseline - total_of_after} ({(total_baseline - total_of_after) / total_baseline * 100 if total_baseline > 0 else 0:.1f}%)"
    )
    print()
    print("🟢 MICROSTRUCTURE ФИЛЬТР:")
    print(f"   ПЕРЕД baseline: {total_ms_before} сигналов")
    print(
        f"   Заблокировано: {total_baseline - total_ms_before} ({(total_baseline - total_ms_before) / total_baseline * 100 if total_baseline > 0 else 0:.1f}%)"
    )
    print(f"   ПОСЛЕ baseline: {total_ms_after} сигналов")
    print(
        f"   Заблокировано: {total_baseline - total_ms_after} ({(total_baseline - total_ms_after) / total_baseline * 100 if total_baseline > 0 else 0:.1f}%)"
    )
    print("=" * 80)
    print()

    print("💡 ВЫВОДЫ:")
    of_before_pct = (
        (total_baseline - total_of_before) / total_baseline * 100 if total_baseline > 0 else 0
    )
    of_after_pct = (
        (total_baseline - total_of_after) / total_baseline * 100 if total_baseline > 0 else 0
    )
    ms_before_pct = (
        (total_baseline - total_ms_before) / total_baseline * 100 if total_baseline > 0 else 0
    )
    ms_after_pct = (
        (total_baseline - total_ms_after) / total_baseline * 100 if total_baseline > 0 else 0
    )

    print(f"   Order Flow ПЕРЕД baseline блокирует {of_before_pct:.1f}% сигналов")
    print(f"   Order Flow ПОСЛЕ baseline блокирует {of_after_pct:.1f}% сигналов")
    print(f"   Microstructure ПЕРЕД baseline блокирует {ms_before_pct:.1f}% сигналов")
    print(f"   Microstructure ПОСЛЕ baseline блокирует {ms_after_pct:.1f}% сигналов")


if __name__ == "__main__":
    analyze_filter_blocking()
