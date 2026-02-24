#!/usr/bin/env python3
"""
Детальный отчет по всем сделкам бэктеста
Показывает каждую сделку с прибылью, балансом, убытками и т.д.
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, Optional

import pandas as pd

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импорты
from src.signals.indicators import add_technical_indicators
from src.signals.risk import get_dynamic_sl_level
from src.utils.shared_utils import get_dynamic_tp_levels

# Константы
START_BALANCE = 10000.0
FEE = 0.001  # 0.1%
RISK_PER_TRADE = 0.05  # 5%
DATA_DIR = "data/backtest_data_yearly"
TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
PERIOD_DAYS = 90

# Включаем все фильтры
os.environ["USE_VP_FILTER"] = "true"
os.environ["USE_VWAP_FILTER"] = "true"
os.environ["USE_ORDER_FLOW_FILTER"] = "true"
os.environ["USE_MICROSTRUCTURE_FILTER"] = "true"
os.environ["USE_MOMENTUM_FILTER"] = "true"
os.environ["USE_TREND_STRENGTH_FILTER"] = "true"
os.environ["USE_AMT_FILTER"] = "true"
os.environ["USE_MARKET_PROFILE_FILTER"] = "true"
os.environ["USE_INSTITUTIONAL_PATTERNS_FILTER"] = "true"
os.environ["USE_INTEREST_ZONE_FILTER"] = "true"
os.environ["USE_FIBONACCI_ZONE_FILTER"] = "true"
os.environ["USE_VOLUME_IMBALANCE_FILTER"] = "true"
os.environ["DISABLE_EXTRA_FILTERS"] = "false"


def get_symbol_tp_sl_multipliers(symbol: str) -> tuple:
    """Получает TP/SL multipliers для символа"""
    default_tp_mult = 2.0
    default_sl_mult = 1.5
    return default_tp_mult, default_sl_mult


def load_yearly_data(symbol: str, limit_days: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Загружает годовые данные из CSV"""
    csv_path = os.path.join(DATA_DIR, f"{symbol}.csv")

    if not os.path.exists(csv_path):
        return None

    try:
        df = pd.read_csv(csv_path)

        # Преобразуем timestamp в datetime и делаем индексом (как в backtest_5coins_simple.py)
        if "timestamp" in df.columns:
            try:
                if df["timestamp"].dtype == "int64" or df["timestamp"].dtype == "float64":
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                else:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
            except Exception:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

            df.set_index("timestamp", inplace=True)

        # Сортируем по времени
        df = df.sort_index()

        # Ограничиваем последними N днями
        if limit_days:
            cutoff_date = df.index[-1] - pd.Timedelta(days=limit_days)
            df = df[df.index >= cutoff_date]

        required_cols = ["open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            return None

        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=required_cols)

        # Добавляем timestamp как колонку для удобства доступа
        df["timestamp"] = df.index
        return df

    except Exception as e:
        print(f"Ошибка загрузки данных для {symbol}: {e}")
        return None


