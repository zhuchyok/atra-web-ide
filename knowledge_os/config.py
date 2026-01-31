"""Конфигурация торгового бота ATRA.

Содержит глобальные константы и параметры: фильтры риска, тренд BTC,
усиленные блоки, расширенную стратегию Bollinger Bands, новостные фильтры,
отслеживание крупных транзакций и прочие системные настройки. Используется
модулями сигналов, Telegram-ботом и бэктестером.
"""
# pylint: disable=too-many-lines
# Файл конфигурации содержит множество настроек, что оправдывает большой размер

import os
try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

def manual_load_dotenv(filepath):
    """Вручную загружает переменные окружения из файла, если python-dotenv недоступен"""
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Удаляем кавычки, если они есть
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = value
        return True
    except Exception as e:
        print(f"⚠️ Ошибка ручной загрузки {filepath}: {e}")
        return False

# 🔐 ПРИОРИТЕТ ЗАГРУЗКИ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ:
# 1. .env (в .gitignore) - для реальных ключей и секретов
# 2. ATRA_ENV_FILE (переменная окружения)
# 3. env.prod/env.dev (в зависимости от ATRA_ENV)
# 4. env (шаблон, без реальных ключей)

def load_all_dotenvs():
    """Загружает все необходимые .env файлы в правильном порядке"""
    # Сначала .env
    if _DOTENV_AVAILABLE:
        if os.path.exists('.env'):
            load_dotenv('.env', override=False)
    else:
        manual_load_dotenv('.env')

    # Затем основной файл в зависимости от окружения
    env_file = os.getenv('ATRA_ENV_FILE')
    if not env_file:
        if os.path.exists('env.prod'):
            if _DOTENV_AVAILABLE:
                load_dotenv('env.prod', override=False)
            else:
                manual_load_dotenv('env.prod')
            
            atra_env_from_file = os.getenv('ATRA_ENV', 'prod').lower().strip()
            if atra_env_from_file == 'prod':
                env_file = 'env.prod'
            else:
                if os.path.exists('env.dev'):
                    env_file = 'env.dev'
                else:
                    env_file = 'env.prod'
        elif os.path.exists('env.dev'):
            env_file = 'env.dev'
        else:
            atra_env = os.getenv('ATRA_ENV', 'dev').lower().strip()
            if atra_env == 'prod' and os.path.exists('env.prod'):
                env_file = 'env.prod'
            elif atra_env == 'dev' and os.path.exists('env.dev'):
                env_file = 'env.dev'
            else:
                env_file = 'env'

    if _DOTENV_AVAILABLE:
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
        else:
            load_dotenv('env', override=True)
    else:
        if os.path.exists(env_file):
            manual_load_dotenv(env_file)
        else:
            manual_load_dotenv('env')

# Запускаем загрузку
load_all_dotenvs()

# Импорт адаптивных настроек (опционально, с fallback)
try:
    # Попытка импорта из корня проекта
    try:
        from adaptive_settings import get_adaptive_setting, AdaptiveKeys  # type: ignore
    except ImportError:
        # Fallback: импорт из archive/experimental
        from archive.experimental.adaptive_settings import get_adaptive_setting, AdaptiveKeys  # type: ignore
except ImportError:
    # Если модуль недоступен, создаем заглушки
    def get_adaptive_setting(key: str, default_value):
        """Заглушка для get_adaptive_setting, если модуль недоступен"""
        return default_value

    class AdaptiveKeys:
        """Заглушка для AdaptiveKeys, если модуль недоступен"""
        DYNAMIC_CALC_INTERVAL = "DYNAMIC_CALC_INTERVAL"
        DYNAMIC_TP_ENABLED = "DYNAMIC_TP_ENABLED"
        VOLUME_BLOCKS_ENABLED = "VOLUME_BLOCKS_ENABLED"
        ADAPTIVE_ENGINE_ENABLED = "ADAPTIVE_ENGINE_ENABLED"
        METRICS_FEEDER_ENABLED = "METRICS_FEEDER_ENABLED"
        METRICS_FEEDER_INTERVAL_SEC = "METRICS_FEEDER_INTERVAL_SEC"
        METRICS_CACHE_TTL_SEC = "METRICS_CACHE_TTL_SEC"
        PERFORMANCE_LOOKBACK_DAYS = "PERFORMANCE_LOOKBACK_DAYS"
        ADAPTIVE_ENTRY_ADJ_ENABLED = "ADAPTIVE_ENTRY_ADJ_ENABLED"
        ADAPTIVE_ENTRY_MAX_ADJUST_PCT = "ADAPTIVE_ENTRY_MAX_ADJUST_PCT"
        DYNAMIC_MODE_SWITCH_ENABLED = "DYNAMIC_MODE_SWITCH_ENABLED"
        CORRELATION_COOLDOWN_ENABLED = "CORRELATION_COOLDOWN_ENABLED"
        CORRELATION_LOOKBACK_HOURS = "CORRELATION_LOOKBACK_HOURS"
        CORRELATION_MAX_PAIRWISE = "CORRELATION_MAX_PAIRWISE"
        CORRELATION_COOLDOWN_SEC = "CORRELATION_COOLDOWN_SEC"
        SOFT_BLOCKLIST_ENABLED = "SOFT_BLOCKLIST_ENABLED"
        SOFT_BLOCKLIST_HYSTERESIS = "SOFT_BLOCKLIST_HYSTERESIS"
        SOFT_BLOCK_COOLDOWN_HOURS = "SOFT_BLOCK_COOLDOWN_HOURS"
        MIN_ACTIVE_COINS = "MIN_ACTIVE_COINS"
        BLOCKLIST_CHURN_FRAC = "BLOCKLIST_CHURN_FRAC"

# Default filter mode for signals if user has no explicit preference
DEFAULT_FILTER_MODE = "strict"  # options: 'strict' | 'soft'

# Список стейблкоинов - сигналы по ним не генерируются
STABLECOIN_SYMBOLS = [
    "USDTUSDT", "USDCUSDT", "BUSDUSDT", "FDUSDUSDT", "TUSDUSDT",
    "USDDUSDT", "USDEUSDT", "DAIUSDT", "FRAXUSDT", "LUSDUSDT",
    "USTCUSDT", "USTUSDT", "MIMUSDT", "ALGUSDT", "EURSUSDT", "USD1USDT"
]

# --- BTC trend filter tuning (practical defaults) ---
# EMA periods for soft/strict trend checks on 1h
BTC_TREND_EMA_SOFT = 50
BTC_TREND_EMA_STRICT = 200
# Lookback candles for additional stability (1h candles)
BTC_TREND_LOOKBACK = 50
# Additional protection: block longs after sharp drops beyond
# this threshold (percent)
BTC_TREND_MAX_DROP_PCT = 8.0
# Multi-timeframe confirmation (require 4h trend agreement)
BTC_TREND_USE_MULTITF = True

# --- ETH trend filter tuning ---
USE_ETH_TREND_FILTER = os.getenv("USE_ETH_TREND_FILTER", "true").lower() in ("1", "true", "yes")
ETH_TREND_FILTER_SOFT = os.getenv("ETH_TREND_FILTER_SOFT", "true").lower() in ("1", "true", "yes")
ETH_TREND_EMA_SOFT = 50
ETH_TREND_EMA_STRICT = 200

# --- SOL trend filter tuning ---
USE_SOL_TREND_FILTER = os.getenv("USE_SOL_TREND_FILTER", "true").lower() in ("1", "true", "yes")
SOL_TREND_FILTER_SOFT = os.getenv("SOL_TREND_FILTER_SOFT", "true").lower() in ("1", "true", "yes")
SOL_TREND_EMA_SOFT = 50
SOL_TREND_EMA_STRICT = 200

