#!/usr/bin/env python3
"""
Ограничитель скорости для Telegram API
"""

import asyncio
import time


class TelegramRateLimiter:
    """Ограничитель скорости для Telegram API с поддержкой пользовательских и групповых лимитов."""

    def __init__(self):
        self.user_limits = {}  # user_id -> last_send_time
        self.bot_limits = {"last_send": 0, "count": 0}  # Общие лимиты бота
        self.user_rate = 1.0  # 1 сообщение в секунду на пользователя
        self.bot_rate = 30.0  # 30 сообщений в секунду на бота
        self.group_rate = 20.0  # 20 сообщений в минуту на группу

    async def can_send_to_user(self, user_id: str) -> bool:
        """Проверяет, можно ли отправить сообщение пользователю"""
        current_time = time.time()

        if user_id not in self.user_limits:
            self.user_limits[user_id] = current_time
            return True

        time_since_last = current_time - self.user_limits[user_id]
        if time_since_last >= self.user_rate:
            self.user_limits[user_id] = current_time
            return True

        return False

    async def can_send_bot_message(self) -> bool:
        """Проверяет, можно ли отправить сообщение от бота"""
        current_time = time.time()

        # Сбрасываем счетчик каждую секунду
        if current_time - self.bot_limits["last_send"] >= 1.0:
            self.bot_limits["count"] = 0
            self.bot_limits["last_send"] = current_time

        if self.bot_limits["count"] < self.bot_rate:
            self.bot_limits["count"] += 1
            return True

        return False

    async def wait_if_needed(self, user_id: str):
        """Ждет, если необходимо соблюсти rate limiting"""
        while not await self.can_send_to_user(user_id) or not await self.can_send_bot_message():
            await asyncio.sleep(0.1)


# Глобальный rate limiter
rate_limiter = TelegramRateLimiter()
