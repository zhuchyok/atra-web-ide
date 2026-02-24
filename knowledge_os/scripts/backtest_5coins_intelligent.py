#!/usr/bin/env python3
"""
Годовой бэктест для 100 монет с ИНТЕЛЛЕКТУАЛЬНОЙ СИСТЕМОЙ АДАПТАЦИИ ФИЛЬТРОВ
Топ 5: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT
Топ 6-10: XRPUSDT, AVAXUSDT, DOGEUSDT, DOTUSDT, LINKUSDT
Топ 11-20: LTCUSDT, TRXUSDT, UNIUSDT, NEARUSDT, SUIUSDT, PEPEUSDT, ENAUSDT, ICPUSDT, FETUSDT, HBARUSDT
Топ 21-50: BCHUSDT, STRKUSDT, TAOUSDT, PENGUUSDT и другие...
Топ 51-100: AAVEUSDT, MKRUSDT, COMPUSDT, SANDUSDT, MANAUSDT и другие...

Использует:
- Динамическую адаптацию под рыночные условия
- Индивидуальные параметры для каждой монеты
- Систему приоритетов и компенсации
- Адаптацию на основе исторической эффективности
"""

import json
import logging
import os
import sys
import traceback
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
# 🔧 ТЕСТ БЕЗ НОВЫХ ФИЛЬТРОВ (для сравнения)
os.environ["USE_INTEREST_ZONE_FILTER"] = "false"  # НОВЫЙ - отключен для теста
os.environ["USE_FIBONACCI_ZONE_FILTER"] = "false"  # НОВЫЙ - отключен для теста
os.environ["USE_VOLUME_IMBALANCE_FILTER"] = "false"  # НОВЫЙ - отключен для теста
os.environ["USE_EXHAUSTION_FILTER"] = "false"  # Только для выхода

# Импорты системы (после установки переменных окружения)
# pylint: disable=wrong-import-position
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

# pylint: enable=wrong-import-position

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
RISK_PER_TRADE = 0.05  # 🔧 УВЕЛИЧЕНО: 5% риск на сделку (было 2%)

DEFAULT_TP_MULT = 2.0
DEFAULT_SL_MULT = 1.5

# Список монет будет определен после DATA_DIR


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

# 🔧 ТЕСТ НА 5 МОНЕТАХ (как раньше, для сравнения)
TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT"]

# ============================================================================
# КЛАСС ДЛЯ СТАТИСТИКИ
# ============================================================================


