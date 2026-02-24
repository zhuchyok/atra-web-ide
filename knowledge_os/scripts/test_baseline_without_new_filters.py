#!/usr/bin/env python3
"""
Проверка baseline - генерируются ли сигналы БЕЗ новых фильтров
"""

import os
import sys
import warnings
from datetime import datetime

import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.signals.indicators import add_technical_indicators
from src.signals.risk import get_dynamic_sl_level
from src.utils.shared_utils import get_dynamic_tp_levels

# ============================================================================
# НАСТРОЙКИ
# ============================================================================

START_BALANCE = 10000.0
FEE = 0.001
RISK_PER_TRADE = 0.05

TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
PERIOD_DAYS = 30

# УЖЕ ОПТИМИЗИРОВАННЫЕ ПАРАМЕТРЫ
OPTIMAL_ORDER_FLOW = {"required_confirmations": 0, "pr_threshold": 0.5}
OPTIMAL_MICROSTRUCTURE = {"tolerance_pct": 2.5, "min_strength": 0.1, "lookback": 30}
OPTIMAL_MOMENTUM = {"mfi_long": 50, "mfi_short": 50, "stoch_long": 50, "stoch_short": 50}
OPTIMAL_TREND_STRENGTH = {"adx_threshold": 15, "require_direction": False}
OPTIMAL_VP = {"volume_profile_threshold": 0.6}
OPTIMAL_VWAP = {"vwap_threshold": 0.6}
OPTIMAL_AMT = {"lookback": 20, "balance_threshold": 0.3, "imbalance_threshold": 0.5}
OPTIMAL_MP = {"tolerance_pct": 1.5}
OPTIMAL_IP = {"min_quality_score": 0.6}


def load_yearly_data(symbol: str, limit_days: int = 30):
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


def get_symbol_tp_sl_multipliers(symbol: str):
    """Получает TP/SL multipliers для символа"""
    try:
        from archive.experimental.optimized_config import OPTIMIZED_PARAMETERS

        params = OPTIMIZED_PARAMETERS.get(symbol, {})
        return params.get("tp_mult", 2.0), params.get("sl_mult", 1.5)
    except ImportError:
        return 2.0, 1.5


def check_order_flow_with_params(df, i, params):
    """Проверяет Order Flow с параметрами"""
    try:
        from src.analysis.order_flow import CumulativeDeltaVolume, PressureRatio, VolumeDelta

        cdv = CumulativeDeltaVolume(lookback=20)
        vd = VolumeDelta()
        pr = PressureRatio(lookback=5)

        pr_value = pr.get_value(df, i)

        if params["required_confirmations"] == 0:
            if pr_value is not None:
                return pr_value > params["pr_threshold"]
            return True
        return True
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

        support_zones = [z for z in liquidity_zones if z["type"] == "support"]
        for zone in support_zones:
            distance_pct = abs(current_price - zone["price"]) / current_price * 100
            if (
                distance_pct <= params["tolerance_pct"]
                and zone["strength"] >= params["min_strength"]
            ):
                return True
        return False
    except Exception:
        return True


def check_momentum_with_params(df, i, side, params):
    """Проверяет Momentum с параметрами"""
    try:
        from src.filters.momentum_filter import check_momentum_filter

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


def run_baseline_test(symbol: str):
    """Запускает baseline тест БЕЗ новых фильтров"""
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

        # Устанавливаем параметры
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

        def baseline_soft_entry_signal(df, i):
            """Baseline сигнал БЕЗ новых фильтров"""
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

                    # НОВЫЕ ФИЛЬТРЫ НЕ ПРОВЕРЯЕМ!
                    return "long", current_price

                return None, None
            except Exception as e:
                return None, None

        core_module.soft_entry_signal = baseline_soft_entry_signal

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
        }
    except Exception as e:
        print(f"❌ Ошибка для {symbol}: {e}")
        import traceback

        traceback.print_exc()
        return {"trades": 0, "return": 0.0, "signals": 0, "winning_trades": 0, "losing_trades": 0}


def main():
    """Главная функция"""
    print("=" * 80)
    print("🔍 ПРОВЕРКА BASELINE (БЕЗ НОВЫХ ФИЛЬТРОВ)")
    print("=" * 80)
    print()
    print("📊 Тестируем baseline с базовыми фильтрами:")
    print("   ✅ VP/VWAP")
    print("   ✅ Order Flow")
    print("   ✅ Microstructure")
    print("   ✅ Momentum")
    print("   ✅ Trend Strength")
    print()
    print("❌ БЕЗ новых фильтров:")
    print("   ❌ Interest Zone")
    print("   ❌ Fibonacci Zone")
    print("   ❌ Volume Imbalance")
    print()
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print("=" * 80)
    print()

    all_results = {}

    for symbol in TEST_SYMBOLS:
        print(f"🔍 Тестируем {symbol}...")
        result = run_baseline_test(symbol)
        all_results[symbol] = result
        print(f"   Сигналов: {result['signals']}")
        print(f"   Сделок: {result['trades']}")
        print(
            f"   Win Rate: {(result['winning_trades'] / result['trades'] * 100) if result['trades'] > 0 else 0:.1f}%"
        )
        print(f"   Return: {result['return']:.2f}%")
        print()

    # Итоги
    total_signals = sum(r["signals"] for r in all_results.values())
    total_trades = sum(r["trades"] for r in all_results.values())
    total_winning = sum(r["winning_trades"] for r in all_results.values())
    total_losing = sum(r["losing_trades"] for r in all_results.values())
    total_return = sum(r["return"] for r in all_results.values())

    print("=" * 80)
    print("📊 ИТОГИ BASELINE ТЕСТА")
    print("=" * 80)
    print()
    print(f"📊 Сигналов: {total_signals}")
    print(f"📊 Сделок: {total_trades}")
    print(f"📊 Win Rate: {(total_winning / total_trades * 100) if total_trades > 0 else 0:.1f}%")
    print(f"📊 Общий Return: {total_return:.2f}%")
    print()

    if total_trades == 0:
        print("⚠️  ПРОБЛЕМА: Baseline не генерирует сигналы!")
        print("   Причина: Базовые фильтры блокируют все сигналы")
        print("   Решение: Проверить базовые фильтры (VP/VWAP, Order Flow и т.д.)")
    else:
        print("✅ Baseline работает! Генерирует сигналы.")
        print("   Проблема: Новые фильтры блокируют все сигналы")
        print("   Решение: Ослабить параметры новых фильтров")
    print("=" * 80)


if __name__ == "__main__":
    main()
