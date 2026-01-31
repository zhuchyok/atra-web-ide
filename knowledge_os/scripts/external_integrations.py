#!/usr/bin/env python3
"""External integrations orchestrating alerts and remote checks."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import aiohttp
import asyncssh

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
LOGGER = logging.getLogger("external_integrations")

TELEGRAM_TOKEN_ENV = "TRADING_BOT_DEV_TOKEN"
TELEGRAM_CHAT_ENV = "TRADING_ALERT_CHAT_ID"
SSH_HOST_ENV = "TRADING_SERVER_HOST"
SSH_USER_ENV = "TRADING_SERVER_USER"
SSH_KEY_PATH_ENV = "TRADING_SERVER_KEY"


class TradingSystemIntegrations:
    """Utility methods for notifying and executing remote control tasks."""

    def __init__(self) -> None:
        self.telegram_token: Optional[str] = os.getenv(TELEGRAM_TOKEN_ENV)
        self.telegram_chat: Optional[str] = os.getenv(TELEGRAM_CHAT_ENV)
        self.server_host: Optional[str] = os.getenv(SSH_HOST_ENV)
        self.server_user: Optional[str] = os.getenv(SSH_USER_ENV, "root")
        self.ssh_key_path: Optional[str] = os.getenv(SSH_KEY_PATH_ENV)

    async def send_telegram_alert(self, message: str) -> bool:
        if not self.telegram_token or not self.telegram_chat:
            LOGGER.warning("Telegram credentials not configured. Skipping alert: %s", message)
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat,
            "text": f"\ud83d\udea8 {message}",
            "parse_mode": "Markdown"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as response:
                if response.status != 200:
                    LOGGER.error("Telegram alert failed: %s", await response.text())
                    return False
                return True

    async def execute_remote_command(self, command: str) -> Optional[str]:
        if not self.server_host:
            LOGGER.warning("SSH host not configured. Skipping command: %s", command)
            return None

        connect_kwargs = {}
        if self.ssh_key_path:
            connect_kwargs["client_keys"] = [self.ssh_key_path]

        try:
            async with asyncssh.connect(
                self.server_host,
                username=self.server_user,
                **connect_kwargs,
            ) as conn:
                result = await conn.run(command, check=False)
                if result.exit_status != 0:
                    LOGGER.error("Command failed: %s", result.stderr)
                return result.stdout
        except (OSError, asyncssh.Error) as exc:
            LOGGER.error("Remote command failed: %s", exc)
            await self.send_telegram_alert(f"Remote command failed: {command}")
            return None

    async def monitor_system_health(self) -> None:
        while True:
            try:
                await self.execute_remote_command("uptime")
                await self.execute_remote_command("docker ps | grep trading || true")
                await self.execute_remote_command("df -h")
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception("Health monitoring error: %s", exc)
            await asyncio.sleep(300)


async def main() -> None:
    integrations = TradingSystemIntegrations()
    await integrations.send_telegram_alert("Trading system integrations started")
    await integrations.monitor_system_health()


if __name__ == "__main__":
    asyncio.run(main())
