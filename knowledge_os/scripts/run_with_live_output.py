#!/usr/bin/env python3
"""
Запускает оптимизацию и показывает прогресс в реальном времени
"""
import subprocess
import sys
import os
import time
import threading

def read_output(pipe, output_list):
    """Читает вывод из pipe и добавляет в список"""
    try:
        for line in iter(pipe.readline, ''):
            if line:
                output_list.append(line.rstrip())
                # Показываем последние 20 строк
                if len(output_list) > 20:
                    output_list.pop(0)
    except Exception:
        pass
    finally:
        pipe.close()

def main():
    script_path = "scripts/optimize_symbol_params_with_ai.py"
    
    print("═══════════════════════════════════════════════════════════")
    print("📊 ЗАПУСК ОПТИМИЗАЦИИ С ПРОГРЕССОМ В РЕАЛЬНОМ ВРЕМЕНИ")
    print("═══════════════════════════════════════════════════════════")
    print()
    
    # Запускаем процесс
    proc = subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    output_lines = []
    
    # Запускаем поток для чтения вывода
    thread = threading.Thread(target=read_output, args=(proc.stdout, output_lines))
    thread.daemon = True
    thread.start()
    
    try:
        last_count = 0
        while proc.poll() is None:
            time.sleep(2)
            
            # Показываем прогресс
            if output_lines:
                current_count = len(output_lines)
                if current_count > last_count:
                    # Очищаем экран (работает в терминале)
                    os.system('clear' if os.name != 'nt' else 'cls')
                    
                    print("═══════════════════════════════════════════════════════════")
                    print("📊 ПРОГРЕСС ОПТИМИЗАЦИИ")
                    print("═══════════════════════════════════════════════════════════")
                    print()
                    
                    # Показываем последние строки
                    for line in output_lines[-15:]:
                        print(line)
                    
                    print()
                    print("═══════════════════════════════════════════════════════════")
                    print(f"⏱️  Обновлено: {time.strftime('%H:%M:%S')}")
                    print(f"📊 Строк вывода: {current_count}")
                    
                    last_count = current_count
        
        # Ждем завершения потока
        thread.join(timeout=1)
        
        # Финальный вывод
        if output_lines:
            os.system('clear' if os.name != 'nt' else 'cls')
            print("═══════════════════════════════════════════════════════════")
            print("📊 ФИНАЛЬНЫЙ РЕЗУЛЬТАТ")
            print("═══════════════════════════════════════════════════════════")
            print()
            for line in output_lines:
                print(line)
        
        print()
        print("═══════════════════════════════════════════════════════════")
        print(f"✅ Процесс завершен с кодом: {proc.returncode}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Прерывание...")
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()

