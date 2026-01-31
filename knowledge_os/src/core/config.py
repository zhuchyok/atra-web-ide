"""
Core configuration for ATRA trading system
Центральная конфигурация торговой системы ATRA

This module contains all constants and configuration parameters
that were previously scattered across different files.

⚠️ MIGRATION TO STATELESS ARCHITECTURE:
Cache variables (SENT_SIGNALS_CACHE, ANOMALY_CACHE, NEWS_CACHE) are being
migrated to stateless architecture. Use get_cache_registry() from src.core.cache
for new code. Backward compatibility is maintained through properties.
"""

from typing import Dict, Any

# Import cache registry for stateless architecture
try:
    from src.core.cache import get_cache_registry
except ImportError:
    # Fallback if cache module is not available
    def get_cache_registry():
        return None

# =============================================================================
# CACHE SETTINGS / НАСТРОЙКИ КЭША
# =============================================================================

# Constants for cache TTL
SIGNAL_CACHE_TIMEOUT = 60  # 1 минута
ANOMALY_TTL_SEC = 600  # 10 минут

CACHE_TTL = {
    'blocked': 3600,      # 1 час для заблокированных
    'positive': 3600,     # 1 час для позитивных новостей
    'combined': 1800      # 30 минут для комбинированных
}

# =============================================================================
# BACKWARD COMPATIBILITY: Legacy cache access
# =============================================================================

# Legacy module-level variables (for backward compatibility)
# These are actually functions that return dict-like objects that proxy
# to the cache registry. This maintains backward compatibility while
# using stateless architecture under the hood.

class _CacheDictProxy:
    """Dict-like proxy that forwards operations to cache registry"""
    
    def __init__(self, cache_type: str):
        self._cache_type = cache_type
    
    def _get_registry(self):
        """Get cache registry"""
        registry = get_cache_registry()
        if registry is None:
            return None
        return registry
    
    def __getitem__(self, key):
        """Get item from cache"""
        registry = self._get_registry()
        if registry is None:
            raise KeyError(key)
        
        if self._cache_type == 'sent_signals':
            return registry.sent_signals.get(key)
        elif self._cache_type == 'anomaly':
            return registry.anomalies.get(key)
        elif self._cache_type == 'news_blocked':
            return registry.news_blocked.get(key)
        elif self._cache_type == 'news_positive':
            return registry.news_positive.get(key)
        elif self._cache_type == 'news_combined':
            return registry.news_combined.get(key)
        raise KeyError(key)
    
    def __setitem__(self, key, value):
        """Set item in cache"""
        registry = self._get_registry()
        if registry is None:
            return
        
        if self._cache_type == 'sent_signals':
            registry.sent_signals.set(key, value, ttl=SIGNAL_CACHE_TIMEOUT)
        elif self._cache_type == 'anomaly':
            registry.anomalies.set(key, value, ttl=ANOMALY_TTL_SEC)
        elif self._cache_type == 'news_blocked':
            registry.news_blocked.set(key, value, ttl=CACHE_TTL['blocked'])
        elif self._cache_type == 'news_positive':
            registry.news_positive.set(key, value, ttl=CACHE_TTL['positive'])
        elif self._cache_type == 'news_combined':
            registry.news_combined.set(key, value, ttl=CACHE_TTL['combined'])
    
    def __contains__(self, key):
        """Check if key exists in cache"""
        registry = self._get_registry()
        if registry is None:
            return False
        
        if self._cache_type == 'sent_signals':
            return registry.sent_signals.has_key(key)
        elif self._cache_type == 'anomaly':
            return registry.anomalies.has_key(key)
        elif self._cache_type == 'news_blocked':
            return registry.news_blocked.has_key(key)
        elif self._cache_type == 'news_positive':
            return registry.news_positive.has_key(key)
        elif self._cache_type == 'news_combined':
            return registry.news_combined.has_key(key)
        return False
    
    def get(self, key, default=None):
        """Get item from cache with default"""
        try:
            return self[key]
        except KeyError:
            return default
    
    def clear(self):
        """Clear cache"""
        registry = self._get_registry()
        if registry is None:
            return
        
        if self._cache_type == 'sent_signals':
            registry.sent_signals.clear()
        elif self._cache_type == 'anomaly':
            registry.anomalies.clear()
        elif self._cache_type == 'news_blocked':
            registry.news_blocked.clear()
        elif self._cache_type == 'news_positive':
            registry.news_positive.clear()
        elif self._cache_type == 'news_combined':
            registry.news_combined.clear()


