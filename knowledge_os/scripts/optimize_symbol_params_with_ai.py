#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""
🤖 СКРИПТ ОПТИМИЗАЦИИ ПАРАМЕТРОВ TP/SL ДЛЯ КАЖДОЙ МОНЕТЫ С ИСПОЛЬЗОВАНИЕМ ИИ

Использует ИИ-оптимизаторы для поиска оптимальных TP/SL multipliers для каждой монеты
на основе исторических данных и бэктестинга.
"""

import json
import os
import sys
import warnings
from datetime import datetime
from typing import Dict, List, Any, Optional
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing as mp

import numpy as np
import pandas as pd

# Прогресс-бар
try:
    from tqdm import tqdm  # pylint: disable=unused-import
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # Заглушка для tqdm, если не установлен
    def tqdm(iterable=None, **kwargs):  # pylint: disable=unused-argument
        """
        Заглушка для tqdm, если библиотека не установлена.

        Args:
            iterable: Итерируемый объект (не используется)
            **kwargs: Дополнительные аргументы (игнорируются)

        Returns:
            Исходный iterable без изменений
        """
        if iterable is None:
            return iterable
        return iterable

warnings.filterwarnings("ignore")

# ВРЕМЕННО отключаем дополнительные фильтры для оптимизации
# ВАЖНО: устанавливаем ДО импорта config, чтобы фильтры не загрузились
os.environ['USE_VP_FILTER'] = 'false'
os.environ['USE_VWAP_FILTER'] = 'false'
os.environ['USE_ORDER_FLOW_FILTER'] = 'false'
os.environ['USE_MICROSTRUCTURE_FILTER'] = 'false'
os.environ['USE_MOMENTUM_FILTER'] = 'false'
os.environ['USE_TREND_STRENGTH_FILTER'] = 'false'

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импорты системы (после установки переменных окружения)
# pylint: disable=wrong-import-position
from src.signals.core import soft_entry_signal
from src.signals.indicators import add_technical_indicators
from src.ai.tp_optimizer import AITakeProfitOptimizer
from src.ai.sl_optimizer import AIStopLossOptimizer

# Пробуем импортировать Rust ускорение
try:
    from src.infrastructure.performance.rust_accelerator import RustAccelerator, RUST_AVAILABLE
    if RUST_AVAILABLE:
        rust_accelerator = RustAccelerator()  # pylint: disable=invalid-name
        print("✅ Rust ускорение доступно")
    else:
        rust_accelerator = None  # pylint: disable=invalid-name
        print("⚠️ Rust ускорение недоступно (используется Python)")
except ImportError:
    rust_accelerator = None  # pylint: disable=invalid-name
    RUST_AVAILABLE = False

# ============================================================================
# НАСТРОЙКИ ОПТИМИЗАЦИИ
# ============================================================================

DATA_DIR = "data/backtest_data_yearly"
START_BALANCE = 10000.0
FEE = 0.001  # 0.1% комиссия
SLIPPAGE = 0.0005  # 0.05% проскальзывание
RISK_PER_TRADE = 0.02  # 2% риск на сделку

# Диапазоны для оптимизации TP/SL multipliers
# Оптимизировано для ускорения: более крупный шаг
TP_MULT_RANGE = np.arange(1.5, 4.5, 0.3)  # От 1.5x до 4.5x ATR (шаг 0.3 для ускорения)
SL_MULT_RANGE = np.arange(0.8, 2.5, 0.25)   # От 0.8x до 2.5x ATR (шаг 0.25 для ускорения)

# Список стейблкоинов для исключения
STABLECOIN_SYMBOLS = [
    "USDTUSDT", "USDCUSDT", "BUSDUSDT", "FDUSDUSDT", "TUSDUSDT",
    "USDDUSDT", "USDEUSDT", "DAIUSDT", "FRAXUSDT", "LUSDUSDT",
    "USTCUSDT", "USTUSDT", "MIMUSDT", "ALGUSDT", "EURSUSDT", "USD1USDT"
]

# Автоматически находим все доступные символы
def get_available_symbols(use_patterns: bool = True, use_config_coins: bool = True) -> List[str]:
    """
    Находит все доступные символы из разных источников

    Args:
        use_patterns: Если True, использует символы из накопленных паттернов
        use_config_coins: Если True, использует список из config.py
    """
    symbols = []

    # 1. ПРИОРИТЕТ: Символы из накопленных паттернов (самый полный список)
    if use_patterns:
        try:
            pattern_paths = [
                "ai_learning_data/trading_patterns.json",
                "../ai_learning_data/trading_patterns.json",
                "trading_patterns.json"
            ]

            patterns_data = None
            for path in pattern_paths:
                if os.path.exists(path):
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            patterns_data = json.load(f)
                            print(f"✅ Загружены паттерны из {path}")
                            break
                    except Exception as e:
                        print(f"⚠️ Ошибка загрузки {path}: {e}")
                        continue

            if patterns_data and isinstance(patterns_data, list):
                pattern_symbols = set()
                for pattern in patterns_data:
                    symbol = pattern.get('symbol', '')
                    if symbol and symbol.endswith('USDT') and symbol not in STABLECOIN_SYMBOLS:
                        pattern_symbols.add(symbol)

                symbols.extend(list(pattern_symbols))
                print(
                    f"✅ Извлечено {len(pattern_symbols)} уникальных символов из паттернов "
                    f"(всего паттернов: {len(patterns_data)})"
                )
        except Exception as e:
            print(f"⚠️ Не удалось загрузить символы из паттернов: {e}")

    # 2. Добавляем символы из config.py
    if use_config_coins:
        try:
            # pylint: disable=import-outside-toplevel
            from config import COINS, STABLECOIN_SYMBOLS as CONFIG_STABLES
            if COINS and len(COINS) > 0:
                config_symbols = [
                    s for s in COINS
                    if s not in CONFIG_STABLES and s.endswith('USDT')
                ]
                symbols.extend(config_symbols)
                print(f"✅ Добавлено {len(config_symbols)} символов из config.py")
        except Exception as e:
            print(f"⚠️ Не удалось загрузить символы из config.py: {e}")

    # 3. Добавляем символы из исторических данных (если есть)
    if os.path.exists(DATA_DIR):
        data_symbols = []
        for filename in os.listdir(DATA_DIR):
            if filename.endswith('.csv'):
                symbol = filename.replace('.csv', '').replace('_1h', '').replace('_4h', '').replace('_1d', '')
                if symbol not in STABLECOIN_SYMBOLS and symbol.endswith('USDT'):
                    data_symbols.append(symbol)

        symbols.extend(data_symbols)
        print(f"✅ Добавлено {len(data_symbols)} символов из исторических данных")

    # Убираем дубликаты и сортируем
    symbols = sorted(list(set(symbols)))
    return symbols

# Получаем список символов автоматически (с приоритетом на паттерны)
ALL_SYMBOLS = get_available_symbols(use_patterns=True, use_config_coins=True)

# Топ символы для оптимизации (~7 часов работы с многопоточностью)
TOP_SYMBOLS = [
    # Топ-10 (основные)
    "BTCUSDT",  # Bitcoin
    "ETHUSDT",  # Ethereum
    "SOLUSDT",  # Solana
    "BNBUSDT",  # Binance Coin
    "ADAUSDT",  # Cardano
    "XRPUSDT",  # Ripple
    "DOGEUSDT", # Dogecoin
    "AVAXUSDT", # Avalanche
    "LINKUSDT", # Chainlink
    "DOTUSDT",  # Polkadot
    # Дополнительные топ-монеты (для ~7 часов)
    "MATICUSDT", # Polygon
    "LTCUSDT",   # Litecoin
    "UNIUSDT",   # Uniswap
    "ATOMUSDT",  # Cosmos
    "ETCUSDT",   # Ethereum Classic
    "XLMUSDT",   # Stellar
    "ALGOUSDT",  # Algorand
    "FILUSDT",   # Filecoin
    "TRXUSDT",   # Tron
    "EOSUSDT",   # EOS
    "AAVEUSDT",  # Aave
    "MKRUSDT",   # Maker
    "COMPUSDT",  # Compound
    "YFIUSDT",   # Yearn Finance
    "SUSHIUSDT", # SushiSwap
    "SNXUSDT",   # Synthetix
    "CRVUSDT",   # Curve
    "1INCHUSDT", # 1inch
    "ENJUSDT",   # Enjin
    "MANAUSDT",  # Decentraland
    "SANDUSDT",  # The Sandbox
    "AXSUSDT",   # Axie Infinity
    "GALAUSDT",  # Gala
    "CHZUSDT",   # Chiliz
    "FLOWUSDT",  # Flow
    "ICPUSDT",   # Internet Computer
    "NEARUSDT",  # NEAR Protocol
    "APTUSDT",   # Aptos
    "SUIUSDT",   # Sui
    "ARBUSDT",   # Arbitrum
    "OPUSDT",    # Optimism
    "INJUSDT",   # Injective
    "FETUSDT",   # Fetch.ai
    "RENDERUSDT", # Render
    "TAOUSDT",   # Bittensor
    "HBARUSDT",  # Hedera
    "THETAUSDT", # Theta Network
    "ZECUSDT",   # Zcash
]

# ТЕСТОВЫЙ РЕЖИМ: только 1 символ для проверки
TEST_MODE = False  # Отключить тестовый режим для оптимизации топ-4 монет
TEST_SYMBOL = "BTCUSDT"  # Символ для теста

# Топ-4 монеты для оптимизации (BTCUSDT уже оптимизирован)
TOP_4_SYMBOLS = ["ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]

if TEST_MODE:
    # Тестовый режим: только 1 символ
    TEST_SYMBOLS = [TEST_SYMBOL] if TEST_SYMBOL in ALL_SYMBOLS else [ALL_SYMBOLS[0] if ALL_SYMBOLS else []]
    print(f"🧪 ТЕСТОВЫЙ РЕЖИМ: оптимизация только для {TEST_SYMBOLS[0]}")
else:
    # Оптимизация топ-4 монет (BTCUSDT уже оптимизирован)
    TEST_SYMBOLS = [s for s in TOP_4_SYMBOLS if s in ALL_SYMBOLS]
    print(
        "🚀 РЕЖИМ ОПТИМИЗАЦИИ: топ-4 монеты "
        "(годовые данные, Rust, до 20 потоков для символов, до 30 для комбинаций)"
    )
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def add_technical_indicators_with_rust(df: pd.DataFrame) -> pd.DataFrame:
    """
    Добавляет технические индикаторы с использованием Rust ускорения (если доступно)
    ВАЖНО: Инициализирует Rust в каждом процессе отдельно для ProcessPoolExecutor
    """
    # Инициализируем Rust в текущем процессе (для ProcessPoolExecutor)
    local_rust_accelerator = None
    try:
        if RUST_AVAILABLE:
            # Используем глобально импортированный RustAccelerator
            local_rust_accelerator = RustAccelerator()
    except Exception:
        local_rust_accelerator = None

    # Используем Rust если доступно (пользователь требует всегда использовать Rust)
    use_rust = local_rust_accelerator is not None

    if use_rust and local_rust_accelerator:
        try:
            # Проверяем минимальное количество данных (нужно минимум 50 для индикаторов)
            if len(df) < 50:
                return add_technical_indicators(df)

            # Проверяем, что все необходимые колонки есть и не пустые
            required_cols = ['close', 'high', 'low', 'volume']
            if not all(col in df.columns for col in required_cols):
                return add_technical_indicators(df)

            # Проверяем, что нет NaN в критических колонках
            if df[required_cols].isna().any().any():
                # Заполняем NaN перед передачей в Rust
                df = df.copy()
                df[required_cols] = df[required_cols].ffill().bfill()

            # Конвертируем в списки для Rust (сохраняем исходную длину, заменяем NaN на предыдущее значение)
            # ВАЖНО: Rust требует списки одинаковой длины без пропусков
            # Заполняем NaN forward fill, затем backward fill
            df_clean = df[['close', 'high', 'low']].ffill().bfill()

            close_prices = [float(x) for x in df_clean['close'].tolist()]

            # КРИТИЧЕСКАЯ ПРОВЕРКА: Rust требует минимум period+1 элементов для расчета индикаторов
            # Максимальный period = 50 (для EMA), поэтому нужно минимум 51 элемент
            min_required = 51
            if not close_prices or len(close_prices) < min_required:
                return add_technical_indicators(df)

            # Проверяем, что все значения валидны (не NaN, не Inf)
            import math  # pylint: disable=import-outside-toplevel
            if any(not (pd.notna(x) and math.isfinite(x)) for x in close_prices[:min_required]):
                return add_technical_indicators(df)

            # Пробуем использовать Rust с безопасной обработкой ошибок
            # Если любая функция Rust паникует, сразу fallback на Python
            try:
                # RSI через Rust (10-50x быстрее)
                rsi_values = local_rust_accelerator.calculate_rsi(close_prices, period=14)
                if rsi_values and len(rsi_values) == len(df):
                    df['rsi'] = pd.Series(rsi_values, index=df.index)
                else:
                    raise ValueError("RSI length mismatch")
            except Exception:
                return add_technical_indicators(df)

            # ATR через Python (Rust версия имеет проблемы с данными)
            # Используем Python версию для надежности
            try:
                import ta.volatility as ta_vol  # pylint: disable=import-outside-toplevel
                atr_indicator = ta_vol.AverageTrueRange(
                    df_clean['high'], df_clean['low'], df_clean['close'], window=14
                )
                atr_values = atr_indicator.average_true_range()
                if atr_values is not None and len(atr_values) == len(df):
                    df['atr'] = pd.Series(atr_values.values, index=df.index)
                    df['volatility'] = (df['atr'] / df['close']) * 100
                else:
                    raise ValueError("ATR calculation failed")
            except Exception:
                return add_technical_indicators(df)

            try:
                # EMA через Rust
                ema7_values = local_rust_accelerator.calculate_ema(close_prices, period=7)
                ema25_values = local_rust_accelerator.calculate_ema(close_prices, period=25)
                if (ema7_values and ema25_values and
                        len(ema7_values) == len(df) and len(ema25_values) == len(df)):
                    df['ema7'] = pd.Series(ema7_values, index=df.index)
                    df['ema25'] = pd.Series(ema25_values, index=df.index)
                    df['ema_fast'] = pd.Series(
                        local_rust_accelerator.calculate_ema(close_prices, period=20),
                        index=df.index
                    )
                    df['ema_slow'] = pd.Series(
                        local_rust_accelerator.calculate_ema(close_prices, period=50),
                        index=df.index
                    )
                else:
                    raise ValueError("EMA length mismatch")
            except Exception:
                return add_technical_indicators(df)

            try:
                # MACD через Rust
                macd_line, macd_signal, macd_hist = local_rust_accelerator.calculate_macd(close_prices, 12, 26, 9)
                if macd_line and len(macd_line) == len(df):
                    df['macd'] = pd.Series(macd_line, index=df.index)
                    df['macd_signal'] = pd.Series(macd_signal, index=df.index)
                    df['macd_histogram'] = pd.Series(macd_hist, index=df.index)
                else:
                    raise ValueError("MACD length mismatch")
            except Exception:
                return add_technical_indicators(df)

            try:
                # Bollinger Bands через Rust
                bb_upper, bb_middle, bb_lower = local_rust_accelerator.calculate_bollinger_bands(
                    close_prices, period=20, std_dev=2.0
                )
                if bb_upper and len(bb_upper) == len(df):
                    df['bb_upper'] = pd.Series(bb_upper, index=df.index)
                    df['bb_mavg'] = pd.Series(bb_middle, index=df.index)
                    df['bb_lower'] = pd.Series(bb_lower, index=df.index)
                else:
                    raise ValueError("BB length mismatch")
            except Exception:
                return add_technical_indicators(df)

            # Остальные индикаторы через pandas
            df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=20).mean()

            # ADX через ta
            import ta.trend as ta_trend  # pylint: disable=import-outside-toplevel
            adx_indicator = ta_trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
            df['adx'] = adx_indicator.adx()
            df['trend_strength'] = df['adx']

            # Momentum
            df['momentum'] = (df['close'] - df['close'].shift(5)) / df['close'].shift(5) * 100

            return df
        except Exception:
            # Fallback на обычный метод, если Rust не работает
            # Не логируем, чтобы не засорять вывод в многопоточности
            return add_technical_indicators(df)
    else:
        # Используем Python (стабильно для многопоточности)
        return add_technical_indicators(df)


def load_historical_data(symbol: str, limit_days: Optional[int] = None) -> Optional[pd.DataFrame]:
    """
    Загружает исторические данные для символа

    Args:
        symbol: Торговый символ
        limit_days: Ограничить количество дней (для тестирования). None = все данные
    """
    try:
        # Пробуем разные варианты имени файла
        possible_paths = [
            os.path.join(DATA_DIR, f"{symbol}_1h.csv"),
            os.path.join(DATA_DIR, f"{symbol}.csv"),
        ]

        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break

        if not file_path:
            print(f"⚠️ Файл не найден для {symbol}")
            return None

        df = pd.read_csv(file_path)

        # Преобразуем timestamp в datetime (с обработкой разных форматов)
        if 'timestamp' in df.columns:
            # Проверяем тип данных
            if df['timestamp'].dtype in ['int64', 'float64', 'int32', 'float32']:
                # Если это число, пробуем как миллисекунды
                try:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
                except Exception:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            else:
                # Если это строка, пробуем как обычную дату
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.set_index('timestamp')
        elif 'open_time' in df.columns:
            # Проверяем тип данных
            if df['open_time'].dtype in ['int64', 'float64', 'int32', 'float32']:
                # Если это число, пробуем как миллисекунды
                try:
                    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', errors='coerce')
                except Exception:
                    df['open_time'] = pd.to_datetime(df['open_time'], errors='coerce')
            else:
                # Если это строка, пробуем как обычную дату
                df['open_time'] = pd.to_datetime(df['open_time'], errors='coerce')
            df = df.set_index('open_time')

        # Убеждаемся, что есть нужные колонки
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            print(f"⚠️ Отсутствуют необходимые колонки в {symbol}")
            return None

        # Преобразуем в float
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Удаляем строки с NaN
        df = df.dropna(subset=required_cols)

        # Сортируем по времени
        df = df.sort_index()

        # Ограничиваем количество дней для тестирования
        if limit_days is not None:
            # Для 1h таймфрейма: 1 день = 24 свечи, неделя = 168 свечей
            limit_candles = limit_days * 24
            if len(df) > limit_candles:
                df = df.tail(limit_candles)
                print(f"✅ Загружено {len(df)} свечей для {symbol} (ограничено {limit_days} днями)")
            else:
                print(f"✅ Загружено {len(df)} свечей для {symbol}")
        else:
            print(f"✅ Загружено {len(df)} свечей для {symbol}")

        return df

    except Exception as e:
        print(f"❌ Ошибка загрузки данных для {symbol}: {e}")
        return None


def run_backtest_with_params(
    df: pd.DataFrame,
    tp_mult: float,
    sl_mult: float,
    use_ai: bool = False,
    tp_optimizer: Optional[AITakeProfitOptimizer] = None,
    sl_optimizer: Optional[AIStopLossOptimizer] = None,
    symbol: str = "UNKNOWN"
) -> Dict[str, Any]:
    """Запускает бэктест с заданными параметрами TP/SL"""

    # Добавляем индикаторы (с Rust ускорением, если доступно)
    df = add_technical_indicators_with_rust(df)

    balance = START_BALANCE
    trades = []
    position = None
    signals_count = 0  # Счетчик сигналов

    # start_idx должен быть достаточным для расчета индикаторов, но не больше размера данных
    # Для недельных данных (168 свечей) используем меньший start_idx
    start_idx = min(100, len(df) - 10)  # Оставляем минимум 10 свечей для торговли
    if start_idx < 50:
        start_idx = 50  # Минимум 50 для расчета индикаторов

    print(
        f"   🔍 Начальный индекс: {start_idx}, всего свечей: {len(df)}, "
        f"доступно для торговли: {len(df) - start_idx}"
    )

    for i in range(start_idx, len(df)):
        current_price = df['close'].iloc[i]
        current_time = df.index[i]

        # Проверяем выход из позиции
        if position is not None:
            entry_price = position['entry_price']
            tp1 = position.get('tp1', position.get('tp'))
            tp2 = position.get('tp2')
            sl = position['sl']
            side = position['side']

            # Проверяем условия выхода
            if side == 'LONG':
                tp1_reached = current_price >= tp1
                tp2_reached = tp2 and current_price >= tp2
                sl_hit = current_price <= sl
            else:  # SHORT
                tp1_reached = current_price <= tp1
                tp2_reached = tp2 and current_price <= tp2
                sl_hit = current_price >= sl

            partial_close = False  # Инициализируем по умолчанию
            exit_price = None

            if tp1_reached and not position.get('tp1_executed', False):
                # Частичный выход на TP1 (50%)
                position['tp1_executed'] = True
                exit_price = tp1
                partial_close = True

                # Перемещаем SL в безубыток
                if side == 'LONG':
                    sl = entry_price * 1.003
                else:
                    sl = entry_price * 0.997
                position['sl'] = sl
            elif tp2_reached and position.get('tp1_executed', False):
                # Полный выход на TP2
                exit_price = tp2
                partial_close = False
            elif sl_hit:
                # Stop Loss
                exit_price = sl
                partial_close = False
            else:
                exit_price = None

            if exit_price is not None:
                # Рассчитываем прибыль
                if side == 'LONG':
                    profit_pct = ((exit_price - entry_price) / entry_price) * 100
                else:
                    profit_pct = ((entry_price - exit_price) / entry_price) * 100

                profit_pct -= (FEE * 2) + (SLIPPAGE * 2)

                position_size = balance * RISK_PER_TRADE
                if partial_close:
                    profit = position_size * (profit_pct / 100) * 0.5
                else:
                    if position.get('tp1_executed', False):
                        profit = position_size * (profit_pct / 100) * 0.5
                    else:
                        profit = position_size * (profit_pct / 100)

                balance += profit
                trades.append({
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'side': side,
                    'profit': profit,
                    'profit_pct': profit_pct
                })

                if not partial_close:
                    position = None

        # Ищем новые сигналы
        if position is None:
            try:
                signal, signal_info = soft_entry_signal(df, i)

                if signal:
                    signals_count += 1
                    # Логируем первые несколько сигналов для диагностики
                    if signals_count <= 3:
                        print(
                            f"   ✅ Сигнал #{signals_count} на свече {i}: {signal}, "
                            f"info={signal_info}"
                        )
                    # Рассчитываем TP/SL
                    atr = (df['atr'].iloc[i] if 'atr' in df.columns and
                           not pd.isna(df['atr'].iloc[i]) else current_price * 0.02)

                    if use_ai and tp_optimizer and sl_optimizer:
                        try:
                            # Используем ИИ-оптимизаторы
                            side = "long" if signal == "LONG" else "short"

                            # ИИ-оптимизированные TP
                            tp1_pct, _ = tp_optimizer.calculate_ai_optimized_tp(
                                symbol=symbol,
                                side=side,
                                df=df,
                                current_index=i,
                                base_tp1=2.0,
                                base_tp2=4.0
                            )

                            # ИИ-оптимизированный SL
                            sl_pct = sl_optimizer.calculate_ai_optimized_sl(
                                symbol=symbol,
                                side=side,
                                df=df,
                                current_index=i,
                                base_sl_pct=2.0
                            )

                            # Конвертируем проценты в multipliers (приблизительно)
                            tp_mult_ai = (tp1_pct / 100.0) / (atr / current_price) if atr > 0 else tp_mult
                            sl_mult_ai = (sl_pct / 100.0) / (atr / current_price) if atr > 0 else sl_mult

                            # Используем среднее между ИИ и базовыми параметрами
                            tp_mult_used = (tp_mult_ai + tp_mult) / 2
                            sl_mult_used = (sl_mult_ai + sl_mult) / 2
                        except Exception:
                            # Fallback на базовые параметры (не логируем для скорости)
                            tp_mult_used = tp_mult
                            sl_mult_used = sl_mult
                    else:
                        tp_mult_used = tp_mult
                        sl_mult_used = sl_mult

                    # Рассчитываем цены TP/SL
                    if signal == 'LONG':
                        sl = current_price - (atr * sl_mult_used)
                        tp1 = current_price + (atr * tp_mult_used)
                        tp2 = current_price + (atr * tp_mult_used * 2)
                    else:  # SHORT
                        sl = current_price + (atr * sl_mult_used)
                        tp1 = current_price - (atr * tp_mult_used)
                        tp2 = current_price - (atr * tp_mult_used * 2)

                    position = {
                        'side': signal,
                        'entry_price': current_price,
                        'entry_time': current_time,
                        'sl': sl,
                        'tp1': tp1,
                        'tp2': tp2,
                        'tp1_executed': False,
                    }
            except Exception:
                continue

    # Рассчитываем метрики
    if len(trades) == 0:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'total_return': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
        }

    winning_trades = [t for t in trades if t['profit'] > 0]
    losing_trades = [t for t in trades if t['profit'] <= 0]

    total_profit = sum(t['profit'] for t in winning_trades) if winning_trades else 0
    total_loss = abs(sum(t['profit'] for t in losing_trades)) if losing_trades else 0

    win_rate = (len(winning_trades) / len(trades)) * 100 if trades else 0
    profit_factor = total_profit / total_loss if total_loss > 0 else 0
    total_return = ((balance - START_BALANCE) / START_BALANCE) * 100

    # Sharpe Ratio (упрощенный)
    if len(trades) > 1:
        returns = [t['profit_pct'] for t in trades]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    else:
        sharpe_ratio = 0

    # Max Drawdown
    equity_curve = [START_BALANCE]
    for trade in trades:
        equity_curve.append(equity_curve[-1] + trade['profit'])

    max_drawdown = 0
    peak = START_BALANCE
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    return {
        'total_trades': len(trades),
        'signals_count': signals_count,  # Добавляем счетчик сигналов
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'final_balance': balance,
    }


def optimize_symbol_params(
    symbol: str,
    use_ai: bool = True
) -> Dict[str, Any]:
    """Оптимизирует параметры TP/SL для символа"""

    print(f"\n{'='*80}")
    print(f"🤖 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ ДЛЯ {symbol}")
    print(f"{'='*80}")

    # Загружаем данные (годовые данные для полной оптимизации)
    df = load_historical_data(symbol, limit_days=None)  # Все данные (год)
    if df is None or len(df) < 100:
        print(f"⚠️ Пропускаем {symbol} - недостаточно данных")
        return None

    # Инициализируем ИИ-оптимизаторы
    tp_optimizer = None
    sl_optimizer = None
    if use_ai:
        try:
            tp_optimizer = AITakeProfitOptimizer()
            sl_optimizer = AIStopLossOptimizer()
            print("✅ ИИ-оптимизаторы инициализированы")
        except Exception as e:
            print(f"⚠️ Ошибка инициализации ИИ-оптимизаторов: {e}")
            use_ai = False

    # Тестируем разные комбинации параметров
    best_score = -np.inf
    best_params = None
    best_metrics = None

    total_combinations = len(TP_MULT_RANGE) * len(SL_MULT_RANGE)

    print(f"📊 Тестируем {total_combinations} комбинаций параметров...")
    sys.stdout.flush()

    # Создаем список всех комбинаций для многопоточности
    combinations = [(tp, sl) for tp in TP_MULT_RANGE for sl in SL_MULT_RANGE]

    # Используем многопоточность для оптимизации комбинаций
    # Максимум потоков: CPU * 4 для I/O bound задач, но не больше количества комбинаций
    # Максимум без искусственных ограничений
    num_workers_combinations = min(mp.cpu_count() * 4, len(combinations))

    def test_combination(args):
        """Тестирует одну комбинацию параметров"""
        tp_mult, sl_mult = args
        try:
            metrics = run_backtest_with_params(
                df.copy(),
                tp_mult=tp_mult,
                sl_mult=sl_mult,
                use_ai=use_ai,
                tp_optimizer=tp_optimizer,
                sl_optimizer=sl_optimizer,
                symbol=symbol
            )

            # Логируем статистику для первых нескольких комбинаций
            if len([c for c in combinations if c[0] == tp_mult and c[1] == sl_mult][:5]) > 0:
                print(
                    f"   📊 TP={tp_mult:.2f}, SL={sl_mult:.2f}: "
                    f"сигналов={metrics.get('signals_count', 0)}, "
                    f"сделок={metrics['total_trades']}"
                )

            # Рассчитываем score
            if metrics['total_trades'] >= 5:
                score = (
                    metrics['profit_factor'] * 0.4 +
                    (metrics['win_rate'] / 100) * 0.3 +
                    (metrics['sharpe_ratio'] / 10) * 0.2 +
                    (metrics['total_return'] / 100) * 0.1
                )
                return {
                    'tp_mult': float(tp_mult),

                    'sl_mult': float(sl_mult),
                    'score': score,
                    'metrics': metrics
                }
        except Exception as e:
            print(
                f"⚠️ Ошибка при TP_MULT={tp_mult:.2f}, SL_MULT={sl_mult:.2f}: {e}"
            )
        return None

    # Многопоточная оптимизация комбинаций
    print(f"🚀 Используем {num_workers_combinations} потоков для оптимизации комбинаций")
    sys.stdout.flush()

    # Используем tqdm для прогресс-бара + текстовый вывод для логов
    if TQDM_AVAILABLE:
        print(f"📊 Тестируем {len(combinations)} комбинаций для {symbol}...")
        sys.stdout.flush()
        with ThreadPoolExecutor(max_workers=num_workers_combinations) as executor:
            # Создаем список futures для отслеживания прогресса
            futures = [executor.submit(test_combination, combo) for combo in combinations]
            results_list = []
            # Используем tqdm для отображения прогресса
            # mininterval=1.0 - обновлять минимум раз в секунду
            # disable=False - всегда показывать, даже если не терминал
            # leave=True - оставить прогресс-бар после завершения
            # dynamic_ncols=True - адаптировать ширину к терминалу
            pbar = tqdm(
                total=len(combinations), desc=f"  [{symbol}]", unit="комб",
                ncols=120, mininterval=0.5, disable=False, leave=True,
                file=sys.stdout, dynamic_ncols=True, ascii=False,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
            )
            completed_count = 0
            for future in as_completed(futures):
                results_list.append(future.result())
                completed_count += 1
                pbar.update(1)
                # Текстовый вывод прогресса каждые 5 комбинаций (чаще для видимости)
                # ВАЖНО: выводим в stderr напрямую, чтобы было видно в логе (2>&1)
                if completed_count % 5 == 0 or completed_count == len(combinations):
                    progress_pct = (completed_count / len(combinations)) * 100
                    bar_length = 40
                    filled = int(bar_length * completed_count / len(combinations))
                    progress_bar = '█' * filled + '░' * (bar_length - filled)  # pylint: disable=invalid-name
                    progress_msg = (
                        f"[{symbol}] Прогресс: [{progress_bar}] "
                        f"{completed_count}/{len(combinations)} ({progress_pct:.1f}%)"
                    )
                    # Выводим в stderr для лога (2>&1 захватывает и stderr)
                    print(progress_msg, file=sys.stderr, flush=True)
                    # Также через tqdm для красивого отображения в терминале
                    pbar.write(progress_msg)
            pbar.close()
    else:
        # Без прогресс-бара (если tqdm не установлен)
        with ThreadPoolExecutor(max_workers=num_workers_combinations) as executor:
            results_list = list(executor.map(test_combination, combinations))

    # Находим лучший результат и собираем статистику
    total_signals = 0
    total_trades_all = 0
    valid_combinations = 0

    for result in results_list:
        if result:
            valid_combinations += 1
            if 'metrics' in result:
                total_signals += result['metrics'].get('signals_count', 0)
                total_trades_all += result['metrics'].get('total_trades', 0)

            if result['score'] > best_score:
                best_score = result['score']
                best_params = {
                    'tp_mult': result['tp_mult'],
                    'sl_mult': result['sl_mult'],
                }
                best_metrics = result['metrics']

    # Выводим статистику
    print("\n📊 СТАТИСТИКА ОПТИМИЗАЦИИ:")
    print(f"   Всего комбинаций: {len(combinations)}")
    print(f"   Успешно протестировано: {valid_combinations}")
    print(f"   Всего сигналов (среднее): {total_signals / max(valid_combinations, 1):.1f}")
    print(f"   Всего сделок (среднее): {total_trades_all / max(valid_combinations, 1):.1f}")
    print(
        f"   Комбинаций с >=5 сделками: "
        f"{sum(1 for r in results_list if r and r.get('metrics', {}).get('total_trades', 0) >= 5)}"
    )

    if best_params:
        print(f"\n✅ ЛУЧШИЕ ПАРАМЕТРЫ ДЛЯ {symbol}:")
        print(f"   TP_MULT: {best_params['tp_mult']:.2f}x")
        print(f"   SL_MULT: {best_params['sl_mult']:.2f}x")
        print(f"   Score: {best_score:.4f}")
        print("   Метрики:")
        print(f"     - Сделок: {best_metrics['total_trades']}")
        print(f"     - Win Rate: {best_metrics['win_rate']:.2f}%")
        print(f"     - Profit Factor: {best_metrics['profit_factor']:.2f}")
        print(f"     - Доходность: {best_metrics['total_return']:.2f}%")
        print(f"     - Sharpe Ratio: {best_metrics['sharpe_ratio']:.2f}")
        print(f"     - Max Drawdown: {best_metrics['max_drawdown']:.2f}%")

        return {
            'symbol': symbol,
            'tp_mult': best_params['tp_mult'],
            'sl_mult': best_params['sl_mult'],
            'metrics': best_metrics,
            'score': best_score,
        }
    else:
        print(f"⚠️ Не найдено оптимальных параметров для {symbol}")
        return None


def save_optimized_params(results: List[Dict[str, Any]]):
    """Сохраняет оптимизированные параметры в файл"""

    # Создаем структуру для сохранения (включая метрики)
    optimized_params = {}
    for result in results:
        if result:
            # Преобразуем метрики в обычные Python типы (для JSON сериализации)
            metrics = result.get('metrics', {})
            if metrics:
                # Конвертируем numpy типы в Python типы
                clean_metrics = {}
                for key, value in metrics.items():
                    try:
                        if value is None:
                            clean_metrics[key] = None
                        elif hasattr(value, 'item'):  # numpy scalar
                            clean_metrics[key] = float(value.item())
                        elif isinstance(value, (np.integer, np.floating)):
                            clean_metrics[key] = float(value)
                        elif isinstance(value, (int, float, str, bool)):
                            clean_metrics[key] = value
                        else:
                            # Пробуем конвертировать в float
                            clean_metrics[key] = float(value)
                    except (ValueError, TypeError):
                        # Если не удается конвертировать, сохраняем как строку
                        clean_metrics[key] = str(value)
                metrics = clean_metrics
            else:
                metrics = {}

            optimized_params[result['symbol']] = {
                'tp_mult': float(result['tp_mult']),
                'sl_mult': float(result['sl_mult']),
                'metrics': metrics,  # Сохраняем метрики
                'score': float(result.get('score', 0)),  # Сохраняем score
            }

            # Отладочный вывод
            print(f"💾 Сохраняем для {result['symbol']}: metrics={bool(metrics)}, score={result.get('score', 0)}")

    # Сохраняем в optimized_config.py
    output_file = "archive/experimental/optimized_config.py"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Оптимизированные параметры стратегии\n")
        f.write("# Автоматически сгенерировано системой оптимизации с ИИ\n")
        f.write(f"# Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("OPTIMIZED_PARAMETERS = {\n")  # noqa: F541

        for symbol, params in optimized_params.items():
            f.write(f"    '{symbol}': {{\n")
            f.write(f"        'tp_mult': {params['tp_mult']:.2f},\n")
            f.write(f"        'sl_mult': {params['sl_mult']:.2f},\n")
            # Всегда сохраняем метрики, если они есть
            m = params.get('metrics', {})
            score_val = params.get('score', 0)
            if m or score_val:
                f.write("        # Метрики:\n")
                f.write(f"        # Score: {float(score_val):.4f}\n")
                if m:
                    f.write(f"        # Сделок: {int(m.get('total_trades', 0))}\n")
                    f.write(f"        # Win Rate: {float(m.get('win_rate', 0)):.2f}%\n")
                    f.write(f"        # Profit Factor: {float(m.get('profit_factor', 0)):.2f}\n")
                    f.write(f"        # Доходность: {float(m.get('total_return', 0)):.2f}%\n")
                    f.write(f"        # Sharpe Ratio: {float(m.get('sharpe_ratio', 0)):.2f}\n")
                    f.write(f"        # Max Drawdown: {float(m.get('max_drawdown', 0)):.2f}%\n")
            f.write("    }},\n")

        f.write("}\n")

    print(f"\n✅ Оптимизированные параметры сохранены в {output_file}")

    # Также сохраняем в JSON для удобства
    json_file = "archive/experimental/optimized_params.json"
    try:
        # Дополнительная проверка и очистка данных перед JSON сериализацией
        json_safe_params = {}
        for symbol, params in optimized_params.items():
            json_safe_params[symbol] = {
                'tp_mult': float(params['tp_mult']),
                'sl_mult': float(params['sl_mult']),
                'score': float(params.get('score', 0)),
            }
            # Добавляем метрики, если они есть
            if params.get('metrics'):
                json_safe_params[symbol]['metrics'] = params['metrics']

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_safe_params, f, indent=2, ensure_ascii=False, default=str)
        print(f"✅ JSON версия сохранена в {json_file}")
        print(f"   Сохранено символов: {len(json_safe_params)}")
        for symbol, params in json_safe_params.items():
            has_metrics = bool(params.get('metrics'))
            print(
                f"   {symbol}: metrics={'✅' if has_metrics else '❌'}, "
                f"score={params.get('score', 0):.4f}"
            )
    except Exception as e:
        print(f"⚠️ Ошибка сохранения JSON: {e}")
        import traceback  # pylint: disable=import-outside-toplevel
        traceback.print_exc()
        # Пробуем сохранить без метрик
        simple_params = {
            symbol: {
                'tp_mult': float(params['tp_mult']),
                'sl_mult': float(params['sl_mult'])
            }
            for symbol, params in optimized_params.items()
        }
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(simple_params, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON версия сохранена (без метрик) в {json_file}")


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def optimize_symbol_worker(args):
    """Worker функция для многопоточности"""
    symbol, use_ai = args
    try:
        return optimize_symbol_params(symbol, use_ai=use_ai)
    except Exception as e:
        print(f"❌ Ошибка при оптимизации {symbol}: {e}")
        return None


def main():
    """Главная функция"""
    print("🤖 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ TP/SL С ИСПОЛЬЗОВАНИЕМ ИИ")
    print("="*80)
    print(f"📅 Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Найдено символов для оптимизации: {len(TEST_SYMBOLS)}")
    if len(TEST_SYMBOLS) <= 20:
        print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    else:
        print(f"📊 Первые 20 символов: {', '.join(TEST_SYMBOLS[:20])}...")
        print(f"📊 Последние 10 символов: {', '.join(TEST_SYMBOLS[-10:])}")
    print(f"🔍 Диапазон TP_MULT: {TP_MULT_RANGE[0]:.2f} - {TP_MULT_RANGE[-1]:.2f}")
    print(f"🔍 Диапазон SL_MULT: {SL_MULT_RANGE[0]:.2f} - {SL_MULT_RANGE[-1]:.2f}")

    # Определяем количество потоков для символов
    # Максимум потоков: CPU * 4 для I/O bound задач, но не больше 20
    # НЕ ограничиваем количеством символов, т.к. каждый символ обрабатывает много комбинаций
    # и внутри уже используется многопоточность для комбинаций
    # Используем максимум потоков независимо от количества символов
    num_workers = min(mp.cpu_count() * 4, 20)  # Максимум 20 потоков для символов
    print(f"🚀 Многопоточность: {num_workers} потоков для символов (символов: {len(TEST_SYMBOLS)})")

    # ВАЖНО: Используем ThreadPoolExecutor для Rust (ProcessPoolExecutor не может сериализовать Rust panic)
    # ThreadPoolExecutor работает в одном процессе, поэтому Rust модуль доступен всем потокам
    use_threads = RUST_AVAILABLE and rust_accelerator
    if use_threads:
        print("⚡ Rust ускорение: ВКЛЮЧЕНО (ThreadPoolExecutor)")
    else:
        print("⚡ Rust ускорение: ОТКЛЮЧЕНО (ProcessPoolExecutor для параллельности)")
    print("="*80)

    if len(TEST_SYMBOLS) == 0:
        print("❌ Не найдено символов для оптимизации!")
        return

    results = []

    # Выбираем executor в зависимости от наличия Rust
    # ThreadPoolExecutor для Rust (один процесс, все потоки используют один Rust модуль)
    # ProcessPoolExecutor для Python fallback (настоящая параллельность, но без Rust)
    executor_class = ThreadPoolExecutor if use_threads else ProcessPoolExecutor

    with executor_class(max_workers=num_workers) as executor:
        # Запускаем задачи
        future_to_symbol = {
            executor.submit(optimize_symbol_worker, (symbol, True)): symbol
            for symbol in TEST_SYMBOLS
        }

        # Собираем результаты по мере завершения с прогресс-баром
        if TQDM_AVAILABLE:
            print(f"\n📊 Оптимизация {len(TEST_SYMBOLS)} символов...")
            sys.stdout.flush()
            pbar = tqdm(
                total=len(TEST_SYMBOLS), desc="📊 Символы", unit="симв",
                ncols=120, mininterval=0.5, disable=False, leave=True,
                file=sys.stdout, dynamic_ncols=True, ascii=False,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )
            completed_symbols = 0
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        completed_symbols += 1
                        progress_pct = (completed_symbols / len(TEST_SYMBOLS)) * 100
                        bar_length = 40
                        filled = int(bar_length * completed_symbols / len(TEST_SYMBOLS))
                        progress_bar = '█' * filled + '░' * (bar_length - filled)  # pylint: disable=invalid-name
                        progress_msg = (
                            f"✅ {symbol} завершен [{progress_bar}] "
                            f"{completed_symbols}/{len(TEST_SYMBOLS)} ({progress_pct:.1f}%)"
                        )
                        # Выводим напрямую в stderr для лога
                        print(progress_msg, file=sys.stderr, flush=True)
                        # Также через tqdm для красивого отображения в терминале
                        pbar.write(progress_msg)
                    else:
                        skip_msg = f"⚠️ {symbol} пропущен"
                        print(skip_msg, file=sys.stderr, flush=True)
                        pbar.write(skip_msg)
                except Exception as e:
                    error_msg = f"❌ {symbol} ошибка: {e}"
                    print(error_msg, file=sys.stderr, flush=True)
                    pbar.write(error_msg)
                pbar.update(1)
            pbar.close()
        else:
            # Без прогресс-бара
            completed = 0
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                completed += 1
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        print(f"\n✅ [{completed}/{len(TEST_SYMBOLS)}] {symbol} завершен")
                    else:
                        print(f"\n⚠️ [{completed}/{len(TEST_SYMBOLS)}] {symbol} пропущен")
                except Exception as e:
                    print(f"\n❌ [{completed}/{len(TEST_SYMBOLS)}] {symbol} ошибка: {e}")

    # Сохраняем результаты
    if results:
        save_optimized_params(results)

        print(f"\n{'='*80}")
        print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ")
        print(f"{'='*80}")
        for result in results:
            print(f"\n{result['symbol']}:")
            print(f"  TP_MULT: {result['tp_mult']:.2f}x")
            print(f"  SL_MULT: {result['sl_mult']:.2f}x")
            print(f"  Win Rate: {result['metrics']['win_rate']:.2f}%")
            print(f"  Profit Factor: {result['metrics']['profit_factor']:.2f}")
            print(f"  Доходность: {result['metrics']['total_return']:.2f}%")
    else:
        print("\n⚠️ Не удалось оптимизировать параметры ни для одного символа")

    print("\n✅ Оптимизация завершена!")


if __name__ == "__main__":
    main()
