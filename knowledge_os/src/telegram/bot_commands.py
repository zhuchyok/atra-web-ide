"""
Модуль команд Telegram-бота для управления торговыми режимами и просмотра статистики.
"""

import asyncio
import csv
import logging
import os
from datetime import datetime, timedelta

from src.core.state import signals_log_path
from src.database.db import Database
from src.shared.utils.datetime_utils import get_utc_now
from src.telegram.handlers import start_accept_button_countdown
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

# Импорты из наших модулей
try:
    from src.telegram.utils import calculate_user_leverage
except ImportError:

    def calculate_user_leverage(*args, **kwargs):
        """Фолбэк для расчета плеча"""
        return 1.0


# Инициализация базы данных
db = Database()


async def set_trade_mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Устанавливает режим торговли для пользователя.
    Использование: /set_trade_mode <spot|futures>
    """
    try:
        if not context.args or len(context.args) < 1:
            await update.message.reply_text("Использование: /set_trade_mode <spot|futures>")
            return

        mode = context.args[0].lower()
        if mode not in ["spot", "futures"]:
            await update.message.reply_text("Режим должен быть 'spot' или 'futures'")
            return

        user_id = update.effective_user.id

        # Загружаем данные пользователя из БД
        user_data = db.get_user_data(str(user_id))
        if not user_data:
            user_data = {}

        # Обновляем режим торговли
        user_data["trade_mode"] = mode

        # Обновляем плечо в зависимости от режима
        if mode == "spot":
            user_data["leverage"] = 1
        elif mode == "futures":
            # Используем расчетное плечо если доступно
            if all(key in user_data for key in ["deposit", "filter_mode"]):
                user_data["leverage"] = calculate_user_leverage(
                    user_data["deposit"], mode, user_data["filter_mode"]
                )
            else:
                user_data["leverage"] = user_data.get(
                    "leverage", 10
                )  # По умолчанию 10x для futures

        # Сохраняем в базу данных
        db.save_user_data(str(user_id), user_data)

        # Также обновляем context.user_data для текущей сессии
        context.user_data.update(user_data)

        await update.message.reply_text(
            f"✅ Режим торговли установлен: {mode.upper()}\n"
            f"⚡ Плечо: {user_data['leverage']}x\n"
            f"💾 Данные сохранены в БД"
        )

    except (ValueError, IndexError) as e:
        logging.error("Ошибка в set_trade_mode_cmd: %s", e)
        await update.message.reply_text("Ошибка: укажите корректный режим (spot|futures)")
    except Exception as e:
        logging.error("Ошибка в set_trade_mode_cmd: %s", e, exc_info=True)
        await update.message.reply_text("❌ Ошибка при установке режима торговли")


async def set_trade_mode_spot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает режим торговли spot"""
    try:
        user_data = context.user_data

        user_data["trade_mode"] = "spot"
        user_data["leverage"] = 1

        await update.message.reply_text("✅ Режим торговли установлен: spot")

    except Exception as e:
        logging.error("Ошибка в set_trade_mode_spot_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при установке режима")


async def set_trade_mode_futures_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает режим торговли futures"""
    try:
        user_data = context.user_data

        user_data["trade_mode"] = "futures"

        # Пересчитываем плечо
        if all(key in user_data for key in ["deposit", "filter_mode"]):
            user_data["leverage"] = calculate_user_leverage(
                user_data["deposit"], "futures", user_data["filter_mode"]
            )

        await update.message.reply_text("✅ Режим торговли установлен: futures")

    except Exception as e:
        logging.error("Ошибка в set_trade_mode_futures_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при установке режима")


async def set_filter_mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает режим фильтров (soft|strict)"""
    try:
        if not context.args or len(context.args) < 1:
            await update.message.reply_text("Использование: /set_filter_mode <soft|strict>")
            return

        mode = context.args[0].lower()
        if mode not in ["soft", "strict"]:
            await update.message.reply_text("Режим должен быть 'soft' или 'strict'")
            return

        user_data = context.user_data

        user_data["filter_mode"] = mode

        # Пересчитываем плечо
        if all(key in user_data for key in ["deposit", "trade_mode"]):
            user_data["leverage"] = calculate_user_leverage(
                user_data["deposit"], user_data["trade_mode"], mode
            )

        await update.message.reply_text(f"✅ Режим фильтров установлен: {mode}")

    except (ValueError, IndexError):
        await update.message.reply_text("Ошибка: укажите 'soft' или 'strict'")


