import logging
import asyncio
import signal
import sys
import os
import json
import time
import hashlib
from types import SimpleNamespace
from telegram import BotCommand, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

# Импорты из существующих модулей
# (unused imports removed)
try:
    from src.utils.user_utils import (
        restore_user_data_to_context
    )
except ImportError:
    # Fallback для обратной совместимости
    try:
        from src.utils.user_utils import (
            restore_user_data_to_context
        )
    except ImportError:
        def restore_user_data_to_context(*args, **kwargs):
            pass

try:
    from src.bot_telegram.commands import (
        set_risk_cmd, set_balance_cmd, help_cmd, myreport_cmd,
        balance_cmd, positions_cmd, status_cmd, last_signal_cmd,
        report_cmd, set_trading_hours_cmd, backtest_cmd, perf_sys_cmd,
        backtest_all_cmd, daily_report_cmd,
        add_admin_cmd, remove_admin_cmd,
        health_cmd, report_week_cmd, audit_today_cmd,
    )
except ImportError as e:
    logging.error("❌ КРИТИЧЕСКАЯ ОШИБКА ИМПОРТА КОМАНД: %s", e)
    # Пытаемся импортировать напрямую если в корне
    try:
        from telegram_commands import (
            set_risk_cmd, set_balance_cmd, help_cmd, myreport_cmd,
            balance_cmd, positions_cmd, status_cmd, last_signal_cmd,
            report_cmd, set_trading_hours_cmd, backtest_cmd, perf_sys_cmd,
            backtest_all_cmd, daily_report_cmd,
            add_admin_cmd, remove_admin_cmd,
            health_cmd, report_week_cmd, audit_today_cmd,
        )
    except ImportError:
        raise e  # Если и это не вышло - падаем сразу, это лучше чем стабы

try:
    from src.bot_telegram.handlers import (
        start, handle_message, button, error_handler, perf, portfolio, sentiment,
        mode_cmd, mode_set_cmd,
    )
except ImportError as e:
    logging.error("❌ КРИТИЧЕСКАЯ ОШИБКА ИМПОРТА ОБРАБОТЧИКОВ: %s", e)
    # Пытаемся импортировать напрямую
    from telegram.handlers import (
        start, handle_message, button, error_handler, perf, portfolio, sentiment,
        mode_cmd, mode_set_cmd,
    )

# Импорты из новых модулей
try:
    from src.bot_telegram.commands import (
        set_trade_mode_cmd,
        set_filter_mode_cmd,
        test_signal_cmd, btc_filter_cmd, signal_stats_cmd
    )
except ImportError:
    try:
        from telegram_bot_commands import (
            set_trade_mode_cmd,
            set_filter_mode_cmd,
            test_signal_cmd, btc_filter_cmd, signal_stats_cmd
        )
    except ImportError:
        async def set_trade_mode_cmd(*args, **kwargs): pass
        async def set_filter_mode_cmd(*args, **kwargs): pass
        async def test_signal_cmd(*args, **kwargs): pass
        async def btc_filter_cmd(*args, **kwargs): pass
        async def signal_stats_cmd(*args, **kwargs): pass

try:
    from src.bot_telegram.trading import (
        close_cmd, accept_signal_cmd, close_all_positions_cmd,
        trade_history_cmd
    )
except ImportError:
    try:
        from telegram_bot_trading import (
            close_cmd, accept_signal_cmd, close_all_positions_cmd,
            trade_history_cmd
        )
    except ImportError:
        async def close_cmd(*args, **kwargs): pass
        async def accept_signal_cmd(*args, **kwargs): pass
        async def close_all_positions_cmd(*args, **kwargs): pass
        async def trade_history_cmd(*args, **kwargs): pass

try:
    from src.bot_telegram.admin import (
        add_user_cmd, remove_user_cmd, list_users_cmd
    )