# Safe fallback for diagnostics expecting COINS
# По умолчанию ИСПОЛЬЗУЕМ фиксированный портфель COINS, авто-подбор можно включить через env
# 🔧 НОВАЯ ЛОГИКА (2025-12-14):
# - Авто-подбор из API (раз в сутки) - основной источник монет
# - Монеты без оптимизированных параметров добавляются и оптимизируются
# - Торговля блокируется до завершения оптимизации
# - intelligent_filter_system используется как источник оптимизированных параметров
AUTO_FETCH_COINS = os.getenv(
    "AUTO_FETCH_COINS", "true"  # 🔧 ИЗМЕНЕНО: используем авто-подбор как основной источник
).lower() in ("1", "true", "yes")
# Финальный портфель TOP-10 по результатам годового бектеста SOL_HIGH (2025-11-16)
# См. отчёт: final_portfolio_backtest_20251116_230305.json
# 🚀 ГИБРИДНАЯ СТРАТЕГИЯ: ТОП-20 ЛИКВИДНЫЕ МОНЕТЫ
# Критерии: 24h volume > $50M, Market cap > $1B, высокая ликвидность
COINS = [
    # Базовые (топ-3) - самая высокая ликвидность
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",

    # Топ альткоины (высокая ликвидность)
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",   # +182.40 USDT, WR 47.06%, PF 1.22
    "DOGEUSDT",
    "LINKUSDT",
    "AVAXUSDT",  # +174.17 USDT, WR 61.90%, PF 1.15
    "LTCUSDT",
    "TRXUSDT",

    # Перспективные (средняя-высокая ликвидность)
    "UNIUSDT",
    "NEARUSDT",
    "ICPUSDT",
    "SUIUSDT",
    "FETUSDT",
    "TAOUSDT",
    "ATOMUSDT",
    "OPUSDT",    # +19.56 USDT, WR 42.86%, PF 1.01
    "ARBUSDT",
    "DOTUSDT",   # +123.54 USDT, WR 43.75%, PF 1.15
    "CRVUSDT",   # +82.38 USDT, WR 43.48%, PF 1.06
]
# Инициализация COINS отложена до запуска event loop
# чтобы избежать вызова асинхронной функции при импорте
def initialize_coins_sync():
    """Синхронная инициализация списка монет"""
    if AUTO_FETCH_COINS:
        try:
            from src.execution.exchange_api import get_filtered_top_usdt_pairs_fast  # pylint: disable=import-outside-toplevel
            # Проверяем, есть ли уже запущенный event loop
            import asyncio  # pylint: disable=import-outside-toplevel
            try:
                loop = asyncio.get_running_loop()
                # Если есть запущенный loop, создаем новый в отдельном потоке
                import concurrent.futures  # pylint: disable=import-outside-toplevel

                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(get_filtered_top_usdt_pairs_fast(top_n=150, final_limit=50))
                    finally:
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_new_loop)
                    fetched_coins = future.result(timeout=30)  # Таймаут 30 секунд
                    return fetched_coins

            except RuntimeError:
                # Нет запущенного loop, создаем новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    fetched_coins = loop.run_until_complete(get_filtered_top_usdt_pairs_fast(top_n=150, final_limit=50))
                    return fetched_coins
                finally:
                    loop.close()
        except (ImportError, ModuleNotFoundError, ValueError, RuntimeError, OSError, concurrent.futures.TimeoutError):
            pass
    return None

