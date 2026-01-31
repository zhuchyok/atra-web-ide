#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Мониторинг прогресса оптимизации"""

import time
import os
import sys

LOG_FILE = "/tmp/optimization_progress.log"

def show_progress():
    """Показывает текущий прогресс из лога"""
    if not os.path.exists(LOG_FILE):
        print("⏳ Ожидание запуска оптимизации...")
        return
    
    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    if not lines:
        print("⏳ Лог пуст, оптимизация еще не началась...")
        return
    
    # Показываем последние строки с прогрессом
    print("\n" + "="*70)
    print("📊 ТЕКУЩИЙ ПРОГРЕСС ОПТИМИЗАЦИИ")
    print("="*70)
    
    # Ищем строки с прогрессом
    progress_lines = [l for l in lines if any(x in l for x in ['Прогресс', 'завершен', 'Тестируем', 'комб', 'симв', '█', '░', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT'])]
    
    if progress_lines:
        print("\n".join(progress_lines[-15:]))
    else:
        # Показываем последние строки
        print("\n".join(lines[-20:]))
    
    print("="*70)
    print(f"📄 Полный лог: tail -f {LOG_FILE}")
    print("="*70)

if __name__ == "__main__":
    while True:
        os.system('clear' if os.name != 'nt' else 'cls')
        show_progress()
        time.sleep(5)

