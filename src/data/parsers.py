"""
Data parsing utilities for different API sources
"""

import re
import time
import logging
from typing import Dict, List, Any, Optional


def parse_market_cap_data(source_name: str, data: Dict[str, Any], symbol: str, base_symbol: str) -> Optional[Dict[str, Any]]:
    """Парсинг данных о капитализации"""
    try:
        if source_name == "CoinGecko":
            market_data = data.get("market_data", {})
            return {
                "market_cap": market_data.get("market_cap", {}).get("usd", 0),
                "volume_24h": market_data.get("total_volume", {}).get("usd", 0),
                "source": source_name
            }
        elif source_name == "CryptoCompare":
            raw_data = data.get("RAW", {})
            if base_symbol in raw_data and "USD" in raw_data[base_symbol]:
                usd_data = raw_data[base_symbol]["USD"]
                return {
                    "market_cap": usd_data.get("MKTCAP", 0),
                    "volume_24h": usd_data.get("TOTALVOLUME24H", 0),
                    "source": source_name
                }
        elif source_name == "CoinLore":
            tickers = data.get("data", [])
            for ticker in tickers:
                if ticker.get("symbol", "").upper() == base_symbol.upper():
                    market_cap = ticker.get("market_cap_usd", 0)
                    volume_24h = ticker.get("volume24", 0)
                    return {
                        "market_cap": float(market_cap) if market_cap is not None else 0.0,
                        "volume_24h": float(volume_24h) if volume_24h is not None else 0.0,
                        "source": source_name
                    }
        elif source_name == "CoinPaprika":
            currencies = data.get("currencies", [])
            for currency in currencies:
                if currency.get("symbol", "").upper() == base_symbol.upper():
                    currency_id = currency.get("id")
                    if currency_id:
                        # Получаем данные о тикере
                        # Здесь нужно будет добавить запрос к ticker API
                        # Пока возвращаем базовые данные
                        return {
                            "market_cap": 0,  # Будет заполнено после запроса к ticker
                            "volume_24h": 0,
                            "source": source_name
                        }
        elif source_name == "CoinCap":
            assets = data.get("data", [])
            for asset in assets:
                if asset.get("symbol", "").upper() == base_symbol.upper():
                    market_cap = asset.get("marketCapUsd", 0)
                    volume_24h = asset.get("volumeUsd24Hr", 0)
                    return {
                        "market_cap": float(market_cap) if market_cap is not None else 0.0,
                        "volume_24h": float(volume_24h) if volume_24h is not None else 0.0,
                        "source": source_name
                    }
        elif source_name == "CoinRanking":
            coins = data.get("data", {}).get("coins", [])
            for coin in coins:
                if coin.get("symbol", "").upper() == base_symbol.upper():
                    market_cap = coin.get("marketCap", 0)
                    volume_24h = coin.get("24hVolume", 0)
                    return {
                        "market_cap": float(market_cap) if market_cap is not None else 0.0,
                        "volume_24h": float(volume_24h) if volume_24h is not None else 0.0,
                        "source": source_name
                    }
        elif source_name == "CoinStats":
            coins = data.get("coins", [])
            for coin in coins:
                if coin.get("symbol", "").upper() == base_symbol.upper():
                    market_cap = coin.get("marketCap", 0)
                    volume_24h = coin.get("volume", 0)
                    return {
                        "market_cap": float(market_cap) if market_cap is not None else 0.0,
                        "volume_24h": float(volume_24h) if volume_24h is not None else 0.0,
                        "source": source_name
                    }
        elif source_name == "Binance":
            for ticker in data:
                if ticker.get("symbol") == symbol:
                    quote_volume = ticker.get("quoteVolume", 0)
                    volume = float(quote_volume) if quote_volume is not None else 0.0
                    # Примерная оценка market cap
                    estimated_market_cap = volume * 100
                    return {
                        "market_cap": estimated_market_cap,
                        "volume_24h": volume,
                        "source": source_name
                    }
        elif source_name == "CoinMarketCap":
            quote_data = data.get("data", {}).get(base_symbol, {}).get("quote", {}).get("USD", {})
            if quote_data:
                market_cap = quote_data.get("market_cap", 0)
                volume_24h = quote_data.get("volume_24h", 0)
                return {
                    "market_cap": float(market_cap) if market_cap is not None else 0.0,
                    "volume_24h": float(volume_24h) if volume_24h is not None else 0.0,
                    "source": source_name
                }
        elif source_name == "Messari":
            metrics = data.get("data", {})
            if metrics:
                market_cap = metrics.get("marketcap", {}).get("current_marketcap_usd", 0)
                volume_24h = metrics.get("market_data", {}).get("volume_usd", 0)
                return {
                    "market_cap": float(market_cap) if market_cap is not None else 0.0,
                    "volume_24h": float(volume_24h) if volume_24h is not None else 0.0,
                    "source": source_name
                }
    except (RuntimeError, OSError, ValueError) as e:
        logging.debug("[MarketCap] Ошибка парсинга %s: %s", source_name, e)

    return None