# ============================================================================
# ОБНОВЛЕННАЯ КОНФИГУРАЦИЯ С УСИЛЕННЫМИ БЛОКАМИ
# Оптимизирована для качественных сигналов при ручной торговле
# ============================================================================
DATABASE = os.getenv("DATABASE", "trading.db")
MIN_DIFF_PERCENT = float(os.getenv("MIN_DIFF_PERCENT", "0.5"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_TOKEN_DEV = os.getenv("TELEGRAM_TOKEN_DEV", "")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS")

# API ключи для новостных источников
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
TRADINGVIEW_API_KEY = os.getenv("TRADINGVIEW_API_KEY", "")
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "")

ATRA_ENV = os.getenv("ATRA_ENV", "dev").lower().strip()
# prod -> TELEGRAM_TOKEN, иначе -> TELEGRAM_TOKEN_DEV
# (с фолбэком на prod, если dev пуст)
TOKEN = (
    TELEGRAM_TOKEN if ATRA_ENV == "prod" else (
        TELEGRAM_TOKEN_DEV or TELEGRAM_TOKEN
    )
)

# Автоматическое исполнение ордеров
# В DEV окружении всегда отключено, в PROD можно включить через переменную окружения
AUTO_EXECUTION_ENABLED = (
    ATRA_ENV == "prod" and
    os.getenv("AUTO_EXECUTION_ENABLED", "false").lower() in ("1", "true", "yes")
)
# --- TP adjustments (absolute percentage points to subtract) ---
# Смещаем TP1 чуть ближе для ускоренного выхода, TP2 умеренно
TP1_OFFSET_PCT = 0.9  # слегка ближе, чтобы чаще исполнялся TP1
TP2_OFFSET_PCT = 0.7

# Доля расстояния до нового TP2, на которой ставится новый TP1 (0..1)
TP1_RATIO_OF_TP2 = 0.7  # доля TP2, куда ставим TP1

# Минимальная доля нового TP2 для TP1 (чтобы TP1 не был слишком близко)
TP1_MIN_RATIO_OF_TP2 = 0.55

# Внутренний сдвиг TP2 на N тиков, чтобы цель чаще исполнялась
# Можно переопределить через переменную окружения TP2_INWARD_TICKS
# Подвигаем TP2 внутрь на 12 тиков по умолчанию (можно менять через env)
TP2_INWARD_TICKS = int(os.getenv("TP2_INWARD_TICKS", "16"))

# --- Комиссии (в процентах от нотионала) ---
# По умолчанию считаем такерскую комиссию.
# При необходимости можно расширить на мейкер.
SPOT_TAKER_FEE_PCT = 0.10   # 0.10%
FUTURES_TAKER_FEE_PCT = 0.04 # 0.04%

# --- DCA триггеры (адаптивные) ---
# Минимальный кулдаун после принятия сигнала, прежде чем
# предлагать DCA (в минутах)
DCA_MIN_COOLDOWN_MIN = 10  # оставляем без изменений
# Базовый минимальный процент отклонения от средней цены входа для DCA
DCA_MIN_DEV_PCT_BASE = 1.0  # ещё снижено (было 1.4)
# Множитель от ATR% для адаптивного порога отклонения
DCA_MIN_DEV_ATR_MULT = 0.9  # ещё снижено (было 1.0)

# --- MTF накопление / скоринг ---
# Полураспад веса события (в секундах) для экспоненциального затухания скоринга
ACCUM_SCORE_HALF_LIFE_SEC = 3600  # 1 час
# Окно, из которого берём события при расчёте скоринга (секунд)
ACCUM_SCORE_WINDOW_SEC = 12 * 3600  # 12 часов
# Окно событий для отображения строки накопления (секунд)
ACCUM_DISPLAY_WINDOW_SEC = 6 * 3600  # 6 часов
# Масштаб перевода score -> 0..100 (до клипа)
ACCUM_PERCENT_SCALE = 16  # было 12; 16 даёт чувствительность при множественных конфирмах

# Максимальное количество усреднений на позицию
MAX_DCA = 4

# Дополнительные подтверждения DCA
# Требовать K закрытий 1m за порогом отклонения (для подавления шпилек)
DCA_REQUIRE_CLOSED_1M = True
DCA_CLOSED_1M_COUNT = 2  # 1 или 2
# Ретест/гистерезис после пробоя порога: ждать микро-откат h*ATR и повторное удержание
DCA_RETEST_ENABLED = True
DCA_RETEST_H_MULT = 0.15  # 0.10–0.20
DCA_EPSILON_ATR_MULT = 0.05  # допуск к порогу в долях ATR

# Максимальное число одновременных символов (лимит открытых позиций)
MAX_CONCURRENT_SYMBOLS = 6

# Минимальный нотионал на позицию (для расчёта доступного количества позиций от депозита)
MIN_NOTIONAL_PER_POSITION_USDT = 200.0

# Динамический портфельный риск: общий риск на портфель (% от депозита)
PORTFOLIO_MAX_RISK_PCT = 8.0  # суммарный риск портфеля 8%
# Нижняя/верхняя границы количества позиций
PORTFOLIO_MIN_POSITIONS = 2
PORTFOLIO_MAX_POSITIONS_HARD = 6  # Максимум 6 позиций одновременно

# Таймфрейм для динамических расчётов при принятии сигнала (e.g., '1h', '1m')
# Теперь из базы данных
def _get_dynamic_calc_interval():
    """Получает интервал динамических расчётов из адаптивных настроек"""
    return get_adaptive_setting(
        AdaptiveKeys.DYNAMIC_CALC_INTERVAL,
        os.getenv("DYNAMIC_CALC_INTERVAL", "1h")
    )

DYNAMIC_CALC_INTERVAL = _get_dynamic_calc_interval()

# ============================================================================
# НАСТРОЙКИ УСИЛЕННЫХ БЛОКОВ ДЛЯ КАЧЕСТВЕННЫХ СИГНАЛОВ
# ============================================================================

# Настройки фильтров риска
# 🔧 ИСПРАВЛЕНИЕ: Снижены пороги из-за проблем с depth (ETHUSDT показывает 1,922 USD)
# require_both изменен на False - достаточно одного условия (volume ИЛИ depth)
RISK_FILTERS = {
    "min_volume_24h": 10_000_000,  # Минимальный объем 24ч (10M) — снижено с 30M для расширения охвата
    "min_market_cap": 50_000_000,  # Минимальная капитализация 50M USD (снижено со 100M)
    "max_spread_pct": 0.5,  # Максимальный спред 0.5% (увеличено с 0.25%)
    "min_depth_usd": 10_000,  # Минимальная глубина ордербука 10K USD (снижено с 20K)
    "min_price": 0.01,  # Минимальная цена $0.01
    "max_price": 100_000,  # Максимальная цена $100K
    "max_volatility_pct": 15.0,  # Максимальная волатильность 15%
    "min_profit_pct": 0.5,  # Минимальная прибыль 0.5%
    "max_profit_pct": 5.0,  # Максимальная прибыль 5%
    "enable_risk_filters": True,  # Включаем фильтры риска
    "use_market_cap_filter": True,  # Включаем фильтр по капитализации
}

# Сокращённая ссылка на блок настроек краткосрочной торговли
# Перенесено ниже, после определения ENHANCED_STRATEGY_CONFIG

# Пороговые значения ОЦЕНКИ (0..100) для фильтрации сигналов
# В строгом режиме порог выше, в мягком — ниже
SIGNAL_SCORE_THRESHOLDS = {
    "strict": 55,
    "soft": 44,
}

# ============================================================================
# НАСТРОЙКИ АДАПТИВНЫХ RSI УРОВНЕЙ
# ============================================================================

# Включение/отключение адаптивных RSI уровней по волатильности
USE_ADAPTIVE_RSI_LEVELS = True  # Использовать адаптивные уровни для разных символов

# ============================================================================
# НАСТРОЙКИ УСИЛЕННЫХ БЛОКОВ
# ============================================================================

# Включение/отключение усиленных блоков
ENHANCED_BLOCKS_ENABLED = True

# Настройки усиленных блоков для качественных сигналов
ENHANCED_BLOCKS_CONFIG = {
    # Усиленные условия для блоков
    "blocks_ratio_threshold": 1.8,  # Усилено с 2.5 до 1.8 (более строгий)
    "min_blocks_required": 2,  # Минимум 2 блока с каждой стороны для надежности
    "quality_score_threshold": 0.5,  # Минимальный показатель качества сигнала
    # Дополнительные фильтры качества
    "volume_ratio_min": 0.8,  # Минимальный объем (ослаблено для краткосрочной торговли)
    # 🔧 НОВЫЕ ПАРАМЕТРЫ ДЛЯ АДАПТИВНОГО VOLUME_RATIO
    "soft_volume_ratio_min": 0.3,  # Минимальный volume_ratio для soft режима (снижено с 0.8)
    "strict_volume_ratio_min": 1.5,  # Минимальный volume_ratio для strict режима (без изменений)
    "use_indicator_compensation": True,  # Использовать компенсацию volume_ratio при сильных индикаторах
    "indicator_compensation_strength_threshold": 0.6,  # Порог силы индикаторов для компенсации
    "use_ai_volume_adaptation": True,  # 🤖 Использовать AI адаптацию volume_ratio (гибридный подход)
    "rsi_overbought_max": 78,  # Максимальный RSI для LONG (оптимизировано для крипто, было 80)
    "rsi_oversold_min": 22,  # Минимальный RSI для SHORT (оптимизировано для крипто, было 20)
    # Настройки для краткосрочной торговли
    "short_term_trading": {
        "enabled": True,
        "bb_position_max": 0.99,  # Цена не у самой границы BB
        "bb_position_min": 0.01,  # Цена не у самой границы BB
        "ema_confirmation": True,  # Подтверждение EMA
        "volume_confirmation": True,  # Подтверждение объемом
    },
    # Настройки динамического плеча
    "dynamic_leverage": {
        "enabled": True,
        "base_leverage": 3,
        "max_leverage": 7,
        "volatility_adjustment": True,
    },
    # Настройки take profi
    "dynamic_tp": {
        "enabled": True,
        "tp1_min": 0.5,  # Минимальный TP1 0.5%
        "tp1_max": 2.2,  # Максимальный TP1 2.2%
        "tp2_min": 1.0,  # Минимальный TP2 1.0%
        "tp2_max": 4.4,  # Максимальный TP2 4.4%
    },
}

# ============================================================================
# НАСТРОЙКИ РАСШИРЕННОЙ СТРАТЕГИИ BOLLINGER BANDS
# ============================================================================

# Включение/отключение расширенной стратегии
ENHANCED_BOLLINGER_STRATEGY = True

# Настройки индикаторов для расширенной стратегии
ENHANCED_STRATEGY_CONFIG = {
    # Bollinger Bands настройки
    "bb_window": 20,
    "bb_std": 2.0,
    # EMA настройки
    "ema_fast": 12,
    "ema_slow": 39,
    "ema_trend": 50,
    # RSI настройки - ОПТИМИЗИРОВАНЫ ПО РЕЗУЛЬТАТАМ БЕКТЕСТА
    "rsi_window": 14,
    "rsi_overbought": 90,  # УЛЬТРА-МЯГКИЙ для мягкого режима (было 75)
    "rsi_oversold": 10,  # УЛЬТРА-МЯГКИЙ для мягкого режима (было 25)
    "rsi_neutral_high": 85,  # МАКСИМАЛЬНО МЯГКИЙ для строгого режима (было 70)
    "rsi_neutral_low": 15,  # МАКСИМАЛЬНО МЯГКИЙ для строгого режима (было 30)
    # ATR настройки для волатильности
    "atr_window": 15,
    "atr_multiplier_sl": 1.7,
    # Настройки пробоя полос Боллинджера
    "breakout_config": {
        "volume_confirmation": True,
        "rsi_confirmation": True,
        "min_breakout_pct": 1.2,
        "golden_cross_confirmation": True,
        "trend_strength_min": 0.3,
        "momentum_confirmation": True,
    },
    # Настройки возврата к средней - ОПТИМИЗИРОВАНЫ ДЛЯ КРАТКОСРОЧНОЙ ТОРГОВЛИ
    "mean_reversion_config": {
        "volume_enhancement": True,
        "trend_filter": True,
        "min_reversion_pct": 1.2,
        "rsi_extreme_overbought": 80,  # Ослаблено для краткосрочной торговли
        "rsi_extreme_oversold": 20,  # Ослаблено для краткосрочной торговли
        "bb_touch_threshold": 0.008,
        "reversion_strength_min": 1.2,
        "volume_spike_threshold": 2.0,
        "confirmation_candles": 4,
        "max_hold_time_hours": 24,
        "bb_width_min": 1.5,
        "bb_width_max": 18.0,
        "atr_min_pct": 0.5,
        "atr_max_pct": 10.0,
        "trend_strength_max": 7.0,
        "price_change_1h_min": 0.2,
        "price_change_4h_min": 0.5,
        "max_recent_signals": 4,
        "sentiment_threshold": 0.4,
        "sentiment_enabled": True,
    },
    # Настройки индекса страха и жадности
    "fear_greed_settings": {
        "fear_greed_enabled": True,
        "fear_greed_strict_threshold": 75,
        "fear_greed_soft_threshold": 85,
    },
    # Настройки squeeze detection
    "squeeze_config": {
        "enabled": True,
        "min_bb_width_pct": 1.5,
        "volume_expansion_threshold": 2.0,
        "squeeze_duration_min": 4,
        "breakout_confirmation": True,
    },
    # Настройки динамического управления
    "dynamic_management": {
        "atr_based_sl": True,
        "volatility_adjustment": True,
        "auto_optimization": True,
        "position_sizing_risk": 2.0,
        "max_positions_per_symbol": 1,
        "profit_taking_ratio": 1.8,
        "trailing_stop_enabled": False,
        "trailing_stop_distance": 1.0,
    },
    # 🆕 Продвинутая адаптивная система trailing stop
    "ADAPTIVE_TRAILING_CONFIG": {
        "enabled": True,
        # Настройки волатильности
        "volatility_regimes": {
            "LOW": {"max_ratio": 1.0, "min_ratio": 0.8, "atr_threshold": 0.01},
            "MEDIUM": {"max_ratio": 0.8, "min_ratio": 0.5, "atr_threshold": 0.025},
            "HIGH": {"max_ratio": 0.6, "min_ratio": 0.3, "atr_threshold": 0.05},
            "EXTREME": {"max_ratio": 0.4, "min_ratio": 0.2, "atr_threshold": 0.1}
        },
        # Настройки тренда
        "trend_strength": {
            "STRONG": 1.3,    # +30% при сильном тренде
            "MEDIUM": 1.1,    # +10% при среднем тренде
            "WEAK": 1.0,      # Без изменений
            "RANGING": 0.7,   # -30% при боковике
            "REVERSAL": 0.5   # -50% при развороте
        },
        # Временные факторы
        "time_factors": {
            "HIGH_VOLATILITY_HOURS": [9, 10, 16, 17],  # Часы высокой волатильности
            "high_vol_multiplier": 0.8,
            "low_vol_multiplier": 1.2
        },
        # Дополнительные параметры
        "min_safe_distance_atr": 1.5,  # Минимальное расстояние в ATR
        "max_ratio": 1.2,
        "min_ratio": 0.15
    },
    # Настройки для краткосрочной торговли
    "profit_distribution_config": {
        "max_daily_trades": 5,
        "min_trade_interval_hours": 2,
        "correlation_filter": True,
        "max_correlation_threshold": 0.8,
        "volatility_filter": True,
        "min_volatility_pct": 0.5,
        "max_volatility_pct": 15.0,
        "market_regime_filter": True,
        "trend_strength_threshold": 0.05,
        "max_positions_per_symbol": 1,
        "portfolio_max_positions": 8,
        "min_profit_per_trade": 0.3,
        "max_loss_per_trade": 2.5,
        "profit_taking_ratio": 1.5,
    },
    # Дублируем блок для удобного импорта параметров краткосрочной торговли
    # PROFIT_DISTRIBUTION_CONFIG используется в месте портфельных ограничений
}

# Сокращённая ссылка на блок настроек краткосрочной торговли
try:
    PROFIT_DISTRIBUTION_CONFIG = ENHANCED_STRATEGY_CONFIG.get("profit_distribution_config", {})
except NameError:
    PROFIT_DISTRIBUTION_CONFIG = {}

# --- News/Sentiment blending ---
# Включать ли смешивание новостного сентимента в общий контекст/риск
NEWS_SENTIMENT_BLEND_ENABLED = True
# Вес новостного компонента в общем сентименте (0..1)
NEWS_SENTIMENT_WEIGHT = 0.5

# --- Alert thresholds ---
# Порог длительности цикла (сек), при превышении присылаем алерт
CYCLE_ALERT_SEC = int(os.getenv("CYCLE_ALERT_SEC", "250"))
# Порог латентности внешних API (мс) для алерта
API_ALERT_MS = int(os.getenv("API_ALERT_MS", "2500"))
# Кулдаун (мин) между одинаковыми алертами
ALERT_COOLDOWN_MIN = int(os.getenv("ALERT_COOLDOWN_MIN", "30"))

# ----------------------------------------------------------------------------
# Bollinger direction filter and band-entry gating (configurable)
# ----------------------------------------------------------------------------
# Близость к средней полосе (epsilon) для фильтра направления
BB_DIR_NEAR_MID_EPSILON_STRICT = 0.07
BB_DIR_NEAR_MID_EPSILON_SOFT = 0.11

# Длина окна для расчёта наклона (slope) средней/EMA50
BB_DIR_SLOPE_LOOKBACK = 4
BB_DIR_USE_EMA50_SLOPE = True

# ADX пороги у средней (mid) — гейтинг силы тренда
BB_DIR_ADX_THRESHOLD_STRICT = 24.0
BB_DIR_ADX_THRESHOLD_SOFT = 20.0

# ADX пороги у касаний/ретестов верхней/нижней полос
BAND_ENTRY_ADX_STRICT = 21.0
BAND_ENTRY_ADX_SOFT = 10.0  # Смягчено с 18.0 для увеличения генерации сигналов

# Lookback для оценки наклона EMA50 у полос
BAND_ENTRY_EMA50_SLOPE_LOOKBACK = 4

# Режимы расширенной стратегии
ENHANCED_STRATEGY_MODES = {
    "breakout": {
        "enabled": True,
        "description": "Пробой полос Боллинджера с подтверждением EMA и RSI",
        "priority": 1,
    },
    "mean_reversion": {
        "enabled": True,
        "description": "Возврат к средней полосе с фильтрацией тренда",
        "priority": 2,
    },
    "squeeze_breakout": {
        "enabled": True,
        "description": "Пробой после сжатия полос с подтверждением объемом",
        "priority": 3,
    },
}

# ============================================================================
# НАСТРОЙКИ НОВОСТНЫХ ФИЛЬТРОВ
# ============================================================================

# Ручной флаг для отключения сигналов по новостям
NEWS_FILTER_ACTIVE = True

# Настройки времени для новостных фильтров
NEWS_SETTINGS = {
    "freshness_hours": 2,
    "negative_block_hours": 2,
    "positive_cache_hours": 0.1,
    "block_short_on_positive_news": True,
}

# Режимы новостного фильтра
NEWS_FILTER_MODES = {
    "conservative": {
        "block_short_on_positive": True,
        "block_long_on_negative": True,
        "enhance_long_on_positive": True,
        "enhance_short_on_negative": True,
        "description": "Консервативный - блокирует сигналы по новостям, усиливает по новостям",
    },
    "soft": {
        "block_short_on_positive": False,
        "block_long_on_negative": False,
        "enhance_long_on_positive": False,
        "enhance_short_on_negative": False,
        "description": "Мягкий - не блокирует и не усиливает сигналы по новостям",
    },
    "aggressive": {
        "block_short_on_positive": False,
        "block_long_on_negative": False,
        "enhance_long_on_positive": True,
        "enhance_short_on_negative": True,
        "description": "Агрессивный - не блокирует сигналы, усиливает по новостям",
    },
}

# Ключевые слова для фильтрации новостей
NEGATIVE_NEWS_KEYWORDS = [
    "hack",
    "exploit",
    "regulation",
    "ban",
    "lawsuit",
    "SEC",
    "CFTC",
    "liquidation",
    "delist",
    "scam",
    "fraud",
    "investigation",
    "arrest",
    "shutdown",
    "outage",
    "fork",
    "upgrade",
    "halving",
    "ETF",
    "approval",
    "rejection",
]

POSITIVE_NEWS_KEYWORDS = [
    "partnership",
    "adoption",
    "integration",
    "launch",
    "release",
    "upgrade",
    "update",
    "innovation",
    "growth",
    "expansion",
    "investment",
    "funding",
    "success",
    "milestone",
    "achievement",
    "breakthrough",
    "development",
    "technology",
    "solution",
    "platform",
    "ecosystem",
    "community",
    "governance",
    "staking",
    "yield",
    "rewards",
    "airdrop",
    "burn",
    "buyback",
    "dividend",
]

# Для обратной совместимости
NEWS_KEYWORDS = NEGATIVE_NEWS_KEYWORDS

# ============================================================================
# НАСТРОЙКИ СИСТЕМЫ ОТСЛЕЖИВАНИЯ КИТОВ
# ============================================================================

# Включение/отключение системы отслеживания китов
WHALE_TRACKING_ENABLED = True
WHALE_FREE_MODE = True

# === Defaults for tests ===
if 'WHALE_WALLETS' not in globals():
    WHALE_WALLETS = []  # дефолт для тестов

# Mapping chain tickers or symbols for whale tracking tests
if 'WHALE_TOKEN_MAPPING' not in globals():
    WHALE_TOKEN_MAPPING = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "USDT": "tether",
        "USDC": "usd-coin",
    }

