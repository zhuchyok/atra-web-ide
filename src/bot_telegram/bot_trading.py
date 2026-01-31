import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from src.shared.utils.datetime_utils import get_utc_now

# Импорты из наших модулей
from src.database.db import Database
try:
    from src.execution.exchange_api import get_current_price_robust
except ImportError:
    from improved_price_api import get_current_price_robust

# Инициализация базы данных
db = Database()

async def clear_positions_cmd(update, context):
    """Очищает все позиции пользователя"""
    try:
        user_data = context.user_data

        if 'positions' in user_data:
            user_data['positions'] = []

        await update.message.reply_text("✅ Все позиции очищены")

    except (RuntimeError, ValueError, KeyError, TypeError, TelegramError) as e:
        logging.error("Ошибка в clear_positions_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при очистке позиций")

async def close_cmd(update, context):
    """Закрывает позицию по символу или показывает список позиций с кнопками"""
    try:
        user_data = context.user_data

        # Если аргументы не указаны, показываем список позиций с кнопками
        if len(context.args) < 1:
            # Получаем открытые позиции
            positions = user_data.get('positions', [])
            open_positions = [p for p in positions if p.get('status') == 'open' and float(p.get('qty', 0)) > 0]

            if not open_positions:
                await update.message.reply_text("📭 Нет открытых позиций")
                return

            # Группируем по символу
            grouped = {}
            for p in open_positions:
                sym = p.get('symbol')
                if not sym:
                    continue
                grouped.setdefault(sym, []).append(p)

            # Отправляем заголовок
            header = f"🔴 <b>ЗАКРЫТИЕ ПОЗИЦИЙ</b>\n\nКоличество: {len(grouped)}\nРежим торговли: {user_data.get('trade_mode', 'SPOT').upper()}\n\n💡 Выберите позицию для закрытия:"
            await update.message.reply_text(header, parse_mode='HTML')

            # Отправляем каждую позицию с кнопками
            for idx, (sym, lots) in enumerate(grouped.items(), start=1):
                # Агрегируем данные по позиции
                total_qty = sum(float(lot.get('qty', 0)) for lot in lots)
                side = (lots[0].get('side') or 'long').lower()
                side_emoji = "🟢" if side == "long" else "🔴"

                # Средняя цена входа
                cost = 0.0
                for lot in lots:
                    ep = float(lot.get('entry_price', 0))
                    q = float(lot.get('qty', 0))
                    cost += ep * q
                avg_entry = (cost / total_qty) if total_qty > 0 else 0.0

                # Текущая цена
                current_price = 0.0
                try:
                    from exchange_api import get_ohlc_binance_sync
                    ohlc = get_ohlc_binance_sync(sym, interval="1m", limit=1)
                    if ohlc and len(ohlc) > 0:
                        current_price = float(ohlc[-1]['close'])
                except Exception:
                    current_price = avg_entry

                # PnL
                pnl = (current_price - avg_entry) * total_qty if side == 'long' else (avg_entry - current_price) * total_qty
                pnl_pct = ((current_price - avg_entry) / avg_entry * 100) if side == 'long' else ((avg_entry - current_price) / avg_entry * 100)

                # Формируем сообщение
                pos_text = (
                    f"{idx}. {side_emoji} <b>{sym}</b> {side.upper()}\n"
                    f"Цена входа: {avg_entry:.4f}\n"
                    f"Текущая цена: {current_price:.4f}\n"
                    f"Объём: {total_qty:.4f}\n"
                    f"P&L: {pnl:.2f} USDT ({pnl_pct:+.2f}%)\n"
                    f"Режим: {user_data.get('trade_mode', 'SPOT').upper()}\n"
                    f"Плечо: x{float(lots[0].get('leverage', 1)):.0f}"
                )

                # Создаем кнопки
                cb50 = f"close|{sym}|50"
                cb100 = f"close|{sym}|100"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔴 Закрыть всю", callback_data=cb100),
                     InlineKeyboardButton("💰 Закрыть 50%", callback_data=cb50)]
                ])

                await update.message.reply_text(pos_text, parse_mode='HTML', reply_markup=keyboard)

            return

        # Если указан символ, закрываем конкретную позицию
        symbol = context.args[0].upper()

        # Обработка закрытия всех позиций
        if symbol.lower() == "all":
            await close_all_positions_cmd(update, context)
            return

        positions = user_data.get('positions', [])
        position_to_close = None

        for pos in positions:
            if pos.get('symbol') == symbol and pos.get('status') == 'open':
                position_to_close = pos
                break

        if not position_to_close:
            await update.message.reply_text(f"❌ Открытая позиция {symbol} не найдена")
            return

        # Закрываем позицию
        position_to_close['status'] = 'closed'
        position_to_close['close_time'] = get_utc_now().isoformat()

        # Получаем актуальную цену для корректного PnL
        entry_price = position_to_close['entry_price']
        try:
            current_price = await get_current_price_robust(symbol) or entry_price
        except Exception as e:
            logging.warning("current price fetch failed for %s: %s", symbol, e)
            current_price = entry_price
        qty = position_to_close['qty']
        side = position_to_close['side']

        if side == 'long':
            pnl = (current_price - entry_price) * qty
        else:
            pnl = (entry_price - current_price) * qty

        position_to_close['pnl'] = pnl
        position_to_close['pnl_pct'] = (pnl / (entry_price * qty)) * 100

        # Обновляем баланс
        user_data['balance'] += pnl

        # Перемещаем в историю
        if 'trade_history' not in user_data:
            user_data['trade_history'] = []
        user_data['trade_history'].append(position_to_close)

        # Удаляем из открытых позиций
        user_data['positions'] = [pos for pos in positions if pos.get('status') != 'closed']

        # Сохраняем данные
        db.save_user_data(update.effective_user.id, user_data)

        # Обновляем запись в БД signals_log: CLOSED_MANUAL и PnL
        try:
            user_id = int(update.effective_user.id)
            with db._lock:
                cur = db.conn.execute(
                    """
                    SELECT id, entry_time FROM signals_log
                    WHERE symbol=? AND (user_id=? OR user_id IS NULL)
                      AND UPPER(IFNULL(result,'OPEN')) LIKE 'OPEN%'
                    ORDER BY datetime(created_at) DESC
                    LIMIT 1
                    """,
                    (symbol, user_id),
                )
                row = cur.fetchone()
                if row:
                    sig_id, entry_time = row
                    db.conn.execute(
                        """
                        UPDATE signals_log
                        SET exit_time=datetime('now'), result='CLOSED_MANUAL',
                            net_profit=?, user_id=COALESCE(user_id, ?)
                        WHERE id=?
                        """,
                        (float(pnl), user_id, int(sig_id)),
                    )
                    db.conn.commit()
        except Exception as e:
            logging.warning("signals_log manual close update failed for %s: %s", symbol, e)

        # Формируем сообщение
        close_text = f"""
🔒 *Позиция закрыта*

🔸 Символ: {symbol}
🔸 Сторона: {side.upper()}
🔸 PnL: ${pnl:.2f} ({position_to_close['pnl_pct']:+.2f}%)
🔸 Новый баланс: ${user_data['balance']:.2f}

⏰ Время закрытия: {get_utc_now().strftime('%H:%M:%S')}
"""

        await update.message.reply_text(close_text, parse_mode='HTML')

    except (RuntimeError, ValueError, KeyError, TypeError, TelegramError) as e:
        logging.error("Ошибка в close_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при закрытии позиции")

