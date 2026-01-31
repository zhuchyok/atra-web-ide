"""
Модуль инициализации систем для торгового бота ATRA.

Содержит функции для инициализации различных систем,
включая интеграции, мониторинг и настройки.
"""

import os
import json
import logging
from datetime import datetime

# Импорты для интегрированных систем
try:
    from system_integration import initialize_improved_systems
    SYSTEM_INTEGRATION_AVAILABLE = True
except ImportError:
    SYSTEM_INTEGRATION_AVAILABLE = False

try:
    from monitoring_system import start_monitoring
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

try:
    from signal_live_integration import initialize_signal_live_integration
    SIGNAL_LIVE_INTEGRATION_AVAILABLE = True
except ImportError:
    SIGNAL_LIVE_INTEGRATION_AVAILABLE = False

try:
    from telegram_bot_integration import initialize_telegram_bot_integration
    TELEGRAM_BOT_INTEGRATION_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_INTEGRATION_AVAILABLE = False

try:
    from backtests.backtest_integration import initialize_backtest_integration
    BACKTEST_INTEGRATION_AVAILABLE = True
except ImportError:
    BACKTEST_INTEGRATION_AVAILABLE = False

try:
    from audit_systems import audit_systems
    AUDIT_SYSTEMS_AVAILABLE = True
except ImportError:
    AUDIT_SYSTEMS_AVAILABLE = False

logger = logging.getLogger(__name__)


async def initialize_system_integrations():
    """Инициализирует интегрированные системы"""
    integration_results = {}
    monitoring_task = None

    if SYSTEM_INTEGRATION_AVAILABLE:
        try:
            logger.info("🔧 Инициализация интегрированных систем...")
            integration_results = await initialize_improved_systems()

            # Запускаем мониторинг здоровья систем
            if integration_results.get('monitoring', False) and MONITORING_AVAILABLE:
                import asyncio
                monitoring_task = asyncio.create_task(start_monitoring())
                logger.info("✅ Система мониторинга запущена")
            else:
                monitoring_task = None

            # Инициализируем интеграции с существующими системами
            if SIGNAL_LIVE_INTEGRATION_AVAILABLE:
                try:
                    await initialize_signal_live_integration()
                    logger.info("✅ Signal live integration initialized")
                except (ValueError, TypeError, KeyError, RuntimeError, OSError, ConnectionError) as e:
                    logger.warning("⚠️ Signal live integration error: %s", e)

            if TELEGRAM_BOT_INTEGRATION_AVAILABLE:
                try:
                    await initialize_telegram_bot_integration()
                    logger.info("✅ Telegram bot integration initialized")
                except (ValueError, TypeError, KeyError, RuntimeError, OSError, ConnectionError) as e:
                    logger.warning("⚠️ Telegram bot integration error: %s", e)

            if BACKTEST_INTEGRATION_AVAILABLE:
                try:
                    await initialize_backtest_integration()
                    logger.info("✅ Backtest integration initialized")
                except (ValueError, TypeError, KeyError, RuntimeError, OSError, ConnectionError) as e:
                    logger.warning("⚠️ Backtest integration error: %s", e)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError, ConnectionError) as e:
            logger.warning("⚠️ Ошибка инициализации интегрированных систем: %s", e)
            monitoring_task = None
            integration_results = {}
    else:
        logger.warning("⚠️ Интегрированные системы недоступны")
        monitoring_task = None
        integration_results = {}

    return integration_results, monitoring_task


def initialize_system_settings():
    """Инициализирует системные настройки"""
    try:
        from db import get_db  # pylint: disable=import-outside-toplevel
        db = get_db()
        db.save_system_setting("system_version", "2.0.0")
        db.save_system_setting("ai_enabled", "true")
        db.save_system_setting("arbitrage_enabled", "false")
        db.save_system_setting("manual_trading_enabled", "true")
        db.save_system_setting("audit_enabled", "true")
        db.save_system_setting("backtest_enabled", "true")

        # Инициализируем blacklist с примерами низкокапитализированных монет
        low_cap_symbols = ["DOGE", "SHIB", "PEPE", "BONK", "WIF"]
        for symbol in low_cap_symbols:
            db.add_to_market_cap_blacklist(f"{symbol}USDT", 1000000, "Low market cap example")

        # Добавляем тестовый результат бэктеста
        db.save_backtest_result(
            symbol="BTCUSDT",
            interval="1h",
            since_days=30,
            bars=720,
            signals=45,
            tp1=30,
            tp2=15,
            sl=10,
            pnl=1250.50,
            mae_avg_pct=2.5,
            mfe_avg_pct=4.2,
            avg_duration_sec=3600,
            started_at=datetime.now().isoformat(),
            ended_at=datetime.now().isoformat()
        )

        logger.info("✅ Системные настройки, blacklist и бэктест инициализированы")
    except Exception as e:
        logger.warning("⚠️ Ошибка инициализации настроек: %s", e)


def ensure_locales_exist():
    """Гарантирует наличие локалей"""
    try:
        locales_dir = os.path.join(os.getcwd(), "locales")
        if not os.path.isdir(locales_dir):
            os.makedirs(locales_dir, exist_ok=True)
        for lang in ("ru", "en"):
            path = os.path.join(locales_dir, f"{lang}.json")
            if not os.path.isfile(path):
                with open(path, "w", encoding="utf-8") as lf:
                    json.dump({}, lf)
                logger.info("Создана дефолтная локаль: %s", path)
    except (OSError, IOError, UnicodeError) as e:
        logger.warning("Не удалось подготовить локали: %s", e)


def create_audit_tasks():
    """Создает задачи для систем аудита"""
    tasks = []
    if AUDIT_SYSTEMS_AVAILABLE:
        try:
            async def audit_task():
                while True:  # Будет остановлен через shutdown_manager
                    # Логируем активные монеты
                    audit_systems.log_active_coin("monitor", "BTCUSDT", "Мониторинг активных монет")
                    import asyncio
                    await asyncio.sleep(3600)  # Проверяем каждый час
            import asyncio
            audit_task_instance = asyncio.create_task(audit_task())
            tasks.append(audit_task_instance)
            logger.info("✅ Системы аудита запущены")
        except (ValueError, TypeError, KeyError, RuntimeError, OSError, ConnectionError) as e:
            logger.warning("⚠️ Ошибка запуска систем аудита: %s", e)
    else:
        logger.warning("⚠️ Системы аудита недоступны")

    return tasks