def run_detailed_backtest(df: pd.DataFrame, symbol: str, initial_balance: float) -> Dict:
    """Запускает детальный бэктест с сохранением всех сделок (использует логику из backtest_5coins_simple.py)"""

    # Импортируем необходимые модули для monkey patching
    import src.signals.core as core_module
    from scripts.optimize_all_filters_comprehensive import (
        check_amt_with_params,
        check_fibonacci_zone_with_params,
        check_institutional_patterns_with_params,
        check_interest_zone_with_params,
        check_market_profile_with_params,
        check_microstructure_with_params,
        check_momentum_with_params,
        check_order_flow_with_params,
        check_trend_strength_with_params,
        check_volume_imbalance_with_params,
    )
    from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter

    # Оптимальные параметры (как в backtest_5coins_simple.py)
    optimal_order_flow = {"required_confirmations": 0, "pr_threshold": 0.5}
    optimal_microstructure = {"tolerance_pct": 2.5, "min_strength": 0.1, "lookback": 30}
    optimal_momentum = {"mfi_long": 50, "mfi_short": 50, "stoch_long": 50, "stoch_short": 50}
    optimal_trend_strength = {"adx_threshold": 15, "require_direction": False}

    # Параметры по умолчанию (из config.py - оптимальные)
    vp_params = {"volume_profile_threshold": 0.6}
    vwap_params = {"vwap_threshold": 0.6}
    amt_params = {"lookback": 20, "balance_threshold": 0.3, "imbalance_threshold": 0.5}
    mp_params = {"tolerance_pct": 1.5}
    ip_params = {"min_quality_score": 0.6}
    iz_params = {
        "lookback_periods": 50,
        "min_volume_cluster": 1.0,
        "zone_width_pct": 0.3,
        "min_zone_strength": 0.5,
    }
    fib_params = {"lookback_periods": 50, "tolerance_pct": 0.3, "require_strong_levels": False}
    vi_params = {
        "lookback_periods": 10,
        "volume_spike_threshold": 1.5,
        "min_volume_ratio": 1.0,
        "require_volume_confirmation": True,
    }

    # Устанавливаем параметры фильтров
    os.environ["volume_profile_threshold"] = str(vp_params["volume_profile_threshold"])
    os.environ["vwap_threshold"] = str(vwap_params["vwap_threshold"])

    # Сохраняем оригинальную функцию
    original_soft_entry = core_module.soft_entry_signal

    # Создаем enhanced_soft_entry_signal
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
                # Все фильтры
                of_ok = check_order_flow_with_params(df, i, optimal_order_flow)
                if not of_ok:
                    return None, None

                ms_ok = check_microstructure_with_params(df, i, optimal_microstructure)
                if not ms_ok:
                    return None, None

                mom_ok = check_momentum_with_params(df, i, "long", optimal_momentum)
                if not mom_ok:
                    return None, None

                trend_ok = check_trend_strength_with_params(df, i, "long", optimal_trend_strength)
                if not trend_ok:
                    return None, None

                amt_ok = check_amt_with_params(df, i, amt_params)
                if not amt_ok:
                    return None, None

                mp_ok = check_market_profile_with_params(df, i, "long", mp_params)
                if not mp_ok:
                    return None, None

                ip_ok = check_institutional_patterns_with_params(df, i, "long", ip_params)
                if not ip_ok:
                    return None, None

                if os.environ.get("USE_INTEREST_ZONE_FILTER", "false").lower() == "true":
                    iz_ok = check_interest_zone_with_params(df, i, "long", iz_params)
                    if not iz_ok:
                        return None, None

                if os.environ.get("USE_FIBONACCI_ZONE_FILTER", "false").lower() == "true":
                    fib_ok = check_fibonacci_zone_with_params(df, i, "long", fib_params)
                    if not fib_ok:
                        return None, None

                if os.environ.get("USE_VOLUME_IMBALANCE_FILTER", "false").lower() == "true":
                    vi_ok = check_volume_imbalance_with_params(df, i, "long", vi_params)
                    if not vi_ok:
                        return None, None

                return "long", current_price

            return None, None
        except Exception:
            return None, None

    core_module.soft_entry_signal = enhanced_soft_entry_signal

    try:
        df = add_technical_indicators(df)

        if len(df) < 25:
            return {"trades": [], "balance_history": [], "total_return": 0.0}

        start_idx = 25
        balance = initial_balance
        trades = []
        balance_history = []
        signals_generated = 0

        tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)

        for i in range(start_idx, len(df)):
            side, entry_price = core_module.soft_entry_signal(df, i)
            signals_generated += 1 if side else 0

            if side and entry_price:
                try:
                    tp1_pct, _ = get_dynamic_tp_levels(df, i, side)
                    if tp1_pct is None:
                        continue
                    tp1 = entry_price * (1 + tp1_pct / 100 * tp_mult)

                    sl_level_pct = get_dynamic_sl_level(df, i, side)
                    if sl_level_pct is None:
                        continue

                    if side == "long":
                        sl_level = entry_price * (1 - sl_level_pct / 100 * sl_mult)
                    else:
                        sl_level = entry_price * (1 + sl_level_pct / 100 * sl_mult)

                    # Размер позиции
                    balance_before = balance
                    risk_amount = balance * RISK_PER_TRADE
                    sl_distance = abs(entry_price - sl_level)

                    if sl_distance > 0:
                        position_size = risk_amount / sl_distance
                        exit_price = tp1

                        if side == "long":
                            profit = (exit_price - entry_price) * position_size * (1 - FEE)
                        else:
                            profit = (entry_price - exit_price) * position_size * (1 - FEE)

                        balance_after = balance + profit
                        balance = balance_after

                        # Получаем timestamp (из индекса, так как timestamp - это индекс)
                        if hasattr(df.index, "iloc") and i < len(df.index):
                            timestamp = df.index[i]
                        elif "timestamp" in df.columns:
                            timestamp = df.iloc[i]["timestamp"]
                        else:
                            timestamp = None

                        timestamp_str = (
                            timestamp.strftime("%Y-%m-%d %H:%M:%S")
                            if timestamp is not None and hasattr(timestamp, "strftime")
                            else (str(timestamp) if timestamp is not None else f"Candle {i}")
                        )

                        trade = {
                            "trade_num": len(trades) + 1,
                            "timestamp": timestamp_str,
                            "side": side,
                            "entry_price": round(entry_price, 8),
                            "exit_price": round(exit_price, 8),
                            "tp1": round(tp1, 8),
                            "sl_level": round(sl_level, 8),
                            "position_size": round(position_size, 8),
                            "risk_amount": round(risk_amount, 2),
                            "balance_before": round(balance_before, 2),
                            "profit": round(profit, 2),
                            "balance_after": round(balance_after, 2),
                            "profit_pct": round((profit / balance_before) * 100, 2),
                            "is_profitable": bool(profit > 0),  # Явно преобразуем в bool для JSON
                        }

                        trades.append(trade)
                        balance_history.append(
                            {
                                "trade_num": len(trades),
                                "balance": round(balance, 2),
                                "timestamp": trade["timestamp"],
                            }
                        )

                except Exception:
                    continue

        total_return = (
            ((balance - initial_balance) / initial_balance) * 100 if initial_balance > 0 else 0.0
        )

        return {
            "trades": trades,
            "balance_history": balance_history,
            "total_return": total_return,
            "final_balance": balance,
            "signals": signals_generated,
        }

    finally:
        core_module.soft_entry_signal = original_soft_entry