class _NewsCacheProxy:
    """Proxy for NEWS_CACHE dict structure"""
    
    def __init__(self):
        self.blocked = _CacheDictProxy('news_blocked')
        self.positive = _CacheDictProxy('news_positive')
        self.combined = _CacheDictProxy('news_combined')
    
    def __getitem__(self, key):
        """Get news cache by type"""
        if key == 'blocked':
            return self.blocked
        elif key == 'positive':
            return self.positive
        elif key == 'combined':
            return self.combined
        raise KeyError(key)


# Legacy module-level variables (for backward compatibility)
# ⚠️ DEPRECATED: Use get_cache_registry() for new code
SENT_SIGNALS_CACHE = _CacheDictProxy('sent_signals')
ANOMALY_CACHE = _CacheDictProxy('anomaly')
NEWS_CACHE = _NewsCacheProxy()

# =============================================================================
# FEATURE FLAGS / ФЛАГИ ФУНКЦИОНАЛЬНОСТИ
# =============================================================================

# Оптимизация производительности
OPTIMIZATION_ENABLED = True

# Система отслеживания китов
WHALE_TRACKING_ENABLED = True
WHALE_FREE_MODE = True  # Использовать бесплатную версию
WHALE_INTEGRATION_ENABLED = True

# Анализ блоков покупателей/продавцов
VOLUME_BLOCKS_ENABLED = True

# Система накапливания сигналов (отключена)
ACCUMULATION_ENABLED = False

# =============================================================================
# TRADING PARAMETERS / ТОРГОВЫЕ ПАРАМЕТРЫ
# =============================================================================

# Таймфреймы
DEFAULT_TIMEFRAME = "1h"
SUPPORTED_TIMEFRAMES = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"]

# Лимиты DCA
MAX_DCA = 3  # Максимальное количество усреднений
ALPHA = 2.0   # Коэффициент увеличения объема при DCA

# Риск-менеджмент
MAX_RISK_PCT = 5.0    # Максимальный риск в процентах
DEFAULT_RISK_PCT = 2.0  # Риск по умолчанию

# Плечо
MAX_LEVERAGE = 20.0   # Максимальное плечо
DEFAULT_LEVERAGE = 1.0  # Плечо по умолчанию

# =============================================================================
# SIGNAL PROCESSING / ОБРАБОТКА СИГНАЛОВ
# =============================================================================

# Режимы фильтрации сигналов
SIGNAL_MODES = {
    "strict": "Строгий режим - высокое качество, мало сигналов",
    "balanced": "Оптимальный баланс качества и количества",
    "soft": "Мягкий режим - больше сигналов, ниже качество"
}

# Настройки фильтрации
FILTER_SETTINGS = {
    "min_volume_24h": 50_000_000,  # Минимальный объем 24ч (50M)
    "max_spread_pct": 2.0,         # Максимальный спред 2%
    "min_price": 0.01,             # Минимальная цена $0.01
    "max_price": 100_000,          # Максимальная цена $100K
    "max_volatility_pct": 15.0,    # Максимальная волатильность 15%
    "min_profit_pct": 0.5,         # Минимальная прибыль 0.5%
    "max_profit_pct": 5.0          # Максимальная прибыль 5%
}

# =============================================================================
# NEWS FILTERING / НОВОСТНЫЕ ФИЛЬТРЫ
# =============================================================================

# Ключевые слова для новостей
NEWS_KEYWORDS = [
    'Bitcoin', 'BTC', 'Bitcoin ETF', 'Bitcoin Spot ETF',
    'cryptocurrency', 'crypto', 'blockchain', 'mining',
    'regulation', 'SEC', 'ETF', 'spot ETF', 'futures',
    'institutional', 'adoption', 'mainstream', 'price',
    'market', 'trading', 'exchange', 'listing', 'delisting'
]

