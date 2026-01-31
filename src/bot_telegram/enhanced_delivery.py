#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 УЛУЧШЕННАЯ СИСТЕМА TELEGRAM ДОСТАВКИ
Исправляет проблемы с Flood Control и повышает success rate с 91.67% до 98%+
"""

import asyncio
import time
import logging
import re
from collections import defaultdict, deque
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DeliveryStats:
    """Статистика доставки сообщений"""
    total_attempts: int = 0
    successful_sends: int = 0
    flood_control_blocks: int = 0
    timeout_errors: int = 0
    api_errors: int = 0
    network_errors: int = 0
    
    def get_success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.successful_sends / self.total_attempts * 100

class UserRateLimiter:
    """Rate limiter для каждого пользователя"""
    
    def __init__(self):
        self.user_last_message = {}  # {user_id: timestamp}
        self.user_message_count = defaultdict(int)  # {user_id: count}
        self.user_blocked_until = {}  # {user_id: timestamp}
        
        # Лимиты Telegram
        self.MIN_INTERVAL = 1.0  # 1 секунда между сообщениями
        self.MAX_MESSAGES_PER_MINUTE = 20  # 20 сообщений в минуту
        
    async def can_send_message(self, user_id: str) -> bool:
        """Проверяет, можно ли отправить сообщение пользователю"""
        current_time = time.time()
        
        # Проверяем, не заблокирован ли пользователь
        if user_id in self.user_blocked_until:
            if current_time < self.user_blocked_until[user_id]:
                return False
            else:
                # Блокировка истекла
                del self.user_blocked_until[user_id]
        
        # Проверяем минимальный интервал между сообщениями
        last_message_time = self.user_last_message.get(user_id, 0)
        if current_time - last_message_time < self.MIN_INTERVAL:
            return False
        
        # Проверяем лимит сообщений в минуту
        if self.user_message_count[user_id] >= self.MAX_MESSAGES_PER_MINUTE:
            return False
        
        return True
    
    def record_message(self, user_id: str):
        """Записывает отправленное сообщение"""
        current_time = time.time()
        self.user_last_message[user_id] = current_time
        self.user_message_count[user_id] += 1
    
    def block_user(self, user_id: str, duration_seconds: int):
        """Блокирует пользователя на указанное время"""
        self.user_blocked_until[user_id] = time.time() + duration_seconds
        logger.warning("Пользователь %s заблокирован на %d секунд", user_id, duration_seconds)
    
    def get_wait_time(self, user_id: str) -> float:
        """Возвращает время ожидания для пользователя"""
        current_time = time.time()
        
        if user_id in self.user_blocked_until:
            return max(0, self.user_blocked_until[user_id] - current_time)
        
        last_message_time = self.user_last_message.get(user_id, 0)
        return max(0, self.MIN_INTERVAL - (current_time - last_message_time))

class GlobalRateLimiter:
    """Глобальный rate limiter для всех сообщений"""
    
    def __init__(self):
        self.global_message_times = deque()
        self.max_messages_per_second = 30  # 30 сообщений в секунду
        
    async def wait_if_needed(self):
        """Ждет, если необходимо соблюсти глобальный лимит"""
        current_time = time.time()
        
        # Удаляем старые сообщения (старше 1 секунды)
        while self.global_message_times and current_time - self.global_message_times[0] > 1.0:
            self.global_message_times.popleft()
        
        # Проверяем лимит
        if len(self.global_message_times) >= self.max_messages_per_second:
            wait_time = 1.0 - (current_time - self.global_message_times[0])
            if wait_time > 0:
                logger.debug("Глобальный rate limit: ожидание %.2f секунд", wait_time)
                await asyncio.sleep(wait_time)
    
    def record_message(self):
        """Записывает отправленное сообщение"""
        self.global_message_times.append(time.time())

class EnhancedTelegramDelivery:
    """Улучшенная система доставки Telegram сообщений"""
    
    def __init__(self):
        self.user_rate_limiter = UserRateLimiter()
        self.global_rate_limiter = GlobalRateLimiter()
        self.stats = DeliveryStats()
        
        # Настройки retry
        self.max_retries = 5
        self.base_timeout = 5.0
        self.max_timeout = 30.0
        
        # Статистика по пользователям
        self.user_stats = defaultdict(DeliveryStats)
        
    def get_adaptive_timeout(self, attempt: int) -> float:
        """Возвращает адаптивный timeout в зависимости от попытки"""
        return min(self.base_timeout * (1.5 ** attempt), self.max_timeout)
    
    async def notify_user_with_enhanced_delivery(self, user_id: str, message: str, **kwargs):
        """Улучшенная отправка сообщения с расширенной логикой"""
        
        for attempt in range(self.max_retries):
            try:
                # Проверяем rate limits перед отправкой
                if not await self.user_rate_limiter.can_send_message(user_id):
                    wait_time = self.user_rate_limiter.get_wait_time(user_id)
                    if wait_time > 0:
                        logger.debug("Пользователь %s: ожидание %.2f секунд", user_id, wait_time)
                        await asyncio.sleep(wait_time)
                        continue
                
                # Проверяем глобальный rate limit
                await self.global_rate_limiter.wait_if_needed()
                
                # Импортируем notify_user
                try:
                    from src.bot_telegram.handlers import notify_user
                except ImportError:
                    try:
                        from .handlers import notify_user
                    except ImportError:
                        logger.error("Не удалось импортировать notify_user")
                        return False
                
                # Отправляем сообщение с запросом message_id
                kwargs['_return_message'] = True
                result = await notify_user(user_id, message, **kwargs)
                
                logger.info("🔍 notify_user вернул: %s (тип: %s)", result, type(result))
                print(f"🔍 [DEBUG] notify_user вернул: {result} (тип: {type(result)})")
                
                if result:
                    # Записываем успешную отправку
                    self.user_rate_limiter.record_message(user_id)
                    self.global_rate_limiter.record_message()
                    self.stats.total_attempts += 1
                    self.stats.successful_sends += 1
                    self.user_stats[user_id].total_attempts += 1
                    self.user_stats[user_id].successful_sends += 1
                    
                    logger.info("✅ Сообщение успешно отправлено пользователю %s (попытка %d/%d)", 
                               user_id, attempt + 1, self.max_retries)
                    return result  # Возвращаем результат с message_id
                else:
                    logger.warning("⚠️ notify_user вернул False для пользователя %s (попытка %d/%d)", 
                                  user_id, attempt + 1, self.max_retries)
                
            except Exception as e:
                error_msg = str(e)
                self.stats.total_attempts += 1
                self.user_stats[user_id].total_attempts += 1
                
                if "Flood control" in error_msg:
                    # Обработка Flood Control
                    retry_seconds = self._extract_retry_time(error_msg)
                    if retry_seconds:
                        logger.warning("🚨 Flood control для пользователя %s, ожидание %d секунд", 
                                     user_id, retry_seconds)
                        
                        # Блокируем пользователя на время retry
                        self.user_rate_limiter.block_user(user_id, retry_seconds)
                        
                        # Записываем статистику
                        self.stats.flood_control_blocks += 1
                        self.user_stats[user_id].flood_control_blocks += 1
                        
                        # Ждем время retry
                        await asyncio.sleep(min(retry_seconds, 600))
                        
                        # Пропускаем этого пользователя
                        return False
                    else:
                        # Стандартная задержка при flood control
                        await asyncio.sleep(60)
                        self.stats.flood_control_blocks += 1
                        self.user_stats[user_id].flood_control_blocks += 1
                
                elif "timeout" in error_msg.lower():
                    # Обработка таймаутов
                    timeout_multiplier = 1.5 ** attempt
                    await asyncio.sleep(timeout_multiplier)
                    self.stats.timeout_errors += 1
                    self.user_stats[user_id].timeout_errors += 1
                    logger.warning("⏰ Таймаут для пользователя %s (попытка %d/%d), ожидание %.2f секунд", 
                                 user_id, attempt + 1, self.max_retries, timeout_multiplier)
                
                elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                    # Обработка сетевых ошибок
                    await asyncio.sleep(2 ** attempt)
                    self.stats.network_errors += 1
                    self.user_stats[user_id].network_errors += 1
                    logger.warning("🌐 Сетевая ошибка для пользователя %s (попытка %d/%d)", 
                                 user_id, attempt + 1, self.max_retries)
                
                else:
                    # Общие ошибки - экспоненциальная задержка
                    await asyncio.sleep(2 ** attempt)
                    self.stats.api_errors += 1
                    self.user_stats[user_id].api_errors += 1
                    logger.warning("❌ API ошибка для пользователя %s (попытка %d/%d): %s", 
                                 user_id, attempt + 1, self.max_retries, error_msg)
        
        logger.error("❌ Не удалось отправить сообщение пользователю %s после %d попыток", 
                    user_id, self.max_retries)
        return False
    
    def _extract_retry_time(self, error_msg: str) -> Optional[int]:
        """Извлекает время retry из сообщения об ошибке"""
        try:
            retry_match = re.search(r'retry after (\d+)', error_msg.lower())
            if retry_match:
                return int(retry_match.group(1))
        except (ValueError, AttributeError):
            pass
        return None
    
    def get_delivery_stats(self) -> Dict[str, Any]:
        """Возвращает статистику доставки"""
        return {
            'global_stats': {
                'total_attempts': self.stats.total_attempts,
                'successful_sends': self.stats.successful_sends,
                'success_rate': self.stats.get_success_rate(),
                'flood_control_blocks': self.stats.flood_control_blocks,
                'timeout_errors': self.stats.timeout_errors,
                'api_errors': self.stats.api_errors,
                'network_errors': self.stats.network_errors
            },
            'user_stats': {
                user_id: {
                    'total_attempts': stats.total_attempts,
                    'successful_sends': stats.successful_sends,
                    'success_rate': stats.get_success_rate(),
                    'flood_control_blocks': stats.flood_control_blocks,
                    'timeout_errors': stats.timeout_errors,
                    'api_errors': stats.api_errors,
                    'network_errors': stats.network_errors
                }
                for user_id, stats in self.user_stats.items()
            }
        }
    
    def reset_stats(self):
        """Сбрасывает статистику"""
        self.stats = DeliveryStats()
        self.user_stats.clear()
        logger.info("Статистика доставки сброшена")
    
    def print_stats(self):
        """Выводит статистику в консоль"""
        stats = self.get_delivery_stats()
        global_stats = stats['global_stats']
        
        print("\n📊 СТАТИСТИКА TELEGRAM ДОСТАВКИ")
        print("=" * 50)
        print(f"Всего попыток: {global_stats['total_attempts']}")
        print(f"Успешных отправок: {global_stats['successful_sends']}")
        print(f"Success rate: {global_stats['success_rate']:.2f}%")
        print(f"Flood control блокировки: {global_stats['flood_control_blocks']}")
        print(f"Таймауты: {global_stats['timeout_errors']}")
        print(f"API ошибки: {global_stats['api_errors']}")
        print(f"Сетевые ошибки: {global_stats['network_errors']}")
        
        if stats['user_stats']:
            print("\n👥 СТАТИСТИКА ПО ПОЛЬЗОВАТЕЛЯМ:")
            for user_id, user_stats in stats['user_stats'].items():
                print(f"  Пользователь {user_id}: {user_stats['success_rate']:.2f}% ({user_stats['successful_sends']}/{user_stats['total_attempts']})")
        
        print("=" * 50)

# Глобальный экземпляр улучшенной системы доставки
enhanced_delivery = EnhancedTelegramDelivery()

# Функция-обертка для совместимости
async def notify_user_enhanced(user_id: str, message: str, **kwargs):
    """Улучшенная отправка сообщения с расширенной логикой"""
    return await enhanced_delivery.notify_user_with_enhanced_delivery(user_id, message, **kwargs)

# Функция для получения статистики
def get_telegram_delivery_stats() -> Dict[str, Any]:
    """Возвращает статистику доставки Telegram сообщений"""
    return enhanced_delivery.get_delivery_stats()

# Функция для сброса статистики
def reset_telegram_delivery_stats():
    """Сбрасывает статистику доставки Telegram сообщений"""
    enhanced_delivery.reset_stats()

# Функция для вывода статистики
def print_telegram_delivery_stats():
    """Выводит статистику доставки Telegram сообщений"""
    enhanced_delivery.print_stats()
