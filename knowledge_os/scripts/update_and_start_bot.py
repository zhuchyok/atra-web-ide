#!/usr/bin/env python3
"""
Скрипт для обновления кода и запуска бота на сервере
"""

import subprocess
import sys
import time

SERVER = "root@185.177.216.15"
PASSWORD = "u44Ww9NmtQj,XG"
REMOTE_DIR = "/root/atra"


def run_ssh_command(command, use_password=True):
    """Выполняет команду на сервере через SSH"""
    if use_password:
        # Используем sshpass для автоматического ввода пароля
        ssh_cmd = [
            "sshpass",
            "-p",
            PASSWORD,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            SERVER,
            command,
        ]
    else:
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", SERVER, command]

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=120,  # Увеличиваем таймаут для длительных операций
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except FileNotFoundError:
        # Если sshpass не установлен, пробуем без него (требует SSH ключи)
        print("⚠️ sshpass не найден, пробуем без пароля (требуются SSH ключи)...")
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", SERVER, command]
        try:
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)


def main():
    print("🚀 ОБНОВЛЕНИЕ И ЗАПУСК БОТА НА СЕРВЕРЕ")
    print("=" * 70)
    print(f"📡 Сервер: {SERVER}")
    print(f"📁 Директория: {REMOTE_DIR}")
    print()

    # 1. Обновление кода
    print("📥 Шаг 1: Обновление кода с git...")
    command = f"cd {REMOTE_DIR} && git fetch origin && git reset --hard origin/main"
    success, stdout, stderr = run_ssh_command(command)
    if success:
        print("✅ Код обновлен")
        if stdout.strip():
            print(f"   {stdout.strip()}")
    else:
        print(f"❌ Ошибка обновления: {stderr}")
        if stdout:
            print(f"   {stdout}")
        return False

    print()

    # 2. Остановка старого процесса
    print("🛑 Шаг 2: Остановка старого процесса (если запущен)...")
    command = f"cd {REMOTE_DIR} && pkill -f 'signal_live.py' || true"
    success, stdout, stderr = run_ssh_command(command)
    if success:
        print("✅ Старые процессы остановлены")
    time.sleep(2)

    print()

    # 3. Запуск бота
    print("🚀 Шаг 3: Запуск бота...")
    # Запускаем в фоне через отдельную команду
    command = f"cd {REMOTE_DIR} && python3 signal_live.py > signal_live.log 2>&1 &"
    success, stdout, stderr = run_ssh_command(command, use_password=True)
    if success or "Timeout" not in stderr:
        print("✅ Команда запуска отправлена")
    else:
        print("⚠️ Возможен таймаут (это нормально для фоновых процессов)")

    time.sleep(5)
    print()

    # 4. Проверка процессов
    print("🔍 Шаг 4: Проверка процессов...")
    command = f"cd {REMOTE_DIR} && ps aux | grep -E '(signal_live|main\\.py)' | grep -v grep"
    success, stdout, stderr = run_ssh_command(command)
    if success and stdout.strip():
        print("✅ Процессы найдены:")
        for line in stdout.strip().split("\n"):
            if line.strip():
                print(f"   {line[:100]}")
    else:
        print("⚠️ Процессы не найдены (возможно, еще запускаются)")

    print()

    # 5. Последние строки лога
    print("📋 Шаг 5: Последние строки лога...")
    command = f"cd {REMOTE_DIR} && tail -10 signal_live.log 2>/dev/null || echo 'Лог еще не создан'"
    success, stdout, stderr = run_ssh_command(command)
    if success and stdout.strip():
        print("📝 Лог:")
        for line in stdout.strip().split("\n"):
            if line.strip():
                print(f"   {line}")

    print()
    print("=" * 70)
    print("✅ ГОТОВО!")
    print()
    print("💡 Для проверки статуса выполните:")
    print(f"   ssh {SERVER}")
    print(f"   cd {REMOTE_DIR}")
    print("   python3 check_signals_status.py")
    print()
    print("💡 Для просмотра логов:")
    print(f"   ssh {SERVER} 'cd {REMOTE_DIR} && tail -f signal_live.log'")

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