NEGATIVE_NEWS_KEYWORDS = [
    'ban', 'banned', 'crackdown', 'crack down', 'regulation',
    'regulatory', 'investigation', 'probe', 'scam', 'fraud',
    'hack', 'hacked', 'exploit', 'vulnerability', 'breach',
    'theft', 'stolen', 'rug pull', 'rug-pull', 'rugpull',
    'exit scam', 'ponzi', 'pyramid', 'scheme', 'scandal',
    'lawsuit', 'legal', 'court', 'SEC', 'CFTC', 'FINRA',
    'FINCEN', 'OFAC', 'sanctions', 'blacklist', 'delist',
    'delisting', 'shutdown', 'closing', 'bankruptcy', 'insolvent'
]

POSITIVE_NEWS_KEYWORDS = [
    'adoption', 'mainstream', 'institutional', 'partnership',
    'collaboration', 'integration', 'implementation', 'launch',
    'upgrade', 'improvement', 'development', 'milestone',
    'breakthrough', 'innovation', 'technology', 'solution',
    'ETF', 'spot ETF', 'Bitcoin ETF', 'approval', 'approved',
    'green light', 'authorized', 'licensed', 'regulated',
    'legitimate', 'trustworthy', 'reliable', 'secure', 'safety'
]

# Настройки новостных фильтров
NEWS_SETTINGS = {
    "negative_block_hours": 24,    # Блокировка на 24 часа при негативных новостях
    "positive_boost_hours": 12,    # Усиление на 12 часов при позитивных новостях
    "min_news_sources": 2,         # Минимум 2 источника для надежности
    "max_news_age_hours": 48       # Максимальный возраст новости 48 часов
}

# Режимы новостных фильтров
NEWS_FILTER_MODES = {
    "conservative": {
        "block_long_on_negative": True,     # Блокировать LONG при негативных новостях
        "block_short_on_positive": True,    # Блокировать SHORT при позитивных новостях
        "enhance_long_on_positive": True,   # Усиливать LONG при позитивных новостях
        "enhance_short_on_negative": True,  # Усиливать SHORT при негативных новостях
        "min_sentiment_score": 0.3          # Минимальный балл настроения
    },
    "moderate": {
        "block_long_on_negative": True,
        "block_short_on_positive": False,
        "enhance_long_on_positive": True,
        "enhance_short_on_negative": True,
        "min_sentiment_score": 0.2
    },
    "aggressive": {
        "block_long_on_negative": False,
        "block_short_on_positive": False,
        "enhance_long_on_positive": True,
        "enhance_short_on_negative": True,
        "min_sentiment_score": 0.1
    }
}

# =============================================================================
# TECHNICAL INDICATORS / ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ
# =============================================================================

# Настройки индикаторов
INDICATOR_SETTINGS = {
    "rsi": {
        "period": 14,
        "overbought": 72,  # 🆕 Оптимизировано для крипто (было 70) - учитывает повышенную волатильность
        "oversold": 28,     # 🆕 Оптимизировано для крипто (было 30) - более чувствительные уровни
        "divergence_lookback": 8,  # Оптимизировано для крипто (было 5)
        "volatility_threshold": 8,  # Оптимизировано для крипто (было 10)
        "use_adaptive_levels": True  # 🆕 Использовать адаптивные уровни по волатильности
    },
    "macd": {
        "fast_period": 8,        # 🆕 Оптимизировано для интрадей (было 12) - более чувствительный
        "slow_period": 21,       # 🆕 Оптимизировано для интрадей (было 26) - быстрее реагирует
        "signal_period": 5,      # 🆕 Оптимизировано для интрадей (было 9) - более отзывчивый
        "min_strength": 0.003,   # 🆕 Оптимизировано для крипто (было 0.005) - меньше требований
        "histogram_min": 0.001,  # Минимальное значение гистограммы
        "trend_confirmation": 2  # 🆕 Требовать подтверждение тренда (2 свечи)
    },
    "bollinger_bands": {
        "period": 18,            # 🆕 Оптимизировано для интрадей (было 20) - более отзывчивый
        "std_dev": 1.8,          # 🆕 Оптимизировано (было 2.0) - уже полосы, больше сигналов
        "min_width": 0.015,      # 🆕 Минимальная ширина полос (было 0.02)
        "position_long": 0.15,   # 🆕 Более строгий (было 0.2) - нижние 15%
        "position_short": 0.85,  # 🆕 Более строгий (было 0.8) - верхние 15%
        "squeeze_threshold": 0.012  # 🆕 Порог сжатия полос для обнаружения пробоев
    },
    "ema": {
        "fast": 6,               # 🆕 Оптимизировано для интрадей (было 7) - более чувствительный
        "medium": 14,            # 🆕 Оптимизировано для интрадей (было 25) - новая средняя EMA
        "slow": 22,              # 🆕 Оптимизировано для интрадей (было 25) - быстрее реагирует
        "trend": 200,            # Оставить
        "min_distance": 0.008,   # 🆕 Оптимизировано (было 0.01) - меньше требование
        "trend_strength": 0.003  # Минимальная сила тренда
    },
    "atr": {
        "period": 14
    },
    "volume_ratio": {
        "lookback": 15,          # 🆕 Оптимизировано для интрадей (было 20)
        "threshold": 1.2,        # 🆕 Оптимизировано для крипто (было 1.5) - меньше требований
        "min_volume": 500,       # 🆕 Оптимизировано для мелких пар (было 1000)
        "max_ratio": 8,          # 🆕 Оптимизировано (было 10) - меньше аномалий
        "spike_threshold": 5.0,  # 🆕 Порог для обнаружения всплесков объема
        "min_volume_usd": 10000  # 🆕 Минимальный объем в USD для качества
    }
}

