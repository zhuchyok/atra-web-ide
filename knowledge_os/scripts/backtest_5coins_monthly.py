#!/usr/bin/env python3
"""
Месячный бэктест для 5 монет с включенными всеми фильтрами
BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT
"""

import json
import os
import sys
import warnings
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ВКЛЮЧАЕМ ВСЕ ФИЛЬТРЫ
os.environ["USE_VP_FILTER"] = "true"
os.environ["USE_VWAP_FILTER"] = "true"
os.environ["USE_ORDER_FLOW_FILTER"] = "true"
os.environ["USE_MICROSTRUCTURE_FILTER"] = "true"
os.environ["USE_MOMENTUM_FILTER"] = "true"
os.environ["USE_TREND_STRENGTH_FILTER"] = "true"
os.environ["USE_EXHAUSTION_FILTER"] = "false"  # Только для выхода

# Импорты системы (после установки переменных окружения)
from src.signals.core import soft_entry_signal, strict_entry_signal
from src.signals.indicators import add_technical_indicators
from src.signals.risk import get_dynamic_sl_level
from src.utils.shared_utils import get_dynamic_tp_levels

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
RISK_PER_TRADE = 0.02  # 2% риск на сделку

DEFAULT_TP_MULT = 2.0
DEFAULT_SL_MULT = 1.5

TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]


def get_symbol_tp_sl_multipliers(symbol: str) -> tuple:
    """Получает оптимизированные TP/SL multipliers для символа"""
    if OPTIMIZED_PARAMS_AVAILABLE:
        params = OPTIMIZED_PARAMETERS.get(symbol, {})
        tp_mult = params.get("tp_mult", DEFAULT_TP_MULT)
        sl_mult = params.get("sl_mult", DEFAULT_SL_MULT)
        if symbol in OPTIMIZED_PARAMETERS:
            print(
                f"✅ Используем оптимизированные параметры для {symbol}: TP={tp_mult:.2f}x, SL={sl_mult:.2f}x"
            )
        return tp_mult, sl_mult
    return DEFAULT_TP_MULT, DEFAULT_SL_MULT


# Путь к историческим данным
DATA_DIR = "data/backtest_data_yearly"

# ============================================================================
# КЛАСС ДЛЯ СТАТИСТИКИ
# ============================================================================