async def accept_signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принимает сигнал вручную"""
    try:
        if len(context.args) < 4:
            await update.message.reply_text("Использование: /accept <символ> <цена> <tp> <сторона>")
            return

        symbol = context.args[0].upper()
        entry_price = float(context.args[1])
        tp_price = float(context.args[2])
        side = context.args[3].lower()

        if side not in ['long', 'short']:
            await update.message.reply_text("Сторона должна быть 'long' или 'short'")
            return

        user_data = context.user_data

        # Проверяем данные пользователя
        if not user_data.get('deposit'):
            await update.message.reply_text("❌ Установите баланс командой /set_balance")
            return

        # Рассчитываем параметры сделки
        deposit = user_data['deposit']
        risk_pct = user_data.get('risk_pct', 2)
        risk_amount = deposit * (risk_pct / 100)
        leverage = user_data.get('leverage', 1)

        # Рассчитываем количество
        qty = risk_amount / entry_price

        # Создаем позицию
        position = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'tp_price': tp_price,
            'qty': qty,
            'leverage': leverage,
            'entry_time': get_utc_now().isoformat(),
            'pnl': 0,
            'pnl_pct': 0,
            'status': 'open'
        }

        # Добавляем позицию в список
        if 'positions' not in user_data:
            user_data['positions'] = []
        user_data['positions'].append(position)

        # Обновляем баланс
        user_data['balance'] = deposit - risk_amount

        # Сохраняем данные
        db.save_user_data(update.effective_user.id, user_data)

        # Формируем сообщение подтверждения
        confirm_text = f"""