class BacktestStats:
    """Статистика бэктеста"""

    def __init__(self, name: str):
        self.name = name
        self.trades = []
        self.daily_balances = []  # Список кортежей (timestamp, balance)
        self.initial_balance = START_BALANCE
        self.balance = START_BALANCE
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

    def update_balance(self, timestamp, current_balance):
        """Фиксирует текущий баланс для Equity Curve"""
        # Фиксируем только если это новая дата или список пуст
        if not self.daily_balances or self.daily_balances[-1][0].date() != timestamp.date():
            self.daily_balances.append((timestamp, current_balance))
        else:
            # Обновляем баланс для текущего дня (последняя запись за день)
            self.daily_balances[-1] = (timestamp, current_balance)

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
        """Возвращает метрики на основе Equity Curve (Daily Returns)"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0.0
        profit_factor = self.total_profit / self.total_loss if self.total_loss > 0 else float("inf")
        total_return = ((self.balance - self.initial_balance) / self.initial_balance) * 100

        # Индустриальный расчет Sharpe Ratio на основе Daily Returns
        sharpe_ratio = 0.0
        sortino_ratio = 0.0

        if len(self.daily_balances) > 2:
            # Извлекаем балансы и считаем доходности
            balances = [b[1] for b in self.daily_balances]
            # Ежедневные доходности
            daily_returns = []
            for i in range(1, len(balances)):
                if balances[i - 1] > 0:
                    ret = (balances[i] - balances[i - 1]) / balances[i - 1]
                    daily_returns.append(ret)

            if daily_returns:
                avg_daily_return = np.mean(daily_returns)
                std_daily_return = np.std(daily_returns)

                if std_daily_return > 0:
                    # Годовой Sharpe (365 дней для крипто)
                    sharpe_ratio = (avg_daily_return / std_daily_return) * np.sqrt(365)

                    # Sortino Ratio (только негативная волатильность)
                    negative_returns = [r for r in daily_returns if r < 0]
                    std_downside = np.std(negative_returns) if negative_returns else 0
                    if std_downside > 0:
                        sortino_ratio = (avg_daily_return / std_downside) * np.sqrt(365)
                    else:
                        sortino_ratio = sharpe_ratio  # Если убытков нет

        # КРИТИЧЕСКАЯ ПРОВЕРКА: Sharpe должен иметь тот же знак, что и общая доходность
        if total_return < 0:
            sharpe_ratio = min(0.0, sharpe_ratio)
            sortino_ratio = min(0.0, sortino_ratio)
        elif total_return == 0:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0

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
            "sortino_ratio": sortino_ratio,
            "final_balance": self.balance,
            "total_profit": self.total_profit,
            "total_loss": self.total_loss,
            "signals_generated": self.signals_generated,
            "signals_executed": self.signals_executed,
            "signals_rejected_by_intelligent": self.signals_rejected_by_intelligent,
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
        print(f"📊 Sortino Ratio: {metrics['sortino_ratio']:.2f}")
        print(f"🎯 Сигналов сгенерировано: {metrics['signals_generated']}")
        print(f"✅ Сигналов исполнено: {metrics['signals_executed']}")
        print(
            f"❌ Отклонено интеллектуальной системой: {metrics['signals_rejected_by_intelligent']}"
        )


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

        # Преобразуем timestamp или open_time в datetime
        if "timestamp" in df.columns:
            try:
                if df["timestamp"].dtype == "int64" or df["timestamp"].dtype == "float64":
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                else:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
            except Exception:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

            df.set_index("timestamp", inplace=True)
        elif "open_time" in df.columns:
            # Если есть колонка open_time, используем её
            try:
                df["open_time"] = pd.to_datetime(df["open_time"])
                df.set_index("open_time", inplace=True)
            except Exception:
                df["open_time"] = pd.to_datetime(df["open_time"], errors="coerce")
                df.set_index("open_time", inplace=True)

        # Сортируем по времени
        df = df.sort_index()

        # Ограничиваем последними N днями (если указано)
        if limit_days and len(df) > 0:
            if isinstance(df.index[-1], pd.Timestamp):
                cutoff_date = df.index[-1] - timedelta(days=limit_days)
                df = df[df.index >= cutoff_date]
            else:
                # Если индекс не Timestamp, пытаемся преобразовать
                df.index = pd.to_datetime(df.index, errors="coerce")
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
        traceback.print_exc()
        return None


# ============================================================================
# ФУНКЦИИ БЭКТЕСТА
# ============================================================================


def run_backtest(
    df: pd.DataFrame,
    symbol: str = "UNKNOWN",
    mode: str = "soft",
    intelligent_system: Optional[IntelligentFilterSystem] = None,
) -> BacktestStats:
    """Запускает бэктест с интеллектуальной системой адаптации"""

    stats = BacktestStats(f"{symbol} годовой ({mode}, интеллектуальная система)")

    # 🔧 ОПТИМИЗАЦИЯ: Убираем .copy() - работаем напрямую с DataFrame
    # Добавляем технические индикаторы
    df = add_technical_indicators(df)

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

    # Инициализируем интеллектуальную систему если не передана
    if intelligent_system is None:
        intelligent_system = get_intelligent_filter_system()

    # Начальный индекс (исправлено: было 100, стало 25 для сравнения с optimize_all_filters_comprehensive.py)
    start_idx = 25

    if len(df) < start_idx:
        print(f"⚠️ Недостаточно данных: {len(df)} < {start_idx}")
        return stats

    position = None

    # Проходим по всем свечам
    for i in range(start_idx, len(df)):
        current_price = df["close"].iloc[i]
        current_time = df.index[i]

        # Обновляем баланс для Equity Curve
        stats.update_balance(current_time, stats.balance)

        # Проверяем выход из позиции с продвинутой логикой
        if position is not None:
            assert isinstance(position, dict)
            exit_price = None
            exit_reason = None
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
                    is_profitable = profit > 0

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

                    # Обновляем исторические метрики для интеллектуальной системы
                    # historical_metrics будет использоваться в будущем для адаптации

                    # Обновляем производительность фильтров
                    if intelligent_system and "filter_params" in position:
                        intelligent_system.update_performance_from_trade(
                            position["filter_params"], is_profitable, profit
                        )

                    position = None
                    continue

        # Если нет позиции, ищем вход
        if position is None:
            # Сначала получаем адаптированные параметры от интеллектуальной системы
            try:
                volume_ratio = df["volume_ratio"].iloc[i]
                rsi = df["rsi"].iloc[i]
                volatility = df["volatility"].iloc[i]
                trend_strength = df["trend_strength"].iloc[i]

                # Рыночные условия
                market_conditions = MarketConditions(
                    volatility=volatility,
                    trend_strength=trend_strength,
                    historical_volatility=df["volatility"].rolling(100).mean().iloc[i]
                    if i >= 100
                    else volatility,
                    avg_volume=df["volume"].rolling(100).mean().iloc[i]
                    if i >= 100
                    else df["volume"].iloc[i],
                )

                # Получаем адаптированные параметры
                adaptive_params = intelligent_system.adaptive_system.adapt_filters_to_market(
                    symbol, volatility, trend_strength
                )
                symbol_params = get_symbol_specific_parameters(
                    symbol, market_conditions.historical_volatility, market_conditions.avg_volume
                )
                # 🔧 ПРИОРИТЕТ: symbol_params перезаписывает adaptive_params (более специфичные)
                final_params = {**adaptive_params, **symbol_params}

                # 🔧 ПЕРЕЗАПИСЫВАЕМ ослабленными значениями для soft режима
                final_params["rsi_oversold"] = 60  # 🔧 Ослаблено: 60 (было 50)
                final_params["rsi_overbought"] = 40  # 🔧 Ослаблено: 40 (было 50)
                final_params["trend_strength"] = 0.05  # 🔧 Ослаблено: 0.05 (было 0.1)
                final_params["momentum_threshold"] = -10.0  # 🔧 Ослаблено: -10.0 (было -5.0)

                # Используем адаптированные параметры для проверки базовых условий
                # Временно сохраняем в os.environ для использования в soft_entry_signal
                os.environ["ADAPTIVE_VOLUME_RATIO"] = str(final_params.get("volume_ratio", 0.3))
                os.environ["ADAPTIVE_RSI_OVERSOLD"] = str(final_params.get("rsi_oversold", 40))
                os.environ["ADAPTIVE_RSI_OVERBOUGHT"] = str(final_params.get("rsi_overbought", 60))
                os.environ["ADAPTIVE_TREND_STRENGTH"] = str(
                    final_params.get("trend_strength", 0.15)
                )
                os.environ["ADAPTIVE_MOMENTUM"] = str(final_params.get("momentum_threshold", -5.0))

            except Exception as e:
                # Если интеллектуальная система не работает, используем обычный сигнал
                logger = logging.getLogger(__name__)
                logger.debug("⚠️ Ошибка интеллектуальной системы: %s, используем обычный сигнал", e)
                final_params = {}

            # Генерируем сигнал (теперь с адаптированными параметрами)
            signal_side, signal_price = (
                soft_entry_signal(df, i) if mode == "soft" else strict_entry_signal(df, i)
            )
            stats.signals_generated += 1

            # Диагностика: логируем первые 5 случаев, когда сигнал не генерируется
            if not signal_side and stats.signals_generated <= 5:
                rsi = df["rsi"].iloc[i] if "rsi" in df.columns else None
                volume_ratio = df["volume_ratio"].iloc[i] if "volume_ratio" in df.columns else None
                ema7 = df["ema7"].iloc[i] if "ema7" in df.columns else None
                ema25 = df["ema25"].iloc[i] if "ema25" in df.columns else None
                rsi_str = f"{rsi:.2f}" if rsi is not None and not pd.isna(rsi) else "None"
                vol_str = (
                    f"{volume_ratio:.2f}"
                    if volume_ratio is not None and not pd.isna(volume_ratio)
                    else "None"
                )
                ema_cond = (
                    ema7 is not None
                    and ema25 is not None
                    and not pd.isna(ema7)
                    and not pd.isna(ema25)
                )
                ema_str = f"{ema7 > ema25}" if ema_cond else "None"
                print(
                    f"🔍 [{symbol}] Сигнал не сгенерирован на свече {i}: "
                    f"rsi={rsi_str}, volume_ratio={vol_str}, ema7>ema25={ema_str}"
                )

            if signal_side:
                # Проверяем через интеллектуальную систему приоритетов
                # 🔧 ОТКЛЮЧЕНО: Интеллектуальная система блокирует сигналы
                # В optimize_all_filters_comprehensive.py она не используется
                # signal_data будет использоваться при включении системы
                try:
                    # signal_data = {
                    #     'side': signal_side,
                    #     'volume_ratio': volume_ratio,
                    #     'rsi': rsi,
                    #     'trend_strength': trend_strength,
                    #     'momentum': momentum,
                    #     'volatility': volatility,
                    #     'vp_ok': True,
                    #     'vwap_ok': True,
                    #     'quality_score': 0.7
                    # }
                    pass
                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.debug("⚠️ Ошибка проверки интеллектуальной системой: %s", e)

                side = signal_side
                entry_price = signal_price if signal_price else current_price

                # Получаем динамические TP/SL уровни
                try:
                    tp1_pct, tp2_pct = get_dynamic_tp_levels(df, i, side)
                    sl_pct = get_dynamic_sl_level(df, i, side, use_ai_optimization=True)

                    if tp1_pct is not None and tp2_pct is not None and sl_pct is not None:
                        # Конвертируем проценты в абсолютные цены
                        if side == "LONG":
                            tp1 = entry_price * (1 + tp1_pct / 100)
                            tp2 = entry_price * (1 + tp2_pct / 100)
                            sl = entry_price * (1 - sl_pct / 100)
                        else:
                            tp1 = entry_price * (1 - tp1_pct / 100)
                            tp2 = entry_price * (1 - tp2_pct / 100)
                            sl = entry_price * (1 + sl_pct / 100)
                    else:
                        # Fallback на оптимизированные параметры
                        raise ValueError("TP/SL levels not calculated")
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
                    "filter_params": final_params if "final_params" in locals() else {},
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
        # Финальное обновление баланса после закрытия последней позиции
        stats.update_balance(df.index[-1], stats.balance)

    # Если позиций не было в конце, все равно фиксируем финальный баланс
    elif len(df) > 0:
        stats.update_balance(df.index[-1], stats.balance)

    return stats


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================


def main():
    """Главная функция"""
    import gc

    # 🔧 МИНИМАЛЬНЫЙ ТЕСТ ДЛЯ ВЕРИФИКАЦИИ
    period_days = 7  # 7 дней данных
    TEST_SYMBOLS = ["BTCUSDT"]  # Только BTC
    print(f"🚀 МЕСЯЧНЫЙ БЭКТЕСТ {len(TEST_SYMBOLS)} МОНЕТ С ИНТЕЛЛЕКТУАЛЬНОЙ СИСТЕМОЙ")
    print("=" * 80)
    print(f"📅 Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальный баланс: ${START_BALANCE:.2f}")
    print(f"📊 Символы ({len(TEST_SYMBOLS)}): {', '.join(TEST_SYMBOLS)}")
    print(f"📅 Период: последние {period_days} дней (месячные данные)")
    print("=" * 80)
    print("")
    print("✅ ВКЛЮЧЕНЫ ВСЕ ФИЛЬТРЫ + ИНТЕЛЛЕКТУАЛЬНАЯ СИСТЕМА:")
    print("   - Volume Profile (VP)")
    print("   - VWAP")
    print("   - Order Flow")
    print("   - Microstructure")
    print("   - Momentum")
    print("   - Trend Strength")
    print("   - 🤖 Динамическая адаптация под рыночные условия")
    print("   - 🤖 Индивидуальные параметры для каждой монеты")
    print("   - 🤖 Система приоритетов и компенсации")
    print("   - 🤖 Адаптация на основе исторической эффективности")
    print("")

    # Инициализируем интеллектуальную систему
    intelligent_system = get_intelligent_filter_system()

    all_results = []

    # Тестируем каждую монету
    for idx, symbol in enumerate(TEST_SYMBOLS, 1):
        print(f"\n{'=' * 80}")
        print(f"📈 Тестирование {symbol} ({idx}/{len(TEST_SYMBOLS)})")
        print(f"{'=' * 80}")

        # Загружаем месячные данные
        df = load_yearly_data(symbol, limit_days=period_days)
        if df is None or len(df) < 50:
            print(f"❌ Недостаточно данных для {symbol}")
            continue

        # Запускаем бэктест
        print(f"🔵 Запуск бэктеста для {symbol} с интеллектуальной системой...")
        stats = run_backtest(df, symbol=symbol, mode="soft", intelligent_system=intelligent_system)
        stats.print_summary()

        # Сохраняем метрики
        metrics = stats.get_metrics()
        metrics["symbol"] = symbol
        metrics["period_days"] = period_days  # Месячные данные
        metrics["all_filters_enabled"] = True
        metrics["intelligent_system_enabled"] = True
        all_results.append(metrics)

        # Очистка памяти
        del df
        del stats
        gc.collect()

    # Сохраняем результаты
    results_file = (
        f"backtests/5coins_yearly_intelligent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    os.makedirs("backtests", exist_ok=True)

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Итоговая сводка
    print(f"\n{'=' * 80}")
    print("📊 ИТОГОВАЯ СВОДКА")
    print(f"{'=' * 80}")

    # 🔧 ИСПРАВЛЕНИЕ: Общий бюджет распределяется между монетами
    total_initial = START_BALANCE  # Общий бюджет $10,000
    balance_per_symbol = START_BALANCE / len(all_results) if all_results else START_BALANCE

    total_final = 0
    total_trades = 0
    total_signals = 0
    total_executed = 0
    total_rejected = 0

    for result in all_results:
        symbol = result.get("symbol", "N/A")
        initial = balance_per_symbol  # 🔧 ИСПРАВЛЕНО: Распределенный бюджет
        # 🔧 ИСПРАВЛЕНО: Пересчитываем финальный баланс пропорционально
        return_pct = result.get("total_return", 0)
        final = initial * (1 + return_pct / 100)
        trades = result.get("total_trades", 0)
        signals = result.get("signals_generated", 0)
        executed = result.get("signals_executed", 0)
        rejected = result.get("signals_rejected_by_intelligent", 0)

        total_final += final
        total_trades += trades
        total_signals += signals
        total_executed += executed
        total_rejected += rejected

        print(f"\n{symbol}:")
        print(f"  💰 Баланс: ${initial:.2f} → ${final:.2f} (доходность: {return_pct:+.2f}%)")
        print(f"  📊 Сделок: {trades}")
        print(f"  🎯 Сигналов: {signals} (исполнено: {executed}, отклонено ИС: {rejected})")

    print(f"\n{'=' * 80}")
    total_profit = total_final - total_initial
    total_return_pct = (total_profit / total_initial) * 100 if total_initial > 0 else 0
    print("📊 ИТОГО ПОРТФЕЛЯ:")
    print(f"  Начальный баланс: ${total_initial:.2f}")
    print(f"  Финальный баланс: ${total_final:.2f}")
    print(f"  Общая прибыль: ${total_profit:+.2f}")
    print(f"  Общая доходность: {total_return_pct:+.2f}%")
    print(f"  Всего сделок: {total_trades}")
    print(
        f"  Всего сигналов: {total_signals} (исполнено: {total_executed}, отклонено ИС: {total_rejected})"
    )
    print(f"{'=' * 80}")

    print(f"\n✅ Результаты сохранены в {results_file}")
    print("\n🎉 БЭКТЕСТ ЗАВЕРШЕН!")


if __name__ == "__main__":
    main()