# API ключи для блокчейнов
WHALE_API_KEYS = {
    "etherscan": os.getenv("ETHERSCAN_API_KEY", ""),
    "bscscan": os.getenv("BSCSCAN_API_KEY", ""),
    "polygonscan": os.getenv("POLYGONSCAN_API_KEY", ""),
    "arbiscan": os.getenv("ARBISCAN_API_KEY", ""),
}

# Минимальные значения транзакций для китов
WHALE_MIN_TRANSACTION_VALUES = {
    "BTC": 100,
    "ETH": 1000,
    "USDT": 1000000,
    "USDC": 1000000,
    "BNB": 10000,
    "SOL": 50000,
    "ADA": 1000000,
    "DOT": 100000,
    "LINK": 100000,
    "MATIC": 1000000,
    "AVAX": 50000,
    "UNI": 100000,
    "ATOM": 50000,
    "LTC": 10000,
    "XRP": 1000000,
}

# Настройки усиления сигналов китами
WHALE_ENHANCEMENT_SETTINGS = {
    "confidence_boost_confirm": 0.20,
    "confidence_boost_contradict": -0.10,
    "volume_ratio_threshold": 2.0,
    "cache_ttl_minutes": 30,
    "max_transactions_per_request": 1000,
}

# Настройки CONF (подтверждение сигналов крупными сделками)
# Окно анализа (минуты), множитель базовой медианы и минимальный порог USD
CONF_WINDOW_MIN = int(os.getenv("CONF_WINDOW_MIN", "60"))  # Увеличиваем окно до 60 минут
CONF_K_MULTIPLIER = float(os.getenv("CONF_K_MULTIPLIER", "1.2"))  # Снижаем множитель
CONF_MIN_THRESHOLD_USD = float(os.getenv("CONF_MIN_THRESHOLD_USD", "5000"))  # Снижаем порог до 5K USD

