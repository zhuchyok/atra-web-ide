#!/usr/bin/env python3
"""
Скрипт для деплоя всех оптимизаций БД на сервер через Python.
Использует pexpect для автоматизации SSH/SCP операций.
"""

import os
import sys
import pexpect
from pathlib import Path

SERVER = "root@185.177.216.15"
PASSWORD = "u44Ww9NmtQj,XG"
REMOTE_DIR = "/root/atra"

# Список файлов для деплоя
FILES = [
    # Модули оптимизаций
    "src/database/archive_manager.py",
    "src/database/index_auditor.py",
    "src/database/query_optimizer.py",
    "src/database/table_maintenance.py",
    "src/database/materialized_views.py",
    "src/database/column_order_optimizer.py",
    "src/database/temp_tables_optimizer.py",
    "src/database/optimization_manager.py",
    "src/database/fetch_optimizer.py",
    "src/database/query_profiler.py",
    # Обновленный db.py
    "src/database/db.py",
    # Скрипты
    "scripts/archive_old_data.py",
    "scripts/optimize_database.py",
    "scripts/apply_all_optimizations.py",
    "scripts/monitor_database_performance.py",
]


def check_files():
    """Проверяет наличие всех файлов"""
    missing = []
    for file in FILES:
        if not Path(file).exists():
            missing.append(file)
        else:
            print(f"✅ {file}")
    return missing


def deploy_file(file_path):
    """Загружает один файл на сервер"""
    try:
        print(f"  📤 {file_path}...", end=" ", flush=True)
        
        # Используем scp с pexpect для автоматического ввода пароля
        cmd = f"scp -o StrictHostKeyChecking=no {file_path} {SERVER}:{REMOTE_DIR}/{file_path}"
        child = pexpect.spawn(cmd, timeout=30)
        
        # Ожидаем запрос пароля
        index = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=10)
        
        if index == 0:
            child.sendline(PASSWORD)
            child.expect(pexpect.EOF)
            child.close()
            if child.exitstatus == 0:
                print("✅")
                return True
            else:
                print(f"❌ (код выхода: {child.exitstatus})")
                return False
        else:
            child.close()
            if child.exitstatus == 0:
                print("✅")
                return True
            else:
                print(f"❌ (код выхода: {child.exitstatus})")
                return False
                
    except pexpect.TIMEOUT:
        print("❌ (таймаут)")
        return False
    except Exception as e:
        print(f"❌ ({e})")
        return False


def create_remote_dirs():
    """Создает необходимые директории на сервере"""
    try:
        print("📁 Создание директорий на сервере...")
        cmd = f"ssh -o StrictHostKeyChecking=no {SERVER} 'mkdir -p {REMOTE_DIR}/src/database {REMOTE_DIR}/scripts'"
        child = pexpect.spawn(cmd, timeout=30)
        
        index = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(PASSWORD)
            child.expect(pexpect.EOF)
        
        child.close()
        return child.exitstatus == 0
    except Exception as e:
        print(f"⚠️  Ошибка создания директорий: {e}")
        return False


def set_permissions():
    """Устанавливает права на выполнение для скриптов"""
    try:
        print("🔧 Установка прав на скрипты...")
        cmd = f"ssh -o StrictHostKeyChecking=no {SERVER} 'cd {REMOTE_DIR} && chmod +x scripts/*.py'"
        child = pexpect.spawn(cmd, timeout=30)
        
        index = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(PASSWORD)
            child.expect(pexpect.EOF)
        
        child.close()
        return child.exitstatus == 0
    except Exception as e:
        print(f"⚠️  Ошибка установки прав: {e}")
        return False


def main():
    """Основная функция деплоя"""
    print("=" * 70)
    print("🚀 ДЕПЛОЙ ОПТИМИЗАЦИЙ БАЗЫ ДАННЫХ НА СЕРВЕР")
    print("=" * 70)
    print()
    
    # Проверяем наличие файлов
    print("📦 Проверка файлов...")
    missing = check_files()
    
    if missing:
        print()
        print(f"❌ Отсутствуют файлы ({len(missing)}):")
        for file in missing:
            print(f"   - {file}")
        print()
        response = input("Продолжить деплой без отсутствующих файлов? (y/n): ")
        if response.lower() != 'y':
            print("Деплой отменен.")
            return 1
    
    print()
    print(f"✅ Найдено файлов: {len(FILES) - len(missing)}/{len(FILES)}")
    print()
    
    # Создаем директории на сервере
    if not create_remote_dirs():
        print("⚠️  Не удалось создать директории, продолжаем...")
    print()
    
    # Загружаем файлы
    print("📤 Загрузка файлов на сервер...")
    print()
    
    success_count = 0
    failed_files = []
    
    for file in FILES:
        if Path(file).exists():
            if deploy_file(file):
                success_count += 1
            else:
                failed_files.append(file)
        else:
            print(f"  ⏭️  {file} (пропущен - файл не найден)")
    
    print()
    
    # Устанавливаем права
    set_permissions()
    print()
    
    # Итоги
    print("=" * 70)
    if failed_files:
        print(f"⚠️  Деплой завершен с ошибками:")
        print(f"   Успешно: {success_count}/{len(FILES) - len(missing)}")
        print(f"   Ошибок: {len(failed_files)}")
        for file in failed_files:
            print(f"      - {file}")
    else:
        print(f"✅ Деплой завершен успешно!")
        print(f"   Загружено файлов: {success_count}")
    
    print()
    print("📋 Следующие шаги на сервере:")
    print("   1. Применить оптимизации: python3 scripts/apply_all_optimizations.py")
    print("   2. Проверить статус: python3 scripts/apply_all_optimizations.py --report")
    print("   3. Мониторинг: python3 scripts/monitor_database_performance.py")
    print()
    print("=" * 70)
    
    return 0 if not failed_files else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Деплой прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