def print_detailed_report(symbol: str, result: Dict, initial_balance: float):
    """Выводит детальный отчет по сделкам"""

    trades = result["trades"]
    if not trades:
        print(f"\n❌ Нет сделок для {symbol}")
        return

    print(f"\n{'=' * 120}")
    print(f"📊 ДЕТАЛЬНЫЙ ОТЧЕТ: {symbol}")
    print(f"{'=' * 120}")
    print(f"Начальный баланс: ${initial_balance:,.2f}")
    print(f"Финальный баланс: ${result['final_balance']:,.2f}")
    print(f"Доходность: {result['total_return']:+.2f}%")
    print(f"Всего сделок: {len(trades)}")
    print(f"Прибыльных: {sum(1 for t in trades if t['is_profitable'])}")
    print(f"Убыточных: {sum(1 for t in trades if not t['is_profitable'])}")
    print(f"{'=' * 120}\n")

    # Таблица сделок
    header = (
        f"{'№':<4} {'Дата/Время':<20} {'Сторона':<6} {'Вход':<12} {'Выход':<12} "
        f"{'TP1':<12} {'SL':<12} {'Размер':<12} {'Риск $':<10} {'Баланс до':<12} "
        f"{'Прибыль $':<12} {'Прибыль %':<10} {'Баланс после':<12}"
    )
    print(header)
    print("-" * 120)

    for trade in trades:
        profit_str = (
            f"${trade['profit']:,.2f}"
            if trade["is_profitable"]
            else f"-${abs(trade['profit']):,.2f}"
        )
        profit_pct_str = (
            f"+{trade['profit_pct']:.2f}%"
            if trade["is_profitable"]
            else f"{trade['profit_pct']:.2f}%"
        )

        print(
            f"{trade['trade_num']:<4} "
            f"{trade['timestamp']:<20} "
            f"{trade['side'].upper():<6} "
            f"${trade['entry_price']:<11.8f} "
            f"${trade['exit_price']:<11.8f} "
            f"${trade['tp1']:<11.8f} "
            f"${trade['sl_level']:<11.8f} "
            f"{trade['position_size']:<12.4f} "
            f"${trade['risk_amount']:<9.2f} "
            f"${trade['balance_before']:<11.2f} "
            f"{profit_str:<12} "
            f"{profit_pct_str:<10} "
            f"${trade['balance_after']:<11.2f}"
        )

    print("-" * 120)

    # Итоговая статистика
    total_profit = sum(t["profit"] for t in trades)
    avg_profit = total_profit / len(trades) if trades else 0
    max_profit = max((t["profit"] for t in trades), default=0)
    min_profit = min((t["profit"] for t in trades), default=0)

    print("\n📈 СТАТИСТИКА:")
    print(f"   Общая прибыль: ${total_profit:,.2f}")
    print(f"   Средняя прибыль на сделку: ${avg_profit:,.2f}")
    print(f"   Максимальная прибыль: ${max_profit:,.2f}")
    print(f"   Минимальная прибыль: ${min_profit:,.2f}")
    print(f"   Win Rate: {(sum(1 for t in trades if t['is_profitable']) / len(trades) * 100):.2f}%")


