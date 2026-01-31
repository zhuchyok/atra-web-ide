"""
Модуль команд Telegram бота для торговых сигналов.

Этот модуль содержит все команды и обработчики для Telegram бота,
включая статистику, позиции, историю сделок и административные функции.
"""

import logging
import sqlite3

from telegram import Update
from telegram.ext import ContextTypes

from config import DATABASE, ATRA_ENV
from src.database.db import Database
from src.shared.utils.datetime_utils import get_utc_now

try:
    from src.bot_telegram.utils import safe_format_price
except ImportError:
    try:
        from telegram_utils import safe_format_price
    except ImportError:
        def safe_format_price(price, symbol=None):
            """Fallback for safe_format_price."""
            return f"{price:.5f}"

# Singleton Database instance с lazy initialization для telegram_commands
DB_COMMANDS = None

def get_db_commands():
    """Получает или создает экземпляр Database для telegram_commands (singleton с lazy init)"""
    global DB_COMMANDS
    if DB_COMMANDS is None:
        try:
            DB_COMMANDS = Database()
            logging.info("✅ Database инициализирован для commands.py")
        except Exception as e:
            logging.error("❌ Ошибка инициализации Database в commands.py: %s", e)
    return DB_COMMANDS

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статус системы (упрощенный)"""
    try:
        user_id = update.effective_user.id if update and update.effective_user else "unknown"
        logging.info("🔔 [COMMAND] /status вызван пользователем %s", user_id)

        message = "📊 <b>Статус ATRA</b>\n\n"
        message += "✅ Система: Работает\n"
        message += f"🌍 Режим: <code>{ATRA_ENV.upper()}</code>\n"
        message += f"📅 Время: <code>{get_utc_now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
        message += "\n📡 <b>Сеть:</b>\n"
        message += "• API Binance: ✅\n"
        message += "• База данных: ✅\n"
        message += "\n💡 <i>Команда упрощена для стабильности.</i>"

        await update.message.reply_text(message, parse_mode='HTML')
        print("✅ [TELEGRAM] /status: Ответ отправлен успешно")
    except Exception as e:
        logging.error("Ошибка в упрощенном status_cmd: %s", e)
        try:
            await update.message.reply_text("❌ Ошибка при получении статуса")
        except Exception:
            pass

async def perf_sys_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сводка системной телеметрии (циклы, API) за последние 24 часа."""
    try:
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        query = (
            "SELECT COUNT(*), IFNULL(AVG(duration_sec),0.0), IFNULL(MAX(duration_sec),0.0) "
            "FROM telemetry_cycles WHERE datetime(ts) >= datetime('now','-1 day')"
        )
        cur.execute(query)
        c_row = cur.fetchone() or (0, 0.0, 0.0)
        cycles_cnt = int(c_row[0] or 0)
        cycles_avg = float(c_row[1] or 0.0)
        cycles_max = float(c_row[2] or 0.0)
        conn.close()

        text = (
            "🖥️ <b>PERF SYS (24h)</b>\n\n"
            f"Циклов: <code>{cycles_cnt}</code> | avg: <code>{cycles_avg:.2f}s</code> "
            f"| max: <code>{cycles_max:.2f}s</code>\n"
        )
        await update.message.reply_text(text, parse_mode='HTML')
    except Exception as e:
        logging.error("perf_sys_cmd error: %s", e)
        await update.message.reply_text("❌ Ошибка телеметрии")

async def add_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет администратора."""
    try:
        user_id = update.effective_user.id
        db_instance = get_db_commands()
        if not db_instance:
            return
        admins = db_instance.get_admin_ids()
        if user_id not in admins:
            await update.message.reply_text("❌ Нет прав")
            return
        parts = (update.message.text or "").split()
        if len(parts) < 2:
            await update.message.reply_text("Использование: /add_admin <user_id>")
            return
        target = int(parts[1])
        ok = db_instance.set_user_admin(target, True)
        await update.message.reply_text("✅ Админ добавлен" if ok else "❌ Ошибка")
    except Exception as e:
        logging.error("add_admin_cmd error: %s", e)
        await update.message.reply_text("❌ Ошибка")

async def remove_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет администратора."""
    try:
        user_id = update.effective_user.id
        db_instance = get_db_commands()
        if not db_instance:
            return
        admins = db_instance.get_admin_ids()
        if user_id not in admins:
            await update.message.reply_text("❌ Нет прав")
            return
        parts = (update.message.text or "").split()
        if len(parts) < 2:
            await update.message.reply_text("Использование: /remove_admin <user_id>")
            return
        target = int(parts[1])
        ok = db_instance.set_user_admin(target, False)
        await update.message.reply_text("✅ Админ удалён" if ok else "❌ Ошибка")
    except Exception as e:
        logging.error("remove_admin_cmd error: %s", e)
        await update.message.reply_text("❌ Ошибка")

