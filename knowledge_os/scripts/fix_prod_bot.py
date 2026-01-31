#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для диагностики и перезапуска бота на прод-сервере
"""

import subprocess
import sys
import time
from pathlib import Path

# Параметры сервера
SERVER = "root@185.177.216.15"
SERVER_PATH = "/root/atra"
PASSWORD = "u44Ww9NmtQj,XG"

def run_ssh_command(command, use_password=True):
    """Выполняет команду на удалённом сервере через SSH"""
    try:
        if use_password:
            # Используем sshpass для автоматического ввода пароля
            cmd = f'sshpass -p "{PASSWORD}" ssh -o StrictHostKeyChecking=no {SERVER} "{command}"'
        else:
            cmd = f'ssh -o StrictHostKeyChecking=no {SERVER} "{command}"'
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", 1
    except Exception as e:
        return "", str(e), 1

def check_bot_status():
    """Проверяет статус бота на сервере"""
    print("🔍 ПРОВЕРКА СОСТОЯНИЯ БОТА НА ПРОД-СЕРВЕРЕ")
    print("=" * 60)
    print()
    
    # 1. Проверка процессов
    print("1️⃣ Проверка процессов main.py:")
    print("-" * 40)
    stdout, stderr, code = run_ssh_command(f"cd {SERVER_PATH} && ps aux | grep main.py | grep -v grep")
    if stdout.strip():
        print(stdout)
        process_count = len([l for l in stdout.strip().split('\n') if l.strip()])
        print(f"\nКоличество процессов: {process_count}")
    else:
        print("❌ Процессы не найдены - бот не запущен!")
        process_count = 0
    print()
    
    # 2. Проверка последних ошибок
    print("2️⃣ Последние ошибки в логах:")
    print("-" * 40)
    stdout, _, _ = run_ssh_command(
        f"cd {SERVER_PATH} && tail -50 system_improved.log | grep -E 'ERROR|Exception|Failed|Traceback' | tail -10"
    )
    if stdout.strip():
        print(stdout)
    else:
        print("✅ Ошибок не найдено")
    print()
    
    # 3. Проверка Telegram polling
    print("3️⃣ Статус Telegram polling:")
    print("-" * 40)
    stdout, _, _ = run_ssh_command(
        f"cd {SERVER_PATH} && tail -30 system_improved.log | grep -E 'Polling|Bot authorized|ERROR.*TG|telegram' | tail -5"
    )
    if stdout.strip():
        print(stdout)
    else:
        print("⚠️ Информации о Telegram не найдено")
    print()
    
    # 4. Проверка блокировок
    print("4️⃣ Проверка блокировок:")
    print("-" * 40)
    stdout, _, _ = run_ssh_command(f"cd {SERVER_PATH} && ls -la *.lock 2>/dev/null || echo 'Блокировок нет'")
    print(stdout)
    print()
    
    # 5. Проверка активности
    print("5️⃣ Активность за последний час:")
    print("-" * 40)
    stdout, _, _ = run_ssh_command(
        f"cd {SERVER_PATH} && python3 -c \""
        "import sqlite3; "
        "try: "
        "  conn = sqlite3.connect('trading.db'); "
        "  cursor = conn.cursor(); "
        "  cursor.execute('SELECT COUNT(*) FROM telemetry_cycles WHERE datetime(ts) >= datetime(\\\"now\\\", \\\"-1 hours\\\")'); "
        "  count = cursor.fetchone()[0]; "
        "  print(f'Циклов за последний час: {count}'); "
        "  conn.close(); "
        "except Exception as e: "
        "  print(f'Ошибка: {e}')"
        "\""
    )
    print(stdout)
    print()
    
    # 6. Последние строки логов
    print("6️⃣ Последние 15 строк логов:")
    print("-" * 40)
    stdout, _, _ = run_ssh_command(f"cd {SERVER_PATH} && tail -15 system_improved.log")
    print(stdout)
    print()
    
    return process_count

def restart_bot():
    """Перезапускает бота на сервере"""
    print("🔄 ПЕРЕЗАПУСК БОТА НА ПРОД-СЕРВЕРЕ")
    print("=" * 60)
    print()
    
    # Останавливаем все процессы
    print("1. Остановка процессов...")
    stdout, stderr, code = run_ssh_command(f"cd {SERVER_PATH} && pkill -9 -f main.py")
    time.sleep(2)
    print("✅ Процессы остановлены")
    print()
    
    # Очищаем блокировки
    print("2. Очистка блокировок...")
    stdout, stderr, code = run_ssh_command(f"cd {SERVER_PATH} && rm -f *.lock telegram_*.lock .telegram_*")
    print("✅ Блокировки очищены")
    print()
    
    # Запускаем бота
    print("3. Запуск бота...")
    stdout, stderr, code = run_ssh_command(
        f"cd {SERVER_PATH} && export ATRA_ENV=prod && nohup python3 main.py > server.log 2>&1 &"
    )
    time.sleep(3)
    print("✅ Бот запущен")
    print()
    
    # Проверяем, что бот запустился
    print("4. Проверка запуска...")
    stdout, stderr, code = run_ssh_command(f"cd {SERVER_PATH} && ps aux | grep main.py | grep -v grep")
    if stdout.strip():
        print("✅ Бот успешно запущен:")
        print(stdout)
    else:
        print("❌ Бот не запустился!")
        print("Проверьте логи:")
        stdout, _, _ = run_ssh_command(f"cd {SERVER_PATH} && tail -20 server.log")
        print(stdout)
    print()
    
    # Показываем последние логи
    print("5. Последние строки логов:")
    print("-" * 40)
    stdout, _, _ = run_ssh_command(f"cd {SERVER_PATH} && tail -20 server.log 2>/dev/null || tail -20 system_improved.log")
    print(stdout)
    print()

def main():
    """Главная функция"""
    print()
    
    # Проверяем статус
    process_count = check_bot_status()
    
    # Определяем, нужно ли перезапускать
    if process_count == 0:
        print("❌ БОТ НЕ ЗАПУЩЕН!")
        response = input("Запустить бота? (y/n): ").strip().lower()
        if response == 'y':
            restart_bot()
        else:
            print("Отменено")
    elif process_count > 1:
        print(f"⚠️ НАЙДЕНО {process_count} ЭКЗЕМПЛЯРОВ!")
        response = input("Перезапустить бота? (y/n): ").strip().lower()
        if response == 'y':
            restart_bot()
        else:
            print("Отменено")
    else:
        print("✅ Бот запущен (1 экземпляр)")
        response = input("Перезапустить бота? (y/n): ").strip().lower()
        if response == 'y':
            restart_bot()
        else:
            print("Бот работает, перезапуск не требуется")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

