import requests
import ccxt
import logging
import time
import asyncio
import socket
from decimal import Decimal
try:
    from src.utils.cache_utils import cache_with_ttl
except ImportError:
    try:
        from cache_utils import cache_with_ttl
    except ImportError:
        def cache_with_ttl(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
try:
    import aiohttp  # type: ignore
    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None  # type: ignore
    AIOHTTP_AVAILABLE = False


# Декоратор для профилирования
def profile(func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logging.info(f"{func.__name__} выполнена за {elapsed:.3f} сек")
        return result

    return wrapper


@profile
def get_ohlc_binance_sync(symbol, interval="1h", limit=100):
    """
    Получить OHLC с Binance API (https://api.binance.com/api/v3/klines)
    symbol: например, BTCUSDT
    interval: "1h", "4h" и т.д.
    limit: до 1000
    Возвращает список словарей с ключами: timestamp, open, high, low, close, volume
    """
    # Игнорируем тестовые символы
    if str(symbol).upper().startswith("TEST"):
        logging.warning("Игнорируем тестовый символ: %s", symbol)
        return []

    hosts = [
        "https://api.binance.com",
        "https://api1.binance.com",
        "https://api2.binance.com",
        "https://api3.binance.com",
        "https://api4.binance.com",  # Дополнительный хост
    ]
    endpoint = "/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    max_retries = 1

    for attempt in range(max_retries):
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (compatible; ATRA-Bot/1.0)',
                'Accept': 'application/json',
                'Connection': 'keep-alive',
            })

            for host_idx, host in enumerate(hosts):
                url = f"{host}{endpoint}"
                try:
                    # Увеличиваем timeout и добавляем retry strategy
                    resp = session.get(
                        url,
                        params=params,
                        timeout=30,  # Увеличенный timeout
                        allow_redirects=True
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if data and len(data) > 0:
                            ohlc = [
                                {
                                    "timestamp": int(item[0]),
                                    "open": Decimal(str(item[1])),
                                    "high": Decimal(str(item[2])),
                                    "low": Decimal(str(item[3])),
                                    "close": Decimal(str(item[4])),
                                    "volume": Decimal(str(item[5])),
                                }
                                for item in data
                            ]
                            print(f"✅ Binance: получено {len(ohlc)} свечей для {symbol} ({host})")
                            return ohlc
                        else:
                            print(f"⚠️ Binance: пустой ответ для {symbol} ({host})")
                            continue
                    elif resp.status_code == 429:  # Rate limit
                        print(f"⚠️ Binance rate limit для {symbol} ({host}), ждем...")
                        import time
                        time.sleep(5)
                        continue
                    elif resp.status_code >= 500:  # Server error
                        print(f"⚠️ Binance server error {resp.status_code} для {symbol} ({host})")
                        continue
                    else:
                        # Клиентские ошибки (4xx, кроме 429) не имеют смысла для повторов —
                        # чаще всего это неверный символ или параметры запроса
                        if 400 <= resp.status_code < 500:
                            print(f"⚠️ Binance: HTTP {resp.status_code} для {symbol} ({host}) — клиентская ошибка, прекращаем повторы")
                            return []
                        print(f"⚠️ Binance: HTTP {resp.status_code} для {symbol} ({host})")
                        continue

                except requests.exceptions.Timeout:
                    print(f"⏰ Binance timeout для {symbol} ({host})")
                    continue
                except requests.exceptions.ConnectionError:
                    print(f"🔌 Binance connection error для {symbol} ({host})")
                    continue
                except socket.gaierror:
                    print(f"🌐 Binance DNS error для {symbol} ({host})")
                    continue
                except requests.exceptions.RequestException as e:
                    print(f"❌ Binance request error {host} для {symbol}: {e}")
                    continue

            # Если все хосты провалились, ждем перед следующей попыткой
            if attempt < max_retries - 1:
                delay = min(2 ** attempt, 10)  # Максимум 10 секунд
                print(f"⏳ Все хосты провалились, ждем {delay} сек перед попыткой {attempt + 2}/{max_retries}")
                import time
                time.sleep(delay)

        except Exception as e:
            print(f"❌ Binance OHLC error for {symbol} {interval}: {e}")
            logging.error(f"Binance OHLC error for {symbol} {interval}: {e}", exc_info=True)
            return []


def _interval_to_ms(interval: str) -> int:
    """Конвертация интервала Binance в миллисекунды для пошаговой пагинации."""
    mapping = {
        "1m": 60_000,
        "3m": 3 * 60_000,
        "5m": 5 * 60_000,
        "15m": 15 * 60_000,
        "30m": 30 * 60_000,
        "1h": 60 * 60_000,
        "2h": 2 * 60 * 60_000,
        "4h": 4 * 60 * 60_000,
        "6h": 6 * 60 * 60_000,
        "12h": 12 * 60 * 60_000,
        "1d": 24 * 60 * 60_000,
    }
    return mapping.get(interval, 60 * 60_000)


@profile
def get_ohlc_binance_sync_range(symbol, interval="1h", days=90, max_per_call=1000):
    """
    Получить полный OHLC диапазон через пагинацию startTime/endTime для покрытия длинных периодов.

    - symbol: например, BTCUSDT
    - interval: "1h"/"4h"/"1d" и т.д.
    - days: глубина истории в днях
    - max_per_call: лимит свечей в одном запросе (до 1000 у Binance)

    Возвращает список словарей: {timestamp, open, high, low, close, volume}
    """
    try:
        import requests
        import time as _time
    except ImportError:
        return []

    if str(symbol).upper().startswith("TEST"):
        logging.warning("Игнорируем тестовый символ (range): %s", symbol)
        return []

    hosts = [
        "https://api.binance.com",
        "https://api1.binance.com",
        "https://api2.binance.com",
        "https://api3.binance.com",
        "https://api4.binance.com",
    ]
    endpoint = "/api/v3/klines"

    now_ms = int(_time.time() * 1000)
    start_ms = now_ms - int(days * 24 * 60 * 60 * 1000)
    step_ms = _interval_to_ms(interval) * max(1, max_per_call - 1)

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (compatible; ATRA-Bot/1.0)',
        'Accept': 'application/json',
        'Connection': 'keep-alive',
    })

    all_rows = []
    cursor = start_ms

    while cursor < now_ms:
        # Двигаем окно так, чтобы избежать дубликатов по границе
        end_ms = min(now_ms, cursor + step_ms)
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": max_per_call,
            "startTime": cursor,
            "endTime": end_ms,
        }

        got = []
        for host in hosts:
            url = f"{host}{endpoint}"
            try:
                resp = session.get(url, params=params, timeout=30, allow_redirects=True)
                if resp.status_code == 200:
                    data = resp.json() or []
                    if data:
                        got = data
                        break
                elif resp.status_code == 429:
                    _time.sleep(2)
                    continue
                elif resp.status_code >= 500:
                    continue
                else:
                    break
            except requests.exceptions.RequestException:
                continue

        if not got:
            # Ничего не получили – двигаемся вперёд, чтобы не зациклиться
            cursor = end_ms + _interval_to_ms(interval)
            continue

        chunk = [
            {
                "timestamp": int(item[0]),
                "open": Decimal(str(item[1])),
                "high": Decimal(str(item[2])),
                "low": Decimal(str(item[3])),
                "close": Decimal(str(item[4])),
                "volume": Decimal(str(item[5])),
            }
            for item in got
        ]

        # Удаляем возможный дубликат стыковочной свечи
        if all_rows and chunk:
            last_ts = all_rows[-1]["timestamp"]
            if chunk[0]["timestamp"] == last_ts:
                chunk = chunk[1:]

        all_rows.extend(chunk)

        if not chunk:
            cursor = end_ms + _interval_to_ms(interval)
        else:
            cursor = chunk[-1]["timestamp"] + _interval_to_ms(interval)

        # Безопасная пауза для rate-limit
        _time.sleep(0.2)

    return all_rows