✅ *Сигнал принят вручную!*

🔸 Символ: {symbol}
🔸 Сторона: {side.upper()}
🔸 Цена входа: ${entry_price:.5f}
🔸 Take Profit: ${tp_price:.5f}
🔸 Количество: {qty:.6f}
🔸 Плечо: {leverage}x
🔸 Риск: ${risk_amount:.2f}

⏰ Время принятия: {get_utc_now().strftime('%H:%M:%S')}
"""

        await update.message.reply_text(confirm_text, parse_mode='HTML')

    except (ValueError, IndexError):
        await update.message.reply_text("Ошибка: проверьте формат команды")

async def close_all_positions_cmd(update, context):
    """Закрывает все позиции"""
    try:
        user_data = context.user_data

        positions = user_data.get('positions', [])
        open_positions = [pos for pos in positions if pos.get('status') == 'open']

        if not open_positions:
            await update.message.reply_text("📭 Нет открытых позиций для закрытия")
            return

        # Создаем кнопку подтверждения
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_close_all")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        confirm_text = f"""
🔒 *Закрытие всех позиций*

📊 Открытых позиций: {len(open_positions)}
💰 Подтвердите закрытие всех позиций
"""

        await update.message.reply_text(confirm_text, parse_mode='HTML', reply_markup=reply_markup)

    except (RuntimeError, ValueError, KeyError, TypeError, TelegramError) as e:
        logging.error("Ошибка в close_all_positions_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при закрытии позиций")

async def trade_history_cmd(update, context):
    """Показывает историю сделок с пагинацией (🚀 УНИВЕРСАЛЬНАЯ ВЕРСИЯ)"""
    try:
        user_data = context.user_data
        trade_history = user_data.get('trade_history', [])

        query = update.callback_query
        
        if not trade_history:
            msg_text = "📭 История сделок пуста"
            if query:
                await query.answer()
                await query.edit_message_text(msg_text)
            else:
                await update.message.reply_text(msg_text)
            return

        # ⚡ ПАГИНАЦИЯ: Определяем страницу из аргументов или callback_data
        page = 0
        if query and query.data.startswith('history_page_'):
            page = int(query.data.split('_')[-1])
        elif context.args and context.args[0].isdigit():
            page = int(context.args[0])

        trades_per_page = 10
        total_pages = (len(trade_history) + trades_per_page - 1) // trades_per_page
        
        # Сортируем: новые сверху
        sorted_history = list(reversed(trade_history))
        start_idx = page * trades_per_page
        end_idx = start_idx + trades_per_page
        recent_trades = sorted_history[start_idx:end_idx]

        history_text = f"📋 <b>ИСТОРИЯ СДЕЛОК (стр. {page + 1}/{total_pages})</b>\n\n"

        total_pnl = sum(t.get('pnl', 0) for t in trade_history)
        
        for i, trade in enumerate(recent_trades, start_idx + 1):
            symbol = trade.get('symbol', 'N/A')
            side = (trade.get('side') or 'N/A').upper()
            entry_price = trade.get('entry_price', 0)
            pnl = trade.get('pnl', 0)
            pnl_pct = trade.get('pnl_pct', 0)
            entry_time = trade.get('entry_time', 'N/A')

            side_emoji = "🟢" if side == "LONG" else "🔴"
            
            try:
                from src.bot_telegram.utils import safe_format_price
                entry_str = safe_format_price(entry_price, symbol)
            except Exception:
                entry_str = f"{entry_price:.5f}"

            history_text += f"{i}. {side_emoji} <b>{symbol}</b> {side}\n"
            history_text += f"├ Вход: <code>{entry_str}</code> | PnL: <b>{pnl_pct:+.2f}%</b>\n"
            history_text += f"└ Дата: <code>{entry_time[:16].replace('T', ' ')}</code>\n\n"

        history_text += f"💰 <b>Всего PnL:</b> <code>{total_pnl:+.2f} USDT</code>"

        # Кнопки навигации
        keyboard = []
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"history_page_{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"history_page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        if query:
            await query.answer()
            from src.bot_telegram.utils import safe_edit_message_text
            await safe_edit_message_text(query, history_text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(history_text, parse_mode='HTML', reply_markup=reply_markup)

    except Exception as e:
        logging.error("Ошибка в trade_history_cmd: %s", e)
        if query:
            await query.answer("❌ Ошибка при загрузке истории")
        else:
            await update.message.reply_text("❌ Ошибка при получении истории сделок")

async def close_all_positions_safe_cmd(update, context):
    """Безопасное закрытие всех позиций"""
    try:
        user_data = context.user_data

        positions = user_data.get('positions', [])
        open_positions = [pos for pos in positions if pos.get('status') == 'open']

        if not open_positions:
            await update.message.reply_text("📭 Нет открытых позиций для закрытия")
            return

        # Закрываем все позиции
        total_pnl = 0
        closed_count = 0

        for pos in open_positions:
            pos['status'] = 'closed'
            pos['close_time'] = get_utc_now().isoformat()

            # Упрощенный расчет PnL
            entry_price = pos['entry_price']
            try:
                current_price = await get_current_price_robust(pos.get('symbol')) or entry_price
            except Exception as e:
                logging.warning("current price fetch failed for %s: %s", pos.get('symbol'), e)
                current_price = entry_price
            qty = pos['qty']
            side = pos['side']

            if side == 'long':
                pnl = (current_price - entry_price) * qty
            else:
                pnl = (entry_price - current_price) * qty

            pos['pnl'] = pnl
            pos['pnl_pct'] = (pnl / (entry_price * qty)) * 100
            total_pnl += pnl
            closed_count += 1

        # Обновляем баланс
        user_data['balance'] += total_pnl

        # Перемещаем в историю
        if 'trade_history' not in user_data:
            user_data['trade_history'] = []
        user_data['trade_history'].extend(open_positions)

        # Очищаем открытые позиции
        user_data['positions'] = []

        # Сохраняем данные
        db.save_user_data(update.effective_user.id, user_data)

        # Обновляем signals_log для каждой закрытой позиции
        try:
            user_id = int(update.effective_user.id)
            with db._lock:
                for pos in open_positions:
                    symbol = str(pos.get('symbol'))
                    pnl = float(pos.get('pnl', 0.0) or 0.0)
                    cur = db.conn.execute(
                        """
                        SELECT id FROM signals_log
                        WHERE symbol=? AND (user_id=? OR user_id IS NULL)
                          AND UPPER(IFNULL(result,'OPEN')) LIKE 'OPEN%'
                        ORDER BY datetime(created_at) DESC
                        LIMIT 1
                        """,
                        (symbol, user_id),
                    )
                    row = cur.fetchone()
                    if row:
                        sig_id = row[0]
                        db.conn.execute(
                            """
                            UPDATE signals_log
                            SET exit_time=datetime('now'), result='CLOSED_MANUAL',
                                net_profit=?, user_id=COALESCE(user_id, ?)
                            WHERE id=?
                            """,
                            (pnl, user_id, int(sig_id)),
                        )
                db.conn.commit()
        except Exception as e:
            logging.warning("signals_log manual close_all (safe) update failed: %s", e)

        # Формируем сообщение
        close_all_text = f"""