def parse_volume_data(source_name: str, data: Dict[str, Any], _symbol: str) -> Optional[float]:
    """Парсинг данных об объеме"""
    try:
        if source_name == "Binance":
            quote_vol = data.get("quoteVolume", 0)
            return float(quote_vol) if quote_vol is not None else 0.0
        elif source_name == "Bybit":
            result = data.get("result", {}).get("list", [])
            if result:
                turnover = result[0].get("turnover24h", 0)
                return float(turnover) if turnover is not None else 0.0
        elif source_name == "MEXC":
            quote_vol = data.get("quoteVolume", 0)
            return float(quote_vol) if quote_vol is not None else 0.0
        elif source_name == "OKX":
            result = data.get("data", [])
            if result:
                vol_ccy = result[0].get("volCcy24h", 0)
                return float(vol_ccy) if vol_ccy is not None else 0.0
        elif source_name == "KuCoin":
            vol = data.get("data", {}).get("vol", 0)
            return float(vol) if vol is not None else 0.0
        elif source_name == "Gate.io":
            result = data.get("data", [])
            if result:
                quote_vol = result[0].get("quote_volume", 0)
                return float(quote_vol) if quote_vol is not None else 0.0
        elif source_name == "Huobi":
            tick_data = data.get("tick", {})
            if tick_data:
                amount = tick_data.get("amount", 0)
                return float(amount) if amount is not None else 0.0
        elif source_name == "Coinbase":
            volume = data.get("volume", 0)
            return float(volume) if volume is not None else 0.0
        elif source_name == "Kraken":
            result = data.get("result", {})
            if result:
                # Kraken возвращает данные по парам в виде словаря
                for pair_data in result.values():
                    if isinstance(pair_data, dict) and "v" in pair_data:
                        volume_value = pair_data["v"][1] if len(pair_data["v"]) > 1 else 0
                        return float(volume_value) if volume_value is not None else 0.0
        elif source_name == "Bitfinex":
            if isinstance(data, list) and len(data) >= 8:
                volume = data[7]
                return float(volume) if volume is not None else 0.0
    except (RuntimeError, OSError, ValueError) as e:
        logging.debug("[Volume] Ошибка парсинга %s: %s", source_name, e)

    return None


def parse_price_data(source_name: str, data: Dict[str, Any], _symbol: str) -> Optional[float]:
    """Парсинг данных о цене"""
    try:
        if source_name == "Binance":
            price = data.get("price", 0)
            return float(price) if price is not None else 0.0
        elif source_name == "Bybit":
            result = data.get("result", {}).get("list", [])
            if result:
                last_price = result[0].get("lastPrice", 0)
                return float(last_price) if last_price is not None else 0.0
        elif source_name == "MEXC":
            price = data.get("price", 0)
            return float(price) if price is not None else 0.0
        elif source_name == "OKX":
            result = data.get("data", [])
            if result:
                last_price = result[0].get("last", 0)
                return float(last_price) if last_price is not None else 0.0
        elif source_name == "KuCoin":
            price = data.get("data", {}).get("price", 0)
            return float(price) if price is not None else 0.0
        elif source_name == "Gate.io":
            result = data.get("data", [])
            if result:
                last_price = result[0].get("last", 0)
                return float(last_price) if last_price is not None else 0.0
        elif source_name == "Huobi":
            tick_data = data.get("tick", {})
            if tick_data:
                close_price = tick_data.get("close", 0)
                return float(close_price) if close_price is not None else 0.0
        elif source_name == "Coinbase":
            price = data.get("price", 0)
            return float(price) if price is not None else 0.0
        elif source_name == "Kraken":
            result = data.get("result", {})
            if result:
                # Kraken возвращает данные по парам в виде словаря
                for pair_data in result.values():
                    if isinstance(pair_data, dict) and "c" in pair_data:
                        price_value = pair_data["c"][0] if len(pair_data["c"]) > 0 else 0
                        return float(price_value) if price_value is not None else 0.0
        elif source_name == "Bitfinex":
            if isinstance(data, list) and len(data) >= 6:
                price = data[6]
                return float(price) if price is not None else 0.0
    except (RuntimeError, OSError, ValueError) as e:
        logging.debug("[Price] Ошибка парсинга %s: %s", source_name, e)

    return None


def parse_news_data(source_name: str, content: str, _symbol: str) -> List[Dict[str, Any]]:
    """Парсинг новостей (RSS/HTML)"""
    try:
        # Простой парсинг RSS/HTML для извлечения заголовков и ссылок
        news_items = []

        # Паттерны для извлечения заголовков и ссылок
        title_patterns = [
            r'<title[^>]*>([^<]+)</title>',
            r'<h[1-6][^>]*>([^<]+)</h[1-6]>',
            r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
        ]

        for pattern in title_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 2:
                        link, title = match
                        if title and len(title.strip()) > 10:
                            news_items.append({
                                'title': title.strip(),
                                'link': link.strip(),
                                'source': source_name,
                                'timestamp': time.time()
                            })
                    else:
                        title = match[0] if match else match
                        if title and len(title.strip()) > 10:
                            news_items.append({
                                'title': title.strip(),
                                'link': '',
                                'source': source_name,
                                'timestamp': time.time()
                            })
                else:
                    if match and len(match.strip()) > 10:
                        news_items.append({
                            'title': match.strip(),
                            'link': '',
                            'source': source_name,
                            'timestamp': time.time()
                        })

        return news_items[:10]  # Ограничиваем количество

    except (RuntimeError, OSError, ValueError) as e:
        logging.debug("[News] Ошибка парсинга %s: %s", source_name, e)

    return []