# ============================================================================
# НАСТРОЙКИ ДИНАМИЧЕСКИХ ФИЛЬТРОВ
# ============================================================================

# Включение/отключение фильтра тренда биткоина
USE_BTC_TREND_FILTER = True

# ============================================================================
# НАСТРОЙКИ НОВЫХ ФИЛЬТРОВ: Interest Zones + BTC Dominance
# ============================================================================

# Включение/отключение фильтра тренда доминации BTC
# По умолчанию ВКЛЮЧЕН (можно отключить через env: USE_DOMINANCE_TREND_FILTER=false)
USE_DOMINANCE_TREND_FILTER = os.getenv("USE_DOMINANCE_TREND_FILTER", "true").lower() in ("1", "true", "yes")

# Настройки фильтра доминации BTC
DOMINANCE_FILTER_CONFIG = {
    "block_long_on_rising": True,  # Блокировать LONG альтов при росте BTC.D
    "block_short_on_falling": True,  # Блокировать SHORT альтов при падении BTC.D
    "dominance_threshold_pct": 1.0,  # Порог изменения доминации (%)
    "min_days_for_trend": 1,  # Минимальное количество дней для определения тренда
}

# Включение/отключение фильтра зон интереса (Interest Zones)
# По умолчанию ВКЛЮЧЕН (можно отключить через env: USE_INTEREST_ZONE_FILTER=false)
USE_INTEREST_ZONE_FILTER = os.getenv("USE_INTEREST_ZONE_FILTER", "true").lower() in ("1", "true", "yes")

# Настройки фильтра зон интереса (ОПТИМИЗИРОВАНЫ)
INTEREST_ZONE_FILTER_CONFIG = {
    "lookback_periods": 50,  # Количество свечей для анализа (оптимизировано: было 100)
    "min_volume_cluster": 1.0,  # Минимальный объем кластера (оптимизировано: было 1.5)
    "zone_width_pct": 0.3,  # Ширина зоны (оптимизировано: было 0.5)
    "min_zone_strength": 0.5,  # Минимальная сила зоны (оптимизировано: было 0.6)
    # Использовать Order Book для точных зон (пока не реализовано, зарезервировано для будущего)
    "use_orderbook": False,
}

# Включение/отключение фильтра Фибоначчи
# По умолчанию ВКЛЮЧЕН (можно отключить через env: USE_FIBONACCI_ZONE_FILTER=false)
USE_FIBONACCI_ZONE_FILTER = os.getenv("USE_FIBONACCI_ZONE_FILTER", "true").lower() in ("1", "true", "yes")

# Настройки фильтра Фибоначчи (ОПТИМИЗИРОВАНЫ)
FIBONACCI_ZONE_FILTER_CONFIG = {
    "lookback_periods": 50,  # Количество свечей для анализа (оптимизировано: было 100)
    "tolerance_pct": 0.3,  # Допустимое отклонение от уровня (оптимизировано: было 0.5)
    "require_strong_levels": False,  # Требовать только сильные уровни (0.618, 0.382)
}

# Включение/отключение фильтра имбалансов объема
# 🔧 ВРЕМЕННО ОТКЛЮЧЕН для восстановления генерации сигналов
# По умолчанию ОТКЛЮЧЕН (можно включить через env: USE_VOLUME_IMBALANCE_FILTER=true)
USE_VOLUME_IMBALANCE_FILTER = os.getenv("USE_VOLUME_IMBALANCE_FILTER", "false").lower() in ("1", "true", "yes")

# ============================================================================
# ПАРАМЕТРЫ НОВЫХ ФИЛЬТРОВ (ОПТИМИЗИРОВАНЫ)
# ============================================================================

# Interest Zone Filter - оптимальные параметры
INTEREST_ZONE_FILTER_CONFIG = {
    'lookback_periods': 50,
    'min_volume_cluster': 1.0,
    'zone_width_pct': 0.3,
    'min_zone_strength': 0.5
}

# Fibonacci Zone Filter - оптимальные параметры
FIBONACCI_ZONE_FILTER_CONFIG = {
    'lookback_periods': 50,
    'tolerance_pct': 0.3,
    'require_strong_levels': False
}

# Volume Imbalance Filter - оптимальные параметры
# 🔧 ИСПРАВЛЕНО: временно отключено require_volume_confirmation
# Проблема: фильтр блокировал все сигналы даже с порогом 0.5 (volume_ratio < 0.5 для всех монет)
# Решение: отключаем требование подтверждения объемом, фильтр продолжает проверять имбаланс
# ⚠️ ВРЕМЕННО: для восстановления генерации сигналов
VOLUME_IMBALANCE_FILTER_CONFIG = {
    'lookback_periods': 10,
    'volume_spike_threshold': 1.5,
    'min_volume_ratio': 0.5,  # 🔧 Исправлено: было 1.0 → 0.8 → 0.6 → 0.5
    'require_volume_confirmation': False  # 🔧 ВРЕМЕННО ОТКЛЮЧЕНО: было True
}

# ============================================================================
# НАСТРОЙКИ ФИЛЬТРОВ VOLUME PROFILE И VWAP
# ============================================================================

# Включение/отключение фильтра Volume Profile (VPVR)
# ⚠️ НЕЭФФЕКТИВЕН: Блокирует только 0.9% сигналов, не дает преимуществ
# 📊 Статистика (2025-11-29): 228 проверок, 2 блокировки (0.9%),
# результаты идентичны baseline
# ✅ ВКЛЮЧЕН: был частью успешной оптимизации (+2,477%, 100% Win Rate)
# с оптимальным параметром volume_profile_threshold = 0.6
USE_VP_FILTER = os.getenv("USE_VP_FILTER", "true").lower() in ("1", "true", "yes")