@profile
def get_ohlc_bybit_sync(symbol, interval="1h", limit=100):
    """
    Получить OHLC с Bybit API (https://api.bybit.com/v5/market/kline)
    symbol: например, BTCUSDT
    interval: "1h", "4h" и т.д.
    limit: до 1000
    Возвращает список словарей с ключами: timestamp, open, high, low, close, volume
    """
    url = "https://api.bybit.com/v5/market/kline"
    # Bybit требует interval: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M
    interval_map = {
        "1m": "1",
        "3m": "3",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "2h": "120",
        "4h": "240",
        "6h": "360",
        "12h": "720",
        "1d": "D",
        "1w": "W",
        "1M": "M",
    }
    bybit_interval = interval_map.get(interval, interval)
    params = {"symbol": symbol, "interval": bybit_interval, "limit": limit, "category": "spot"}
    try:
        import requests

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

        resp = session.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            klines = data.get("result", {}).get("list", [])
            if klines and len(klines) > 0:
                ohlc = [
                    {
                        "timestamp": int(item[0]),
                        "open": Decimal(str(item[1])),
                        "high": Decimal(str(item[2])),
                        "low": Decimal(str(item[3])),
                        "close": Decimal(str(item[4])),
                        "volume": Decimal(str(item[5])),
                    }
                    for item in klines
                ]
                print(f"✅ Bybit: получено {len(ohlc)} свечей для {symbol}")
                return ohlc
            else:
                print(f"❌ Bybit: пустой ответ для {symbol}")
                return []
        else:
            print(f"❌ Bybit: HTTP {resp.status_code} для {symbol}")
            return []
    except Exception as e:
        print(f"❌ Bybit OHLC error for {symbol} {interval}: {e}")
        logging.error(f"Bybit OHLC error for {symbol} {interval}: {e}", exc_info=True)
        return []


