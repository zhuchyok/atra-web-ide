#!/usr/bin/env python3
"""
Скрипт для проверки статуса выполнения теста
"""

import glob
import os
from pathlib import Path

def check_status():
    """Проверить статус последнего теста"""

    # Находим последний лог
    log_files = sorted(
        glob.glob('logs/task_trace_*.log'),
        key=os.path.getmtime,
        reverse=True
    )

    if not log_files:
        print("❌ Логи не найдены")
        return

    latest_log = log_files[0]
    print(f"📄 Последний лог: {latest_log}\n")

    # Читаем последние строки
    with open(latest_log, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Показываем последние 30 строк
    print("=" * 80)
    print("ПОСЛЕДНИЕ СОБЫТИЯ:")
    print("=" * 80)
    for line in lines[-30:]:
        print(line.rstrip())

    # Ищем ключевые слова
    content = ''.join(lines)

    if '✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО' in content:
        print("\n✅ ТЕСТ ЗАВЕРШЕН!")

        # Ищем результат
        if '📄 РЕЗУЛЬТАТ:' in content:
            result_start = content.find('📄 РЕЗУЛЬТАТ:')
            result_section = content[result_start:result_start+2000]
            print("\n" + "=" * 80)
            print("РЕЗУЛЬТАТ:")
            print("=" * 80)
            print(result_section[:1500])
            if len(result_section) > 1500:
                print(f"\n... (еще {len(result_section) - 1500} символов)")

        # Ищем сохраненные файлы
        result_files = list(Path('logs').glob('website*.html')) + list(Path('logs').glob('website*.txt'))
        if result_files:
            print("\n" + "=" * 80)
            print("СОХРАНЕННЫЕ ФАЙЛЫ:")
            print("=" * 80)
            for f in sorted(result_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                print(f"  {f}")
    else:
        print("\n⏳ ТЕСТ ВЫПОЛНЯЕТСЯ...")
        print("   Подождите несколько минут и проверьте снова")

if __name__ == "__main__":
    check_status()
