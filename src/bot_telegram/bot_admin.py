"""Админ-команды Telegram-бота: добавление, удаление и список пользователей.

Содержит обработчики /add_user, /remove_user и /list_users с проверкой прав админа.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

# Импорты из наших модулей
from src.database.db import Database

# Инициализация базы данных
db = Database()

async def add_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет пользователя (админ команда)"""
    try:
        if len(context.args) < 1:
            await update.message.reply_text("Использование: /add_user <user_id>")
            return

        user_id = int(context.args[0])

        # Проверяем, является ли текущий пользователь админом
        try:
            admins = db.get_admin_ids()
        except (RuntimeError, ValueError, TypeError):
            admins = []
        if int(update.effective_user.id) not in admins:
            await update.message.reply_text("❌ Нет прав")
            return

        # Добавляем пользователя в базу
        user_data = {
            'deposit': 1000,
            'balance': 1000,
            'risk_pct': 2,
            'risk_amount': 20,
            'trade_mode': 'spot',
            'filter_mode': 'soft',
            'leverage': 1,
            'positions': [],
            'trade_history': [],
            'pending_dca': []
        }

        db.save_user_data(user_id, user_data)

        await update.message.reply_text(f"✅ Пользователь {user_id} добавлен")

    except (ValueError, IndexError):
        await update.message.reply_text("Ошибка: укажите корректный ID пользователя")

async def remove_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет пользователя (админ команда)"""
    try:
        if len(context.args) < 1:
            await update.message.reply_text("Использование: /remove_user <user_id>")
            return

        user_id = int(context.args[0])

        # Проверяем, является ли текущий пользователь админом
        try:
            admins = db.get_admin_ids()
        except (RuntimeError, ValueError, TypeError):
            admins = []
        if int(update.effective_user.id) not in admins:
            await update.message.reply_text("❌ Нет прав")
            return

        # Удаляем пользователя из базы
        db.delete_user_data(user_id)

        await update.message.reply_text(f"✅ Пользователь {user_id} удален")

    except (ValueError, IndexError):
        await update.message.reply_text("Ошибка: укажите корректный ID пользователя")

async def list_users_cmd(update: Update, _context):
    """Показывает список пользователей (админ команда)"""
    try:
        # Проверяем, является ли текущий пользователь админом
        try:
            admins = db.get_admin_ids()
        except (RuntimeError, ValueError, TypeError):
            admins = []
        if int(update.effective_user.id) not in admins:
            await update.message.reply_text("❌ Нет прав")
            return

        # Получаем список пользователей
        users = db.get_all_users()

        if not users:
            await update.message.reply_text("📭 Нет пользователей в базе")
            return

        users_text = f"👥 <b>Список пользователей ({len(users)}):</b>\n\n"

        for i, user_id in enumerate(users, 1):
            user_data = db.get_user_data(user_id) or {}

            deposit = float(user_data.get('deposit', 0) or 0)
            balance = float(user_data.get('balance', deposit) or deposit)
            free_deposit = float(user_data.get('free_deposit', balance) or balance)
            risk_pct = user_data.get('risk_pct', user_data.get('riskPercent', 0)) or 0
            leverage = user_data.get('leverage', 1)
            trade_mode = user_data.get('trade_mode', 'spot')
            filter_mode = user_data.get('filter_mode', 'soft')
            # Если флаг не сохранён, считаем завершённым при наличии ключевых полей
            setup_completed = user_data.get('setup_completed', False)
            if not setup_completed:
                try:
                    setup_completed = all(k in user_data for k in ('deposit', 'trade_mode', 'filter_mode'))
                except (TypeError, KeyError):
                    setup_completed = False
            # Позиции: считаем только открытые лоты с qty>0
            positions_all = user_data.get('positions', []) or user_data.get('open_positions', []) or []
            open_positions = []
            for p in (positions_all or []):
                try:
                    qty_val = float(p.get('qty', 0) or 0)
                except (TypeError, ValueError):
                    qty_val = 0.0
                if p.get('status', 'open') == 'open' and qty_val > 0:
                    open_positions.append(p)
            positions_count = len(open_positions)

            # DCA в ожидании: используем ключ pending_dca_signals, если есть
            pending_dca = user_data.get('pending_dca_signals', []) or user_data.get('pending_dca', []) or []
            pending_dca_count = len(pending_dca)

            # Принятые сигналы: берём из user_data
            accepted_signals = user_data.get('accepted_signals', []) or []
            accepted_signals_count = len(accepted_signals)
            # Значения по умолчанию для отображения
            if 'risk_pct' not in user_data:
                user_data['risk_pct'] = 2.0 if trade_mode == 'spot' else 2.0
            if 'leverage' not in user_data:
                user_data['leverage'] = 1 if trade_mode == 'spot' else 15
            # Не записываем в БД здесь, только отображение

            users_text += (
                f"{i}. <b>ID:</b> <code>{user_id}</code>\n"
                f"   💵 <b>Депозит:</b> ${deposit:.2f} | <b>Баланс:</b> ${balance:.2f} | <b>Свободно:</b> ${free_deposit:.2f}\n"
                f"   🔧 <b>Режим:</b> {trade_mode.upper()} / {('Строгий' if filter_mode=='strict' else 'Мягкий')}\n"
                f"   🎯 <b>Риск:</b> {float(risk_pct):.2f}% | ⚡ <b>Плечо:</b> {leverage}x\n"
                f"   📊 <b>Позиции:</b> {positions_count} | ⏳ <b>DCA в ожидании:</b> {pending_dca_count} | ✅ <b>Принято сигналов:</b> {accepted_signals_count}\n"
                f"   🧩 <b>Setup:</b> {'Завершён' if setup_completed else 'Не завершён'}\n\n"
            )

        await update.message.reply_text(users_text, parse_mode='HTML')

    except (RuntimeError, ValueError, TypeError, KeyError) as e:
        logging.error("Ошибка в list_users_cmd: %s", e)
        await update.message.reply_text("❌ Ошибка при получении списка пользователей")