# =============================================================================
# ERROR HANDLING / ОБРАБОТКА ОШИБОК
# =============================================================================

# Таймауты для API запросов
API_TIMEOUTS = {
    "default": 10,      # 10 секунд
    "news": 15,         # 15 секунд для новостей
    "price": 5,         # 5 секунд для цен
    "ohlc": 30          # 30 секунд для исторических данных
}

# Настройки повторных попыток
RETRY_SETTINGS = {
    "max_retries": 3,
    "backoff_factor": 1.5,    # Увеличение задержки
    "max_delay": 60          # Максимальная задержка
}

# =============================================================================
# LOCALIZATION / ЛОКАЛИЗАЦИЯ
# =============================================================================

# Языковые настройки
DEFAULT_LANGUAGE = "ru"  # Русский по умолчанию
SUPPORTED_LANGUAGES = ["ru", "en"]

# =============================================================================
# LOGGING / ЛОГИРОВАНИЕ
# =============================================================================

# Уровни логирования
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Пути к логам
LOG_PATHS = {
    "system": "system.log",
    "signals": "signals.log",
    "errors": "errors.log",
    "performance": "performance.log"
}

# =============================================================================
# SYMBOL-SPECIFIC CONFIGURATION / ИНДИВИДУАЛЬНЫЕ ПАРАМЕТРЫ ДЛЯ КАЖДОЙ МОНЕТЫ
# =============================================================================

