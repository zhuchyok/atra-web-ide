#!/usr/bin/env python3
"""
Ожидание завершения теста и автоматический показ результатов
"""

import time
import glob
import os
from pathlib import Path

def wait_for_completion(max_wait_minutes=10):
    """Ожидать завершения теста"""
    print("⏳ Ожидание завершения теста...")
    print(f"Максимальное время ожидания: {max_wait_minutes} минут\n")

    start_time = time.time()
    last_size = 0
    last_file = None

    while (time.time() - start_time) < (max_wait_minutes * 60):
        # Находим последний лог
        log_files = sorted(
            glob.glob('logs/task_trace_*.log'),
            key=os.path.getmtime,
            reverse=True
        )

        if log_files:
            current_file = log_files[0]
            current_size = os.path.getsize(current_file)

            if current_file != last_file:
                print(f"📄 Отслеживаю: {current_file}")
                last_file = current_file
                last_size = 0

            # Проверяем завершение
            with open(current_file, 'r', encoding='utf-8') as f:
                content = f.read()

                if '✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО' in content:
                    print("\n✅ ТЕСТ ЗАВЕРШЕН!\n")

                    # Ищем результат
                    if '📄 РЕЗУЛЬТАТ:' in content:
                        result_start = content.find('📄 РЕЗУЛЬТАТ:')
                        result_end = content.find('\n', result_start + 2000)
                        result_section = content[result_start:result_end if result_end > 0 else result_start + 2000]

                        print("=" * 80)
                        print("РЕЗУЛЬТАТ:")
                        print("=" * 80)
                        print(result_section)
                        print("=" * 80)

                    # Ищем файлы результатов
                    result_files = list(Path('logs').glob('website*.html')) + list(Path('logs').glob('website*.txt'))
                    if result_files:
                        print("\n" + "=" * 80)
                        print("СОХРАНЕННЫЕ ФАЙЛЫ:")
                        print("=" * 80)
                        for f in sorted(result_files, key=lambda x: x.stat().st_mtime, reverse=True):
                            print(f"  📄 {f}")
                            if f.suffix == '.html':
                                print(f"     Откройте в браузере: open {f}")

                    return True

                # Показываем прогресс
                if current_size > last_size:
                    elapsed = int(time.time() - start_time)
                    print(f"⏳ Выполняется... ({elapsed}с) | Размер лога: {current_size} байт")
                    last_size = current_size

        time.sleep(5)

    print(f"\n⏱️ Превышено время ожидания ({max_wait_minutes} минут)")
    print("Проверьте логи вручную: python3 scripts/check_test_status.py")
    return False

if __name__ == "__main__":
    wait_for_completion()