# Включение/отключение фильтра VWAP
USE_VWAP_FILTER = os.getenv("USE_VWAP_FILTER", "true").lower() in ("1", "true", "yes")

# Включение/отключение фильтра Order Flow (Cumulative Delta Volume, Volume Delta, Pressure Ratio)
USE_ORDER_FLOW_FILTER = os.getenv("USE_ORDER_FLOW_FILTER", "true").lower() in ("1", "true", "yes")

# Включение/отключение Exhaustion фильтра для раннего выхода
USE_EXHAUSTION_FILTER = os.getenv("USE_EXHAUSTION_FILTER", "true").lower() in ("1", "true", "yes")

# Включение/отключение Microstructure фильтра (Liquidity Zones, Absorption Levels)
USE_MICROSTRUCTURE_FILTER = os.getenv("USE_MICROSTRUCTURE_FILTER", "true").lower() in ("1", "true", "yes")

# Включение/отключение Momentum фильтра (MFI, Stochastic RSI)
# ✅ ВКЛЮЧЕН: Будет оптимизирован для отсечения убыточных сделок
USE_MOMENTUM_FILTER = os.getenv("USE_MOMENTUM_FILTER", "true").lower() in ("1", "true", "yes")

# Включение/отключение Trend Strength фильтра (ADX, TSI)
# ✅ ВКЛЮЧЕН: Будет оптимизирован для отсечения убыточных сделок
USE_TREND_STRENGTH_FILTER = os.getenv("USE_TREND_STRENGTH_FILTER", "true").lower() in ("1", "true", "yes")

# Включение/отключение Auction Market Theory (AMT) фильтра
USE_AMT_FILTER = os.getenv("USE_AMT_FILTER", "true").lower() in ("1", "true", "yes")

# Включение/отключение Market Profile (TPO) фильтра
USE_MARKET_PROFILE_FILTER = os.getenv("USE_MARKET_PROFILE_FILTER", "true").lower() in ("1", "true", "yes")

# Включение/отключение Institutional Patterns фильтра
USE_INSTITUTIONAL_PATTERNS_FILTER = (
    os.getenv("USE_INSTITUTIONAL_PATTERNS_FILTER", "true").lower() in ("1", "true", "yes")
)

# Настройки Volume Profile
# Оптимизированные параметры: volume_profile_threshold = 0.6
VP_FILTER_CONFIG = {
    "bins": 50,  # Количество бинов (улучшено с 24 до 50)
    "default_lookback": 100,  # Дефолтный lookback период (улучшено с 20 до 100)
    "value_area_pct": 0.70,  # Процент объема для Value Area
    "tolerance_pct": 1.0,  # Допустимое отклонение от уровня (%)
    "volume_profile_threshold": 0.6,  # Оптимизировано: 0.6 (влияет на tolerance и value_area)
}

# Настройки VWAP
# Оптимизированные параметры: vwap_threshold = 0.6
VWAP_FILTER_CONFIG = {
    "reset_time": "00:00:00",  # Время сброса Daily VWAP (UTC)
    "sd_multipliers": [1.0, 2.0],  # Множители для полос стандартного отклонения
    "vwap_threshold": 0.6,  # Оптимизировано: 0.6 (влияет на множители SD)
}

# Настройки Auction Market Theory (AMT)
# Оптимизированные параметры: lookback=20, balance=0.3, imbalance=0.5
AMT_FILTER_CONFIG = {
    "lookback": 20,  # Период для анализа (оптимизировано: 20)
    "balance_threshold": 0.3,  # Порог для определения баланса (оптимизировано: 0.3)
    "imbalance_threshold": 0.5,  # Порог для определения дисбаланса (оптимизировано: было 0.6, стало 0.5)
}

# Настройки Market Profile (TPO)
# Оптимизированные параметры: tolerance_pct = 1.5
MARKET_PROFILE_FILTER_CONFIG = {
    "bins": 50,  # Количество бинов
    "value_area_pct": 0.70,  # Процент для Value Area
    "default_lookback": 100,  # Дефолтный lookback период
    "tolerance_pct": 1.5,  # Допустимое отклонение от Value Area (%) (оптимизировано: было 1.0, стало 1.5)
}

# Настройки Institutional Patterns
# Оптимизированные параметры: min_quality_score = 0.6
INSTITUTIONAL_PATTERNS_FILTER_CONFIG = {
    "min_quality_score": 0.6,  # Минимальный балл качества сигнала (оптимизировано: 0.6)
    "iceberg_large_trade_threshold": 2.0,  # Порог для большой сделки (в стандартных отклонениях)
    "iceberg_min_size": 5,  # Минимальное количество больших сделок для паттерна
    "spoofing_volume_price_divergence_threshold": 0.5,  # Порог расхождения объема и цены
}

# Настройки Order Flow фильтра
# Оптимизированные параметры из успешного бэктеста (+2,477%): required_confirmations=0, pr_threshold=0.5
ORDER_FLOW_FILTER_CONFIG = {
    "required_confirmations": 0,  # Количество подтверждений (оптимизировано: 0 - без подтверждений)
    "pr_threshold": 0.5,  # Порог Pressure Ratio (оптимизировано: 0.5)
    "lookback": 20,  # Период для анализа
}

# Настройки Microstructure фильтра
# Оптимизированные параметры из успешного бэктеста (+2,477%): tolerance_pct=2.5, min_strength=0.1, lookback=30
MICROSTRUCTURE_FILTER_CONFIG = {
    "tolerance_pct": 2.5,  # Допустимое отклонение от уровня ликвидности (%) (оптимизировано: 2.5)
    "min_strength": 0.1,  # Минимальная сила уровня (оптимизировано: 0.1)
    "lookback": 30,  # Период для анализа (оптимизировано: 30)
}

# Настройки Momentum фильтра
# Оптимизированные параметры из успешного бэктеста (+2,477%): mfi_long=50, mfi_short=50, stoch_long=50, stoch_short=50
MOMENTUM_FILTER_CONFIG = {
    "mfi_long": 50,  # Порог MFI для LONG (оптимизировано: 50)
    "mfi_short": 50,  # Порог MFI для SHORT (оптимизировано: 50)
    "stoch_long": 50,  # Порог Stochastic RSI для LONG (оптимизировано: 50)
    "stoch_short": 50,  # Порог Stochastic RSI для SHORT (оптимизировано: 50)
}

# Настройки Trend Strength фильтра
# Оптимизированные параметры из успешного бэктеста (+2,477%): adx_threshold=15, require_direction=false
TREND_STRENGTH_FILTER_CONFIG = {
    "adx_threshold": 15,  # Порог ADX (оптимизировано: 15 - низкий порог)
    "require_direction": False,  # Требовать направление тренда (оптимизировано: False - не требуется)
}

# Настройки фильтра имбалансов объема (ОПТИМИЗИРОВАНЫ)
# 🔧 ИСПРАВЛЕНО: min_volume_ratio снижен с 1.0 до 0.8 (дубликат удален, используется определение выше)
# VOLUME_IMBALANCE_FILTER_CONFIG определен выше (строка 839)

# Включение/отключение динамических TP/SL от зон (Фибоначчи + Interest Zones)
# По умолчанию ВКЛЮЧЕН (можно отключить через env: USE_DYNAMIC_TP_SL_FROM_ZONES=false)
USE_DYNAMIC_TP_SL_FROM_ZONES = os.getenv("USE_DYNAMIC_TP_SL_FROM_ZONES", "true").lower() in ("1", "true", "yes")

# Включение/отключение новой логики входа на откате (вместо EMA кроссовера)
# По умолчанию ВКЛЮЧЕН для тестирования (можно отключить через env: USE_PULLBACK_ENTRY=false)
USE_PULLBACK_ENTRY = os.getenv("USE_PULLBACK_ENTRY", "true").lower() in ("1", "true", "yes")