# Индивидуальные параметры для каждой торговой пары
# Эти параметры переопределяют значения по умолчанию из symbol_specific_optimizer
SYMBOL_SPECIFIC_CONFIG = {
    "BTCUSDT": {
        "optimal_rsi_oversold": 28,        # ✅ ОПТИМАЛЬНЫЕ: Найдены тестированием (было 25, оригинал 30)
        "optimal_rsi_overbought": 72,     # ✅ ОПТИМАЛЬНЫЕ: Найдены тестированием (было 75, оригинал 70)
        "ai_score_threshold": 6.0,        # ✅ ОПТИМАЛЬНЫЕ: Найдены тестированием (было 5.0, оригинал 6.5)
        "soft_volume_ratio": 1.2,         # Оставить текущий
        "min_confidence": 68,              # ✅ ОПТИМАЛЬНЫЕ: Найдены тестированием (было 65, оригинал 70)
        "position_size_multiplier": 1.0,  # Оставить текущий
        "filter_mode": "soft"
    },
    "ETHUSDT": {
        "optimal_rsi_oversold": 26,       # ✅ ЛУЧШИЕ: Найдены тестированием (наименьший убыток, было 25)
        "optimal_rsi_overbought": 74,     # ✅ ЛУЧШИЕ: Найдены тестированием (наименьший убыток, было 75)
        "ai_score_threshold": 5.0,        # ✅ ЛУЧШИЕ: Найдены тестированием (наименьший убыток, было 5.0)
        "soft_volume_ratio": 1.2,         # Оставить текущий
        "min_confidence": 66,              # ✅ ЛУЧШИЕ: Найдены тестированием (наименьший убыток, было 65)
        "position_size_multiplier": 1.0,  # Оставить текущий
        "filter_mode": "soft"
    },
    "BNBUSDT": {
        "optimal_rsi_oversold": 20,       # ✅ ИСПРАВЛЕНО: Ослаблено (было 35 - слишком строго)
        "optimal_rsi_overbought": 80,     # ✅ ИСПРАВЛЕНО: Ослаблено (было 65 - слишком строго)
        "ai_score_threshold": 5.0,        # ✅ ИСПРАВЛЕНО: Вернуть к стандартному (было 7.5 - слишком строго)
        "soft_volume_ratio": 1.2,         # Оставить текущий
        "min_confidence": 65,              # ✅ ИСПРАВЛЕНО: Снизить (было 75 - слишком строго)
        "position_size_multiplier": 0.8,  # ✅ ИСПРАВЛЕНО: Увеличить вес (было 0.6)
        "filter_mode": "soft"
    },
    "SOLUSDT": {
        "optimal_rsi_oversold": 25,       # Оставить текущие (работают отлично)
        "optimal_rsi_overbought": 75,     # Оставить текущие (работают отлично)
        "ai_score_threshold": 5.0,        # Оставить текущие (работают отлично)
        "soft_volume_ratio": 1.2,         # Оставить текущий
        "min_confidence": 60,              # Оставить текущий
        "position_size_multiplier": 1.5,  # Увеличить вес на 50%
        "filter_mode": "soft"
    },
    # Новые монеты из массового скрининга (2025-11-13)
    "AVAXUSDT": {
        "optimal_rsi_oversold": 25,       # Стандартные параметры (61.90% WR в скрининге)
        "optimal_rsi_overbought": 75,     # Стандартные параметры
        "ai_score_threshold": 5.0,        # Стандартные параметры
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.2,  # Увеличить вес на 20% (хорошие результаты)
        "filter_mode": "soft"
    },
    "LINKUSDT": {
        "optimal_rsi_oversold": 25,       # Стандартные параметры (61.11% WR в скрининге)
        "optimal_rsi_overbought": 75,     # Стандартные параметры
        "ai_score_threshold": 5.0,        # Стандартные параметры
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.3,  # Увеличить вес на 30% (отличные результаты)
        "filter_mode": "soft"
    },
    "SUIUSDT": {
        "optimal_rsi_oversold": 25,       # Стандартные параметры (50.00% WR в скрининге)
        "optimal_rsi_overbought": 75,     # Стандартные параметры
        "ai_score_threshold": 5.0,        # Стандартные параметры
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.1,  # Увеличить вес на 10% (хорошие результаты)
        "filter_mode": "soft"
    },
    "DOGEUSDT": {
        "optimal_rsi_oversold": 25,       # Стандартные параметры (50.00% WR в скрининге)
        "optimal_rsi_overbought": 75,     # Стандартные параметры
        "ai_score_threshold": 5.0,        # Стандартные параметры
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,  # Стандартный вес
        "filter_mode": "soft"
    },
    # ✅ ОПТИМИЗИРОВАНО: Монеты из финального портфеля (оптимизация параметров)
    "WIFUSDT": {
        "optimal_rsi_oversold": 27,       # ✅ DATA-DRIVEN BOTTOM-UP: Скорректировано (было 26, найдено 26.5)
        "optimal_rsi_overbought": 73,     # ✅ DATA-DRIVEN BOTTOM-UP: Скорректировано (было 74, найдено 73.5)
        "ai_score_threshold": 5.25,       # ✅ DATA-DRIVEN BOTTOM-UP: Подтверждено (найдено 5.25)
        "soft_volume_ratio": 1.2,
        "min_confidence": 67,              # ✅ DATA-DRIVEN BOTTOM-UP: Скорректировано (было 66, найдено 66.5)
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "BONKUSDT": {
        "optimal_rsi_oversold": 22,       # ✅ DATA-DRIVEN BOTTOM-UP: Найдены полной оптимизацией (было 24)
        "optimal_rsi_overbought": 78,     # ✅ DATA-DRIVEN BOTTOM-UP: Найдены полной оптимизацией (было 76)
        "ai_score_threshold": 3.5,        # ✅ DATA-DRIVEN BOTTOM-UP: Найдены полной оптимизацией (было 4.5)
        "soft_volume_ratio": 1.2,
        "min_confidence": 62,              # ✅ DATA-DRIVEN BOTTOM-UP: Найдены полной оптимизацией (было 64)
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    # ✅ ОПТИМИЗИРОВАНО: Монеты из BTC групп (параметры как у SOL)
    "SYRUPUSDT": {
        "optimal_rsi_oversold": 25,       # Оптимизировано для BTC группы
        "optimal_rsi_overbought": 75,     # Оптимизировано для BTC группы
        "ai_score_threshold": 5.0,        # Оптимизировано для BTC группы
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "AVNTUSDT": {
        "optimal_rsi_oversold": 25,       # Оптимизировано для BTC группы
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "DASHUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "EDENUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "VIRTUALUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    # ✅ ОПТИМИЗИРОВАНО: Монеты из ETH групп (параметры как у SOL)
    "AAVEUSDT": {
        "optimal_rsi_oversold": 25,       # Оптимизировано для ETH группы
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "LDOUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "BCHUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "TRXUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "UNIUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "CAKEUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "BABYUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "KITEUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "LSKUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "VELODROMEUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    },
    "MINAUSDT": {
        "optimal_rsi_oversold": 25,
        "optimal_rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "soft_volume_ratio": 1.2,
        "min_confidence": 65,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    }
}

# Параметры по умолчанию (используются, если для символа нет индивидуальных настроек)
DEFAULT_SYMBOL_CONFIG = {
    "optimal_rsi_oversold": 25,
    "optimal_rsi_overbought": 75,
    "ai_score_threshold": 5.0,
    "soft_volume_ratio": 1.2,
    "min_confidence": 65,
    "position_size_multiplier": 1.0,
    "filter_mode": "soft"
}

# =============================================================================
# EXTERNAL SERVICES / ВНЕШНИЕ СЕРВИСЫ
# =============================================================================

# API ключи и настройки
EXTERNAL_APIS = {
    "coingecko": {
        "enabled": True,
        "timeout": 10,
        "rate_limit": 50  # запросов в минуту
    },
    "tradingview": {
        "enabled": True,
        "timeout": 15,
        "rate_limit": 30
    },
    "binance": {
        "enabled": True,
        "timeout": 5,
        "rate_limit": 1000
    }
}

# =============================================================================
# DATA PROVIDER SETTINGS / НАСТРОЙКИ ПРООВАЙДЕРОВ ДАННЫХ
# =============================================================================

# Rate limits для API (запросов в минуту)
API_RATE_LIMITS = {
    "coingecko": 50,
    "tradingview": 30,
    "binance": 1000,
    "default": 10
}

# Таймауты запросов
REQUEST_TIMEOUT = 10  # секунд

# Максимальное количество повторных попыток
MAX_RETRIES = 3

# API ключи (можно переопределить через переменные окружения)
COINGECKO_API_KEY = None  # os.getenv('COINGECKO_API_KEY')
TRADINGVIEW_API_KEY = None  # os.getenv('TRADINGVIEW_API_KEY')

# =============================================================================
# CACHE SETTINGS EXTENDED / РАСШИРЕННЫЕ НАСТРОЙКИ КЭША
# =============================================================================

# Настройки кэша данных
CACHE_SETTINGS = {
    "ohlc_max_size": 500,
    "news_max_size": 200,
    "anomaly_max_size": 300,
    "whale_max_size": 100,
    "whale_ttl": 1800,  # 30 минут
    "signal_max_size": 1000,
    "default_ttl": 300  # 5 минут
}

# TTL для разных типов данных (секунды)
OHLC_CACHE_TTL = 1800     # 30 минут для OHLC
NEWS_CACHE_TTL = 3600     # 1 час для новостей
ANOMALY_CACHE_TTL = 600   # 10 минут для аномалий

# =============================================================================
# VALIDATION SETTINGS / НАСТРОЙКИ ВАЛИДАЦИИ
# =============================================================================

# Пороги валидации цен
PRICE_VALIDATION = {
    "min_price": 0.000001,
    "max_price": 1000000,
    "max_decimals": 18,
    "max_symbol_length": 20
}

# Пороги валидации объемов
VOLUME_VALIDATION = {
    "max_change_pct": 1000,  # Предупреждение при изменении > 10x
    "min_volume": 0
}

# Пороги валидации новостей
NEWS_VALIDATION = {
    "min_title_length": 10,
    "max_title_length": 200,
    "max_items": 50
}

# Диапазоны дат для валидации
DATE_VALIDATION = {
    "min_year": 2010,
    "max_future_days": 1
}