async def audit_today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает аудит за сегодня (упрощенный)."""
    await update.message.reply_text("📊 Аудит временно упрощен.")

async def last_signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает последний сигнал."""
    try:
        user_id = update.effective_user.id
        db_instance = get_db_commands()
        if db_instance:
            latest = db_instance.get_last_signal_log(user_id=user_id)
            if latest:
                symbol = latest.get('symbol', 'N/A')
                entry = latest.get('entry', 'N/A')
                msg = (
                    f"📡 <b>Последний сигнал</b>\n\n"
                    f"🔸 Символ: <code>{symbol}</code>\n"
                    f"🔸 Цена: <code>{entry}</code>"
                )
                await update.message.reply_text(msg, parse_mode='HTML')
                return
        await update.message.reply_text("📭 Нет записей")
    except Exception as e:
        logging.error("last_signal_cmd error: %s", e)
        await update.message.reply_text("❌ Ошибка")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает справку по командам."""
    help_text = (
        "📋 <b>Доступные команды:</b>\n\n"
        "/status - Статус системы\n"
        "/balance - Твой баланс\n"
        "/positions - Открытые позиции\n"
        "/mode - Режим торговли\n"
        "/connect_bitget - Подключить ключи\n"
        "/help - Эта справка"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

async def set_risk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает процент риска на сделку"""
    try:
        user_id = update.effective_user.id
        if not context.args:
            await update.message.reply_text("Использование: /set_risk <процент>")
            return
        
        risk = float(context.args[0])
        db_instance = get_db_commands()
        if db_instance:
            user_data = db_instance.get_user_data(user_id) or {}
            user_data['risk_pct'] = risk
            db_instance.save_user_data(user_id, user_data)
            await update.message.reply_text(f"✅ Риск установлен: <code>{risk}%</code>", parse_mode='HTML')
        else:
            await update.message.reply_text("❌ Ошибка базы данных")
    except Exception as e:
        logging.error("set_risk_cmd error: %s", e)
        await update.message.reply_text("❌ Ошибка при установке риска")

async def set_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает баланс (депозит) пользователя"""
    try:
        user_id = update.effective_user.id
        if not context.args:
            await update.message.reply_text("Использование: /set_balance <сумма>")
            return
        
        amount = float(context.args[0])
        db_instance = get_db_commands()
        if db_instance:
            user_data = db_instance.get_user_data(user_id) or {}
            user_data['deposit'] = amount
            user_data['balance'] = amount
            db_instance.save_user_data(user_id, user_data)
            await update.message.reply_text(f"✅ Баланс установлен: <code>{amount:.2f} USDT</code>", parse_mode='HTML')
        else:
            await update.message.reply_text("❌ Ошибка базы данных")
    except Exception as e:
        logging.error("set_balance_cmd error: %s", e)
        await update.message.reply_text("❌ Ошибка при установке баланса")

async def myreport_cmd(*args, **kwargs):
    """Stub for myreport_cmd."""

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает баланс пользователя (из БД или с биржи)"""
    try:
        user_id = update.effective_user.id
        logging.info("💰 [COMMAND] /balance вызван пользователем %s", user_id)

        from src.database.acceptance import AcceptanceDatabase
        adb = AcceptanceDatabase()
        
        # 1. Пробуем получить реальный баланс с биржи
        keys = await adb.get_active_exchange_keys(user_id)
        if keys:
            try:
                from src.execution.exchange_adapter import ExchangeAdapter
                async with ExchangeAdapter('bitget', keys=keys) as adapter:
                    balance_data = await adapter.fetch_balance()
                    if balance_data:
                        total = balance_data.get('total', 0)
                        free = balance_data.get('free', 0)
                        used = balance_data.get('used', 0)
                        
                        msg = (
                            "💰 <b>Баланс Bitget</b>\n\n"
                            f"💵 <b>Всего:</b> <code>{total:.2f} USDT</code>\n"
                            f"🔓 <b>Доступно:</b> <code>{free:.2f} USDT</code>\n"
                            f"🔒 <b>В сделках:</b> <code>{used:.2f} USDT</code>\n\n"
                            "🛰️ <i>Данные получены напрямую с биржи.</i>"
                        )
                        await update.message.reply_text(msg, parse_mode='HTML')
                        return
            except Exception as e:
                logging.warning("⚠️ Не удалось получить баланс с биржи для %s: %s", user_id, e)

        # 2. Fallback: Баланс из локальной БД (users_data)
        db_instance = get_db_commands()
        user_data = db_instance.get_user_data(user_id) if db_instance else None
        
        if user_data:
            deposit = float(user_data.get('deposit', 0))
            current_balance = float(user_data.get('balance', deposit))
            
            msg = (
                "💰 <b>Локальный баланс</b>\n\n"
                f"💵 <b>Депозит:</b> <code>{deposit:.2f} USDT</code>\n"
                f"💳 <b>Текущий:</b> <code>{current_balance:.2f} USDT</code>\n"
                f"📊 <b>PnL:</b> <code>{current_balance - deposit:+.2f} USDT</code>\n\n"
                "💡 <i>Для просмотра реального баланса подключите API Bitget.</i>"
            )
            await update.message.reply_text(msg, parse_mode='HTML')
        else:
            await update.message.reply_text(
                "❌ <b>Данные не найдены</b>\n\n"
                "Используйте /start для инициализации или /connect_bitget для подключения биржи.",
                parse_mode='HTML'
            )

    except Exception as e:
        logging.error("Ошибка в balance_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при получении баланса")