except ImportError:
    try:
        from telegram_bot_admin import (
            add_user_cmd, remove_user_cmd, list_users_cmd
        )
    except ImportError:
        async def add_user_cmd(*args, **kwargs): pass
        async def remove_user_cmd(*args, **kwargs): pass
        async def list_users_cmd(*args, **kwargs): pass

try:
    from src.bot_telegram.metrics import (
        metrics_cmd, performance_cmd, trades_cmd
    )
except ImportError:
    try:
        from telegram_metrics_commands import (
            metrics_cmd, performance_cmd, trades_cmd
        )
    except ImportError:
        async def metrics_cmd(*args, **kwargs): pass
        async def performance_cmd(*args, **kwargs): pass
        async def trades_cmd(*args, **kwargs): pass
# from telegram_commands import audit_today_cmd

# Импорты из других модулей
from config import TOKEN

# Database НЕ создается при импорте! Используйте локальные экземпляры в функциях
# db = Database()  # ❌ ОТКЛЮЧЕНО - создавало подключение при импорте, ломало БД!

# Состояние бота (избегаем использования global)
bot_state = SimpleNamespace(application=None, stop_event=None)

# Экспорт совместимости: другие модули ожидают переменную bot_application
# Значение синхронизируется с bot_state.application
bot_application = None  # backward-compatible export

bot_task = None  # deprecated


# --- Single-instance lock to avoid Telegram polling conflicts ---
def _lock_path_for_token(token: str) -> str:
    try:
        h = hashlib.sha1((token or "").encode("utf-8")).hexdigest()[:12]
    except Exception:  # noqa: E722
        h = "nohash"
    return f"/tmp/atra_tg_poll_{h}.lock"


def _is_pid_running(pid: int) -> bool:
    try:
        if pid <= 0:
            return False
        # On Unix, signal 0 checks for existence
        os.kill(pid, 0)
        return True
    except Exception:  # noqa: E722
        return False


def _acquire_polling_lock(token: str) -> bool:
    path = _lock_path_for_token(token)
    now_ts = int(time.time())
    try:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                pid = int(meta.get("pid", 0))
                ts = int(meta.get("ts", 0))
            except Exception:  # noqa: E722
                pid, ts = 0, 0
            # Проверяем, жив ли процесс
            is_running = _is_pid_running(pid)
            
            # Если это наш собственный PID, разрешаем (перезапуск или повторная попытка)
            current_pid = os.getpid()
            if pid == current_pid:
                logging.info("[TG] Lock файл принадлежит текущему процессу (pid=%s). Пересоздаём lock.", pid)
                # Удаляем старый lock и создадим новый
                try:
                    os.remove(path)
                except OSError:
                    pass
            elif is_running:
                # Проверяем, не является ли это родительским процессом main.py
                # (lock может быть от основного процесса, а мы запускаемся из задачи)
                try:
                    import psutil
                    current_process = psutil.Process(current_pid)
                    parent_pid = current_process.ppid()
                    # Если lock от родительского процесса или самого процесса - разрешаем
                    if pid == parent_pid or pid == current_pid:
                        logging.info("[TG] Lock файл принадлежит родительскому процессу (pid=%s). Пересоздаём lock.", pid)
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                    else:
                        # Процесс жив и это другой процесс - блокировка валидна
                        logging.error("[TG] Поллинг уже запущен другим процессом (pid=%s). Пропускаю запуск.", pid)
                        return False
                except Exception:
                    # Если не удалось проверить - считаем что это другой процесс
                    logging.error("[TG] Поллинг уже запущен другим процессом (pid=%s). Пропускаю запуск.", pid)
                    return False
            
            # Процесс не жив - проверяем время lock файла
            file_age = now_ts - ts
            if file_age < 10:  # Файл СЛИШКОМ свежий (< 10 сек)
                # Возможно, процесс только что завершился или файл поврежден
                logging.warning("[TG] Процесс pid=%s не найден, но lock файл слишком свежий (%d сек). Подождем.", pid, file_age)
                return False
            
            # Процесс не жив - очищаем блокировку
            logging.info("[TG] Процесс pid=%s не найден. Очищаем блокировку.", pid)
            try:
                os.remove(path)
            except OSError:
                pass

        with open(path, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "ts": now_ts}, f)
        return True
    except OSError as e:
        logging.error("[TG] Не удалось установить лок поллинга: %s", e)
        return False


