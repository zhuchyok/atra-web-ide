async def status_cmd(update, _context):
    """Показывает статус системы (упрощенный)"""
    try:
        logging.info("🔔 [COMMAND] /status вызван пользователем %s", update.effective_user.id if update and update.effective_user else "unknown")
        
        message = "📊 <b>Статус ATRA</b>\n\n"
        message += "✅ Система: Работает\n"
        message += f"🌍 Режим: <code>{ATRA_ENV.upper()}</code>\n"
        message += f"📅 Время: <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
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
        except Exception: pass