🔒 *Все позиции закрыты (безопасно)*

📊 Закрыто позиций: {closed_count}
💰 Общий PnL: ${total_pnl:.2f}
💳 Новый баланс: ${user_data['balance']:.2f}

⏰ Время: {get_utc_now().strftime('%H:%M:%S')}
"""

        await update.message.reply_text(close_all_text, parse_mode='HTML')

    except (RuntimeError, ValueError, KeyError, TypeError, TelegramError) as e:
        logging.error("Ошибка в close_all_positions_safe_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при закрытии позиций")

async def confirm_close_all_cmd(update, context):
    """Подтверждает закрытие всех позиций"""
    try:
        user_data = context.user_data

        positions = user_data.get('positions', [])
        open_positions = [pos for pos in positions if pos.get('status') == 'open']

        if not open_positions:
            await update.message.reply_text("📭 Нет открытых позиций для закрытия")
            return

        # Закрываем все позиции
        total_pnl = 0
        closed_count = 0

        for pos in open_positions:
            pos['status'] = 'closed'
            pos['close_time'] = get_utc_now().isoformat()

            # Упрощенный расчет PnL
            entry_price = pos['entry_price']
            try:
                current_price = await get_current_price_robust(pos.get('symbol')) or entry_price
            except Exception as e:
                logging.warning("current price fetch failed for %s: %s", pos.get('symbol'), e)
                current_price = entry_price
            qty = pos['qty']
            side = pos['side']

            if side == 'long':
                pnl = (current_price - entry_price) * qty
            else:
                pnl = (entry_price - current_price) * qty

            pos['pnl'] = pnl
            pos['pnl_pct'] = (pnl / (entry_price * qty)) * 100
            total_pnl += pnl
            closed_count += 1

        # Обновляем баланс
        user_data['balance'] += total_pnl

        # Перемещаем в историю
        if 'trade_history' not in user_data:
            user_data['trade_history'] = []
        user_data['trade_history'].extend(open_positions)

        # Очищаем открытые позиции
        user_data['positions'] = []

        # Сохраняем данные
        db.save_user_data(update.effective_user.id, user_data)

        # Обновляем signals_log для каждой закрытой позиции
        try:
            user_id = int(update.effective_user.id)
            with db._lock:
                for pos in open_positions:
                    symbol = str(pos.get('symbol'))
                    pnl = float(pos.get('pnl', 0.0) or 0.0)
                    cur = db.conn.execute(
                        """
                        SELECT id FROM signals_log
                        WHERE symbol=? AND (user_id=? OR user_id IS NULL)
                          AND UPPER(IFNULL(result,'OPEN')) LIKE 'OPEN%'
                        ORDER BY datetime(created_at) DESC
                        LIMIT 1
                        """,
                        (symbol, user_id),
                    )
                    row = cur.fetchone()
                    if row:
                        sig_id = row[0]
                        db.conn.execute(
                            """
                            UPDATE signals_log
                            SET exit_time=datetime('now'), result='CLOSED_MANUAL',
                                net_profit=?, user_id=COALESCE(user_id, ?)
                            WHERE id=?
                            """,
                            (pnl, user_id, int(sig_id)),
                        )
                db.conn.commit()
        except Exception as e:
            logging.warning("signals_log manual close_all (confirm) update failed: %s", e)

        # Формируем сообщение
        close_all_text = f"""
🔒 *Все позиции закрыты (подтверждено)*

📊 Закрыто позиций: {closed_count}
💰 Общий PnL: ${total_pnl:.2f}
💳 Новый баланс: ${user_data['balance']:.2f}

⏰ Время: {get_utc_now().strftime('%H:%M:%S')}
"""

        await update.message.reply_text(close_all_text, parse_mode='HTML')

    except (RuntimeError, ValueError, KeyError, TypeError, TelegramError) as e:
        logging.error("Ошибка в confirm_close_all_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при закрытии позиций")
