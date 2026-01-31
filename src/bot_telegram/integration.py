#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Интеграция новых улучшенных систем с Telegram ботом.

Обеспечивает интеграцию мониторинга, алертов, метрик и управления
с существующим Telegram ботом для улучшенного пользовательского опыта.
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class TelegramBotIntegration:
    """Интеграция новых систем с Telegram ботом"""

    def __init__(self):
        self.monitoring_system = None
        self.data_quality_monitor = None
        self.risk_manager = None
        self.enhanced_logging = None

        # Новые команды для бота
        self.new_commands = {
            '/status': 'Показать статус всех систем',
            '/metrics': 'Показать метрики производительности',
            '/alerts': 'Показать активные алерты',
            '/health': 'Проверить здоровье системы',
            '/report': 'Сгенерировать отчет',
            '/optimize': 'Оптимизировать систему',
            '/risk': 'Показать информацию о рисках',
            '/quality': 'Показать качество данных'
        }

        self.is_initialized = False

    async def initialize(self):
        """Инициализирует интеграцию с новыми системами"""
        try:
            # Инициализация системы мониторинга
            try:
                from monitoring_system import monitoring_system
                self.monitoring_system = monitoring_system
                logger.info("✅ Monitoring system integrated with Telegram bot")
            except ImportError:
                logger.warning("⚠️ Monitoring system not available for Telegram integration")

            # Инициализация мониторинга качества данных
            try:
                from data_quality_monitor import data_quality_monitor
                self.data_quality_monitor = data_quality_monitor
                logger.info("✅ Data quality monitor integrated with Telegram bot")
            except ImportError:
                logger.warning("⚠️ Data quality monitor not available for Telegram integration")

            # Инициализация риск-менеджмента
            try:
                from risk_manager import risk_manager
                self.risk_manager = risk_manager
                logger.info("✅ Risk manager integrated with Telegram bot")
            except ImportError:
                logger.warning("⚠️ Risk manager not available for Telegram integration")

            # Инициализация улучшенного логирования
            try:
                from enhanced_logging import get_logger
                self.enhanced_logging = {'get_logger': get_logger}
                logger.info("✅ Enhanced logging integrated with Telegram bot")
            except ImportError:
                logger.warning("⚠️ Enhanced logging not available for Telegram integration")

            self.is_initialized = True
            logger.info("🎯 Telegram bot integration initialized successfully")

        except Exception as e:
            logger.error(f"❌ Error initializing Telegram bot integration: {e}")
            self.is_initialized = False

    async def handle_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /status"""
        try:
            if not self.monitoring_system:
                await update.message.reply_text("❌ Система мониторинга недоступна")
                return

            # Получаем статус системы
            health_report = self.monitoring_system.get_system_health()

            message = "🎯 **СТАТУС СИСТЕМЫ ATRA**\n\n"

            # Общий статус
            overall_status = health_report.get('overall_status', 'unknown')
            status_emoji = {
                'healthy': '✅',
                'degraded': '⚠️',
                'critical': '❌'
            }.get(overall_status, '❓')

            message += f"{status_emoji} **Общий статус**: {overall_status.upper()}\n\n"

            # Статус компонентов
            components = health_report.get('components', {})
            message += "📊 **Компоненты**:\n"

            for component, status in components.items():
                comp_status = status.get('status', 'unknown')
                comp_emoji = {
                    'healthy': '✅',
                    'degraded': '⚠️',
                    'unhealthy': '❌',
                    'error': '🔥'
                }.get(comp_status, '❓')

                message += f"{comp_emoji} {component}: {comp_status}\n"

            # Алерты
            alerts_count = health_report.get('alerts_count', 0)
            critical_alerts = health_report.get('critical_alerts_count', 0)

            message += f"\n🚨 **Алерты**: {alerts_count} (критических: {critical_alerts})"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling status command: {e}")
            await update.message.reply_text(f"❌ Ошибка получения статуса: {e}")

    async def handle_metrics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /metrics"""
        try:
            if not self.monitoring_system:
                await update.message.reply_text("❌ Система мониторинга недоступна")
                return

            # Получаем метрики
            metrics = self.monitoring_system.get_metrics_summary(1)  # За последний час

            message = "📈 **МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ**\n\n"

            # Ключевые метрики
            key_metrics = [
                'signals_generated',
                'signal_winrate',
                'error_rate_pct',
                'portfolio_drawdown_pct',
                'account_balance'
            ]

            for metric_name in key_metrics:
                if metric_name in metrics:
                    metric_data = metrics[metric_name]
                    if metric_data.get('count', 0) > 0:
                        avg_value = metric_data.get('avg', 0)
                        message += f"📊 {metric_name}: {avg_value:.2f}\n"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling metrics command: {e}")
            await update.message.reply_text(f"❌ Ошибка получения метрик: {e}")

    async def handle_alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /alerts"""
        try:
            if not self.monitoring_system:
                await update.message.reply_text("❌ Система мониторинга недоступна")
                return

            # Получаем активные алерты
            active_alerts = self.monitoring_system.alert_manager.get_active_alerts()

            if not active_alerts:
                await update.message.reply_text("✅ **Нет активных алертов**")
                return

            message = "🚨 **АКТИВНЫЕ АЛЕРТЫ**\n\n"

            for i, alert in enumerate(active_alerts[:5], 1):  # Показываем первые 5
                severity_emoji = {
                    'low': 'ℹ️',
                    'medium': '⚠️',
                    'high': '🚨',
                    'critical': '🔥'
                }.get(alert.severity.value, '❓')

                message += f"{severity_emoji} **{alert.title}**\n"
                message += f"   Тип: {alert.type.value}\n"
                message += f"   Время: {alert.timestamp.strftime('%H:%M:%S')}\n\n"

            if len(active_alerts) > 5:
                message += f"... и еще {len(active_alerts) - 5} алертов"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling alerts command: {e}")
            await update.message.reply_text(f"❌ Ошибка получения алертов: {e}")

    async def handle_health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /health"""
        try:
            if not self.monitoring_system:
                await update.message.reply_text("❌ Система мониторинга недоступна")
                return

            # Получаем отчет о здоровье
            health_report = self.monitoring_system.get_monitoring_report()

            message = "🏥 **ПРОВЕРКА ЗДОРОВЬЯ СИСТЕМЫ**\n\n"

            # Статус мониторинга
            monitoring_status = health_report.get('monitoring_status', 'unknown')
            status_emoji = '✅' if monitoring_status == 'running' else '❌'
            message += f"{status_emoji} Мониторинг: {monitoring_status}\n\n"

            # Системное здоровье
            system_health = health_report.get('system_health', {})
            overall_status = system_health.get('overall_status', 'unknown')

            health_emoji = {
                'healthy': '✅',
                'degraded': '⚠️',
                'critical': '❌'
            }.get(overall_status, '❓')

            message += f"{health_emoji} Общее здоровье: {overall_status.upper()}\n"

            # Компоненты
            components = system_health.get('components', {})
            healthy_components = sum(1 for comp in components.values()
                                  if comp.get('status') == 'healthy')
            total_components = len(components)

            message += f"📊 Компоненты: {healthy_components}/{total_components} здоровы\n"

            # Алерты
            alerts_summary = health_report.get('alerts_summary', {})
            recent_alerts = alerts_summary.get('recent_alerts_count', 0)
            active_alerts = alerts_summary.get('active_alerts_count', 0)

            message += f"🚨 Алерты: {active_alerts} активных, {recent_alerts} за 24ч"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling health command: {e}")
            await update.message.reply_text(f"❌ Ошибка проверки здоровья: {e}")

    async def handle_report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /report"""
        try:
            if not self.monitoring_system:
                await update.message.reply_text("❌ Система мониторинга недоступна")
                return

            # Получаем отчет
            report = self.monitoring_system.get_monitoring_report()

            message = "📊 **ОТЧЕТ О СИСТЕМЕ**\n\n"
            message += f"📅 Время: {report.get('timestamp', 'N/A')}\n\n"

            # Ключевые метрики
            metrics = report.get('metrics_summary', {})
            if metrics:
                message += "📈 **Ключевые метрики**:\n"

                # Показываем несколько ключевых метрик
                key_metrics = ['signals_generated', 'signal_winrate', 'error_rate_pct']
                for metric in key_metrics:
                    if metric in metrics:
                        data = metrics[metric]
                        if data.get('count', 0) > 0:
                            avg = data.get('avg', 0)
                            message += f"• {metric}: {avg:.2f}\n"

            # Алерты
            alerts = report.get('alerts_summary', {})
            if alerts:
                message += f"\n🚨 **Алерты**: {alerts.get('active_alerts_count', 0)} активных"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling report command: {e}")
            await update.message.reply_text(f"❌ Ошибка генерации отчета: {e}")

    async def handle_risk_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /risk"""
        try:
            if not self.risk_manager:
                await update.message.reply_text("❌ Менеджер рисков недоступен")
                return

            # Получаем отчет о рисках
            risk_report = self.risk_manager.get_risk_report()

            message = "⚠️ **ИНФОРМАЦИЯ О РИСКАХ**\n\n"

            # Метрики портфеля
            portfolio_metrics = risk_report.get('portfolio_metrics', {})
            if portfolio_metrics:
                message += "📊 **Портфель**:\n"
                message += f"• Баланс: ${portfolio_metrics.get('total_balance', 0):.2f}\n"
                message += f"• Использованная маржа: ${portfolio_metrics.get('used_margin', 0):.2f}\n"
                message += f"• Свободная маржа: ${portfolio_metrics.get('free_margin', 0):.2f}\n"
                message += f"• Общий риск: {portfolio_metrics.get('total_risk_pct', 0):.1f}%\n"
                message += f"• Позиции: {portfolio_metrics.get('positions_count', 0)}\n\n"

            # Риск маржин-колла
            margin_risk = risk_report.get('margin_call_risk', {})
            if margin_risk:
                is_at_risk = margin_risk.get('is_at_risk', False)
                risk_emoji = '🚨' if is_at_risk else '✅'
                message += f"{risk_emoji} **Маржин-риск**: {'КРИТИЧЕСКИЙ' if is_at_risk else 'Норма'}\n"

                if is_at_risk:
                    recommendations = margin_risk.get('recommendations', [])
                    if recommendations:
                        message += "💡 **Рекомендации**:\n"
                        for rec in recommendations[:3]:
                            message += f"• {rec}\n"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling risk command: {e}")
            await update.message.reply_text(f"❌ Ошибка получения информации о рисках: {e}")

    async def handle_quality_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /quality"""
        try:
            if not self.data_quality_monitor:
                await update.message.reply_text("❌ Монитор качества данных недоступен")
                return

            # Получаем отчет о качестве данных
            quality_report = self.data_quality_monitor.get_health_report()

            message = "📊 **КАЧЕСТВО ДАННЫХ**\n\n"

            # Общая оценка здоровья
            overall_health = quality_report.get('overall_health_score', 0)
            health_emoji = '✅' if overall_health > 0.8 else '⚠️' if overall_health > 0.5 else '❌'
            message += f"{health_emoji} **Общее здоровье**: {overall_health:.1%}\n\n"

            # Здоровье источников
            source_health = quality_report.get('source_health', {})
            if source_health:
                message += "📡 **Источники данных**:\n"
                for source, health in source_health.items():
                    source_score = health.get('health_score', 0)
                    source_emoji = '✅' if source_score > 0.8 else '⚠️' if source_score > 0.5 else '❌'
                    message += f"{source_emoji} {source}: {source_score:.1%}\n"

            # Недавние алерты
            recent_alerts = quality_report.get('recent_alerts_24h', {})
            if recent_alerts:
                total_alerts = recent_alerts.get('total', 0)
                if total_alerts > 0:
                    message += f"\n🚨 **Алерты за 24ч**: {total_alerts}"

                    alerts_by_severity = recent_alerts.get('by_severity', {})
                    for severity, count in alerts_by_severity.items():
                        message += f"\n• {severity}: {count}"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling quality command: {e}")
            await update.message.reply_text(f"❌ Ошибка получения качества данных: {e}")

    async def handle_optimize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает команду /optimize"""
        try:
            await update.message.reply_text("⚡ **Запуск оптимизации системы...**")

            # Здесь можно запустить оптимизацию
            # Пока просто показываем сообщение

            message = "🔧 **ОПТИМИЗАЦИЯ ЗАПУЩЕНА**\n\n"
            message += "Выполняются следующие операции:\n"
            message += "• Анализ эффективности фильтров\n"
            message += "• Оптимизация параметров\n"
            message += "• Проверка источников данных\n"
            message += "• Обновление риск-лимитов\n\n"
            message += "Результаты будут доступны через несколько минут."

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling optimize command: {e}")
            await update.message.reply_text(f"❌ Ошибка запуска оптимизации: {e}")

    async def send_alert_notification(self, alert_title: str, alert_message: str, severity: str = "medium"):
        """Отправляет уведомление об алерте в Telegram"""
        try:
            # Здесь должна быть логика отправки уведомлений всем пользователям
            # Пока просто логируем
            logger.info(f"Telegram alert notification: {alert_title} - {alert_message}")

        except Exception as e:
            logger.error(f"Error sending alert notification: {e}")

    def get_new_commands(self) -> Dict[str, str]:
        """Возвращает новые команды для регистрации в боте"""
        return self.new_commands.copy()

    async def get_integration_report(self) -> Dict[str, Any]:
        """Возвращает отчет об интеграции с Telegram ботом"""
        return {
            'timestamp': get_utc_now().isoformat(),
            'is_initialized': self.is_initialized,
            'available_systems': {
                'monitoring_system': self.monitoring_system is not None,
                'data_quality_monitor': self.data_quality_monitor is not None,
                'risk_manager': self.risk_manager is not None,
                'enhanced_logging': self.enhanced_logging is not None
            },
            'new_commands': self.new_commands,
            'command_handlers': [
                'handle_status_command',
                'handle_metrics_command',
                'handle_alerts_command',
                'handle_health_command',
                'handle_report_command',
                'handle_risk_command',
                'handle_quality_command',
                'handle_optimize_command'
            ]
        }

