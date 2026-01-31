#!/usr/bin/env python3
"""
Мониторинг выполнения теста в реальном времени
"""

import time
import glob
import os
from pathlib import Path

def monitor_test():
    """Мониторить выполнение теста"""
    print("🔍 Мониторинг теста...")
    print("Нажмите Ctrl+C для остановки\n")
    
    last_size = 0
    last_file = None
    
    try:
        while True:
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
                    print(f"📄 Новый лог: {current_file}")
                    last_file = current_file
                    last_size = 0
                
                if current_size > last_size:
                    # Читаем новые строки
                    with open(current_file, 'r', encoding='utf-8') as f:
                        f.seek(last_size)
                        new_lines = f.readlines()
                        
                        for line in new_lines:
                            if any(keyword in line for keyword in ['✅', '❌', 'РЕЗУЛЬТАТ', 'COMPLETE', 'ERROR', 'Выполнено', 'Синтезир', 'сайт', 'HTML']):
                                print(line.rstrip())
                    
                    last_size = current_size
                
                # Проверяем завершение
                with open(current_file, 'r', encoding='utf-8') as f:
                    content = f.read()
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
                        
                        # Ищем файлы результатов
                        result_files = list(Path('logs').glob('website*.html')) + list(Path('logs').glob('website*.txt'))
                        if result_files:
                            print("\n" + "=" * 80)
                            print("СОХРАНЕННЫЕ ФАЙЛЫ:")
                            print("=" * 80)
                            for f in sorted(result_files, key=lambda x: x.stat().st_mtime, reverse=True):
                                print(f"  {f}")
                        
                        break
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Мониторинг остановлен")

if __name__ == "__main__":
    monitor_test()
