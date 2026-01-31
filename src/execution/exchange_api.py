# -*- coding: utf-8 -*-
"""
Main exchange API module - imports from modular structure
"""
# Import all exchange APIs
from exchanges import BinanceAPI, BybitAPI, MEXCAPI, BitgetAPI

# Import utility functions
try:
    from src.utils.exchange_utils import (
        get_symbol_precision,
        get_full_price_format,
        get_price_precision_from_tick,
        is_valid_pair,
        INVALID_PAIRS
    )
except ImportError:
    # Заглушки
    def get_symbol_precision(*args, **kwargs):
        return 8
    def get_full_price_format(*args, **kwargs):
        return "0.00000000"
    def get_price_precision_from_tick(*args, **kwargs):
        return 8
    def is_valid_pair(*args, **kwargs):
        return True
    INVALID_PAIRS = set()

# Import cache management
try:
    from src.utils.cache_manager import (
        CacheManager,
        clear_symbol_info_cache,
        get_dynamic_price_precision,
        get_symbol_info
    )
except ImportError:
    # Заглушки
    class CacheManager:
        pass
    def clear_symbol_info_cache():
        pass
    def get_dynamic_price_precision(*args, **kwargs):
        return 8
    def get_symbol_info(*args, **kwargs):
        return {}

# Import market cap functions
try:
    from src.data.market_cap import (
        get_market_cap_data,
        get_market_cap_fallback_sources,
        get_whitelisted_symbols,
        get_blacklisted_symbols,
        initialize_market_cap_filtering,
        get_all_available_symbols
    )
except ImportError:
    # Заглушки
    def get_market_cap_data(*args, **kwargs):
        return {}
    def get_market_cap_fallback_sources(*args, **kwargs):
        return []
    def get_whitelisted_symbols(*args, **kwargs):
        return []
    def get_blacklisted_symbols(*args, **kwargs):
        return []
    async def initialize_market_cap_filtering(*args, **kwargs):
        pass
    def get_all_available_symbols(*args, **kwargs):
        return []

# Import pair filtering
try:
    from pair_filtering import (
        get_top_usdt_pairs_by_volume,
        get_filtered_top_usdt_pairs,
        get_filtered_top_usdt_pairs_optimized,
        get_filtered_top_usdt_pairs_async,
        get_filtered_top_usdt_pairs_fast
    )
except ImportError:
    try:
        from src.filters.pair_filtering import (
            get_top_usdt_pairs_by_volume,
            get_filtered_top_usdt_pairs,
            get_filtered_top_usdt_pairs_optimized,
            get_filtered_top_usdt_pairs_async,
            get_filtered_top_usdt_pairs_fast
        )
    except ImportError:
        # Заглушки
        def get_top_usdt_pairs_by_volume(*args, **kwargs):
            return []
        def get_filtered_top_usdt_pairs(*args, **kwargs):
            return []
        def get_filtered_top_usdt_pairs_optimized(*args, **kwargs):
            return []
        def get_filtered_top_usdt_pairs_async(*args, **kwargs):
            return []
        def get_filtered_top_usdt_pairs_fast(*args, **kwargs):
            return []

# Import base functionality
from src.execution.exchange_base import (
    ExchangeAPI,
    cache_prices,
    get_ohlc_with_fallback
)

# Import improved price API
try:
    from src.data.price_api import get_current_price_robust, get_prices_bulk
except ImportError:
    # Fallback if improved_price_api is not available
    def get_current_price_robust(symbol, max_retries=3):
        return None
    def get_prices_bulk(symbols, max_retries=3):
        return {}

# Import additional required modules
import asyncio
import sqlite3
import logging
import requests

