import asyncio
import os
import sys
from typing import Optional

# Add knowledge_os/app to sys.path
sys.path.append(os.path.join(os.getcwd(), 'knowledge_os', 'app'))

async def test_tg():
    from telegram_alerter import get_telegram_alerter

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_USER_ID')

    print(f"Testing TG with Token: {token[:10]}... Chat ID: {chat_id}")

    alerter = get_telegram_alerter(token=token, chat_id=chat_id)
    success = await alerter.send_alert(
        "🔔 Тестовое уведомление от Виктории (Wisdom Era).\nЕсли вы это видите, значит система уведомлений работает исправно!",
        priority="high",
        source="System Audit"
    )

    if success:
        print("✅ Test alert sent successfully!")
    else:
        print("❌ Failed to send test alert.")

if __name__ == "__main__":
    asyncio.run(test_tg())
