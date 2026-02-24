"""
Market capitalization filtering and management
"""

import asyncio
import logging
import sqlite3

import requests

from src.data.sources_hub import SourcesHub


async def get_market_cap_data(symbols):
    """
    Gets market cap data for list of symbols using SourcesHub.

    Args:
        symbols (list): List of symbols (e.g., ['BTCUSDT', 'ETHUSDT'])

    Returns:
        dict: Dictionary {symbol: market_cap_usd}
    """
    hub = SourcesHub()
    market_caps = {}

    # Ограничиваем количество одновременных запросов
    semaphore = asyncio.Semaphore(5)

    async def fetch_one(symbol):
        async with semaphore:
            try:
                mc_data = await hub.get_market_cap_data(symbol)
                if mc_data and mc_data.get("market_cap", 0) > 0:
                    return symbol, mc_data["market_cap"]
            except Exception as e:
                logging.debug("Ошибка получения капы для %s через Hub: %s", symbol, e)
            return symbol, 0

    tasks = [fetch_one(s) for s in symbols]
    results = await asyncio.gather(*tasks)

    for symbol, mc in results:
        if mc > 0:
            market_caps[symbol] = mc

    logging.info(
        "Получены данные капитализации для %d/%d монет через SourcesHub",
        len(market_caps),
        len(symbols),
    )
    return market_caps


def get_whitelisted_symbols():
    """
    Gets whitelist of coins from special whitelist table
    """
    try:
        conn = sqlite3.connect("trading.db")
        cursor = conn.cursor()

        # Get symbols from whitelist
        cursor.execute("SELECT symbol FROM whitelist WHERE status = 'active'")
        whitelisted = [row[0] for row in cursor.fetchall()]

        conn.close()

        if whitelisted:
            logging.info(
                "✅ Белый список содержит %d монет: %s", len(whitelisted), whitelisted[:10]
            )

        return set(whitelisted)
    except (sqlite3.Error, ValueError, TypeError, KeyError) as e:
        logging.warning("Ошибка получения белого списка: %s", e)
        return set()


def get_blacklisted_symbols():
    """
    Gets blacklist of coins from special blacklist table
    """
    try:
        conn = sqlite3.connect("trading.db")
        cursor = conn.cursor()

        # Get symbols from blacklist
        cursor.execute("SELECT symbol FROM blacklist WHERE status = 'active'")
        blacklisted = [row[0] for row in cursor.fetchall()]

        conn.close()

        if blacklisted:
            logging.info(
                "🚫 Черный список содержит %d монет: %s", len(blacklisted), blacklisted[:10]
            )

        return set(blacklisted)
    except (sqlite3.Error, ValueError, TypeError, KeyError) as e:
        logging.warning("Ошибка получения черного списка: %s", e)
        return set()


async def initialize_market_cap_filtering():
    """
    Initialize market cap filtering on system startup
    """
    logging.info("🔄 Инициализация фильтрации по капитализации...")

    try:
        # Get all available coins
        all_symbols = await get_all_available_symbols()
        if not all_symbols:
            logging.warning("Не удалось получить список монет для фильтрации")
            return

        logging.info("📊 Получено %d монет для проверки капитализации", len(all_symbols))

        # Get market cap data
        market_caps = await get_market_cap_data(all_symbols)
        min_market_cap = 100_000_000  # 100M USD (только качественные проекты)

        # Split into whitelist, blacklist and pending check
        whitelist = []
        blacklist = []
        pending_check = []

        for symbol in all_symbols:
            market_cap = market_caps.get(symbol, 0)
            if market_cap == 0:
                pending_check.append(symbol)
                logging.debug("⏳ %s: данные не получены -> список на проверке", symbol)
            elif market_cap >= min_market_cap:
                whitelist.append(symbol)
                logging.debug("✅ %s: %.1fM USD -> белый список", symbol, market_cap / 1_000_000)
            else:
                blacklist.append(symbol)
                logging.debug("❌ %s: %.1fM USD -> черный список", symbol, market_cap / 1_000_000)

        # Save to database
        conn = sqlite3.connect("trading.db")
        cursor = conn.cursor()

        # Create tables if they don't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                symbol TEXT PRIMARY KEY,
                market_cap REAL,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                symbol TEXT PRIMARY KEY,
                market_cap REAL,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_check (
                symbol TEXT PRIMARY KEY,
                attempts INTEGER DEFAULT 1,
                last_check TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)

        # Clear old data
        cursor.execute("DELETE FROM whitelist")
        cursor.execute("DELETE FROM blacklist")
        cursor.execute("DELETE FROM pending_check")

        # Add new data
        for symbol in whitelist:
            market_cap = market_caps.get(symbol, 0)
            cursor.execute(
                """
                INSERT INTO whitelist (symbol, market_cap) VALUES (?, ?)
            """,
                (symbol, market_cap),
            )

        for symbol in blacklist:
            market_cap = market_caps.get(symbol, 0)
            cursor.execute(
                """
                INSERT INTO blacklist (symbol, market_cap) VALUES (?, ?)
            """,
                (symbol, market_cap),
            )

        for symbol in pending_check:
            cursor.execute(
                """
                INSERT INTO pending_check (symbol) VALUES (?)
            """,
                (symbol,),
            )

        conn.commit()
        conn.close()

        logging.info(
            "✅ Инициализация завершена: %d в белом списке, %d в черном списке, %d на проверке",
            len(whitelist),
            len(blacklist),
            len(pending_check),
        )

    except (sqlite3.Error, ValueError, TypeError, KeyError) as e:
        logging.error("Ошибка инициализации фильтрации: %s", e)


async def get_all_available_symbols():
    """
    Gets all available symbols for filtering
    """
    try:
        # Get top coins by volume directly from Binance API
        url = "https://api.binance.com/api/v3/ticker/24hr"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            tickers = response.json()
            volume_data = {}

            for ticker in tickers:
                if ticker["symbol"].endswith("USDT"):
                    volume_data[ticker["symbol"]] = float(ticker["quoteVolume"])

            # Sort by volume and take top 300
            sorted_pairs = sorted(volume_data.items(), key=lambda x: x[1], reverse=True)
            top_symbols = [pair[0] for pair in sorted_pairs[:300]]

            logging.info("Получено %d символов для фильтрации (топ‑300)", len(top_symbols))
            return top_symbols
        else:
            logging.error("Ошибка получения данных с Binance: статус %d", response.status_code)
            return []

    except (requests.exceptions.RequestException, ValueError, TypeError, KeyError) as e:
        logging.error("Ошибка получения символов: %s", e)
        return []
