#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines,import-outside-toplevel

"""Главный модуль ATRA.

Запускает Telegram-бота, систему оптимизации и генерации сигналов,
проверяет зависимости, очищает webhook и обеспечивает корректное
завершение работы. Также содержит CLI для запуска бэктеста.
"""

import asyncio
import logging
import signal
import sys
import traceback

# Динамический слой совместимости для импортов (позволяет удалить заглушки из корня)
try:
    # Добавляем путь к src если он еще не там
    import os
    src_path = os.path.join(os.path.dirname(__file__), 'src')
    if src_path not in sys.path:
        sys.path.append(src_path)
    
    import src.core.compat
except ImportError:
    pass

# import json  # Удален как неиспользуемый
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
import os
import warnings

# Оптимизация: используем uvloop для ускорения async операций (2-4x быстрее)
try:
    import uvloop
    uvloop.install()
    logging.info("✅ uvloop установлен и активирован")
except ImportError:
    logging.warning("⚠️ uvloop не установлен, используется стандартный event loop")
from src.infrastructure.websockets.binance_ws import start_binance_ws
from src.risk.autonomous.rollback_manager import start_rollback_manager
# import fcntl  # Не используется
from logging.handlers import RotatingFileHandler

# Загружаем переменные окружения из файла env
try:
    from dotenv import load_dotenv
    # Загружаем из файла env (приоритет над .env)
    env_path = os.path.join(os.path.dirname(__file__), 'env')
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
    # Также проверяем .env как fallback
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path, override=False)
except ImportError:
    # python-dotenv не установлен, используем системные переменные окружения
    pass

# Импорты извлеченных модулей
from src.adapters.parameters import AdaptiveParameterController
from src.adapters.signal import run_adaptive_analysis
from cleanup import cleanup, graceful_shutdown
from config import TOKEN, ATRA_ENV, initialize_coins_sync, COINS
from src.database.initialization import initialize_database_on_startup, sync_user_data_from_json_to_db
from src.utils.dependencies import check_critical_dependencies
from src.execution.exchange_api import (
    check_pending_symbols,
    initialize_market_cap_filtering,
    weekly_blacklist_check,
    weekly_whitelist_check,
)
# Импорты системных задач из archive (бывший system_tasks.py)
try:
    from archive.experimental.system_manager import (
        run_optimization_system,
        run_retention_tasks,
        run_metrics_feeder,
        run_soft_blocklist_task,
    )
except ImportError:
    async def run_optimization_system(): pass
    async def run_retention_tasks(): pass
    async def run_metrics_feeder(): pass
    async def run_soft_blocklist_task(): pass

# Импорты system_initialization (переименован в scripts/setup/system_init.py)
from scripts.setup.system_init import (
    initialize_system_integrations,
    initialize_system_settings,
    ensure_locales_exist,
)

# Импорты price_monitor_system (переименован в src/monitoring/price_monitor.py)
from src.monitoring.price_monitor import run_price_monitoring

# Импорты auto_pattern_cleaner (переименован в src/strategies/pattern_cleaner.py)
try:
    from src.strategies.pattern_cleaner import start_auto_pattern_cleanup
except ImportError:
    def start_auto_pattern_cleanup(): pass

# Импорты ai_system_manager (переименован в src/ai/system_manager.py)
try:
    from src.ai.system_manager import run_ai_learning_system, AI_AVAILABLE
    from src.ai.autonomous.learning_loop import start_autonomous_learning
    from src.infrastructure.self_healing.manager import run_self_healing
    from src.risk.autonomous.risk_guard import start_risk_guard
    from src.ai.autonomous.sync.knowledge_bridge import start_knowledge_sync
except ImportError:
    AI_AVAILABLE = False
    async def run_ai_learning_system(): pass
    async def start_autonomous_learning(): pass
    async def run_self_healing(): pass
    async def start_risk_guard(): pass
    async def start_knowledge_sync(): pass

try:
    import signal_live as sl
    from signal_live import (
        run_hybrid_signal_system_fixed,
        initialize_signal_acceptance_system,
        signal_acceptance_manager,
    )
    SIGNAL_LIVE_AVAILABLE = True
except ImportError:
    sl = None
    SIGNAL_LIVE_AVAILABLE = False
    async def run_hybrid_signal_system_fixed(*args, **kwargs): pass
    def initialize_signal_acceptance_system(*args, **kwargs): pass
    signal_acceptance_manager = None

from src.telegram.handlers import set_signal_acceptance_manager

from src.telegram.bot_core import run_telegram_bot_in_existing_loop
TELEGRAM_BOT_CORE_AVAILABLE = True

# Импорты для интегрированных систем (перенесены в system_initialization)

# REST API на FastAPI (асинхронный, не блокирует event loop)
try:
    from rest_api import run_rest_api_async
    REST_API_AVAILABLE = True
    print("✅ REST API (FastAPI) доступен")
except ImportError:
    REST_API_AVAILABLE = False

# Dashboard с защитой БД (READONLY + WAL mode)
try:
    from web.dashboard import dashboard
    WEB_DASHBOARD_AVAILABLE = True
    print("✅ Web Dashboard доступен")
except ImportError:
    WEB_DASHBOARD_AVAILABLE = False

# Бэктест
try:
    from tools.backtest.cli import run_backtest_command, run_dca_backtest_command
except ImportError:
    try:
        from backtest_cli import run_backtest_command, run_dca_backtest_command
    except ImportError:
        def run_backtest_command():
            print("❌ Backtest CLI not available")
        def run_dca_backtest_command():
            print("❌ DCA Backtest CLI not available")

# Импорты для УМНОЙ гибридной системы сигналов с резервными источниками
try:
    # Используем уже импортированную функцию
    check_and_send_signals_hybrid = run_hybrid_signal_system_fixed  # Используем новую систему
    HYBRID_SYSTEM_AVAILABLE = True
    print("🧠 Используется УМНАЯ гибридная система с резервными источниками")
except ImportError:
    try:
        # Уже импортировано выше, не нужно дублировать
        HYBRID_SYSTEM_AVAILABLE = True
        print("✅ Используется НОВАЯ гибридная система сигналов")
    except ImportError:
        HYBRID_SYSTEM_AVAILABLE = False
        print("❌ Гибридная система недоступна")

# Импорт background_data_updater отдельно
try:
    try:
        from src.data.background_updater import background_data_updater
    except ImportError:
        from background_data_updater import background_data_updater
    BACKGROUND_UPDATER_AVAILABLE = True
except ImportError:
    BACKGROUND_UPDATER_AVAILABLE = False

# Импорты для веб-запросов
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Импорты для многопоточности (threading не используется в main.py)
# try:
#     import threading
#     THREADING_AVAILABLE = True
# except ImportError:
#     THREADING_AVAILABLE = False
THREADING_AVAILABLE = False


# ИИ система управляется через ai_system_manager

async def run_weekly_checks():
    """
    Еженедельные проверки белого и черного списков
    """

    while True:
        try:
            # Проверяем каждый понедельник в 9:00
            now = get_utc_now()
            if now.weekday() == 0 and now.hour == 9 and now.minute < 5:  # Понедельник, 9:00
                logger.info("📅 Запуск еженедельных проверок списков...")

                # Проверяем черный список
                await weekly_blacklist_check()

                # Проверяем белый список
                await weekly_whitelist_check()
                logger.info("✅ Еженедельные проверки завершены")

                # Ждем до следующего понедельника
                await asyncio.sleep(3600)  # 1 час
            else:
                # Проверяем каждые 6 часов
                await asyncio.sleep(6 * 3600)
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("Ошибка еженедельных проверок: %s", e)
            await asyncio.sleep(3600)  # 1 час при ошибке

async def run_hourly_pending_checks():
    """
    Ежечасная проверка монет из списка на проверке
    """
    while True:
        try:
            # Проверяем каждый час
            logger.info("🔄 Запуск ежечасной проверки монет из списка на проверке...")

            await check_pending_symbols()

            logger.info("✅ Ежечасная проверка завершена")
            # Ждем 1 час
            await asyncio.sleep(3600)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("Ошибка ежечасной проверки: %s", e)
            await asyncio.sleep(3600)  # 1 час при ошибке

# Импорты новых систем
# Система арбитража отключена (не используется)
ARBITRAGE_AVAILABLE = False

try:
    from manual_trading import manual_trading  # noqa: F401; pylint: disable=unused-import
    MANUAL_TRADING_AVAILABLE = True
except ImportError:
    MANUAL_TRADING_AVAILABLE = False

try:
    from audit_systems import audit_systems
    AUDIT_SYSTEMS_AVAILABLE = True
except ImportError:
    AUDIT_SYSTEMS_AVAILABLE = False

# Импорты основной конфигурации

# Импорты для работы с базой данных перенесены в database_initialization.py

# Язык по умолчанию
DEFAULT_LANGUAGE = "ru"

# Импортируем улучшенную систему логирования
try:
    from enhanced_logging import get_logger
    logger = get_logger(__name__)
    logger.info("✅ Enhanced logging system initialized")
except ImportError as e:
    # Fallback к стандартному логированию
    print(f"⚠️ Enhanced logging not available: {e}")

    # Настройка логирования (более подробная в dev)
    _root_logger = logging.getLogger()
    for _h in list(_root_logger.handlers):
        _root_logger.removeHandler(_h)
    _root_logger.setLevel(logging.DEBUG if ATRA_ENV != "prod" else logging.INFO)

    _formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Ротация логов: 5 MB на файл, до 5 файлов
    _file_handler = RotatingFileHandler("system_improved.log", maxBytes=5*1024*1024, backupCount=5)
    _file_handler.setLevel(logging.INFO)
    _file_handler.setFormatter(_formatter)

    _stream_handler = logging.StreamHandler()
    _stream_handler.setLevel(logging.DEBUG if ATRA_ENV != "prod" else logging.INFO)
    _stream_handler.setFormatter(_formatter)

    _root_logger.addHandler(_file_handler)
    _root_logger.addHandler(_stream_handler)

    logger = logging.getLogger(__name__)

# 🆕 Импорты модулей развития АТРА (после инициализации логгера)
try:
    from src.core.evolution import start_evolution_task
    EVOLUTION_AVAILABLE = True
except ImportError:
    EVOLUTION_AVAILABLE = False
    logger.warning("⚠️ Модуль эволюции не найден")

try:
    from src.core.research_lab import start_research_lab
    RESEARCH_AVAILABLE = True
except ImportError:
    RESEARCH_AVAILABLE = False
    logger.warning("⚠️ Модуль исследований не найден")

try:
    from src.data.background_updater import background_data_updater
    BACKGROUND_UPDATER_AVAILABLE = True
except ImportError:
    BACKGROUND_UPDATER_AVAILABLE = False
    logger.warning("⚠️ Фоновый обновлятель данных не найден")

# Подавляем шумное предупреждение urllib3 о LibreSSL в dev/локальной среде
try:
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
except ImportError:
    pass

# ПАТЧ ДЛЯ TALIB - АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ
try:
    from talib_wrapper import get_talib
    TALIB = get_talib()  # noqa: F841
    if TALIB is not None:
        print("✅ talib успешно загружен и готов к работе")
    else:
        print("ℹ️ talib недоступен, используется fallback режим")
except ImportError:
    print("ℹ️ talib wrapper недоступен, используется fallback режим")
    TALIB = None


class ShutdownManager:
    """Менеджер для управления состоянием завершения работы"""
    def __init__(self):
        self._shutdown_requested = False

    @property
    def shutdown_requested(self):
        """Проверяет, запрошено ли завершение работы"""
        return self._shutdown_requested

    def request_shutdown(self):
        """Запрашивает завершение работы"""
        self._shutdown_requested = True

    def reset(self):
        """Сбрасывает флаг завершения (для тестирования)"""
        self._shutdown_requested = False

# Глобальный экземпляр менеджера завершения
shutdown_manager = ShutdownManager()

# Глобальные переменные системы принятия сигналов
ACCEPTANCE_DB = None
TELEGRAM_UPDATER = None
POSITION_MANAGER = None
SIGNAL_ACCEPTANCE = None

# Функция для запуска гибридной системы сигналов
async def run_hybrid_signal_system():
    """Запускает гибридную систему обработки сигналов"""
    try:
        logger.info("🔄 Запуск гибридной системы сигналов...")

        while not shutdown_manager.shutdown_requested:
            try:
                # Запускаем гибридную проверку сигналов
                await check_and_send_signals_hybrid()

                # Пауза между циклами (30 секунд)
                await asyncio.sleep(30)

            except Exception as e:
                logger.error("Ошибка в гибридной системе сигналов: %s", e)
                await asyncio.sleep(10)  # Пауза при ошибке

    except asyncio.CancelledError:
        logger.info("🛑 Гибридная система сигналов остановлена")
    except Exception as e:
        logger.error("❌ Критическая ошибка гибридной системы: %s", e)

# Глобальные переменные для веб-сервисов
API_SERVER = None
DASHBOARD_SERVER = None


