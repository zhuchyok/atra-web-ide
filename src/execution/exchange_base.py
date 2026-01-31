# -*- coding: utf-8 -*-
"""
Base exchange API classes and common functionality
"""
import functools
import logging
import time
from abc import ABC, abstractmethod

import aiohttp


class ExchangeAPI(ABC):
    """Base class for exchange APIs"""

    @staticmethod
    @abstractmethod
    async def get_liquid_spot_pairs(min_turnover=10000):
        pass

    @staticmethod
    @abstractmethod
    async def get_prices(symbols):
        pass

    @staticmethod
    async def log_timing(name, coro):
        start = time.time()
        result = await coro
        elapsed = time.time() - start
        logging.info("%s took %.3fs", name, elapsed)
        return result


def cache_prices(exchange_name):
    """Decorator for caching price data"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(symbols):
            # This would be implemented with actual caching logic
            # Using exchange_name for cache key generation
            logging.debug("Caching prices for %s exchange: %s", exchange_name, symbols)
            return await func(symbols)
        return wrapper
    return decorator


async def get_ohlc_with_fallback(symbol, interval="1h", limit=100, max_retries=1):
    """
    Universal function for getting OHLC data with automatic fallback
    Tries: Binance → Bybit → MEXC → OKX → KuCoin → Gate.io
    """
    from exchanges.binance_api import BinanceAPI
    from exchanges.bybit_api import BybitAPI
    from exchanges.mexc_api import MEXCAPI
    
    # Попытка импорта дополнительных бирж
    try:
        from exchanges.okx_api import OKXAPI
        okx_available = True
    except ImportError:
        okx_available = False
    
    try:
        from exchanges.kucoin_api import KuCoinAPI
        kucoin_available = True
    except ImportError:
        kucoin_available = False
    
    try:
        from exchanges.gateio_api import GateIOAPI
        gateio_available = True
    except ImportError:
        gateio_available = False

    exchanges = [
        ("Binance", BinanceAPI.get_ohlc),
        ("Bybit", BybitAPI.get_ohlc),
        ("MEXC", MEXCAPI.get_ohlc)
    ]
    
    # Добавляем дополнительные биржи если доступны
    if okx_available:
        exchanges.append(("OKX", OKXAPI.get_ohlc))
    if kucoin_available:
        exchanges.append(("KuCoin", KuCoinAPI.get_ohlc))
    if gateio_available:
        exchanges.append(("Gate.io", GateIOAPI.get_ohlc))

    for exchange_name, exchange_func in exchanges:
        try:
            logging.info("Пробуем получить OHLC для %s с %s...", symbol, exchange_name)
            ohlc = await exchange_func(symbol, interval, limit, max_retries)

            if ohlc and len(ohlc) > 0:
                logging.info("✅ Успешно получены данные для %s с %s: %d свечей", symbol, exchange_name, len(ohlc))
                return ohlc
            else:
                logging.warning("❌ %s вернул пустой результат для %s", exchange_name, symbol)
                continue

        except (aiohttp.ClientError, ValueError, TypeError) as e:
            logging.error("❌ Ошибка получения данных с %s для %s: %s", exchange_name, symbol, e)
            continue

    logging.error("❌ Не удалось получить данные для %s ни с одной биржи", symbol)
    return []
