"""
BTC Dominance Analyzer - анализ доминации BTC и альтсезона
Интеграция с CoinGecko API для получения данных о доминации BTC
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, Optional, List, Any
from dataclasses import dataclass

import aiohttp
import pandas as pd

logger = logging.getLogger(__name__)

# Кэш для BTC.D данных (TTL 1 час)
_DOMINANCE_CACHE: Dict[str, Dict] = {}
_CACHE_TTL = 3600  # 1 час


@dataclass
class DominanceData:
    """Данные о доминации BTC"""
    btc_dominance: float  # Процент доминации BTC (0-100)
    timestamp: datetime
    eth_btc_ratio: Optional[float] = None  # ETH/BTC ratio
    alt_market_cap: Optional[float] = None  # Альткойн market cap


class BTCDominanceAnalyzer:
    """Анализатор доминации BTC"""
    
    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        self.session: Optional[aiohttp.ClientSession] = None
        self.coingecko_base = "https://api.coingecko.com/api/v3"
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_current_dominance(self) -> Optional[DominanceData]:
        """
        Получает текущую доминацию BTC через CoinGecko API
        
        Returns:
            DominanceData или None при ошибке
        """
        try:
            # Проверяем кэш
            cache_key = "current"
            if cache_key in _DOMINANCE_CACHE:
                cached = _DOMINANCE_CACHE[cache_key]
                if time.time() - cached.get("timestamp", 0) < self.cache_ttl:
                    logger.debug("📊 Используем кэшированные данные BTC.D")
                    return cached["data"]
            
            # Запрос к CoinGecko
            url = f"{self.coingecko_base}/global"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Извлекаем BTC доминацию
                    market_data = data.get("data", {})
                    btc_dominance = market_data.get("market_cap_percentage", {}).get("btc", None)
                    
                    if btc_dominance is None:
                        logger.warning("⚠️ BTC доминация не найдена в ответе CoinGecko")
                        return None
                    
                    # Получаем ETH/BTC ratio (опционально)
                    eth_btc_ratio = None
                    try:
                        # Запрос для ETH/BTC
                        eth_url = f"{self.coingecko_base}/simple/price"
                        params = {"ids": "ethereum,bitcoin", "vs_currencies": "btc"}
                        async with self.session.get(eth_url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as eth_response:
                            if eth_response.status == 200:
                                eth_data = await eth_response.json()
                                eth_btc = eth_data.get("ethereum", {}).get("btc", None)
                                if eth_btc:
                                    eth_btc_ratio = eth_btc
                    except Exception as e:
                        logger.debug("⚠️ Не удалось получить ETH/BTC ratio: %s", e)
                    
                    dominance_data = DominanceData(
                        btc_dominance=btc_dominance,
                        timestamp=get_utc_now(),
                        eth_btc_ratio=eth_btc_ratio
                    )
                    
                    # Кэшируем
                    _DOMINANCE_CACHE[cache_key] = {
                        "data": dominance_data,
                        "timestamp": time.time()
                    }
                    
                    logger.info("✅ BTC доминация: %.2f%%", btc_dominance)
                    return dominance_data
                else:
                    logger.warning("⚠️ CoinGecko API вернул статус %d", response.status)
                    return None
                    
        except asyncio.TimeoutError:
            logger.warning("⚠️ Таймаут запроса к CoinGecko API")
            return None
        except Exception as e:
            logger.error("❌ Ошибка получения BTC доминации: %s", e)
            return None
    
    async def get_dominance_history(self, days: int = 7) -> Optional[pd.DataFrame]:
        """
        Получает историю доминации BTC за последние N дней
        
        Args:
            days: Количество дней истории
            
        Returns:
            DataFrame с колонками: timestamp, btc_dominance
        """
        try:
            # CoinGecko не предоставляет прямого API для истории доминации
            # Используем fallback: возвращаем текущее значение
            current = await self.get_current_dominance()
            if current is None:
                return None
            
            # Создаем простой DataFrame с текущим значением
            df = pd.DataFrame({
                "timestamp": [current.timestamp],
                "btc_dominance": [current.btc_dominance]
            })
            
            logger.debug("📊 История доминации: %d записей", len(df))
            return df
            
        except Exception as e:
            logger.error("❌ Ошибка получения истории доминации: %s", e)
            return None
    
    def calculate_dominance_trend(self, history_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Рассчитывает тренд доминации BTC
        
        Args:
            history_df: DataFrame с историей доминации
            
        Returns:
            Dict с метриками тренда:
            - trend: "rising" | "falling" | "neutral"
            - change_pct: изменение за период (%)
            - days_rising: количество дней роста
        """
        if history_df is None or len(history_df) < 2:
            return {
                "trend": "neutral",
                "change_pct": 0.0,
                "days_rising": 0
            }
        
        try:
            # Сортируем по времени
            df_sorted = history_df.sort_values("timestamp")
            
            first_dom = df_sorted.iloc[0]["btc_dominance"]
            last_dom = df_sorted.iloc[-1]["btc_dominance"]
            
            change_pct = ((last_dom - first_dom) / first_dom) * 100
            
            # Определяем тренд
            if change_pct > 1.0:
                trend = "rising"
            elif change_pct < -1.0:
                trend = "falling"
            else:
                trend = "neutral"
            
            # Подсчитываем дни роста
            df_sorted["change"] = df_sorted["btc_dominance"].diff()
            days_rising = (df_sorted["change"] > 0).sum()
            
            return {
                "trend": trend,
                "change_pct": change_pct,
                "days_rising": days_rising,
                "current_dominance": last_dom,
                "first_dominance": first_dom
            }
            
        except Exception as e:
            logger.error("❌ Ошибка расчета тренда доминации: %s", e)
            return {
                "trend": "neutral",
                "change_pct": 0.0,
                "days_rising": 0
            }


# Глобальный экземпляр (ленивая инициализация)
_dominance_analyzer: Optional[BTCDominanceAnalyzer] = None


async def get_dominance_analyzer() -> BTCDominanceAnalyzer:
    """Получает глобальный экземпляр анализатора"""
    global _dominance_analyzer
    if _dominance_analyzer is None:
        _dominance_analyzer = BTCDominanceAnalyzer()
    return _dominance_analyzer