def signal_handler(signum, _frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info("📡 Получен сигнал %s, завершение работы...", signum)

    # Просим подсистему сигналов остановиться как можно раньше
    try:
        import signal_live as sl_mod
        stopper = getattr(sl_mod, "request_stop", None)
        if stopper is not None and callable(stopper):
            stopper()
            logger.info("🛑 Запрошена остановка системы сигналов (graceful)")
    except ImportError:
        pass
    except Exception as e:
        logger.warning("⚠️ Ошибка при остановке signal_live: %s", e)

    # Останавливаем веб-сервисы
    try:
        # Останавливаем REST API
        if API_SERVER:
            try:
                API_SERVER.shutdown()
                logger.info("🛑 REST API остановлен")
            except (AttributeError, RuntimeError):
                pass

        # Останавливаем Dashboard
        if DASHBOARD_SERVER:
            try:
                DASHBOARD_SERVER.shutdown()
                logger.info("🛑 Web Dashboard остановлен")
            except (AttributeError, RuntimeError):
                pass
    except (NameError, AttributeError):
        # Переменные могут быть не определены
        pass

    # Для всех сигналов используем graceful shutdown
    logger.info("🛑 Сигнал %s получен, начинаем graceful shutdown...", signum)
    # Устанавливаем флаг остановки
    shutdown_manager.request_shutdown()

    # Для SIGTERM (systemd) даем больше времени на завершение
    if signum == signal.SIGTERM:
        logger.info("🛑 SIGTERM получен, systemd ожидает завершения...")
    else:
        # Для SIGINT (Ctrl+C) также используем graceful shutdown
        logger.info("🛑 SIGINT получен, graceful shutdown...")



# Инициализация базы данных перенесена в database_initialization.py


# Синхронизация данных пользователей перенесена в database_initialization.py


async def main():
    """Основная функция"""
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 📊 Запуск Prometheus Metrics Server (Сергей + Елена)
    try:
        from prometheus_metrics import start_metrics_server
        # Запускаем на порту 8000 (можно изменить через конфиг)
        start_metrics_server(port=8000)
        logger.info("✅ Prometheus metrics server started on port 8000")
        logger.info("   Metrics endpoint: http://localhost:8000/metrics")
    except ImportError:
        logger.warning("⚠️ Prometheus metrics not available (prometheus-client not installed)")
    except Exception as e:
        logger.warning("⚠️ Failed to start Prometheus metrics server: %s", e)

    # Инициализируем список задач для дополнительных сервисов
    tasks = []
    main_tasks = []
    telegram_task_local = None
    optimization_task_local = None
    retention_task_local = None
    metrics_task_local = None
    soft_blocklist_task_local = None
    daily_summary_task_local = None
    market_cap_blacklist_task_local = None
    strategy_cb_task_local = None
    bandit_task_local = None
    weekly_check_task_local = None
    hourly_pending_task_local = None
    price_monitor_task_local = None
    adaptive_task_local = None
    pattern_cleanup_task_local = None

    # Запуск автономных систем (Виктория + Команда)
    try:
        # 🌐 START BINANCE WEBSOCKET STREAMER (High Speed Prices)
        main_tasks.append(asyncio.create_task(start_binance_ws()))
        logger.info("✅ Binance WebSocket Streamer запущен")

        # 🛡️ START SELF-HEALING (Now includes Position Sync)
        from src.infrastructure.self_healing.manager import run_self_healing
        main_tasks.append(asyncio.create_task(run_self_healing()))
        logger.info("✅ Self-Healing System (с авто-синхронизацией) запущена")
        try:
            from src.infrastructure.self_healing.janitor import start_janitor_loop
            main_tasks.append(asyncio.create_task(start_janitor_loop()))
            logger.info("✅ Autonomous Janitor (Система очистки) запущен")
        except Exception as e:
            logger.warning("Не удалось запустить Janitor: %s", e)
        main_tasks.append(asyncio.create_task(start_risk_guard()))
        main_tasks.append(asyncio.create_task(start_knowledge_sync()))
        
        # 🛡️ AUTONOMOUS RECOVERY SYSTEM (ARS)
        try:
            from src.risk.autonomous.stuck_monitor import start_stuck_monitor
            main_tasks.append(asyncio.create_task(start_stuck_monitor()))
            logger.info("✅ Autonomous Recovery System (ARS) запущена")
        except Exception as e:
            logger.warning("Не удалось запустить ARS: %s", e)

        # 🛡️ AUTONOMOUS ROLLBACK SYSTEM
        try:
            main_tasks.append(asyncio.create_task(start_rollback_manager()))
            logger.info("✅ Autonomous Rollback System запущен")
        except Exception as e:
            logger.warning("Не удалось запустить Rollback System: %s", e)

        logger.info("✅ Автономные системы (Self-Healing, Risk Guard, Knowledge Sync) запущены")
    except Exception as e:
        logger.warning("Не удалось запустить автономные системы: %s", e)

    # Запуск периодического истечения PENDING сигналов
    try:
        try:
            from src.database.acceptance import AcceptanceDatabase
        except ImportError:
            try:
                from acceptance_database import AcceptanceDatabase
            except ImportError:
                class AcceptanceDatabase:
                    async def expire_pending_signals(self, *args, **kwargs): return 0
        adb = AcceptanceDatabase()

        # Алерт-сервис подключится после запуска Telegram бота (в фоновой задаче)

        async def _expire_pending_periodically():
            while True:
                try:
                    await asyncio.sleep(300)
                    affected = await adb.expire_pending_signals(ttl_minutes=60)
                    if affected:
                        logger.info("🕒 PENDING→EXPIRED: %d записей", affected)
                except Exception as e:
                    logger.warning("TTL expire task error: %s", e)
                    await asyncio.sleep(60)
        main_tasks.append(asyncio.create_task(_expire_pending_periodically()))
    except Exception as e:
        logger.warning("Не удалось запустить задачу истечения PENDING: %s", e)

    # Периодическая синхронизация позиций с биржей для auto-режима
    try:
        async def _sync_positions_periodically():
            try:
                from src.database.acceptance import AcceptanceDatabase
            except ImportError:
                try:
                    from acceptance_database import AcceptanceDatabase
                except ImportError:
                    class AcceptanceDatabase:
                        async def get_users_by_mode(self, *args, **kwargs): return []
                        async def get_active_exchange_keys(self, *args, **kwargs): return []
                        async def get_signal_data(self, *args, **kwargs): return None
                        async def upsert_active_position(self, *args, **kwargs): pass
            try:
                from src.execution.exchange_adapter import ExchangeAdapter
            except ImportError:
                from exchange_adapter import ExchangeAdapter
            adb_local = AcceptanceDatabase()

            # Трекинг размеров позиций для определения срабатывания TP1
            position_sizes = {}  # {(user_id, symbol): original_size}
            tp1_triggered = set()  # {(user_id, symbol)}
            manual_protection = {}  # {(user_id, symbol): {'tp1', 'tp2', 'sl', ...}}

            while True:
                try:
                    # Получаем пользователей в auto режиме И с активными ключами
                    user_ids = await adb_local.get_users_by_mode('auto')
                    # Добавляем пользователей с активными ключами (для всех режимов)
                    try:
                        import sqlite3
                        conn_temp = sqlite3.connect('trading.db')
                        cursor_temp = conn_temp.cursor()
                        cursor_temp.execute(
                            'SELECT DISTINCT user_id FROM user_exchange_keys WHERE is_active = 1'
                        )
                        all_users_with_keys = [row[0] for row in cursor_temp.fetchall()]
                        conn_temp.close()
                        # Объединяем списки (убираем дубликаты)
                        user_ids = list(set(user_ids + all_users_with_keys))
                        logger.info(
                            "🔍 Мониторинг позиций для %d пользователей",
                            len(user_ids)
                        )
                    except Exception as keys_err:
                        logger.debug("Could not fetch users with keys: %s", keys_err)

                    for uid in user_ids:
                        # Получаем режим торговли пользователя (spot/futures)
                        # ВАЖНО: Синхронизируем позиции для обоих режимов
                        # Для futures: используем fetch_positions() (возвращает futures позиции)
                        # Для spot: позиции отслеживаются локально и синхронизируются
                        try:
                            try:
                                from src.database.db import Database
                            except ImportError:
                                from db import Database
                            db_temp = Database()
                            user_data_temp = db_temp.get_user_data(str(uid)) or {}
                            user_trade_mode = user_data_temp.get('trade_mode', 'spot')
                        except Exception:
                            user_trade_mode = 'spot'

                        # 🛡️ ПРОВЕРКА: Если биржа не подключена (нет ключей), пропускаем синхронизацию
                            keys = await adb_local.get_active_exchange_keys(uid, 'bitget')
                            if not keys or len(keys) == 0:
                                logger.debug(
                                    "⏭️ [SYNC] Пропущена синхронизация для пользователя %d "
                                    "(биржа не подключена - нет ключей API)",
                                    uid
                                )
                                continue

                            async with ExchangeAdapter('bitget', keys=keys, sandbox=False) as adapter:
                                # Для futures получаем позиции с биржи
                                # Для spot позиции отслеживаются локально
                                # (spot - это баланс, но мы синхронизируем локальные позиции)
                                if user_trade_mode == 'futures':
                                    positions = await adapter.fetch_positions()
                                else:
                                    # Для spot режима позиции отслеживаются локально
                                    # fetch_positions() возвращает только futures, поэтому для spot используем пустой список
                                    positions = []

                                # 🛡️ Проверка hedge-позиций (LONG+SHORT на один символ)
                                try:
                                    from src.risk.portfolio import detect_hedge_positions, close_hedge_positions
                                    hedge_conflicts = await detect_hedge_positions(positions)
                                except (ImportError, Exception):
                                    hedge_conflicts = []
                                if hedge_conflicts:
                                    logger.warning(
                                        "⚠️ [HEDGE WARNING] Обнаружено %d hedge-конфликтов для user %s",
                                        len(hedge_conflicts), uid
                                    )
                                    # Автоматически закрываем hedge позиции
                                    close_results = await close_hedge_positions(hedge_conflicts, adapter)
                                    logger.info(
                                        "✅ [HEDGE CLOSE] Закрыто %d hedge-позиций",
                                        len([r for r in close_results if 'error' not in r])
                                    )
                                    # Перезагружаем позиции после закрытия
                                    positions = await adapter.fetch_positions()

                                # Собираем набор символов, которые биржа считает открытыми
                                open_symbols_remote = set()
                                logger.info(
                                    "🔍 [SYNC] Пользователь %d: получено %d позиций с биржи",
                                    uid, len(positions or [])
                                )

                                # 🛡️ ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ: Выводим все позиции с биржи для отладки
                                if positions:
                                    logger.info(
                                        "📊 [SYNC] Все позиции с биржи для пользователя %d: %s",
                                        uid, [p.get('symbol') or p.get('info', {}).get('symbol', 'N/A')
                                              for p in positions[:10]]
                                    )

                                for p in (positions or []):
                                    try:
                                        symbol = p.get('symbol') or p.get('info', {}).get('symbol')

                                        # 🛡️ НОРМАЛИЗАЦИЯ СИМВОЛА: Приводим к единому формату
                                        # с учетом режима торговли
                                        # Для futures: Bitget возвращает ETHFI/USDT:USDT или ETHFI/USDT
                                        # -> нормализуем в ETHFIUSDT
                                        # Для spot: Bitget возвращает ETHFIUSDT -> оставляем как есть
                                        if symbol:
                                            # Убираем пробелы и приводим к верхнему регистру
                                            symbol = symbol.strip().upper()

                                            # Нормализация для futures (формат /USDT:USDT или /USDT)
                                            # Для spot обычно формат уже ETHFIUSDT, но на всякий случай проверяем
                                            if user_trade_mode == 'futures':
                                                # Futures: убираем суффиксы типа /USDT:USDT, /USDT
                                                if '/USDT:USDT' in symbol:
                                                    symbol = symbol.replace('/USDT:USDT', 'USDT')
                                                elif '/USDT' in symbol and not symbol.endswith('USDT'):
                                                    symbol = symbol.replace('/USDT', 'USDT')
                                            # Для spot обычно формат уже правильный (ETHFIUSDT), но если есть /USDT - убираем
                                            else:  # spot
                                                if '/USDT' in symbol and not symbol.endswith('USDT'):
                                                    symbol = symbol.replace('/USDT', 'USDT')

                                        contracts = float(p.get('contracts') or p.get('positionAmt') or 0)

                                        # Логирование для отладки
                                        logger.info(
                                            "🔍 [SYNC] Позиция с биржи: symbol=%s (нормализован), "
                                            "contracts=%.6f",
                                            symbol, contracts
                                        )

                                        if contracts and abs(contracts) > 0:
                                            # Определяем направление: в hedge mode смотрим на holdSide
                                            hold_side = p.get('side') or p.get('info', {}).get('holdSide', '')
                                            if hold_side:
                                                # В hedge mode: holdSide = 'long' или 'short'
                                                direction = 'BUY' if hold_side.lower() == 'long' else 'SELL'
                                            else:
                                                # Fallback: по знаку contracts (для one-way mode)
                                                direction = 'BUY' if contracts > 0 else 'SELL'
                                            
                                            # 🛡️ ПРОВЕРКА: Определяем источник позиции (сигнал или ручная)
                                            signal_data = await adb_local.get_signal_data(user_symbol=(uid, symbol))
                                            if not signal_data:
                                                logger.warning(
                                                    "🚫 [SYNC_BLOCK] %s %s: Позиция найдена на бирже (contracts=%.6f) "
                                                    "БЕЗ сигнала в БД для пользователя %d. "
                                                    "Позиция НЕ будет добавлена в БД (открыта вручную или через другой процесс).",
                                                    symbol, direction, contracts, uid
                                                )
                                                open_symbols_remote.add(symbol)
                                                continue  # 🆕 БЛОКИРУЕМ: не добавляем ручные позиции
                                            else:
                                                # 🛡️ ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: Проверяем направление сигнала для автоматических позиций
                                                try:
                                                    signal_check_query = """
                                                        SELECT direction FROM signals_log
                                                        WHERE symbol = ? AND user_id = ?
                                                        ORDER BY created_at DESC
                                                        LIMIT 1
                                                    """
                                                    signal_rows = await adb_local.execute_with_retry(
                                                        signal_check_query, (symbol, uid), is_write=False
                                                    )
                                                    
                                                    if signal_rows:
                                                        signal_direction = signal_rows[0][0].upper()
                                                        if signal_direction != direction:
                                                            logger.warning(
                                                                "🚫 [SYNC_BLOCK] %s %s: Автоматическая позиция найдена на бирже, "
                                                                "но направление сигнала в БД = %s. "
                                                                "Позиция НЕ будет добавлена (несоответствие направления - возможна ошибка auto_execution).",
                                                                symbol, direction, signal_direction
                                                            )
                                                            open_symbols_remote.add(symbol)
                                                            continue
                                                except Exception as signal_check_err:
                                                    logger.debug("⚠️ [SYNC] Ошибка проверки направления сигнала для %s: %s", symbol, signal_check_err)

                                            entry_price = float(p.get('entryPrice') or p.get('entry_price') or 0) or 0.0
                                            await adb_local.upsert_active_position(
                                                uid, symbol, direction, entry_price, 'open'
                                            )
                                            open_symbols_remote.add(symbol)
                                            logger.info(
                                                "✅ [SYNC] Добавлена позиция с биржи: %s "
                                                "(contracts=%.6f, direction=%s, есть сигнал в БД)",
                                                symbol, contracts, direction
                                            )

                                            # 🆕 TP1/TP2 мониторинг и перенос SL в безубыток
                                            pos_key = (uid, symbol)
                                            current_size = abs(contracts)

                                            # Получаем текущую цену для проверки прогресса к TP1
                                            try:
                                                from src.execution.exchange_api import get_current_price_robust
                                                current_price = await get_current_price_robust(
                                                    symbol.replace('/USDT:USDT', 'USDT')
                                                )
                                            except Exception:
                                                current_price = None

                                            # Запоминаем начальный размер позиции
                                            if pos_key not in position_sizes:
                                                position_sizes[pos_key] = current_size
                                                logger.info(
                                                    "📊 [TP Monitor] %s для user %s: начальный размер %.4f",
                                                    symbol, uid, current_size
                                                )
                                                
                                                # 🆕 Инициализируем trailing stop manager для отслеживания прогресса к TP1
                                                try:
                                                    from trailing_stop_manager import get_trailing_manager
                                                    trailing_mgr = get_trailing_manager()
                                                    
                                                    # Получаем TP1 из сигнала
                                                    signal_data_init = await adb_local.get_signal_data(user_symbol=(uid, symbol))
                                                    tp1_price_init = None
                                                    if signal_data_init:
                                                        tp1_price_init = float(signal_data_init.get('tp1_price', 0) or 0)
                                                    
                                                    if tp1_price_init and tp1_price_init > 0:
                                                        # Получаем начальный SL из сигнала или используем fallback
                                                        initial_sl_value = None
                                                        if signal_data_init:
                                                            initial_sl_value = float(signal_data_init.get('sl_price', 0) or 0)
                                                        if not initial_sl_value or initial_sl_value <= 0:
                                                            # Fallback: рассчитываем стандартный SL
                                                            if direction == 'BUY':
                                                                initial_sl_value = entry_price * 0.98  # -2%
                                                            else:
                                                                initial_sl_value = entry_price * 1.02  # +2%
                                                        
                                                        trailing_mgr.setup_position(
                                                            symbol=symbol,
                                                            entry_price=entry_price,
                                                            initial_sl=initial_sl_value,
                                                            side=direction,
                                                            tp1_price=tp1_price_init
                                                        )
                                                        logger.info(
                                                            "🎯 [TRAILING] %s: инициализирован trailing stop "
                                                            "для переноса SL при 50%% пути к TP1 (%.8f)",
                                                            symbol, tp1_price_init
                                                        )
                                                except Exception as trailing_init_err:
                                                    logger.debug("⚠️ [TRAILING] Ошибка инициализации trailing stop для %s: %s", 
                                                                symbol, trailing_init_err)

                                                # 🛡️ Автоматическое создание защитных ордеров для новой позиции
                                                try:
                                                    # Получаем TP/SL уровни из БД
                                                    signal_data = await adb_local.get_signal_data(user_symbol=(uid, symbol))
                                                    if signal_data:
                                                        tp1_price = float(signal_data.get('tp1_price', 0) or 0)
                                                        tp2_price = float(signal_data.get('tp2_price', 0) or 0)
                                                        sl_price = float(signal_data.get('sl_price', 0) or 0)
                                                    else:
                                                        # Рассчитываем стандартные уровни
                                                        if direction == 'BUY':
                                                            tp1_price = entry_price * 1.02  # +2%
                                                            tp2_price = entry_price * 1.04  # +4%
                                                            sl_price = entry_price * 0.98   # -2%
                                                        else:  # SHORT
                                                            tp1_price = entry_price * 0.98  # -2%
                                                            tp2_price = entry_price * 0.96  # -4%
                                                            sl_price = entry_price * 1.02   # +2%

                                                    # Проверяем есть ли уже защитные ордера
                                                    open_orders = await adapter.fetch_open_orders(symbol)
                                                    has_protection = False

                                                    for order in (open_orders or []):
                                                        order_side = order.get('side', '').lower()
                                                        # Для LONG: защита = SELL, для SHORT: защита = BUY
                                                        if (direction == 'BUY' and order_side == 'sell') or \
                                                           (direction == 'SELL' and order_side == 'buy'):
                                                            has_protection = True
                                                            break

                                                    if not has_protection and tp1_price and tp2_price and sl_price:
                                                        logger.info(
                                                            "🛡️ [Protection] Создаю защитные ордера для %s:",
                                                            symbol
                                                        )
                                                        logger.info(
                                                            "   TP1: $%.8f | TP2: $%.8f | SL: $%.8f",
                                                            tp1_price, tp2_price, sl_price
                                                        )

                                                        # Инициализируем переменные
                                                        tp1_order = None
                                                        tp2_order = None
                                                        sl_order = None
                                                        client = getattr(adapter, "client", None)

                                                        def normalize_amount(val: float, client_obj, symbol_str: str) -> float:
                                                            """Нормализует количество с учетом precision биржи.
                                                            
                                                            Args:
                                                                val: Значение для нормализации
                                                                client_obj: Клиент биржи
                                                                symbol_str: Символ
                                                            
                                                            Returns:
                                                                Нормализованное значение
                                                            """
                                                            if client_obj:
                                                                try:
                                                                    precision_val = client_obj.amount_to_precision(
                                                                        symbol_str, val
                                                                    )
                                                                    return float(precision_val)
                                                                except Exception:
                                                                    pass
                                                            return float(f"{val:.8f}")

                                                        try:
                                                            tp1_amount = normalize_amount(
                                                                current_size * 0.5, client, symbol
                                                            )
                                                            tp2_amount = normalize_amount(
                                                                max(current_size - tp1_amount, 0.0),
                                                                client,
                                                                symbol,
                                                            )
                                                        except Exception:
                                                            # Fallback если нормализация не удалась
                                                            tp1_amount = float(f"{current_size * 0.5:.8f}")
                                                            tp2_amount = float(f"{max(current_size - tp1_amount, 0.0):.8f}")
                                                        if tp2_amount <= 0:
                                                            tp2_amount = tp1_amount

                                                        tp1_order = await adapter.place_take_profit_order(
                                                            symbol=symbol,
                                                            direction=direction,
                                                            position_amount=tp1_amount,
                                                            take_profit_price=tp1_price,
                                                            client_tag="tp1",
                                                        )

                                                        tp2_order = await adapter.place_take_profit_order(
                                                            symbol=symbol,
                                                            direction=direction,
                                                            position_amount=tp2_amount,
                                                            take_profit_price=tp2_price,
                                                            client_tag="tp2",
                                                        )

                                                        # Создаем SL (100% позиции)
                                                        sl_order = await adapter.place_stop_loss_order(
                                                            symbol=symbol,
                                                            direction=direction,
                                                            position_amount=current_size,
                                                            stop_price=sl_price,
                                                        )

                                                        success_count = sum(
                                                            1
                                                            for order in (tp1_order, tp2_order, sl_order)
                                                            if order
                                                        )

                                                        if success_count == 3:
                                                            logger.info(
                                                                "✅ [Protection] Защитные ордера созданы для %s: TP1, TP2, SL",
                                                                symbol,
                                                            )
                                                        elif success_count > 0:
                                                            logger.warning(
                                                                "⚠️ [Protection] Частично созданы ордера "
                                                                "для %s: %d/3 (TP1, TP2, SL)",
                                                                symbol, success_count
                                                            )
                                                        else:
                                                            logger.error(
                                                                "❌ [Protection] Не удалось создать ордера для %s",
                                                                symbol
                                                            )
                                                except Exception as prot_err:
                                                    logger.error(
                                                        "❌ [Protection] Ошибка создания защитных ордеров "
                                                        "для %s: %s",
                                                        symbol, prot_err
                                                    )

                                            # 🆕 ПРОВЕРКА: Перенос SL в безубыток при достижении 50% пути к TP1
                                            # (выполняется ДО проверки достижения TP1)
                                            if current_price and pos_key not in tp1_triggered:
                                                try:
                                                    from trailing_stop_manager import get_trailing_manager
                                                    trailing_mgr = get_trailing_manager()
                                                    
                                                    # Получаем TP1 из сигнала
                                                    signal_data_tp1 = await adb_local.get_signal_data(user_symbol=(uid, symbol))
                                                    tp1_price_check = None
                                                    if signal_data_tp1:
                                                        tp1_price_check = float(signal_data_tp1.get('tp1_price', 0) or 0)
                                                    
                                                    if tp1_price_check and tp1_price_check > 0:
                                                        # Получаем DataFrame для адаптивной логики (если доступен)
                                                        df_for_trailing = None
                                                        try:
                                                            # Пытаемся получить исторические данные для анализа
                                                            from src.execution.exchange_api import get_ohlc_binance_sync_async
                                                            import pandas as pd
                                                            ohlc_data = await get_ohlc_binance_sync_async(
                                                                symbol.replace('/USDT:USDT', 'USDT'),
                                                                '1h',
                                                                100
                                                            )
                                                            if ohlc_data and len(ohlc_data) > 0:
                                                                df_for_trailing = pd.DataFrame(ohlc_data)
                                                                # Убеждаемся, что есть нужные колонки
                                                                required_cols = ['open', 'high', 'low', 'close']
                                                                if all(col in df_for_trailing.columns for col in required_cols):
                                                                    df_for_trailing = df_for_trailing[required_cols].astype(float)
                                                                else:
                                                                    df_for_trailing = None
                                                        except Exception as df_err:
                                                            logger.debug("⚠️ [TRAILING] Не удалось получить DataFrame для %s: %s", symbol, df_err)
                                                        
                                                        # Проверяем прогресс к TP1 и переносим SL если нужно
                                                        trailing_result = trailing_mgr.calculate_tp1_trailing_stop(
                                                            symbol=symbol,
                                                            current_price=current_price,
                                                            atr_value=None,  # Можно добавить ATR позже
                                                            df=df_for_trailing  # 🆕 Передаем DataFrame для адаптивной логики
                                                        )
                                                        
                                                        if trailing_result and trailing_result.get('stop_moved'):
                                                            new_sl_price = trailing_result.get('new_stop')
                                                            progress_pct = trailing_result.get('progress_to_tp1', 0)
                                                            
                                                            logger.info(
                                                                "🎯 [SL→BE 50%%] %s для user %s: "
                                                                "SL перенесён в безубыток при %.1f%% пути к TP1 "
                                                                "(новый SL: %.8f)",
                                                                symbol, uid, progress_pct, new_sl_price
                                                            )
                                                            
                                                            # Обновляем SL на бирже
                                                            try:
                                                                # Отменяем старые SL ордера
                                                                old_orders = await adapter.fetch_open_orders(symbol)
                                                                for old_order in (old_orders or []):
                                                                    order_price = float(old_order.get('price', 0))
                                                                    order_side = old_order.get('side', '').lower()
                                                                    order_id = old_order.get('id')
                                                                    
                                                                    is_sl_order = False
                                                                    if (direction == 'BUY' and order_side == 'sell'
                                                                            and order_price < entry_price):
                                                                        is_sl_order = True
                                                                    elif (direction == 'SELL' and order_side == 'buy'
                                                                            and order_price > entry_price):
                                                                        is_sl_order = True
                                                                    
                                                                    if is_sl_order and order_id:
                                                                        await adapter.cancel_order(order_id, symbol)
                                                                        logger.info(
                                                                            "🗑️ [Cancel Old SL] %s: отменён старый SL ордер %s",
                                                                            symbol, order_id
                                                                        )
                                                            except Exception as cancel_err:
                                                                logger.debug("⚠️ [SL→BE] Ошибка отмены старых ордеров: %s", cancel_err)
                                                            
                                                            # Выставляем новый SL в безубыток
                                                            try:
                                                                sl_order_new = await adapter.place_stop_loss_order(
                                                                    symbol,
                                                                    direction,
                                                                    current_size,
                                                                    new_sl_price,
                                                                )
                                                                if sl_order_new:
                                                                    logger.info(
                                                                        "✅ [SL→BE 50%%] %s для user %s: "
                                                                        "SL успешно перенесён в безубыток (%.8f) "
                                                                        "при %.1f%% пути к TP1",
                                                                        symbol, uid, new_sl_price, progress_pct
                                                                    )
                                                                    
                                                                    # Уведомляем пользователя
                                                                    try:
                                                                        from alert_notifications import get_alert_service
                                                                        alert_svc = get_alert_service()
                                                                        if hasattr(alert_svc, 'alert_sl_moved_to_breakeven'):
                                                                            await alert_svc.alert_sl_moved_to_breakeven(
                                                                                uid, symbol, new_sl_price
                                                                            )
                                                                    except Exception:
                                                                        pass
                                                                else:
                                                                    logger.warning(
                                                                        "⚠️ [SL→BE 50%%] %s: не удалось выставить новый SL",
                                                                        symbol
                                                                    )
                                                            except Exception as sl_update_err:
                                                                logger.error(
                                                                    "❌ [SL→BE 50%%] %s: ошибка обновления SL: %s",
                                                                    symbol, sl_update_err
                                                                )
                                                except Exception as trailing_err:
                                                    logger.debug("⚠️ [TRAILING] Ошибка проверки trailing stop для %s: %s", 
                                                                symbol, trailing_err)

                                            # Проверяем: уменьшилась ли позиция примерно на 50%?
                                            # (TP1 сработал)
                                            # (только для позиций, которые уже отслеживаются)
                                            original_size = position_sizes.get(pos_key, current_size)
                                            if pos_key in position_sizes and pos_key not in tp1_triggered and original_size > 0:
                                                size_reduction_pct = (
                                                    (original_size - current_size) / original_size
                                                ) * 100

                                                # Если размер уменьшился на 40-60% - это TP1
                                                if 40 <= size_reduction_pct <= 60:
                                                    logger.info(
                                                        "🎯 [TP1 Hit] %s для user %s: "
                                                        "размер уменьшился с %.4f до %.4f (%.1f%%), "
                                                        "TP1 сработал!",
                                                        symbol, uid, original_size,
                                                        current_size, size_reduction_pct
                                                    )

                                                    tp1_triggered.add(pos_key)
                                                    # 1. Переносим SL в безубыток через лимитный ордер
                                                    try:
                                                        # Безубыток = entry_price + 0.1% (покрытие комиссий)
                                                        if direction == 'BUY':
                                                            breakeven_price = entry_price * 1.001
                                                        else:
                                                            breakeven_price = entry_price * 0.999
                                                        side = 'buy' if direction == 'BUY' else 'sell'

                                                        # Отменяем старые SL ордера для этого символа
                                                        try:
                                                            old_orders = await adapter.fetch_open_orders(symbol)
                                                            for old_order in old_orders:
                                                                # Ищем ордера, которые выглядят как SL
                                                                # (цена ниже входа для LONG)
                                                                order_price = float(old_order.get('price', 0))
                                                                order_side = old_order.get('side', '').lower()
                                                                order_id = old_order.get('id')

                                                                # Для LONG позиции SL - это SELL ордер ниже входа
                                                                # Для SHORT позиции SL - это BUY ордер выше входа
                                                                is_sl_order = False
                                                                if (direction == 'BUY' and order_side == 'sell'
                                                                        and order_price < entry_price):
                                                                    is_sl_order = True
                                                                elif (direction == 'SELL' and order_side == 'buy'
                                                                        and order_price > entry_price):
                                                                    is_sl_order = True

                                                                if is_sl_order and order_id:
                                                                    logger.info(
                                                                        "🗑️ [Cancel Old SL] %s: "
                                                                        "отменяю старый SL ордер %s",
                                                                        symbol, order_id
                                                                    )
                                                                    await adapter.cancel_order(order_id, symbol)
                                                        except Exception as cancel_err:
                                                            logger.debug("Cancel old orders skipped: %s", cancel_err)

                                                        # Выставляем новый SL в безубыток через лимитный ордер
                                                        sl_order = await adapter.place_stop_loss_order(
                                                            symbol,
                                                            direction,
                                                            current_size,
                                                            breakeven_price,
                                                        )
                                                        if sl_order:
                                                            logger.info(
                                                                "✅ [SL→BE] %s для user %s: "
                                                                "SL перенесён в безубыток (%.8f) "
                                                                "через лимитный ордер",
                                                                symbol, uid, breakeven_price
                                                            )

                                                            # Уведомляем пользователя
                                                            try:
                                                                from alert_notifications import get_alert_service
                                                                alert_svc = get_alert_service()
                                                                if hasattr(alert_svc, 'alert_sl_moved_to_breakeven'):
                                                                    await alert_svc.alert_sl_moved_to_breakeven(
                                                                        uid, symbol, breakeven_price
                                                                    )
                                                            except Exception as alert_err:
                                                                logger.debug(
                                                                    "Alert notification skipped: %s", alert_err
                                                                )
                                                        else:
                                                            logger.warning(
                                                                "⚠️ [SL→BE] %s: "
                                                                "не удалось перенести SL в безубыток",
                                                                symbol
                                                            )
                                                    except Exception as e:
                                                        logger.error(
                                                            "❌ [SL→BE] %s: ошибка переноса SL: %s",
                                                            symbol, e
                                                        )

                                                    # 2. Выставляем TP2 на оставшиеся 50% через лимитный ордер
                                                    try:
                                                        # Получаем данные сигнала из БД для расчёта TP2
                                                        signal_data = await adb_local.get_signal_data(user_symbol=(uid, symbol))
                                                        if signal_data and signal_data.get('tp2_price'):
                                                            tp2_price = float(signal_data['tp2_price'])
                                                        else:
                                                            # Фолбэк: TP2 = entry + 4% для LONG,
                                                            # entry - 4% для SHORT
                                                            if direction == 'BUY':
                                                                tp2_price = entry_price * 1.04
                                                            else:
                                                                tp2_price = entry_price * 0.96

                                                        tp2_order = await adapter.place_take_profit_order(
                                                            symbol, side, tp2_price, current_size
                                                        )
                                                        if tp2_order:
                                                            logger.info(
                                                                "✅ [TP2 Set] %s для user %s: "
                                                                "TP2 выставлен (%.8f) на оставшиеся %.4f "
                                                                "через лимитный ордер",
                                                                symbol, uid, tp2_price, current_size
                                                            )
                                                        else:
                                                            logger.warning(
                                                                "⚠️ [TP2 Set] %s: не удалось выставить TP2",
                                                                symbol
                                                            )
                                                    except Exception as e:
                                                        logger.error(
                                                            "❌ [TP2 Set] %s: ошибка выставления TP2: %s",
                                                            symbol, e
                                                        )

                                                # Если размер уменьшился более чем на 80% - это TP2
                                                elif size_reduction_pct > 80:
                                                    logger.info(
                                                        "🎯 [TP2 Hit] %s для user %s: "
                                                        "размер уменьшился на %.1f%%, TP2 сработал!",
                                                        symbol, uid, size_reduction_pct
                                                    )
                                                    # Позиция почти закрыта, очистим трекинг
                                                    if pos_key in position_sizes:
                                                        del position_sizes[pos_key]
                                                    if pos_key in tp1_triggered:
                                                        tp1_triggered.remove(pos_key)
                                                    if pos_key in manual_protection:
                                                        del manual_protection[pos_key]

                                            # 🆕 РЕЗЕРВНАЯ СИСТЕМА: Проверяем цены и закрываем
                                            # маркет-ордерами если нужно
                                            try:
                                                # Получаем текущую цену
                                                from improved_price_api import get_current_price_robust
                                                current_price = await get_current_price_robust(
                                                    symbol.replace('/USDT:USDT', 'USDT')
                                                )
                                                if not current_price or current_price <= 0:
                                                    continue

                                                # Проверяем, есть ли открытые защитные ордера
                                                open_orders = await adapter.fetch_open_orders(symbol)
                                                has_protection_orders = False

                                                for order in (open_orders or []):
                                                    order_side = order.get('side', '').lower()
                                                    # Для LONG: защитные ордера = SELL
                                                    # Для SHORT: защитные ордера = BUY
                                                    if (direction == 'BUY' and order_side == 'sell') or \
                                                       (direction == 'SELL' and order_side == 'buy'):
                                                        has_protection_orders = True
                                                        break

                                                # Если защитных ордеров нет - включаем ручное управление
                                                if not has_protection_orders:
                                                    # Получаем целевые уровни из БД
                                                    signal_data = await adb_local.get_signal_data(user_symbol=(uid, symbol))
                                                    if signal_data:
                                                        tp1_price = (
                                                            float(signal_data.get('tp1_price', 0))
                                                            if signal_data.get('tp1_price') else None
                                                        )
                                                        tp2_price = (
                                                            float(signal_data.get('tp2_price', 0))
                                                            if signal_data.get('tp2_price') else None
                                                        )
                                                        sl_price = (
                                                            float(signal_data.get('sl_price', 0))
                                                            if signal_data.get('sl_price') else None
                                                        )
                                                    else:
                                                        # Фолбэк на стандартные уровни
                                                        if direction == 'BUY':
                                                            tp1_price = entry_price * 1.02
                                                            tp2_price = entry_price * 1.04
                                                            sl_price = entry_price * 0.98
                                                        else:
                                                            tp1_price = entry_price * 0.98
                                                            tp2_price = entry_price * 0.96
                                                            sl_price = entry_price * 1.02

                                                    # Сохраняем данные для ручного управления
                                                    manual_protection[pos_key] = {
                                                        'tp1': tp1_price,
                                                        'tp2': tp2_price,
                                                        'sl': sl_price,
                                                        'entry': entry_price,
                                                        'direction': direction
                                                    }

                                                    logger.info(
                                                        "🛡️ [Manual Protection] %s: "
                                                        "включен ручной режим (нет защитных ордеров)",
                                                        symbol
                                                    )

                                                    # 🛡️ АВТОМАТИЧЕСКИЕ ЗАЩИТЫ (ГИБРИДНАЯ СИСТЕМА)
                                                    # 1. Рассчитываем текущий PnL
                                                    if direction == 'BUY':
                                                        pnl_pct = ((current_price - entry_price) / entry_price) * 100
                                                    else:
                                                        pnl_pct = ((entry_price - current_price) / entry_price) * 100

                                                    # Проверяем условия для закрытия
                                                    close_pct = None
                                                    close_reason = None

                                                    # 2. ГИБРИДНЫЙ СТОП: AI SL из БД или резервная защита
                                                    try:
                                                        # Получаем AI-оптимизированный SL из БД
                                                        signal_data_for_sl = await adb_local.get_signal_data(user_symbol=(uid, symbol))
                                                        ai_sl_price = None
                                                        ai_sl_pct = None

                                                        if signal_data_for_sl:
                                                            ai_sl_price = float(signal_data_for_sl.get('sl_price', 0) or 0)
                                                            if ai_sl_price and entry_price:
                                                                # Рассчитываем AI SL в процентах
                                                                if direction == 'BUY':
                                                                    ai_sl_pct = (
                                                                        (ai_sl_price - entry_price) / entry_price
                                                                    ) * 100
                                                                else:
                                                                    ai_sl_pct = (
                                                                        (entry_price - ai_sl_price) / entry_price
                                                                    ) * 100

                                                        # Используем гибридную логику:
                                                        # - Если есть AI SL и он сработал → закрываем
                                                        # - Резервная защита: -5% критический стоп
                                                        # - AI SL имеет приоритет и может быть больше/меньше -5%

                                                        if ai_sl_price and ai_sl_pct is not None:
                                                            # AI SL: проверяем достигнута ли цена
                                                            sl_triggered = False
                                                            if direction == 'BUY' and current_price <= ai_sl_price:
                                                                sl_triggered = True
                                                            elif direction == 'SELL' and current_price >= ai_sl_price:
                                                                sl_triggered = True

                                                            if sl_triggered:
                                                                close_pct = 100
                                                                close_reason = (
                                                                    f"🤖 AI STOP LOSS {pnl_pct:.2f}% "
                                                                    f"(AI SL: {ai_sl_pct:.2f}%)"
                                                                )
                                                                logger.warning(
                                                                    "🤖 [AI STOP] %s: AI SL сработал, "
                                                                    "текущий PnL %.2f%%, AI SL %.2f%%",
                                                                    symbol, pnl_pct, ai_sl_pct
                                                                )
                                                            # Резервная критическая защита (если AI SL не сработал)
                                                            elif pnl_pct <= -5.0:
                                                                close_pct = 100
                                                                close_reason = (
                                                                    f"🚨 КРИТИЧЕСКИЙ СТОП {pnl_pct:.2f}% "
                                                                    f"(резервная защита, AI SL: {ai_sl_pct:.2f}%)"
                                                                )
                                                                logger.warning(
                                                                    "🚨 [CRITICAL] %s: Резервная защита -5%%, "
                                                                    "PnL %.2f%%, AI SL %.2f%%",
                                                                    symbol, pnl_pct, ai_sl_pct
                                                                )
                                                        else:
                                                            # Нет AI SL → используем стандартную защиту
                                                            if pnl_pct <= -5.0:
                                                                close_pct = 100
                                                                close_reason = (
                                                                    f"🚨 КРИТИЧЕСКИЙ УБЫТОК {pnl_pct:.2f}% "
                                                                    f"(стандартная защита)"
                                                                )
                                                                logger.warning(
                                                                    "🚨 [STANDARD STOP] %s: Убыток %.2f%%, "
                                                                    "AI SL недоступен, используем стандартную защиту",
                                                                    symbol, pnl_pct
                                                                )
                                                            elif pnl_pct <= -3.0:
                                                                close_pct = 100
                                                                close_reason = (
                                                                    f"⚠️ АВТО-СТОП {pnl_pct:.2f}% "
                                                                    f"(стандартная защита)"
                                                                )
                                                                logger.warning(
                                                                    "⚠️ [AUTO STOP] %s: Убыток %.2f%%, "
                                                                    "AI SL недоступен, используем стандартную защиту",
                                                                    symbol, pnl_pct
                                                                )
                                                    except Exception as sl_err:
                                                        logger.error(
                                                            "❌ [SL CHECK] Ошибка проверки SL для %s: %s",
                                                            symbol, sl_err
                                                        )
                                                        # Fallback на стандартную защиту при ошибке
                                                        if pnl_pct <= -5.0:
                                                            close_pct = 100
                                                            close_reason = f"🚨 КРИТИЧЕСКИЙ УБЫТОК {pnl_pct:.2f}%"

                                                    # 3. Стандартные проверки TP/SL (если не сработала защита)
                                                    if not close_pct and direction == 'BUY':
                                                        # LONG позиция
                                                        if sl_price and current_price <= sl_price:
                                                            close_pct = 100
                                                            close_reason = (
                                                                f"SL (цена {current_price:.8f} "
                                                                f"<= {sl_price:.8f})"
                                                            )
                                                        elif (tp2_price and current_price >= tp2_price
                                                                and pos_key in tp1_triggered):
                                                            close_pct = 50  # Закрываем оставшиеся 50%
                                                            close_reason = (
                                                                f"TP2 (цена {current_price:.8f} "
                                                                f">= {tp2_price:.8f})"
                                                            )
                                                        elif (tp1_price and current_price >= tp1_price
                                                                and pos_key not in tp1_triggered):
                                                            close_pct = 50  # Закрываем первые 50%
                                                            close_reason = (
                                                                f"TP1 (цена {current_price:.8f} "
                                                                f">= {tp1_price:.8f})"
                                                            )
                                                    elif not close_pct and direction == 'SELL':
                                                        # SHORT позиция
                                                        if sl_price and current_price >= sl_price:
                                                            close_pct = 100
                                                            close_reason = (
                                                                f"SL (цена {current_price:.8f} "
                                                                f">= {sl_price:.8f})"
                                                            )
                                                        elif (
                                                            tp2_price and current_price <= tp2_price
                                                            and pos_key in tp1_triggered
                                                        ):
                                                            close_pct = 50
                                                            close_reason = (
                                                                f"TP2 (цена {current_price:.8f} "
                                                                f"<= {tp2_price:.8f})"
                                                            )
                                                        elif (
                                                            tp1_price and current_price <= tp1_price
                                                            and pos_key not in tp1_triggered
                                                        ):
                                                            close_pct = 50
                                                            close_reason = f"TP1 (цена {current_price:.8f} <= {tp1_price:.8f})"

                                                    # Выполняем закрытие маркет-ордером если нужно
                                                    if close_pct:
                                                        close_amount = current_size * (close_pct / 100.0)
                                                        close_side = 'sell' if direction == 'BUY' else 'buy'

                                                        logger.info(
                                                            "🚨 [Manual Close] %s: закрываю %.0f%% "
                                                            "позиции маркет-ордером (%s)",
                                                            symbol, close_pct, close_reason
                                                        )

                                                        # Создаем маркет-ордер на закрытие
                                                        close_order = await adapter.create_market_order(
                                                            symbol=symbol,
                                                            side=close_side,
                                                            amount=close_amount
                                                        )

                                                        if close_order:
                                                            logger.info(
                                                                "✅ [Manual Close] %s: позиция закрыта "
                                                                "маркет-ордером, id=%s",
                                                                symbol, close_order.get('id')
                                                            )

                                                            # Отмечаем TP1 как сработавший если это был TP1
                                                            if 'TP1' in close_reason:
                                                                tp1_triggered.add(pos_key)
                                                                logger.info(
                                                                    "🎯 [Manual TP1] %s: TP1 достигнут "
                                                                    "через ручное закрытие",
                                                                    symbol
                                                                )

                                                            # 📊 Записываем сделку в TradeTracker (SL, TP1, TP2)
                                                            try:
                                                                from trade_tracker import get_trade_tracker

                                                                # Определяем exit_reason из close_reason
                                                                exit_reason = 'MANUAL'
                                                                if 'SL' in close_reason or 'STOP' in close_reason:
                                                                    exit_reason = 'SL'
                                                                elif 'TP1' in close_reason:
                                                                    exit_reason = 'TP1'
                                                                elif 'TP2' in close_reason:
                                                                    exit_reason = 'TP2'

                                                                # Получаем данные позиции из signals_log
                                                                from db import Database
                                                                db_local = Database()

                                                                with db_local.get_lock():
                                                                    db_local.cursor.execute("""
                                                                        SELECT entry, entry_time, qty_added, 
                                                                               leverage_used, risk_pct_used, 
                                                                               direction, signal_key, trade_mode
                                                                        FROM signals_log
                                                                        WHERE user_id = ? AND symbol = ?
                                                                        AND UPPER(IFNULL(result, 'OPEN')) LIKE 'OPEN%'
                                                                        ORDER BY created_at DESC
                                                                        LIMIT 1
                                                                    """, (uid, symbol))

                                                                    pos_row = db_local.cursor.fetchone()

                                                                    if pos_row:
                                                                        (entry_price_db, entry_time_str, _,
                                                                         leverage_db, risk_pct_db, direction_db,
                                                                         signal_key_db, trade_mode_db) = pos_row

                                                                        # Получаем TP/SL из accepted_signals
                                                                        # pylint: disable=reimported
                                                                        try:
                                                                            from src.database.acceptance import AcceptanceDatabase
                                                                        except ImportError:
                                                                            try:
                                                                                from acceptance_database import AcceptanceDatabase
                                                                            except ImportError:
                                                                                class AcceptanceDatabase:
                                                                                    async def get_signal_data(self, *args, **kwargs): return None
                                                                        adb_local_sl = AcceptanceDatabase()

                                                                        if signal_key_db:
                                                                            signal_data_sl = (
                                                                                await adb_local_sl.get_signal_data(
                                                                                    user_symbol=(uid, symbol)
                                                                                )
                                                                            )
                                                                            if signal_data_sl:
                                                                                tp1_price_sl = (
                                                                                    signal_data_sl.get(
                                                                                        'tp1_price'
                                                                                    )
                                                                                )
                                                                                tp2_price_sl = (
                                                                                    signal_data_sl.get(
                                                                                        'tp2_price'
                                                                                    )
                                                                                )
                                                                                sl_price_sl = (
                                                                                    signal_data_sl.get(
                                                                                        'sl_price'
                                                                                    )
                                                                                )
                                                                            else:
                                                                                tp1_price_sl = (
                                                                                    tp1_price
                                                                                    if 'tp1_price' in locals()
                                                                                    else None
                                                                                )
                                                                                tp2_price_sl = (
                                                                                    tp2_price
                                                                                    if 'tp2_price' in locals()
                                                                                    else None
                                                                                )
                                                                                sl_price_sl = (
                                                                                    sl_price
                                                                                    if 'sl_price' in locals()
                                                                                    else None
                                                                                )
                                                                        else:
                                                                            tp1_price_sl = (
                                                                                tp1_price
                                                                                if 'tp1_price' in locals()
                                                                                else None
                                                                            )
                                                                            tp2_price_sl = (
                                                                                tp2_price
                                                                                if 'tp2_price' in locals()
                                                                                else None
                                                                            )
                                                                            sl_price_sl = (
                                                                                sl_price
                                                                                if 'sl_price' in locals()
                                                                                else None
                                                                            )

                                                                        # Парсим entry_time
                                                                        try:
                                                                            if isinstance(entry_time_str, str):
                                                                                pos_entry_time = datetime.fromisoformat(
                                                                                    entry_time_str.replace('Z', '+00:00')
                                                                                )
                                                                            else:
                                                                                pos_entry_time = get_utc_now()
                                                                        except (ValueError, AttributeError):
                                                                            pos_entry_time = get_utc_now()

                                                                        # Рассчитываем количество для закрытия
                                                                        closed_qty = close_amount
                                                                        position_size_usdt = (
                                                                            float(entry_price_db or entry_price)
                                                                            * float(closed_qty)
                                                                        )

                                                                        # Рассчитываем комиссии с реальными данными из API
                                                                        async def _calculate_trade_fees_async(
                                                                            entry_p: float,
                                                                            exit_p: float,
                                                                            qty: float,
                                                                            mode: str,
                                                                            uid: str,
                                                                            sym: str
                                                                        ) -> float:
                                                                            """Рассчитывает реальные комиссии
                                                                            для сделки через API"""
                                                                            try:
                                                                                from exchange_fee_manager import (
                                                                                    get_real_fee_rate
                                                                                )
                                                                                fee_rate = await get_real_fee_rate(
                                                                                    uid, sym, mode, exchange_adapter=None
                                                                                )
                                                                                entry_fee = entry_p * qty * fee_rate
                                                                                exit_fee = exit_p * qty * fee_rate
                                                                                return round(entry_fee + exit_fee, 2)
                                                                            except Exception:
                                                                                # Fallback на стандартные ставки
                                                                                fee_rate = 0.001 if mode == 'spot' else 0.0005
                                                                                entry_fee = entry_p * qty * fee_rate
                                                                                exit_fee = exit_p * qty * fee_rate
                                                                                return round(entry_fee + exit_fee, 2)

                                                                        calculated_fees = await _calculate_trade_fees_async(
                                                                            float(entry_price_db or entry_price),
                                                                            float(current_price),
                                                                            float(closed_qty),
                                                                            (
                                                                                str(trade_mode_db)
                                                                                if trade_mode_db
                                                                                else 'futures'
                                                                            ),
                                                                            str(uid),
                                                                            symbol
                                                                        )

                                                                        # Записываем сделку
                                                                        tracker = get_trade_tracker()
                                                                        await tracker.record_trade(
                                                                            symbol=symbol,
                                                                            direction=direction_db or direction,
                                                                            entry_price=float(entry_price_db or entry_price),
                                                                            exit_price=float(current_price),
                                                                            entry_time=pos_entry_time,
                                                                            exit_time=get_utc_now(),
                                                                            quantity=float(closed_qty),
                                                                            position_size_usdt=position_size_usdt,
                                                                            leverage=(
                                                                                float(leverage_db)
                                                                                if leverage_db
                                                                                else 1.0
                                                                            ),
                                                                            risk_percent=(
                                                                                float(risk_pct_db)
                                                                                if risk_pct_db
                                                                                else None
                                                                            ),
                                                                            fees_usd=calculated_fees,
                                                                            exit_reason=exit_reason,
                                                                            tp1_price=(
                                                                                float(tp1_price_sl)
                                                                                if tp1_price_sl
                                                                                else None
                                                                            ),
                                                                            tp2_price=(
                                                                                float(tp2_price_sl)
                                                                                if tp2_price_sl
                                                                                else None
                                                                            ),
                                                                            sl_price=(
                                                                                float(sl_price_sl)
                                                                                if sl_price_sl
                                                                                else None
                                                                            ),
                                                                            signal_key=signal_key_db or None,
                                                                            user_id=str(uid),
                                                                            trade_mode=(
                                                                                str(trade_mode_db)
                                                                                if trade_mode_db
                                                                                else 'futures'
                                                                            ),
                                                                        )
                                                                        logger.info(
                                                                            "✅ Сделка %s записана в TradeTracker для %s",
                                                                            exit_reason,
                                                                            symbol
                                                                        )
                                                            except Exception as e:
                                                                logger.error(
                                                                    "⚠️ Ошибка записи сделки в TradeTracker: %s",
                                                                    e,
                                                                    exc_info=True
                                                                )

                                                            # Уведомляем пользователя
                                                            try:
                                                                from alert_notifications import get_alert_service
                                                                alert_svc = get_alert_service()
                                                                if hasattr(
                                                                    alert_svc, 'alert_manual_close'
                                                                ):
                                                                    await alert_svc.alert_manual_close(
                                                                        uid, symbol, close_pct,
                                                                        close_reason, current_price
                                                                    )
                                                            except Exception:
                                                                pass
                                                        else:
                                                            logger.error(
                                                                "❌ [Manual Close] %s: не удалось "
                                                                "закрыть позицию",
                                                                symbol
                                                            )

                                            except Exception as manual_err:
                                                logger.debug(
                                                    "Manual protection check skipped: %s",
                                                    manual_err
                                                )

                                    except Exception as p_err:
                                        logger.error("Ошибка синхронизации позиции %s: %s", p, p_err)

                                # Синхронизация закрытых позиций
                                try:
                                    await adb_local.sync_closed_positions(uid, open_symbols_remote)
                                except Exception as sync_err:
                                    logger.error("Ошибка sync_closed_positions для %d: %s", uid, sync_err)

                        except Exception as e:
                            logger.warning(
                                "Position monitoring error for symbol: %s",
                                e
                            )
                            continue

                        # Закрываем локально те символы, которые более не числятся открытыми на бирже
                        # ВАЖНО: Для пользователей в manual режиме НЕ закрываем позиции автоматически,
                        # так как они используют бота только как сигнал-провайдер и не открывают позиции на бирже
                        # ВАЖНО: Для spot и futures пользователей синхронизируем позиции
                        # Для futures: используем fetch_positions() (возвращает futures позиции)
                        # Для spot: позиции отслеживаются локально
                        # (spot - это баланс, но мы синхронизируем локальные позиции)
                        try:
                            # Получаем режим торговли пользователя (spot/futures)
                            try:
                                try:
                                    from src.database.db import Database
                                except ImportError:
                                    from db import Database
                                db_temp = Database()
                                user_data_temp = db_temp.get_user_data(str(uid)) or {}
                                user_trade_mode = user_data_temp.get('trade_mode', 'spot')
                            except Exception:
                                user_trade_mode = 'spot'

                            local_open = set(await adb_local.get_user_active_symbols(uid))

                            # Для spot режима: синхронизируем локальные позиции
                            # (spot - это баланс, но мы отслеживаем позиции локально)
                            # Для futures режима: синхронизируем с биржей через open_symbols_remote
                            if user_trade_mode == 'spot':
                                # Для spot: позиции отслеживаются локально, поэтому не закрываем их автоматически
                                # Пользователь сам управляет spot позициями (они - это баланс на спотовом счете)
                                logger.debug(
                                    "ℹ️ [SYNC] Пользователь %d (spot режим): позиции отслеживаются локально",
                                    uid
                                )
                                # Для spot не закрываем позиции автоматически,
                                # так как они отслеживаются локально
                                continue

                            # Для futures: закрываем позиции, если они не найдены на бирже
                            # 🛡️ УЛУЧШЕННАЯ ПРОВЕРКА: Нормализуем символы для сравнения
                            # Убеждаемся, что символы в обоих множествах в одинаковом формате
                            # ВАЖНО: Используем тот же режим торговли, что и при получении с биржи!
                            local_open_normalized = set()
                            for sym in local_open:
                                # Нормализуем символ из БД так же, как при получении с биржи (с учетом режима!)
                                sym_norm = sym.strip().upper()
                                if user_trade_mode == 'futures':
                                    # Futures: убираем суффиксы типа /USDT:USDT, /USDT
                                    if '/USDT:USDT' in sym_norm:
                                        sym_norm = sym_norm.replace('/USDT:USDT', 'USDT')
                                    elif '/USDT' in sym_norm and not sym_norm.endswith('USDT'):
                                        sym_norm = sym_norm.replace('/USDT', 'USDT')
                                else:  # spot
                                    # Spot: убираем /USDT (если не заканчивается на USDT)
                                    if '/USDT' in sym_norm and not sym_norm.endswith('USDT'):
                                        sym_norm = sym_norm.replace('/USDT', 'USDT')
                                local_open_normalized.add(sym_norm)

                            to_close = local_open_normalized - open_symbols_remote

                            # Логирование для отладки
                            logger.info(
                                "🔍 [SYNC] Пользователь %d: local_open=%s, "
                                "local_open_normalized=%s, remote_open=%s, to_close=%s",
                                uid, local_open, local_open_normalized, open_symbols_remote, to_close
                            )

                            # Проверяем режим пользователя (manual/auto)
                            user_mode = await adb_local.get_user_mode(uid)

                            for sym in to_close:
                                # 🔍 НАХОДИМ ОРИГИНАЛЬНЫЙ СИМВОЛ ИЗ БД (до нормализации)
                                # Нужно найти оригинальный символ для поиска в БД
                                # ВАЖНО: Используем ту же нормализацию, что и выше (с учетом режима!)
                                original_symbol = None
                                for orig_sym in local_open:
                                    orig_sym_norm = orig_sym.strip().upper()
                                    if user_trade_mode == 'futures':
                                        # Futures: убираем суффиксы типа /USDT:USDT, /USDT
                                        if '/USDT:USDT' in orig_sym_norm:
                                            orig_sym_norm = orig_sym_norm.replace('/USDT:USDT', 'USDT')
                                        elif '/USDT' in orig_sym_norm and not orig_sym_norm.endswith('USDT'):
                                            orig_sym_norm = orig_sym_norm.replace('/USDT', 'USDT')
                                    else:  # spot
                                        # Spot: убираем /USDT (если не заканчивается на USDT)
                                        if '/USDT' in orig_sym_norm and not orig_sym_norm.endswith('USDT'):
                                            orig_sym_norm = orig_sym_norm.replace('/USDT', 'USDT')
                                    if orig_sym_norm == sym:
                                        original_symbol = orig_sym
                                        break

                                # Если не нашли оригинальный символ, используем нормализованный
                                if not original_symbol:
                                    original_symbol = sym

                                # 🛡️ ДОП. ЗАЩИТА: пропускаем свежие позиции (<5 минут)
                                try:
                                    from datetime import timedelta
                                    try:
                                        position_info = await adb_local.get_position_data(uid, original_symbol)
                                    except Exception as pos_info_err:
                                        logger.debug("⚠️ [SYNC] Не удалось получить данные позиции %s/%s: %s",
                                                     uid, original_symbol, pos_info_err)
                                        position_info = None

                                    if position_info and position_info.get('entry_time'):
                                        try:
                                            from shared_utils import get_msk_now
                                            now_msk = get_msk_now()
                                        except (ImportError, AttributeError):
                                            now_msk = get_utc_now()

                                        entry_time_raw = position_info['entry_time']
                                        if isinstance(entry_time_raw, str):
                                            entry_time_check = datetime.strptime(entry_time_raw, '%Y-%m-%d %H:%M:%S')
                                        else:
                                            entry_time_check = datetime.fromtimestamp(entry_time_raw)

                                        now_msk_naive = now_msk.replace(tzinfo=None) if now_msk.tzinfo else now_msk
                                        age = now_msk_naive - entry_time_check

                                        if age < timedelta(minutes=5):
                                            logger.warning(
                                                "🟡 [SYNC] Пользователь %d: позиция %s слишком свежая (%s < 5 минут). "
                                                "Пропускаем авто-закрытие.",
                                                uid, original_symbol, age
                                            )
                                            continue
                                except Exception as age_err:
                                    logger.debug("⚠️ [SYNC] Ошибка дополнительной защиты %s/%s: %s",
                                                 uid, original_symbol, age_err)

                                # Дополнительное логирование перед закрытием
                                logger.warning(
                                    "⚠️ [SYNC] Пользователь %d: Позиция %s (нормализован: %s) "
                                    "есть локально, но НЕТ на бирже. "
                                    "Режим: %s. Проверяем время создания...",
                                    uid, original_symbol, sym, user_mode
                                )

                                # 🛡️ ЗАЩИТА: Не закрываем позиции,
                                # которые были открыты менее 3 минут назад
                                # Это защита от преждевременного закрытия из-за задержки
                                # появления позиции на бирже
                                # 3 минуты достаточно для появления позиции в API,
                                # но не слишком долго для пропуска реального закрытия
                                try:
                                    from datetime import timedelta
                                    import sqlite3

                                    # 🔍 ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ: Проверяем, что ищем
                                    logger.info(
                                        "🔍 [SYNC] Проверка защиты для позиции %s "
                                        "пользователя %d (ищем в БД)",
                                        sym, uid
                                    )

                                    # Получаем время создания позиции из БД
                                    with sqlite3.connect(adb_local.db_path) as conn:
                                        cursor = conn.cursor()

                                        # 🔍 ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: Смотрим все позиции
                                        # пользователя для отладки
                                        cursor.execute(
                                            """
                                            SELECT symbol, accepted_by, status, entry_time, created_at 
                                            FROM active_positions
                                            WHERE accepted_by = ?
                                            ORDER BY created_at DESC LIMIT 5
                                            """,
                                            (str(uid),)
                                        )
                                        all_positions = cursor.fetchall()
                                        logger.info(
                                            "🔍 [SYNC] Все позиции пользователя %d в БД: %s",
                                            uid, [(p[0], p[1], p[2], p[3], p[4])
                                                  for p in all_positions]
                                        )

                                        # Основной запрос для защиты
                                        # Используем оригинальный символ из БД, а не нормализованный
                                        cursor.execute(
                                            """
                                            SELECT entry_time, created_at FROM active_positions
                                            WHERE symbol = ? AND accepted_by = ? 
                                              AND UPPER(IFNULL(status,'open')) LIKE 'OPEN%'
                                            ORDER BY created_at DESC LIMIT 1
                                            """,
                                            (original_symbol, str(uid))
                                        )
                                        result = cursor.fetchone()

                                        logger.info(
                                            "🔍 [SYNC] Результат запроса для %s "
                                            "(оригинал: %s) пользователя %d: %s",
                                            sym, original_symbol, uid, result
                                        )

                                        if result:
                                            entry_time_str = result[0] or result[1]
                                            logger.info(
                                                "🔍 [SYNC] Позиция %s для пользователя %d найдена: "
                                                "entry_time=%s, created_at=%s",
                                                sym, uid, result[0], result[1]
                                            )
                                            if entry_time_str:
                                                try:
                                                    # 🛡️ ИСПРАВЛЕНИЕ: Используем московское время для сравнения
                                                    # Получаем текущее московское время
                                                    try:
                                                        from shared_utils import get_msk_now
                                                        now_msk = get_msk_now()
                                                    except (ImportError, AttributeError):
                                                        # Fallback на get_utc_now(),
                                                        # если get_msk_now недоступен
                                                        now_msk = get_utc_now()

                                                    # Парсим время создания из БД
                                                    # Время в БД теперь сохраняется в формате MSK (YYYY-MM-DD HH:MM:SS)
                                                    if isinstance(entry_time_str, str):
                                                        # Парсим строку формата 'YYYY-MM-DD HH:MM:SS'
                                                        try:
                                                            entry_time = datetime.strptime(
                                                                entry_time_str, '%Y-%m-%d %H:%M:%S'
                                                            )
                                                            # Если now_msk имеет timezone,
                                                            # приводим entry_time к нему
                                                            if now_msk.tzinfo:
                                                                # Убираем timezone у now_msk
                                                                # для сравнения с naive datetime
                                                                now_msk_naive = now_msk.replace(tzinfo=None)
                                                            else:
                                                                now_msk_naive = now_msk
                                                        except ValueError:
                                                            # Попробуем ISO формат с timezone
                                                            entry_time = datetime.fromisoformat(
                                                                entry_time_str.replace('Z', '+00:00')
                                                            )
                                                            now_msk_naive = (
                                                                now_msk.replace(tzinfo=None)
                                                                if now_msk.tzinfo else now_msk
                                                            )
                                                            entry_time = entry_time.replace(tzinfo=None)
                                                    else:
                                                        entry_time = datetime.fromtimestamp(
                                                            entry_time_str
                                                        )
                                                        now_msk_naive = (
                                                            now_msk.replace(tzinfo=None)
                                                            if now_msk.tzinfo else now_msk
                                                        )

                                                    # Проверяем, прошло ли 3 минуты
                                                    # (баланс между защитой и реакцией на закрытие)
                                                    # Это защита от задержки появления позиции
                                                    # на бирже после открытия
                                                    time_since_entry = now_msk_naive - entry_time

                                                    logger.info(
                                                        "🔍 [SYNC] Время проверки: now_msk=%s, "
                                                        "entry_time=%s, разница=%s",
                                                        now_msk_naive, entry_time, time_since_entry
                                                    )

                                                    if time_since_entry < timedelta(minutes=3):
                                                        logger.warning(
                                                            "⏸️ [SYNC] Позиция %s (оригинал: %s) "
                                                            "для пользователя %d слишком новая "
                                                            "(открыта %s назад, требуется минимум "
                                                            "3 минуты). "
                                                            "Пропускаем закрытие "
                                                            "(защита от преждевременного закрытия).",
                                                            sym, original_symbol, uid, time_since_entry
                                                        )
                                                        continue
                                                except (ValueError, TypeError) as e:
                                                    logger.warning(
                                                        "⚠️ [SYNC] Не удалось распарсить время "
                                                        "для позиции %s (оригинал: %s): %s. "
                                                        "Защита: НЕ закрываем позицию (безопасный режим)",
                                                        sym, original_symbol, e
                                                    )
                                                    # В случае ошибки парсинга НЕ закрываем позицию (безопасный режим)
                                                    continue
                                            else:
                                                logger.warning(
                                                    "⚠️ [SYNC] Позиция %s (оригинал: %s) "
                                                    "для пользователя %d: entry_time и "
                                                    "created_at пусты. "
                                                    "Защита: НЕ закрываем позицию (безопасный режим)",
                                                    sym, original_symbol, uid
                                                )
                                                continue
                                        else:
                                            logger.warning(
                                                "⚠️ [SYNC] Позиция %s (оригинал: %s) "
                                                "для пользователя %d не найдена в БД. "
                                                "Защита: НЕ закрываем позицию (безопасный режим)",
                                                sym, original_symbol, uid
                                            )
                                except Exception as e:
                                    logger.warning(
                                        "⚠️ [SYNC] Ошибка проверки времени создания позиции "
                                        "%s (оригинал: %s): %s. "
                                        "Защита: НЕ закрываем позицию (безопасный режим)",
                                        sym, original_symbol if 'original_symbol' in locals() else 'N/A', e
                                    )
                                    # В случае ошибки проверки НЕ закрываем позицию
                                    # (безопасный режим)
                                    continue

                                # Для manual режима НЕ закрываем позиции автоматически
                                # Пользователи в manual режиме используют бота только как сигнал-провайдер
                                if user_mode == 'manual':
                                    logger.debug(
                                        "⏭️ Пропущено авто-закрытие позиции %s для пользователя %d "
                                        "(manual режим - сигнал-провайдер)",
                                        sym, uid
                                    )
                                    continue

                                # Для auto режима закрываем позиции,
                                # если они не найдены на бирже
                                logger.warning(
                                    "🔴 [SYNC] Закрываем позицию %s (оригинал: %s) для пользователя %d "
                                    "(не найдена на бирже, прошло >3 минут с открытия)",
                                    sym, original_symbol, uid
                                )
                                await adb_local.close_active_position_by_symbol(uid, original_symbol)
                                # Очищаем трекинг
                                pos_key = (uid, sym)
                                if pos_key in position_sizes:
                                    del position_sizes[pos_key]
                                if pos_key in tp1_triggered:
                                    tp1_triggered.remove(pos_key)
                                if pos_key in manual_protection:
                                    del manual_protection[pos_key]
                                # Алерт о закрытии
                                try:
                                    from alert_notifications import get_alert_service
                                    alert_svc = get_alert_service()
                                    await alert_svc.alert_position_closed_by_exchange(uid, sym)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    # Проверяем позиции каждые 2 минуты для быстрой реакции
                    await asyncio.sleep(120)
                except Exception as e:
                    logger.warning("sync positions error: %s", e)
                    await asyncio.sleep(60)
        main_tasks.append(asyncio.create_task(_sync_positions_periodically()))
    except Exception as e:
        logger.warning("Не удалось запустить синхронизацию позиций: %s", e)

    # Периодическая синхронизация баланса с биржей для auto-режима
    try:
        async def _sync_balance_periodically():
            try:
                from src.database.acceptance import AcceptanceDatabase
            except ImportError:
                try:
                    from acceptance_database import AcceptanceDatabase
                except ImportError:
                    class AcceptanceDatabase:
                        async def get_users_by_mode(self, *args, **kwargs): return []
                        async def get_active_exchange_keys(self, *args, **kwargs): return []
            try:
                from src.execution.exchange_adapter import ExchangeAdapter
            except ImportError:
                from exchange_adapter import ExchangeAdapter
            try:
                from src.database.db import Database
            except ImportError:
                from db import Database
            adb_local = AcceptanceDatabase()
            db = Database()

            while True:
                try:
                    user_ids = await adb_local.get_users_by_mode('auto')
                    for uid in user_ids:
                        try:
                            keys = await adb_local.get_active_exchange_keys(uid, 'bitget')
                            if not keys:
                                continue

                            async with ExchangeAdapter('bitget', keys=keys or {}, sandbox=False) as adapter:
                                balance_data = await adapter.fetch_balance()

                                if balance_data and balance_data.get('total', 0) > 0:
                                    # Получаем текущие данные пользователя
                                    user_data = db.get_user_data(uid)
                                    if not user_data:
                                        user_data = {}

                                    # Обновляем баланс из биржи
                                    exchange_balance = balance_data['total']
                                    user_data['deposit'] = exchange_balance
                                    user_data['balance'] = exchange_balance
                                    user_data['free_deposit'] = balance_data['free']

                                    # Сохраняем обновленные данные
                                    db.save_user_data(uid, user_data)

                                    logger.info("💰 [AUTO SYNC] Баланс пользователя %s обновлен с биржи: %.2f USDT",
                                              uid, exchange_balance)
                        except Exception as e:
                            logger.debug("Ошибка синхронизации баланса для пользователя %s: %s", uid, e)
                            continue

                    # Синхронизируем каждые 5 минут
                    await asyncio.sleep(300)
                except Exception as e:
                    logger.warning("sync balance error: %s", e)
                    await asyncio.sleep(60)

        main_tasks.append(asyncio.create_task(_sync_balance_periodically()))
        logger.info("✅ Синхронизация баланса с биржей запущена (интервал: 5 мин)")
    except Exception as e:
        logger.warning("Не удалось запустить синхронизацию баланса: %s", e)
    await initialize_database_on_startup()

    # Инициализируем систему принятия сигналов
    try:
        logger.info("🎯 Инициализация системы принятия сигналов...")
        success = await initialize_signal_acceptance_system()
        if success:
            logger.info("✅ Система принятия сигналов инициализирована")

            # Передаем менеджер в telegram_handlers
            try:
                set_signal_acceptance_manager(signal_acceptance_manager)
                logger.info("✅ signal_acceptance_manager передан в telegram_handlers")
            except Exception as e:
                logger.warning("⚠️ Не удалось передать signal_acceptance_manager в telegram_handlers: %s", e)
        else:
            logger.warning("⚠️ Система принятия сигналов не инициализирована")
    except Exception as e:
        logger.error("❌ Ошибка инициализации системы принятия сигналов: %s", e)
        logger.warning("⚠️ Система будет работать без интерактивных кнопок")

    # Инициализируем список монет (если включен AUTO_FETCH_COINS)
    try:
        if not COINS:  # Если список пустой, инициализируем
            logger.info("🪙 Инициализация списка монет...")

            # Повторяем попытки с задержкой
            max_retries = 3
            retry_delay = 30  # секунд

            for attempt in range(1, max_retries + 1):
                initialized_coins = initialize_coins_sync()
                if initialized_coins:
                    # Используем инициализированные монеты
                    logger.info("✅ Загружено %d монет для анализа (попытка %d/%d)",
                               len(initialized_coins), attempt, max_retries)
                    break
                else:
                    if attempt < max_retries:
                        logger.warning("⚠️ Не удалось загрузить монеты (попытка %d/%d)",
                                     attempt, max_retries)
                        logger.info("⏳ Повторная попытка через %d секунд...", retry_delay)
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error("❌ Не удалось загрузить монеты после %d попыток", max_retries)
                        logger.info("ℹ️ Используется список монет по умолчанию")
    except (ImportError, ValueError, RuntimeError, OSError, TypeError) as e:
        logger.warning("⚠️ Ошибка инициализации списка монет: %s", e)

    # Синхронизируем данные пользователей из файла в базу данных
    try:
        logger.info("🔄 Синхронизация данных пользователей...")
        await sync_user_data_from_json_to_db()
        logger.info("✅ Синхронизация данных пользователей завершена")
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.warning("⚠️ Ошибка синхронизации данных пользователей: %s", e)

    # Одноразовая диагностика: вывод ключевых настроек пользователей
    try:
        from diagnostics_user_state import log_users_trading_config
        await log_users_trading_config()
    except Exception as e:
        logger.debug("Диагностика users_data пропущена: %s", e)

    logger.info("🚀 Запуск улучшенной торговой системы ATRA...")

    # Инициализируем интегрированные системы
    integration_results, monitoring_task = await initialize_system_integrations()
    if integration_results:  # Проверяем результаты инициализации
        logger.debug("Системы инициализированы: %s", list(integration_results.keys()))

    # Инициализируем системные настройки
        initialize_system_settings()

    # Гарантируем наличие локалей
        ensure_locales_exist()

    # Проверяем критические зависимости
    if not check_critical_dependencies():
        logger.error(
            "❌ Не удалось установить критические зависимости. "
            "Система не может запуститься."
        )
        return

    logger.info("ℹ️ Восстановление критических исправлений отключено")
    logger.info("ℹ️ Кэширование состояния отключено")

    try:
        # Предварительная очистка webhook (ОТКЛЮЧЕНО для ускорения и стабильности)
        logger.info("🧹 Пропускаем синхронную очистку webhook...")
        # if REQUESTS_AVAILABLE:
        #    ... (код очистки) ...


        # Запускаем задачи
        # Инициализируем переменные заранее, чтобы избежать NameError
        telegram_task_local = None
        print("🤖 [STDOUT] Инициализация Telegram бота...")
        logger.info("🤖 Инициализация Telegram бота...")
        logger.info("🔍 [DEBUG] Перед вызовом run_telegram_bot_in_existing_loop()...")
        print("🔍 [STDOUT] Перед вызовом run_telegram_bot_in_existing_loop()...")
        try:
            logger.info("🔍 Вызываем run_telegram_bot_in_existing_loop()...")
            print("🔍 [STDOUT] Вызываем run_telegram_bot_in_existing_loop()...")
            telegram_task_local = asyncio.create_task(run_telegram_bot_in_existing_loop())
            logger.info("✅ Telegram бот запущен успешно (задача создана)")
            print("✅ [STDOUT] Telegram бот запущен успешно (задача создана)")

            # Подключаем алерт-сервис к боту после небольшой задержки
            async def _connect_alerts():
                await asyncio.sleep(10)  # Ждём инициализации бота
                try:
                    from alert_notifications import get_alert_service
                    from src.telegram.bot_core import bot_state
                    if bot_state and bot_state.application and bot_state.application.bot:
                        get_alert_service(bot=bot_state.application.bot)
                        logger.info("✅ Алерт-сервис подключен к Telegram боту")
                except Exception as e:
                    logger.debug("Алерт-сервис: %s", e)

            asyncio.create_task(_connect_alerts())

        except Exception as e:
            logger.error("❌ Ошибка запуска Telegram бота: %s", e)
            traceback.print_exc()

        logger.info("🔧 Инициализация системы оптимизации...")
        optimization_task_local = asyncio.create_task(run_optimization_system())
        
        # 🆕 Автоматическое переобучение LightGBM моделей
        try:
            try:
                from src.ai.autonomous.learning_loop import start_autonomous_learning as start_lightgbm_auto_retrain
            except ImportError:
                from lightgbm_auto_retrain import start_lightgbm_auto_retrain
            lightgbm_retrain_task = asyncio.create_task(start_lightgbm_auto_retrain())
            logger.info("✅ Автоматическое переобучение LightGBM запущено")
        except ImportError as e:
            logger.warning("⚠️ Автоматическое переобучение LightGBM недоступно: %s", e)
        except Exception as e:
            logger.error("❌ Ошибка запуска автоматического переобучения LightGBM: %s", e)

        # 🆕 ЗАПУСК AI CONTINUOUS OPTIMIZATION
        logger.info("🧠 Инициализация AI continuous optimization...")
        ai_optimization_task_local = None
        try:
            # Создаем AI регулятор (режим обучения by default)
            ai_regulator = AdaptiveParameterController(enable_optimization=False)
            # Запускаем continuous optimization
            ai_optimization_task_local = asyncio.create_task(ai_regulator.start_continuous_optimization())
            logger.info("✅ AI continuous optimization запущен (режим обучения)")
            logger.info("💡 Оптимизация активируется автоматически после 50+ сделок")
        except Exception as e:
            logger.warning("⚠️ Не удалось запустить AI optimization: %s", e)

        # 🚀 ЗАПУСК ИСПРАВЛЕННОЙ ГИБРИДНОЙ СИСТЕМЫ СИГНАЛОВ
        # Инициализируем переменные заранее
        background_updater_task = None
        hybrid_signal_task = None

        if HYBRID_SYSTEM_AVAILABLE:
            logger.info("🚀 Инициализация ИСПРАВЛЕННОЙ гибридной системы сигналов...")

            # Инициализируем систему принятия сигналов
            logger.info("🎯 Инициализация системы принятия сигналов...")
            try:
                await initialize_signal_acceptance_system()
                logger.info("✅ Система принятия сигналов инициализирована")
            except Exception as e:
                logger.error("❌ Ошибка инициализации системы принятия сигналов: %s", e)
                traceback.print_exc()

            # ИСПРАВЛЕНО: Запускаем только исправленную версию
            try:
                hybrid_signal_task = asyncio.create_task(
                    run_hybrid_signal_system_fixed()
                )
                main_tasks.append(hybrid_signal_task)
                logger.info("✅ ИСПРАВЛЕННАЯ гибридная система сигналов запущена с улучшениями:")
                logger.info("  • Реальные фильтры вместо заглушек")
                logger.info("  • Улучшенный flood control")
                logger.info("  • Trace ID для отслеживания")
                logger.info("  • Централизованный мониторинг")
            except Exception as e:
                logger.error("❌ Ошибка запуска исправленной гибридной системы: %s", e)
                logger.warning("⚠️ Переходим к стандартной системе сигналов")
        else:
            logger.warning("⚠️ Гибридная система недоступна, используем стандартную")

        logger.info("🔄 Инициализация фильтрации по капитализации...")
        try:
            # Оборачиваем в задачу с таймаутом для возможности отмены
            market_cap_task = asyncio.create_task(initialize_market_cap_filtering())
            await asyncio.wait_for(market_cap_task, timeout=30.0)

            # Однократный прогон списков с новым порогом 50M
            logger.info("🧹 Одноразовый прогон: pending/black/white списки (50M)")
            await check_pending_symbols()
            await weekly_blacklist_check()
            await weekly_whitelist_check()
        except (asyncio.TimeoutError, asyncio.CancelledError) as e:
            logger.warning("⚠️ Инициализация фильтрации отменена или превышен таймаут: %s", e)
            # Отменяем задачу если она еще выполняется
            if 'market_cap_task' in locals() and not market_cap_task.done():
                market_cap_task.cancel()
        except (ValueError, TypeError, KeyError, RuntimeError, OSError, ConnectionError, TimeoutError) as e:
            logger.warning("⚠️ Не удалось выполнить одноразовый прогон списков: %s", e)

        # Запуск ИИ системы обучения
        if AI_AVAILABLE:
            logger.info("🤖 Инициализация системы обучения ИИ...")
            ai_learning_task = asyncio.create_task(run_ai_learning_system())
            
            # 🔄 АВТОНОМНЫЙ ЦИКЛ ОБУЧЕНИЯ (Дмитрий + Виктория)
            if start_autonomous_learning is not None:
                logger.info("🔄 Запуск автономного цикла переобучения ML...")
                autonomous_learning_task = asyncio.create_task(start_autonomous_learning(interval_hours=24))
                main_tasks.append(autonomous_learning_task)
            else:
                logger.warning("⚠️ Система автономного обучения недоступна (модуль не найден)")

        # ОТКЛЮЧЕНО: Старая система сигналов (заменена на hybrid_signal_system_fixed)
        # logger.info("📊 Инициализация системы сигналов...")
        # signal_task_local = asyncio.create_task(run_signal_system())

        logger.info("🧹 Инициализация задач ретенции БД...")
        retention_task_local = asyncio.create_task(run_retention_tasks())

        # logger.info("📈 Инициализация метрик‑фидера...")
        # metrics_task_local = asyncio.create_task(run_metrics_feeder())  # Модуль не найден
        metrics_task_local = None  # Инициализация для проверки

        # logger.info("🧠 Инициализация adaptive soft blocklist...")
        # soft_blocklist_task_local = asyncio.create_task(run_soft_blocklist_task())  # Модуль не найден
        soft_blocklist_task_local = None  # Инициализация для проверки

        # logger.info("📊 Инициализация дневной сводки и алертов...")
        # daily_summary_task_local = asyncio.create_task(run_daily_summary_and_alerts_task())  # Модуль не найден
        daily_summary_task_local = None  # Инициализация для проверки

        # logger.info("🚫 Инициализация блоклиста капитализации...")
        # market_cap_blacklist_task_local = asyncio.create_task(run_market_cap_blacklist_task())  # Модуль не найден
        market_cap_blacklist_task_local = None  # Инициализация для проверки
        # logger.info("🛡️ Инициализация strategy circuit-breaker...")
        # strategy_cb_task_local = asyncio.create_task(run_strategy_circuit_breaker_task())  # Модуль не найден
        strategy_cb_task_local = None  # Инициализация для проверки
        # logger.info("🎯 Инициализация bandit‑тюнера параметров...")
        # bandit_task_local = asyncio.create_task(run_bandit_tuner_task())  # Модуль не найден
        bandit_task_local = None  # Инициализация для проверки

        logger.info("📅 Инициализация еженедельных проверок списков...")
        weekly_check_task_local = asyncio.create_task(run_weekly_checks())

        logger.info("⏰ Инициализация ежечасных проверок списка на проверке...")
        hourly_pending_task_local = asyncio.create_task(run_hourly_pending_checks())

        # Система очистки сигналов отключена - сигналы закрываются только пользователем
        # logger.info("🧹 Инициализация системы очистки сигналов...")
        # signal_cleanup_task_local = asyncio.create_task(run_signal_cleanup())

        logger.info("📊 Инициализация системы мониторинга цен и позиций...")
        price_monitor_task_local = asyncio.create_task(run_price_monitoring())

        # Адаптивная система анализа сигналов
        async def adaptive_analysis_task():
            """Задача адаптивного анализа каждые 3 дня"""
            while True:
                try:
                    await asyncio.sleep(3600)  # Проверяем каждый час
                    if run_adaptive_analysis():
                        logger.info("🧠 Адаптивная система обновила настройки")
                except (RuntimeError, OSError, ValueError) as e:
                    logger.error("Ошибка адаптивного анализа: %s", e)
                    await asyncio.sleep(3600)  # Ждем час при ошибке

        logger.info("🧠 Инициализация адаптивной системы анализа сигналов...")
        adaptive_task_local = asyncio.create_task(adaptive_analysis_task())

        # Автоматическая очистка паттернов
        logger.info("🧹 Инициализация автоматической очистки паттернов...")
        pattern_cleanup_task_local = asyncio.create_task(start_auto_pattern_cleanup())

# 🧠 Системы улучшений агентов (менторство, A/B тестирование, KPI и т.д.)
        try:
            from src.monitoring.agent_improvements_scheduler import run_agent_improvements_scheduler_task
            # run_self_healing импортирован выше
            
            agent_improvements_task = asyncio.create_task(run_agent_improvements_scheduler_task())
            main_tasks.append(agent_improvements_task)
            
            # 🛡️ СИСТЕМА САМОВОССТАНОВЛЕНИЯ (Игорь + Сергей)
            logger.info("🛡️ Системы самовосстановления и риск-менеджмента уже запущены...")
            
            # 📅 ЕЖЕДНЕВНЫЕ ОТЧЕТЫ (Виктория)
            logger.info("📅 Запуск планировщика ежедневных отчетов (09:00)...")
            from src.monitoring.reports.daily_report import start_daily_reports
            daily_reports_task = asyncio.create_task(start_daily_reports())
            main_tasks.append(daily_reports_task)

            # 💓 SIGNAL HEARTBEAT MONITOR (Иван)
            logger.info("💓 Запуск монитора генерации сигналов (Signal Heartbeat)...")
            from src.infrastructure.monitoring.heartbeat import start_heartbeat_monitor
            # Используем путь к БД из AcceptanceDatabase для консистентности
            adb_for_path = AcceptanceDatabase()
            heartbeat_task = asyncio.create_task(start_heartbeat_monitor(db_path=adb_for_path.db_path))
            main_tasks.append(heartbeat_task)
            
            logger.info("✅ Системы улучшений агентов и самовосстановления запущены")
        except Exception as e:
            logger.warning("⚠️ Ошибка запуска систем улучшений агентов: %s", e)

        # Создаем основные задачи (только если они были созданы)
        logger.info("🔍 [DIAG] Создание main_tasks...")
        # # # main_tasks = []  # FIXED: moved to start of main()  # FIXED: moved to start of main()  # УДАЛЕНО: Список уже инициализирован в начале main()
        if telegram_task_local is not None:
            main_tasks.append(telegram_task_local)
        if optimization_task_local is not None:
            main_tasks.append(optimization_task_local)
        if retention_task_local is not None:
            main_tasks.append(retention_task_local)
        if metrics_task_local is not None:
            main_tasks.append(metrics_task_local)
        if soft_blocklist_task_local is not None:
            main_tasks.append(soft_blocklist_task_local)
        if daily_summary_task_local is not None:
            main_tasks.append(daily_summary_task_local)
        if market_cap_blacklist_task_local is not None:
            main_tasks.append(market_cap_blacklist_task_local)
        if strategy_cb_task_local is not None:
            main_tasks.append(strategy_cb_task_local)
        if bandit_task_local is not None:
            main_tasks.append(bandit_task_local)
        if weekly_check_task_local is not None:
            main_tasks.append(weekly_check_task_local)
        if hourly_pending_task_local is not None:
            main_tasks.append(hourly_pending_task_local)
        if price_monitor_task_local is not None:
            main_tasks.append(price_monitor_task_local)
        if adaptive_task_local is not None:
            main_tasks.append(adaptive_task_local)
        if pattern_cleanup_task_local is not None:
            main_tasks.append(pattern_cleanup_task_local)



        # Добавляем AI optimization task если доступен
        if ai_optimization_task_local is not None:
            main_tasks.append(ai_optimization_task_local)

        # Добавляем задачу мониторинга если доступна
        if monitoring_task:
            main_tasks.append(monitoring_task)

        # Добавляем дополнительные сервисные задачи (TTL, синк позиций)
        logger.info("🔍 [DIAG] Добавление дополнительных сервисных задач...")
        for task in tasks:
            main_tasks.append(task)

        # 🔍 Диагностика перед запуском REST API и Dashboard
        logger.info(
            "🔍 [DIAG] REST_API_AVAILABLE: %s, WEB_DASHBOARD_AVAILABLE: %s",
            REST_API_AVAILABLE, WEB_DASHBOARD_AVAILABLE
        )

        # 🚀 REST API на FastAPI (асинхронный, с поддержкой HTTPS)
        if REST_API_AVAILABLE:
            try:
                # Проверяем, нужно ли использовать HTTPS (через env переменную)
                use_https = os.getenv("USE_HTTPS", "false").lower() in ("true", "1", "yes")
                rest_api_task = asyncio.create_task(run_rest_api_async(host="0.0.0.0", port=8080, use_https=use_https))
                main_tasks.append(rest_api_task)
                protocol = "HTTPS" if use_https else "HTTP"
                logger.info("✅ REST API запущен на порту 8080 (FastAPI, %s)", protocol)
            except Exception as e:
                logger.warning("⚠️ Ошибка запуска REST API: %s", e)
        else:
            logger.info("ℹ️  REST API недоступен")

        # 🌐 Web Dashboard (с защитой БД: READONLY + WAL mode)
        if WEB_DASHBOARD_AVAILABLE:
            try:
                import threading
                def run_dashboard():
                    dashboard.run(host='0.0.0.0', port=5000, debug=False)

                dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
                dashboard_thread.start()
                logger.info("✅ Web Dashboard запущен на порту 5000 (READONLY + WAL mode)")
            except OSError as e:
                if "Address already in use" in str(e) or "address is already in use" in str(e).lower():
                    logger.warning("⚠️ Порт 5000 занят, пробуем порт 5001...")
                    try:
                        def run_dashboard_alt():
                            dashboard.run(host='0.0.0.0', port=5001, debug=False)
                        dashboard_thread = threading.Thread(target=run_dashboard_alt, daemon=True)
                        dashboard_thread.start()
                        logger.info("✅ Web Dashboard запущен на порту 5001 (READONLY + WAL mode)")
                    except Exception as e2:
                        logger.error("❌ Ошибка запуска Dashboard на альтернативном порту: %s", e2)
                else:
                    logger.warning("⚠️ Ошибка запуска Dashboard: %s", e)
            except Exception as e:
                logger.warning("⚠️ Ошибка запуска Dashboard: %s", e)
        else:
            logger.info("ℹ️  Web Dashboard недоступен")

        # Добавляем ИИ задачу если доступна
        if AI_AVAILABLE:
            main_tasks.append(ai_learning_task)

        # Добавляем систему мониторинга и автоперезапуска (ВРЕМЕННО ОТКЛЮЧЕНО)
        # ВНИМАНИЕ: system_monitor вызывает автоматические перезапуски системы
        # if SYSTEM_MONITOR_AVAILABLE and SYSTEM_MONITOR_CLASS:
        #     try:
        #         monitor = SYSTEM_MONITOR_CLASS()
        #         system_monitor_task = asyncio.create_task(monitor.monitor_loop())
        #         tasks.append(system_monitor_task)
        #         logger.info("✅ Система мониторинга и автоперезапуска запущена")
        #     except (ValueError, TypeError, KeyError, RuntimeError, OSError, ConnectionError) as e:
        #         logger.warning("⚠️ Ошибка запуска мониторинга: %s", e)
        # else:
        #     logger.warning("⚠️ Система мониторинга недоступна")
        logger.info("ℹ️ Система мониторинга временно отключена (предотвращает автоматические перезапуски)")

        # Система арбитража отключена (редко используется)
        logger.info("ℹ️ Система арбитража отключена (не используется)")

        # Добавляем системы аудита
        if AUDIT_SYSTEMS_AVAILABLE:
            try:
                async def audit_task():
                    while not shutdown_manager.shutdown_requested:
                        # Логируем активные монеты
                        audit_systems.log_active_coin("monitor", "BTCUSDT", "Мониторинг активных монет")
                        await asyncio.sleep(3600)  # Проверяем каждый час
                audit_task_instance = asyncio.create_task(audit_task())
                main_tasks.append(audit_task_instance)
                logger.info("✅ Системы аудита запущены")
            except (ValueError, TypeError, KeyError, RuntimeError, OSError, ConnectionError) as e:
                logger.warning("⚠️ Ошибка запуска систем аудита: %s", e)
        else:
            logger.warning("⚠️ Системы аудита недоступны")

        # 🆕 Добавляем систему алертов на отсутствие сигналов (Елена + Сергей - To 10/10)
        try:
            from monitoring.signal_alerts import get_signal_alert_system
            signal_alert_system = get_signal_alert_system()
            alert_task = asyncio.create_task(signal_alert_system.run_monitoring_loop())
            main_tasks.append(alert_task)
            logger.info("✅ Система алертов на отсутствие сигналов запущена")
        except Exception as e:
            logger.warning("⚠️ Ошибка запуска системы алертов: %s", e)

        # 🆕 Запуск Двигателя Эволюции (каждый час новое действие)
        if EVOLUTION_AVAILABLE:
            try:
                evolution_task = asyncio.create_task(start_evolution_task())
                main_tasks.append(evolution_task)
                logger.info("✅ Двигатель Эволюции (АТРА Evolution) запущен")
            except Exception as e:
                logger.error("❌ Ошибка запуска модуля эволюции: %s", e)

        # 🆕 Запуск Исследовательской Лаборатории (Каждый час новая гипотеза)
        if RESEARCH_AVAILABLE:
            try:
                research_task = asyncio.create_task(start_research_lab())
                main_tasks.append(research_task)
                logger.info("✅ Исследовательская Лаборатория (АТРА R&D) запущена")
            except Exception as e:
                logger.error("❌ Ошибка запуска лаборатории исследований: %s", e)

        if BACKGROUND_UPDATER_AVAILABLE:
            try:
                background_updater_task = asyncio.create_task(background_data_updater.start_background_updates())
                main_tasks.append(background_updater_task)
                logger.info("✅ Фоновый обновлятель данных запущен")
            except Exception as e:
                logger.error("❌ Ошибка запуска фонового обновлятеля: %s", e)

            # Ждем завершения всех задач с проверкой флага shutdown
        try:
            while not shutdown_manager.shutdown_requested:
                done, pending = await asyncio.wait(
                    main_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=1.0
                )

                # Проверяем завершенные задачи
                for task in done:
                    if task.cancelled():
                        logger.info("🛑 Задача отменена: %s", task.get_name())
                    elif task.exception():
                        exception = task.exception()
                        logger.error("❌ Задача завершилась с ошибкой: %s", exception)
                        logger.error("❌ Тип ошибки: %s", type(exception).__name__)

                        # Если это критическая ошибка, логируем детали
                        if isinstance(exception, (SystemExit, KeyboardInterrupt)):
                            logger.error("❌ Критическая ошибка, завершаем работу")
                            shutdown_manager.request_shutdown()
                        elif isinstance(exception, (MemoryError, OSError)):
                            logger.error("❌ Ошибка ресурсов, перезапускаем через 30 секунд")
                            await asyncio.sleep(30)
                    else:
                        logger.info("✅ Задача завершилась успешно: %s", task.get_name())

                # Если все задачи завершены и нет shutdown запроса, перезапускаем
                if not pending and not shutdown_manager.shutdown_requested:
                    logger.info("🔄 Все задачи завершены, перезапускаем...")
                    break

                main_tasks = list(pending)

            # Если получен shutdown запрос, отменяем оставшиеся задачи
            if shutdown_manager.shutdown_requested:
                logger.info("🛑 Получен запрос на остановку, отменяем %d задач...", len(main_tasks))
                for task in main_tasks:
                    if not task.done():
                        task.cancel()

                # Ждем завершения отмененных задач с увеличенным таймаутом
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*main_tasks, return_exceptions=True), timeout=15.0
                    )
                    logger.info("✅ Все задачи корректно завершены")
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Таймаут при ожидании завершения задач")
        except asyncio.CancelledError:
            logger.info("🛑 Главный цикл отменён (cancelled)")
        except RuntimeError as e:
            logger.exception("❌ Ошибка в системе: %s", e)

    except KeyboardInterrupt:
        logger.info("🛑 Система остановлена пользователем")
    except asyncio.CancelledError:
        logger.info("🛑 Система отменена (cancelled)")
    except (RuntimeError, OSError) as e:
        logger.exception("❌ Критическая ошибка: %s", e)
    finally:
        # Грациозное завершение
        try:
            tasks_to_stop = locals().get("main_tasks", [])
            if isinstance(tasks_to_stop, list):
                logger.info("🛑 Начинаем финальный graceful shutdown...")
                await graceful_shutdown(tasks_to_stop, timeout=10.0)
        except (asyncio.CancelledError, RuntimeError, OSError, TypeError, ValueError, TimeoutError) as e:
            logger.warning("⚠️ Ошибка graceful shutdown: %s", e)

        # Финальная очистка
        try:
            logger.info("🧹 Выполняем финальную очистку...")
            await cleanup()
            logger.info("✅ Финальная очистка завершена")
        except (asyncio.CancelledError, RuntimeError, OSError, TypeError, ValueError, TimeoutError) as e:
            logger.warning("⚠️ Ошибка cleanup: %s", e)

        logger.info("🏁 Система корректно завершена")


