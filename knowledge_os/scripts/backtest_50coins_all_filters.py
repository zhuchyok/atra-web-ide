#!/usr/bin/env python3
"""
Месячный бэктест для 50 монет со ВСЕМИ ФИЛЬТРАМИ (включая новые оптимизированные)
Топ 1-50 монет по капитализации
"""

import glob
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

# ВКЛЮЧАЕМ ВСЕ ФИЛЬТРЫ (включая новые оптимизированные)
os.environ["USE_VP_FILTER"] = "true"
os.environ["USE_VWAP_FILTER"] = "true"
os.environ["USE_ORDER_FLOW_FILTER"] = "true"
os.environ["USE_MICROSTRUCTURE_FILTER"] = "true"
os.environ["USE_MOMENTUM_FILTER"] = "true"
os.environ["USE_TREND_STRENGTH_FILTER"] = "true"
os.environ["USE_AMT_FILTER"] = "true"
os.environ["USE_MARKET_PROFILE_FILTER"] = "true"
os.environ["USE_INSTITUTIONAL_PATTERNS_FILTER"] = "true"
os.environ["USE_INTEREST_ZONE_FILTER"] = "true"  # НОВЫЙ
os.environ["USE_FIBONACCI_ZONE_FILTER"] = "true"  # НОВЫЙ
os.environ["USE_VOLUME_IMBALANCE_FILTER"] = "true"  # НОВЫЙ
os.environ["USE_EXHAUSTION_FILTER"] = "false"  # Только для выхода
os.environ["DISABLE_EXTRA_FILTERS"] = "false"  # Включаем все фильтры

# Импорты системы (после установки переменных окружения)
from src.ai.intelligent_filter_system import (
    IntelligentFilterSystem,
    MarketConditions,
    get_intelligent_filter_system,
    get_symbol_specific_parameters,
)
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
RISK_PER_TRADE = 0.05  # 5% риск на сделку

DEFAULT_TP_MULT = 2.0
DEFAULT_SL_MULT = 1.5


PERIOD_DAYS = 30  # 1 месяц

# Путь к историческим данным
DATA_DIR = "data/backtest_data_yearly"

# Используем только монеты, для которых есть данные
# Сначала получаем список доступных монет
available_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
available_symbols = [os.path.basename(f).replace(".csv", "") for f in available_files]

# Топ 50 монет по капитализации (только те, для которых есть данные)
PREFERRED_SYMBOLS = [
    # Топ 1-10
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "ADAUSDT",
    "XRPUSDT",
    "AVAXUSDT",
    "DOGEUSDT",
    "DOTUSDT",
    "LINKUSDT",
    # Топ 11-20
    "LTCUSDT",
    "TRXUSDT",
    "UNIUSDT",
    "NEARUSDT",
    "SUIUSDT",
    "PEPEUSDT",
    "ENAUSDT",
    "ICPUSDT",
    "FETUSDT",
    "HBARUSDT",
    # Топ 21-30
    "BCHUSDT",
    "STRKUSDT",
    "TAOUSDT",
    "PENGUUSDT",
    "ALLOUSDT",
    "ASTERUSDT",
    "MMTUSDT",
    "PUMPUSDT",
    "TNSRUSDT",
    "WLFIUSDT",
    # Топ 31-40
    "XPLUSDT",
    "ZECUSDT",
    "PAXGUSDT",
    "USDEUSDT",
    "TONUSDT",
    "MATICUSDT",
    "ATOMUSDT",
    "ETCUSDT",
    "FILUSDT",
    "OPUSDT",
    # Топ 41-50
    "APTUSDT",
    "ARBUSDT",
    "WLDUSDT",
    "SEIUSDT",
    "CFXUSDT",
    "BONKUSDT",
    "WIFUSDT",
    "FLOKIUSDT",
    "SHIBUSDT",
    "CRVUSDT",
]

# Фильтруем только те, для которых есть данные
TEST_SYMBOLS = [s for s in PREFERRED_SYMBOLS if s in available_symbols]

# Если меньше 50, добавляем остальные доступные
if len(TEST_SYMBOLS) < 50:
    remaining = [s for s in available_symbols if s not in TEST_SYMBOLS]
    TEST_SYMBOLS.extend(remaining[: 50 - len(TEST_SYMBOLS)])

