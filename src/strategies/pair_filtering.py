"""
Pair filtering and selection utilities
"""

import asyncio
import logging
import threading

import ccxt
import pandas as pd
import requests
import ta

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


from config import RISK_FILTERS

try:
    from src.utils.exchange_utils import is_valid_pair
except ImportError:
    try:
        from src.utils.exchange_utils import is_valid_pair
    except ImportError:
        # Fallback: простая проверка
        def is_valid_pair(symbol):
            return symbol and isinstance(symbol, str) and len(symbol) > 0


try:
    from src.data.market_cap import get_blacklisted_symbols, get_whitelisted_symbols
except ImportError:
    try:
        from src.utils.market_cap import get_blacklisted_symbols, get_whitelisted_symbols
    except ImportError:
        try:
            from market_cap import get_blacklisted_symbols, get_whitelisted_symbols
        except ImportError:
            # Fallback: пустые списки
            def get_blacklisted_symbols():
                return []

            def get_whitelisted_symbols():
                return []


async def get_top_usdt_pairs_by_volume(limit=20):
    """
    Gets top-N USDT pairs by trading volume from Binance (spot) via direct HTTP requests.
    """
    logging.info("🔍 Получаем топ-%d USDT пар по объему с Binance...", limit)

    # Cache for results (5 minutes)
    cache_key = f"top_pairs_{limit}"

    # Use cache manager
    try:
        from src.utils.cache_manager import (
            EXTERNAL_CACHE_AVAILABLE,
            CacheManager,
            ExternalCacheManager,
        )

        if EXTERNAL_CACHE_AVAILABLE:
            pairs_cache = ExternalCacheManager()
        else:
            # If module unavailable, create simple in-memory cache
            pairs_cache = CacheManager.get_pairs_cache()
            if not pairs_cache:
                pairs_cache = {}
                CacheManager.set_pairs_cache_value("_initialized", True)
    except ImportError:
        try:
            from cache_manager import EXTERNAL_CACHE_AVAILABLE, CacheManager, ExternalCacheManager

            if EXTERNAL_CACHE_AVAILABLE:
                pairs_cache = ExternalCacheManager()
            else:
                pairs_cache = CacheManager.get_pairs_cache()
                if not pairs_cache:
                    pairs_cache = {}
                    CacheManager.set_pairs_cache_value("_initialized", True)
        except ImportError:
            # Fallback: простой in-memory кэш
            pairs_cache = {}

    # Check cache
    cached_result = None
    if hasattr(pairs_cache, "get"):
        cached_result = pairs_cache.get(cache_key, max_age=300)  # 5 minutes
        if cached_result:
            logging.info("📦 Используем кэшированные данные для топ-%d пар", limit)
        else:
            logging.info("🔄 Кэш пуст, получаем свежие данные с Binance")
    elif cache_key in pairs_cache:
        cached_result = pairs_cache[cache_key]

    if cached_result is not None:
        logging.info("Используем кэшированные топ-%d монет", len(cached_result))
        return cached_result

    # Standard coin list in case of errors
    default_pairs = [
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "BNBUSDT",
        "XRPUSDT",
        "DOGEUSDT",
        "ADAUSDT",
        "AVAXUSDT",
        "LINKUSDT",
        "TONUSDT",
        "MATICUSDT",
        "DOTUSDT",
        "LTCUSDT",
        "UNIUSDT",
        "ATOMUSDT",
        "ETCUSDT",
        "FILUSDT",
        "NEARUSDT",
        "APTUSDT",
        "OPUSDT",
    ]

    try:
        exchange = ccxt.binance()
        # Use threading.Timer instead of signal for thread compatibility
        timeout_occurred = threading.Event()

        def timeout_handler():
            timeout_occurred.set()

        # Set 30 second timeout
        timer = threading.Timer(30.0, timeout_handler)
        timer.start()

        try:
            if timeout_occurred.is_set():
                raise TimeoutError("fetch_tickers timeout")
            tickers = exchange.fetch_tickers()
        finally:
            timer.cancel()  # Disable timeout

        usdt_pairs = {
            symbol: ticker for symbol, ticker in tickers.items() if symbol.endswith("/USDT")
        }

        # Filter out stablecoins and pairs with zero volume
        stablecoins = [
            "USDC/USDT",
            "TUSD/USDT",
            "FDUSD/USDT",
            "USDP/USDT",
            "AEUR/USDT",
            "CUSD/USDT",
        ]
        # 🔧 ИСПРАВЛЕНО: Снижен порог объема в два раза для получения большего количества монет
        min_volume_threshold = RISK_FILTERS.get("min_volume_24h", 50_000_000) // 2  # 15M вместо 30M

        filtered_pairs = {
            s: t
            for s, t in usdt_pairs.items()
            if s not in stablecoins
            and t.get("quoteVolume")
            and t["quoteVolume"] > min_volume_threshold  # Minimum volume threshold
        }

        # Sort by volume in USDT
        sorted_pairs = sorted(filtered_pairs.values(), key=lambda x: x["quoteVolume"], reverse=True)

        top_pairs = [
            pair["symbol"].replace("/", "") for pair in sorted_pairs[: limit * 2]
        ]  # Take more for filtering

        # Get whitelist and blacklist
        whitelisted_symbols = get_whitelisted_symbols()
        blacklisted_symbols = get_blacklisted_symbols()

        # Filter by whitelist (если он не пустой) и исключаем blacklist
        if whitelisted_symbols and len(whitelisted_symbols) > 0:
            # Если whitelist есть, используем только его
            whitelisted_pairs = [symbol for symbol in top_pairs if symbol in whitelisted_symbols]
            blacklisted_pairs = [symbol for symbol in top_pairs if symbol in blacklisted_symbols]
            logging.info(
                "📊 Монеты: %d в белом списке, %d в черном списке",
                len(whitelisted_pairs),
                len(blacklisted_pairs),
            )
            top_pairs = whitelisted_pairs[:limit]
            logging.info("✅ Используем только белый список: %d монет", len(top_pairs))
        else:
            # Если whitelist пустой, используем все пары кроме blacklist
            blacklisted_pairs = [symbol for symbol in top_pairs if symbol in blacklisted_symbols]
            filtered_pairs = [symbol for symbol in top_pairs if symbol not in blacklisted_symbols]
            logging.info(
                "📊 Whitelist пустой, используем все пары (исключая blacklist): %d в черном списке, %d доступно",
                len(blacklisted_pairs),
                len(filtered_pairs),
            )
            top_pairs = filtered_pairs[:limit]
            logging.info(
                "✅ Используем все доступные пары (кроме blacklist): %d монет", len(top_pairs)
            )

        # Save to cache
        if hasattr(pairs_cache, "set"):
            pairs_cache.set(cache_key, top_pairs)
        else:
            CacheManager.set_pairs_cache_value(cache_key, top_pairs)

        return top_pairs

    except (requests.exceptions.Timeout, TimeoutError, ccxt.RequestTimeout) as e:
        logging.warning("⚠️ Таймаут при получении топ монет с Binance: %s", e)
        logging.info("🔄 Пробуем получить данные с Bybit...")

        # Fallback #1: Пробуем Bybit
        try:
            exchange_bybit = ccxt.bybit()
            tickers_bybit = exchange_bybit.fetch_tickers()
            usdt_pairs_bybit = {
                symbol: ticker
                for symbol, ticker in tickers_bybit.items()
                if symbol.endswith("/USDT")
            }

            # Фильтруем стейблкоины и пары с нулевым объемом
            stablecoins = [
                "USDC/USDT",
                "TUSD/USDT",
                "FDUSD/USDT",
                "USDP/USDT",
                "AEUR/USDT",
                "CUSD/USDT",
            ]
            filtered_pairs_bybit = {
                s: t
                for s, t in usdt_pairs_bybit.items()
                if s not in stablecoins
                and t.get("quoteVolume")
                and t["quoteVolume"] > min_volume_threshold
            }

            sorted_pairs_bybit = sorted(
                filtered_pairs_bybit.values(), key=lambda x: x["quoteVolume"], reverse=True
            )
            top_pairs_bybit = [
                pair["symbol"].replace("/", "") for pair in sorted_pairs_bybit[: limit * 2]
            ]

            whitelisted_symbols = get_whitelisted_symbols()
            whitelisted_pairs_bybit = [
                symbol for symbol in top_pairs_bybit if symbol in whitelisted_symbols
            ]

            result = (
                whitelisted_pairs_bybit[:limit]
                if whitelisted_pairs_bybit
                else default_pairs[:limit]
            )

            if len(result) >= limit // 2:  # Если получили хотя бы половину - используем
                logging.info("✅ Используем данные с Bybit: %d монет", len(result))
                if hasattr(pairs_cache, "set"):
                    pairs_cache.set(cache_key, result)
                else:
                    CacheManager.set_pairs_cache_value(cache_key, result)
                return result
            else:
                raise Exception("Недостаточно данных с Bybit")

        except Exception as bybit_error:
            logging.error("❌ Bybit fallback не сработал: %s", bybit_error)

        # Fallback #2: Проверяем устаревший кэш (>5 мин, но <1 час)
        if hasattr(pairs_cache, "get"):
            old_cached_result = pairs_cache.get(cache_key, max_age=3600)  # 1 час
            if old_cached_result and len(old_cached_result) >= limit // 2:
                logging.warning(
                    "⚠️ Все источники недоступны, используем УСТАРЕВШИЙ КЭШ (возраст < 1 час)"
                )
                logging.warning("⚠️ ВНИМАНИЕ: Данные могут быть неактуальными!")
                return old_cached_result

        # Fallback #3: Возвращаем None для повторной попытки
        logging.error("❌ Все источники данных недоступны (Binance, Bybit)")
        logging.error("❌ Невозможно получить актуальный список монет")
        logging.error("❌ Кэш отсутствует или слишком старый")
        logging.info("⏳ Возвращаем None - система повторит попытку позже")
        return None  # Вернем None, система повторит попытку

    except requests.exceptions.RequestException as e:
        logging.error("❌ Ошибка сети при получении топ монет с Binance: %s", e)
        logging.info("⏳ Возвращаем None - система повторит попытку позже")
        return None

    except (ValueError, TypeError, KeyError) as e:
        logging.error("❌ Ошибка при получении топ монет: %s", e)
        logging.info("⏳ Возвращаем None - система повторит попытку позже")
        return None


