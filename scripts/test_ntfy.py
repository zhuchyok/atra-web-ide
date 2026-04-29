import asyncio
import os
import sys

# Добавляем путь к ядру системы
sys.path.append('/app/knowledge_os/app')
from services.notification_service import get_notification_service

async def test_ntfy():
    notifier = get_notification_service()
    print(f"Testing ntfy.sh at {notifier.ntfy_url}...")
    await notifier.notify(
        "🧪 Test Notification",
        "Hello from Victoria! This is a test of the unified notification system (Singularity v29.3).",
        priority="high",
        tags=["test_tube", "robot"]
    )
    print("Notification sent. Check your ntfy.sh app/web.")

if __name__ == "__main__":
    asyncio.run(test_ntfy())
