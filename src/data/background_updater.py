#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔄 ФОНОВЫЙ ОБНОВЛЯТЕЛЬ ДАННЫХ
Проактивное обновление данных с приоритизацией и rate limiting
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
try:
    from src.data.hybrid_manager import hybrid_data_manager
except ImportError:
    from hybrid_manager import hybrid_data_manager

try:
    from src.utils.smart_rate_limiter import smart_rate_limiter
except ImportError:
    from smart_rate_limiter import smart_rate_limiter

logger = logging.getLogger(__name__)

class BackgroundDataUpdater:
    """Фоновый обновлятель данных с приоритизацией"""
    
    def __init__(self):
        self.data_manager = hybrid_data_manager
        self.rate_limiter = smart_rate_limiter
        
        # УМНЫЕ ПРИОРИТЕТЫ С РЕЗЕРВНЫМИ ИСТОЧНИКАМИ
        self.update_schedules = {
            "critical": {
                "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
                "interval": 60,  # 1 минута (было 30 сек)
                "last_update": 0,
                "primary_source": "binance",
                "fallback_sources": ["bybit", "okx"],
                "use_fallback": True
            },
            "high": {
                "symbols": ["ADAUSDT", "SOLUSDT", "DOTUSDT", "LINKUSDT"],
                "interval": 180,  # 3 минуты (было 60 сек)
                "last_update": 0,
                "primary_source": "binance",
                "fallback_sources": ["bybit", "okx"],
                "use_fallback": True
            },
            "medium": {
                "symbols": ["UNIUSDT", "SNXUSDT"],
                "interval": 300,  # 5 минут (было 120 сек)
                "last_update": 0,
                "primary_source": "binance",
                "fallback_sources": ["bybit"],
                "use_fallback": False  # экономим на резервах
            },
            "low": {
                "symbols": ["DASHUSDT", "NEARUSDT"],
                "interval": 600,  # 10 минут (было 120 сек)
                "last_update": 0,
                "primary_source": "binance",
                "fallback_sources": [],
                "use_fallback": False
            },
            "very_low": {
                "symbols": ["WIFUSDT", "AAVEUSDT", "FETUSDT", "TRUMPUSDT", "ZENUSDT"],
                "interval": 900,  # 15 минут (было 300 сек)
                "last_update": 0,
                "primary_source": "binance",
                "fallback_sources": [],
                "use_fallback": False
            }
        }
        
        # Статус работы
        self.is_running = False
        self.update_task = None
        
        # Статистика
        self.stats = {
            "total_updates": 0,
            "successful_updates": 0,
            "failed_updates": 0,
            "rate_limited_updates": 0,
            "last_update_time": 0,
            "uptime_start": time.time()
        }
    
    async def start_background_updates(self):
        """Запускает фоновое обновление данных"""
        if self.is_running:
            logger.warning("Фоновое обновление уже запущено")
            return
        
        self.is_running = True
        self.stats["uptime_start"] = time.time()
        logger.info("🚀 Запуск фонового обновления данных")
        
        try:
            while self.is_running:
                try:
                    await self._update_all_priorities()
                    await asyncio.sleep(10)  # Проверяем каждые 10 секунд
                    
                except Exception as e:
                    logger.error(f"Ошибка в фоновом обновлении: {e}")
                    await asyncio.sleep(30)  # Пауза при ошибке
                    
        except asyncio.CancelledError:
            logger.info("Фоновое обновление остановлено")
        finally:
            self.is_running = False
    
    async def _update_all_priorities(self):
        """Обновляет все приоритеты согласно расписанию"""
        current_time = time.time()
        
        for priority, schedule in self.update_schedules.items():
            time_since_last = current_time - schedule["last_update"]
            
            if time_since_last >= schedule["interval"]:
                await self._update_priority_batch(priority, schedule["symbols"])
                schedule["last_update"] = current_time
    
    async def _update_priority_batch(self, priority: str, symbols: List[str]):
        """Обновляет пакет символов определенного приоритета"""
        logger.debug(f"Обновление {priority} символов: {symbols}")

        # Фильтрация стейблкоинов на уровне пакетного обновления
        try:
            from src.strategies.stablecoin_filter import should_skip_stablecoin
            symbols = [s for s in symbols if not should_skip_stablecoin(s, context="data_update")]
        except ImportError:
            try:
                from stablecoin_filter import should_skip_stablecoin
                symbols = [s for s in symbols if not should_skip_stablecoin(s, context="data_update")]
            except Exception:
                pass
        except Exception:
            pass
        
        for symbol in symbols:
            try:
                # Проверяем rate limit перед каждым символом
                if not self.rate_limiter.can_make_request("binance"):
                    wait_time = self.rate_limiter.get_wait_time("binance")
                    logger.debug(f"Rate limit для {symbol}, ждем {wait_time:.1f}с")
                    await asyncio.sleep(wait_time)
                
                # Обновляем данные для символа
                success = await self._update_symbol_data(symbol)
                
                if success:
                    self.stats["successful_updates"] += 1
                else:
                    self.stats["failed_updates"] += 1
                
                self.stats["total_updates"] += 1
                
                # Небольшая задержка между символами
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Ошибка обновления {symbol}: {e}")
                self.stats["failed_updates"] += 1
                await asyncio.sleep(2)  # Пауза при ошибке
    
    async def _update_symbol_data(self, symbol: str) -> bool:
        """Обновляет данные для конкретного символа"""
        try:
            # Обновляем OHLC данные
            ohlc_success = await self.data_manager.ensure_fresh_data(symbol, "ohlc")
            
            # Обновляем цену (если есть возможность)
            if self.rate_limiter.can_make_request("binance"):
                price_success = await self.data_manager.ensure_fresh_data(symbol, "price")
            else:
                price_success = True  # Пропускаем если rate limit
            
            success = ohlc_success and price_success
            
            if success:
                logger.debug(f"✅ Обновлены данные для {symbol}")
            else:
                logger.warning(f"⚠️ Не удалось обновить данные для {symbol}")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка обновления данных {symbol}: {e}")
            return False
    
    async def force_update_symbol(self, symbol: str) -> bool:
        """Принудительно обновляет данные для символа"""
        logger.info(f"Принудительное обновление для {symbol}")
        
        try:
            # Принудительно получаем свежие данные
            fresh_data = await self.data_manager.get_smart_data(symbol, "ohlc", force_fresh=True)
            
            if fresh_data:
                logger.info(f"✅ Принудительное обновление успешно для {symbol}")
                return True
            else:
                logger.warning(f"❌ Не удалось принудительно обновить {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка принудительного обновления {symbol}: {e}")
            return False
    
    async def update_symbols_batch(self, symbols: List[str], priority: str = "medium") -> Dict[str, bool]:
        """Обновляет пакет символов"""
        results = {}
        
        for symbol in symbols:
            try:
                success = await self._update_symbol_data(symbol)
                results[symbol] = success
                
                # Задержка между символами
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Ошибка пакетного обновления {symbol}: {e}")
                results[symbol] = False
        
        return results
    
    def get_update_status(self) -> Dict[str, Any]:
        """Возвращает статус обновлений"""
        current_time = time.time()
        uptime = current_time - self.stats["uptime_start"]
        
        # Статус по приоритетам
        priority_status = {}
        for priority, schedule in self.update_schedules.items():
            time_since_last = current_time - schedule["last_update"]
            next_update_in = max(0, schedule["interval"] - time_since_last)
            
            priority_status[priority] = {
                "symbols_count": len(schedule["symbols"]),
                "interval_seconds": schedule["interval"],
                "last_update_ago": time_since_last,
                "next_update_in": next_update_in,
                "symbols": schedule["symbols"]
            }
        
        return {
            "is_running": self.is_running,
            "uptime_seconds": uptime,
            "total_updates": self.stats["total_updates"],
            "successful_updates": self.stats["successful_updates"],
            "failed_updates": self.stats["failed_updates"],
            "success_rate": (self.stats["successful_updates"] / self.stats["total_updates"] * 100) if self.stats["total_updates"] > 0 else 0,
            "priority_status": priority_status
        }
    
    def stop_background_updates(self):
        """Останавливает фоновое обновление"""
        if self.is_running:
            self.is_running = False
            if self.update_task:
                self.update_task.cancel()
            logger.info("Фоновое обновление остановлено")
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику обновлятеля"""
        data_manager_stats = self.data_manager.get_stats()
        rate_limiter_stats = self.rate_limiter.get_stats()
        
        return {
            "background_updater": {
                "is_running": self.is_running,
                "uptime_seconds": time.time() - self.stats["uptime_start"],
                "total_updates": self.stats["total_updates"],
                "successful_updates": self.stats["successful_updates"],
                "failed_updates": self.stats["failed_updates"],
                "success_rate_percent": (self.stats["successful_updates"] / self.stats["total_updates"] * 100) if self.stats["total_updates"] > 0 else 0
            },
            "data_manager": data_manager_stats,
            "rate_limiter": rate_limiter_stats
        }

# Глобальный экземпляр
background_data_updater = BackgroundDataUpdater()
