#!/usr/bin/env python3

import asyncio
import logging
import time
from functools import lru_cache
from typing import Dict, List, Optional

import aiohttp

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PriceCache:
    """Кэш для цен с TTL"""

    def __init__(self, ttl_seconds: int = 10):
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, symbol: str) -> Optional[float]:
        """Получить цену из кэша"""
        if symbol in self.cache:
            price, timestamp = self.cache[symbol]
            if time.time() - timestamp < self.ttl:
                return price
            else:
                del self.cache[symbol]
        return None

    def set(self, symbol: str, price: float):
        """Установить цену в кэш"""
        self.cache[symbol] = (price, time.time())

    def clear(self):
        """Очистить кэш"""
        self.cache.clear()


# Глобальный кэш цен
price_cache = PriceCache(ttl_seconds=10)


# Состояние источников (health/circuit-breaker)
class SourceState:
    def __init__(self, fail_threshold: int = 3, cooldown_sec: int = 300):
        self.fail_threshold = fail_threshold
        self.cooldown_sec = cooldown_sec
        self.state = {}

    def is_available(self, name: str) -> bool:
        info = self.state.get(name) or {}
        disabled_until = float(info.get("disabled_until", 0))
        if disabled_until and time.time() < disabled_until:
            return False
        return True

    def mark_result(self, name: str, ok: bool, latency_ms: int = None):
        now = time.time()
        info = self.state.get(name) or {"fails": 0, "disabled_until": 0, "latency_ms": None}
        if ok:
            # На успехе снимаем счётчик и разбан
            info["fails"] = 0
            info["disabled_until"] = 0
            if latency_ms is not None:
                # Сохраняем последнюю успешную латентность (эксп. сглаживание можно добавить при желании)
                info["latency_ms"] = int(latency_ms)
        else:
            info["fails"] = int(info.get("fails", 0)) + 1
            if info["fails"] >= self.fail_threshold:
                info["disabled_until"] = now + self.cooldown_sec
                logger.warning(
                    "⛔ Источник %s временно отключён на %ds (сбои=%d)",
                    name,
                    self.cooldown_sec,
                    info["fails"],
                )
        self.state[name] = info

    def get_latency(self, name: str) -> float:
        info = self.state.get(name) or {}
        lat = info.get("latency_ms")
        return float(lat) if lat is not None else float("inf")


source_state = SourceState(fail_threshold=3, cooldown_sec=300)


