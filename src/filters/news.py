"""
Фильтры новостей для торговых сигналов
Полная реализация с 9 источниками новостей
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.shared.utils.datetime_utils import get_utc_now
from .base import BaseFilter, FilterResult

import aiohttp
import requests

from config import (
    CRYPTOPANIC_API_KEY,
    NEWSDATA_API_KEY
)

logger = logging.getLogger(__name__)

# Кэш для новостей
NEWS_CACHE: Dict[str, Dict[str, Any]] = {}
NEWS_CACHE_TTL = {
    'coingecko': 1800,    # 30 минут
    'tradingview': 900,   # 15 минут
    'cryptopanic': 900,   # 15 минут
    'newsdata': 900,      # 15 минут
    'coindesk': 1200,     # 20 минут
    'bitcoincom': 1200,   # 20 минут
    'cryptoslate': 1200,  # 20 минут
    'cointelegraph': 1200, # 20 минут
    'ambcrypto': 1200,    # 20 минут
    'combined': 900       # 15 минут для комбинированных
}

# Ключевые слова для анализа новостей
POSITIVE_KEYWORDS = [
    'adoption', 'mainstream', 'institutional', 'partnership',
    'collaboration', 'integration', 'implementation', 'launch',
    'upgrade', 'improvement', 'development', 'milestone',
    'breakthrough', 'innovation', 'technology', 'solution',
    'ETF', 'spot ETF', 'Bitcoin ETF', 'approval', 'approved',
    'green light', 'authorized', 'licensed', 'regulated',
    'legitimate', 'trustworthy', 'reliable', 'secure', 'safety',
    'bullish', 'rally', 'surge', 'gain', 'up', 'positive',
    'growth', 'profit', 'success'
]

NEGATIVE_KEYWORDS = [
    'ban', 'banned', 'crackdown', 'crack down', 'regulation',
    'regulatory', 'investigation', 'probe', 'scam', 'fraud',
    'hack', 'hacked', 'exploit', 'vulnerability', 'breach',
    'theft', 'stolen', 'rug pull', 'rug-pull', 'rugpull',
    'exit scam', 'ponzi', 'pyramid', 'scheme', 'scandal',
    'lawsuit', 'legal', 'court', 'SEC', 'CFTC', 'FINRA',
    'FINCEN', 'OFAC', 'sanctions', 'blacklist', 'delist',
    'delisting', 'shutdown', 'closing', 'bankruptcy', 'insolvent',
    'bearish', 'drop', 'fall', 'crash', 'down', 'negative'
]

# Маппинг символов на CoinGecko ID
SYMBOL_TO_COINGECKO_ID = {
    "BTCUSDT": "bitcoin",
    "ETHUSDT": "ethereum",
    "XRPUSDT": "ripple",
    "SOLUSDT": "solana",
    "DOGEUSDT": "dogecoin",
    "ADAUSDT": "cardano",
    "BNBUSDT": "binancecoin",
    "MATICUSDT": "matic-network",
    "DOTUSDT": "polkadot",
    "LTCUSDT": "litecoin",
    "BCHUSDT": "bitcoin-cash",
    "LINKUSDT": "chainlink",
    "UNIUSDT": "uniswap",
    "AVAXUSDT": "avalanche-2",
    "ATOMUSDT": "cosmos",
    "XLMUSDT": "stellar",
    "ALGOUSDT": "algorand",
    "VETUSDT": "vechain",
    "ICPUSDT": "internet-computer",
    "FILUSDT": "filecoin",
    "TRXUSDT": "tron",
    "ETCUSDT": "ethereum-classic",
    "NEARUSDT": "near",
    "APTUSDT": "aptos",
    "ARBUSDT": "arbitrum",
    "OPUSDT": "optimism",
}


class NewsFilter(BaseFilter):
    """Фильтр новостей"""

    def __init__(self, enabled: bool = True):
        super().__init__("news", enabled, priority=2)

    async def filter_signal(self, signal_data: Dict[str, Any]) -> FilterResult:
        """Фильтрация сигнала на основе новостей"""
        try:
            symbol = signal_data.get('symbol', '')
            
            # Используем существующую логику
            has_negative = check_negative_news(symbol)
            
            if has_negative:
                return FilterResult(False, "Обнаружены негативные новости")
            else:
                return FilterResult(True, "Негативных новостей не обнаружено")
                
        except Exception as e:
            logger.error("Ошибка в NewsFilter: %s", e)
            return FilterResult(True, f"Ошибка проверки новостей (пропущено): {e}")


def symbol_to_coingecko_id(symbol: str) -> Optional[str]:
    """Преобразует торговый символ в CoinGecko ID"""
    # Сначала проверяем маппинг
    if symbol in SYMBOL_TO_COINGECKO_ID:
        return SYMBOL_TO_COINGECKO_ID[symbol]
    
    # Пытаемся найти через API
    base = symbol.upper().replace("USDT", "").replace("USD", "").replace("BUSD", "").replace("USDC", "")
    url = f"https://api.coingecko.com/api/v3/search?query={base}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            coins = data.get("coins", [])
            if coins:
                coingecko_id = coins[0]["id"]
                logger.debug(f"CoinGecko: найден id для {symbol} -> {coingecko_id}")
                return coingecko_id
    except Exception as e:
        logger.debug(f"Ошибка поиска CoinGecko ID для {symbol}: {e}")
    
    return None


def get_coingecko_news(symbol: str) -> List[Dict[str, Any]]:
    """Получение новостей с CoinGecko (синхронный)"""
    cache_key = f"coingecko:{symbol}"
    if cache_key in NEWS_CACHE:
        cached = NEWS_CACHE[cache_key]
        if time.time() - cached['timestamp'] < NEWS_CACHE_TTL['coingecko']:
            return cached['data']
    
    coingecko_id = symbol_to_coingecko_id(symbol)
    if not coingecko_id:
        return []
    
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            news = []
            
            # Извлекаем описание
            if data.get("description", {}).get("en"):
                description = data["description"]["en"]
                if len(description) > 50:
                    description_lower = description.lower()
                    has_negative = any(kw in description_lower for kw in NEGATIVE_KEYWORDS)
                    
                    if not has_negative:
                        news.append({
                            "title": f"Latest info about {symbol}",
                            "description": description[:200] + "..." if len(description) > 200 else description,
                            "created_at": get_utc_now().isoformat(),
                            "source": "coingecko",
                            "news_type": "neutral"
                        })
            
            # Кэшируем результат
            NEWS_CACHE[cache_key] = {'data': news, 'timestamp': time.time()}
            return news
    except Exception as e:
        logger.debug(f"CoinGecko ошибка для {symbol}: {e}")
    
    return []


async def get_tradingview_news(symbol: str) -> List[Dict[str, Any]]:
    """Получение новостей с TradingView (RSS)"""
    cache_key = f"tradingview:{symbol}"
    if cache_key in NEWS_CACHE:
        cached = NEWS_CACHE[cache_key]
        if time.time() - cached['timestamp'] < NEWS_CACHE_TTL['tradingview']:
            return cached['data']
    
    try:
        url = "https://www.tradingview.com/feed/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    symbol_news = []
                    symbol_lower = symbol.replace("USDT", "").lower()
                    
                    item_pattern = r'<item>(.*?)</item>'
                    items = re.findall(item_pattern, content, re.DOTALL)
                    
                    for item in items:
                        title_match = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
                        description_match = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
                        
                        if title_match:
                            title = title_match.group(1).strip()
                            title = re.sub(r'<[^>]+>', '', title)
                            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                            title = re.sub(r'\s+', ' ', title).strip()
                            
                            if symbol_lower in title.lower():
                                description = ""
                                if description_match:
                                    description = description_match.group(1).strip()
                                    description = re.sub(r'<[^>]+>', '', description)
                                    description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', description)
                                    description = re.sub(r'\s+', ' ', description).strip()
                                
                                if len(title) > 10:
                                    # Анализ настроения
                                    title_lower = title.lower()
                                    news_type = 'neutral'
                                    if any(kw in title_lower for kw in POSITIVE_KEYWORDS):
                                        news_type = 'positive'
                                    elif any(kw in title_lower for kw in NEGATIVE_KEYWORDS):
                                        news_type = 'negative'
                                    
                                    symbol_news.append({
                                        "title": title,
                                        "description": description,
                                        "created_at": get_utc_now().isoformat(),
                                        "source": "tradingview",
                                        "news_type": news_type
                                    })
                    
                    NEWS_CACHE[cache_key] = {'data': symbol_news, 'timestamp': time.time()}
                    return symbol_news
    except Exception as e:
        logger.debug(f"TradingView ошибка для {symbol}: {e}")
    
    return []


async def get_cryptopanic_news(symbol: str) -> List[Dict[str, Any]]:
    """Получение новостей с CryptoPanic (API)"""
    if not CRYPTOPANIC_API_KEY:
        return []
    
    cache_key = f"cryptopanic:{symbol}"
    if cache_key in NEWS_CACHE:
        cached = NEWS_CACHE[cache_key]
        if time.time() - cached['timestamp'] < NEWS_CACHE_TTL['cryptopanic']:
            return cached['data']
    
    try:
        base_symbol = symbol.replace('USDT', '').replace('USD', '').replace('BTC', '')
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            'auth_token': CRYPTOPANIC_API_KEY,
            'currencies': base_symbol,
            'filter': 'hot',
            'public': 'true'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    news_list = []
                    
                    for post in data.get('results', []):
                        currencies = [curr.get('code', '').upper() for curr in post.get('currencies', [])]
                        if base_symbol.upper() in currencies:
                            sentiment = post.get('sentiment', 'neutral')
                            votes = post.get('votes', {})
                            
                            news_type = 'neutral'
                            if sentiment == 'positive' or votes.get('positive', 0) > votes.get('negative', 0):
                                news_type = 'positive'
                            elif sentiment == 'negative' or votes.get('negative', 0) > votes.get('positive', 0):
                                news_type = 'negative'
                            
                            news_list.append({
                                'title': post.get('title', ''),
                                'description': post.get('metadata', {}).get('description', ''),
                                'created_at': post.get('created_at', ''),
                                'source': 'CryptoPanic',
                                'url': post.get('url', ''),
                                'sentiment': sentiment,
                                'news_type': news_type
                            })
                    
                    NEWS_CACHE[cache_key] = {'data': news_list, 'timestamp': time.time()}
                    return news_list
    except Exception as e:
        logger.debug(f"CryptoPanic ошибка для {symbol}: {e}")
    
    return []


async def get_newsdata_news(symbol: str) -> List[Dict[str, Any]]:
    """Получение новостей с NewsData.io (API)"""
    if not NEWSDATA_API_KEY:
        return []
    
    cache_key = f"newsdata:{symbol}"
    if cache_key in NEWS_CACHE:
        cached = NEWS_CACHE[cache_key]
        if time.time() - cached['timestamp'] < NEWS_CACHE_TTL['newsdata']:
            return cached['data']
    
    try:
        base_symbol = symbol.replace('USDT', '').replace('USD', '').replace('BTC', '')
        url = "https://newsdata.io/api/1/news"
        params = {
            'apikey': NEWSDATA_API_KEY,
            'q': f'{base_symbol} cryptocurrency',
            'language': 'en',
            'category': 'business',
            'country': 'us'
        }
        
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    news_list = []
                    
                    for article in data.get('results', []):
                        title = article.get('title', '').lower()
                        description = article.get('description', '').lower()
                        content = article.get('content', '').lower()
                        
                        news_type = 'neutral'
                        if any(kw in title or kw in description or kw in content for kw in POSITIVE_KEYWORDS):
                            news_type = 'positive'
                        elif any(kw in title or kw in description or kw in content for kw in NEGATIVE_KEYWORDS):
                            news_type = 'negative'
                        
                        news_list.append({
                            'title': article.get('title', ''),
                            'description': article.get('description', ''),
                            'created_at': article.get('pubDate', ''),
                            'source': 'NewsData.io',
                            'url': article.get('link', ''),
                            'news_type': news_type
                        })
                    
                    NEWS_CACHE[cache_key] = {'data': news_list, 'timestamp': time.time()}
                    return news_list
    except Exception as e:
        logger.debug(f"NewsData.io ошибка для {symbol}: {e}")
    
    return []


async def get_coindesk_news(symbol: str) -> List[Dict[str, Any]]:
    """Получение новостей с CoinDesk (RSS)"""
    cache_key = f"coindesk:{symbol}"
    if cache_key in NEWS_CACHE:
        cached = NEWS_CACHE[cache_key]
        if time.time() - cached['timestamp'] < NEWS_CACHE_TTL['coindesk']:
            return cached['data']
    
    try:
        base_symbol = symbol.replace('USDT', '').replace('USD', '').replace('BTC', '')
        url = "https://www.coindesk.com/feed/"
        timeout = aiohttp.ClientTimeout(total=15)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    symbol_news = []
                    symbol_lower = base_symbol.lower()
                    
                    item_pattern = r'<item>(.*?)</item>'
                    items = re.findall(item_pattern, content, re.DOTALL)
                    
                    for item in items:
                        title_match = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
                        description_match = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
                        
                        if title_match:
                            title = title_match.group(1).strip()
                            title = re.sub(r'<[^>]+>', '', title)
                            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                            title = re.sub(r'\s+', ' ', title).strip()
                            
                            if symbol_lower in title.lower():
                                description = ""
                                if description_match:
                                    description = description_match.group(1).strip()
                                    description = re.sub(r'<[^>]+>', '', description)
                                    description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', description)
                                    description = re.sub(r'\s+', ' ', description).strip()
                                
                                if len(title) > 10:
                                    title_lower = title.lower()
                                    news_type = 'neutral'
                                    if any(kw in title_lower for kw in POSITIVE_KEYWORDS):
                                        news_type = 'positive'
                                    elif any(kw in title_lower for kw in NEGATIVE_KEYWORDS):
                                        news_type = 'negative'
                                    
                                    symbol_news.append({
                                        "title": title,
                                        "description": description,
                                        "created_at": get_utc_now().isoformat(),
                                        "source": "CoinDesk",
                                        "news_type": news_type
                                    })
                    
                    NEWS_CACHE[cache_key] = {'data': symbol_news, 'timestamp': time.time()}
                    return symbol_news
    except Exception as e:
        logger.debug(f"CoinDesk ошибка для {symbol}: {e}")
    
    return []


async def get_bitcoincom_news(symbol: str) -> List[Dict[str, Any]]:
    """Получение новостей с Bitcoin.com (RSS)"""
    cache_key = f"bitcoincom:{symbol}"
    if cache_key in NEWS_CACHE:
        cached = NEWS_CACHE[cache_key]
        if time.time() - cached['timestamp'] < NEWS_CACHE_TTL['bitcoincom']:
            return cached['data']
    
    try:
        base_symbol = symbol.replace('USDT', '').replace('USD', '').replace('BTC', '')
        url = "https://news.bitcoin.com/feed/"
        timeout = aiohttp.ClientTimeout(total=15)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    symbol_news = []
                    symbol_lower = base_symbol.lower()
                    
                    item_pattern = r'<item>(.*?)</item>'
                    items = re.findall(item_pattern, content, re.DOTALL)
                    
                    for item in items:
                        title_match = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
                        description_match = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
                        
                        if title_match:
                            title = title_match.group(1).strip()
                            title = re.sub(r'<[^>]+>', '', title)
                            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                            title = re.sub(r'\s+', ' ', title).strip()
                            
                            if symbol_lower in title.lower():
                                description = ""
                                if description_match:
                                    description = description_match.group(1).strip()
                                    description = re.sub(r'<[^>]+>', '', description)
                                    description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', description)
                                    description = re.sub(r'\s+', ' ', description).strip()
                                
                                if len(title) > 10:
                                    title_lower = title.lower()
                                    news_type = 'neutral'
                                    if any(kw in title_lower for kw in POSITIVE_KEYWORDS):
                                        news_type = 'positive'
                                    elif any(kw in title_lower for kw in NEGATIVE_KEYWORDS):
                                        news_type = 'negative'
                                    
                                    symbol_news.append({
                                        "title": title,
                                        "description": description,
                                        "created_at": get_utc_now().isoformat(),
                                        "source": "Bitcoin.com",
                                        "news_type": news_type
                                    })
                    
                    NEWS_CACHE[cache_key] = {'data': symbol_news, 'timestamp': time.time()}
                    return symbol_news
    except Exception as e:
        logger.debug(f"Bitcoin.com ошибка для {symbol}: {e}")
    
    return []


async def get_cryptoslate_news(symbol: str) -> List[Dict[str, Any]]:
    """Получение новостей с CryptoSlate (RSS)"""
    cache_key = f"cryptoslate:{symbol}"
    if cache_key in NEWS_CACHE:
        cached = NEWS_CACHE[cache_key]
        if time.time() - cached['timestamp'] < NEWS_CACHE_TTL['cryptoslate']:
            return cached['data']
    
    try:
        base_symbol = symbol.replace('USDT', '').replace('USD', '').replace('BTC', '')
        url = "https://cryptoslate.com/feed/"
        timeout = aiohttp.ClientTimeout(total=15)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    symbol_news = []
                    symbol_lower = base_symbol.lower()
                    
                    item_pattern = r'<item>(.*?)</item>'
                    items = re.findall(item_pattern, content, re.DOTALL)
                    
                    for item in items:
                        title_match = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
                        description_match = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
                        
                        if title_match:
                            title = title_match.group(1).strip()
                            title = re.sub(r'<[^>]+>', '', title)
                            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                            title = re.sub(r'\s+', ' ', title).strip()
                            
                            if symbol_lower in title.lower():
                                description = ""
                                if description_match:
                                    description = description_match.group(1).strip()
                                    description = re.sub(r'<[^>]+>', '', description)
                                    description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', description)
                                    description = re.sub(r'\s+', ' ', description).strip()
                                
                                if len(title) > 10:
                                    title_lower = title.lower()
                                    news_type = 'neutral'
                                    if any(kw in title_lower for kw in POSITIVE_KEYWORDS):
                                        news_type = 'positive'
                                    elif any(kw in title_lower for kw in NEGATIVE_KEYWORDS):
                                        news_type = 'negative'
                                    
                                    symbol_news.append({
                                        "title": title,
                                        "description": description,
                                        "created_at": get_utc_now().isoformat(),
                                        "source": "CryptoSlate",
                                        "news_type": news_type
                                    })
                    
                    NEWS_CACHE[cache_key] = {'data': symbol_news, 'timestamp': time.time()}
                    return symbol_news
    except Exception as e:
        logger.debug(f"CryptoSlate ошибка для {symbol}: {e}")
    
    return []


async def get_cointelegraph_news(symbol: str) -> List[Dict[str, Any]]:
    """Получение новостей с Cointelegraph (RSS)"""
    cache_key = f"cointelegraph:{symbol}"
    if cache_key in NEWS_CACHE:
        cached = NEWS_CACHE[cache_key]
        if time.time() - cached['timestamp'] < NEWS_CACHE_TTL['cointelegraph']:
            return cached['data']
    
    try:
        base_symbol = symbol.replace('USDT', '').replace('USD', '').replace('BTC', '')
        url = "https://cointelegraph.com/rss"
        timeout = aiohttp.ClientTimeout(total=15)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    symbol_news = []
                    symbol_lower = base_symbol.lower()
                    
                    item_pattern = r'<item>(.*?)</item>'
                    items = re.findall(item_pattern, content, re.DOTALL)
                    
                    for item in items:
                        title_match = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
                        description_match = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
                        
                        if title_match:
                            title = title_match.group(1).strip()
                            title = re.sub(r'<[^>]+>', '', title)
                            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                            title = re.sub(r'\s+', ' ', title).strip()
                            
                            if symbol_lower in title.lower():
                                description = ""
                                if description_match:
                                    description = description_match.group(1).strip()
                                    description = re.sub(r'<[^>]+>', '', description)
                                    description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', description)
                                    description = re.sub(r'\s+', ' ', description).strip()
                                
                                if len(title) > 10:
                                    title_lower = title.lower()
                                    news_type = 'neutral'
                                    if any(kw in title_lower for kw in POSITIVE_KEYWORDS):
                                        news_type = 'positive'
                                    elif any(kw in title_lower for kw in NEGATIVE_KEYWORDS):
                                        news_type = 'negative'
                                    
                                    symbol_news.append({
                                        "title": title,
                                        "description": description,
                                        "created_at": get_utc_now().isoformat(),
                                        "source": "Cointelegraph",
                                        "news_type": news_type
                                    })
                    
                    NEWS_CACHE[cache_key] = {'data': symbol_news, 'timestamp': time.time()}
                    return symbol_news
    except Exception as e:
        logger.debug(f"Cointelegraph ошибка для {symbol}: {e}")
    
    return []


async def get_ambcrypto_news(symbol: str) -> List[Dict[str, Any]]:
    """Получение новостей с AMBCrypto (RSS)"""
    cache_key = f"ambcrypto:{symbol}"
    if cache_key in NEWS_CACHE:
        cached = NEWS_CACHE[cache_key]
        if time.time() - cached['timestamp'] < NEWS_CACHE_TTL['ambcrypto']:
            return cached['data']
    
    try:
        base_symbol = symbol.replace('USDT', '').replace('USD', '').replace('BTC', '')
        url = "https://ambcrypto.com/feed/"
        timeout = aiohttp.ClientTimeout(total=15)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    symbol_news = []
                    symbol_lower = base_symbol.lower()
                    
                    item_pattern = r'<item>(.*?)</item>'
                    items = re.findall(item_pattern, content, re.DOTALL)
                    
                    for item in items:
                        title_match = re.search(r'<title>(.*?)</title>', item, re.DOTALL)
                        description_match = re.search(r'<description>(.*?)</description>', item, re.DOTALL)
                        
                        if title_match:
                            title = title_match.group(1).strip()
                            title = re.sub(r'<[^>]+>', '', title)
                            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title)
                            title = re.sub(r'\s+', ' ', title).strip()
                            
                            if symbol_lower in title.lower():
                                description = ""
                                if description_match:
                                    description = description_match.group(1).strip()
                                    description = re.sub(r'<[^>]+>', '', description)
                                    description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', description)
                                    description = re.sub(r'\s+', ' ', description).strip()
                                
                                if len(title) > 10:
                                    title_lower = title.lower()
                                    news_type = 'neutral'
                                    if any(kw in title_lower for kw in POSITIVE_KEYWORDS):
                                        news_type = 'positive'
                                    elif any(kw in title_lower for kw in NEGATIVE_KEYWORDS):
                                        news_type = 'negative'
                                    
                                    symbol_news.append({
                                        "title": title,
                                        "description": description,
                                        "created_at": get_utc_now().isoformat(),
                                        "source": "AMBCrypto",
                                        "news_type": news_type
                                    })
                    
                    NEWS_CACHE[cache_key] = {'data': symbol_news, 'timestamp': time.time()}
                    return symbol_news
    except Exception as e:
        logger.debug(f"AMBCrypto ошибка для {symbol}: {e}")
    
    return []


def deduplicate_news(news_sources: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Объединяет новости из разных источников и убирает дубликаты"""
    all_news = []
    seen_titles = set()
    
    for source_news in news_sources:
        if isinstance(source_news, list):
            for news in source_news:
                title = news.get("title", "").lower().strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    all_news.append(news)
    
    return all_news


