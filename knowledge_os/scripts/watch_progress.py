#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Показ прогресса оптимизации"""

import time
import os
import sys

LOG_FILE = "/tmp/opt_progress_bar.log"

def show_progress():
    """Показывает текущий прогресс"""
    if not os.path.exists(LOG_FILE):
        return "⏳ Ожидание запуска оптимизации..."
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        if not lines:
            return "⏳ Лог пуст, оптимизация еще не началась..."
        
        # Ищем строки с прогрессом
        progress_info = []
        last_lines = lines[-50:]
        
        for line in last_lines:
            if any(x in line for x in ['Прогресс', '█', '░', 'завершен', 'Тестируем', 'комб', 'симв', 
                                       'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT', 
                                       'СТАТИСТИКА', 'ЛУЧШИЕ', '✅', '⚠️', '❌']):
                progress_info.append(line.strip())
        
        if progress_info:
            return "\n".join(progress_info[-20:])
        else:
            return "\n".join(last_lines[-20:])
    except Exception as e:
        return f"Ошибка чтения лога: {e}"

if __name__ == "__main__":
    print(show_progress())