# Настройки новой логики входа на откате
PULLBACK_ENTRY_CONFIG = {
    "min_quality_score": 0.7,  # Минимальная оценка качества входа (0.0-1.0) - оптимизировано с 0.6
    "require_trend": True,  # Требовать тренд для входа
    "support_tolerance_pct": 0.8,  # Допустимое отклонение от поддержки (%) - оптимизировано с 1.0
    "resistance_tolerance_pct": 0.8,  # Допустимое отклонение от сопротивления (%) - оптимизировано с 1.0
}

# Включение/отключение адаптивной стратегии (разные стратегии для разных режимов рынка)
# По умолчанию ВКЛЮЧЕН (можно отключить через env: USE_ADAPTIVE_STRATEGY=false)
USE_ADAPTIVE_STRATEGY = os.getenv("USE_ADAPTIVE_STRATEGY", "true").lower() in ("1", "true", "yes")

# Настройки адаптивной стратегии
ADAPTIVE_STRATEGY_CONFIG = {
    "base_risk": 0.02,  # Базовый риск (2%)
    "enable_adaptive_risk": True,  # Включить адаптивный риск на основе качества входа
    "max_risk_multiplier": 1.5,  # Максимальный множитель риска (для высококачественных сигналов)
    "min_risk_multiplier": 0.5,  # Минимальный множитель риска (для слабых сигналов)
}

BTC_TREND_FILTER_SOFT = True

# Включение/отключение расширенных фильтров
ENHANCED_FILTERS = True

# Динамические уровни take profit - теперь из базы данных
def _get_dynamic_tp_settings():
    """Получает настройки динамических TP из адаптивных настроек"""
    return {
        'DYNAMIC_TP_ENABLED': get_adaptive_setting(AdaptiveKeys.DYNAMIC_TP_ENABLED, True),
        'VOLUME_BLOCKS_ENABLED': get_adaptive_setting(AdaptiveKeys.VOLUME_BLOCKS_ENABLED, True)
    }

_dynamic_tp_settings = _get_dynamic_tp_settings()
DYNAMIC_TP_ENABLED = _dynamic_tp_settings['DYNAMIC_TP_ENABLED']
VOLUME_BLOCKS_ENABLED = _dynamic_tp_settings['VOLUME_BLOCKS_ENABLED']

# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ
# ============================================================================

TRADE_FEES_DEFAULT = {"Bybit": 0.001, "MEXC": 0.001}
AMOUNTS_DEFAULT = {"BTCUSDT": 0.01, "ETHUSDT": 0.5, "SOLUSDT": 10}

# Комиссии по биржам и парам
FEES = {
    "Bybit": 0.001,
    "Binance": 0.00075,
    "BTCUSDT": 0.0005,
}

# Настройки для бесплатных API
WHALE_FREE_API_ENABLED = True
WHALE_FREE_API_SOURCES = [
    "etherscan_free",
    "bscscan_free",
    "polygonscan_free",
    "arbiscan_free",
]

WHALE_FREE_API_LIMITS = {
    "requests_per_second": 5,
    "requests_per_minute": 300,
    "requests_per_day": 100000,
}

# ----------------------------------------------------------------------------
# Политика хранения данных (ретенция)
# Стандартный профиль для intraday/1h: quotes 14d, signals/arbitrage 90d,
# history 365d, accum 2d, cache очищается по TTL, VACUUM еженедельно.
# Можно переопределить через переменные окружения.
# ----------------------------------------------------------------------------
RETENTION_QUOTES_DAYS = int(os.getenv("RETENTION_QUOTES_DAYS", "14"))
RETENTION_SIGNALS_DAYS = int(os.getenv("RETENTION_SIGNALS_DAYS", "90"))
RETENTION_SIGNALS_LOG_DAYS = int(os.getenv("RETENTION_SIGNALS_LOG_DAYS", "365"))
RETENTION_ACCUM_EVENTS_DAYS = int(os.getenv("RETENTION_ACCUM_EVENTS_DAYS", "2"))
RETENTION_APP_CACHE_DAYS = int(os.getenv("RETENTION_APP_CACHE_DAYS", "3"))
RETENTION_ENABLE_WEEKLY_VACUUM = (
    os.getenv("RETENTION_ENABLE_WEEKLY_VACUUM", "true")
    .lower()
    in ("1", "true", "yes")
)

# ============================================================================
# АДАПТИВНЫЙ ДВИЖОК (ФАЗА 1) - ТЕПЕРЬ ИЗ БАЗЫ ДАННЫХ
# Включаем мягкую авто-настройку порогов, фидер метрик и корреляционный кулдаун
# ============================================================================

# Используем уже импортированные get_adaptive_setting и AdaptiveKeys
# Главный флаг адаптивного движка
ADAPTIVE_ENGINE_ENABLED = get_adaptive_setting(
    AdaptiveKeys.ADAPTIVE_ENGINE_ENABLED,
    os.getenv("ADAPTIVE_ENGINE_ENABLED", "true").lower() in ("1", "true", "yes")
)

# Фидер метрик в БД (hourly)
METRICS_FEEDER_ENABLED = get_adaptive_setting(
    AdaptiveKeys.METRICS_FEEDER_ENABLED,
    os.getenv("METRICS_FEEDER_ENABLED", "true").lower() in ("1", "true", "yes")
)
METRICS_FEEDER_INTERVAL_SEC = get_adaptive_setting(
    AdaptiveKeys.METRICS_FEEDER_INTERVAL_SEC,
    int(os.getenv("METRICS_FEEDER_INTERVAL_SEC", "3600"))
)
METRICS_CACHE_TTL_SEC = get_adaptive_setting(
    AdaptiveKeys.METRICS_CACHE_TTL_SEC,
    int(os.getenv("METRICS_CACHE_TTL_SEC", "3600"))
)

# Сводные окна/пороги
PERFORMANCE_LOOKBACK_DAYS = get_adaptive_setting(
    AdaptiveKeys.PERFORMANCE_LOOKBACK_DAYS,
    int(os.getenv("PERFORMANCE_LOOKBACK_DAYS", "7"))
)

# Адаптивная подстройка порогов входа (мягкая)
ADAPTIVE_ENTRY_ADJ_ENABLED = get_adaptive_setting(
    AdaptiveKeys.ADAPTIVE_ENTRY_ADJ_ENABLED,
    os.getenv("ADAPTIVE_ENTRY_ADJ_ENABLED", "true").lower() in ("1", "true", "yes")
)
# Максимальная величина корректировки базовых порогов (в процентах)
ADAPTIVE_ENTRY_MAX_ADJUST_PCT = get_adaptive_setting(
    AdaptiveKeys.ADAPTIVE_ENTRY_MAX_ADJUST_PCT,
    float(os.getenv("ADAPTIVE_ENTRY_MAX_ADJUST_PCT", "10.0"))
)

# Динамический свитчер режима фильтров strict/sof
DYNAMIC_MODE_SWITCH_ENABLED = get_adaptive_setting(
    AdaptiveKeys.DYNAMIC_MODE_SWITCH_ENABLED,
    os.getenv("DYNAMIC_MODE_SWITCH_ENABLED", "true").lower() in ("1", "true", "yes")
)

# Корреляционный кулдаун (ограничение одновременных высоко-коррелированных сигналов)
CORRELATION_COOLDOWN_ENABLED = get_adaptive_setting(
    AdaptiveKeys.CORRELATION_COOLDOWN_ENABLED,
    os.getenv("CORRELATION_COOLDOWN_ENABLED", "true").lower() in ("1", "true", "yes")
)
CORRELATION_LOOKBACK_HOURS = get_adaptive_setting(
    AdaptiveKeys.CORRELATION_LOOKBACK_HOURS,
    int(os.getenv("CORRELATION_LOOKBACK_HOURS", "24"))
)
CORRELATION_MAX_PAIRWISE = get_adaptive_setting(
    AdaptiveKeys.CORRELATION_MAX_PAIRWISE,
    float(os.getenv("CORRELATION_MAX_PAIRWISE", "0.85"))
)
CORRELATION_COOLDOWN_SEC = get_adaptive_setting(
    AdaptiveKeys.CORRELATION_COOLDOWN_SEC,
    int(os.getenv("CORRELATION_COOLDOWN_SEC", "3600"))
)

