"""
Filters Configuration - Централизованная конфигурация фильтров
"""

# =============================================================================
# BTC TREND FILTER CONFIGURATION
# =============================================================================

BTC_TREND_FILTER = {
    "enabled": True,
    "use_soft_filter": True,  # True = мягкий фильтр, False = строгий

    # Настройки мягкого фильтра
    "soft": {
        "ema_period": 200,
        "threshold_pct": 0.0  # Цена > EMA200
    },

    # Настройки строгого фильтра
    "strict": {
        "ema_short_period": 25,
        "ema_long_period": 200,
        "trend_threshold_pct": 0.5  # Сила тренда > 0.5%
    },

    # Общие настройки
    "priority": 1,
    "description": "Фильтр тренда биткоина - блокирует сигналы при нисходящем тренде BTC"
}

# =============================================================================
# NEWS FILTER CONFIGURATION
# =============================================================================

NEWS_FILTER = {
    "enabled": True,
    "priority": 2,
    "description": "Новостные фильтры - блокируют сигналы при негативных новостях",

    # Настройки блокировки
    "blocking": {
        "negative_block_hours": 24,    # Блокировка на 24 часа при негативных новостях
        "positive_boost_hours": 12,    # Усиление на 12 часов при позитивных новостях
        "min_sentiment_score": 0.3     # Минимальный балл настроения
    },

    # Режимы фильтрации
    "modes": {
        "conservative": {
            "block_long_on_negative": True,     # Блокировать LONG при негативных новостях
            "block_short_on_positive": True,    # Блокировать SHORT при позитивных новостях
            "enhance_long_on_positive": True,   # Усиливать LONG при позитивных новостях
            "enhance_short_on_negative": True,  # Усиливать SHORT при негативных новостях
            "min_sentiment_score": 0.3
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
    },

    # Ключевые слова для анализа новостей
    "keywords": {
        "positive": [
            'adoption', 'mainstream', 'institutional', 'partnership',
            'collaboration', 'integration', 'implementation', 'launch',
            'upgrade', 'improvement', 'development', 'milestone',
            'breakthrough', 'innovation', 'technology', 'solution',
            'ETF', 'spot ETF', 'Bitcoin ETF', 'approval', 'approved',
            'green light', 'authorized', 'licensed', 'regulated',
            'legitimate', 'trustworthy', 'reliable', 'secure', 'safety'
        ],

        "negative": [
            'ban', 'banned', 'crackdown', 'crack down', 'regulation',
            'regulatory', 'investigation', 'probe', 'scam', 'fraud',
            'hack', 'hacked', 'exploit', 'vulnerability', 'breach',
            'theft', 'stolen', 'rug pull', 'rug-pull', 'rugpull',
            'exit scam', 'ponzi', 'pyramid', 'scheme', 'scandal',
            'lawsuit', 'legal', 'court', 'SEC', 'CFTC', 'FINRA',
            'FINCEN', 'OFAC', 'sanctions', 'blacklist', 'delist',
            'delisting', 'shutdown', 'closing', 'bankruptcy', 'insolvent'
        ]
    },

    # Настройки источников новостей
    "sources": {
        "coingecko": {
            "enabled": True,
            "weight": 1.0,
            "cache_ttl": 1800  # 30 минут
        },
        "tradingview": {
            "enabled": True,
            "weight": 0.8,
            "cache_ttl": 900   # 15 минут
        },
        "cryptopanic": {
            "enabled": True,
            "weight": 0.9,
            "cache_ttl": 900   # 15 минут
        }
    }
}

# =============================================================================
# ANOMALY FILTER CONFIGURATION
# =============================================================================

ANOMALY_FILTER = {
    "enabled": True,
    "priority": 3,
    "description": "Фильтр аномалий - использует объем/капитализацию для выявления необычной активности",

    # Настройки аномалий
    "settings": {
        "volume_anomaly_threshold": 1.5,    # Коэффициент аномального объема
        "market_cap_anomaly_threshold": 2.0, # Коэффициент аномальной капитализации
        "lookback_periods": 20,             # Период анализа для baseline
        "min_volume_threshold": 100_000,    # Минимальный объем для анализа
        "cache_ttl": 600                    # 10 минут кэша
    },

    # Типы аномалий
    "types": {
        "volume_spike": {
            "enabled": True,
            "threshold": 2.0,
            "description": "Резкий скачок объема"
        },
        "market_cap_change": {
            "enabled": True,
            "threshold": 1.5,
            "description": "Резкое изменение капитализации"
        },
        "whale_activity": {
            "enabled": True,
            "threshold": 3.0,
            "description": "Активность крупных игроков"
        }
    }
}

# =============================================================================
# WHALE TRACKING FILTER CONFIGURATION
# =============================================================================

WHALE_FILTER = {
    "enabled": True,
    "priority": 4,
    "description": "Фильтр отслеживания китов - анализирует активность крупных игроков",

    "settings": {
        "min_whale_size_usdt": 1_000_000,   # Минимальный размер кита (1M USDT)
        "activity_threshold": 0.5,          # Порог активности (% от объема)
        "time_window_minutes": 60,          # Временное окно анализа
        "cache_ttl": 300                    # 5 минут кэша
    },

    "modes": {
        "free": {
            "enabled": True,
            "description": "Бесплатная версия (топ-100 китов)"
        },
        "premium": {
            "enabled": False,
            "description": "Платная версия (расширенный трекинг)"
        }
    }
}

# =============================================================================
# FILTER PIPELINE CONFIGURATION
# =============================================================================

FILTER_PIPELINE = {
    "enabled": True,
    "execution_order": [
        "btc_trend",    # 1. Сначала BTC тренд
        "news",         # 2. Потом новости
        "anomaly",      # 3. Затем аномалии
        "whale"         # 4. И киты
    ],

    # Настройки пайплайна
    "settings": {
        "fail_fast": False,               # Продолжать проверку даже после первого блока
        "collect_all_reasons": True,      # Собирать все причины блокировки
        "enable_filter_stats": True,      # Включить статистику фильтров
        "stats_retention_days": 7         # Хранить статистику N дней
    }
}

# =============================================================================
# FILTER DEFAULTS
# =============================================================================

DEFAULT_FILTER_CONFIG = {
    "btc_trend": BTC_TREND_FILTER,
    "news": NEWS_FILTER,
    "anomaly": ANOMALY_FILTER,
    "whale": WHALE_FILTER,
    "pipeline": FILTER_PIPELINE
}

# Функция для получения конфигурации фильтра
def get_filter_config(filter_name: str) -> dict:
    """Получить конфигурацию для конкретного фильтра"""
    return DEFAULT_FILTER_CONFIG.get(filter_name, {})

# Функция для обновления конфигурации фильтра
def update_filter_config(filter_name: str, new_config: dict) -> bool:
    """Обновить конфигурацию фильтра"""
    if filter_name in DEFAULT_FILTER_CONFIG:
        DEFAULT_FILTER_CONFIG[filter_name].update(new_config)
        return True
    return False

# Функция для получения порядка выполнения фильтров
def get_filter_execution_order() -> list:
    """Получить порядок выполнения фильтров"""
    return FILTER_PIPELINE["execution_order"]

# Функция для проверки включен ли фильтр
def is_filter_enabled(filter_name: str) -> bool:
    """Проверить включен ли фильтр"""
    config = get_filter_config(filter_name)
    return config.get("enabled", False)