class PriceAPI:
    """Улучшенный API для получения цен с множественными источниками"""

    def __init__(self):
        self.session = None
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def __aenter__(self):
        from src.utils.session_manager import session_manager

        self.session = await session_manager.get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Мы не закрываем общую сессию здесь, она управляется SessionManager
        pass

    async def get_price_binance(self, symbol: str) -> Optional[float]:
        """Получить цену с Binance"""
        try:
            start = time.perf_counter()
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    price = float(data["price"])
                    try:
                        from db import Database

                        Database().log_api_latency(
                            "price:binance", int((time.perf_counter() - start) * 1000), True
                        )
                    except Exception:
                        pass
                    return price
                else:
                    logger.warning(f"Binance API error for {symbol}: HTTP {response.status}")
                    try:
                        from db import Database

                        Database().log_api_latency(
                            "price:binance", int((time.perf_counter() - start) * 1000), False
                        )
                    except Exception:
                        pass
                    return None
        except Exception as e:
            logger.warning(f"Binance API error for {symbol}: {e}")
            try:
                from db import Database

                Database().log_api_latency("price:binance", 0, False)
            except Exception:
                pass
            return None

    async def get_price_bybit(self, symbol: str) -> Optional[float]:
        """Получить цену с Bybit"""
        try:
            start = time.perf_counter()
            url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("result", {}).get("list"):
                        price = float(data["result"]["list"][0]["lastPrice"])
                        try:
                            from db import Database

                            Database().log_api_latency(
                                "price:bybit", int((time.perf_counter() - start) * 1000), True
                            )
                        except Exception:
                            pass
                        return price
                    try:
                        from db import Database

                        Database().log_api_latency(
                            "price:bybit", int((time.perf_counter() - start) * 1000), False
                        )
                    except Exception:
                        pass
                    return None
                else:
                    logger.warning(f"Bybit API error for {symbol}: HTTP {response.status}")
                    try:
                        from db import Database

                        Database().log_api_latency(
                            "price:bybit", int((time.perf_counter() - start) * 1000), False
                        )
                    except Exception:
                        pass
                    return None
        except Exception as e:
            logger.warning(f"Bybit API error for {symbol}: {e}")
            try:
                from db import Database

                Database().log_api_latency("price:bybit", 0, False)
            except Exception:
                pass
            return None

    async def get_price_mexc(self, symbol: str) -> Optional[float]:
        """Получить цену с MEXC"""
        try:
            start = time.perf_counter()
            url = f"https://www.mexc.com/api/platform/spot/market/v2/ticker?symbol={symbol}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        price = float(data["data"]["last"])
                        try:
                            from db import Database

                            Database().log_api_latency(
                                "price:mexc", int((time.perf_counter() - start) * 1000), True
                            )
                        except Exception:
                            pass
                        return price
                    try:
                        from db import Database

                        Database().log_api_latency(
                            "price:mexc", int((time.perf_counter() - start) * 1000), False
                        )
                    except Exception:
                        pass
                    return None
                else:
                    logger.warning(f"MEXC API error for {symbol}: HTTP {response.status}")
                    try:
                        from db import Database

                        Database().log_api_latency(
                            "price:mexc", int((time.perf_counter() - start) * 1000), False
                        )
                    except Exception:
                        pass
                    return None
        except Exception as e:
            logger.warning(f"MEXC API error for {symbol}: {e}")
            try:
                from db import Database

                Database().log_api_latency("price:mexc", 0, False)
            except Exception:
                pass
            return None

    async def get_price_okx(self, symbol: str) -> Optional[float]:
        """Получить цену с OKX"""
        try:
            start = time.perf_counter()

            # OKX использует формат BTC-USDT вместо BTCUSDT
            def _okx_symbol(sym: str) -> str:
                if sym.endswith("USDT") and len(sym) > 4:
                    return f"{sym[:-4]}-USDT"
                return sym

            okx_sym = _okx_symbol(symbol)
            url = f"https://www.okx.com/api/v5/market/ticker?instId={okx_sym}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        price = float(data["data"][0]["last"])
                        try:
                            from db import Database

                            Database().log_api_latency(
                                "price:okx", int((time.perf_counter() - start) * 1000), True
                            )
                        except Exception:
                            pass
                        return price
                    try:
                        from db import Database

                        Database().log_api_latency(
                            "price:okx", int((time.perf_counter() - start) * 1000), False
                        )
                    except Exception:
                        pass
                    return None
                else:
                    logger.warning(f"OKX API error for {symbol}: HTTP {response.status}")
                    try:
                        from db import Database

                        Database().log_api_latency(
                            "price:okx", int((time.perf_counter() - start) * 1000), False
                        )
                    except Exception:
                        pass
                    return None
        except Exception as e:
            logger.warning(f"OKX API error for {symbol}: {e}")
            try:
                from db import Database

                Database().log_api_latency("price:okx", 0, False)
            except Exception:
                pass
            return None


