#!/usr/bin/env python3
"""
Бэктест институциональных индикаторов

Сравнивает результаты:
1. Baseline (без новых фильтров)
2. С новыми фильтрами (Order Flow, Microstructure, Momentum, Trend Strength)
3. Анализирует влияние каждого фильтра отдельно
"""

import json
import os
import sys
import warnings
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.shared.utils.datetime_utils import get_utc_now

warnings.filterwarnings("ignore")

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импорты системы
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

# Дефолтные значения TP/SL multipliers (будут переопределены для каждой монеты)
DEFAULT_TP_MULT = 2.0  # Take Profit = 2x ATR
DEFAULT_SL_MULT = 1.5  # Stop Loss = 1.5x ATR


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

# Список символов для тестирования (можно изменить)
TEST_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "ADAUSDT",
]

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

        # Статистика по фильтрам
        self.rejected_by_order_flow = 0
        self.rejected_by_microstructure = 0
        self.rejected_by_momentum = 0
        self.rejected_by_trend_strength = 0

    def add_trade(
        self,
        entry_price: float,
        exit_price: float,
        side: str,
        entry_time: datetime,
        exit_time: datetime,
        profit: float,
    ):
        """Добавляет сделку"""
        self.trades.append(
            {
                "entry_price": entry_price,
                "exit_price": exit_price,
                "side": side,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "profit": profit,
                "profit_pct": (profit / self.balance) * 100 if self.balance > 0 else 0,
            }
        )

        self.balance += profit
        self.total_trades += 1

        if profit > 0:
            self.winning_trades += 1
            self.total_profit += profit
            self.max_profit = max(self.max_profit, profit)
        else:
            self.losing_trades += 1
            self.total_loss += abs(profit)
            self.max_loss = max(self.max_loss, abs(profit))

        if self.balance > self.max_balance:
            self.max_balance = self.balance

        if self.balance < self.min_balance:
            self.min_balance = self.balance
            drawdown = (self.max_balance - self.balance) / self.max_balance * 100
            if drawdown > self.max_drawdown_pct:
                self.max_drawdown_pct = drawdown
                self.max_drawdown = self.max_balance - self.balance

    def get_metrics(self) -> Dict:
        """Возвращает метрики"""
        if self.total_trades == 0:
            return {
                "name": self.name,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_return": 0.0,
                "max_drawdown_pct": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "final_balance": self.balance,
                "total_profit": 0.0,
                "total_loss": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "signals_generated": self.signals_generated,
                "signals_executed": self.signals_executed,
                "rejected_by_order_flow": self.rejected_by_order_flow,
                "rejected_by_microstructure": self.rejected_by_microstructure,
                "rejected_by_momentum": self.rejected_by_momentum,
                "rejected_by_trend_strength": self.rejected_by_trend_strength,
            }

        win_rate = (self.winning_trades / self.total_trades) * 100
        profit_factor = self.total_profit / self.total_loss if self.total_loss > 0 else float("inf")
        total_return = ((self.balance - self.initial_balance) / self.initial_balance) * 100

        # Sharpe Ratio (упрощенный)
        if len(self.trades) > 1:
            returns = [t["profit_pct"] for t in self.trades]
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0.0
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
            "avg_profit": self.total_profit / self.winning_trades if self.winning_trades > 0 else 0,
            "avg_loss": self.total_loss / self.losing_trades if self.losing_trades > 0 else 0,
            "signals_generated": self.signals_generated,
            "signals_executed": self.signals_executed,
            "rejected_by_order_flow": self.rejected_by_order_flow,
            "rejected_by_microstructure": self.rejected_by_microstructure,
            "rejected_by_momentum": self.rejected_by_momentum,
            "rejected_by_trend_strength": self.rejected_by_trend_strength,
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

        if metrics["signals_generated"] > 0:
            print("\n🔍 ОТКЛОНЕНИЯ ПО ФИЛЬТРАМ:")
            print(f"   Order Flow: {metrics['rejected_by_order_flow']}")
            print(f"   Microstructure: {metrics['rejected_by_microstructure']}")
            print(f"   Momentum: {metrics['rejected_by_momentum']}")
            print(f"   Trend Strength: {metrics['rejected_by_trend_strength']}")


