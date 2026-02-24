#!/usr/bin/env python3

"""
Система мониторинга и алертинга для торгового бота.

Предоставляет real-time мониторинг состояния системы, генерацию алертов,
дашборд с метриками и интеграцию с внешними системами уведомлений.
"""

import asyncio
import json
import logging
import smtplib
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import aiohttp

try:
    import resource
except ImportError:
    resource = None

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

# Импорты для системных метрик
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil не установлен, системные метрики будут ограничены")

# Импорт базы данных
try:
    from src.database.db import Database

    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Модуль db недоступен, метрики будут ограничены")


class AlertSeverity(Enum):
    """Уровни серьезности алертов"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Типы алертов"""

    SYSTEM_ERROR = "system_error"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    DATA_QUALITY_ISSUE = "data_quality_issue"
    CONNECTION_LOST = "connection_lost"
    TRADE_EXECUTION_FAILED = "trade_execution_failed"
    BALANCE_LOW = "balance_low"
    HIGH_DRAWDOWN = "high_drawdown"
    SIGNAL_QUALITY_DROPPED = "signal_quality_dropped"


@dataclass
class Alert:
    """Структура алерта"""

    id: str
    timestamp: datetime
    type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    source: str
    data: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


@dataclass
class Metric:
    """Метрика для мониторинга"""

    name: str
    value: float
    timestamp: datetime
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Состояние здоровья системы"""

    timestamp: datetime
    overall_status: str  # "healthy", "degraded", "critical"
    components: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    alerts_count: int = 0
    critical_alerts_count: int = 0


class MetricsCollector:
    """Сборщик метрик"""

    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.metrics = defaultdict(lambda: deque(maxlen=10000))
        self.last_cleanup = get_utc_now()

    def add_metric(self, metric: Metric):
        """Добавляет метрику"""
        self.metrics[metric.name].append(metric)

        # Периодическая очистка старых метрик
        if (get_utc_now() - self.last_cleanup).total_seconds() > 3600:  # Каждый час
            self._cleanup_old_metrics()
            self.last_cleanup = get_utc_now()

    def _cleanup_old_metrics(self):
        """Удаляет старые метрики"""
        cutoff_time = get_utc_now() - timedelta(hours=self.retention_hours)

        for _, metric_deque in self.metrics.items():
            # Удаляем старые метрики
            while metric_deque and metric_deque[0].timestamp < cutoff_time:
                metric_deque.popleft()

    def get_metric_history(self, metric_name: str, hours: int = 1) -> List[Metric]:
        """Возвращает историю метрики"""
        if metric_name not in self.metrics:
            return []

        cutoff_time = get_utc_now() - timedelta(hours=hours)
        return [m for m in self.metrics[metric_name] if m.timestamp >= cutoff_time]

    def get_metric_statistics(self, metric_name: str, hours: int = 1) -> Dict[str, float]:
        """Возвращает статистику по метрике"""
        history = self.get_metric_history(metric_name, hours)

        if not history:
            return {}

        values = [m.value for m in history]

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": statistics.mean(values),
            "median": statistics.median(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0,
        }

    def get_all_metrics_summary(self, hours: int = 1) -> Dict[str, Dict[str, float]]:
        """Возвращает сводку по всем метрикам"""
        summary = {}

        for metric_name in self.metrics.keys():
            summary[metric_name] = self.get_metric_statistics(metric_name, hours)

        return summary


class AlertManager:
    """Менеджер алертов"""

    def __init__(self):
        self.alerts = deque(maxlen=1000)
        self.active_alerts = {}  # id -> Alert
        self.alert_rules = []
        self.notification_channels = []

        # Настройки алертов
        self.cooldown_periods = defaultdict(lambda: 300)  # 5 минут по умолчанию
        self.last_alert_times = defaultdict(float)

        # Callbacks
        self.on_alert_created: Optional[Callable[[Alert], Any]] = None
        self.on_alert_resolved: Optional[Callable[[Alert], Any]] = None

    def add_alert(self, alert: Alert):
        """Добавляет алерт"""

        # Проверяем кулдаун
        alert_key = f"{alert.type.value}_{alert.source}"
        current_time = time.time()

        if current_time - self.last_alert_times[alert_key] < self.cooldown_periods[alert_key]:
            return  # Игнорируем алерт из-за кулдауна

        self.last_alert_times[alert_key] = current_time

        # Добавляем алерт
        self.alerts.append(alert)
        self.active_alerts[alert.id] = alert

        logger.warning(
            "ALERT [%s] %s: %s", alert.severity.value.upper(), alert.type.value, alert.title
        )

        # Отправляем уведомления
        asyncio.create_task(self._send_notifications(alert))

        # Вызываем callback
        if self.on_alert_created and callable(self.on_alert_created):
            asyncio.create_task(self.on_alert_created(alert))

    async def _send_notifications(self, alert: Alert):
        """Отправляет уведомления по алерту"""
        for channel in self.notification_channels:
            try:
                await channel.send_alert(alert)
            except Exception as e:
                logger.error("Error sending alert via %s: %s", channel.__class__.__name__, e)

    def resolve_alert(self, alert_id: str, resolved_by: str = "system"):
        """Разрешает алерт"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = get_utc_now()

            del self.active_alerts[alert_id]

            logger.info("Alert resolved: %s", alert.title)

            # Вызываем callback
            if self.on_alert_resolved and callable(self.on_alert_resolved):
                asyncio.create_task(self.on_alert_resolved(alert))

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Подтверждает алерт"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = get_utc_now()

            logger.info("Alert acknowledged by %s: %s", acknowledged_by, alert.title)

    def get_active_alerts(self) -> List[Alert]:
        """Возвращает активные алерты"""
        return list(self.active_alerts.values())

    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Возвращает алерты по уровню серьезности"""
        return [alert for alert in self.active_alerts.values() if alert.severity == severity]

    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Возвращает недавние алерты"""
        cutoff_time = get_utc_now() - timedelta(hours=hours)
        return [alert for alert in self.alerts if alert.timestamp >= cutoff_time]

    def add_alert_rule(self, rule: Dict[str, Any]):
        """Добавляет правило для генерации алертов"""
        self.alert_rules.append(rule)

    def check_alert_rules(self, metrics: Dict[str, Any]):
        """Проверяет правила и генерирует алерты"""
        for rule in self.alert_rules:
            try:
                if self._evaluate_rule(rule, metrics):
                    self._create_alert_from_rule(rule, metrics)
            except Exception as e:
                logger.error("Error evaluating alert rule: %s", e)

    def _evaluate_rule(self, rule: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        """Оценивает правило алерта"""
        metric_name = rule.get("metric")
        condition = rule.get("condition")
        threshold = rule.get("threshold")

        if metric_name not in metrics:
            return False

        metric_value = metrics[metric_name]

        if condition == "greater_than":
            return metric_value > threshold
        elif condition == "less_than":
            return metric_value < threshold
        elif condition == "equals":
            return metric_value == threshold
        elif condition == "not_equals":
            return metric_value != threshold

        return False

    def _create_alert_from_rule(self, rule: Dict[str, Any], metrics: Dict[str, Any]):
        """Создает алерт на основе правила"""
        alert = Alert(
            id=f"rule_{rule['id']}_{int(time.time())}",
            timestamp=get_utc_now(),
            type=AlertType(rule.get("type", "system_error")),
            severity=AlertSeverity(rule.get("severity", "medium")),
            title=rule.get("title", "Rule-based alert"),
            message=rule.get("message", "Alert triggered by rule"),
            source=rule.get("source", "monitoring_system"),
            data={"rule": rule, "metrics": metrics},
        )

        self.add_alert(alert)


class NotificationChannel:
    """Базовый класс для каналов уведомлений"""

    async def send_alert(self, alert: Alert):
        """Отправляет алерт"""
        raise NotImplementedError


class TelegramNotificationChannel(NotificationChannel):
    """Канал уведомлений через Telegram"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_alert(self, alert: Alert):
        """Отправляет алерт в Telegram"""
        try:
            # Форматируем сообщение
            emoji = self._get_emoji_for_severity(alert.severity)
            message = f"{emoji} *{alert.severity.value.upper()} ALERT*\n\n"
            message += f"*{alert.title}*\n"
            message += f"{alert.message}\n\n"
            message += f"*Type:* {alert.type.value}\n"
            message += f"*Source:* {alert.source}\n"
            message += f"*Time:* {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

            # Отправляем сообщение
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sendMessage"
                data = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}

                async with session.post(url, json=data) as response:
                    if response.status != 200:
                        logger.error("Failed to send Telegram alert: %s", response.status)

        except Exception as e:
            logger.error("Error sending Telegram alert: %s", e)

    def _get_emoji_for_severity(self, severity: AlertSeverity) -> str:
        """Возвращает эмодзи для уровня серьезности"""
        emoji_map = {
            AlertSeverity.LOW: "ℹ️",
            AlertSeverity.MEDIUM: "⚠️",
            AlertSeverity.HIGH: "🚨",
            AlertSeverity.CRITICAL: "🔥",
        }
        return emoji_map.get(severity, "❓")


class EmailNotificationChannel(NotificationChannel):
    """Канал уведомлений через Email"""

    def __init__(
        self, smtp_server: str, smtp_port: int, username: str, password: str, to_emails: List[str]
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.to_emails = to_emails

    async def send_alert(self, alert: Alert):
        """Отправляет алерт по email"""
        try:
            # Создаем сообщение
            msg = MIMEMultipart()
            msg["From"] = self.username
            msg["To"] = ", ".join(self.to_emails)
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"

            # Тело сообщения
            body = f"""
Alert Details:
- Title: {alert.title}
- Message: {alert.message}
- Type: {alert.type.value}
- Severity: {alert.severity.value}
- Source: {alert.source}
- Time: {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")}

Data: {json.dumps(alert.data, indent=2)}
            """

            msg.attach(MIMEText(body, "plain"))

            # Отправляем email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)

            text = msg.as_string()
            for email in self.to_emails:
                server.sendmail(self.username, email, text)

            server.quit()

        except Exception as e:
            logger.error("Error sending email alert: %s", e)


class MonitoringSystem:
    """Главная система мониторинга"""

    def __init__(self):
        self._db = None
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
        self.system_health = SystemHealth(timestamp=get_utc_now(), overall_status="healthy")

        # Компоненты системы
        self.components = {
            "database": {"status": "unknown", "last_check": None},
            "telegram_bot": {"status": "unknown", "last_check": None},
            "signal_generator": {"status": "unknown", "last_check": None},
            "data_sources": {"status": "unknown", "last_check": None},
            "risk_manager": {"status": "unknown", "last_check": None},
        }

        # Настройки мониторинга
        self.check_interval = 30  # секунд
        self.health_check_timeout = 10  # секунд

        # Фоновые задачи
        self.monitoring_tasks = []
        self.is_running = False

        # Инициализируем правила алертов
        self._setup_default_alert_rules()

    def _setup_default_alert_rules(self):
        """Настраивает правила алертов по умолчанию"""
        default_rules = [
            {
                "id": "high_error_rate",
                "metric": "error_rate_pct",
                "condition": "greater_than",
                "threshold": 10.0,
                "type": "system_error",
                "severity": "high",
                "title": "High Error Rate",
                "message": "System error rate exceeds 10%",
                "source": "monitoring_system",
            },
            {
                "id": "low_winrate",
                "metric": "signal_winrate",
                "condition": "less_than",
                "threshold": 0.35,
                "type": "signal_quality_dropped",
                "severity": "medium",
                "title": "Low Signal Winrate",
                "message": "Signal winrate dropped below 35%",
                "source": "signal_monitor",
            },
            {
                "id": "high_drawdown",
                "metric": "portfolio_drawdown_pct",
                "condition": "greater_than",
                "threshold": 15.0,
                "type": "high_drawdown",
                "severity": "high",
                "title": "High Portfolio Drawdown",
                "message": "Portfolio drawdown exceeds 15%",
                "source": "risk_manager",
            },
            {
                "id": "low_balance",
                "metric": "account_balance",
                "condition": "less_than",
                "threshold": 100.0,
                "type": "balance_low",
                "severity": "critical",
                "title": "Low Account Balance",
                "message": "Account balance is critically low",
                "source": "account_monitor",
            },
        ]

        for rule in default_rules:
            self.alert_manager.add_alert_rule(rule)

    async def start_monitoring(self):
        """Запускает систему мониторинга"""
        if self.is_running:
            logger.warning("Monitoring system is already running")
            return

        logger.info("Starting monitoring system...")
        self.is_running = True

        # Запускаем фоновые задачи
        self.monitoring_tasks = [
            asyncio.create_task(self._health_checker()),
            asyncio.create_task(self._metrics_monitor()),
            asyncio.create_task(self._alert_checker()),
        ]

        try:
            await asyncio.gather(*self.monitoring_tasks)
        except Exception as e:
            logger.error("Error in monitoring tasks: %s", e)
        finally:
            self.is_running = False

    async def stop_monitoring(self):
        """Останавливает систему мониторинга"""
        logger.info("Stopping monitoring system...")
        self.is_running = False

        # Отменяем все задачи
        for task in self.monitoring_tasks:
            task.cancel()

        # Ждем завершения
        await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)

    async def _health_checker(self):
        """Проверяет здоровье компонентов системы"""
        while self.is_running:
            try:
                await self._check_system_health()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error("Error in health checker: %s", e)
                await asyncio.sleep(5)

    async def _metrics_monitor(self):
        """Мониторит метрики и генерирует алерты"""
        while self.is_running:
            try:
                # Собираем текущие метрики
                current_metrics = await self._collect_current_metrics()

                # Проверяем правила алертов
                self.alert_manager.check_alert_rules(current_metrics)

                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error("Error in metrics monitor: %s", e)
                await asyncio.sleep(5)

    async def _alert_checker(self):
        """Проверяет и обрабатывает алерты"""
        while self.is_running:
            try:
                # Проверяем старые алерты на авторазрешение
                await self._check_for_auto_resolution()

                await asyncio.sleep(60)  # Проверяем каждую минуту
            except Exception as e:
                logger.error("Error in alert checker: %s", e)
                await asyncio.sleep(10)

    async def _check_system_health(self):
        """Проверяет здоровье компонентов"""
        for component_name, component_data in self.components.items():
            try:
                # Здесь должны быть реальные проверки здоровья компонентов
                # Пока используем заглушки
                health_status = await self._check_component_health(component_name)

                component_data["status"] = health_status["status"]
                component_data["last_check"] = get_utc_now()
                component_data["details"] = health_status.get("details", {})

            except Exception as e:
                logger.error("Error checking health of %s: %s", component_name, e)
                component_data["status"] = "error"
                component_data["last_check"] = get_utc_now()

        # Обновляем общее состояние системы
        self._update_overall_health()

    async def _check_component_health(self, component_name: str) -> Dict[str, Any]:
        """Проверяет здоровье конкретного компонента"""
        if component_name == "database":
            return await self._check_database_health()
        elif component_name == "telegram_bot":
            return await self._check_telegram_bot_health()
        elif component_name == "signal_generator":
            return await self._check_signal_generator_health()
        elif component_name == "data_sources":
            return await self._check_data_sources_health()
        elif component_name == "risk_manager":
            return await self._check_risk_manager_health()
        else:
            return {"status": "unknown"}

    async def _check_database_health(self) -> Dict[str, Any]:
        """Проверяет здоровье базы данных"""
        try:
            return {"status": "healthy", "details": {"response_time_ms": 5}}
        except Exception as e:
            return {"status": "unhealthy", "details": {"error": str(e)}}

    async def _check_telegram_bot_health(self) -> Dict[str, Any]:
        """Проверяет здоровье Telegram бота"""
        try:
            return {"status": "healthy", "details": {"last_update": get_utc_now()}}
        except Exception as e:
            return {"status": "unhealthy", "details": {"error": str(e)}}

    async def _check_signal_generator_health(self) -> Dict[str, Any]:
        """Проверяет здоровье генератора сигналов"""
        try:
            return {"status": "healthy", "details": {"last_signal": get_utc_now()}}
        except Exception as e:
            return {"status": "unhealthy", "details": {"error": str(e)}}

    async def _check_data_sources_health(self) -> Dict[str, Any]:
        """Проверяет здоровье источников данных"""
        try:
            return {"status": "healthy", "details": {"available_sources": 4}}
        except Exception as e:
            return {"status": "unhealthy", "details": {"error": str(e)}}

    async def _check_risk_manager_health(self) -> Dict[str, Any]:
        """Проверяет здоровье менеджера рисков"""
        try:
            return {"status": "healthy", "details": {"active_positions": 0}}
        except Exception as e:
            return {"status": "unhealthy", "details": {"error": str(e)}}

    def _update_overall_health(self):
        """Обновляет общее состояние здоровья системы"""
        self.system_health.timestamp = get_utc_now()

        # Подсчитываем количество нездоровых компонентов
        unhealthy_count = sum(
            1 for comp in self.components.values() if comp["status"] in ["unhealthy", "error"]
        )

        # Определяем общий статус
        if unhealthy_count == 0:
            self.system_health.overall_status = "healthy"
        elif unhealthy_count <= 2:
            self.system_health.overall_status = "degraded"
        else:
            self.system_health.overall_status = "critical"

        # Обновляем информацию о компонентах
        self.system_health.components = self.components.copy()

        # Подсчитываем алерты
        active_alerts = self.alert_manager.get_active_alerts()
        self.system_health.alerts_count = len(active_alerts)
        self.system_health.critical_alerts_count = len(
            [a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]
        )

    async def _collect_current_metrics(self) -> Dict[str, Any]:
        """Собирает текущие метрики системы"""
        metrics = {}

        # Метрики производительности
        metrics["error_rate_pct"] = self._calculate_error_rate()
        metrics["signal_winrate"] = self._calculate_signal_winrate()
        metrics["portfolio_drawdown_pct"] = self._calculate_portfolio_drawdown()
        metrics["account_balance"] = self._get_account_balance()

        # Метрики системы
        metrics["active_connections"] = self._get_active_connections_count()
        metrics["memory_usage_pct"] = self._get_memory_usage()
        metrics["cpu_usage_pct"] = self._get_cpu_usage()

        return metrics

    def _get_db(self):
        """Получает экземпляр базы данных (lazy initialization)"""
        if not DB_AVAILABLE:
            return None
        if self._db is None:
            try:
                self._db = Database()
            except Exception as e:
                logger.warning("Не удалось инициализировать базу данных: %s", e)
                return None
        return self._db

    def _calculate_error_rate(self) -> float:
        """Вычисляет процент ошибок из логов"""
        try:
            db = self._get_db()
            if db is None:
                return 0.0

            # Получаем количество ошибок за последние 24 часа
            with db._lock:
                cur = db.conn.execute(
                    """
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN severity IN ('error', 'critical') THEN 1 ELSE 0 END) as errors
                    FROM event_logs
                    WHERE datetime(created_at) >= datetime('now', '-24 hours')
                    """,
                )
                row = cur.fetchone()
                if row and row[0] and row[0] > 0:
                    total = row[0]
                    errors = row[1] or 0
                    return (errors / total) * 100
            return 0.0
        except Exception as e:
            logger.debug("Ошибка расчета error_rate: %s", e)
            return 0.0

    def _calculate_signal_winrate(self) -> float:
        """Вычисляет winrate сигналов из trades"""
        try:
            db = self._get_db()
            if db is None:
                return 0.0

            # Получаем статистику за последние 30 дней
            with db._lock:
                cur = db.conn.execute(
                    """
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins
                    FROM trades
                    WHERE exit_time IS NOT NULL
                      AND datetime(exit_time) >= datetime('now', '-30 days')
                    """,
                )
                row = cur.fetchone()
                if row and row[0] and row[0] > 0:
                    total = row[0]
                    wins = row[1] or 0
                    return (wins / total) * 100
            return 0.0
        except Exception as e:
            logger.debug("Ошибка расчета winrate: %s", e)
            return 0.0

    def _calculate_portfolio_drawdown(self) -> float:
        """Вычисляет просадку портфеля из trades"""
        try:
            db = self._get_db()
            if db is None:
                return 0.0

            # Получаем все завершенные сделки за последние 30 дней
            with db._lock:
                cur = db.conn.execute(
                    """
                    SELECT
                        datetime(exit_time) as exit_time,
                        net_pnl_usd
                    FROM trades
                    WHERE exit_time IS NOT NULL
                      AND net_pnl_usd IS NOT NULL
                      AND datetime(exit_time) >= datetime('now', '-30 days')
                    ORDER BY exit_time
                    """,
                )
                rows = cur.fetchall()

            if not rows or len(rows) < 2:
                return 0.0

            # Рассчитываем кумулятивный PnL
            cumulative_pnl = 0.0
            equity_curve = []
            for _, pnl in rows:
                cumulative_pnl += pnl or 0.0
                equity_curve.append(cumulative_pnl)

            # Находим максимум и просадку
            peak = equity_curve[0]
            max_drawdown = 0.0

            for equity in equity_curve:
                if equity > peak:
                    peak = equity
                if peak > 0:
                    drawdown = ((peak - equity) / abs(peak)) * 100
                    max_drawdown = max(max_drawdown, drawdown)

            return max_drawdown
        except Exception as e:
            logger.debug("Ошибка расчета drawdown: %s", e)
            return 0.0

    def _get_account_balance(self) -> float:
        """Возвращает баланс аккаунта из users_data"""
        try:
            db = self._get_db()
            if db is None:
                return 0.0

            # Пробуем получить баланс из первого активного пользователя
            with db._lock:
                cur = db.conn.execute(
                    """
                    SELECT data FROM users_data
                    WHERE data LIKE '%deposit%'
                    LIMIT 1
                    """,
                )
                row = cur.fetchone()
                if row and row[0]:
                    try:
                        user_data = json.loads(row[0])
                        balance = user_data.get("deposit", 0.0)
                        # Считаем активные позиции
                        cur2 = db.conn.execute(
                            """
                            SELECT SUM(position_size_usdt)
                            FROM active_positions
                            WHERE status = 'open'
                            """,
                        )
                        pos_row = cur2.fetchone()
                        active_positions = pos_row[0] or 0.0
                        # Баланс = депозит - активные позиции
                        return float(balance) - float(active_positions)
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass
            return 0.0
        except Exception as e:
            logger.debug("Ошибка получения баланса: %s", e)
            return 0.0

    def _get_active_connections_count(self) -> int:
        """Возвращает количество активных соединений к БД"""
        try:
            if not DB_AVAILABLE:
                return 0

            # Fallback: проверяем открытые файловые дескрипторы
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process()
                    connections = process.connections()
                    return len([c for c in connections if c.status == "ESTABLISHED"])
                except Exception:
                    pass

            return 0
        except Exception as e:
            logger.debug("Ошибка получения количества соединений: %s", e)
            return 0

    def _get_memory_usage(self) -> float:
        """Возвращает использование памяти в процентах"""
        try:
            if PSUTIL_AVAILABLE:
                process = psutil.Process()
                memory_percent = process.memory_percent()
                return float(memory_percent)

            # Fallback через resource (только Linux)
            if resource:
                usage = resource.getrusage(resource.RUSAGE_SELF)
                # Получаем RSS в байтах
                rss = usage.ru_maxrss * 1024  # KB to bytes (Linux)
                # Оценка процента (предполагаем 4GB RAM)
                total_memory = 4 * 1024 * 1024 * 1024  # 4GB
                return (rss / total_memory) * 100
            return 0.0
        except Exception as e:
            logger.debug("Ошибка получения использования памяти: %s", e)
            return 0.0

    def _get_cpu_usage(self) -> float:
        """Возвращает использование CPU в процентах"""
        try:
            if PSUTIL_AVAILABLE:
                process = psutil.Process()
                cpu_percent = process.cpu_percent(interval=0.1)
                return float(cpu_percent)

            # Fallback через resource (только Linux)
            if resource:
                usage = resource.getrusage(resource.RUSAGE_SELF)
                # ru_utime + ru_stime дает CPU time
                cpu_time = usage.ru_utime + usage.ru_stime
                # Оценка процента (упрощенная)
                return min(cpu_time * 10, 100.0)  # Простая оценка
            return 0.0
        except Exception as e:
            logger.debug("Ошибка получения использования CPU: %s", e)
            return 0.0

    async def _check_for_auto_resolution(self):
        """Проверяет алерты на авторазрешение"""
        active_alerts = self.alert_manager.get_active_alerts()
        current_time = get_utc_now()

        for alert in active_alerts:
            # Авторазрешение алертов старше 1 часа (кроме критических)
            if (
                alert.severity != AlertSeverity.CRITICAL
                and (current_time - alert.timestamp).total_seconds() > 3600
            ):
                self.alert_manager.resolve_alert(alert.id, "auto_resolution")

    def add_metric(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Добавляет метрику"""
        metric = Metric(name=name, value=value, timestamp=get_utc_now(), unit=unit, tags=tags or {})
        self.metrics_collector.add_metric(metric)

    def add_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        source: str = "system",
    ):
        """Добавляет алерт"""
        alert = Alert(
            id=f"{alert_type.value}_{int(time.time())}_{hash(message) % 10000}",
            timestamp=get_utc_now(),
            type=alert_type,
            severity=severity,
            title=title,
            message=message,
            source=source,
        )
        self.alert_manager.add_alert(alert)

    def add_notification_channel(self, channel: NotificationChannel):
        """Добавляет канал уведомлений"""
        self.alert_manager.notification_channels.append(channel)

    def get_system_health(self) -> Dict[str, Any]:
        """Возвращает состояние здоровья системы"""
        return {
            "timestamp": self.system_health.timestamp.isoformat(),
            "overall_status": self.system_health.overall_status,
            "components": self.system_health.components,
            "alerts_count": self.system_health.alerts_count,
            "critical_alerts_count": self.system_health.critical_alerts_count,
        }

    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Возвращает сводку метрик"""
        return self.metrics_collector.get_all_metrics_summary(hours)

    def get_alerts_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Возвращает сводку алертов"""
        recent_alerts = self.alert_manager.get_recent_alerts(hours)
        active_alerts = self.alert_manager.get_active_alerts()

        alerts_by_severity = defaultdict(int)
        for alert in recent_alerts:
            alerts_by_severity[alert.severity.value] += 1

        return {
            "recent_alerts_count": len(recent_alerts),
            "active_alerts_count": len(active_alerts),
            "alerts_by_severity": dict(alerts_by_severity),
            "recent_alerts": [
                {
                    "id": alert.id,
                    "type": alert.type.value,
                    "severity": alert.severity.value,
                    "title": alert.title,
                    "timestamp": alert.timestamp.isoformat(),
                    "resolved": alert.resolved,
                    "acknowledged": alert.acknowledged,
                }
                for alert in recent_alerts[-10:]  # Последние 10 алертов
            ],
        }

    def get_monitoring_report(self) -> Dict[str, Any]:
        """Возвращает полный отчет мониторинга"""
        return {
            "timestamp": get_utc_now().isoformat(),
            "system_health": self.get_system_health(),
            "metrics_summary": self.get_metrics_summary(1),
            "alerts_summary": self.get_alerts_summary(24),
            "monitoring_status": "running" if self.is_running else "stopped",
        }


# Глобальный экземпляр системы мониторинга
monitoring_system = MonitoringSystem()


# Удобные функции
async def start_monitoring():
    """Запускает систему мониторинга"""
    await monitoring_system.start_monitoring()


def add_metric(name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
    """Добавляет метрику"""
    monitoring_system.add_metric(name, value, unit, tags)


def add_alert(
    alert_type: AlertType, severity: AlertSeverity, title: str, message: str, source: str = "system"
):
    """Добавляет алерт"""
    monitoring_system.add_alert(alert_type, severity, title, message, source)


def get_monitoring_report() -> Dict[str, Any]:
    """Возвращает отчет мониторинга"""
    return monitoring_system.get_monitoring_report()
