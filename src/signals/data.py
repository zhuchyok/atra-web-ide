#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль работы с данными
Вынесен из signal_live.py для рефакторинга
"""

import asyncio
import concurrent.futures
import pandas as pd
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Импорты для гибридного менеджера данных
try:
    from hybrid_data_manager import hybrid_data_manager
    HYBRID_DATA_MANAGER_AVAILABLE = True
    HYBRID_DATA_MANAGER = hybrid_data_manager
except ImportError:
    HYBRID_DATA_MANAGER_AVAILABLE = False
    HYBRID_DATA_MANAGER = None

# Импорт для fallback
try:
    from exchange_api import get_ohlc_with_fallback
except ImportError:
    get_ohlc_with_fallback = None

# Импорт индикаторов
try:
    from src.signals.indicators import add_technical_indicators
except ImportError:
    # Fallback: импорт из signal_live если модуль не найден
    try:
        from signal_live import add_technical_indicators
    except ImportError:
        def add_technical_indicators(df):
            return df

# Импорт пользователей
try:
    from src.utils.user_utils import load_user_data_for_signals
except ImportError:
    def load_user_data_for_signals():
        return {}


async def get_symbol_data(symbol: str, force_fresh: bool = False) -> Optional[Any]:
    """Получение данных символа с использованием кеша"""
    try:
        # Пробуем получить данные через гибридный менеджер (с кешированием)
        if HYBRID_DATA_MANAGER_AVAILABLE and HYBRID_DATA_MANAGER:
            df = await HYBRID_DATA_MANAGER.get_smart_data(symbol, "ohlc", force_fresh=force_fresh)
        else:
            # Fallback: прямой доступ к API (без кеша, но с rate limiting)
            if get_ohlc_with_fallback:
                df = await get_ohlc_with_fallback(symbol, interval="1h", limit=300)
            else:
                logger.error("Не доступны ни HybridDataManager, ни get_ohlc_with_fallback")
                return None
        
        # Проверяем, что данные получены и не пустые
        if df is None or (hasattr(df, '__len__') and len(df) == 0):
            logger.debug("Нет данных для %s", symbol)
            return None

        if not isinstance(df, pd.DataFrame):
            try:
                # Проверяем, что df не пустой и содержит данные
                if df is not None and len(df) > 0:
                    df = pd.DataFrame(df)
                    logger.debug("Конвертировали список в DataFrame для %s", symbol)
                else:
                    logger.debug("Пустые данные для %s", symbol)
                    return None
            except Exception as e:
                logger.error("Ошибка конвертации данных для %s: %s", symbol, e)
                return None

        if df is not None and len(df) > 0:
            df = add_technical_indicators(df)
            logger.debug("✅ Добавлены технические индикаторы для %s", symbol)

        return df

    except Exception as e:
        logger.error("Ошибка получения данных для %s: %s", symbol, e)
        return None


async def load_user_data() -> Dict[str, Any]:
    """Загрузка данных пользователей из базы данных"""
    try:
        # load_user_data_for_signals() не асинхронная функция
        user_data_dict = load_user_data_for_signals()
        logger.info("✅ Загружено %d пользователей из базы данных", len(user_data_dict))
        return user_data_dict
    except Exception as e:
        logger.error("Ошибка загрузки пользователей: %s", e)
        return {}


def get_symbols() -> List[str]:
    """Получение символов для анализа"""
    try:
        # Получаем реальные символы из API (как было 10 октября)
        try:
            from exchange_api import get_filtered_top_usdt_pairs_fast
        except ImportError:
            logger.error("Не удалось импортировать get_filtered_top_usdt_pairs_fast")
            return ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        
        current_loop = asyncio.get_event_loop()
        if current_loop.is_running():
            # Если loop уже запущен, используем ThreadPoolExecutor для запуска в новом event loop
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, get_filtered_top_usdt_pairs_fast(top_n=150, final_limit=60))
                symbols = future.result()
        else:
            # Если loop не запущен, запускаем его
            symbols = current_loop.run_until_complete(get_filtered_top_usdt_pairs_fast(top_n=150, final_limit=60))

        if symbols:
            # Дополнительная фильтрация стейблкоинов, чёрного списка и некорректных символов
            from config import STABLECOIN_SYMBOLS, BLACKLISTED_SYMBOLS

            # Фильтруем:
            # 1. Стейблкоины
            # 2. Чёрный список проблемных символов
            # 3. Дублированные символы (CAKEUSDTUSDT, USDEUSDTUSDT и т.д.)
            # 4. Символы не заканчивающиеся на USDT
            filtered_symbols = [
                s for s in symbols
                if s not in STABLECOIN_SYMBOLS
                and s not in BLACKLISTED_SYMBOLS
                and s.endswith('USDT')
                and not s.endswith('USDTUSDT')  # Фильтруем дубли
                and s.count('USDT') == 1  # Только одно вхождение USDT
            ]

            logger.info("✅ Загружено %d реальных символов из API (после фильтрации: %d)",
                       len(symbols), len(filtered_symbols))
            return filtered_symbols
        else:
            logger.warning("⚠️ Не удалось получить символы из API, используем fallback")
            # Fallback список без стейблкоинов
            fallback_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SNXUSDT", "DASHUSDT", "NEARUSDT"]
            from config import STABLECOIN_SYMBOLS
            filtered_fallback = [s for s in fallback_symbols if s not in STABLECOIN_SYMBOLS]
            return filtered_fallback
    except Exception as e:
        logger.error("Ошибка получения символов: %s", e)
        # Fallback список без стейблкоинов
        fallback_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SNXUSDT", "DASHUSDT", "NEARUSDT"]
        try:
            from config import STABLECOIN_SYMBOLS
            filtered_fallback = [s for s in fallback_symbols if s not in STABLECOIN_SYMBOLS]
        except ImportError:
            filtered_fallback = fallback_symbols
        return filtered_fallback