# ============================================================================
# МЯГКИЙ БЛОКЛИСТ (ФАЗА 2) - ТЕПЕРЬ ИЗ БАЗЫ ДАННЫХ
# ============================================================================
SOFT_BLOCKLIST_ENABLED = get_adaptive_setting(
    AdaptiveKeys.SOFT_BLOCKLIST_ENABLED,
    os.getenv("SOFT_BLOCKLIST_ENABLED", "true").lower() in ("1", "true", "yes")
)
SOFT_BLOCKLIST_HYSTERESIS = get_adaptive_setting(
    AdaptiveKeys.SOFT_BLOCKLIST_HYSTERESIS,
    int(os.getenv("SOFT_BLOCKLIST_HYSTERESIS", "2"))
)
SOFT_BLOCK_COOLDOWN_HOURS = get_adaptive_setting(
    AdaptiveKeys.SOFT_BLOCK_COOLDOWN_HOURS,
    int(os.getenv("SOFT_BLOCK_COOLDOWN_HOURS", "6"))
)
MIN_ACTIVE_COINS = get_adaptive_setting(
    AdaptiveKeys.MIN_ACTIVE_COINS,
    int(os.getenv("MIN_ACTIVE_COINS", "30"))
)
BLOCKLIST_CHURN_FRAC = get_adaptive_setting(
    AdaptiveKeys.BLOCKLIST_CHURN_FRAC,
    float(os.getenv("BLOCKLIST_CHURN_FRAC", "0.2"))
)

ALWAYS_ACTIVE_COINS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"
]

# ============================================================================
# АУДИТ, АЛЕРТЫ, СЕКТОРНЫЕ ЛИМИТЫ (БЕЗ КОНФЛИКТОВ)
# ============================================================================
AUDIT_ENABLED = os.getenv("AUDIT_ENABLED", "true").lower() in ("1", "true", "yes")
ALERTS_ENABLED = os.getenv("ALERTS_ENABLED", "false").lower() in ("1", "true", "yes")
DAILY_SUMMARY_ENABLED = os.getenv("DAILY_SUMMARY_ENABLED", "true").lower() in ("1", "true", "yes")
DAILY_SUMMARY_HOUR_UTC = int(os.getenv("DAILY_SUMMARY_HOUR_UTC", "4"))

# Пороговые значения для сигналов за 24ч (алерты тишина/всплеск)
MIN_DAILY_SIGNALS_THRESHOLD = int(os.getenv("MIN_DAILY_SIGNALS_THRESHOLD", "2"))
MIN_SIGNALS_LAST_HOURS = int(os.getenv("MIN_SIGNALS_LAST_HOURS", "1"))
MAX_DAILY_SIGNALS_THRESHOLD = int(os.getenv("MAX_DAILY_SIGNALS_THRESHOLD", "80"))

# Секторные лимиты портфеля при отборе кандидатов
SECTOR_MAX_PER_GROUP = int(os.getenv("SECTOR_MAX_PER_GROUP", "4"))

# ============================================================================
# MTF-ВЗВЕШИВАНИЕ (MULTI-TIMEFRAME)
# ============================================================================
MTF_ENABLED = os.getenv("MTF_ENABLED", "true").lower() in ("1", "true", "yes")
MTF_TIMEFRAMES = ["1h", "4h", "1d"]
MTF_WEIGHTS_BULL = {
    "1h": float(os.getenv("MTF_WEIGHT_1H_BULL", "0.3")),
    "4h": float(os.getenv("MTF_WEIGHT_4H_BULL", "0.5")),
    "1d": float(os.getenv("MTF_WEIGHT_1D_BULL", "0.2"))
}
MTF_WEIGHTS_BEAR = {
    "1h": float(os.getenv("MTF_WEIGHT_1H_BEAR", "0.6")),
    "4h": float(os.getenv("MTF_WEIGHT_4H_BEAR", "0.3")),
    "1d": float(os.getenv("MTF_WEIGHT_1D_BEAR", "0.1"))
}
MTF_WEIGHTS_NEUTRAL = {
    "1h": float(os.getenv("MTF_WEIGHT_1H_NEUTRAL", "0.4")),
    "4h": float(os.getenv("MTF_WEIGHT_4H_NEUTRAL", "0.4")),
    "1d": float(os.getenv("MTF_WEIGHT_1D_NEUTRAL", "0.2"))
}
MTF_MIN_CONFIRMATIONS = int(os.getenv("MTF_MIN_CONFIRMATIONS", "2"))
MTF_QUALITY_BOOST = float(os.getenv("MTF_QUALITY_BOOST", "0.15"))

# ============================================================================
# ML-СКОРИНГ (MACHINE LEARNING)
# ============================================================================
ML_SCORING_ENABLED = os.getenv("ML_SCORING_ENABLED", "true").lower() in ("1", "true", "yes")
ML_MODEL_RETRAIN_HOURS = int(os.getenv("ML_MODEL_RETRAIN_HOURS", "24"))
ML_MIN_TRAINING_SAMPLES = int(os.getenv("ML_MIN_TRAINING_SAMPLES", "100"))
ML_PREDICTION_THRESHOLD = float(os.getenv("ML_PREDICTION_THRESHOLD", "0.65"))
ML_QUALITY_BOOST = float(os.getenv("ML_QUALITY_BOOST", "0.2"))
ML_FEATURES = [
    "rsi", "adx", "volume_ratio", "bollinger_position",
    "ema_trend", "market_regime", "mtf_score"
]

# ============================================================================
# КОНФИГУРАЦИЯ ГОТОВА К ИСПОЛЬЗОВАНИЮ
# ============================================================================

# Asset-specific configurations (defaults for tests)
if 'ASSET_SPECIFIC_CONFIG' not in globals():
    ASSET_SPECIFIC_CONFIG = {
        'BTC': {'risk_multiplier': 0.8},
        'ETH': {'risk_multiplier': 0.9},
    }

# Enhanced strategy tuning (defaults for tests)
if 'ENHANCED_STRATEGY_CONFIG' not in globals():
    ENHANCED_STRATEGY_CONFIG = {
        'bollinger': {'window': 20, 'std': 2.0},
        'rsi': {'window': 14, 'overbought': 70, 'oversold': 30},
    }

# ============================================================================
# ГИБРИДНАЯ MTF СИСТЕМА (HYBRID MTF CONFIRMATION)
# ============================================================================
HYBRID_MTF_CONFIG = {
    'enabled': os.getenv("HYBRID_MTF_ENABLED", "true").lower() in ("1", "true", "yes"),
    'primary_timeframe': '4h',  # Binance поддерживает
    'compensation_timeframe': '1h',
    # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
    # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
    # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
    # 🔧 ПОДДЕРЖКА БЭКТЕСТОВ: Переопределение через environment variables
    'min_h4_confidence': float(os.getenv("BACKTEST_min_h4_confidence") or os.getenv("HYBRID_MTF_MIN_H4_CONFIDENCE", "0.4")),
    'min_h4_confidence_short': float(os.getenv("BACKTEST_min_h4_confidence") or os.getenv("HYBRID_MTF_MIN_H4_CONFIDENCE_SHORT", "0.4")),
    'min_h4_confidence_long': float(os.getenv("BACKTEST_min_h4_confidence") or os.getenv("HYBRID_MTF_MIN_H4_CONFIDENCE_LONG", "0.4")),
    'max_hybrid_boost': float(os.getenv("HYBRID_MTF_MAX_BOOST", "0.35")),
    'h1_trend_thresholds': {
        'VERY_STRONG': 0.9,
        'STRONG': 0.8,
        'MODERATE': 0.7,
        'WEAK': 0.6
    },
    'market_momentum_thresholds': {
        'VERY_STRONG': 0.8,
        'STRONG': 0.7,
        'MODERATE': 0.6
    },
    'boost_multipliers': {
        'h1_very_strong': 0.8,
        'h1_strong': 0.6,
        'h1_moderate': 0.4,
        'h1_weak': 0.2,
        'market_very_strong': 0.5,
        'market_strong': 0.3,
        'market_moderate': 0.15
    }
}
