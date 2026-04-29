import logging
import os
import httpx
import json
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("NotificationService")

class NotificationService:
    """
    [SINGULARITY 29.3] Unified Notification Service.
    Supports Telegram (via SOCKS5 proxy) and ntfy.sh (direct).
    """
    def __init__(self):
        self.ntfy_url = os.getenv("NTFY_URL", "https://ntfy.sh/atra_victoria_curator")
        self.tg_token = os.getenv("TG_TOKEN")
        self.tg_chat_id = os.getenv("TG_CHAT_ID")
        self.tg_proxy = os.getenv("TG_PROXY") # e.g. socks5://127.0.0.1:1080

    async def notify(self, title: str, message: str, priority: str = "default", tags: list = None):
        """Send notification to all enabled channels."""
        # 1. ntfy.sh (Primary/Fallback)
        await self.send_ntfy(title, message, priority, tags)
        
        # 2. Telegram (Optional)
        if self.tg_token and self.tg_chat_id:
            await self.send_telegram(title, message)

    async def send_ntfy(self, title: str, message: str, priority: str = "default", tags: list = None):
        """Send notification via ntfy.sh."""
        try:
            # priority map: min, low, default, high, urgent
            # [FIX 29.3] Use URL encoding for headers to support emojis/unicode
            from urllib.parse import quote
            
            headers = {
                "Title": quote(title),
                "Priority": priority,
                "Tags": ",".join(tags or [])
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.ntfy_url,
                    content=message,
                    headers=headers,
                    timeout=10.0
                )
                if resp.status_code == 200:
                    logger.info(f"🔔 [NTFY] Sent: {title}")
                else:
                    logger.warning(f"⚠️ [NTFY] Failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"❌ [NTFY] Error: {e}")

    async def send_telegram(self, title: str, message: str):
        """Send notification via Telegram (with proxy support)."""
        if not self.tg_token or not self.tg_chat_id:
            return

        try:
            url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
            payload = {
                "chat_id": self.tg_chat_id,
                "text": f"<b>{title}</b>\n\n{message}",
                "parse_mode": "HTML"
            }
            
            proxy_mounts = None
            if self.tg_proxy:
                proxy_mounts = {"all://": self.tg_proxy}

            async with httpx.AsyncClient(proxies=proxy_mounts) as client:
                resp = await client.post(url, json=payload, timeout=15.0)
                if resp.status_code == 200:
                    logger.info(f"🔔 [TG] Sent: {title}")
                else:
                    logger.warning(f"⚠️ [TG] Failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"❌ [TG] Error: {e}")

_service = None

def get_notification_service() -> NotificationService:
    global _service
    if _service is None:
        _service = NotificationService()
    return _service