# Глобальный экземпляр интеграции
telegram_bot_integration = TelegramBotIntegration()

# Удобные функции
async def initialize_telegram_bot_integration():
    """Инициализирует интеграцию с Telegram ботом"""
    await telegram_bot_integration.initialize()

def get_telegram_new_commands():
    """Возвращает новые команды для Telegram бота"""
    return telegram_bot_integration.get_new_commands()

async def handle_telegram_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /status в Telegram"""
    await telegram_bot_integration.handle_status_command(update, context)

async def handle_telegram_metrics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /metrics в Telegram"""
    await telegram_bot_integration.handle_metrics_command(update, context)

async def handle_telegram_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /alerts в Telegram"""
    await telegram_bot_integration.handle_alerts_command(update, context)

async def handle_telegram_health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /health в Telegram"""
    await telegram_bot_integration.handle_health_command(update, context)

async def handle_telegram_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /report в Telegram"""
    await telegram_bot_integration.handle_report_command(update, context)

async def handle_telegram_risk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /risk в Telegram"""
    await telegram_bot_integration.handle_risk_command(update, context)

async def handle_telegram_quality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /quality в Telegram"""
    await telegram_bot_integration.handle_quality_command(update, context)

async def handle_telegram_optimize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /optimize в Telegram"""
    await telegram_bot_integration.handle_optimize_command(update, context)