async def get_news_multi_source(symbol: str) -> List[Dict[str, Any]]:
    """
    Получает новости из всех источников одновременно
    с дедупликацией и кэшированием
    """
    cache_key = f"combined:{symbol}"
    if cache_key in NEWS_CACHE:
        cached = NEWS_CACHE[cache_key]
        if time.time() - cached['timestamp'] < NEWS_CACHE_TTL['combined']:
            logger.debug(f"Используем кэшированные новости для {symbol}")
            return cached['data']
    
    try:
        # Запускаем все источники параллельно
        results = await asyncio.gather(
            get_tradingview_news(symbol),
            get_cryptopanic_news(symbol),
            get_newsdata_news(symbol),
            get_coindesk_news(symbol),
            get_bitcoincom_news(symbol),
            get_cryptoslate_news(symbol),
            get_cointelegraph_news(symbol),
            get_ambcrypto_news(symbol),
            return_exceptions=True
        )
        
        # CoinGecko - синхронный
        coingecko_news = get_coingecko_news(symbol)
        
        # Собираем все новости
        news_sources = []
        if isinstance(coingecko_news, list):
            news_sources.append(coingecko_news)
        
        source_names = ['tradingview', 'cryptopanic', 'newsdata', 'coindesk', 
                       'bitcoincom', 'cryptoslate', 'cointelegraph', 'ambcrypto']
        for idx, result in enumerate(results):
            if isinstance(result, list):
                news_sources.append(result)
            elif isinstance(result, Exception):
                logger.debug(f"Ошибка получения новостей из {source_names[idx]}: {result}")
        
        # Дедупликация
        all_news = deduplicate_news(news_sources)
        
        # Кэшируем результат
        NEWS_CACHE[cache_key] = {'data': all_news, 'timestamp': time.time()}
        
        logger.info(f"[NewsFilter] Получено новостей для {symbol}: {len(all_news)} уникальных из {len(news_sources)} источников")
        return all_news
    except Exception as e:
        logger.error(f"Ошибка получения новостей для {symbol}: {e}")
        return []


