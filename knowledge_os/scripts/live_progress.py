#!/usr/bin/env python3
"""Показ прогресса оптимизации в реальном времени"""
import time
import os
import subprocess
import sys

LOG_FILE = "/tmp/opt_realtime.log"
SCRIPT = "scripts/optimize_symbol_params_with_ai.py"

def show_progress():
    """Показывает текущий прогресс"""
    if not os.path.exists(LOG_FILE):
        return "⏳ Ожидание запуска..."
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        if not lines:
            return "⏳ Лог пуст..."
        
        # Ищем важные строки
        important = []
        for line in lines:
            line_lower = line.lower()
            if any(kw in line_lower for kw in [
                'прогресс', 'завершен', 'символ', 'ethusdt', 'bnbusdt', 
                'solusdt', 'adausdt', 'оптимизация', 'лучшие', 'сохранение',
                'error', 'exception', 'tp_mult', 'sl_mult', '✅', '❌'
            ]):
                important.append(line.rstrip())
        
        if important:
            return "\n".join(important[-15:])
        return "\n".join([l.rstrip() for l in lines[-10:]])
    except Exception as e:
        return f"❌ Ошибка: {e}"

def main():
    # Запускаем оптимизацию в фоне
    print("🚀 Запуск оптимизации...")
    proc = subprocess.Popen(
        [sys.executable, SCRIPT],
        stdout=open(LOG_FILE, 'w'),
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    print(f"✅ PID: {proc.pid}")
    print()
    
    # Показываем прогресс
    try:
        while proc.poll() is None:
            os.system('clear' if os.name != 'nt' else 'cls')
            print("═══════════════════════════════════════════════════════════")
            print("📊 ПРОГРЕСС ОПТИМИЗАЦИИ В РЕАЛЬНОМ ВРЕМЕНИ")
            print("═══════════════════════════════════════════════════════════")
            print()
            print(show_progress())
            print()
            print("═══════════════════════════════════════════════════════════")
            print(f"⏱️  {time.strftime('%H:%M:%S')} | PID: {proc.pid} | Ctrl+C для выхода")
            time.sleep(3)
    except KeyboardInterrupt:
        print("\n\n👋 Остановка мониторинга...")
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()

