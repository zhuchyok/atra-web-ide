"""
Telegram Alerter для централизованной отправки алертов в Telegram.
Интегрируется со всеми компонентами системы для единой точки алертинга.
"""

import asyncio
import os
import logging
import httpx
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class AlertPriority(Enum):
    """Приоритет алерта"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TelegramAlerter:
    """
    Централизованная система Telegram алертов.
    Отправляет алерты в единый канал с приоритизацией.
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None
    ):
        self.token = token or os.getenv('TG_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = chat_id or os.getenv('CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID', '')
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self._alert_queue: List[Dict] = []
        self._rate_limit_delay = 1.0  # Задержка между отправками (Telegram limit: 30 msg/sec)
        self._last_send_time = 0.0
    
    def _get_priority_emoji(self, priority: str) -> str:
        """Возвращает эмодзи для приоритета"""
        priority_map = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🔴",
            "critical": "🚨"
        }
        return priority_map.get(priority.lower(), "📢")
    
    def _format_alert(self, message: str, priority: str, source: Optional[str] = None) -> str:
        """Форматирует алерт для отправки"""
        emoji = self._get_priority_emoji(priority)
        priority_text = priority.upper()
        
        formatted = f"{emoji} *{priority_text} ALERT*\n\n"
        
        if source:
            formatted += f"📡 *Источник:* {source}\n\n"
        
        formatted += f"{message}\n\n"
        formatted += f"🕐 *Время:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return formatted
    
    async def send_alert(
        self,
        message: str,
        priority: str = "medium",
        source: Optional[str] = None,
        retry_count: int = 3
    ) -> bool:
        """
        Отправляет алерт в Telegram.
        
        Args:
            message: Текст алерта
            priority: Приоритет ('low', 'medium', 'high', 'critical')
            source: Источник алерта (например, 'Circuit Breaker', 'Anomaly Detector')
            retry_count: Количество попыток при ошибке
        
        Returns:
            True если успешно отправлено, False иначе
        """
        if not self.token or not self.chat_id:
            logger.debug("TG_TOKEN/CHAT_ID не заданы, пропуск Telegram алерта")
            return False
        formatted_message = self._format_alert(message, priority, source)
        
        # Rate limiting
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_send_time
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        
        for attempt in range(retry_count):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{self.base_url}/sendMessage",
                        data={
                            'chat_id': self.chat_id,
                            'text': formatted_message,
                            'parse_mode': 'Markdown',
                            'disable_web_page_preview': True
                        }
                    )
                    
                    if response.status_code == 200:
                        self._last_send_time = asyncio.get_event_loop().time()
                        logger.info(f"✅ [TELEGRAM ALERT] Отправлен алерт: {priority} от {source or 'unknown'}")
                        return True
                    else:
                        logger.warning(f"⚠️ [TELEGRAM ALERT] HTTP {response.status_code}: {response.text[:100]}")
                        
            except httpx.TimeoutException:
                logger.warning(f"⚠️ [TELEGRAM ALERT] Timeout при отправке (попытка {attempt + 1}/{retry_count})")
            except Exception as e:
                logger.error(f"❌ [TELEGRAM ALERT] Ошибка отправки: {e}")
            
            if attempt < retry_count - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        # Если не удалось отправить, добавляем в очередь
        self._alert_queue.append({
            "message": message,
            "priority": priority,
            "source": source,
            "timestamp": datetime.now()
        })
        
        logger.error(f"❌ [TELEGRAM ALERT] Не удалось отправить алерт после {retry_count} попыток")
        return False
    
    async def send_batch_alerts(self, alerts: List[Dict]) -> int:
        """Отправляет батч алертов"""
        sent_count = 0
        for alert in alerts:
            success = await self.send_alert(
                alert.get("message", ""),
                alert.get("priority", "medium"),
                alert.get("source")
            )
            if success:
                sent_count += 1
        return sent_count
    
    async def retry_failed_alerts(self):
        """Повторяет отправку неудачных алертов из очереди"""
        if not self._alert_queue:
            return
        
        failed_alerts = self._alert_queue.copy()
        self._alert_queue.clear()
        
        for alert in failed_alerts:
            # Проверяем, не слишком ли старый алерт (старше 1 часа - пропускаем)
            if (datetime.now() - alert["timestamp"]).total_seconds() > 3600:
                continue
            
            await self.send_alert(
                alert["message"],
                alert["priority"],
                alert["source"]
            )
    
    async def send_system_status(
        self,
        status: Dict[str, Any],
        priority: str = "medium"
    ):
        """Отправляет статус системы"""
        message = "📊 *СТАТУС СИСТЕМЫ*\n\n"
        
        for key, value in status.items():
            if isinstance(value, dict):
                message += f"*{key}:*\n"
                for sub_key, sub_value in value.items():
                    message += f"  • {sub_key}: {sub_value}\n"
            else:
                message += f"*{key}:* {value}\n"
        
        await self.send_alert(message, priority, "System Monitor")

# Глобальный экземпляр
_telegram_alerter: Optional[TelegramAlerter] = None

def get_telegram_alerter(
    token: Optional[str] = None,
    chat_id: Optional[str] = None
) -> TelegramAlerter:
    """Получить глобальный экземпляр TelegramAlerter"""
    global _telegram_alerter
    if _telegram_alerter is None:
        _telegram_alerter = TelegramAlerter(token, chat_id)
    return _telegram_alerter