def main():
    """Главная функция"""
    print("=" * 120)
    print("👥 КОМАНДА ИЗ 13 ЭКСПЕРТОВ - ДЕТАЛЬНЫЙ ОТЧЕТ ПО СДЕЛКАМ")
    print("=" * 120)
    print(f"📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Период: {PERIOD_DAYS} дней")
    print(f"💰 Начальный баланс: ${START_BALANCE:,.2f}")
    print(f"📈 Монет: {len(TEST_SYMBOLS)}")
    print("=" * 120)

    all_results = {}
    total_initial = START_BALANCE
    total_final = 0.0

    for symbol in TEST_SYMBOLS:
        print(f"\n🔄 Обработка {symbol}...")

        df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
        if df is None or len(df) < 25:
            print(f"❌ Недостаточно данных для {symbol}")
            continue

        balance_per_coin = START_BALANCE / len(TEST_SYMBOLS)
        result = run_detailed_backtest(df, symbol, balance_per_coin)

        all_results[symbol] = result
        total_final += result["final_balance"]

        # Выводим детальный отчет
        print_detailed_report(symbol, result, balance_per_coin)

    # Итоговый отчет
    print(f"\n{'=' * 120}")
    print("📊 ИТОГО ПО ПОРТФЕЛЮ")
    print(f"{'=' * 120}")
    print(f"Начальный баланс: ${total_initial:,.2f}")
    print(f"Финальный баланс: ${total_final:,.2f}")
    print(f"Общая прибыль: ${total_final - total_initial:,.2f}")
    print(f"Общая доходность: {((total_final - total_initial) / total_initial * 100):+.2f}%")
    print(f"Всего сделок: {sum(len(r['trades']) for r in all_results.values())}")
    print(f"{'=' * 120}\n")

    # Сохраняем в JSON (преобразуем bool в int для совместимости)
    output_file = (
        f"backtests/detailed_trades_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    json_data = {
        "period_days": PERIOD_DAYS,
        "total_initial": total_initial,
        "total_final": total_final,
        "symbols": {},
    }
    for s, r in all_results.items():
        # Преобразуем trades для JSON (bool -> int)
        trades_json = []
        for trade in r["trades"]:
            trade_json = trade.copy()
            trade_json["is_profitable"] = 1 if trade_json.get("is_profitable", False) else 0
            trades_json.append(trade_json)

        json_data["symbols"][s] = {
            "trades": trades_json,
            "balance_history": r["balance_history"],
            "total_return": r["total_return"],
            "final_balance": r["final_balance"],
        }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)

    print(f"✅ Детальный отчет сохранен в: {output_file}")


if __name__ == "__main__":
    main()
