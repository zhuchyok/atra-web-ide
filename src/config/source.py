"""
Source configuration and data structures
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class SourceConfig:
    """Конфигурация источника данных"""
    name: str
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    timeout: int = 15
    priority: int = 1
    enabled: bool = True
    circuit_breaker_threshold: int = 5  # Количество ошибок до блокировки
    circuit_breaker_timeout: int = 300  # Время блокировки в секундах


def get_sources_config():
    """Returns the configuration for all data sources"""
    return {
        'market_cap': [
            SourceConfig(
                "CoinGecko",
                "https://api.coingecko.com/api/v3/coins/{symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=1
            ),
            SourceConfig(
                "CryptoCompare",
                "https://min-api.cryptocompare.com/data/pricemultifull?fsyms={base}&tsyms=USD",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=2
            ),
            SourceConfig(
                "CoinLore",
                "https://api.coinlore.net/api/tickers/",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=3
            ),
            SourceConfig(
                "CoinPaprika",
                "https://api.coinpaprika.com/v1/search?q={base}&c=currencies",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=4
            ),
            SourceConfig(
                "CoinRanking",
                "https://api.coinranking.com/v2/coins",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=6
            ),
            SourceConfig(
                "CoinStats",
                "https://api.coinstats.app/public/v1/coins",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=7
            ),
            SourceConfig(
                "Binance",
                "https://api.binance.com/api/v3/ticker/24hr",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=8
            ),
            SourceConfig(
                "CoinMarketCap",
                "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?symbol={base}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)", "X-CMC_PRO_API_KEY": "demo"},
                priority=9
            ),
            SourceConfig(
                "Messari",
                "https://data.messari.io/api/v1/assets/{base}/metrics",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=10
            ),
        ],

        'volume': [
            SourceConfig(
                "Binance",
                "https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=1
            ),
            SourceConfig(
                "Bybit",
                "https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=2
            ),
            SourceConfig(
                "MEXC",
                "https://api.mexc.com/api/v3/ticker/24hr?symbol={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=3
            ),
            SourceConfig(
                "OKX",
                "https://www.okx.com/api/v5/market/ticker?instId={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=4
            ),
            SourceConfig(
                "KuCoin",
                "https://api.kucoin.com/api/v1/market/stats?symbol={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=5
            ),
            SourceConfig(
                "Gate.io",
                "https://api.gateio.ws/api/v4/spot/tickers?currency_pair={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=6
            ),
            SourceConfig(
                "Huobi",
                "https://api.huobi.pro/market/detail/merged?symbol={symbol_lower}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=7
            ),
            SourceConfig(
                "Coinbase",
                "https://api.exchange.coinbase.com/products/{symbol}/stats",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=8
            ),
            SourceConfig(
                "Kraken",
                "https://api.kraken.com/0/public/Ticker?pair={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=9
            ),
            SourceConfig(
                "Bitfinex",
                "https://api-pub.bitfinex.com/v2/ticker/t{symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=10
            ),
        ],

        'price': [
            SourceConfig(
                "Binance",
                "https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=1
            ),
            SourceConfig(
                "Bybit",
                "https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=2
            ),
            SourceConfig(
                "MEXC",
                "https://api.mexc.com/api/v3/ticker/price?symbol={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=3
            ),
            SourceConfig(
                "OKX",
                "https://www.okx.com/api/v5/market/ticker?instId={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=4
            ),
            SourceConfig(
                "KuCoin",
                "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=5
            ),
            SourceConfig(
                "Gate.io",
                "https://api.gateio.ws/api/v4/spot/tickers?currency_pair={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=6
            ),
            SourceConfig(
                "Huobi",
                "https://api.huobi.pro/market/detail/merged?symbol={symbol_lower}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=7
            ),
            SourceConfig(
                "Coinbase",
                "https://api.exchange.coinbase.com/products/{symbol}/ticker",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=8
            ),
            SourceConfig(
                "Kraken",
                "https://api.kraken.com/0/public/Ticker?pair={symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=9
            ),
            SourceConfig(
                "Bitfinex",
                "https://api-pub.bitfinex.com/v2/ticker/t{symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=10
            ),
        ],

        'news': [
            SourceConfig(
                "TradingView",
                "https://www.tradingview.com/news/",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=1
            ),
            SourceConfig(
                "CoinDesk",
                "https://www.coindesk.com/",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=2
            ),
            SourceConfig(
                "Bitcoin.com",
                "https://news.bitcoin.com/",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=3
            ),
            SourceConfig(
                "CryptoSlate",
                "https://cryptoslate.com/",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=4
            ),
            SourceConfig(
                "Cointelegraph",
                "https://cointelegraph.com/",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=5
            ),
            SourceConfig(
                "AMBCrypto",
                "https://ambcrypto.com/",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=6
            ),
            SourceConfig(
                "Binance News",
                "https://www.binance.com/en/news",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=7
            ),
            SourceConfig(
                "CoinGecko News",
                "https://api.coingecko.com/api/v3/coins/{symbol}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=8
            ),
            SourceConfig(
                "CryptoPanic",
                "https://cryptopanic.com/api/v1/posts/",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=9
            ),
            SourceConfig(
                "NewsData",
                "https://newsdata.io/api/1/news?apikey=demo&q=cryptocurrency",
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"},
                priority=10
            ),
        ],
    }
