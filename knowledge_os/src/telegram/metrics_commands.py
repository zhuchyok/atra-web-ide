#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram команды для просмотра метрик производительности
"""

import logging
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from telegram import Update
from telegram.ext import ContextTypes
from performance_metrics_calculator import get_metrics_calculator
from trade_tracker import get_trade_tracker

logger = logging.getLogger(__name__)


async def metrics_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /metrics - показывает общие метрики производительности"""
    try:
        user_id = update.effective_user.id
        
        # Получаем метрики за последние 30 дней
        end_date = get_utc_now()
        start_date = end_date - timedelta(days=30)
        
        calculator = get_metrics_calculator()
        metrics = calculator.calculate_metrics(
            user_id=str(user_id),
            start_date=start_date,
            end_date=end_date
        )
        
        if metrics['total_trades'] == 0:
            await update.message.reply_text(
                "📊 **Метрики производительности**\n\n"
                "❌ Нет закрытых сделок за последние 30 дней.\n\n"
                "После закрытия позиций метрики появятся здесь.",
                parse_mode='Markdown'
            )
            return
        
        # Формируем сообщение
        message = "📊 **МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ**\n\n"
        message += f"📅 Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
        
        # Базовые метрики
        message += "**📈 БАЗОВЫЕ ПОКАЗАТЕЛИ:**\n"
        message += f"• Всего сделок: `{metrics['total_trades']}`\n"
        message += f"• Прибыльных: `{metrics['winning_trades']}` | Убыточных: `{metrics['losing_trades']}`\n"
        message += f"• Win Rate: `{metrics['win_rate']:.2f}%`\n"
        message += f"• Profit Factor: `{metrics['profit_factor']:.2f}`\n\n"
        
        # PnL метрики
        message += "**💰 P&L:**\n"
        message += f"• Общий PnL: `{metrics['total_net_pnl_usd']:+.2f} USDT`\n"
        message += f"• Средний PnL: `{metrics['avg_pnl_usd']:+.2f} USDT`\n"
        message += f"• Средний PnL %: `{metrics['avg_pnl_percent']:+.2f}%`\n"
        message += f"• Лучшая сделка: `{metrics['largest_win']:+.2f} USDT`\n"
        message += f"• Худшая сделка: `{metrics['largest_loss']:+.2f} USDT`\n\n"
        
        # Продвинутые метрики
        message += "**📊 ПРОДВИНУТЫЕ МЕТРИКИ:**\n"
        message += f"• Sharpe Ratio: `{metrics['sharpe_ratio']:.2f}`\n"
        message += f"• Sortino Ratio: `{metrics['sortino_ratio']:.2f}`\n"
        message += f"• Max Drawdown: `{metrics['max_drawdown_pct']:.2f}%`\n"
        message += f"• Годовая доходность: `{metrics['annual_return_pct']:.2f}%`\n"
        message += f"• Волатильность: `{metrics['volatility_pct']:.2f}%`\n\n"
        
        # Дополнительно
        message += "**📉 ДОПОЛНИТЕЛЬНО:**\n"
        message += f"• Среднее время удержания: `{metrics['avg_duration_minutes']:.0f} мин`\n"
        message += f"• Макс. серия побед: `{metrics['consecutive_wins']}`\n"
        message += f"• Макс. серия поражений: `{metrics['consecutive_losses']}`\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error("❌ Ошибка команды /metrics: %s", e, exc_info=True)
        await update.message.reply_text("❌ Ошибка получения метрик. Попробуйте позже.")


