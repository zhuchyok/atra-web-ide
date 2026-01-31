#!/usr/bin/env python3
"""
Скрипт для показа прогресса оптимизации в реальном времени
"""
import os
import sys
import time
import re
from pathlib import Path

LOG_FILE = "/tmp/opt_realtime.log"
UPDATE_INTERVAL = 3  # секунды

def extract_progress_info(lines):
    """Извлекает информацию о прогрессе из лога"""
    info = {
        'current_symbol': None,
        'symbol_progress': None,
        'overall_progress': None,
        'completed_symbols': [],
        'errors': [],
        'last_lines': []
    }
    
    # Ищем текущий символ и прогресс
    for line in lines:
        # Текущий символ
        match = re.search(r'\[([A-Z]+USDT)\]', line)
        if match:
            info['current_symbol'] = match.group(1)
        
        # Прогресс комбинаций
        match = re.search(r'(\d+)/(\d+)\s*\(([\d.]+)%\)', line)
        if match:
            current, total, percent = match.groups()
            info['symbol_progress'] = f"{current}/{total} ({percent}%)"
        
        # Завершенные символы
        if 'завершен' in line.lower() or 'completed' in line.lower():
            match = re.search(r'\[([A-Z]+USDT)\]', line)
            if match and match.group(1) not in info['completed_symbols']:
                info['completed_symbols'].append(match.group(1))
        
        # Ошибки
        if 'ERROR' in line or 'Exception' in line or 'Error' in line:
            info['errors'].append(line.strip())
    
    info['last_lines'] = lines[-15:]
    return info

def format_progress_bar(current, total, width=40):
    """Форматирует текстовый прогресс-бар"""
    if total == 0:
        return "[" + " " * width + "] 0%"
    percent = (current / total) * 100
    filled = int((current / total) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {current}/{total} ({percent:.1f}%)"

def main():
    print("═══════════════════════════════════════════════════════════")
    print("📊 МОНИТОРИНГ ОПТИМИЗАЦИИ В РЕАЛЬНОМ ВРЕМЕНИ")
    print("═══════════════════════════════════════════════════════════")
    print(f"📁 Лог: {LOG_FILE}")
    print(f"🔄 Обновление каждые {UPDATE_INTERVAL} сек")
    print("═══════════════════════════════════════════════════════════")
    print()
    
    try:
        while True:
            # Очистка экрана (работает в терминале)
            os.system('clear' if os.name != 'nt' else 'cls')
            
            print("═══════════════════════════════════════════════════════════")
            print("📊 ПРОГРЕСС ОПТИМИЗАЦИИ")
            print("═══════════════════════════════════════════════════════════")
            print()
            
            if not os.path.exists(LOG_FILE):
                print("⏳ Ожидание запуска оптимизации...")
                print(f"   Лог файл: {LOG_FILE}")
                time.sleep(UPDATE_INTERVAL)
                continue
            
            # Читаем лог
            try:
                with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"❌ Ошибка чтения лога: {e}")
                time.sleep(UPDATE_INTERVAL)
                continue
            
            if not lines:
                print("⏳ Лог пуст, ожидание данных...")
                time.sleep(UPDATE_INTERVAL)
                continue
            
            # Извлекаем информацию
            info = extract_progress_info(lines)
            
            # Показываем текущий символ
            if info['current_symbol']:
                print(f"🔄 Текущий символ: {info['current_symbol']}")
                if info['symbol_progress']:
                    print(f"   Прогресс: {info['symbol_progress']}")
                print()
            
            # Показываем завершенные символы
            if info['completed_symbols']:
                print(f"✅ Завершено символов: {len(info['completed_symbols'])}")
                print(f"   {', '.join(info['completed_symbols'])}")
                print()
            
            # Показываем ошибки (если есть)
            if info['errors']:
                print("⚠️  ОШИБКИ:")
                for error in info['errors'][-5:]:  # Последние 5 ошибок
                    print(f"   {error}")
                print()
            
            # Показываем последние строки лога
            print("═══════════════════════════════════════════════════════════")
            print("📈 Последние строки лога:")
            print("═══════════════════════════════════════════════════════════")
            for line in info['last_lines']:
                # Фильтруем только важные строки
                if any(keyword in line.lower() for keyword in [
                    'прогресс', 'завершен', 'символ', 'ethusdt', 'bnbusdt', 
                    'solusdt', 'adausdt', 'оптимизация', 'лучшие', 'сохранение',
                    'error', 'exception', '✅', '❌'
                ]):
                    print(line.rstrip())
            
            print()
            print("═══════════════════════════════════════════════════════════")
            print(f"⏱️  Обновлено: {time.strftime('%H:%M:%S')}")
            print("   Нажмите Ctrl+C для выхода")
            print("═══════════════════════════════════════════════════════════")
            
            time.sleep(UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n👋 Мониторинг остановлен")

if __name__ == "__main__":
    main()