async def positions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список открытых позиций пользователя (из БД или с биржи)"""
    try:
        user_id = update.effective_user.id
        logging.info("📋 [COMMAND] /positions вызван пользователем %s", user_id)

        from src.database.acceptance import AcceptanceDatabase
        adb = AcceptanceDatabase()
        
        # 1. Пробуем получить реальные позиции с биржи
        keys = await adb.get_active_exchange_keys(user_id)
        if keys:
            try:
                from src.execution.exchange_adapter import ExchangeAdapter
                async with ExchangeAdapter('bitget', keys=keys) as adapter:
                    exchange_positions = await adapter.fetch_positions()
                    
                    # Фильтруем только реально открытые позиции (size > 0)
                    active_exchange_positions = []
                    if exchange_positions:
                        for pos in exchange_positions:
                            # У Bitget/ccxt позиции могут иметь contracts или size
                            size = float(pos.get('contracts', 0) or pos.get('size', 0) or 0)
                            if size > 0:
                                active_exchange_positions.append(pos)

                if active_exchange_positions:
                    message = f"📋 <b>ОТКРЫТЫЕ ПОЗИЦИИ ({len(active_exchange_positions)})</b>\n\n"
                    for idx, pos in enumerate(active_exchange_positions, start=1):
                        symbol = pos.get('symbol', 'N/A').replace(':USDT', '')
                        side = pos.get('side', 'N/A').upper()
                        side_emoji = "🟢" if side in ('LONG', 'BUY') else "🔴"
                        entry_price = float(pos.get('entryPrice') or pos.get('avgCost') or 0)
                        mark_price = float(pos.get('markPrice') or 0)
                        pnl = float(pos.get('unrealizedPnl') or 0)
                        pnl_pct = float(pos.get('percentage') or 0)
                        
                        entry_str = safe_format_price(entry_price, symbol)
                        mark_str = safe_format_price(mark_price, symbol)
                        
                        message += f"{idx}. {side_emoji} <b>{symbol}</b> {side}\n"
                        message += f"├ Вход: <code>{entry_str}</code>\n"
                        message += f"├ Тек.: <code>{mark_str}</code>\n"
                        message += f"└ PnL: <b>{pnl:+.2f} USDT ({pnl_pct:+.2f}%)</b>\n\n"
                    
                    message += "🛰️ <i>Данные получены напрямую с биржи.</i>"
                    await update.message.reply_text(message, parse_mode='HTML')
                    return
            except Exception as e:
                logging.warning("⚠️ Не удалось получить позиции с биржи для %s: %s", user_id, e)

        # 2. Fallback: Позиции из локальной БД (active_positions)
        db_positions = await adb.get_active_positions_by_user(str(user_id))
        if db_positions:
            message = f"📋 <b>ОТКРЫТЫЕ ПОЗИЦИИ ({len(db_positions)})</b>\n\n"
            for idx, pos in enumerate(db_positions, start=1):
                symbol = pos.get('symbol', 'N/A')
                side = pos.get('direction', 'N/A').upper()
                side_emoji = "🟢" if side in ('LONG', 'BUY') else "🔴"
                entry_price = float(pos.get('entry_price') or 0)
                
                entry_str = safe_format_price(entry_price, symbol)
                
                message += f"{idx}. {side_emoji} <b>{symbol}</b> {side}\n"
                message += f"├ Вход: <code>{entry_str}</code>\n"
                message += f"└ <i>Статус: Открыта (локально)</i>\n\n"
            
            message += "💡 <i>Подключите API для отображения реального PnL.</i>"
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("📭 <b>У вас нет открытых позиций</b>", parse_mode='HTML')

    except Exception as e:
        logging.error("Error in positions_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при получении списка позиций")

async def report_cmd(*args, **kwargs):
    """Stub for report_cmd."""

async def set_trading_hours_cmd(*args, **kwargs):
    """Stub for set_trading_hours_cmd."""

async def backtest_cmd(*args, **kwargs):
    """Stub for backtest_cmd."""

async def backtest_all_cmd(*args, **kwargs):
    """Stub for backtest_all_cmd."""

async def daily_report_cmd(*args, **kwargs):
    """Stub for daily_report_cmd."""

async def report_week_cmd(*args, **kwargs):
    """Stub for report_week_cmd."""

async def health_cmd(*args, **kwargs):
    """Stub for health_cmd."""

async def set_trade_mode_cmd(*args, **kwargs):
    """Stub for set_trade_mode_cmd."""

async def set_filter_mode_cmd(*args, **kwargs):
    """Stub for set_filter_mode_cmd."""

async def test_signal_cmd(*args, **kwargs):
    """Stub for test_signal_cmd."""

async def btc_filter_cmd(*args, **kwargs):
    """Stub for btc_filter_cmd."""

async def signal_stats_cmd(*args, **kwargs):
    """Stub for signal_stats_cmd."""