def get_news_data(symbol: str) -> List[Dict[str, Any]]:
    """
    Получение новостных данных для символа (синхронная обертка)
    
    Args:
        symbol: Торговый символ
        
    Returns:
        List[Dict]: Список новостей
    """
    try:
        # Используем asyncio для запуска async функции
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Если loop уже запущен, создаем новую задачу
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, get_news_multi_source(symbol))
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(get_news_multi_source(symbol))
    except Exception as e:
        logger.error(f"Ошибка получения новостей для {symbol}: {e}")
        return []


def check_negative_news(symbol: str) -> bool:
    """
    Проверка наличия негативных новостей для символа
    
    Args:
        symbol: Торговый символ
        
    Returns:
        bool: True если есть негативные новости
    """
    try:
        news_list = get_news_data(symbol)
        
        # Проверяем наличие негативных новостей
        for news in news_list:
            news_type = news.get('news_type', 'neutral')
            if news_type == 'negative':
                logger.info(f"[NewsFilter] Найдены негативные новости для {symbol}: {news.get('title', '')}")
                return True
        
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки новостей для {symbol}: {e}")
        return False


def check_positive_news(symbol: str) -> bool:
    """
    Проверка наличия позитивных новостей для символа
    
    Args:
        symbol: Торговый символ
        
    Returns:
        bool: True если есть позитивные новости
    """
    try:
        news_list = get_news_data(symbol)
        
        # Проверяем наличие позитивных новостей
        for news in news_list:
            news_type = news.get('news_type', 'neutral')
            if news_type == 'positive':
                logger.debug(f"[NewsFilter] Найдены позитивные новости для {symbol}: {news.get('title', '')}")
                return True
        
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки новостей для {symbol}: {e}")
        return False

async def get_symbol_news_analysis(symbol: str) -> Dict[str, Any]:
    """Анализирует новости для символа и возвращает сентимент и топ новостей"""
    try:
        all_news = await get_news_multi_source(symbol)
        
        if not all_news:
            return {
                'sentiment': 'neutral',
                'top_news': [],
                'score': 0
            }
        
        # Считаем сентимент
        bullish_count = sum(1 for n in all_news if n.get('news_type') == 'positive')
        bearish_count = sum(1 for n in all_news if n.get('news_type') == 'negative')
        
        sentiment = 'neutral'
        if bullish_count > bearish_count:
            sentiment = 'bullish'
        elif bearish_count > bullish_count:
            sentiment = 'bearish'
            
        return {
            'sentiment': sentiment,
            'top_news': all_news[:5], # Берем топ 5 новостей
            'score': bullish_count - bearish_count
        }
    except Exception as e:
        logger.error(f"Ошибка в get_symbol_news_analysis: {e}")
        return {
            'sentiment': 'neutral',
            'top_news': [],
            'score': 0
        }
