"""
Централизованный хаб для всех источников данных
Единый интерфейс для получения цен, объемов, капитализации, новостей
Кэширование только в БД через db.cache_get/cache_set
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp

from src.database.db import Database
try:
    from src.utils.rest_api_rate_limiter import RateLimiter
except ImportError:
    # Fallback для обратной совместимости
    RateLimiter = None
try:
    from src.core.circuit_breaker import CircuitBreaker
except ImportError:
    CircuitBreaker = None
try:
    from src.config.source import get_sources_config, SourceConfig
except ImportError:
    # Fallback for old structure
    try:
        from source_config import get_sources_config, SourceConfig
    except ImportError:
        def get_sources_config(): return {}
        class SourceConfig: pass
try:
    from src.data.parsers import (
        parse_market_cap_data,
        parse_volume_data,
        parse_price_data,
        parse_news_data,
    )
except ImportError:
    try:
        from data_parsers import (
            parse_market_cap_data,
            parse_volume_data,
            parse_price_data,
            parse_news_data,
        )
    except ImportError:
        def parse_market_cap_data(*args): return {}
        def parse_volume_data(*args): return 0
        def parse_price_data(*args): return 0
        def parse_news_data(*args): return []


@dataclass
class RequestMetrics:
    latency_sec: Optional[float] = None
    sources_count: Optional[int] = None
    source: Optional[str] = None
    cache_hit: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "latency_sec": self.latency_sec,
            "sources_count": self.sources_count,
            "source": self.source,
            "cache_hit": self.cache_hit,
        }


@dataclass
class SourcesHubMetrics:
    market_cap: RequestMetrics = field(default_factory=RequestMetrics)
    price: RequestMetrics = field(default_factory=RequestMetrics)
    volume: RequestMetrics = field(default_factory=RequestMetrics)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_cap": self.market_cap.as_dict(),
            "price": self.price.as_dict(),
            "volume": self.volume.as_dict(),
        }

class SourcesHub:
    """Централизованный хаб для всех источников данных с L1 кэшированием"""

    def __init__(self):
        self.db = Database()
        self.circuit_breakers = {}
        # 🚀 ЭКСПЕРТНАЯ ОПТИМИЗАЦИЯ (Сергей): L1 In-memory cache
        self._l1_cache = {}
        self._l1_ttl = 5  # секунд для L1 кэша
        
        if RateLimiter is not None:
            self.rate_limiter = RateLimiter(requests_per_minute=25)
        else:
            self.rate_limiter = None
        # Конфигурация источников
        self.sources = get_sources_config()
        self.metrics = SourcesHubMetrics()

    def _get_circuit_breaker(self, source_name: str):
        """Получает circuit breaker для источника"""
        if CircuitBreaker is None:
            return None
        if source_name not in self.circuit_breakers:
            self.circuit_breakers[source_name] = CircuitBreaker()
        return self.circuit_breakers[source_name]

    def _get_cache_key(self, data_type: str, symbol: str, **kwargs) -> str:
        """Генерирует ключ кэша"""
        params = "_".join([f"{k}={v}" for k, v in sorted(kwargs.items())])
        return f"{data_type}:{symbol}:{params}" if params else f"{data_type}:{symbol}"

    def _get_cached_data(self, cache_key: str, _ttl_seconds: int = 300):
        """Получает данные из L1 (memory) или L2 (DB) кэша"""
        # 1. Проверяем L1 кэш (память)
        if cache_key in self._l1_cache:
            data, ts = self._l1_cache[cache_key]
            if time.time() - ts < self._l1_ttl:
                logging.debug("[Cache L1] ✅ Найден кэш для %s", cache_key)
                return data
            else:
                del self._l1_cache[cache_key]

        # 2. Проверяем L2 кэш (БД)
        try:
            cached = self.db.cache_get("sources_hub", cache_key)
            if cached:
                logging.debug("[Cache L2] ✅ Найден кэш для %s", cache_key)
                # Обновляем L1 кэш
                self._l1_cache[cache_key] = (cached, time.time())
                return cached
        except (OSError, RuntimeError) as e:
            logging.debug("[Cache] Ошибка получения кэша %s: %s", cache_key, e)
        return None

    def _set_cached_data(self, cache_key: str, data: Any, ttl_seconds: int = 300):
        """Сохраняет данные в L1 (memory) и L2 (DB) кэш"""
        # 1. Сохраняем в L1
        self._l1_cache[cache_key] = (data, time.time())
        
        # 2. Сохраняем в L2
        try:
            self.db.cache_set("sources_hub", cache_key, data, ttl_seconds)
            logging.debug("[Cache] ✅ Сохранен кэш для %s", cache_key)
        except (OSError, RuntimeError) as e:
            logging.debug("[Cache] Ошибка сохранения кэша %s: %s", cache_key, e)

    def build_cache_key(self, data_type: str, symbol: str, **kwargs) -> str:
        """Публичный доступ к генерации ключа кэша."""
        return self._get_cache_key(data_type, symbol, **kwargs)

    def purge_cache_entry(self, data_type: str, symbol: str, **kwargs) -> None:
        """Удаляет конкретный элемент кэша."""
        cache_key = self._get_cache_key(data_type, symbol, **kwargs)
        with self.db.conn:
            self.db.conn.execute(
                "DELETE FROM app_cache WHERE cache_type = ? AND cache_key = ?",
                ("sources_hub", cache_key),
            )

    async def get_market_cap_data(self, symbol: str, _ttl_seconds: int = 3600) -> Optional[Dict[str, Any]]:
        """Получение данных о капитализации"""
        cache_key = self._get_cache_key("market_cap", symbol)

        # Проверяем кэш
        cached_data = self._get_cached_data(cache_key, 3600)
        if cached_data:
            self.metrics.market_cap = RequestMetrics(
                latency_sec=0.0,
                sources_count=cached_data.get("sources_used"),
                source="cache",
                cache_hit=True,
            )
            return cached_data

        base_symbol = symbol.replace('USDT', '') if symbol.endswith('USDT') else symbol
        sources = self.sources['market_cap']

        results = []
        start_ts = time.perf_counter()

        # Параллельно запрашиваем все источники
        # Создаем задачи СРАЗУ, чтобы при отмене их можно было корректно завершить
        tasks_with_names = []
        for source in sources:
            if not source.enabled:
                continue

            breaker = self._get_circuit_breaker(source.name)
            if not breaker.can_execute():
                logging.debug("[MarketCap] %s заблокирован circuit breaker", source.name)
                continue

            # Создаем задачу СРАЗУ (не храним корутину)
            task = asyncio.create_task(
                self._fetch_market_cap_from_source(source, symbol, base_symbol),
                name=f"market_cap_{source.name}"
            )
            tasks_with_names.append((source.name, task))

        if tasks_with_names:
            tasks = [task for _, task in tasks_with_names]
            
            try:
                # Выполняем все задачи параллельно
                gathered_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for idx, (source_name, _) in enumerate(tasks_with_names):
                    result = gathered_results[idx]
                    if isinstance(result, Exception):
                        logging.debug("[MarketCap] %s ошибка: %s", source_name, result)
                        self._get_circuit_breaker(source_name).on_failure()
                    elif result:
                        results.append(result)
                        self._get_circuit_breaker(source_name).on_success()
            except asyncio.CancelledError:
                # При отмене - отменяем все созданные задачи
                for task in tasks:
                    task.cancel()
                # Даем задачам возможность завершиться
                for task in tasks:
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
                raise

        if results:
            # Агрегируем результаты (берем медиану для market_cap)
            market_caps = [r['market_cap'] for r in results if r['market_cap'] > 0]
            volumes = [r['volume_24h'] for r in results if r['volume_24h'] > 0]

            if market_caps:
                market_caps.sort()
                median_market_cap = market_caps[len(market_caps) // 2]
            else:
                median_market_cap = 0

            if volumes:
                max_volume = max(volumes)
            else:
                max_volume = 0

            # Если все источники вернули 0, используем emergency fallback
            if median_market_cap == 0 and max_volume > 0:
                median_market_cap = max_volume * 100
                logging.warning("[MarketCap] Emergency fallback для %s: %s", symbol, median_market_cap)

            result = {
                'market_cap': median_market_cap,
                'volume_24h': max_volume,
                'sources_used': len(results),
                'timestamp': time.time()
            }

            # Кэшируем результат
            self._set_cached_data(cache_key, result, 1800)
            self.metrics.market_cap = RequestMetrics(
                latency_sec=time.perf_counter() - start_ts,
                sources_count=len(results),
                source=f"{len(results)}_sources",
                cache_hit=False,
            )
            return result

        logging.warning("[MarketCap] ❌ Все источники недоступны для %s", symbol)
        self.metrics.market_cap = RequestMetrics(
            latency_sec=time.perf_counter() - start_ts,
            sources_count=0,
            source=None,
            cache_hit=False,
        )
        return None

    def _convert_symbol_to_coingecko_id(self, symbol: str) -> Optional[str]:
        """Конвертирует символ биржи в ID CoinGecko"""
        mapping = {
            'BTCUSDT': 'bitcoin',
            'ETHUSDT': 'ethereum',
            'BNBUSDT': 'binancecoin',
            'ADAUSDT': 'cardano',
            'SOLUSDT': 'solana',
            'XRPUSDT': 'ripple',
            'DOTUSDT': 'polkadot',
            'DOGEUSDT': 'dogecoin',
            'AVAXUSDT': 'avalanche-2',
            'LINKUSDT': 'chainlink',
            'TRXUSDT': 'tron',
            'MATICUSDT': 'matic-network',
            'LTCUSDT': 'litecoin',
            'UNIUSDT': 'uniswap',
            'ATOMUSDT': 'cosmos',
            'ETCUSDT': 'ethereum-classic',
            'NEARUSDT': 'near',
            'FILUSDT': 'filecoin',
            'APTUSDT': 'aptos',
            'OPUSDT': 'optimism',
            'ARBUSDT': 'arbitrum',
            'STXUSDT': 'stack',
            'VETUSDT': 'vechain',
            'ICPUSDT': 'internet-computer',
            'RUNEUSDT': 'thorchain',
            'INJUSDT': 'injective-protocol',
            'TIAUSDT': 'celestia',
            'SUIUSDT': 'sui',
            'SEIUSDT': 'sei-network',
            'IMXUSDT': 'immutable-x',
            'KASUSDT': 'kaspa',
            'ORDIUSDT': 'ordinals',
            'PEPEUSDT': 'pepe',
            'BONKUSDT': 'bonk',
            'FLOKIUSDT': 'floki',
            'WIFUSDT': 'dogwifhat',
            'TAOUSDT': 'bittensor',
            'FETUSDT': 'fetch-ai',
            'AGIXUSDT': 'singularitynet',
            'OCEANUSDT': 'ocean-protocol',
            'RNDRUSDT': 'render-token',
            'RENDERUSDT': 'render-token',
            'PYTHUSDT': 'pyth-network',
            'JUPUSDT': 'jupiter-exchange-solana',
            'ONDOUSDT': 'ondo-finance',
            'PENDLEUSDT': 'pendle',
            'ARKMUSDT': 'arkham',
            'STRKUSDT': 'starknet',
            'AXLUSDT': 'axelarnetwork',
            'WLDUSDT': 'worldcoin-org',
            'PIXELUSDT': 'pixels',
            'PORTALUSDT': 'portal',
            'AEVOUSDT': 'aevo',
            'ETHFIUSDT': 'ether-fi',
            'ENAUSDT': 'ethena',
            'TNSRUSDT': 'tensor',
            'SAGAUSDT': 'saga-2',
            'TAOUSDT': 'bittensor',
            'OMUSDT': 'mantra-dao',
            'JTOUSDT': 'jito-governance-token',
            'MANTAUSDT': 'manta-network',
            'ALTUSDT': 'altlayer',
            'DYMUSDT': 'dymension',
            'ZROUSDT': 'layerzero',
            'ZKUSDT': 'zksync',
            'LISTAUSDT': 'lista-dao',
            'NOTUSDT': 'notcoin',
            'IOUSDT': 'io-net',
            'WELLUSDT': 'wellfield',
            'EIGENUSDT': 'eigenlayer',
            'SCRUSDT': 'scroll',
            'PENGUUSDT': 'pudgy-penguins',
            'VIRTUALUSDT': 'virtual-protocol',
            'TRUMPUSDT': 'maga',
            'MOVEUSDT': 'movement-dao',
            'SAPIENUSDT': 'sapien',
            'SAHARAUSDT': 'sahara-ai',
            'AVNTUSDT': 'avante',
            'SOMIUSDT': 'somis',
            'PLUMEUSDT': 'plume-network',
            'WLFIUSDT': 'world-liberty-financial',
            'RESOLVUSDT': 'resolv',
            'SYRUPUSDT': 'syrup-finance',
            'VANAUSDT': 'vana',
            'ALLOUSDT': 'allo',
            'SHELLUSDT': 'shell-protocol',
            'BARDUSDT': 'bard-core',
            'PARTIUSDT': 'partisia-blockchain',
            'AIXBTUSDT': 'aixbt',
            'ACTUSDT': 'act-the-ai-prophecy',
            'AIUSDT': 'any-inu',
            'TURBOUSDT': 'turbo',
            'RAREUSDT': 'superrare',
            'RAYUSDT': 'raydium',
            'POWRUSDT': 'power-ledger',
            'QNTUSDT': 'quant',
            'QTUMUSDT': 'qtum',
            'NMRUSDT': 'numeraire',
            'OGNUSDT': 'origin-protocol',
            'OGUSDT': 'og-fan-token',
            'ONEUSDT': 'harmony',
            'ONGUSDT': 'ontology-gas',
            'ONTUSDT': 'ontology',
            'SSVUSDT': 'ssv-network',
            'STORJUSDT': 'storj',
            'PHBUSDT': 'phoenix',
            'PYTHUSDT': 'pyth-network',
            'PUMPUSDT': 'pump',
            'ACHUSDT': 'alchemy-pay',
            'AAVEUSDT': 'aave'
        }
        # Убираем USDT и ищем в маппинге
        base = symbol.replace('USDT', '').upper()
        # Сначала ищем по полному символу (BTCUSDT)
        if symbol in mapping:
            return mapping[symbol]
        # Затем по базе (BTC)
        for k, v in mapping.items():
            if k.replace('USDT', '').upper() == base:
                return v
        # Если не нашли, возвращаем lowercase базу (рискованно, но лучше чем ничего)
        return base.lower()

    async def _fetch_market_cap_from_source(
        self, source: SourceConfig, symbol: str, base_symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Получение данных о капитализации из конкретного источника с повторными попытками"""
        max_retries = 2
        retry_delay = 1
        
        # Для CoinGecko используем специальный ID
        target_symbol = symbol
        if source.name == "CoinGecko":
            cg_id = self._convert_symbol_to_coingecko_id(symbol)
            if cg_id:
                target_symbol = cg_id
            else:
                logging.debug("[MarketCap] CoinGecko ID не найден для %s, используем %s", symbol, symbol)
        
        for attempt in range(max_retries + 1):
            try:
                # Rate limiting для CoinGecko
                if source.name == "CoinGecko":
                    wait_time = self.rate_limiter.get_wait_time() if self.rate_limiter else 0
                    if wait_time > 0:
                        logging.debug("[MarketCap] Rate limiting: waiting %.1fs", wait_time)
                        await asyncio.sleep(wait_time)
                    if self.rate_limiter:
                        self.rate_limiter.record_request()
                
                # Форматируем URL с учетом ID для CoinGecko
                url = source.url.format(symbol=target_symbol, base=base_symbol)

                async with aiohttp.ClientSession() as session:
                    timeout = aiohttp.ClientTimeout(total=source.timeout)

                    async with session.get(url, headers=source.headers, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            return parse_market_cap_data(source.name, data, symbol, base_symbol)
                        elif response.status == 429:
                            logging.debug("[MarketCap] %s HTTP 429", source.name)
                        elif response.status == 403:
                            logging.debug("[MarketCap] %s HTTP 403", source.name)
                        else:
                            logging.debug("[MarketCap] %s HTTP %s", source.name, response.status)

            except (RuntimeError, OSError, ValueError, asyncio.TimeoutError, aiohttp.ClientError) as e:
                error_msg = str(e)
                if "timeout" in error_msg.lower() and attempt < max_retries:
                    logging.debug("[MarketCap] %s таймаут, попытка %d/%d, повтор через %d сек", 
                                source.name, attempt + 1, max_retries + 1, retry_delay)
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Экспоненциальная задержка
                    continue
                elif "Domain name not found" in error_msg or "Name or service not known" in error_msg:
                    logging.warning("[MarketCap] %s API недоступен (домен не найден): %s", source.name, error_msg)
                elif "timeout" in error_msg.lower():
                    logging.debug("[MarketCap] %s таймаут: %s", source.name, error_msg)
                else:
                    logging.debug("[MarketCap] %s ошибка: %s", source.name, e)
                break

        return None


    async def get_volume_data(self, symbol: str) -> Optional[float]:
        """Получение данных об объеме (максимальный из всех источников)"""
        cache_key = self._get_cache_key("volume", symbol)

        # Проверяем кэш
        cached_data = self._get_cached_data(cache_key, 300)
        if cached_data:
            self.metrics.volume = RequestMetrics(
                latency_sec=0.0,
                sources_count=cached_data.get("sources_count"),
                source="cache",
                cache_hit=True,
            )
            return cached_data.get('volume', 0)

        sources = self.sources['volume']
        volumes = []
        start_ts = time.perf_counter()

        # Параллельно запрашиваем все источники
        # Создаем задачи СРАЗУ, чтобы при отмене их можно было корректно завершить
        tasks_with_names = []
        for source in sources:
            if not source.enabled:
                continue

            breaker = self._get_circuit_breaker(source.name)
            if not breaker.can_execute():
                logging.debug("[Volume] %s заблокирован circuit breaker", source.name)
                continue

            # Создаем задачу СРАЗУ (не храним корутину)
            task = asyncio.create_task(
                self._fetch_volume_from_source(source, symbol),
                name=f"volume_{source.name}"
            )
            tasks_with_names.append((source.name, task))

        if tasks_with_names:
            tasks = [task for _, task in tasks_with_names]
            
            try:
                # Выполняем все задачи параллельно
                gathered_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for idx, (source_name, _) in enumerate(tasks_with_names):
                    result = gathered_results[idx]
                    if isinstance(result, Exception):
                        logging.debug("[Volume] %s ошибка: %s", source_name, result)
                        self._get_circuit_breaker(source_name).on_failure()
                    elif result and result > 0:
                        volumes.append(result)
                        self._get_circuit_breaker(source_name).on_success()
            except asyncio.CancelledError:
                # При отмене - отменяем все созданные задачи
                for task in tasks:
                    if not task.done():
                        task.cancel()
                # Ждем завершения всех отмененных задач
                await asyncio.gather(*tasks, return_exceptions=True)
                raise

        if volumes:
            max_volume = max(volumes)
            result = {'volume': max_volume, 'sources_count': len(volumes), 'timestamp': time.time()}

            # Кэшируем результат
            self._set_cached_data(cache_key, result, 300)

            latency = time.perf_counter() - start_ts
            self.metrics.volume = RequestMetrics(
                latency_sec=latency,
                sources_count=len(volumes),
                source=f"{len(volumes)}_sources",
                cache_hit=False,
            )
            logging.info("[Volume] ✅ Макс. объём для %s: %s (из %s источников, %.3f с)", symbol, max_volume, len(volumes), latency)
            return max_volume

        logging.warning("[Volume] ❌ Все источники недоступны для %s", symbol)
        self.metrics.volume = RequestMetrics(
            latency_sec=time.perf_counter() - start_ts,
            sources_count=0,
            source=None,
            cache_hit=False,
        )
        return None

    async def _fetch_volume_from_source(self, source: SourceConfig, symbol: str) -> Optional[float]:
        """Получение данных об объеме из конкретного источника"""
        try:
            url = source.url.format(symbol=symbol)

            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=source.timeout)

                async with session.get(url, headers=source.headers, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        return parse_volume_data(source.name, data, symbol)
                    elif response.status == 429:
                        logging.debug("[Volume] %s HTTP 429", source.name)
                    elif response.status == 403:
                        logging.debug("[Volume] %s HTTP 403", source.name)
                    else:
                        logging.debug("[Volume] %s HTTP %s", source.name, response.status)

        except (RuntimeError, OSError, ValueError, asyncio.TimeoutError, aiohttp.ClientError) as e:
            error_msg = str(e)
            if "Domain name not found" in error_msg or "Name or service not known" in error_msg:
                logging.warning("[Volume] %s API недоступен (домен не найден): %s", source.name, error_msg)
            elif "timeout" in error_msg.lower():
                logging.debug("[Volume] %s таймаут: %s", source.name, error_msg)
            else:
                logging.debug("[Volume] %s ошибка: %s", source.name, e)

        return None


    async def get_price_data(self, symbol: str) -> Optional[float]:
        """Получение данных о цене (первый успешный источник)"""
        cache_key = self._get_cache_key("price", symbol)

        # Проверяем кэш
        cached_data = self._get_cached_data(cache_key, 60)
        if cached_data:
            self.metrics.price = RequestMetrics(
                latency_sec=0.0,
                sources_count=1,
                source=cached_data.get("source", "cache"),
                cache_hit=True,
            )
            return cached_data.get('price', 0)

        sources = self.sources['price']
        start_ts = time.perf_counter()

        # Быстрое переключение между источниками
        for source in sorted(sources, key=lambda x: x.priority):
            if not source.enabled:
                continue

            breaker = self._get_circuit_breaker(source.name)
            if not breaker.can_execute():
                logging.debug("[Price] %s заблокирован circuit breaker", source.name)
                continue

            try:
                price = await self._fetch_price_from_source(source, symbol)
                if price and price > 0:
                    result = {'price': price, 'source': source.name, 'timestamp': time.time()}

                    # Кэшируем результат
                    self._set_cached_data(cache_key, result, 60)

                    self._get_circuit_breaker(source.name).on_success()
                    latency = time.perf_counter() - start_ts
                    self.metrics.price = RequestMetrics(
                        latency_sec=latency,
                        sources_count=1,
                        source=source.name,
                        cache_hit=False,
                    )
                    logging.info("[Price] ✅ Цена для %s: %s (из %s, %.3f с)", symbol, price, source.name, latency)
                    return price

            except (RuntimeError, OSError, ValueError, asyncio.TimeoutError, aiohttp.ClientError) as e:
                logging.debug("[Price] %s ошибка: %s", source.name, e)
                self._get_circuit_breaker(source.name).on_failure()

        logging.warning("[Price] ❌ Все источники недоступны для %s", symbol)
        self.metrics.price = RequestMetrics(
            latency_sec=time.perf_counter() - start_ts,
            sources_count=0,
            source=None,
            cache_hit=False,
        )
        return None

    async def _fetch_price_from_source(self, source: SourceConfig, symbol: str) -> Optional[float]:
        """Получение данных о цене из конкретного источника"""
        try:
            url = source.url.format(symbol=symbol)

            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=source.timeout)

                async with session.get(url, headers=source.headers, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        return parse_price_data(source.name, data, symbol)
                    elif response.status == 429:
                        logging.debug("[Price] %s HTTP 429", source.name)
                    elif response.status == 403:
                        logging.debug("[Price] %s HTTP 403", source.name)
                    else:
                        logging.debug("[Price] %s HTTP %s", source.name, response.status)

        except (RuntimeError, OSError, ValueError, asyncio.TimeoutError, aiohttp.ClientError) as e:
            error_msg = str(e)
            if "Domain name not found" in error_msg or "Name or service not known" in error_msg:
                logging.warning("[Price] %s API недоступен (домен не найден): %s", source.name, error_msg)
            elif "timeout" in error_msg.lower():
                logging.debug("[Price] %s таймаут: %s", source.name, error_msg)
            else:
                logging.debug("[Price] %s ошибка: %s", source.name, e)

        return None


    async def get_news_data(self, symbol: str) -> List[Dict[str, Any]]:
        """Получение новостей из всех источников (RSS + API)"""
        cache_key = self._get_cache_key("news", symbol)

        # Проверяем кэш
        cached_data = self._get_cached_data(cache_key, 14400)
        if cached_data:
            return cached_data.get('news', [])

        sources = self.sources['news']
        all_news = []

        # Параллельно запрашиваем все источники
        tasks = []
        for source in sources:
            if not source.enabled:
                continue

            breaker = self._get_circuit_breaker(source.name)
            if not breaker.can_execute():
                logging.debug("[News] %s заблокирован circuit breaker", source.name)
                continue

            task = self._fetch_news_from_source(source, symbol)
            tasks.append((source.name, task))

        if tasks:
            # Выполняем все задачи параллельно
            for source_name, task in tasks:
                try:
                    news = await task
                    if news:
                        all_news.extend(news)
                        self._get_circuit_breaker(source_name).on_success()
                except (RuntimeError, OSError, ValueError, asyncio.TimeoutError, aiohttp.ClientError) as e:
                    logging.debug("[News] %s ошибка: %s", source_name, e)
                    self._get_circuit_breaker(source_name).on_failure()

        # Дедупликация по заголовку
        unique_news = []
        seen_titles = set()
        for news_item in all_news:
            title = news_item.get('title', '').lower()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(news_item)

        result = {
            'news': unique_news,
            'sources_count': len([t for t in tasks if t]),
            'total_count': len(unique_news),
            'timestamp': time.time()
        }

        # Кэшируем результат
        self._set_cached_data(cache_key, result, 14400)

        logging.info("[News] ✅ Получено %s новостей для %s (из %s источников)", len(unique_news), symbol, len(tasks))
        return unique_news

    async def _fetch_news_from_source(self, source: SourceConfig, symbol: str) -> List[Dict[str, Any]]:
        """Получение новостей из конкретного источника"""
        try:
            url = source.url.format(symbol=symbol)

            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=source.timeout)

                async with session.get(url, headers=source.headers, timeout=timeout) as response:
                    if response.status == 200:
                        content = await response.text()
                        return parse_news_data(source.name, content, symbol)
                    elif response.status == 429:
                        logging.debug("[News] %s HTTP 429", source.name)
                    elif response.status == 403:
                        logging.debug("[News] %s HTTP 403", source.name)
                    else:
                        logging.debug("[News] %s HTTP %s", source.name, response.status)

        except (RuntimeError, OSError, ValueError, asyncio.TimeoutError, aiohttp.ClientError) as e:
            error_msg = str(e)
            if "Domain name not found" in error_msg or "Name or service not known" in error_msg:
                logging.warning("[News] %s API недоступен (домен не найден): %s", source.name, error_msg)
            elif "timeout" in error_msg.lower():
                logging.debug("[News] %s таймаут: %s", source.name, error_msg)
            else:
                logging.debug("[News] %s ошибка: %s", source.name, e)

        return []

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Возвращает последние метрики latency/источников по запросам."""
        return self.metrics.to_dict()


# Глобальный экземпляр хаба (lazy initialization для предотвращения Database() при импорте)
_sources_hub = None

def get_sources_hub():
    """Получает или создает экземпляр SourcesHub (singleton с lazy init)"""
    global _sources_hub
    if _sources_hub is None:
        _sources_hub = SourcesHub()
    return _sources_hub

# Для обратной совместимости (создается только при обращении)
class _LazySourcesHub:
    """Lazy proxy для sources_hub"""
    def __getattr__(self, name):
        return getattr(get_sources_hub(), name)

sources_hub = _LazySourcesHub()