# ============================================================================
# ФУНКЦИИ ЗАГРУЗКИ ДАННЫХ
# ============================================================================


def load_historical_data(symbol: str) -> Optional[pd.DataFrame]:
    """Загружает исторические данные из CSV"""
    csv_path = os.path.join(DATA_DIR, f"{symbol}.csv")

    if not os.path.exists(csv_path):
        print(f"⚠️ Файл не найден: {csv_path}")
        return None

    try:
        df = pd.read_csv(csv_path)

        # Преобразуем timestamp в datetime
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)

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

        # Сортируем по времени
        df = df.sort_index()

        print(f"✅ Загружено {len(df)} свечей для {symbol}")
        return df

    except Exception as e:
        print(f"❌ Ошибка загрузки {symbol}: {e}")
        return None


# ============================================================================
# ФУНКЦИИ БЭКТЕСТА
# ============================================================================


def run_backtest(
    df: pd.DataFrame, symbol: str = "UNKNOWN", use_new_filters: bool = False, mode: str = "soft"
) -> BacktestStats:  # Используем soft по умолчанию
    """
    Запускает бэктест

    Args:
        df: DataFrame с историческими данными
        use_new_filters: Использовать ли новые фильтры
        mode: "strict" или "soft"
    """
    # Устанавливаем флаги фильтров
    os.environ["USE_ORDER_FLOW_FILTER"] = "true" if use_new_filters else "false"
    os.environ["USE_MICROSTRUCTURE_FILTER"] = "true" if use_new_filters else "false"
    os.environ["USE_MOMENTUM_FILTER"] = "true" if use_new_filters else "false"
    os.environ["USE_TREND_STRENGTH_FILTER"] = "true" if use_new_filters else "false"
    os.environ["USE_EXHAUSTION_FILTER"] = "false"  # Exhaustion только для выхода

    stats = BacktestStats(f"{'С новыми фильтрами' if use_new_filters else 'Baseline'} ({mode})")

    # Добавляем технические индикаторы
    df = add_technical_indicators(df.copy())

    if len(df) < 100:
        print(f"⚠️ Недостаточно данных: {len(df)} свечей")
        return stats

    # Проверяем наличие необходимых колонок
    required_cols = [
        "ema7",
        "ema25",
        "bb_lower",
        "bb_upper",
        "rsi",
        "volume_ratio",
        "volatility",
        "momentum",
        "trend_strength",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"⚠️ Отсутствуют колонки: {missing_cols}")
        # Пытаемся добавить недостающие колонки
        if "ema7" not in df.columns or "ema25" not in df.columns:
            import ta  # pylint: disable=import-outside-toplevel

            if "ema7" not in df.columns:
                df["ema7"] = ta.trend.EMAIndicator(df["close"], window=7).ema_indicator()
            if "ema25" not in df.columns:
                df["ema25"] = ta.trend.EMAIndicator(df["close"], window=25).ema_indicator()

    # Перезагружаем модуль для применения новых флагов
    # (флаги уже установлены через os.environ выше)

    position: Optional[Dict[str, Any]] = (
        None  # {side, entry_price, entry_time, sl, tp1, tp2, sl_moved_30, sl_moved_50, tp1_executed}
    )

    # Проходим по всем свечам (начинаем с большего индекса для стабильности индикаторов)
    start_idx = max(100, 200)  # Увеличиваем для лучшей стабильности индикаторов
    for i in range(start_idx, len(df)):
        current_price = df["close"].iloc[i]
        current_time = df.index[i]

        # Проверяем выход из позиции с продвинутой логикой
        if position is not None:
            # Type narrowing для линтера
            assert isinstance(position, dict)
            exit_price = None
            partial_close = False

            entry_price = position["entry_price"]
            tp1 = position.get("tp1", position.get("tp"))  # Fallback на старый tp
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
            # 1. При 30% движения к TP1 - первое перемещение SL
            if progress_to_tp1 >= 0.3 and not position.get("sl_moved_30", False):
                position["sl_moved_30"] = True
                if side == "LONG":
                    # Перемещаем SL на 30% пути к TP1
                    new_sl = entry_price + (tp1 - entry_price) * 0.3
                    new_sl = max(new_sl, entry_price * 1.001)  # Минимум безубыток + комиссия
                    sl = max(sl, new_sl)  # Только улучшаем
                else:  # SHORT
                    new_sl = entry_price - (entry_price - tp1) * 0.3
                    new_sl = min(new_sl, entry_price * 0.999)  # Минимум безубыток - комиссия
                    sl = min(sl, new_sl)  # Только улучшаем
                position["sl"] = sl

            # 2. При 50% движения к TP1 - второе перемещение SL
            if progress_to_tp1 >= 0.5 and not position.get("sl_moved_50", False):
                position["sl_moved_50"] = True
                if side == "LONG":
                    # Перемещаем SL на 50% пути к TP1
                    new_sl = entry_price + (tp1 - entry_price) * 0.5
                    new_sl = max(new_sl, entry_price * 1.001)  # Минимум безубыток + комиссия
                    sl = max(sl, new_sl)  # Только улучшаем
                else:  # SHORT
                    new_sl = entry_price - (entry_price - tp1) * 0.5
                    new_sl = min(new_sl, entry_price * 0.999)  # Минимум безубыток - комиссия
                    sl = min(sl, new_sl)  # Только улучшаем
                position["sl"] = sl

            # 3. При достижении TP1 - SL в безубыток + частичный выход
            if side == "LONG":
                tp1_reached = current_price >= tp1
                tp2_reached = tp2 and current_price >= tp2
                sl_hit = current_price <= sl
            else:  # SHORT
                tp1_reached = current_price <= tp1
                tp2_reached = tp2 and current_price <= tp2
                sl_hit = current_price >= sl

            if tp1_reached and not position.get("tp1_executed", False):
                # Частичный выход на TP1 (50%)
                position["tp1_executed"] = True
                exit_price = tp1
                partial_close = True

                # Перемещаем SL в безубыток
                if side == "LONG":
                    sl = entry_price * 1.003  # Безубыток + 0.3% (комиссия)
                else:  # SHORT
                    sl = entry_price * 0.997  # Безубыток - 0.3% (комиссия)
                position["sl"] = sl
                position["sl_moved_to_be"] = True

            elif tp2_reached and position.get("tp1_executed", False):
                # Полный выход на TP2 (остаток 50%)
                exit_price = tp2
                partial_close = False

            elif sl_hit:
                # Stop Loss
                exit_price = sl
                partial_close = False

            if exit_price is not None:
                # Рассчитываем прибыль
                if side == "LONG":
                    profit_pct = ((exit_price - entry_price) / entry_price) * 100
                else:
                    profit_pct = ((entry_price - exit_price) / entry_price) * 100

                # Учитываем комиссию и проскальзывание
                profit_pct -= FEE * 2  # Комиссия на вход и выход
                profit_pct -= SLIPPAGE * 2  # Проскальзывание

                position_size = stats.balance * RISK_PER_TRADE
                if partial_close:
                    # Частичный выход - только 50% позиции
                    profit = position_size * (profit_pct / 100) * 0.5
                else:
                    # Полный выход
                    if position.get("tp1_executed", False):
                        # Второй выход (остаток 50%)
                        profit = position_size * (profit_pct / 100) * 0.5
                    else:
                        # Первый выход (100%)
                        profit = position_size * (profit_pct / 100)

                stats.add_trade(
                    entry_price, exit_price, side, position["entry_time"], current_time, profit
                )

                if not partial_close:
                    # Полный выход - закрываем позицию
                    position = None
                # Если partial_close, позиция остается открытой для TP2

        # Ищем новые сигналы
        if position is None:
            try:
                if mode == "strict":
                    signal, _ = strict_entry_signal(df, i)
                else:
                    signal, _ = soft_entry_signal(df, i)

                # Диагностика (только для первых сигналов)
                if i % 1000 == 0 and i > 100:
                    # Проверяем базовые условия
                    bb_lower = df["bb_lower"].iloc[i] if "bb_lower" in df.columns else None
                    bb_upper = df["bb_upper"].iloc[i] if "bb_upper" in df.columns else None
                    ema7 = df["ema7"].iloc[i] if "ema7" in df.columns else None
                    ema25 = df["ema25"].iloc[i] if "ema25" in df.columns else None

                    if pd.isna(bb_lower) or pd.isna(bb_upper) or pd.isna(ema7) or pd.isna(ema25):
                        if i == 1000:  # Только один раз
                            print(
                                f"⚠️ NaN значения на свече {i}: bb_lower={bb_lower}, bb_upper={bb_upper}, ema7={ema7}, ema25={ema25}"
                            )

                if signal:
                    stats.signals_generated += 1

                    # 🤖 ПРОДВИНУТЫЙ РАСЧЕТ TP/SL (как в продакшене)
                    # Используем те же функции, что и в signal_live.py
                    try:
                        side = "long" if signal == "LONG" else "short"

                        # Динамический расчет TP1 и TP2 (как в продакшене)
                        tp1_pct, tp2_pct = get_dynamic_tp_levels(
                            df, i, side=side, trade_mode="spot", adjust_for_fees=True
                        )

                        # Динамический расчет SL (как в продакшене)
                        sl_pct = get_dynamic_sl_level(
                            df, i, side=side, base_sl_pct=2.0, symbol=None, use_ai_optimization=True
                        )

                        # Рассчитываем цены TP и SL
                        if signal == "LONG":
                            tp1 = current_price * (1 + tp1_pct / 100.0)
                            tp2 = current_price * (1 + tp2_pct / 100.0)
                            sl = current_price * (1 - sl_pct / 100.0)
                        else:  # SHORT
                            tp1 = current_price * (1 - tp1_pct / 100.0)
                            tp2 = current_price * (1 - tp2_pct / 100.0)
                            sl = current_price * (1 + sl_pct / 100.0)

                    except Exception as e:
                        # Fallback на базовый расчет на основе ATR с оптимизированными параметрами
                        if i % 1000 == 0:  # Логируем только периодически
                            print(
                                f"⚠️ Ошибка динамического расчета TP/SL: {e}, используем базовый расчет с оптимизированными параметрами"
                            )
                        atr = (
                            df["atr"].iloc[i]
                            if "atr" in df.columns and not pd.isna(df["atr"].iloc[i])
                            else current_price * 0.02
                        )

                        # Получаем оптимизированные multipliers для символа
                        tp_mult, sl_mult = get_symbol_tp_sl_multipliers(symbol)

                        if signal == "LONG":
                            sl = current_price - (atr * sl_mult)
                            tp1 = current_price + (atr * tp_mult)
                            tp2 = current_price + (atr * tp_mult * 2)
                        else:  # SHORT
                            sl = current_price + (atr * sl_mult)
                            tp1 = current_price - (atr * tp_mult)
                            tp2 = current_price - (atr * tp_mult * 2)

                    position = {
                        "side": signal,
                        "entry_price": current_price,
                        "entry_time": current_time,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "sl_moved_30": False,
                        "sl_moved_50": False,
                        "sl_moved_to_be": False,
                        "tp1_executed": False,
                    }
                    stats.signals_executed += 1
            except Exception as e:
                # Логируем ошибку, но продолжаем
                if i % 1000 == 0:  # Логируем только каждую 1000-ю свечу
                    print(f"⚠️ Ошибка генерации сигнала на свече {i}: {e}")
                continue

    return stats


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================