# Additional functions that need to be implemented
async def check_pending_symbols():
    """
    Проверка монет из списка на проверке - получаем данные и распределяем по спискам
    """
    logging.info("🔄 Проверка монет из списка на проверке...")

    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()

        # Получаем все символы из списка на проверке
        cursor.execute("SELECT symbol FROM pending_check WHERE status = 'pending'")
        pending_symbols = [row[0] for row in cursor.fetchall()]

        if not pending_symbols:
            logging.info("Список на проверке пуст")
            conn.close()
            return

        logging.info("📊 Проверяем %d монет из списка на проверке", len(pending_symbols))

        # Получаем актуальные данные капитализации с более агрессивной стратегией
        market_caps = await get_market_cap_data_aggressive(pending_symbols)
        min_market_cap = 50_000_000  # 50M USD
        # Доп. эвристика: 24h Binance quote volume как временная замена капы
        volumes = {}
        try:
            volumes = _get_binance_quote_volumes(pending_symbols)
        except (requests.RequestException, ValueError, TypeError):
            volumes = {}

        moved_to_whitelist = []
        moved_to_blacklist = []
        still_pending = []

        for symbol in pending_symbols:
            market_cap = market_caps.get(symbol, 0)

            if market_cap == 0:
                # Попробуем классифицировать по 24h quote volume
                vol = float(volumes.get(symbol, 0) or 0)
                if vol >= 50_000_000:
                    # Проверяем, не существует ли уже символ в whitelist
                    cursor.execute("SELECT symbol FROM whitelist WHERE symbol = ?", (symbol,))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO whitelist (symbol, market_cap) VALUES (?, ?)
                        """, (symbol, 0))
                        moved_to_whitelist.append(symbol)
                        logging.info("✅ %s: 24h volume %.1fM USD -> белый список", symbol, vol/1_000_000)
                    else:
                        logging.debug("⏭️ %s: уже в белом списке, пропускаем", symbol)
                    cursor.execute("DELETE FROM pending_check WHERE symbol = ?", (symbol,))
                else:
                    # Все еще нет капы — инкремент попыток; при 3+ попытках и низком объеме — в черный
                    cursor.execute("SELECT attempts FROM pending_check WHERE symbol = ?", (symbol,))
                    row = cursor.fetchone()
                    attempts = int(row[0]) if row else 0
                    if vol < 25_000_000 and attempts >= 3:
                        # Проверяем, не существует ли уже символ в blacklist
                        cursor.execute("SELECT symbol FROM blacklist WHERE symbol = ?", (symbol,))
                        if not cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO blacklist (symbol, market_cap) VALUES (?, ?)
                            """, (symbol, 0))
                            moved_to_blacklist.append(symbol)
                            logging.info("❌ %s: нет капы, 24h volume %.1fM, attempts=%d -> черный список", symbol, vol/1_000_000, attempts)
                        else:
                            logging.debug("⏭️ %s: уже в черном списке, пропускаем", symbol)
                        cursor.execute("DELETE FROM pending_check WHERE symbol = ?", (symbol,))
                    else:
                        cursor.execute("""
                            UPDATE pending_check
                            SET attempts = attempts + 1, last_check = CURRENT_TIMESTAMP
                            WHERE symbol = ?
                        """, (symbol,))
                        still_pending.append(symbol)
                        logging.debug("⏳ %s: данных о капе нет (vol=%.1fM), оставляем pending", symbol, vol/1_000_000)
            elif market_cap >= min_market_cap:
                # Переводим в белый список
                # Проверяем, не существует ли уже символ в whitelist
                cursor.execute("SELECT symbol FROM whitelist WHERE symbol = ?", (symbol,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO whitelist (symbol, market_cap) VALUES (?, ?)
                    """, (symbol, market_cap))
                    moved_to_whitelist.append(symbol)
                    logging.info("✅ %s: %.1fM USD -> переводим в белый список", symbol, market_cap/1_000_000)
                else:
                    logging.debug("⏭️ %s: уже в белом списке, пропускаем", symbol)
                cursor.execute("DELETE FROM pending_check WHERE symbol = ?", (symbol,))
            else:
                # Переводим в черный список
                # Проверяем, не существует ли уже символ в blacklist
                cursor.execute("SELECT symbol FROM blacklist WHERE symbol = ?", (symbol,))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO blacklist (symbol, market_cap) VALUES (?, ?)
                    """, (symbol, market_cap))
                    moved_to_blacklist.append(symbol)
                    logging.info("❌ %s: %.1fM USD -> переводим в черный список", symbol, market_cap/1_000_000)
                else:
                    logging.debug("⏭️ %s: уже в черном списке, пропускаем", symbol)
                cursor.execute("DELETE FROM pending_check WHERE symbol = ?", (symbol,))

        conn.commit()
        conn.close()

        logging.info("✅ Проверка завершена: %d в белый список, %d в черный список, %d остались на проверке",
                   len(moved_to_whitelist), len(moved_to_blacklist), len(still_pending))

    except (sqlite3.Error, ValueError, TypeError, KeyError) as e:
        logging.error("Ошибка проверки монет из списка на проверке: %s", e)

def _get_binance_quote_volumes(symbols):
    """Возвращает словарь {symbol: quoteVolume_usd} по данным Binance 24hr ticker.
    Используется как эвристика, когда капа недоступна.
    """
    url = "https://api.binance.com/api/v3/ticker/24hr"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    tickers = resp.json()
    vol_map = {}
    wanted = set(symbols)
    for t in tickers:
        sym = t.get('symbol')
        if sym in wanted:
            try:
                vol_map[sym] = float(t.get('quoteVolume') or 0)
            except (TypeError, ValueError):
                pass
    return vol_map

async def weekly_blacklist_check():
    """
    Еженедельная проверка черного списка - переводим в белый список тех, кто превысил 150M
    """
    logging.info("🔄 Еженедельная проверка черного списка...")

    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()

        # Получаем все символы из черного списка
        cursor.execute("SELECT symbol FROM blacklist WHERE status = 'active'")
        blacklisted_symbols = [row[0] for row in cursor.fetchall()]

        if not blacklisted_symbols:
            logging.info("Черный список пуст")
            conn.close()
            return

        logging.info("📊 Проверяем %d монет из черного списка", len(blacklisted_symbols))

        # Получаем актуальные данные капитализации с агрессивной стратегией
        market_caps = await get_market_cap_data_aggressive(blacklisted_symbols)
        min_market_cap = 50_000_000  # 50M USD

        promoted = []
        for symbol in blacklisted_symbols:
            market_cap = market_caps.get(symbol, 0)
            if market_cap >= min_market_cap:
                promoted.append(symbol)
                logging.info("⬆️ %s: %.1fM USD -> переводим в белый список", symbol, market_cap/1_000_000)

        # Переводим в белый список
        for symbol in promoted:
            # Получаем данные из черного списка
            cursor.execute("SELECT market_cap FROM blacklist WHERE symbol = ?", (symbol,))
            result = cursor.fetchone()
            market_cap = result[0] if result else 0

            # Добавляем в белый список
            cursor.execute("""
                INSERT OR REPLACE INTO whitelist (symbol, market_cap) VALUES (?, ?)
            """, (symbol, market_cap))

            # Удаляем из черного списка
            cursor.execute("DELETE FROM blacklist WHERE symbol = ?", (symbol,))

        conn.commit()
        conn.close()

        if promoted:
            logging.info("✅ Переведено в белый список: %d монет", len(promoted))
        else:
            logging.info("ℹ️ Никто не переведен в белый список")

    except (sqlite3.Error, ValueError, TypeError, KeyError) as e:
        logging.error("Ошибка еженедельной проверки черного списка: %s", e)

async def weekly_whitelist_check():
    """
    Еженедельная проверка белого списка - переводим в черный список тех, кто просел ниже 150M
    """
    logging.info("🔄 Еженедельная проверка белого списка...")

    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()

        # Получаем все символы из белого списка
        cursor.execute("SELECT symbol FROM whitelist WHERE status = 'active'")
        whitelisted_symbols = [row[0] for row in cursor.fetchall()]

        if not whitelisted_symbols:
            logging.info("Белый список пуст")
            conn.close()
            return

        logging.info("📊 Проверяем %d монет из белого списка", len(whitelisted_symbols))

        # Получаем актуальные данные капитализации с агрессивной стратегией
        market_caps = await get_market_cap_data_aggressive(whitelisted_symbols)
        min_market_cap = 50_000_000  # 50M USD

        demoted = []
        for symbol in whitelisted_symbols:
            market_cap = market_caps.get(symbol, 0)
            if market_cap < min_market_cap:
                demoted.append(symbol)
                logging.info("⬇️ %s: %.1fM USD -> переводим в черный список", symbol, market_cap/1_000_000)

        # Переводим в черный список
        for symbol in demoted:
            # Получаем данные из белого списка
            cursor.execute("SELECT market_cap FROM whitelist WHERE symbol = ?", (symbol,))
            result = cursor.fetchone()
            market_cap = result[0] if result else 0

            # Добавляем в черный список
            cursor.execute("""
                INSERT OR REPLACE INTO blacklist (symbol, market_cap) VALUES (?, ?)
            """, (symbol, market_cap))

            # Удаляем из белого списка
            cursor.execute("DELETE FROM whitelist WHERE symbol = ?", (symbol,))

        conn.commit()
        conn.close()

        if demoted:
            logging.info("✅ Переведено в черный список: %d монет", len(demoted))
        else:
            logging.info("ℹ️ Никто не переведен в черный список")

    except (sqlite3.Error, ValueError, TypeError, KeyError) as e:
        logging.error("Ошибка еженедельной проверки белого списка: %s", e)

async def get_market_cap_data_aggressive(symbols):
    """
    Агрессивная стратегия получения данных о капитализации
    Пробует все источники последовательно для каждой монеты
    """
    market_caps = {}

    logging.info("🚀 Агрессивная проверка капитализации для %d монет", len(symbols))

    # Разбиваем на группы и сначала пытаемся получить капу пакетно (снижает 429)
    batch_size = 25
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        logging.info("📊 Обрабатываем группу %d-%d из %d", i+1, min(i+batch_size, len(symbols)), len(symbols))

        # 1) Пакетная попытка через CoinGecko
        try:
            bulk = await get_market_cap_data(batch)
            if isinstance(bulk, dict):
                for s, v in bulk.items():
                    if v and v > 0:
                        market_caps[s] = float(v)
        except (ValueError, TypeError):
            pass

        # 2) Резервные источники для недостающих в батче
        remaining = [s for s in batch if s not in market_caps]
        if remaining:
            try:
                fb = await get_market_cap_fallback_sources(remaining)
                if isinstance(fb, dict):
                    for s, v in fb.items():
                        if v and v > 0:
                            market_caps[s] = float(v)
            except (ValueError, TypeError):
                pass

        # 3) Последний шанс — поштучно (дорого, используем только для оставшихся)
        tail = [s for s in batch if s not in market_caps]
        for symbol in tail:
            mc = await try_all_sources_for_symbol(symbol)
            if mc > 0:
                market_caps[symbol] = mc

        # Небольшая задержка между группами, чтобы не усугублять rate-limit
        await asyncio.sleep(1)

    logging.info(
        "🎯 Агрессивная проверка завершена: получены данные для %d из %d монет",
        len(market_caps), len(symbols),
    )
    return market_caps

async def try_all_sources_for_symbol(symbol):
    """
    Пробует все источники для получения данных о капитализации для одного символа
    """
    logging.debug("Проверяем источники для символа: %s", symbol)
    # 1) Попытка через основной батч‑метод CoinGecko (на один символ)
    try:
        caps = await get_market_cap_data([symbol])
        mc = float(caps.get(symbol, 0) or 0)
        if mc > 0:
            return mc
    except (ValueError, TypeError):
        pass

    # 2) Фолбэк через резервные источники (CryptoCompare и др.)
    try:
        caps_fb = await get_market_cap_fallback_sources([symbol])
        mc2 = float(caps_fb.get(symbol, 0) or 0)
        if mc2 > 0:
            return mc2
    except (ValueError, TypeError):
        pass

    # Нет данных
    return 0

# Re-export everything for backward compatibility
__all__ = [
    # Exchange APIs
    'BinanceAPI', 'BybitAPI', 'MEXCAPI', 'BitgetAPI',

    # Utility functions
    'get_symbol_precision', 'get_full_price_format', 'get_price_precision_from_tick',
    'is_valid_pair', 'INVALID_PAIRS',

    # Cache management
    'CacheManager', 'clear_symbol_info_cache', 'get_dynamic_price_precision', 'get_symbol_info',

    # Market cap
    'get_market_cap_data', 'get_market_cap_fallback_sources', 'get_whitelisted_symbols',
    'get_blacklisted_symbols', 'initialize_market_cap_filtering', 'get_all_available_symbols',

    # Pair filtering
    'get_top_usdt_pairs_by_volume', 'get_filtered_top_usdt_pairs',
    'get_filtered_top_usdt_pairs_optimized', 'get_filtered_top_usdt_pairs_async',
    'get_filtered_top_usdt_pairs_fast',

    # Base functionality
    'ExchangeAPI', 'cache_prices', 'get_ohlc_with_fallback',

    # Additional functions
    'check_pending_symbols', 'weekly_blacklist_check', 'weekly_whitelist_check',
    'get_market_cap_data_aggressive', 'try_all_sources_for_symbol'
]