async def set_filter_strict_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает строгий режим фильтров"""
    try:
        user_data = context.user_data

        user_data["filter_mode"] = "strict"

        # Пересчитываем плечо
        if all(key in user_data for key in ["deposit", "trade_mode"]):
            user_data["leverage"] = calculate_user_leverage(
                user_data["deposit"], user_data["trade_mode"], "strict"
            )

        await update.message.reply_text("✅ Режим фильтров установлен: strict")

    except Exception as e:
        logging.error("Ошибка в set_filter_strict_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при установке режима")


async def set_filter_soft_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает мягкий режим фильтров"""
    try:
        user_data = context.user_data

        user_data["filter_mode"] = "soft"

        # Пересчитываем плечо
        if all(key in user_data for key in ["deposit", "trade_mode"]):
            user_data["leverage"] = calculate_user_leverage(
                user_data["deposit"], user_data["trade_mode"], "soft"
            )

        await update.message.reply_text("✅ Режим фильтров установлен: soft")

    except Exception as e:
        logging.error("Ошибка в set_filter_soft_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при установке режима")


async def test_signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестирует отправку сигнала с кнопкой и обратным отсчётом."""
    try:
        user_data = context.user_data

        # Тестовые параметры
        symbol = "BTCUSDT"
        side = "long"
        entry_price = 50000.0
        risk_pct = float(user_data.get("risk_pct", 2.0) or 2.0)
        leverage = float(user_data.get("leverage", 1) or 1)

        # Сообщение
        signal_text = (
            "📡 <b>Тестовый сигнал</b>\n\n"
            f"🔸 Символ: <code>{symbol}</code>\n"
            f"🔸 Сторона: <code>{side.upper()}</code>\n"
            f"🔸 Цена входа: <code>{entry_price:.2f}</code>\n"
            f"🔸 Время: <code>{get_utc_now().strftime('%H:%M:%S')}</code>\n\n"
            "💡 Это тестовый сигнал для проверки кнопки с таймером."
        )

        # Callback data в рабочем формате: accept|symbol|time|price|side|risk|leverage
        short_time = get_utc_now().strftime("%m%d%H%M")
        cb = f"accept|{symbol}|{short_time}|{entry_price:.2f}|{side}|{risk_pct:.1f}|{leverage:.1f}"

        # Стартовая метка таймера на кнопке (1 час)
        initial_label = "Принять (60:00)"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(initial_label, callback_data=cb)]])

        # Отправляем сообщение
        msg = await update.message.reply_text(signal_text, parse_mode="HTML", reply_markup=keyboard)

        # Фиксируем активный сигнал с TTL в БД
        chat_id = update.effective_chat.id
        try:
            expiry_iso = (get_utc_now() + timedelta(hours=1.0)).isoformat()
            entry_time_iso = get_utc_now().strftime("%Y-%m-%dT%H:%M")
            signal_key = f"{symbol}|{short_time}|{side}"
            db.add_active_signal_with_expiry(
                signal_key,
                "active",
                expiry_iso,
                entry_time=entry_time_iso,
                chat_id=chat_id,
                message_id=msg.message_id,
            )
        except Exception:
            expiry_iso = (get_utc_now() + timedelta(hours=1.0)).isoformat()

        # Запускаем обратный отсчёт (фоново)
        try:
            asyncio.create_task(
                start_accept_button_countdown(int(chat_id), int(msg.message_id), expiry_iso, cb)
            )
        except Exception:
            pass

    except Exception as e:
        logging.error("Ошибка в test_signal_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при отправке тестового сигнала")


async def btc_filter_cmd(update: Update, *_):
    """Показывает статус BTC фильтра"""
    try:
        # Здесь можно добавить логику проверки BTC фильтра
        btc_status = "✅ Активен"

        status_text = f"""
   🔸 *BTC Фильтр*

   Статус: {btc_status}
   Текущая цена BTC: $N/A
   Тренд: N/A

   💡 Фильтр проверяет направление тренда BTC перед отправкой сигналов.
   """

        await update.message.reply_text(status_text, parse_mode="HTML")

    except Exception as e:
        logging.error("Ошибка в btc_filter_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при получении статуса BTC фильтра")


async def active_signals_cmd(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Показывает активные сигналы"""
    try:
        # Здесь можно добавить логику получения активных сигналов
        await update.message.reply_text("📡 Активные сигналы будут показаны позже")

    except Exception as e:
        logging.error("Ошибка в active_signals_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при получении активных сигналов")