@cache_with_ttl(ttl_seconds=60)
async def get_ohlc_binance_sync_async(symbol, interval="1h", limit=100, **kwargs):
    """Асинхронная функция - используем только синхронные запросы для надежности"""
    if str(symbol).upper().startswith("TEST"):
        logging.warning("Игнорируем тестовый символ (async): %s", symbol)
        return []
    try:
        # Используем только синхронный запрос для максимальной надежности
        # При необходимости можно принудительно обойти кэш вызовом с _no_cache=True (прокидывается через декоратор)
        result = get_ohlc_binance_sync(symbol, interval, limit)
        if result and len(result) > 0:
            print(f"✅ Успешно получены данные для {symbol}: {len(result)} свечей")
            return result
        else:
            print(f"❌ Синхронный запрос вернул пустой результат для {symbol}")
            return []
    except Exception as e:
        print(f"❌ Синхронный запрос не сработал для {symbol}: {e}")
        return []


@cache_with_ttl(ttl_seconds=60)
async def get_ohlc_bybit_sync_async(symbol, interval="1h", limit=100, **kwargs):
    """Асинхронная функция - используем только синхронные запросы для надежности"""
    try:
        # Используем только синхронный запрос для максимальной надежности
        result = get_ohlc_bybit_sync(symbol, interval, limit)
        if result and len(result) > 0:
            print(f"✅ Успешно получены данные Bybit для {symbol}: {len(result)} свечей")
            return result
        else:
            print(f"❌ Синхронный запрос Bybit вернул пустой результат для {symbol}")
            return []
    except Exception as e:
        print(f"❌ Синхронный запрос Bybit не сработал для {symbol}: {e}")
        return []


def get_ohlc_bitget_sync(symbol, interval="1h", limit=100):
    """
    Получить OHLC с Bitget API (https://api.bitget.com/api/spot/v1/market/candles)
    symbol: например, BTCUSDT
    interval: "1h", "4h" и т.д.
    limit: до 1000
    Возвращает список словарей с ключами: timestamp, open, high, low, close, volume
    """
    url = "https://api.bitget.com/api/spot/v1/market/candles"

    def to_bitget_symbol(symbol):
        if symbol.endswith("USDT"):
            return symbol.replace("USDT", "-USDT")
        return symbol

    bitget_symbol = to_bitget_symbol(symbol)
    params = {"symbol": bitget_symbol, "period": interval, "limit": limit}
    try:
        import requests

        # Настройки для более надежного подключения
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

        resp = session.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            klines = data.get("data")
            if not klines or not isinstance(klines, list):
                print(f"Bitget OHLC: пустой или некорректный ответ для {bitget_symbol} {interval}")
                return []
        ohlc = [
            {
                "timestamp": int(item[0]),
                "open": Decimal(str(item[1])),
                "high": Decimal(str(item[2])),
                "low": Decimal(str(item[3])),
                "close": Decimal(str(item[4])),
                "volume": Decimal(str(item[5])),
            }
            for item in klines
        ]
        return ohlc
    except Exception as e:
        print(f"Bitget OHLC error for {bitget_symbol} {interval}: {e}")
        logging.error(f"Bitget OHLC error for {bitget_symbol} {interval}: {e}", exc_info=True)
        return []