def main():
    """Главная функция"""
    print("🚀 БЭКТЕСТ ИНСТИТУЦИОНАЛЬНЫХ ИНДИКАТОРОВ")
    print("=" * 80)
    print(f"📅 Дата запуска: {get_utc_now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальный баланс: ${START_BALANCE:.2f}")
    print(f"📊 Символы для тестирования: {', '.join(TEST_SYMBOLS)}")
    print("=" * 80)

    all_results = []

    for symbol_idx, symbol in enumerate(TEST_SYMBOLS, 1):
        print(f"\n{'=' * 80}")
        print(f"📈 Тестирование {symbol} ({symbol_idx}/{len(TEST_SYMBOLS)})")
        print(f"{'=' * 80}")
        sys.stdout.flush()

        # Загружаем данные
        print(f"⏳ Загрузка данных для {symbol}...")
        sys.stdout.flush()
        df = load_historical_data(symbol)
        if df is None or len(df) < 100:
            print(f"⚠️ Пропускаем {symbol} - недостаточно данных")
            continue
        print(f"✅ Загружено {len(df)} свечей, начинаем бэктест...")
        sys.stdout.flush()

        # Baseline (без новых фильтров)
        print("\n🔵 Baseline (без новых фильтров)...")
        sys.stdout.flush()
        baseline_stats = run_backtest(df, symbol=symbol, use_new_filters=False, mode="soft")
        print(f"✅ Baseline для {symbol} завершен")
        sys.stdout.flush()
        baseline_stats.print_summary()
        baseline_metrics = baseline_stats.get_metrics()
        baseline_metrics["symbol"] = symbol
        all_results.append(baseline_metrics)

        # С новыми фильтрами
        print("\n🟢 С новыми фильтрами...")
        sys.stdout.flush()
        new_filters_stats = run_backtest(df, symbol=symbol, use_new_filters=True, mode="soft")
        print(f"✅ С фильтрами для {symbol} завершен")
        sys.stdout.flush()
        new_filters_stats.print_summary()
        new_metrics = new_filters_stats.get_metrics()
        new_metrics["symbol"] = symbol
        all_results.append(new_metrics)

        # Сравнение
        print(f"\n{'=' * 80}")
        print(f"📊 СРАВНЕНИЕ РЕЗУЛЬТАТОВ ДЛЯ {symbol}")
        print(f"{'=' * 80}")

        baseline_metrics = baseline_stats.get_metrics()
        new_metrics = new_filters_stats.get_metrics()

        print("💰 Финальный баланс:")
        print(f"   Baseline: ${baseline_metrics['final_balance']:.2f}")
        print(f"   С фильтрами: ${new_metrics['final_balance']:.2f}")
        diff_balance = new_metrics["final_balance"] - baseline_metrics["final_balance"]
        diff_pct = (
            (diff_balance / baseline_metrics["final_balance"] * 100)
            if baseline_metrics["final_balance"] > 0
            else 0
        )
        print(f"   Разница: ${diff_balance:.2f} ({diff_pct:.2f}%)")

        print("\n📊 Сделки:")
        print(f"   Baseline: {baseline_metrics['total_trades']}")
        print(f"   С фильтрами: {new_metrics['total_trades']}")
        print(f"   Разница: {new_metrics['total_trades'] - baseline_metrics['total_trades']}")

        print("\n✅ Win Rate:")
        print(f"   Baseline: {baseline_metrics['win_rate']:.2f}%")
        print(f"   С фильтрами: {new_metrics['win_rate']:.2f}%")
        print(f"   Разница: {new_metrics['win_rate'] - baseline_metrics['win_rate']:.2f}%")

        print("\n💵 Profit Factor:")
        print(f"   Baseline: {baseline_metrics['profit_factor']:.2f}")
        print(f"   С фильтрами: {new_metrics['profit_factor']:.2f}")
        print(f"   Разница: {new_metrics['profit_factor'] - baseline_metrics['profit_factor']:.2f}")

    # Сохраняем результаты
    results_file = f"backtests/institutional_indicators_backtest_{get_utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("backtests", exist_ok=True)

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\n✅ Результаты сохранены в {results_file}")
    print("\n🎉 БЭКТЕСТ ЗАВЕРШЕН!")


if __name__ == "__main__":
    main()
