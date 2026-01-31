#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Менеджер источников данных с валидацией качества и cross-checking.

Обеспечивает надежное получение данных о ценах, объемах и свечах
с автоматическим переключением между источниками при сбоях.
"""

# Standard library imports
import asyncio
import logging
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, List, Optional, Tuple, Any

# Third party imports
import aiohttp
import pandas as pd

try:
    from src.infrastructure.websockets.binance_ws import PriceStreamCache
    BINANCE_WS_AVAILABLE = True
except ImportError:
    BINANCE_WS_AVAILABLE = False
    PriceStreamCache = None

logger = logging.getLogger(__name__)

@dataclass
class DataSource:
    """Конфигурация источника данных"""
    name: str
    base_url: str
    rate_limit: int  # запросов в минуту
    timeout: int = 10
    priority: int = 1  # 1 = высший приоритет
    enabled: bool = True
    last_error: Optional[str] = None
    error_count: int = 0
    success_count: int = 0

@dataclass
class PriceData:
    """Данные о цене с метаинформацией"""
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    source: str
    confidence: float = 1.0  # 0.0 - 1.0

class DataQualityValidator:
    """Валидатор качества данных"""

    def __init__(self):
        self.price_threshold = 0.1  # 0.1% максимальное отклонение
        self.volume_threshold = 0.5  # 50% максимальное отклонение объема
        self.anomaly_threshold = 3.0  # Z-score для детекции аномалий

    def validate_price_consistency(self, prices: List[float]) -> Tuple[bool, float]:
        """Проверяет консистентность цен между источниками"""
        if len(prices) < 2:
            return True, 1.0

        # Находим медианную цену как эталон
        median_price = statistics.median(prices)

        # Проверяем отклонения
        max_deviation = 0.0
        for price in prices:
            deviation = abs(price - median_price) / median_price * 100
            max_deviation = max(max_deviation, deviation)

        is_consistent = max_deviation <= self.price_threshold
        confidence = max(0.0, 1.0 - max_deviation / self.price_threshold)

        return is_consistent, confidence

    def detect_anomalies(self, values: List[float]) -> List[bool]:
        """Детектирует аномалии в данных"""
        if len(values) < 3:
            return [False] * len(values)

        mean_val = statistics.mean(values)
        stdev_val = statistics.stdev(values) if len(values) > 1 else 0

        if stdev_val == 0:
            return [False] * len(values)

        anomalies = []
        for val in values:
            z_score = abs(val - mean_val) / stdev_val
            anomalies.append(z_score > self.anomaly_threshold)

        return anomalies

from collections import OrderedDict
from src.data.dataframe_optimizer import optimize_dataframe_types

class DataSourcesManager:
    """Менеджер источников данных с валидацией и LRU кэшированием"""

    def __init__(self):
        self.sources = self._initialize_sources()
        self.validator = DataQualityValidator()
        self.cache = OrderedDict()  # 🚀 Оптимизация: Используем OrderedDict для LRU
        self.max_cache_size = 100   # 🚀 Оптимизация: Ограничиваем размер кэша
        self.cache_ttl = 10  # секунд
        self._session = None

    def _initialize_sources(self) -> Dict[str, DataSource]:
        """Инициализирует источники данных"""
        return {
            'binance': DataSource(
                name='Binance',
                base_url='https://api.binance.com/api/v3',
                rate_limit=1200,
                priority=1
            ),
            'bybit': DataSource(
                name='Bybit',
                base_url='https://api.bybit.com/v5',
                rate_limit=120,
                priority=2
            ),
            'okx': DataSource(
                name='OKX',
                base_url='https://www.okx.com/api/v5',
                rate_limit=20,
                priority=3
            ),
            'coingecko': DataSource(
                name='CoinGecko',
                base_url='https://api.coingecko.com/api/v3',
                rate_limit=50,
                priority=4
            ),
            'coinmarketcap': DataSource(
                name='CoinMarketCap',
                base_url='https://pro-api.coinmarketcap.com/v1',
                rate_limit=10,
                priority=5
            )
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получает или создает HTTP сессию"""
        from src.utils.session_manager import session_manager
        return await session_manager.get_session()

    async def close(self):
        """Закрывает HTTP сессию"""
        # Мы не закрываем общую сессию здесь, она управляется SessionManager
        pass

    def _get_cache_key(self, symbol: str, data_type: str) -> str:
        """Генерирует ключ кэша"""
        return f"{symbol}_{data_type}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Проверяет валидность кэша и обновляет позицию в LRU"""
        if cache_key not in self.cache:
            return False

        _, timestamp = self.cache[cache_key]
        is_valid = time.time() - timestamp < self.cache_ttl
        
        if is_valid:
            # 🚀 Оптимизация: Перемещаем в конец при обращении
            self.cache.move_to_end(cache_key)
            
        return is_valid

    def _set_cache(self, cache_key: str, data: Any):
        """Сохраняет данные в кэш с ротацией (LRU)"""
        # 🚀 ЭКСПЕРТНАЯ ОПТИМИЗАЦИЯ (Сергей): Ротация кэша
        if len(self.cache) >= self.max_cache_size:
            self.cache.popitem(last=False)  # Удаляем самый старый элемент
        
        # Если данные - DataFrame, оптимизируем типы перед кэшированием
        if isinstance(data, pd.DataFrame):
            data = optimize_dataframe_types(data)
            
        self.cache[cache_key] = (data, time.time())
        # Перемещаем в конец (как недавно использованный)
        self.cache.move_to_end(cache_key)

    async def get_price_binance(self, symbol: str) -> Optional[PriceData]:
        """Получает цену с Binance"""
        try:
            session = await self._get_session()
            url = f"{self.sources['binance'].base_url}/ticker/price"
            params = {'symbol': symbol}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return PriceData(
                        symbol=symbol,
                        price=float(data['price']),
                        volume=0.0,  # Binance ticker/price не возвращает volume
                        timestamp=get_utc_now(),
                        source='binance',
                        confidence=1.0
                    )
                else:
                    logger.warning("Binance API error: %s", response.status)
                    return None

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as e:
            logger.error("Error getting price from Binance: %s", e)
            self.sources['binance'].error_count += 1
            self.sources['binance'].last_error = str(e)
            return None

    async def get_price_bybit(self, symbol: str) -> Optional[PriceData]:
        """Получает цену с Bybit"""
        try:
            session = await self._get_session()
            url = f"{self.sources['bybit'].base_url}/market/tickers"
            params = {'category': 'spot', 'symbol': symbol}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                        ticker = data['result']['list'][0]
                        return PriceData(
                            symbol=symbol,
                            price=float(ticker['lastPrice']),
                            volume=float(ticker['volume24h']),
                            timestamp=get_utc_now(),
                            source='bybit',
                            confidence=1.0
                        )
                return None

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as e:
            logger.error("Error getting price from Bybit: %s", e)
            self.sources['bybit'].error_count += 1
            self.sources['bybit'].last_error = str(e)
            return None

    async def get_price_okx(self, symbol: str) -> Optional[PriceData]:
        """Получает цену с OKX"""
        try:
            session = await self._get_session()
            url = f"{self.sources['okx'].base_url}/market/ticker"
            params = {'instId': symbol}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('code') == '0' and data.get('data'):
                        ticker = data['data'][0]
                        return PriceData(
                            symbol=symbol,
                            price=float(ticker['last']),
                            volume=float(ticker['vol24h']),
                            timestamp=get_utc_now(),
                            source='okx',
                            confidence=1.0
                        )
                return None

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as e:
            logger.error("Error getting price from OKX: %s", e)
            self.sources['okx'].error_count += 1
            self.sources['okx'].last_error = str(e)
            return None

    async def get_price_coingecko(self, symbol: str) -> Optional[PriceData]:
        """Получает цену с CoinGecko"""
        try:
            # Конвертируем символ в CoinGecko формат
            coin_id = self._convert_symbol_to_coingecko_id(symbol)
            if not coin_id:
                return None

            session = await self._get_session()
            url = f"{self.sources['coingecko'].base_url}/simple/price"
            params = {'ids': coin_id, 'vs_currencies': 'usd', 'include_24hr_vol': 'true'}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if coin_id in data:
                        coin_data = data[coin_id]
                        return PriceData(
                            symbol=symbol,
                            price=float(coin_data['usd']),
                            volume=float(coin_data.get('usd_24h_vol', 0)),
                            timestamp=get_utc_now(),
                            source='coingecko',
                            confidence=0.9  # Немного ниже из-за возможной задержки
                        )
                return None

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as e:
            logger.error("Error getting price from CoinGecko: %s", e)
            self.sources['coingecko'].error_count += 1
            self.sources['coingecko'].last_error = str(e)
            return None

    def _convert_symbol_to_coingecko_id(self, symbol: str) -> Optional[str]:
        """Конвертирует символ биржи в ID CoinGecko"""
        # Простое маппирование основных монет
        mapping = {
            'BTCUSDT': 'bitcoin',
            'ETHUSDT': 'ethereum',
            'BNBUSDT': 'binancecoin',
            'ADAUSDT': 'cardano',
            'SOLUSDT': 'solana',
            'XRPUSDT': 'ripple',
            'DOGEUSDT': 'dogecoin',
            'AVAXUSDT': 'avalanche-2',
            'LINKUSDT': 'chainlink',
            'TRXUSDT': 'tron'
        }
        return mapping.get(symbol)

    async def get_price_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получает данные о цене в формате словаря для совместимости"""
        price_data = await self.get_price_robust(symbol)
        if price_data:
            return {
                "price": price_data.price,
                "source": price_data.source,
                "timestamp": price_data.timestamp
            }
        return None

    async def get_price_robust(self, symbol: str, max_sources: int = 3) -> Optional[PriceData]:
        """Получает цену с валидацией от нескольких источников"""
        # 0. Проверяем WebSocket кэш (Zero Latency)
        if BINANCE_WS_AVAILABLE and PriceStreamCache:
            ws_price = PriceStreamCache.get_price(symbol)
            if ws_price:
                logger.debug("🎯 [WS-CACHE] %s: %.8f (Zero Latency)", symbol, ws_price['last'])
                return PriceData(
                    symbol=symbol,
                    price=float(ws_price['last']),
                    volume=0.0,
                    timestamp=get_utc_now(),
                    source='binance_ws',
                    confidence=1.0
                )

        cache_key = self._get_cache_key(symbol, 'price')

        # Проверяем кэш
        if self._is_cache_valid(cache_key):
            data, _ = self.cache[cache_key]
            return data

        # Сортируем источники по приоритету
        sorted_sources = sorted(
            [s for s in self.sources.values() if s.enabled],
            key=lambda x: x.priority
        )

        # Получаем данные от нескольких источников параллельно
        tasks = []
        source_methods = {
            'binance': self.get_price_binance,
            'bybit': self.get_price_bybit,
            'okx': self.get_price_okx,
            'coingecko': self.get_price_coingecko
        }

        for source in sorted_sources[:max_sources]:
            if source.name.lower() in source_methods:
                tasks.append(source_methods[source.name.lower()](symbol))

        if not tasks:
            logger.error("No available sources for symbol %s", symbol)
            return None

        # Выполняем запросы параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Фильтруем успешные результаты
        valid_prices = []
        for i, result in enumerate(results):
            if isinstance(result, PriceData) and result is not None:
                valid_prices.append(result)
                # Обновляем статистику успеха
                source_name = sorted_sources[i].name.lower()
                self.sources[source_name].success_count += 1

        if not valid_prices:
            logger.error("No valid prices received for %s", symbol)
            return None

        # Валидируем консистентность цен
        prices = [p.price for p in valid_prices]
        is_consistent, confidence = self.validator.validate_price_consistency(prices)

        if not is_consistent:
            logger.warning("Price inconsistency detected for %s: %s", symbol, prices)
            # Берем цену от источника с наивысшим приоритетом
            best_price = valid_prices[0]
            best_price.confidence = confidence
        else:
            # Берем средневзвешенную цену
            weights = [p.confidence for p in valid_prices]
            total_weight = sum(weights)

            if total_weight > 0:
                weighted_price = sum(p.price * w for p, w in zip(valid_prices, weights)) / total_weight
                weighted_volume = sum(p.volume * w for p, w in zip(valid_prices, weights)) / total_weight

                best_price = PriceData(
                    symbol=symbol,
                    price=weighted_price,
                    volume=weighted_volume,
                    timestamp=get_utc_now(),
                    source='multiple',
                    confidence=confidence
                )
            else:
                best_price = valid_prices[0]

        # Сохраняем в кэш
        self._set_cache(cache_key, best_price)

        logger.info("Price for %s: %.6f (confidence: %.2f)", symbol, best_price.price, best_price.confidence)
        return best_price

    async def get_ohlcv_data(self, symbol: str, interval: str = '1h', limit: int = 100) -> Optional[pd.DataFrame]:
        """Получает OHLCV данные с валидацией"""
        cache_key = self._get_cache_key(f"{symbol}_{interval}_{limit}", 'ohlcv')

        # Проверяем кэш
        if self._is_cache_valid(cache_key):
            data, _ = self.cache[cache_key]
            return data

        # Пробуем получить данные от Binance (основной источник)
        try:
            session = await self._get_session()
            url = f"{self.sources['binance'].base_url}/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    # Конвертируем в DataFrame
                    df = pd.DataFrame(data, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'volume',
                        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                        'taker_buy_quote', 'ignore'
                    ])

                    # Конвертируем типы данных
                    numeric_columns = ['open', 'high', 'low', 'close', 'volume']
                    for col in numeric_columns:
                        df[col] = pd.to_numeric(df[col])

                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df.set_index('timestamp', inplace=True)

                    # Валидируем данные на аномалии
                    self._validate_ohlcv_data(df, symbol)

                    # Сохраняем в кэш
                    self._set_cache(cache_key, df)

                    logger.info("OHLCV data loaded for %s: %d candles", symbol, len(df))
                    return df
                else:
                    logger.error("Binance OHLCV API error: %s", response.status)

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as e:
            logger.error("Error getting OHLCV data from Binance: %s", e)
            self.sources['binance'].error_count += 1

        return None

    def _validate_ohlcv_data(self, df: pd.DataFrame, symbol: str):
        """Валидирует OHLCV данные на аномалии"""
        try:
            # Проверяем на пропущенные значения
            if df.isnull().any().any():
                logger.warning("Missing values detected in OHLCV data for %s", symbol)

            # Проверяем на аномальные цены
            price_columns = ['open', 'high', 'low', 'close']
            for col in price_columns:
                values = df[col].dropna().tolist()
                if values:
                    anomalies = self.validator.detect_anomalies(values)
                    if any(anomalies):
                        logger.warning("Price anomalies detected in %s for %s", col, symbol)

            # Проверяем логику OHLC
            invalid_ohlc = (
                (df['high'] < df['low']) |
                (df['high'] < df['open']) |
                (df['high'] < df['close']) |
                (df['low'] > df['open']) |
                (df['low'] > df['close'])
            )
            if invalid_ohlc.any():
                logger.warning("Invalid OHLC logic detected for %s", symbol)

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as e:
            logger.error("Error validating OHLCV data for %s: %s", symbol, e)

    def get_source_statistics(self) -> Dict[str, Dict]:
        """Возвращает статистику по источникам данных"""
        stats = {}
        for name, source in self.sources.items():
            total_requests = source.success_count + source.error_count
            success_rate = source.success_count / total_requests if total_requests > 0 else 0

            stats[name] = {
                'enabled': source.enabled,
                'priority': source.priority,
                'success_count': source.success_count,
                'error_count': source.error_count,
                'success_rate': success_rate,
                'last_error': source.last_error,
                'rate_limit': source.rate_limit
            }

        return stats

    def disable_failing_source(self, source_name: str, error_threshold: int = 10):
        """Отключает источник при превышении порога ошибок"""
        if source_name in self.sources:
            source = self.sources[source_name]
            if source.error_count >= error_threshold:
                source.enabled = False
                logger.warning("Disabled data source %s due to %d errors", source_name, source.error_count)

    async def health_check(self) -> Dict[str, bool]:
        """Проверяет здоровье всех источников данных"""
        health_status = {}

        for name, source in self.sources.items():
            if not source.enabled:
                health_status[name] = False
                continue

            try:
                # Простой тест доступности
                session = await self._get_session()
                test_url = f"{source.base_url}/ping" if name == 'binance' else f"{source.base_url}"

                async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    health_status[name] = response.status < 500

            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                health_status[name] = False

        return health_status

# Глобальный экземпляр менеджера
data_sources_manager = DataSourcesManager()
# Алиас для обратной совместимости
data_manager = data_sources_manager

# Удобные функции для использования в других модулях
async def get_current_price(symbol: str) -> Optional[float]:
    """Получает текущую цену с валидацией"""
    price_data = await data_sources_manager.get_price_robust(symbol)
    return price_data.price if price_data else None

async def get_ohlcv_data(symbol: str, interval: str = '1h', limit: int = 100) -> Optional[pd.DataFrame]:
    """Получает OHLCV данные с валидацией"""
    return await data_sources_manager.get_ohlcv_data(symbol, interval, limit)

async def get_data_sources_stats() -> Dict[str, Dict]:
    """Возвращает статистику источников данных"""
    return data_sources_manager.get_source_statistics()

async def check_data_sources_health() -> Dict[str, bool]:
    """Проверяет здоровье источников данных"""
    return await data_sources_manager.health_check()
