#!/usr/bin/env python3

"""
Система алертинга для торгового бота.

Предоставляет комплексную систему уведомлений:
- Уведомления о важных событиях
- Предупреждения о рисках
- Алерты производительности
- Настраиваемые триггеры
"""

import asyncio
import collections
import json
import logging
import os
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp

from src.shared.utils.datetime_utils import get_utc_now

# Используем общую конфигурацию ATRA для выбора prod/dev Telegram
try:
    from config import TELEGRAM_CHAT_IDS
    from config import TOKEN as ATRA_TELEGRAM_TOKEN
except Exception:  # pragma: no cover
    ATRA_TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Алерт"""

    alert_id: str
    alert_type: str  # 'risk', 'performance', 'system', 'market'
    severity: str  # 'low', 'medium', 'high', 'critical'
    title: str
    message: str
    timestamp: datetime = field(default_factory=get_utc_now)
    resolved: bool = False
    resolved_time: datetime = None
    channels: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    user_id: Optional[int] = None  # 🆕 ID пользователя для персональных алертов


@dataclass
class AlertRule:
    """Правило алерта"""

    rule_id: str
    name: str
    condition: str  # Python expression
    severity: str
    channels: List[str]
    cooldown: int  # seconds
    enabled: bool = True
    last_triggered: datetime = None


@dataclass
class NotificationChannel:
    """Канал уведомлений"""

    channel_id: str
    channel_type: str  # 'telegram', 'email', 'webhook', 'slack'
    config: Dict
    enabled: bool = True


class AlertSystem:
    """Главный класс системы алертинга"""

    def __init__(self):
        self.alerts = []
        self.alert_rules = {}
        self.notification_channels = {}

        # Настройки системы
        self.settings = {
            "max_alerts_per_hour": 50,
            "alert_retention_days": 30,
            "auto_resolve_timeout": 3600,  # 1 час
            "batch_notifications": True,
            "notification_delay": 5,  # секунд
        }

        # Статистика
        self.stats = {
            "total_alerts": 0,
            "alerts_by_type": collections.defaultdict(int),
            "alerts_by_severity": collections.defaultdict(int),
            "notifications_sent": 0,
            "failed_notifications": 0,
        }

        # Инициализируем стандартные каналы
        self._initialize_default_channels()

        # Инициализируем стандартные правила
        self._initialize_default_rules()

    def _initialize_default_channels(self):
        """Инициализирует стандартные каналы уведомлений"""

        # Telegram канал
        # По умолчанию используем тот же токен/чат, что и основной бот ATRA,
        # чтобы не было рассинхронизации prod/dev между сигналами и алертами.
        # Можно переопределить через env:
        #   ALERT_TELEGRAM_BOT_TOKEN, ALERT_TELEGRAM_CHAT_ID
        env_bot_token = os.getenv("ALERT_TELEGRAM_BOT_TOKEN", "") or os.getenv(
            "TELEGRAM_BOT_TOKEN", ""
        )
        env_chat_id = os.getenv("ALERT_TELEGRAM_CHAT_ID", "") or os.getenv(
            "TELEGRAM_BOT_CHAT_ID", ""
        )

        # Если env не задан, падаем обратно на конфиг бота (TOKEN + TELEGRAM_CHAT_IDS)
        bot_token = env_bot_token or ATRA_TELEGRAM_TOKEN
        chat_id = env_chat_id
        chat_ids_list = []

        if not chat_id and TELEGRAM_CHAT_IDS:
            # Берём все чаты из списка для отправки алертов во все чаты
            # Очищаем от квадратных скобок и пробелов
            chat_ids_str = TELEGRAM_CHAT_IDS.strip("[]").strip()
            chat_ids_raw = [
                cid.strip().strip("[]") for cid in chat_ids_str.split(",") if cid.strip()
            ]

            # Валидируем и добавляем все валидные chat_id
            for cid in chat_ids_raw:
                try:
                    validated_id = str(int(cid.strip().strip("[]")))
                    chat_ids_list.append(validated_id)
                except (ValueError, TypeError):
                    logger.warning("⚠️ [ALERT] Пропущен некорректный chat_id: %s", cid)

            # Если есть валидные chat_id, используем первый как основной (для обратной совместимости)
            if chat_ids_list:
                chat_id = chat_ids_list[0]
        elif chat_id:
            # Если chat_id задан через env, используем только его
            chat_ids_list = [chat_id]

        telegram_channel = NotificationChannel(
            channel_id="telegram",
            channel_type="telegram",
            config={
                "bot_token": bot_token,
                "chat_id": chat_id,  # Основной chat_id (для обратной совместимости)
                "chat_ids": chat_ids_list,  # 🆕 Список всех chat_id для отправки во все чаты
                "parse_mode": "HTML",
            },
            enabled=True,
        )
        self.notification_channels["telegram"] = telegram_channel

        # Email канал
        email_channel = NotificationChannel(
            channel_id="email",
            channel_type="email",
            config={
                "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
                "smtp_port": int(os.getenv("SMTP_PORT", "587")),
                "username": os.getenv("EMAIL_USERNAME", ""),
                "password": os.getenv("EMAIL_PASSWORD", ""),
                "from_email": os.getenv("FROM_EMAIL", ""),
                "to_emails": os.getenv("TO_EMAILS", "").split(","),
            },
            enabled=True,
        )
        self.notification_channels["email"] = email_channel

        # Webhook канал
        webhook_channel = NotificationChannel(
            channel_id="webhook",
            channel_type="webhook",
            config={
                "url": os.getenv("WEBHOOK_URL", ""),
                "headers": {"Content-Type": "application/json"},
                "timeout": 10,
            },
            enabled=True,
        )
        self.notification_channels["webhook"] = webhook_channel

    def _initialize_default_rules(self):
        """Инициализирует стандартные правила алертов"""

        # Правило для критической просадки
        drawdown_rule = AlertRule(
            rule_id="critical_drawdown",
            name="Critical Drawdown",
            condition="current_drawdown > 15",
            severity="critical",
            channels=["telegram", "email"],
            cooldown=3600,  # 1 час
        )
        self.alert_rules["critical_drawdown"] = drawdown_rule

        # Правило для высокого дневного убытка
        daily_loss_rule = AlertRule(
            rule_id="high_daily_loss",
            name="High Daily Loss",
            condition="daily_pnl < -5",
            severity="high",
            channels=["telegram"],
            cooldown=1800,  # 30 минут
        )
        self.alert_rules["high_daily_loss"] = daily_loss_rule

        # Правило для низкого win rate
        winrate_rule = AlertRule(
            rule_id="low_winrate",
            name="Low Win Rate",
            condition="win_rate < 40 and total_trades > 10",
            severity="medium",
            channels=["telegram"],
            cooldown=7200,  # 2 часа
        )
        self.alert_rules["low_winrate"] = winrate_rule

        # Правило для высокого плеча
        leverage_rule = AlertRule(
            rule_id="high_leverage",
            name="High Leverage",
            condition="leverage_used > 15",
            severity="high",
            channels=["telegram"],
            cooldown=1800,  # 30 минут
        )
        self.alert_rules["high_leverage"] = leverage_rule

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        channels: List[str] = None,
        metadata: Dict = None,
        user_id: Optional[int] = None,
    ) -> str:
        """
        Создает новый алерт

        Args:
            user_id: ID пользователя для персональных алертов.
                    Если указан, алерт отправится только этому пользователю.
                    Если None, алерт отправится в админские чаты (TELEGRAM_CHAT_IDS).
        """

        # Проверяем лимит алертов в час
        hour_ago = get_utc_now() - timedelta(hours=1)
        recent_alerts = len([a for a in self.alerts if a.timestamp > hour_ago])

        if recent_alerts >= self.settings["max_alerts_per_hour"]:
            logger.warning("Alert rate limit exceeded")
            return None

        alert_id = f"ALERT_{int(get_utc_now().timestamp())}"

        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            channels=channels or ["telegram"],
            metadata=metadata or {},
            user_id=user_id,  # 🆕 Сохраняем user_id для персональных алертов
        )

        self.alerts.append(alert)
        self.stats["total_alerts"] += 1
        self.stats["alerts_by_type"][alert_type] += 1
        self.stats["alerts_by_severity"][severity] += 1

        # Отправляем уведомления
        asyncio.create_task(self._send_notifications(alert))

        logger.info("Alert created: %s - %s (user_id=%s)", alert_type, title, user_id or "all")
        return alert_id

    def check_alert_rules(self, data: Dict):
        """Проверяет правила алертов"""

        for rule_id, rule in self.alert_rules.items():
            if not rule.enabled:
                continue

            # Проверяем cooldown
            if rule.last_triggered:
                time_since_trigger = (get_utc_now() - rule.last_triggered).total_seconds()
                if time_since_trigger < rule.cooldown:
                    continue

            # Проверяем условие
            try:
                # pylint: disable=eval-used
                if eval(rule.condition, {"__builtins__": {}}, data):
                    self._trigger_rule(rule, data)
            except Exception as e:
                logger.error("Error evaluating rule %s: %s", rule_id, e)

    def _trigger_rule(self, rule: AlertRule, data: Dict):
        """Срабатывает правило алерта"""

        # Создаем алерт
        alert_id = self.create_alert(
            alert_type="rule_triggered",
            severity=rule.severity,
            title=f"Rule Triggered: {rule.name}",
            message=f"Condition '{rule.condition}' evaluated to True",
            channels=rule.channels,
            metadata={"rule_id": rule.rule_id, "condition": rule.condition},
        )

        if alert_id:
            rule.last_triggered = get_utc_now()
            logger.info("Rule triggered: %s", rule.name)

    async def _send_notifications(self, alert: Alert):
        """Отправляет уведомления по каналам"""

        for channel_id in alert.channels:
            if channel_id not in self.notification_channels:
                logger.error("Channel %s not found", channel_id)
                continue

            channel = self.notification_channels[channel_id]
            if not channel.enabled:
                continue

            try:
                await self._send_to_channel(channel, alert)
                self.stats["notifications_sent"] += 1
            except Exception as e:
                logger.error("Failed to send notification to %s: %s", channel_id, e)
                self.stats["failed_notifications"] += 1

    async def _send_to_channel(self, channel: NotificationChannel, alert: Alert):
        """Отправляет уведомление в канал"""

        if channel.channel_type == "telegram":
            await self._send_telegram_notification(channel, alert)
        elif channel.channel_type == "email":
            await self._send_email_notification(channel, alert)
        elif channel.channel_type == "webhook":
            await self._send_webhook_notification(channel, alert)
        elif channel.channel_type == "slack":
            await self._send_slack_notification(channel, alert)

    async def _send_telegram_notification(self, channel: NotificationChannel, alert: Alert):
        """Отправляет уведомление в Telegram (асинхронно)"""

        config = channel.config
        bot_token = config.get("bot_token")

        if not bot_token:
            logger.error("Telegram bot_token не установлен")
            return

        if alert.user_id:
            chat_ids_list = [str(alert.user_id)]
        else:
            chat_id = config.get("chat_id")
            if chat_id:
                chat_ids_list = [chat_id]
            else:
                chat_ids_list = config.get("chat_ids", [])[:1]

        if not chat_ids_list:
            logger.error("Telegram chat_ids не установлен")
            return

        severity_emoji = {"low": "ℹ️", "medium": "⚠️", "high": "🚨", "critical": "🔥"}

        emoji = severity_emoji.get(alert.severity, "📢")
        msg_template = "{emoji} *{title}*\n\n{message}\n\nSeverity: {severity}\nTime: {time}"
        message = msg_template.format(
            emoji=emoji,
            title=alert.title,
            message=alert.message,
            severity=alert.severity.upper(),
            time=alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        )

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        async with aiohttp.ClientSession() as session:
            for chat_id in chat_ids_list:
                for attempt in range(3):
                    try:
                        data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
                        async with session.post(url, data=data, timeout=10) as response:
                            if response.status == 200:
                                logger.debug("✅ [ALERT] Алерт отправлен в chat_id: %s", chat_id)
                                self.stats["notifications_sent"] += 1
                                break
                            else:
                                logger.warning(
                                    "⚠️ [ALERT] Ошибка Telegram (attempt %d): %d",
                                    attempt + 1,
                                    response.status,
                                )
                    except Exception as e:
                        logger.warning(
                            "⚠️ [ALERT] Ошибка сетевого запроса (attempt %d): %s", attempt + 1, e
                        )

                    if attempt < 2:
                        await asyncio.sleep(2**attempt)
                else:
                    self.stats["failed_notifications"] += 1

    async def _send_email_notification(self, channel: NotificationChannel, alert: Alert):
        """Отправляет уведомление по email"""

        config = channel.config
        smtp_server = config.get("smtp_server")
        smtp_port = config.get("smtp_port")
        username = config.get("username")
        password = config.get("password")
        from_email = config.get("from_email")
        to_emails = config.get("to_emails", [])

        if not all([smtp_server, username, password, from_email, to_emails]):
            logger.error("Email configuration incomplete")
            return

        # Формируем сообщение
        subject = f"[{alert.severity.upper()}] {alert.title}"
        body = (
            f"Alert ID: {alert.alert_id}\n"
            f"Type: {alert.alert_type}\n"
            f"Severity: {alert.severity}\n"
            f"Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"{alert.message}\n\n"
            f"Metadata: {json.dumps(alert.metadata, indent=2)}"
        )

        # Отправляем email
        msg = f"From: {from_email}\nTo: {', '.join(to_emails)}\nSubject: {subject}\n\n{body}"

        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(username, password)
            server.sendmail(from_email, to_emails, msg)
            server.quit()
        except Exception as e:
            logger.error("Failed to send email alert: %s", e)

    async def _send_webhook_notification(self, channel: NotificationChannel, alert: Alert):
        """Отправляет уведомление через webhook (асинхронно)"""

        config = channel.config
        url = config.get("url")
        headers = config.get("headers", {})
        timeout = config.get("timeout", 10)

        if not url:
            logger.error("Webhook URL not configured")
            return

        # Формируем payload
        payload = {
            "alert_id": alert.alert_id,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat(),
            "metadata": alert.metadata,
        }

        # Отправляем POST запрос через aiohttp
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url, json=payload, headers=headers, timeout=timeout
                ) as response:
                    response.raise_for_status()
            except Exception as e:
                logger.error("Webhook notification failed: %s", e)
                raise

    async def _send_slack_notification(self, channel: NotificationChannel, alert: Alert):
        """Отправляет уведомление в Slack (асинхронно)"""

        config = channel.config
        webhook_url = config.get("webhook_url")

        if not webhook_url:
            logger.error("Slack webhook URL not configured")
            return

        # Формируем сообщение
        severity_color = {
            "low": "#36a64f",
            "medium": "#ff9500",
            "high": "#ff0000",
            "critical": "#8b0000",
        }

        color = severity_color.get(alert.severity, "#36a64f")

        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.upper(), "short": True},
                        {"title": "Type", "value": alert.alert_type, "short": True},
                        {
                            "title": "Time",
                            "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            "short": True,
                        },
                    ],
                    "footer": "ATRA Trading Bot",
                    "ts": int(alert.timestamp.timestamp()),
                }
            ]
        }

        # Отправляем в Slack через aiohttp
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(webhook_url, json=payload, timeout=10) as response:
                    response.raise_for_status()
            except Exception as e:
                logger.error("Slack notification failed: %s", e)
                raise

    def resolve_alert(self, alert_id: str):
        """Помечает алерт как решенный"""

        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolved_time = get_utc_now()
                logger.info("Alert %s resolved", alert_id)
                break

    def add_alert_rule(self, rule: AlertRule):
        """Добавляет правило алерта"""

        self.alert_rules[rule.rule_id] = rule
        logger.info("Alert rule added: %s", rule.name)

    def remove_alert_rule(self, rule_id: str):
        """Удаляет правило алерта"""

        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            logger.info("Alert rule removed: %s", rule_id)

    def add_notification_channel(self, channel: NotificationChannel):
        """Добавляет канал уведомлений"""

        self.notification_channels[channel.channel_id] = channel
        logger.info("Notification channel added: %s", channel.channel_id)

    def remove_notification_channel(self, channel_id: str):
        """Удаляет канал уведомлений"""

        if channel_id in self.notification_channels:
            del self.notification_channels[channel_id]
            logger.info("Notification channel removed: %s", channel_id)

    def get_active_alerts(self) -> List[Dict]:
        """Возвращает активные алерты"""

        active_alerts = [a for a in self.alerts if not a.resolved]
        return [
            {
                "alert_id": a.alert_id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "timestamp": a.timestamp.isoformat(),
                "channels": a.channels,
                "metadata": a.metadata,
            }
            for a in active_alerts
        ]

    def get_alert_statistics(self) -> Dict:
        """Возвращает статистику алертов"""

        # Статистика за последние 24 часа
        day_ago = get_utc_now() - timedelta(days=1)
        recent_alerts = [a for a in self.alerts if a.timestamp > day_ago]

        total_notifications = self.stats["notifications_sent"] + self.stats["failed_notifications"]
        success_rate = (
            (self.stats["notifications_sent"] / total_notifications) * 100
            if total_notifications > 0
            else 0
        )

        return {
            "total_alerts": self.stats["total_alerts"],
            "active_alerts": len([a for a in self.alerts if not a.resolved]),
            "alerts_last_24h": len(recent_alerts),
            "alerts_by_type": dict(self.stats["alerts_by_type"]),
            "alerts_by_severity": dict(self.stats["alerts_by_severity"]),
            "notifications_sent": self.stats["notifications_sent"],
            "failed_notifications": self.stats["failed_notifications"],
            "notification_success_rate": success_rate,
            "alert_rules_count": len(self.alert_rules),
            "notification_channels_count": len(self.notification_channels),
            "timestamp": get_utc_now().isoformat(),
        }

    def cleanup_old_alerts(self):
        """Очищает старые алерты"""

        cutoff_date = get_utc_now() - timedelta(days=self.settings["alert_retention_days"])
        old_alerts = [a for a in self.alerts if a.timestamp < cutoff_date]

        for alert in old_alerts:
            self.alerts.remove(alert)

        if old_alerts:
            logger.info("Cleaned up %d old alerts", len(old_alerts))

    def save_state(self, filepath: str = "alert_system_state.json"):
        """Сохраняет состояние системы"""

        state = {
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "title": a.title,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                    "resolved": a.resolved,
                    "resolved_time": a.resolved_time.isoformat() if a.resolved_time else None,
                    "channels": a.channels,
                    "metadata": a.metadata,
                }
                for a in self.alerts
            ],
            "alert_rules": {
                k: {
                    "rule_id": v.rule_id,
                    "name": v.name,
                    "condition": v.condition,
                    "severity": v.severity,
                    "channels": v.channels,
                    "cooldown": v.cooldown,
                    "enabled": v.enabled,
                    "last_triggered": v.last_triggered.isoformat() if v.last_triggered else None,
                }
                for k, v in self.alert_rules.items()
            },
            "notification_channels": {
                k: {
                    "channel_id": v.channel_id,
                    "channel_type": v.channel_type,
                    "config": v.config,
                    "enabled": v.enabled,
                }
                for k, v in self.notification_channels.items()
            },
            "stats": self.stats,
            "settings": self.settings,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        logger.info("Alert system state saved to %s", filepath)

    def load_state(self, filepath: str = "alert_system_state.json"):
        """Загружает состояние системы"""

        if not os.path.exists(filepath):
            logger.warning("State file %s not found", filepath)
            return

        with open(filepath, encoding="utf-8") as f:
            state = json.load(f)

        # Восстанавливаем алерты
        if state.get("alerts"):
            self.alerts = []
            for alert_data in state["alerts"]:
                alert_data["timestamp"] = datetime.fromisoformat(alert_data["timestamp"])
                if alert_data.get("resolved_time"):
                    alert_data["resolved_time"] = datetime.fromisoformat(
                        alert_data["resolved_time"]
                    )
                self.alerts.append(Alert(**alert_data))

        # Восстанавливаем правила
        if state.get("alert_rules"):
            self.alert_rules = {}
            for rule_id, rule_data in state["alert_rules"].items():
                if rule_data.get("last_triggered"):
                    rule_data["last_triggered"] = datetime.fromisoformat(
                        rule_data["last_triggered"]
                    )
                self.alert_rules[rule_id] = AlertRule(**rule_data)

        # Восстанавливаем каналы
        if state.get("notification_channels"):
            self.notification_channels = {}
            for channel_id, channel_data in state["notification_channels"].items():
                self.notification_channels[channel_id] = NotificationChannel(**channel_data)

        # Восстанавливаем статистику и настройки
        if state.get("stats"):
            self.stats = state["stats"]

        if state.get("settings"):
            self.settings = state["settings"]

        logger.info("Alert system state loaded from %s", filepath)


# Глобальный экземпляр
alert_system = AlertSystem()
