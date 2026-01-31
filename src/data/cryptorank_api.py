#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 CRYPTORANK API ИНТЕГРАЦИЯ
Резервный источник данных с хорошими лимитами
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

class CryptoRankAPI:
    """API интеграция с CryptoRank"""
    
    def __init__(self, api_key: str = "fe4393f7b12dcbc09c605019e5f857922905512211eb0f6b9cc67652f2e9"):
        self.api_key = api_key
        self.base_url = "https://api.cryptorank.io/v2"
        self.session = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получает или создает HTTP сессию"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """Закрывает HTTP сессию"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получает цену символа"""
        try:
            session = await self._get_session()
            
            # Преобразуем символ для CryptoRank (убираем USDT)
            base_symbol = symbol.replace("USDT", "").upper()
            
            # Получаем данные о монете через поиск
            url = f"{self.base_url}/coins"
            params = {
                "api_key": self.api_key,
                "symbol": base_symbol,
                "fields": "price,marketCap,volume24h,priceChange24h"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("status") and data.get("data"):
                        # Ищем нужную монету в списке
                        coins = data["data"]
                        target_coin = None
                        
                        for coin in coins:
                            if coin.get("symbol", "").upper() == base_symbol:
                                target_coin = coin
                                break
                        
                        if target_coin:
                            return {
                                "symbol": symbol,
                                "price": float(target_coin.get("price", 0)),
                                "market_cap": float(target_coin.get("marketCap", 0)),
                                "volume_24h": float(target_coin.get("volume24h", 0)),
                                "change_24h": float(target_coin.get("priceChange24h", 0)),
                                "timestamp": get_utc_now().timestamp(),
                                "source": "cryptorank"
                            }
                        else:
                            logger.warning(f"CryptoRank: Монета {base_symbol} не найдена")
                            return None
                    else:
                        logger.warning(f"CryptoRank: Нет данных для {symbol}")
                        return None
                else:
                    logger.warning(f"CryptoRank API error для {symbol}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка получения цены от CryptoRank для {symbol}: {e}")
            return None
    
    async def get_multiple_prices(self, symbols: list) -> Dict[str, Dict[str, Any]]:
        """Получает цены для нескольких символов"""
        results = {}
        
        # Получаем данные параллельно
        tasks = []
        for symbol in symbols:
            tasks.append(self.get_price(symbol))
        
        prices = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, price_data in enumerate(prices):
            if isinstance(price_data, dict) and price_data:
                results[symbols[i]] = price_data
            elif isinstance(price_data, Exception):
                logger.error(f"Ошибка получения цены для {symbols[i]}: {price_data}")
        
        return results
    
    async def get_market_data(self) -> Optional[Dict[str, Any]]:
        """Получает общие рыночные данные"""
        try:
            session = await self._get_session()
            
            url = f"{self.base_url}/global"
            params = {"api_key": self.api_key}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("status") and data.get("data"):
                        market_data = data["data"]
                        
                        return {
                            "total_market_cap": float(market_data.get("totalMarketCap", 0)),
                            "total_volume_24h": float(market_data.get("totalVolume24h", 0)),
                            "btc_dominance": float(market_data.get("btcDominance", 0)),
                            "eth_dominance": float(market_data.get("ethDominance", 0)),
                            "active_cryptocurrencies": int(market_data.get("activeCryptocurrencies", 0)),
                            "timestamp": get_utc_now().timestamp(),
                            "source": "cryptorank"
                        }
                    else:
                        logger.warning("CryptoRank: Нет рыночных данных")
                        return None
                else:
                    logger.warning(f"CryptoRank API error для рыночных данных: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка получения рыночных данных от CryptoRank: {e}")
            return None

# Создаем глобальный экземпляр
cryptorank_api = CryptoRankAPI()

async def test_cryptorank_integration():
    """Тестирует интеграцию с CryptoRank"""
    print("🧪 ТЕСТИРОВАНИЕ CRYPTORANK API:")
    print("="*50)
    
    try:
        # Тестируем получение цены BTC
        btc_price = await cryptorank_api.get_price("BTCUSDT")
        if btc_price:
            print(f"✅ BTC цена: ${btc_price['price']:,.2f}")
            print(f"📊 Market Cap: ${btc_price['market_cap']:,.0f}")
            print(f"📈 Изменение 24h: {btc_price['change_24h']:+.2f}%")
        else:
            print("❌ Не удалось получить цену BTC")
        
        # Тестируем рыночные данные
        market_data = await cryptorank_api.get_market_data()
        if market_data:
            print(f"\n🌍 РЫНОЧНЫЕ ДАННЫЕ:")
            print(f"📊 Общая капитализация: ${market_data['total_market_cap']:,.0f}")
            print(f"📈 Объем 24h: ${market_data['total_volume_24h']:,.0f}")
            print(f"🥇 BTC доминирование: {market_data['btc_dominance']:.2f}%")
            print(f"🥈 ETH доминирование: {market_data['eth_dominance']:.2f}%")
        else:
            print("❌ Не удалось получить рыночные данные")
        
        # Тестируем несколько символов
        symbols = ["ETHUSDT", "BNBUSDT", "ADAUSDT"]
        multiple_prices = await cryptorank_api.get_multiple_prices(symbols)
        
        print(f"\n📊 ЦЕНЫ ДЛЯ {len(symbols)} СИМВОЛОВ:")
        for symbol, data in multiple_prices.items():
            print(f"  {symbol}: ${data['price']:,.4f}")
        
        print(f"\n✅ CryptoRank API работает корректно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования CryptoRank: {e}")
        return False
    finally:
        await cryptorank_api.close()

if __name__ == "__main__":
    asyncio.run(test_cryptorank_integration())
