import asyncio
import os
import sys

# Добавляем путь к приложению для импорта
sys.path.append(os.path.join(os.getcwd(), 'knowledge_os', 'app'))

async def notify():
    from telegram_alerter import get_telegram_alerter

    # Загружаем переменные из .env вручную для надежности
    with open('.env', 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

    message = (
        "📢 ВНИМАНИЕ ВСЕМ ЭКСПЕРТАМ! 📢\n\n"
        "Ядро Singularity 14.0 обновлено до версии 21.5 (Total Dominance).\n\n"
        "✅ Victoria Wisdom v3.5 (Qwen 3.5 MoE 35B) полностью активирована.\n"
        "✅ Архитектура унифицирована: v3.5 в MLX (Мозг) и v3.5 в Ollama (Руки).\n"
        "✅ Модель v3.5 получила статус IMMORTAL (бессмертная) в памяти Mac Studio.\n\n"
        "Ликвидирован разрыв в знаниях между планированием и исполнением. Мы вышли на новый уровень интеллектуальной мощности.\n\n"
        "Виктория готова к приему задач. 🦾🧠"
    )

    alerter = get_telegram_alerter()
    await alerter.send_alert(message, priority='high', source='System Update')
    print("✅ Уведомление отправлено!")

if __name__ == "__main__":
    asyncio.run(notify())