async def get_current_price_robust(symbol: str, max_retries: int = 3) -> Optional[float]:
    """
    Надежное получение текущей цены с множественными источниками

    Args:
        symbol: Торговая пара (например, 'BTCUSDT')
        max_retries: Максимальное количество попыток

    Returns:
        Цена или None если не удалось получить
    """

    # Фильтруем тестовые символы
    if symbol.upper().startswith("TEST"):
        logger.debug(f"Пропускаем тестовый символ: {symbol}")
        return None

    # Глобальная фильтрация стейблкоинов для общих запросов цены
    try:
        from stablecoin_filter import should_skip_stablecoin

        if should_skip_stablecoin(symbol, context="price_update"):
            logger.debug(f"🛑 Пропуск запроса цены для стейблкоина: {symbol}")
            return None
    except Exception:
        pass

    # Проверяем кэш
    cached_price = price_cache.get(symbol)
    if cached_price is not None:
        logger.debug(f"Cache hit for {symbol}: {cached_price}")
        return cached_price

    # Сначала пробуем универсальный менеджер источников данных
    try:
        from src.data.sources_manager import data_manager

        price_data = await data_manager.get_price_data(symbol)
        if price_data and "price" in price_data:
            price = float(price_data["price"])
            if price > 0:
                price_cache.set(symbol, price)
                logger.info(f"✅ {price_data.get('source', 'Unknown')}: {symbol} = {price}")
                return price
    except Exception as e:
        logger.warning(f"Ошибка получения цены через универсальный менеджер: {e}")

    # Список источников в порядке приоритета (расширенный)
    sources = [
        ("Binance", "get_price_binance"),
        ("Bybit", "get_price_bybit"),
        ("MEXC", "get_price_mexc"),
        ("OKX", "get_price_okx"),
        ("KuCoin", "get_price_kucoin"),
        ("Gate.io", "get_price_gateio"),
        ("Huobi", "get_price_huobi"),
        ("Coinbase", "get_price_coinbase"),
    ]

    # Динамическая сортировка: доступные вперёд, затем по последней латентности
    def _sort_key(item):
        name = item[0]
        avail = 0 if source_state.is_available(name) else 1
        lat = source_state.get_latency(name)
        return (avail, lat)

    sources.sort(key=_sort_key)

    async with PriceAPI() as api:
        # Быстрое переключение между всеми источниками
        for source_name, method_name in sources:
            # Пропускаем источник, если он временно отключён
            if not source_state.is_available(source_name):
                logger.debug("Источник %s временно отключён", source_name)
                continue
            try:
                method = getattr(api, method_name)
                price = await method(symbol)

                if price is not None and price > 0:
                    # Сохраняем в кэш
                    price_cache.set(symbol, price)
                    logger.info(f"✅ Получена цена {symbol}: {price} с {source_name}")
                    # Латентность уже известна в методе источника; если не была отмечена, отметим без неё
                    source_state.mark_result(source_name, True)
                    return price
                # Неуспех — считаем как сбой источника
                source_state.mark_result(source_name, False)
            except Exception as e:
                logger.debug(f"❌ {source_name} недоступен: {e}")
                source_state.mark_result(source_name, False)
                continue

    logger.error(f"❌ Не удалось получить цену для {symbol} после {max_retries} попыток")
    return None


async def get_prices_bulk(symbols: List[str], max_retries: int = 3) -> Dict[str, float]:
    """
    Получение цен для множества символов одновременно

    Args:
        symbols: Список торговых пар
        max_retries: Максимальное количество попыток

    Returns:
        Словарь {symbol: price}
    """
    results = {}

    # Создаем задачи для всех символов
    tasks = []
    for symbol in symbols:
        task = asyncio.create_task(get_current_price_robust(symbol, max_retries))
        tasks.append((symbol, task))

    # Выполняем все задачи
    for symbol, task in tasks:
        try:
            price = await task
            if price is not None:
                results[symbol] = price
        except Exception as e:
            logger.error(f"Ошибка получения цены для {symbol}: {e}")

    return results


# Функция для обратной совместимости
async def get_current_price_simple(symbol: str) -> Optional[float]:
    """Простая функция для получения текущей цены (обратная совместимость)"""
    return await get_current_price_robust(symbol, max_retries=2)


# Тестовая функция
async def test_price_api():
    """Тест API получения цен"""
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOTUSDT"]

    print("🧪 ТЕСТ УЛУЧШЕННОГО API ЦЕН")
    print("=" * 50)

    # Тест одиночных цен
    for symbol in symbols:
        price = await get_current_price_robust(symbol)
        if price:
            print(f"✅ {symbol}: {price:.4f}")
        else:
            print(f"❌ {symbol}: Не удалось получить цену")

    print("\n" + "=" * 50)

    # Тест массового получения
    print("📊 МАССОВОЕ ПОЛУЧЕНИЕ ЦЕН:")
    prices = await get_prices_bulk(symbols)
    for symbol, price in prices.items():
        print(f"✅ {symbol}: {price:.4f}")

    print(f"\n📈 Получено цен: {len(prices)}/{len(symbols)}")
    print("✅ ТЕСТ ЗАВЕРШЕН!")


if __name__ == "__main__":
    asyncio.run(test_price_api())
