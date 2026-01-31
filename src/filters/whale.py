"""
Фильтры китовых движений для торговых сигналов
Полная реализация с использованием бесплатных API
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, List, Any, Optional
from .base import BaseFilter, FilterResult

import aiohttp
import requests

from config import WHALE_API_KEYS

logger = logging.getLogger(__name__)

# Кэш для данных о китах
WHALE_CACHE: Dict[str, Dict[str, Any]] = {}
WHALE_CACHE_TTL = 1800  # 30 минут

# Минимальные значения транзакций для определения китов (в USD)
MIN_WHALE_VALUE = {
    "BTC": 100000,      # 100K USD
    "ETH": 50000,       # 50K USD
    "BNB": 20000,       # 20K USD
    "USDT": 100000,     # 100K USD
    "USDC": 100000,     # 100K USD
    "SOL": 50000,       # 50K USD
    "ADA": 50000,       # 50K USD
    "default": 50000    # 50K USD по умолчанию
}

# Известные кошельки бирж (публичные данные)
KNOWN_EXCHANGE_WALLETS = {
    "binance": [
        "0x28C6c06298d514Db089934071355E5743bf21d60",
        "0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549",
        "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE",
    ],
    "coinbase": [
        "0xA090e606E30bD747d4E6245a1517EbE430F0057e",
        "0x503828976D22510aad0201ac7EC88293211D23Da",
    ],
    "kraken": [
        "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",
        "0x0A869d79a7052C7f1b55a8eBABB9A0C6Fe2D700db",
    ],
}


class WhaleFilter(BaseFilter):
    """Фильтр китовых движений"""

    def __init__(self, enabled: bool = True):
        super().__init__("whale", enabled, priority=3)

    async def filter_signal(self, signal_data: Dict[str, Any]) -> FilterResult:
        """Фильтрация сигнала на основе китовых движений"""
        try:
            symbol = signal_data.get('symbol', '')
            
            # Используем существующую логику
            sentiment = await get_whale_signal_async(symbol)
            
            if sentiment == 'bearish':
                return FilterResult(False, "Обнаружена медвежья активность китов")
            else:
                return FilterResult(True, f"Активность китов: {sentiment}")
                
        except Exception as e:
            logger.error("Ошибка в WhaleFilter: %s", e)
            return FilterResult(True, f"Ошибка проверки китов (пропущено): {e}")


def get_min_whale_value(symbol: str) -> float:
    """Получает минимальное значение транзакции для определения кита"""
    base = symbol.replace("USDT", "").replace("USD", "").replace("BTC", "").upper()
    return MIN_WHALE_VALUE.get(base, MIN_WHALE_VALUE["default"])


async def get_binance_whale_data(symbol: str, hours: int = 24) -> List[Dict[str, Any]]:
    """Получает данные о крупных сделках с Binance API"""
    cache_key = f"binance_whale:{symbol}"
    if cache_key in WHALE_CACHE:
        cached = WHALE_CACHE[cache_key]
        if time.time() - cached['timestamp'] < WHALE_CACHE_TTL:
            return cached['data']
    
    try:
        base_symbol = symbol.replace("USDT", "").replace("USD", "")
        min_value = get_min_whale_value(symbol)
        
        # Получаем последние сделки
        url = f"https://api.binance.com/api/v3/trades"
        params = {
            'symbol': symbol,
            'limit': 1000
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    trades = await resp.json()
                    whale_trades = []
                    
                    # Получаем текущую цену для расчета USD значения
                    price_url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                    async with session.get(price_url, timeout=5) as price_resp:
                        if price_resp.status == 200:
                            price_data = await price_resp.json()
                            current_price = float(price_data.get('price', 0))
                            
                            for trade in trades:
                                quantity = float(trade.get('qty', 0))
                                trade_value_usd = quantity * current_price
                                
                                if trade_value_usd >= min_value:
                                    whale_trades.append({
                                        'symbol': symbol,
                                        'price': float(trade.get('price', 0)),
                                        'quantity': quantity,
                                        'value_usd': trade_value_usd,
                                        'side': trade.get('isBuyerMaker', False),
                                        'time': trade.get('time', 0),
                                        'source': 'binance'
                                    })
                    
                    WHALE_CACHE[cache_key] = {'data': whale_trades, 'timestamp': time.time()}
                    return whale_trades
    except Exception as e:
        logger.debug(f"Binance whale data ошибка для {symbol}: {e}")
    
    return []


async def get_coingecko_whale_data(symbol: str, hours: int = 24) -> List[Dict[str, Any]]:
    """Получает данные о китах из CoinGecko (анализ объемов)"""
    cache_key = f"coingecko_whale:{symbol}"
    if cache_key in WHALE_CACHE:
        cached = WHALE_CACHE[cache_key]
        if time.time() - cached['timestamp'] < WHALE_CACHE_TTL:
            return cached['data']
    
    try:
        base_symbol = symbol.replace("USDT", "").replace("USD", "").lower()
        
        # Получаем данные о токене
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': base_symbol,
            'vs_currencies': 'usd',
            'include_24hr_vol': 'true'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    if base_symbol in data:
                        token_data = data[base_symbol]
                        volume_24h = token_data.get('usd_24h_vol', 0)
                        
                        # Если объем высокий (>1M USD), считаем это активностью китов
                        if volume_24h > 1000000:
                            whale_data = [{
                                'symbol': symbol,
                                'volume_24h_usd': volume_24h,
                                'price': token_data.get('usd', 0),
                                'source': 'coingecko',
                                'time': int(time.time() * 1000)
                            }]
                            
                            WHALE_CACHE[cache_key] = {'data': whale_data, 'timestamp': time.time()}
                            return whale_data
    except Exception as e:
        logger.debug(f"CoinGecko whale data ошибка для {symbol}: {e}")
    
    return []


def analyze_whale_sentiment(whale_data: List[Dict[str, Any]], signal_type: str) -> str:
    """
    Анализирует настроение китов на основе данных о транзакциях
    
    Args:
        whale_data: Список данных о транзакциях китов
        signal_type: Тип сигнала ('LONG' или 'SHORT')
        
    Returns:
        str: 'bullish', 'bearish', или 'neutral'
    """
    if not whale_data:
        return "neutral"
    
    # Анализируем покупки и продажи
    total_buy_value = 0.0
    total_sell_value = 0.0
    buy_count = 0
    sell_count = 0
    
    for data in whale_data:
        if 'side' in data:
            # Binance данные
            if data.get('side') is False:  # isBuyerMaker=False означает покупку
                total_buy_value += data.get('value_usd', 0)
                buy_count += 1
            else:
                total_sell_value += data.get('value_usd', 0)
                sell_count += 1
        elif 'volume_24h_usd' in data:
            # CoinGecko данные - высокий объем может указывать на активность китов
            # Не можем определить направление, но считаем нейтральным/позитивным
            total_buy_value += data.get('volume_24h_usd', 0) * 0.5
            total_sell_value += data.get('volume_24h_usd', 0) * 0.5
    
    # Определяем настроение
    if total_buy_value == 0 and total_sell_value == 0:
        return "neutral"
    
    buy_ratio = total_buy_value / (total_buy_value + total_sell_value) if (total_buy_value + total_sell_value) > 0 else 0.5
    
    if buy_ratio > 0.6:
        return "bullish"
    elif buy_ratio < 0.4:
        return "bearish"
    else:
        return "neutral"


async def get_whale_signal_async(symbol: str) -> str:
    """
    Получение китового сигнала для символа (асинхронная версия)
    
    Args:
        symbol: Торговый символ
        
    Returns:
        str: Статус китового сигнала ('bullish', 'bearish', 'neutral')
    """
    try:
        # Получаем данные из всех источников параллельно
        results = await asyncio.gather(
            get_binance_whale_data(symbol),
            get_coingecko_whale_data(symbol),
            return_exceptions=True
        )
        
        # Собираем все данные
        all_whale_data = []
        for result in results:
            if isinstance(result, list):
                all_whale_data.extend(result)
            elif isinstance(result, Exception):
                logger.debug(f"Ошибка получения whale data: {result}")
        
        # Анализируем настроение
        sentiment = analyze_whale_sentiment(all_whale_data, "LONG")
        
        logger.debug(f"[Whale] {symbol}: sentiment={sentiment}, transactions={len(all_whale_data)}")
        return sentiment
    except Exception as e:
        logger.error(f"Ошибка получения китового сигнала для {symbol}: {e}")
        return "neutral"


def get_whale_signal(symbol: str) -> str:
    """
    Получение китового сигнала для символа (синхронная обертка)
    
    Args:
        symbol: Торговый символ
        
    Returns:
        str: Статус китового сигнала ('bullish', 'bearish', 'neutral')
    """
    try:
        # Используем asyncio для запуска async функции
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если loop уже запущен, используем новый event loop в отдельном потоке
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_whale_signal_async(symbol))
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(get_whale_signal_async(symbol))
        except RuntimeError:
            # Если нет event loop, создаем новый
            return asyncio.run(get_whale_signal_async(symbol))
    except Exception as e:
        logger.error(f"Ошибка получения китового сигнала для {symbol}: {e}")
        return "neutral"