@cache_with_ttl(ttl_seconds=0)  # Disable cache for testing
async def get_filtered_top_usdt_pairs(
    top_n=50, min_volatility=0.02, max_volatility=0.15, final_limit=10
):
    """
    [PiuX_Trade] Gets top-N coins by volume, filters them by trend and volatility,
    and returns top-X strongest.
    """
    logging.info("[PiuX_Trade] 1. Получаем топ-%d монет по объему...", top_n)
    top_pairs_unfiltered = await get_top_usdt_pairs_by_volume(limit=top_n)
    if not top_pairs_unfiltered:
        return []

    logging.info("[PiuX_Trade] 2. Фильтруем монеты по тренду и волатильности...")
    promising_coins = []
    for symbol in top_pairs_unfiltered:
        # Check pair validity
        if not is_valid_pair(symbol):
            logging.debug("[DEBUG] %s: пропускаем невалидную пару", symbol)
            continue

        try:
            # Load 4-hour candles for trend/volatility analysis
            from src.execution.exchange_base import get_ohlc_with_fallback

            ohlc = await get_ohlc_with_fallback(symbol, interval="4h", limit=51)
            if not ohlc or len(ohlc) < 51:
                logging.debug(
                    "[DEBUG] %s: недостаточно данных для анализа (len=%d)",
                    symbol,
                    len(ohlc) if ohlc else 0,
                )
                continue

            df = pd.DataFrame(ohlc)
            df["open_time"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("open_time")

            # Volatility filter (ATR as % of price)
            from src.signals.indicators import add_technical_indicators

            if "atr" not in df.columns or "ema20" not in df.columns or "ema50" not in df.columns:
                df = add_technical_indicators(df, ema_periods=[20, 50], atr_period=14)

            atr = df["atr"].iloc[-1]
            price = df["close"].iloc[-1]
            atr_percent = atr / price if price > 0 else 0
            if not min_volatility < atr_percent < max_volatility:
                logging.debug(
                    "[DEBUG] %s: не прошёл по ATR/price (atr_percent=%.4f)", symbol, atr_percent
                )
                continue

            # Trend filter (EMA20 > EMA50 on 4h)
            ema20 = df["ema20"].iloc[-1]
            ema50 = df["ema50"].iloc[-1]
            if ema20 > ema50:
                promising_coins.append(symbol)
                logging.debug(
                    "[DEBUG] %s: прошёл все фильтры (atr_percent=%.4f, ema20=%.4f, ema50=%.4f)",
                    symbol,
                    atr_percent,
                    ema20,
                    ema50,
                )
            else:
                logging.debug(
                    "[DEBUG] %s: не прошёл по тренду (ema20=%.4f, ema50=%.4f)", symbol, ema20, ema50
                )
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logging.warning("[PiuX_Trade][WARN] Ошибка при фильтрации %s: %s", symbol, e)
            continue

    logging.info(
        "[PiuX_Trade] Отобрано %d монет после фильтрации: %s", len(promising_coins), promising_coins
    )
    return promising_coins[:final_limit]


@cache_with_ttl(ttl_seconds=0)  # Disable cache for testing
async def get_filtered_top_usdt_pairs_optimized(
    top_n=50, min_volatility=0.02, max_volatility=0.15, final_limit=10
):
    """
    Optimized version with parallel OHLC requests
    """
    logging.info("[PiuX_Trade] 1. Получаем топ-%d монет по объему...", top_n)
    top_pairs_unfiltered = await get_top_usdt_pairs_by_volume(limit=top_n)
    if not top_pairs_unfiltered:
        return []

    # Filter invalid pairs
    top_pairs_unfiltered = [s for s in top_pairs_unfiltered if is_valid_pair(s)]

    logging.info("[PiuX_Trade] 2. Параллельно получаем OHLC для всех монет...")

    async def fetch_ohlc_for_symbol(symbol):
        try:
            from src.execution.exchange_base import get_ohlc_with_fallback

            ohlc = await get_ohlc_with_fallback(symbol, interval="4h", limit=51)
            return symbol, ohlc
        except Exception as e:
            logging.warning("[PiuX_Trade][WARN] Ошибка получения OHLC для %s: %s", symbol, e)
            return symbol, None

    # Parallel OHLC requests
    tasks = [fetch_ohlc_for_symbol(symbol) for symbol in top_pairs_unfiltered]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    logging.info("[PiuX_Trade] 3. Фильтруем монеты по тренду и волатильности...")
    promising_coins = []

    for symbol, ohlc in results:
        if not ohlc or len(ohlc) < 51:
            logging.debug("[DEBUG] %s: недостаточно данных для анализа", symbol)
            continue

        try:
            df = pd.DataFrame(ohlc)
            df["open_time"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("open_time")

            # Volatility filter (ATR as % of price)
            from src.signals.indicators import add_technical_indicators

            df = add_technical_indicators(df, ema_periods=[20, 50], atr_period=14)

            atr = df["atr"].iloc[-1]
            price = df["close"].iloc[-1]
            atr_percent = atr / price if price > 0 else 0
            if not min_volatility < atr_percent < max_volatility:
                logging.debug(
                    "[DEBUG] %s: не прошёл по ATR/price (atr_percent=%.4f)", symbol, atr_percent
                )
                continue

            # Trend filter (EMA20 > EMA50 on 4h)
            ema20 = df["ema20"].iloc[-1]
            ema50 = df["ema50"].iloc[-1]
            if ema20 > ema50:
                promising_coins.append(symbol)
                logging.debug(
                    "[DEBUG] %s: прошёл все фильтры (atr_percent=%.4f, ema20=%.4f, ema50=%.4f)",
                    symbol,
                    atr_percent,
                    ema20,
                    ema50,
                )
            else:
                logging.debug(
                    "[DEBUG] %s: не прошёл по тренду (ema20=%.4f, ema50=%.4f)", symbol, ema20, ema50
                )
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logging.warning("[PiuX_Trade][WARN] Ошибка при фильтрации %s: %s", symbol, e)
            continue

    logging.info(
        "[PiuX_Trade] Отобрано %d монет после фильтрации: %s", len(promising_coins), promising_coins
    )
    return promising_coins[:final_limit]


@cache_with_ttl(ttl_seconds=300)  # Increase TTL to 5 minutes
async def get_filtered_top_usdt_pairs_async(
    top_n=100, min_volatility=0.02, max_volatility=0.15, final_limit=20
):
    # 1. Get top-N coins by volume (synchronously, for simplicity)
    symbols = await get_top_usdt_pairs_by_volume(limit=top_n)

    # Filter invalid pairs
    symbols = [s for s in symbols if is_valid_pair(s)]

    # 2. Asynchronously collect OHLC for all coins
    async def fetch_ohlc(symbol):
        try:
            from src.execution.exchange_base import get_ohlc_with_fallback

            ohlc = await get_ohlc_with_fallback(symbol, interval="1h", limit=48)
            return symbol, ohlc
        except Exception:
            return symbol, []

    tasks = [fetch_ohlc(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks)

    # 3. Volatility filtering
    filtered = []
    for symbol, ohlc in results:
        if not ohlc or len(ohlc) < 20:
            continue
        closes = [x["close"] for x in ohlc]
        if len(closes) < 20:
            continue
        min_c = min(closes)
        max_c = max(closes)
        volatility = (max_c - min_c) / min_c if min_c > 0 else 0
        if min_volatility <= volatility <= max_volatility:
            filtered.append(symbol)
        if len(filtered) >= final_limit:
            break
    return filtered


@cache_with_ttl(ttl_seconds=0)  # Disable cache for testing
async def get_filtered_top_usdt_pairs_fast(
    top_n=500, final_limit=200
):  # 🔧 УВЕЛИЧЕНО для всех монет
    """
    Fast version without OHLC analysis - only volume filtering
    """
    logging.info("[PiuX_Trade] Быстрая фильтрация топ-%d монет (лимит: %d)...", top_n, final_limit)

    try:
        # 🔧 ИСПРАВЛЕНО: Используем прямое получение с Binance без жесткого порога объема
        # для быстрой фильтрации берем топ-N по объему, а не фильтруем по min_volume_24h
        import ccxt

        exchange = ccxt.binance()
        tickers = exchange.fetch_tickers()

        # Получаем все USDT пары
        usdt_pairs = {
            symbol: ticker for symbol, ticker in tickers.items() if symbol.endswith("/USDT")
        }

        # Фильтруем стейблкоины
        stablecoins = [
            "USDC/USDT",
            "TUSD/USDT",
            "FDUSD/USDT",
            "USDP/USDT",
            "AEUR/USDT",
            "CUSD/USDT",
        ]

        filtered_pairs = {
            s: t
            for s, t in usdt_pairs.items()
            if s not in stablecoins
            and t.get("quoteVolume")
            and t["quoteVolume"] > 0  # Только ненулевой объем, без жесткого порога
        }

        # Сортируем по объему и берем топ-N
        sorted_pairs = sorted(filtered_pairs.values(), key=lambda x: x["quoteVolume"], reverse=True)
        top_pairs = [
            pair["symbol"].replace("/", "") for pair in sorted_pairs[: top_n * 2]
        ]  # Берем больше для дальнейшей фильтрации

        # Filter invalid pairs
        filtered_pairs_list = [symbol for symbol in top_pairs if is_valid_pair(symbol)]

        # Filter stablecoins (дополнительная проверка)
        from config import STABLECOIN_SYMBOLS

        filtered_pairs_list = [
            symbol for symbol in filtered_pairs_list if symbol not in STABLECOIN_SYMBOLS
        ]
        logging.info("После фильтрации стейблкоинов: %d пар", len(filtered_pairs_list))

        result = filtered_pairs_list[:final_limit]
        logging.info(
            "Быстрая фильтрация: отобрано %d пар из %d полученных (всего USDT пар: %d)",
            len(result),
            len(top_pairs),
            len(usdt_pairs),
        )
        return result

    except (ValueError, TypeError, KeyError, Exception) as e:
        logging.error("Ошибка в get_filtered_top_usdt_pairs_fast: %s", e)
        # Fallback на старую функцию
        try:
            top_pairs = await get_top_usdt_pairs_by_volume(limit=min(top_n, 500))
            if top_pairs:
                from config import STABLECOIN_SYMBOLS

                filtered = [
                    s for s in top_pairs if s not in STABLECOIN_SYMBOLS and is_valid_pair(s)
                ]
                return filtered[:final_limit]
        except Exception as fallback_error:
            logging.error("Fallback также не сработал: %s", fallback_error)
        return []