# Ограничиваем до 50
TEST_SYMBOLS = TEST_SYMBOLS[:50]

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
        self.signals_rejected_by_intelligent = 0

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
            drawdown = (self.max_balance - self.balance) / self.max_balance
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown
                self.max_drawdown_pct = drawdown * 100

    def get_metrics(self) -> dict:
        """Возвращает метрики"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        profit_factor = (
            (self.total_profit / self.total_loss)
            if self.total_loss > 0
            else float("inf")
            if self.total_profit > 0
            else 0
        )
        total_return = ((self.balance - self.initial_balance) / self.initial_balance) * 100

        # Sharpe Ratio (для крипто 24/7 используем sqrt(365))
        if len(self.trades) > 1:
            returns = [t.get("profit", 0) / self.initial_balance for t in self.trades]
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (mean_return / std_return * np.sqrt(365)) if std_return > 0 else 0
        else:
            sharpe = 0

        return_per_signal = (
            (total_return / self.signals_generated) if self.signals_generated > 0 else 0
        )
        avg_profit_per_trade = (
            (self.total_profit / self.total_trades) if self.total_trades > 0 else 0
        )

        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": self.max_drawdown_pct,
            "signals_generated": self.signals_generated,
            "signals_executed": self.signals_executed,
            "return_per_signal": return_per_signal,
            "avg_profit_per_trade": avg_profit_per_trade,
        }


def get_symbol_tp_sl_multipliers(symbol: str) -> tuple:
    """Получает оптимизированные TP/SL multipliers для символа"""
    if OPTIMIZED_PARAMS_AVAILABLE:
        params = OPTIMIZED_PARAMETERS.get(symbol, {})
        tp_mult = params.get("tp_mult", DEFAULT_TP_MULT)
        sl_mult = params.get("sl_mult", DEFAULT_SL_MULT)
        return tp_mult, sl_mult
    return DEFAULT_TP_MULT, DEFAULT_SL_MULT


def load_yearly_data(symbol: str, limit_days: int = 30) -> Optional[pd.DataFrame]:
    """Загружает данные для символа (использует формат из рабочего скрипта)"""
    csv_path = os.path.join(DATA_DIR, f"{symbol}.csv")

    if not os.path.exists(csv_path):
        print(f"⚠️  Файл не найден: {csv_path}")
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

        # Ограничиваем последними N днями
        if limit_days:
            cutoff_date = df.index[-1] - timedelta(days=limit_days)
            df = df[df.index >= cutoff_date]

        # Убеждаемся, что есть нужные колонки
        required_cols = ["open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            print(f"⚠️  Отсутствуют необходимые колонки в {symbol}")
            return None

        # Преобразуем в float
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Удаляем строки с NaN
        df = df.dropna(subset=required_cols)

        # Сбрасываем индекс для совместимости
        df = df.reset_index()

        period_str = f"последние {limit_days} дней" if limit_days else "годовые данные"
        print(f"✅ Загружено {len(df)} свечей для {symbol} ({period_str})")
        return df

    except Exception as e:
        print(f"❌ Ошибка загрузки {symbol}: {e}")
        import traceback

        traceback.print_exc()
        return None


def run_backtest_for_symbol(symbol: str) -> dict:
    """Запускает бэктест для одного символа"""
    stats = BacktestStats(symbol)

    # Загружаем данные
    df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
    if df is None or len(df) < 25:
        return stats.get_metrics()

    # Добавляем индикаторы
    df = add_technical_indicators(df)

    # Получаем TP/SL multipliers
    tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)

    # Бэктест
    start_idx = 25
    balance = START_BALANCE

    for i in range(start_idx, len(df)):
        side, entry_price = soft_entry_signal(df, i)
        stats.signals_generated += 1 if side else 0

        if side and entry_price:
            # Получаем TP/SL уровни
            tp1_pct, tp2_pct = get_dynamic_tp_levels(df, i, side)
            tp1 = entry_price * (1 + tp1_pct / 100 * tp_mult)
            tp2 = entry_price * (1 + tp2_pct / 100 * tp_mult) if tp2_pct else None

            sl_level_pct = get_dynamic_sl_level(df, i, side)
            if side == "long":
                sl_level = entry_price * (1 - sl_level_pct / 100 * sl_mult)
            else:
                sl_level = entry_price * (1 + sl_level_pct / 100 * sl_mult)

            # Размер позиции
            risk_amount = balance * RISK_PER_TRADE
            sl_distance = abs(entry_price - sl_level)

            if sl_distance > 0:
                position_size = risk_amount / sl_distance

                # Ищем выход
                exit_price = None
                exit_reason = None

                for j in range(i + 1, len(df)):
                    current_price = df["close"].iloc[j]

                    # Проверяем TP1
                    if side == "long" and current_price >= tp1:
                        exit_price = tp1
                        exit_reason = "TP1"
                        # Частичный выход 50% на TP1
                        partial_size = position_size * 0.5
                        profit = (exit_price - entry_price) * partial_size * (1 - FEE)
                        stats.add_trade(
                            {
                                "symbol": symbol,
                                "side": side,
                                "entry": entry_price,
                                "exit": exit_price,
                                "profit": profit,
                                "reason": exit_reason,
                                "timestamp": df["timestamp"].iloc[i],
                            }
                        )
                        balance += profit
                        position_size = position_size * 0.5  # Осталось 50%
                        entry_price = exit_price  # Обновляем цену входа для оставшейся позиции
                        tp1 = tp2 if tp2 else tp1  # Переходим к TP2
                        continue

                    # Проверяем SL
                    if (
                        side == "long"
                        and current_price <= sl_level
                        or side == "short"
                        and current_price >= sl_level
                    ):
                        exit_price = sl_level
                        exit_reason = "SL"
                        break

                    # Динамический SL: переносим в безубыток при достижении 30% пути к TP1
                    if side == "long":
                        progress = (
                            (current_price - entry_price) / (tp1 - entry_price)
                            if (tp1 - entry_price) > 0
                            else 0
                        )
                        if progress >= 0.3:
                            new_sl = entry_price * (1 + FEE)  # Безубыток с учетом комиссии
                            if new_sl > sl_level:
                                sl_level = new_sl
                    else:  # short
                        progress = (
                            (entry_price - current_price) / (entry_price - tp1)
                            if (entry_price - tp1) > 0
                            else 0
                        )
                        if progress >= 0.3:
                            new_sl = entry_price * (1 - FEE)  # Безубыток с учетом комиссии
                            if new_sl < sl_level:
                                sl_level = new_sl

                # Финальный выход (если не вышли ранее)
                if exit_price is None:
                    exit_price = df["close"].iloc[-1]
                    exit_reason = "END"

                # Финальная сделка
                profit = (
                    (exit_price - entry_price) * position_size * (1 - FEE)
                    if side == "long"
                    else (entry_price - exit_price) * position_size * (1 - FEE)
                )
                stats.add_trade(
                    {
                        "symbol": symbol,
                        "side": side,
                        "entry": entry_price,
                        "exit": exit_price,
                        "profit": profit,
                        "reason": exit_reason,
                        "timestamp": df["timestamp"].iloc[i],
                    }
                )
                balance += profit
                stats.signals_executed += 1

    return stats.get_metrics()


def main():
    """Главная функция"""
    print("=" * 80)
    print("🚀 МЕСЯЧНЫЙ БЭКТЕСТ: 50 МОНЕТ СО ВСЕМИ ФИЛЬТРАМИ")
    print("=" * 80)
    print()
    print(f"📅 Период: {PERIOD_DAYS} дней (1 месяц)")
    print(f"📊 Монет: {len(TEST_SYMBOLS)}")
    print(f"💰 Начальный баланс: ${START_BALANCE:,.2f}")
    print(f"📈 Риск на сделку: {RISK_PER_TRADE * 100}%")
    print()
    print("🔧 ВКЛЮЧЕНЫ ВСЕ ФИЛЬТРЫ:")
    print("   ✅ Volume Profile (VP)")
    print("   ✅ VWAP")
    print("   ✅ Order Flow")
    print("   ✅ Microstructure")
    print("   ✅ Momentum")
    print("   ✅ Trend Strength")
    print("   ✅ AMT Filter")
    print("   ✅ Market Profile")
    print("   ✅ Institutional Patterns")
    print("   ✅ Interest Zone (НОВЫЙ - оптимизирован)")
    print("   ✅ Fibonacci Zone (НОВЫЙ - оптимизирован)")
    print("   ✅ Volume Imbalance (НОВЫЙ - оптимизирован)")
    print()
    print("=" * 80)
    print()

    all_results = {}
    total_signals = 0
    total_trades = 0
    total_winning = 0
    total_losing = 0
    total_return = 0.0

    # Запускаем бэктест для каждого символа
    for i, symbol in enumerate(TEST_SYMBOLS, 1):
        print(f"[{i}/{len(TEST_SYMBOLS)}] Тестируем {symbol}...")
        result = run_backtest_for_symbol(symbol)
        all_results[symbol] = result

        total_signals += result.get("signals_generated", 0)
        total_trades += result.get("total_trades", 0)
        total_winning += result.get("winning_trades", 0)
        total_losing += result.get("losing_trades", 0)
        total_return += result.get("total_return", 0)

        print(f"   Сигналов: {result.get('signals_generated', 0)}")
        print(f"   Сделок: {result.get('total_trades', 0)}")
        print(f"   Win Rate: {result.get('win_rate', 0):.1f}%")
        print(f"   Return: {result.get('total_return', 0):.2f}%")
        print()

    # Итоговая статистика
    avg_win_rate = (total_winning / total_trades * 100) if total_trades > 0 else 0
    avg_return_per_signal = (total_return / total_signals) if total_signals > 0 else 0

    print("=" * 80)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 80)
    print()
    print(f"📊 Всего сигналов: {total_signals}")
    print(f"📊 Всего сделок: {total_trades}")
    print(f"📊 Прибыльных: {total_winning}")
    print(f"📊 Убыточных: {total_losing}")
    print(f"📊 Win Rate: {avg_win_rate:.1f}%")
    print(f"📊 Общий Return: {total_return:.2f}%")
    print(f"📊 Return/сигнал: {avg_return_per_signal:.2f}%")
    print()

    # Сохраняем результаты
    output_file = "backtests/50coins_month_all_filters_results.json"
    os.makedirs("backtests", exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(
            {
                "period_days": PERIOD_DAYS,
                "symbols_count": len(TEST_SYMBOLS),
                "total_signals": total_signals,
                "total_trades": total_trades,
                "total_winning": total_winning,
                "total_losing": total_losing,
                "avg_win_rate": avg_win_rate,
                "total_return": total_return,
                "avg_return_per_signal": avg_return_per_signal,
                "symbols": all_results,
            },
            f,
            indent=2,
        )

    print(f"📁 Результаты сохранены: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
