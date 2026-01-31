#!/usr/bin/env python3
"""
Очередь сигналов с TTL и приоритетами
"""

import time
from typing import Dict, Any, Optional


class SignalQueue:
    """Очередь сигналов с TTL и приоритетами для управления торговыми сигналами."""

    def __init__(self):
        self.queue = []
        self.ttl = 3600  # 1 час TTL
        self.max_size = 1000

    async def add_signal(self, signal_data: Dict[str, Any], priority: int = 1):
        """Добавляет сигнал в очередь с приоритетом"""
        signal_data["priority"] = priority
        signal_data["queue_time"] = time.time()
        self.queue.append(signal_data)

        # Ограничиваем размер очереди
        if len(self.queue) > self.max_size:
            self.queue = self.queue[-self.max_size:]

    async def get_next_signal(self) -> Optional[Dict[str, Any]]:
        """Получает следующий сигнал из очереди"""
        if not self.queue:
            return None

        # Сортируем по приоритету (высший приоритет = меньше число)
        self.queue.sort(key=lambda x: x.get("priority", 1))

        # Удаляем просроченные сигналы
        current_time = time.time()
        self.queue = [s for s in self.queue if current_time - s.get("queue_time", 0) < self.ttl]

        if self.queue:
            return self.queue.pop(0)
        return None

    def get_queue_stats(self) -> Dict[str, Any]:
        """Возвращает статистику очереди"""
        return {
            "queue_size": len(self.queue),
            "max_size": self.max_size,
            "ttl": self.ttl
        }


# Глобальная очередь сигналов
signal_queue = SignalQueue()