async def signal_stats_cmd(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику сигналов (БД → фолбэк на CSV)."""
    try:
        total = None
        accepted = None
        declined = None
        last_time = None

        # 1) Пытаемся получить из БД
        try:
            db.cursor.execute("SELECT COUNT(*) FROM signals_log")
            row = db.cursor.fetchone()
            if row:
                total = int(row[0] or 0)

            db.cursor.execute(
                """
                SELECT result FROM signals_log WHERE result IS NOT NULL AND result != ''
                """
            )
            results = [r[0] for r in db.cursor.fetchall()]
            # wins = sum(1 for r in results if str(r).upper() in ("TP", "TP1", "WIN"))
            losses = sum(1 for r in results if str(r).upper() in ("SL", "LOSS"))

            # Принято трактуем как количество записанных сигналов (отправленных)
            accepted = total if total is not None else None
            declined = losses

            db.cursor.execute(
                """
                SELECT entry_time FROM signals_log
                WHERE entry_time IS NOT NULL AND entry_time != ''
                ORDER BY datetime(entry_time) DESC LIMIT 1
                """
            )
            lr = db.cursor.fetchone()
            if lr and lr[0]:
                last_time = str(lr[0])
        except Exception:
            pass

        # 2) Фолбэк на CSV
        if (total is None or last_time is None) and os.path.exists(signals_log_path):
            try:
                with open(signals_log_path, encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                if total is None:
                    total = len(rows)
                if accepted is None:
                    accepted = len(rows)
                if declined is None:
                    declined = sum(
                        1 for r in rows if (r.get("result") or "").upper() in ("SL", "LOSS")
                    )
                if last_time is None and rows:
                    # Берём время из последней по entry_time записи
                    def _parse_dt(s):
                        try:
                            return datetime.fromisoformat(s)
                        except Exception:
                            return None

                    rows_valid = [r for r in rows if r.get("entry_time")]
                    if rows_valid:
                        rows_valid.sort(
                            key=lambda r: _parse_dt(str(r.get("entry_time")) or "") or datetime.min
                        )
                        last_time = rows_valid[-1].get("entry_time")
            except Exception:
                pass

        def fmt(v):
            return str(v) if v is not None else "N/A"

        stats_text = (
            "📊 <b>Статистика сигналов</b>\n\n"
            f"🔸 Всего сигналов: {fmt(total)}\n"
            f"🔸 Принято: {fmt(accepted)}\n"
            f"🔸 Отклонено: {fmt(declined)}\n"
            f"🔸 Время последнего: {fmt(last_time)}\n"
        )

        await update.message.reply_text(stats_text, parse_mode="HTML")
    except Exception as e:
        logging.error("Ошибка в signal_stats_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при получении статистики")