def _release_polling_lock(token: str) -> None:
    path = _lock_path_for_token(token)
    try:
        if os.path.exists(path):
            # Снимаем лок только если он наш
            try:
                with open(path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if int(meta.get("pid", 0)) != os.getpid():
                    return
            except Exception:  # noqa: E722
                pass
            os.remove(path)
    except OSError:
        pass

async def stop_telegram_bot():
    """Останавливает Telegram бота"""

    try:
        if bot_state.application:
            try:
                # Останавливаем polling, если доступен
                updater = getattr(bot_state.application, "updater", None)
                if updater is not None:
                    await updater.stop()
            except (RuntimeError, AttributeError):
                pass

            try:
                await bot_state.application.stop()
            except (RuntimeError, OSError):
                pass

            try:
                await bot_state.application.shutdown()
            except (RuntimeError, OSError):
                pass

            logging.info("Telegram бот остановлен")

        # Сигнализируем ожиданию завершения
        stop_event = getattr(bot_state, "stop_event", None)
        if stop_event is not None:
            setter = getattr(stop_event, "set", None)
            if callable(setter):
                try:
                    setter()
                except RuntimeError:
                    # Игнорируем возможную гонку при остановке event loop
                    pass

        # Всегда сбрасываем ссылку на приложение, даже если оно уже было None
        bot_state.application = None
        # синхронизируем экспортируемую переменную
        globals()["bot_application"] = None
        # Снимаем single-instance lock
        _release_polling_lock(TOKEN)

        # bot_task deprecated; no cancellation needed here

    except (RuntimeError, OSError) as e:
        logging.error("Ошибка при остановке бота: %s", e)

async def run_telegram_bot_in_existing_loop():
    """Запускает Telegram бота в существующем event loop"""

    try:
        print("🔍 [TG STDOUT] Начало run_telegram_bot_in_existing_loop()")
        logging.info("🔍 [TELEGRAM] Начало run_telegram_bot_in_existing_loop()")
        # Single-instance guard
        print("🔍 [TG STDOUT] Проверка lock...")
        lock_acquired = _acquire_polling_lock(TOKEN)
        print(f"🔍 [TG STDOUT] Lock получен: {lock_acquired}")
        if not lock_acquired:
            logging.error("❌ [TELEGRAM] Не удалось получить lock для polling. Telegram бот не запущен!")
            print("❌ [TG STDOUT] Не удалось получить lock для polling!")
            return
        logging.info("✅ [TELEGRAM] Lock получен, запускаем Telegram бота...")
        print("✅ [TG STDOUT] Lock получен, запускаем Telegram бота...")
        # Создаем приложение
        print("🔍 [TG STDOUT] Создаем ApplicationBuilder...")
        try:
            bot_state.application = ApplicationBuilder().token(TOKEN).build()
            print("✅ [TG STDOUT] Application создано успешно")
            # синхронизируем экспортируемую переменную
            globals()["bot_application"] = bot_state.application
        except Exception as e:
            print(f"❌ [TG STDOUT] Ошибка создания Application: {e}")
            logging.error("❌ [TELEGRAM] Ошибка создания Application: %s", e)
            raise

        # Добавляем обработчики команд
        bot_state.application.add_handler(CommandHandler("start", start))
        bot_state.application.add_handler(CommandHandler("help", help_cmd))
        bot_state.application.add_handler(CommandHandler("balance", balance_cmd))
        bot_state.application.add_handler(CommandHandler("positions", positions_cmd))
        bot_state.application.add_handler(CommandHandler("status", status_cmd))
        bot_state.application.add_handler(CommandHandler("myreport", myreport_cmd))
        # Перфоманс-сводка
        bot_state.application.add_handler(CommandHandler("perf", perf))
        # Портфельная сводка
        bot_state.application.add_handler(CommandHandler("portfolio", portfolio))
        # Сводный сентимент
        bot_state.application.add_handler(CommandHandler("sentiment", sentiment))

        # Команды настроек
        bot_state.application.add_handler(CommandHandler("set_balance", set_balance_cmd))
        bot_state.application.add_handler(CommandHandler("set_risk", set_risk_cmd))
        bot_state.application.add_handler(CommandHandler("set_trade_mode", set_trade_mode_cmd))
        bot_state.application.add_handler(CommandHandler("set_filter_mode", set_filter_mode_cmd))
        bot_state.application.add_handler(CommandHandler("set_trading_hours", set_trading_hours_cmd))
        # Режимы торговли (manual/auto)
        bot_state.application.add_handler(CommandHandler("mode", mode_cmd))
        bot_state.application.add_handler(CommandHandler("mode_set", mode_set_cmd))

        # Ключи биржи (Bitget)
        from src.bot_telegram.handlers import connect_bitget_cmd, disconnect_bitget_cmd
        bot_state.application.add_handler(CommandHandler("connect_bitget", connect_bitget_cmd))
        bot_state.application.add_handler(CommandHandler("disconnect_bitget", disconnect_bitget_cmd))

        # Команды торговли
        bot_state.application.add_handler(CommandHandler("accept", accept_signal_cmd))
        bot_state.application.add_handler(CommandHandler("close", close_cmd))
        bot_state.application.add_handler(CommandHandler("close_all", close_all_positions_cmd))
        bot_state.application.add_handler(CommandHandler("trade_history", trade_history_cmd))

        # Команды отчетов
        bot_state.application.add_handler(CommandHandler("report", report_cmd))
        bot_state.application.add_handler(CommandHandler("daily_report", daily_report_cmd))
        bot_state.application.add_handler(CommandHandler("report_week", report_week_cmd))
        bot_state.application.add_handler(CommandHandler("last_signal", last_signal_cmd))
        bot_state.application.add_handler(CommandHandler("signal_stats", signal_stats_cmd))
        bot_state.application.add_handler(CommandHandler("audit_today", audit_today_cmd))
        
        # Команды метрик производительности
        bot_state.application.add_handler(CommandHandler("metrics", metrics_cmd))
        bot_state.application.add_handler(CommandHandler("performance", performance_cmd))
        bot_state.application.add_handler(CommandHandler("trades", trades_cmd))

        # Технические команды
        bot_state.application.add_handler(CommandHandler("backtest", backtest_cmd))
        bot_state.application.add_handler(CommandHandler("backtest_all", backtest_all_cmd))
        bot_state.application.add_handler(CommandHandler("health", health_cmd))
        bot_state.application.add_handler(CommandHandler("perf_sys", perf_sys_cmd))
        bot_state.application.add_handler(CommandHandler("add_admin", add_admin_cmd))
        bot_state.application.add_handler(CommandHandler("remove_admin", remove_admin_cmd))
        bot_state.application.add_handler(CommandHandler("test_signal", test_signal_cmd))
        bot_state.application.add_handler(CommandHandler("btc_filter", btc_filter_cmd))

        # Админ команды
        bot_state.application.add_handler(CommandHandler("add_user", add_user_cmd))
        bot_state.application.add_handler(CommandHandler("remove_user", remove_user_cmd))
        bot_state.application.add_handler(CommandHandler("list_users", list_users_cmd))

        # Обработчики сообщений и кнопок
        bot_state.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        bot_state.application.add_handler(CallbackQueryHandler(button))

        # Обработчик ошибок
        bot_state.application.add_error_handler(error_handler)
        
        # Включаем автоматический перезапуск polling при ошибках сети
        print("🚀 Настройка автоматического восстановления сессии...")
        # (параметры по умолчанию обычно достаточны)

        # Восстанавливаем пользовательские данные из файлов бэкапа
        print("🔄 Восстанавливаем пользовательские данные...")
        result = restore_user_data_to_context(bot_state.application)
        print(f"🔄 Результат восстановления данных: {result}")

        # Устанавливаем список команд (подсказки в клиенте)
        try:
            commands = [
                BotCommand("start", "🚀 Запустить бота"),
                BotCommand("help", "📋 Справка"),
                BotCommand("balance", "💰 Баланс"),
                BotCommand("positions", "📊 Открытые позиции"),
                BotCommand("trade_history", "📈 История сделок"),
                BotCommand("trades", "📋 Последние сделки (метрики)"),
                BotCommand("metrics", "📊 Метрики производительности"),
                BotCommand("performance", "📈 Статистика по символу"),
                BotCommand("signal_stats", "📊 Статистика сигналов"),
                BotCommand("perf", "📊 Сводка эффективности (7 дн. по умолчанию)"),
                BotCommand("portfolio", "📊 Сводка портфеля пользователя"),
                BotCommand("sentiment", "🧭 Рыночный сентимент по монете"),
                BotCommand("audit_today", "🧾 Аудит сигналов за сегодня"),
                BotCommand("myreport", "📑 Персональный отчёт"),
                BotCommand("status", "📊 Статус системы"),
                BotCommand("last_signal", "📡 Последний сигнал"),
                BotCommand("set_balance", "💵 Установить баланс"),
                BotCommand("set_trade_mode", "⚙️ Режим торговли (spot|futures)"),
                BotCommand("set_filter_mode", "⚙️ Режим фильтров (soft|strict)"),
                BotCommand("set_trading_hours", "⏰ Торговые часы (HH:MM-HH:MM)"),
                BotCommand("mode", "⚙️ Показать режим торговли (manual|auto)"),
                BotCommand("mode_set", "⚙️ Установить режим торговли (manual|auto)"),
                BotCommand("connect_bitget", "🔐 Подключить ключи Bitget"),
                BotCommand("disconnect_bitget", "🔐 Отключить ключи Bitget"),
                BotCommand("report", "🗓️ Отчёт за день"),
                BotCommand("report_week", "📅 Отчёт за неделю"),
                BotCommand("health", "🩺 Проверка здоровья системы"),
                BotCommand("backtest", "🧪 Бэктест (один символ)"),
                BotCommand("backtest_all", "🧪 Бэктест (несколько символов)"),
                BotCommand("add_user", "➕ Добавить пользователя"),
                BotCommand("remove_user", "➖ Удалить пользователя"),
                BotCommand("list_users", "📋 Список пользователей"),
            ]
            await bot_state.application.bot.set_my_commands(commands)
        except (RuntimeError, ValueError, TypeError) as e:
            logging.warning("set_my_commands failed: %s", e)

        # Явно удаляем webhook перед polling и сбрасываем хвост апдейтов
        try:
            me = await bot_state.application.bot.get_me()
            logging.info("Bot authorized: @%s (%s)", me.username, me.id)
            await bot_state.application.bot.delete_webhook(drop_pending_updates=True)
        except (RuntimeError, ValueError, TypeError) as e:
            logging.warning("Не удалось удалить webhook: %s", e)

        # Запускаем бота в существующем loop через initialize/start + start_polling
        logging.info("🚀 [TELEGRAM] Инициализация Application...")
        await bot_state.application.initialize()
        logging.info("🚀 [TELEGRAM] Запуск Application...")
        await bot_state.application.start()
        
        logging.info("🚀 [TELEGRAM] Поиск Updater...")
        updater = getattr(bot_state.application, "updater", None)
        if updater is not None:
            logging.info("🚀 [TELEGRAM] Запуск Polling через Updater...")
            await updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
            logging.info("✅ [TELEGRAM] Polling запущен!")
            # Создаем stop_event для остановки
            bot_state.stop_event = asyncio.Event()
            
            # Отправляем приветственное сообщение Ивану (тест связи)
            try:
                await bot_state.application.bot.send_message(
                    chat_id=556251171,
                    text="🤖 ATRA PROD Bot запущен и готов к командам! Попробуй /status"
                )
                logging.info("✅ Тестовое сообщение отправлено Ивану")
            except Exception as e:
                logging.error("❌ Не удалось отправить тестовое сообщение: %s", e)

            # Polling работает в фоне, не блокируем event loop
            # Ждем сигнала остановки в бесконечном цикле, чтобы не блокировать обработку команд
            try:
                while not bot_state.stop_event.is_set():
                    await asyncio.sleep(1)  # Проверяем каждую секунду
            except asyncio.CancelledError:
                logging.info("Telegram бот получил сигнал отмены")
        else:
            # Фолбэк на run_polling, если updater недоступен
            await bot_state.application.run_polling(close_loop=False)
        logging.info("Telegram бот завершил работу")

    except (RuntimeError, OSError) as e:
        logging.error("Ошибка при запуске бота: %s", e)
        raise

async def run_telegram_bot_with_retry():
    """Запускает бота с повторными попытками"""

    max_retries = 10  # Увеличено с 1 до 10 для отказоустойчивости
    retry_delay = 10  # Начальная задержка 10 секунд

    for attempt in range(max_retries):
        try:
            logging.info("Попытка запуска бота %s/%s", attempt + 1, max_retries)
            # Запускаем бота напрямую, а не как отдельную задачу
            await run_telegram_bot_in_existing_loop()
            # Если дошли сюда, значит бот запустился успешно
            logging.info("Telegram бот успешно завершил работу")
            return

        except Exception as e:  # Ловим все исключения для ретрая
            logging.error("Ошибка запуска/работы бота (попытка %s): %s", attempt + 1, e)
            if "nodename nor servname provided, or not known" in str(e):
                logging.warning("⚠️ Обнаружена сетевая ошибка DNS. Возможно, временный сбой сети.")

            if attempt < max_retries - 1:
                logging.info("Повторная попытка через %s секунд...", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 300)  # Экспоненциальная задержка, макс 5 минут
            else:
                logging.error("Все попытки запуска бота исчерпаны")
                raise

def is_bot_ready():
    """Проверяет готовность бота"""
    return bot_state.application is not None and bot_state.application.running

def run_telegram_bot_stub(*_args, **_kwargs):
    """Заглушка для запуска бота"""
    logging.warning("Запуск бота через заглушку - используйте run_telegram_bot()")

# Обработчик сигналов для корректного завершения
def signal_handler(signum, _):
    """Обработчик сигналов для корректного завершения"""
    logging.info("Получен сигнал %s, завершаю работу...", signum)
    asyncio.create_task(stop_telegram_bot())
    sys.exit(0)

# Регистрируем обработчики сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Совместимость: реэкспорт функций уведомлений через тонкие обёртки
async def notify_user(user_id, text, **kwargs):
    """Отправляет сообщение пользователю (совместимая обёртка)."""
    try:
        from src.bot_telegram.handlers import notify_user as _notify_user
    except ImportError:
        try:
            from .handlers import notify_user as _notify_user
        except ImportError:
            async def _notify_user(*args, **kwargs): pass
    return await _notify_user(user_id, text, **kwargs)

async def notify_all(text, **kwargs):
    """Отправляет сообщение всем пользователям (совместимая обёртка)."""
    try:
        from src.bot_telegram.handlers import notify_all as _notify_all
    except ImportError:
        try:
            from .handlers import notify_all as _notify_all
        except ImportError:
            async def _notify_all(*args, **kwargs): pass
    return await _notify_all(text, **kwargs)

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('telegram_bot.log'),
            logging.StreamHandler()
        ]
    )

    # Запускаем бота
    try:
        asyncio.run(run_telegram_bot_with_retry())
    except KeyboardInterrupt:
        logging.info("Получен сигнал прерывания, завершаю работу...")
    except (RuntimeError, OSError) as e:
        logging.error("Критическая ошибка: %s", e)
        sys.exit(1)