# DEBUG: Проверка что импорты завершились
print("🔍 DEBUG: Все импорты завершены, переходим к if __name__")

if __name__ == "__main__":
    print("🔍 DEBUG: Вошли в if __name__ == '__main__'")
    # CLI для различных команд
    if len(sys.argv) > 1 and sys.argv[1].lower() == "backtest":
        run_backtest_command()
    elif len(sys.argv) > 1 and sys.argv[1].lower() == "dca":
        run_dca_backtest_command()
    elif len(sys.argv) > 1 and sys.argv[1].lower() == "health":
        # run_health_check_command()
        print("Health check command temporarily disabled")
    else:
        # Улучшенный механизм блокировки для предотвращения запуска нескольких экземпляров
        LOCK_FILE = "atra.lock"

        # Проверяем существующий lock файл
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, 'r', encoding='utf-8') as f:
                    existing_pid = int(f.read().strip())
                # Проверяем, жив ли процесс
                try:
                    os.kill(existing_pid, 0)  # Проверка существования процесса
                    print(f"❌ Система уже запущена! PID: {existing_pid}")
                    print("💡 Для принудительной остановки используйте: pkill -f 'main.py'")
                    sys.exit(1)
                except (OSError, ProcessLookupError):
                    # Процесс не существует, удаляем старый lock
                    os.remove(LOCK_FILE)
                    print("🧹 Удален старый lock файл от несуществующего процесса")
            except (ValueError, OSError):
                # Некорректный lock файл, удаляем его
                os.remove(LOCK_FILE)
                print("🧹 Удален некорректный lock файл")

        # Создаем новый lock файл
        try:
            with open(LOCK_FILE, 'w', encoding='utf-8') as f:
                f.write(str(os.getpid()))
            print(f"🔒 Блокировка установлена - запуск системы (PID: {os.getpid()})")
        except (IOError, OSError):
            print("❌ Не удалось создать lock файл!")
            sys.exit(1)
        try:
            asyncio.run(main())
        finally:
            # Освобождаем lock файл
            try:
                os.remove(LOCK_FILE)
                print("Блокировка снята")
            except (OSError, IOError):
                pass
