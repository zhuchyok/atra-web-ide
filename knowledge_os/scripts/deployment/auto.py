#!/usr/bin/env python3
"""
Автоматическое развертывание на PROD сервере
"""

import sys
import time

import pexpect

SERVER = "185.177.216.15"
USER = "root"
PASSWORD = "u44Ww9NmtQj,XG"
TIMEOUT = 60


def deploy():
    print("🚀 Начало автоматического развертывания на PROD сервере...")
    print("=" * 60)

    try:
        # Подключение к серверу
        print(f"📡 Подключение к {USER}@{SERVER}...")
        child = pexpect.spawn(
            f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 {USER}@{SERVER}",
            encoding="utf-8",
            timeout=TIMEOUT,
        )
        child.logfile = sys.stdout

        # Ожидание запроса пароля или подтверждения
        index = child.expect(["password:", "yes/no", pexpect.EOF, pexpect.TIMEOUT], timeout=10)

        if index == 1:  # yes/no
            child.sendline("yes")
            child.expect("password:", timeout=10)
            child.sendline(PASSWORD)
        elif index == 0:  # password
            child.sendline(PASSWORD)

        # Ожидание промпта
        child.expect("# ", timeout=10)
        print("✅ Подключение установлено")

        # Выполнение команд
        commands = [
            ("cd /root/atra", "📁 Переход в директорию проекта"),
            ("git fetch origin", "📥 Получение изменений из git"),
            ("git checkout insight", "🔄 Переключение на ветку insight"),
            ("git pull origin insight", "⬇️ Обновление кода"),
            ("pkill -f 'python.*signal_live' || true", "🛑 Остановка signal_live процессов"),
            ("pkill -f 'python.*main.py' || true", "🛑 Остановка main.py процессов"),
            ("sleep 2", "⏳ Ожидание..."),
            (
                "ps aux | grep -E '(python.*signal_live|python.*main\\.py)' | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true",
                "🛑 Принудительная остановка оставшихся процессов",
            ),
            (
                "python3 -c 'from config import ATRA_ENV; print(f\"ATRA_ENV: {ATRA_ENV}\")'",
                "🔍 Проверка окружения",
            ),
            ("nohup python3 main.py > main.log 2>&1 &", "🚀 Запуск процесса"),
            ("sleep 3", "⏳ Ожидание запуска..."),
            ("ps aux | grep 'python.*main.py' | grep -v grep", "📊 Проверка статуса процесса"),
            ("tail -20 main.log", "📋 Последние строки лога"),
        ]

        for cmd, desc in commands:
            print(f"\n{desc}...")
            child.sendline(cmd)
            child.expect("# ", timeout=30)
            time.sleep(0.5)

        # Завершение
        print("\n" + "=" * 60)
        print("✅ Развертывание завершено!")
        child.sendline("exit")
        child.expect(pexpect.EOF, timeout=5)
        child.close()

        return True

    except pexpect.TIMEOUT:
        print("❌ Ошибка: Timeout при выполнении команды")
        return False
    except pexpect.EOF:
        print("❌ Ошибка: Соединение закрыто")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


if __name__ == "__main__":
    success = deploy()
    sys.exit(0 if success else 1)