class BacktestStats:
    """Статистика бэктеста"""

    def __init__(self, name: str):
        self.name = name
        self.trades = []
        self.balance = START_BALANCE
        self.initial_balance = START_BALANCE
        self.max_balance = START_BALANCE
        self.min_balance = START_BALANCE
        self.max_drawdown = 0.0
        self.max_drawdown_pct = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_loss = 0.0
        self.max_profit = 0.0
        self.max_loss = 0.0
        self.signals_generated = 0
        self.signals_executed = 0

    def add_trade(self, trade: dict):
        """Добавляет сделку"""
        self.trades.append(trade)
        self.total_trades += 1

        profit = trade.get("profit", 0)
        if profit > 0:
            self.winning_trades += 1
            self.total_profit += profit
            self.max_profit = max(self.max_profit, profit)
        else:
            self.losing_trades += 1
            self.total_loss += abs(profit)
            self.max_loss = min(self.max_loss, profit)

        self.balance += profit
        self.max_balance = max(self.max_balance, self.balance)
        self.min_balance = min(self.min_balance, self.balance)

        # Обновляем максимальную просадку
        if self.max_balance > 0:
            current_dd = ((self.max_balance - self.balance) / self.max_balance) * 100
            if current_dd > self.max_drawdown_pct:
                self.max_drawdown_pct = current_dd
                self.max_drawdown = self.max_balance - self.balance

    def get_metrics(self) -> dict:
        """Возвращает метрики"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0.0
        profit_factor = self.total_profit / self.total_loss if self.total_loss > 0 else float("inf")
        total_return = ((self.balance - self.initial_balance) / self.initial_balance) * 100

        # Sharpe Ratio (исправленный расчет)
        # ⚠️ ВАЖНО: Sharpe = (R_p - R_f) / σ_p, где R_p = total_return, R_f = 0
        # Правильная формула использует общую доходность портфеля, а не средний profit_pct
        if len(self.trades) > 1:
            returns = [t.get("profit_pct", 0) for t in self.trades]
            std_return = np.std(returns)

            if std_return > 0:
                # Используем общую доходность портфеля (total_return в %)
                annualized_return_pct = total_return * 12  # Годовая доходность (%)
                annualized_volatility_pct = std_return * np.sqrt(365)  # Годовая волатильность (%)
                sharpe_ratio = (
                    annualized_return_pct / annualized_volatility_pct
                    if annualized_volatility_pct > 0
                    else 0.0
                )
            else:
                sharpe_ratio = 0.0

            # КРИТИЧЕСКАЯ ПРОВЕРКА: Sharpe должен иметь тот же знак, что и общая доходность
            if total_return < 0:
                sharpe_ratio = min(0.0, sharpe_ratio)  # Принудительно делаем отрицательным или 0
            elif total_return == 0:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0

        return {
            "name": self.name,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_return": total_return,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "final_balance": self.balance,
            "total_profit": self.total_profit,
            "total_loss": self.total_loss,
            "signals_generated": self.signals_generated,
            "signals_executed": self.signals_executed,
        }

    def print_summary(self):
        """Выводит сводку"""
        metrics = self.get_metrics()
        print(f"\n{'=' * 80}")
        print(f"📊 {self.name}")
        print(f"{'=' * 80}")
        print(f"💰 Финальный баланс: ${metrics['final_balance']:.2f}")
        print(f"📈 Общая доходность: {metrics['total_return']:.2f}%")
        print(f"📊 Всего сделок: {metrics['total_trades']}")
        print(f"✅ Прибыльных: {metrics['winning_trades']} ({metrics['win_rate']:.2f}%)")
        print(f"❌ Убыточных: {metrics['losing_trades']}")
        print(f"💵 Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"📉 Макс. просадка: {metrics['max_drawdown_pct']:.2f}%")
        print(f"📊 Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"🎯 Сигналов сгенерировано: {metrics['signals_generated']}")
        print(f"✅ Сигналов исполнено: {metrics['signals_executed']}")


# ============================================================================
# ФУНКЦИИ ЗАГРУЗКИ ДАННЫХ
# ============================================================================


def load_yearly_data(symbol: str, limit_days: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Загружает годовые данные из CSV"""
    csv_path = os.path.join(DATA_DIR, f"{symbol}.csv")

    if not os.path.exists(csv_path):
        print(f"⚠️ Файл не найден: {csv_path}")
        return None

    try:
        df = pd.read_csv(csv_path)

        # Преобразуем timestamp в datetime
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

        # Ограничиваем последними N днями (если указано)
        if limit_days:
            cutoff_date = df.index[-1] - timedelta(days=limit_days)
            df = df[df.index >= cutoff_date]

        # Убеждаемся, что есть нужные колонки
        required_cols = ["open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            print(f"⚠️ Отсутствуют необходимые колонки в {symbol}")
            return None

        # Преобразуем в float
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

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


# ============================================================================
# ФУНКЦИИ БЭКТЕСТА
# ============================================================================


def run_backtest(df: pd.DataFrame, symbol: str = "UNKNOWN", mode: str = "soft") -> BacktestStats:
    """Запускает бэктест с включенными всеми фильтрами"""

    stats = BacktestStats(f"{symbol} годовой ({mode}, все фильтры)")

    # Добавляем технические индикаторы
    df = add_technical_indicators(df.copy())

    # Проверяем наличие необходимых колонок
    required_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ema7",
        "ema25",
        "rsi",
        "macd",
        "bb_upper",
        "bb_lower",
        "atr",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"⚠️ Отсутствуют колонки: {missing_cols}")
        return stats

    # Получаем оптимизированные параметры
    tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)

    # Начальный индекс
    start_idx = 100

    if len(df) < start_idx:
        print(f"⚠️ Недостаточно данных: {len(df)} < {start_idx}")
        return stats

    position = None

    # Проходим по всем свечам
    for i in range(start_idx, len(df)):
        current_price = df["close"].iloc[i]
        current_time = df.index[i]

        # Проверяем выход из позиции с продвинутой логикой
        if position is not None:
            assert isinstance(position, dict)
            exit_price = None
            partial_close = False

            entry_price = position["entry_price"]
            tp1 = position.get("tp1", position.get("tp"))
            tp2 = position.get("tp2")
            sl = position["sl"]
            side = position["side"]

            # Рассчитываем прогресс к TP1
            if side == "LONG":
                if tp1 > entry_price:
                    progress_to_tp1 = (current_price - entry_price) / (tp1 - entry_price)
                else:
                    progress_to_tp1 = 0
            else:  # SHORT
                if tp1 < entry_price:
                    progress_to_tp1 = (entry_price - current_price) / (entry_price - tp1)
                else:
                    progress_to_tp1 = 0

            # ПРОДВИНУТАЯ ЛОГИКА ПЕРЕМЕЩЕНИЯ SL
            # 1. При 30% движения к TP1
            if progress_to_tp1 >= 0.3 and not position.get("sl_moved_30", False):
                position["sl_moved_30"] = True
                if side == "LONG":
                    new_sl = entry_price + (tp1 - entry_price) * 0.3
                    new_sl = max(new_sl, entry_price * 1.001)
                    sl = max(sl, new_sl)
                else:
                    new_sl = entry_price - (entry_price - tp1) * 0.3
                    new_sl = min(new_sl, entry_price * 0.999)
                    sl = min(sl, new_sl)
                position["sl"] = sl

            # 2. При 50% движения к TP1
            if progress_to_tp1 >= 0.5 and not position.get("sl_moved_50", False):
                position["sl_moved_50"] = True
                if side == "LONG":
                    new_sl = entry_price + (tp1 - entry_price) * 0.5
                    new_sl = max(new_sl, entry_price * 1.001)
                    sl = max(sl, new_sl)
                else:
                    new_sl = entry_price - (entry_price - tp1) * 0.5
                    new_sl = min(new_sl, entry_price * 0.999)
                    sl = min(sl, new_sl)
                position["sl"] = sl

            # 3. При достижении TP1 - перемещаем SL в безубыток
            if progress_to_tp1 >= 1.0 and not position.get("sl_moved_to_be", False):
                position["sl_moved_to_be"] = True
                if side == "LONG":
                    sl = entry_price * 1.003  # +0.3% комиссия
                else:
                    sl = entry_price * 0.997  # -0.3% комиссия
                position["sl"] = sl

            # Проверяем выходы
            if side == "LONG":
                if current_price <= sl:
                    exit_price = sl
                    exit_reason = "SL"
                elif current_price >= tp1 and not position.get("tp1_executed", False):
                    position["tp1_executed"] = True
                    partial_close = True
                    exit_price = tp1
                    exit_reason = "TP1 (50%)"
                elif position.get("tp1_executed", False) and current_price >= tp2:
                    exit_price = tp2
                    exit_reason = "TP2 (50%)"
            else:  # SHORT
                if current_price >= sl:
                    exit_price = sl
                    exit_reason = "SL"
                elif current_price <= tp1 and not position.get("tp1_executed", False):
                    position["tp1_executed"] = True
                    partial_close = True
                    exit_price = tp1
                    exit_reason = "TP1 (50%)"
                elif position.get("tp1_executed", False) and current_price <= tp2:
                    exit_price = tp2
                    exit_reason = "TP2 (50%)"

            if exit_price:
                # Рассчитываем прибыль
                if side == "LONG":
                    profit_pct = ((exit_price - entry_price) / entry_price) * 100
                else:
                    profit_pct = ((entry_price - exit_price) / entry_price) * 100

                # Учитываем комиссии
                profit_pct -= FEE * 2  # Вход и выход
                profit_pct -= SLIPPAGE * 2

                # Если частичный выход, учитываем только 50%
                if partial_close:
                    profit_pct = profit_pct * 0.5
                    position["entry_price"] = entry_price
                    position["size"] = position.get("size", 1.0) * 0.5
                else:
                    # Полный выход
                    profit = (profit_pct / 100) * position.get(
                        "size", START_BALANCE * RISK_PER_TRADE
                    )
                    stats.add_trade(
                        {
                            "entry_time": position["entry_time"],
                            "exit_time": current_time,
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "side": side,
                            "profit": profit,
                            "profit_pct": profit_pct,
                            "exit_reason": exit_reason,
                        }
                    )
                    position = None
                    continue

        # Если нет позиции, ищем вход
        if position is None:
            # Генерируем сигнал
            signal_side, signal_price = (
                soft_entry_signal(df, i) if mode == "soft" else strict_entry_signal(df, i)
            )
            stats.signals_generated += 1

            if signal_side:
                side = signal_side
                entry_price = signal_price if signal_price else current_price

                # Получаем динамические TP/SL уровни
                try:
                    tp_levels = get_dynamic_tp_levels(df, i, side, use_ai=True)
                    sl_level = get_dynamic_sl_level(df, i, side, use_ai=True)

                    if tp_levels and sl_level:
                        tp1 = tp_levels.get("tp1")
                        tp2 = tp_levels.get("tp2")
                        sl = sl_level
                    else:
                        # Fallback на оптимизированные параметры
                        atr = df["atr"].iloc[i]
                        if side == "LONG":
                            tp1 = entry_price + (atr * tp_mult)
                            tp2 = entry_price + (atr * tp_mult * 1.5)
                            sl = entry_price - (atr * sl_mult)
                        else:
                            tp1 = entry_price - (atr * tp_mult)
                            tp2 = entry_price - (atr * tp_mult * 1.5)
                            sl = entry_price + (atr * sl_mult)
                except Exception:
                    # Fallback на оптимизированные параметры
                    atr = df["atr"].iloc[i]
                    if side == "LONG":
                        tp1 = entry_price + (atr * tp_mult)
                        tp2 = entry_price + (atr * tp_mult * 1.5)
                        sl = entry_price - (atr * sl_mult)
                    else:
                        tp1 = entry_price - (atr * tp_mult)
                        tp2 = entry_price - (atr * tp_mult * 1.5)
                        sl = entry_price + (atr * sl_mult)

                # Открываем позицию
                position = {
                    "entry_time": current_time,
                    "entry_price": entry_price,
                    "tp1": tp1,
                    "tp2": tp2,
                    "sl": sl,
                    "side": side,
                    "size": START_BALANCE * RISK_PER_TRADE,
                    "sl_moved_30": False,
                    "sl_moved_50": False,
                    "sl_moved_to_be": False,
                    "tp1_executed": False,
                }
                stats.signals_executed += 1

    # Закрываем открытую позицию в конце
    if position is not None:
        final_price = df["close"].iloc[-1]
        entry_price = position["entry_price"]
        side = position["side"]

        if side == "LONG":
            profit_pct = ((final_price - entry_price) / entry_price) * 100
        else:
            profit_pct = ((entry_price - final_price) / entry_price) * 100

        profit_pct -= (FEE * 2) + (SLIPPAGE * 2)
        profit = (profit_pct / 100) * position.get("size", START_BALANCE * RISK_PER_TRADE)

        stats.add_trade(
            {
                "entry_time": position["entry_time"],
                "exit_time": df.index[-1],
                "entry_price": entry_price,
                "exit_price": final_price,
                "side": side,
                "profit": profit,
                "profit_pct": profit_pct,
                "exit_reason": "End of data",
            }
        )

    return stats


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================