def get_ohlc_binance_futures_sync(symbol, interval="1h", limit=720):
    """
    Получить OHLC с Binance Futures через ccxt
    symbol: например, BTCUSDT
    interval: "1h", "4h" и т.д.
    limit: до 1500
    Возвращает список словарей с ключами: timestamp, open, high, low, close, volume
    """
    exchange = ccxt.binance({"options": {"defaultType": "future"}})
    tf_map = {"1h": "1h", "4h": "4h", "1d": "1d"}
    tf = tf_map.get(interval, interval)
    since = exchange.milliseconds() - limit * 60 * 60 * 1000  # limit часов назад
    try:
        ohlcv = exchange.fetch_ohlcv(
            symbol.replace("USDT", "/USDT"), timeframe=tf, since=since, limit=limit
        )
        return [
            {
                "timestamp": int(item[0]),
                "open": Decimal(str(item[1])),
                "high": Decimal(str(item[2])),
                "low": Decimal(str(item[3])),
                "close": Decimal(str(item[4])),
                "volume": Decimal(str(item[5])),
            }
            for item in ohlcv
        ]
    except Exception as e:
        print(f"Binance Futures OHLC error for {symbol} {interval}: {e}")
        logging.error(f"Binance Futures OHLC error for {symbol} {interval}: {e}", exc_info=True)
        return []