async def performance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /performance [symbol] - показывает детальную статистику по символу"""
    try:
        user_id = update.effective_user.id
        args = context.args
        
        if not args:
            await update.message.reply_text(
                "📊 **Статистика по символу**\n\n"
                "Использование: `/performance SYMBOL`\n\n"
                "Пример: `/performance BTCUSDT`",
                parse_mode='Markdown'
            )
            return
        
        symbol = args[0].upper()
        if not symbol.endswith('USDT'):
            symbol = f"{symbol}USDT"
        
        calculator = get_metrics_calculator()
        
        # Получаем метрики за последние 90 дней для символа
        end_date = get_utc_now()
        start_date = end_date - timedelta(days=90)
        
        # Получаем все сделки и фильтруем по символу
        tracker = get_trade_tracker()
        trades = tracker.get_trades(
            user_id=str(user_id),
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=1000
        )
        
        if not trades:
            await update.message.reply_text(
                f"📊 **Статистика по {symbol}**\n\n"
                f"❌ Нет закрытых сделок по этому символу за последние 90 дней.",
                parse_mode='Markdown'
            )
            return
        
        # Рассчитываем метрики для символа
        import pandas as pd
        df = pd.DataFrame(trades)
        
        total_trades = len(df)
        winning = len(df[df['pnl_usd'] > 0])
        losing = len(df[df['pnl_usd'] < 0])
        win_rate = (winning / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = df['net_pnl_usd'].sum()
        avg_pnl = df['pnl_usd'].mean()
        avg_pnl_pct = df['pnl_percent'].mean()
        
        profits = df[df['pnl_usd'] > 0]['pnl_usd']
        losses = df[df['pnl_usd'] < 0]['pnl_usd']
        total_profit = profits.sum() if len(profits) > 0 else 0
        total_loss = abs(losses.sum()) if len(losses) > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Формируем сообщение
        message = f"📊 **СТАТИСТИКА ПО {symbol}**\n\n"
        message += f"📅 Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
        
        message += "**📈 БАЗОВЫЕ ПОКАЗАТЕЛИ:**\n"
        message += f"• Всего сделок: `{total_trades}`\n"
        message += f"• Прибыльных: `{winning}` | Убыточных: `{losing}`\n"
        message += f"• Win Rate: `{win_rate:.2f}%`\n"
        message += f"• Profit Factor: `{profit_factor:.2f}`\n\n"
        
        message += "**💰 P&L:**\n"
        message += f"• Общий PnL: `{total_pnl:+.2f} USDT`\n"
        message += f"• Средний PnL: `{avg_pnl:+.2f} USDT`\n"
        message += f"• Средний PnL %: `{avg_pnl_pct:+.2f}%`\n"
        
        if len(profits) > 0:
            message += f"• Лучшая сделка: `{profits.max():+.2f} USDT`\n"
        if len(losses) > 0:
            message += f"• Худшая сделка: `{losses.min():+.2f} USDT`\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error("❌ Ошибка команды /performance: %s", e, exc_info=True)
        await update.message.reply_text("❌ Ошибка получения статистики. Попробуйте позже.")


async def trades_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /trades [limit] - показывает историю последних сделок"""
    try:
        user_id = update.effective_user.id
        args = context.args
        
        limit = 10
        if args:
            try:
                limit = int(args[0])
                limit = max(1, min(50, limit))  # Ограничиваем 1-50
            except (ValueError, TypeError):
                pass
        
        tracker = get_trade_tracker()
        trades = tracker.get_trades(
            user_id=str(user_id),
            limit=limit
        )
        
        if not trades:
            await update.message.reply_text(
                "📋 **История сделок**\n\n"
                "❌ Нет закрытых сделок.\n\n"
                "После закрытия позиций сделки появятся здесь.",
                parse_mode='Markdown'
            )
            return
        
        message = f"📋 **ПОСЛЕДНИЕ {len(trades)} СДЕЛОК**\n\n"
        
        for i, trade in enumerate(trades, 1):
            symbol = trade['symbol']
            direction = trade['direction']
            entry_price = trade['entry_price']
            exit_price = trade['exit_price']
            pnl_usd = trade['net_pnl_usd']
            pnl_pct = trade['pnl_percent']
            exit_reason = trade['exit_reason']
            exit_time = trade['exit_time']
            
            if isinstance(exit_time, str):
                try:
                    exit_time = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    exit_time = get_utc_now()
            
            # Иконка направления
            direction_icon = "📈" if direction.upper() == "LONG" else "📉"
            
            # Иконка результата
            result_icon = "✅" if pnl_usd > 0 else "❌"
            
            # Причина выхода
            reason_map = {
                'TP1': 'TP1',
                'TP2': 'TP2',
                'SL': 'SL',
                'MANUAL': 'Ручное',
                'TIMEOUT': 'Таймаут',
                'TRAILING_STOP': 'Трейлинг'
            }
            reason_text = reason_map.get(exit_reason, exit_reason)
            
            message += f"{i}. {direction_icon} **{symbol}** {direction}\n"
            message += f"   Вход: `{entry_price:.4f}` → Выход: `{exit_price:.4f}`\n"
            message += f"   {result_icon} PnL: `{pnl_usd:+.2f} USDT` ({pnl_pct:+.2f}%)\n"
            message += f"   📅 {exit_time.strftime('%d.%m %H:%M')} | Причина: {reason_text}\n\n"
        
        if len(trades) >= limit:
            message += f"_Показано {limit} последних сделок. Используйте `/trades {limit+10}` для большего количества._"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error("❌ Ошибка команды /trades: %s", e, exc_info=True)
        await update.message.reply_text("❌ Ошибка получения истории сделок. Попробуйте позже.")