def main():
    """Главная функция"""
    print("🚀 ГОДОВОЙ БЭКТЕСТ 5 МОНЕТ С ВСЕМИ ФИЛЬТРАМИ")
    print("=" * 80)
    print(f"📅 Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальный баланс: ${START_BALANCE:.2f}")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print("📅 Период: годовые данные")
    print("=" * 80)
    print("")
    print("✅ ВКЛЮЧЕНЫ ВСЕ ФИЛЬТРЫ:")
    print("   - Volume Profile (VP)")
    print("   - VWAP")
    print("   - Order Flow")
    print("   - Microstructure")
    print("   - Momentum")
    print("   - Trend Strength")
    print("")

    all_results = []

    # Тестируем каждую монету
    for idx, symbol in enumerate(TEST_SYMBOLS, 1):
        print(f"\n{'=' * 80}")
        print(f"📈 Тестирование {symbol} ({idx}/{len(TEST_SYMBOLS)})")
        print(f"{'=' * 80}")

        # Загружаем годовые данные
        df = load_yearly_data(symbol, limit_days=None)
        if df is None or len(df) < 100:
            print(f"❌ Недостаточно данных для {symbol}")
            continue

        # Запускаем бэктест
        print(f"🔵 Запуск бэктеста для {symbol}...")
        stats = run_backtest(df, symbol=symbol, mode="soft")
        stats.print_summary()

        # Сохраняем метрики
        metrics = stats.get_metrics()
        metrics["symbol"] = symbol
        metrics["period_days"] = None  # Годовые данные
        metrics["all_filters_enabled"] = True
        all_results.append(metrics)

    # Сохраняем результаты
    results_file = f"backtests/5coins_yearly_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("backtests", exist_ok=True)

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Итоговая сводка
    print(f"\n{'=' * 80}")
    print("📊 ИТОГОВАЯ СВОДКА")
    print(f"{'=' * 80}")

    total_initial = 0
    total_final = 0
    total_trades = 0
    total_signals = 0
    total_executed = 0

    for result in all_results:
        symbol = result.get("symbol", "N/A")
        initial = START_BALANCE
        final = result.get("final_balance", 0)
        return_pct = result.get("total_return", 0)
        trades = result.get("total_trades", 0)
        signals = result.get("signals_generated", 0)
        executed = result.get("signals_executed", 0)

        total_initial += initial
        total_final += final
        total_trades += trades
        total_signals += signals
        total_executed += executed

        print(f"\n{symbol}:")
        print(f"  💰 Баланс: ${initial:.2f} → ${final:.2f}")
        print(f"  📈 Доходность: {return_pct:+.2f}%")
        print(f"  📊 Сделок: {trades}")
        print(f"  🎯 Сигналов: {signals} (исполнено: {executed})")

    print(f"\n{'=' * 80}")
    total_profit = total_final - total_initial
    total_return_pct = (total_profit / total_initial) * 100 if total_initial > 0 else 0
    print("📊 ИТОГО ПОРТФЕЛЯ:")
    print(f"  Начальный баланс: ${total_initial:.2f}")
    print(f"  Финальный баланс: ${total_final:.2f}")
    print(f"  Общая прибыль: ${total_profit:+.2f}")
    print(f"  Общая доходность: {total_return_pct:+.2f}%")
    print(f"  Всего сделок: {total_trades}")
    print(f"  Всего сигналов: {total_signals} (исполнено: {total_executed})")
    print(f"{'=' * 80}")

    print(f"\n✅ Результаты сохранены в {results_file}")
    print("\n🎉 БЭКТЕСТ ЗАВЕРШЕН!")


if __name__ == "__main__":
    main()