@cache_with_ttl(ttl_seconds=60)
async def get_ohlc_coingecko_sync_async(symbol, interval="1h", limit=100):
    """
    Получает OHLC данные с CoinGecko API
    """
    if not AIOHTTP_AVAILABLE:
        print("[DEBUG] CoinGecko: aiohttp недоступен, пропуск провайдера")
        return []
    import time

    # Конвертируем symbol в coingecko_id
    def symbol_to_coingecko_id(symbol):
        # Базовое сопоставление популярных монет
        mapping = {
            "BTCUSDT": "bitcoin",
            "ETHUSDT": "ethereum",
            "BNBUSDT": "binancecoin",
            "SOLUSDT": "solana",
            "XRPUSDT": "ripple",
            "ADAUSDT": "cardano",
            "AVAXUSDT": "avalanche-2",
            "DOTUSDT": "polkadot",
            "LINKUSDT": "chainlink",
            "MATICUSDT": "matic-network",
            "UNIUSDT": "uniswap",
            "LTCUSDT": "litecoin",
            "ATOMUSDT": "cosmos",
            "ETCUSDT": "ethereum-classic",
            "FILUSDT": "filecoin",
            "NEARUSDT": "near",
            "APTUSDT": "aptos",
            "OPUSDT": "optimism",
            "TONUSDT": "the-open-network",
            "DOGEUSDT": "dogecoin"
        }
        return mapping.get(symbol, None)

    # Конвертируем интервал в дни для CoinGecko
    def interval_to_days(interval):
        mapping = {
            "1m": 1,
            "5m": 1,
            "15m": 1,
            "30m": 1,
            "1h": 1,
            "2h": 2,
            "4h": 4,
            "6h": 7,
            "12h": 7,
            "1d": 30,
            "1w": 90,
            "1M": 365
        }
        return mapping.get(interval, 1)

    coingecko_id = symbol_to_coingecko_id(symbol)
    if not coingecko_id:
        print(f"CoinGecko: неизвестный символ {symbol}")
        return []

    days = interval_to_days(interval)
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/ohlc"
    params = {"vs_currency": "usd", "days": str(days)}

    timeout = aiohttp.ClientTimeout(total=30, connect=10)

    for attempt in range(3):  # 3 попытки
        try:
            print(f"[DEBUG] {symbol}: CoinGecko попытка {attempt + 1}")
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, params=params) as resp:
                    print(f"[DEBUG] {symbol}: CoinGecko статус {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"[DEBUG] {symbol}: CoinGecko размер данных {len(data) if data else 0}")
                        if data and len(data) > 0:
                            ohlc = [
                                {
                                    "timestamp": int(item[0]),
                                    "open": Decimal(str(item[1])),
                                    "high": Decimal(str(item[2])),
                                    "low": Decimal(str(item[3])),
                                    "close": Decimal(str(item[4])),
                                    "volume": Decimal("0")  # CoinGecko не предоставляет volume в OHLC
                                }
                                for item in data
                            ]
                            print(f"[DEBUG] {symbol}: CoinGecko успешно получено {len(ohlc)} записей")
                            return ohlc
                        else:
                            print(f"[DEBUG] {symbol}: CoinGecko пустой ответ")
                            if attempt < 2:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return []
                    elif resp.status == 429:  # Rate limit
                        print(f"[DEBUG] {symbol}: CoinGecko rate limit попытка {attempt + 1}")
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return []
                    else:
                        print(f"[DEBUG] {symbol}: CoinGecko HTTP {resp.status}")
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return []

        except asyncio.TimeoutError:
            print(f"[DEBUG] {symbol}: CoinGecko timeout попытка {attempt + 1}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            return []
        except Exception as e:
            print(f"[DEBUG] {symbol}: CoinGecko error попытка {attempt + 1}: {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            return []

    print(f"[DEBUG] {symbol}: CoinGecko все попытки исчерпаны")
    return []

    return []


@cache_with_ttl(ttl_seconds=60)
async def get_ohlc_cryptocompare_sync_async(symbol, interval="1h", limit=100):
    """
    Получить OHLC с CryptoCompare API (https://min-api.cryptocompare.com/)
    symbol: например, BTCUSDT -> BTC
    interval: "1h", "4h" и т.д.
    limit: до 2000
    Возвращает список словарей с ключами: timestamp, open, high, low, close, volume
    """
    # Преобразуем символ для CryptoCompare (убираем USDT)
    base_symbol = symbol.replace("USDT", "").replace("USD", "")

    # Маппинг интервалов для CryptoCompare
    interval_map = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "6h": "6h",
        "12h": "12h",
        "1d": "1d",
        "1w": "1w",
        "1M": "1M"
    }

    cryptocompare_interval = interval_map.get(interval, interval)

    # URL для CryptoCompare
    url = f"https://min-api.cryptocompare.com/data/v2/histohour"
    params = {
        "fsym": base_symbol,
        "tsym": "USD",
        "limit": min(limit, 2000),  # CryptoCompare максимум 2000
        "aggregate": 1
    }

    # Если aiohttp недоступен, пропускаем CryptoCompare
    if not AIOHTTP_AVAILABLE:
        print("[DEBUG] CryptoCompare: aiohttp недоступен, пропуск провайдера")
        return []

    # Увеличиваем таймаут для стабильности
    timeout = aiohttp.ClientTimeout(total=30, connect=10)

    for attempt in range(3):  # 3 попытки
        try:
            print(f"[DEBUG] {symbol}: CryptoCompare попытка {attempt + 1}")
            connector = aiohttp.TCPConnector(ssl=False)  # Отключаем SSL проверку
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, params=params) as resp:
                    print(f"[DEBUG] {symbol}: CryptoCompare статус {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"[DEBUG] {symbol}: CryptoCompare размер данных {len(data.get('Data', {}).get('Data', [])) if data.get('Data', {}).get('Data') else 0}")

                        if data.get('Response') == 'Success' and data.get('Data', {}).get('Data'):
                            ohlc_data = data['Data']['Data']
                            ohlc = [
                                {
                                    "timestamp": int(item["time"]) * 1000,  # Конвертируем в миллисекунды
                                    "open": float(item["open"]),
                                    "high": float(item["high"]),
                                    "low": float(item["low"]),
                                    "close": float(item["close"]),
                                    "volume": float(item["volumeto"]),  # Объем в USD
                                }
                                for item in ohlc_data
                            ]
                            print(f"[DEBUG] {symbol}: CryptoCompare успешно получено {len(ohlc)} записей")
                            return ohlc
                        else:
                            print(f"[DEBUG] {symbol}: CryptoCompare пустой ответ или ошибка")
                            if attempt < 2:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return []
                    else:
                        print(f"[DEBUG] {symbol}: CryptoCompare HTTP {resp.status}")
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return []

        except asyncio.TimeoutError:
            print(f"[DEBUG] {symbol}: CryptoCompare timeout попытка {attempt + 1}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            return []
        except Exception as e:
            print(f"[DEBUG] {symbol}: CryptoCompare error попытка {attempt + 1}: {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            return []

    print(f"[DEBUG] {symbol}: CryptoCompare все попытки исчерпаны")
    return []

@cache_with_ttl(ttl_seconds=60)
async def get_ohlc_coincap_sync_async(symbol, interval="1h", limit=100):
    """
    Получить OHLC с CoinCap API (https://docs.coincap.io/)
    symbol: например, BTCUSDT -> bitcoin
    interval: "1h", "4h" и т.д.
    limit: до 2000
    Возвращает список словарей с ключами: timestamp, open, high, low, close, volume
    """
    # Преобразуем символ для CoinCap
    symbol_map = {
        "BTCUSDT": "bitcoin",
        "ETHUSDT": "ethereum",
        "BNBUSDT": "binance-coin",
        "ADAUSDT": "cardano",
        "SOLUSDT": "solana",
        "DOTUSDT": "polkadot",
        "DOGEUSDT": "dogecoin",
        "AVAXUSDT": "avalanche-2",
        "MATICUSDT": "matic-network",
        "LINKUSDT": "chainlink"
    }

    coin_id = symbol_map.get(symbol, symbol.lower().replace("usdt", ""))

    # URL для CoinCap (исторические данные)
    url = f"https://api.coincap.io/v2/assets/{coin_id}/history"

    # Маппинг интервалов для CoinCap
    interval_map = {
        "1h": "h1",
        "4h": "h4",
        "1d": "d1"
    }

    coincap_interval = interval_map.get(interval, "h1")
    params = {
        "interval": coincap_interval
    }

    if not AIOHTTP_AVAILABLE:
        print("[DEBUG] CoinCap: aiohttp недоступен, пропуск провайдера")
        return []

    # Увеличиваем таймаут для стабильности
    timeout = aiohttp.ClientTimeout(total=30, connect=10)

    for attempt in range(3):  # 3 попытки
        try:
            print(f"[DEBUG] {symbol}: CoinCap попытка {attempt + 1}")
            connector = aiohttp.TCPConnector(ssl=False)  # Отключаем SSL проверку
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, params=params) as resp:
                    print(f"[DEBUG] {symbol}: CoinCap статус {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        history_data = data.get('data', [])
                        print(f"[DEBUG] {symbol}: CoinCap размер данных {len(history_data)}")

                        if history_data:
                            ohlc = [
                                {
                                    "timestamp": int(item["time"]),
                                    "open": float(item["priceUsd"]),
                                    "high": float(item["priceUsd"]),  # CoinCap не предоставляет OHLC, используем цену
                                    "low": float(item["priceUsd"]),
                                    "close": float(item["priceUsd"]),
                                    "volume": float(item.get("volumeUsd", 0)),
                                }
                                for item in history_data[-limit:]  # Берем последние записи
                            ]
                            print(f"[DEBUG] {symbol}: CoinCap успешно получено {len(ohlc)} записей")
                            return ohlc
                        else:
                            print(f"[DEBUG] {symbol}: CoinCap пустой ответ")
                            if attempt < 2:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return []
                    else:
                        print(f"[DEBUG] {symbol}: CoinCap HTTP {resp.status}")
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return []

        except asyncio.TimeoutError:
            print(f"[DEBUG] {symbol}: CoinCap timeout попытка {attempt + 1}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            return []
        except Exception as e:
            print(f"[DEBUG] {symbol}: CoinCap error попытка {attempt + 1}: {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            return []

    print(f"[DEBUG] {symbol}: CoinCap все попытки исчерпаны")
    return []

@cache_with_ttl(ttl_seconds=60)
async def get_ohlc_coinpaprika_sync_async(symbol, interval="1h", limit=100):
    """
    Получить OHLC с Coinpaprika API (https://api.coinpaprika.com/)
    symbol: например, BTCUSDT -> btc-bitcoin
    interval: "1h", "4h" и т.д.
    limit: до 1000
    Возвращает список словарей с ключами: timestamp, open, high, low, close, volume
    """
    # Преобразуем символ для Coinpaprika
    symbol_map = {
        "BTCUSDT": "btc-bitcoin",
        "ETHUSDT": "eth-ethereum",
        "BNBUSDT": "bnb-binance-coin",
        "ADAUSDT": "ada-cardano",
        "SOLUSDT": "sol-solana",
        "DOTUSDT": "dot-polkadot",
        "DOGEUSDT": "doge-dogecoin",
        "AVAXUSDT": "avax-avalanche",
        "MATICUSDT": "matic-polygon",
        "LINKUSDT": "link-chainlink"
    }

    coin_id = symbol_map.get(symbol, symbol.lower().replace("usdt", ""))

    # URL для Coinpaprika
    url = f"https://api.coinpaprika.com/v1/coins/{coin_id}/ohlcv/historical"

    # Маппинг интервалов для Coinpaprika
    interval_map = {
        "1h": "1h",
        "4h": "4h",
        "1d": "1d"
    }

    coinpaprika_interval = interval_map.get(interval, "1h")
    params = {
        "quote": "usd",
        "interval": coinpaprika_interval
    }

    if not AIOHTTP_AVAILABLE:
        print("[DEBUG] Coinpaprika: aiohttp недоступен, пропуск провайдера")
        return []

    # Увеличиваем таймаут для стабильности
    timeout = aiohttp.ClientTimeout(total=30, connect=10)

    for attempt in range(3):  # 3 попытки
        try:
            print(f"[DEBUG] {symbol}: Coinpaprika попытка {attempt + 1}")
            connector = aiohttp.TCPConnector(ssl=False)  # Отключаем SSL проверку
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, params=params) as resp:
                    print(f"[DEBUG] {symbol}: Coinpaprika статус {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"[DEBUG] {symbol}: Coinpaprika размер данных {len(data) if data else 0}")

                        if data:
                            ohlc = [
                                {
                                    "timestamp": int(item["timestamp"]),
                                    "open": float(item["open"]),
                                    "high": float(item["high"]),
                                    "low": float(item["low"]),
                                    "close": float(item["close"]),
                                    "volume": float(item["volume"]),
                                }
                                for item in data[-limit:]  # Берем последние записи
                            ]
                            print(f"[DEBUG] {symbol}: Coinpaprika успешно получено {len(ohlc)} записей")
                            return ohlc
                        else:
                            print(f"[DEBUG] {symbol}: Coinpaprika пустой ответ")
                            if attempt < 2:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return []
                    else:
                        print(f"[DEBUG] {symbol}: Coinpaprika HTTP {resp.status}")
                        if attempt < 2:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return []

        except asyncio.TimeoutError:
            print(f"[DEBUG] {symbol}: Coinpaprika timeout попытка {attempt + 1}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            return []
        except Exception as e:
            print(f"[DEBUG] {symbol}: Coinpaprika error попытка {attempt + 1}: {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            return []

    print(f"[DEBUG] {symbol}: Coinpaprika все попытки исчерпаны")
    return []


if __name__ == "__main__":
    import datetime

    print("Тест получения последних свечей по DOGEUSDT:")
    print("Binance:")
    ohlc_binance = get_ohlc_binance_sync("DOGEUSDT", interval="1h", limit=3)
    for o in ohlc_binance:
        ts = o["timestamp"]
        print(f"timestamp={ts}, {datetime.datetime.fromtimestamp(ts/1000)} | close={o['close']}")
    print("Bybit:")
    ohlc_bybit = get_ohlc_bybit_sync("DOGEUSDT", interval="1h", limit=3)
    for o in ohlc_bybit:
        ts = o["timestamp"]
        print(f"timestamp={ts}, {datetime.datetime.fromtimestamp(ts/1000)} | close={o['close']}")
