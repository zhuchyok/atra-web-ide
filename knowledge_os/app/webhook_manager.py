"""
Webhook Manager: Система webhooks для интеграции с внешними системами

Функционал:
- Webhooks для уведомлений
- Интеграция с Slack, Discord, Telegram
- Автоматические отчеты
- REST API для внешних систем
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

# API Keys (из environment variables)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class WebhookType(Enum):
    """Типы webhooks"""

    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    CUSTOM = "custom"


@dataclass
class WebhookConfig:
    """Конфигурация webhook"""

    webhook_type: WebhookType
    url: str
    enabled: bool = True
    events: List[str] = None  # Список событий для подписки
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.events is None:
            self.events = []
        if self.metadata is None:
            self.metadata = {}


class WebhookManager:
    """Класс для управления webhooks"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self._webhooks_cache: Dict[str, WebhookConfig] = {}

    async def register_webhook(
        self,
        webhook_type: WebhookType,
        url: str,
        events: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> Optional[str]:
        """Регистрация нового webhook"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                webhook_id = await conn.fetchval(
                    """
                    INSERT INTO webhooks
                    (webhook_type, url, enabled, events, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """,
                    webhook_type.value,
                    url,
                    True,
                    json.dumps(events or []),
                    json.dumps(metadata or {}),
                )

                # Обновляем кеш
                self._webhooks_cache[str(webhook_id)] = WebhookConfig(
                    webhook_type=webhook_type,
                    url=url,
                    enabled=True,
                    events=events or [],
                    metadata=metadata or {},
                )

                logger.info(f"✅ Registered webhook: {webhook_type.value} -> {url}")
                return str(webhook_id)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error registering webhook: {e}")
            return None

    async def send_webhook(
        self, event_type: str, payload: Dict[str, Any], webhook_id: Optional[str] = None
    ) -> List[bool]:
        """Отправка webhook для события"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Получаем webhooks для этого события
                if webhook_id:
                    webhooks = await conn.fetch(
                        """
                        SELECT * FROM webhooks
                        WHERE id = $1 AND enabled = TRUE
                    """,
                        webhook_id,
                    )
                else:
                    webhooks = await conn.fetch(
                        """
                        SELECT * FROM webhooks
                        WHERE enabled = TRUE
                          AND (events = '[]'::jsonb OR events @> $1::jsonb)
                    """,
                        json.dumps([event_type]),
                    )

                results = []
                for webhook in webhooks:
                    config = WebhookConfig(
                        webhook_type=WebhookType(webhook["webhook_type"]),
                        url=webhook["url"],
                        enabled=webhook["enabled"],
                        events=webhook["events"]
                        if isinstance(webhook["events"], list)
                        else json.loads(webhook["events"]),
                        metadata=webhook["metadata"]
                        if isinstance(webhook["metadata"], dict)
                        else json.loads(webhook["metadata"]),
                    )

                    success = await self._send_to_webhook(config, event_type, payload)
                    results.append(success)

                    # Логируем попытку
                    await conn.execute(
                        """
                        INSERT INTO webhook_logs (webhook_id, event_type, payload, success, response)
                        VALUES ($1, $2, $3, $4, $5)
                    """,
                        webhook["id"],
                        event_type,
                        json.dumps(payload),
                        success,
                        json.dumps({"status": "sent" if success else "failed"}),
                    )

                return results
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
            return []

    async def _send_to_webhook(
        self, config: WebhookConfig, event_type: str, payload: Dict[str, Any]
    ) -> bool:
        """Отправка сообщения в конкретный webhook"""
        try:
            if config.webhook_type == WebhookType.SLACK:
                return await self._send_to_slack(config.url, event_type, payload)
            elif config.webhook_type == WebhookType.DISCORD:
                return await self._send_to_discord(config.url, event_type, payload)
            elif config.webhook_type == WebhookType.TELEGRAM:
                return await self._send_to_telegram(config.url, event_type, payload)
            else:
                return await self._send_to_custom(config.url, event_type, payload)
        except Exception as e:
            logger.error(f"Error sending to {config.webhook_type.value}: {e}")
            return False

    async def _send_to_slack(
        self, webhook_url: str, event_type: str, payload: Dict[str, Any]
    ) -> bool:
        """Отправка в Slack"""
        try:
            async with httpx.AsyncClient() as client:
                message = self._format_slack_message(event_type, payload)
                response = await client.post(webhook_url, json=message, timeout=10.0)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Slack webhook error: {e}")
            return False

    async def _send_to_discord(
        self, webhook_url: str, event_type: str, payload: Dict[str, Any]
    ) -> bool:
        """Отправка в Discord"""
        try:
            async with httpx.AsyncClient() as client:
                message = self._format_discord_message(event_type, payload)
                response = await client.post(webhook_url, json=message, timeout=10.0)
                return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Discord webhook error: {e}")
            return False

    async def _send_to_telegram(
        self, chat_id: str, event_type: str, payload: Dict[str, Any]
    ) -> bool:
        """Отправка в Telegram"""
        try:
            if not TELEGRAM_BOT_TOKEN:
                return False

            async with httpx.AsyncClient() as client:
                message = self._format_telegram_message(event_type, payload)
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                response = await client.post(
                    url,
                    json={
                        "chat_id": chat_id or TELEGRAM_CHAT_ID,
                        "text": message,
                        "parse_mode": "Markdown",
                    },
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram webhook error: {e}")
            return False

    async def _send_to_custom(self, url: str, event_type: str, payload: Dict[str, Any]) -> bool:
        """Отправка в кастомный webhook"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={
                        "event_type": event_type,
                        "timestamp": datetime.now().isoformat(),
                        "payload": payload,
                    },
                    timeout=10.0,
                )
                return response.status_code in [200, 201, 204]
        except Exception as e:
            logger.error(f"Custom webhook error: {e}")
            return False

    def _format_slack_message(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Форматирование сообщения для Slack"""
        title = f"🔔 {event_type.replace('_', ' ').title()}"
        text = payload.get("message", json.dumps(payload, indent=2))

        return {
            "text": title,
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": title}},
                {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            ],
        }

    def _format_discord_message(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Форматирование сообщения для Discord"""
        title = f"🔔 {event_type.replace('_', ' ').title()}"
        description = payload.get("message", json.dumps(payload, indent=2))

        return {
            "embeds": [
                {
                    "title": title,
                    "description": description,
                    "color": 0x58A6FF,  # Синий цвет
                    "timestamp": datetime.now().isoformat(),
                }
            ]
        }

    def _format_telegram_message(self, event_type: str, payload: Dict[str, Any]) -> str:
        """Форматирование сообщения для Telegram"""
        title = f"🔔 *{event_type.replace('_', ' ').title()}*"
        message = payload.get("message", json.dumps(payload, indent=2))
        return f"{title}\n\n{message}"


class AutoReporter:
    """Класс для автоматических отчетов"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.webhook_manager = WebhookManager(db_url)

    async def send_daily_report(self, webhook_id: Optional[str] = None) -> bool:
        """Отправка ежедневного отчета"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Собираем статистику за день
                stats = await conn.fetchrow("""
                    SELECT
                        (SELECT count(*) FROM knowledge_nodes WHERE created_at > CURRENT_DATE) as new_knowledge,
                        (SELECT count(*) FROM tasks WHERE status = 'completed' AND completed_at > CURRENT_DATE) as completed_tasks,
                        (SELECT count(*) FROM interaction_logs WHERE created_at > CURRENT_DATE) as interactions,
                        (SELECT avg(feedback_score) FROM interaction_logs WHERE feedback_score IS NOT NULL AND created_at > CURRENT_DATE) as avg_feedback
                """)

                report = {
                    "title": "📊 Ежедневный отчет Knowledge OS",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "stats": {
                        "new_knowledge": stats["new_knowledge"] or 0,
                        "completed_tasks": stats["completed_tasks"] or 0,
                        "interactions": stats["interactions"] or 0,
                        "avg_feedback": round(float(stats["avg_feedback"] or 0), 2),
                    },
                }

                message = f"""
📊 *Ежедневный отчет Knowledge OS*
Дата: {report["date"]}

📈 Статистика:
• Новых знаний: {report["stats"]["new_knowledge"]}
• Завершено задач: {report["stats"]["completed_tasks"]}
• Взаимодействий: {report["stats"]["interactions"]}
• Средний feedback: {report["stats"]["avg_feedback"]}
"""

                results = await self.webhook_manager.send_webhook(
                    "daily_report", {"message": message, "report": report}, webhook_id
                )

                return any(results)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
            return False

    async def send_weekly_report(self, webhook_id: Optional[str] = None) -> bool:
        """Отправка еженедельного отчета"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Собираем статистику за неделю
                stats = await conn.fetchrow("""
                    SELECT
                        (SELECT count(*) FROM knowledge_nodes WHERE created_at > NOW() - INTERVAL '7 days') as new_knowledge,
                        (SELECT count(*) FROM tasks WHERE status = 'completed' AND completed_at > NOW() - INTERVAL '7 days') as completed_tasks,
                        (SELECT count(*) FROM experts) as total_experts,
                        (SELECT count(*) FROM domains) as total_domains
                """)

                report = {
                    "title": "📊 Еженедельный отчет Knowledge OS",
                    "period": "7 дней",
                    "stats": {
                        "new_knowledge": stats["new_knowledge"] or 0,
                        "completed_tasks": stats["completed_tasks"] or 0,
                        "total_experts": stats["total_experts"] or 0,
                        "total_domains": stats["total_domains"] or 0,
                    },
                }

                message = f"""
📊 *Еженедельный отчет Knowledge OS*
Период: {report["period"]}

📈 Статистика:
• Новых знаний: {report["stats"]["new_knowledge"]}
• Завершено задач: {report["stats"]["completed_tasks"]}
• Всего экспертов: {report["stats"]["total_experts"]}
• Всего доменов: {report["stats"]["total_domains"]}
"""

                results = await self.webhook_manager.send_webhook(
                    "weekly_report", {"message": message, "report": report}, webhook_id
                )

                return any(results)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error sending weekly report: {e}")
            return False


async def run_webhook_reports():
    """Запуск автоматических отчетов"""
    logger.info("📊 Starting webhook reports...")

    reporter = AutoReporter()

    # Ежедневный отчет (если сейчас утро)
    if datetime.now().hour == 9:
        await reporter.send_daily_report()

    # Еженедельный отчет (если понедельник)
    if datetime.now().weekday() == 0:
        await reporter.send_weekly_report()

    logger.info("✅ Webhook reports completed")


if __name__ == "__main__":
    asyncio.run(run_webhook_reports())
