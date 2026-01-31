#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализ блокировок сигналов из логов
"""

import re
import sys
import os
from collections import defaultdict
from datetime import datetime

def analyze_log_file(log_file):
    """Анализ лог файла на предмет блокировок сигналов"""
    
    block_reasons = defaultdict(int)
    stage_stats = defaultdict(lambda: {'passed': 0, 'blocked': 0})
    symbol_stats = defaultdict(lambda: {'attempts': 0, 'blocks': 0, 'reasons': []})
    
    # Паттерны для поиска блокировок
    patterns = {
        'direction_check': re.compile(r'Direction.*confidence|Direction Check|direction_confidence', re.I),
        'quality_score': re.compile(r'Quality Score|quality.*score|качество.*сигнала', re.I),
        'rsi_warning': re.compile(r'RSI.*Warning|RSI.*блок|RSI.*65|RSI.*35', re.I),
        'mtf_confirmation': re.compile(r'MTF.*Confirmation|MTF.*блок|мультитаймфрейм', re.I),
        'btc_alignment': re.compile(r'BTC.*alignment|BTC.*тренд|BTC.*блок', re.I),
        'anomaly': re.compile(r'аномали|anomaly|кружков', re.I),
        'false_breakout': re.compile(r'False.*Breakout|ложный.*пробой', re.I),
        'volume': re.compile(r'Volume.*filter|объем.*фильтр', re.I),
        'liquidity': re.compile(r'ликвидность|liquidity|depth', re.I),
    }
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        print(f"📊 Анализ лог файла: {log_file}")
        print(f"   Всего строк: {len(lines)}")
        print("")
        
        # Анализируем последние 10000 строк
        recent_lines = lines[-10000:] if len(lines) > 10000 else lines
        
        for line in recent_lines:
            # Поиск блокировок
            if any(keyword in line.lower() for keyword in ['блок', 'отклонен', 'отклонён', 'rejected', 'blocked', 'не пройден']):
                # Определяем причину блокировки
                for reason, pattern in patterns.items():
                    if pattern.search(line):
                        block_reasons[reason] += 1
                        break
                
                # Извлекаем символ
                symbol_match = re.search(r'\[([A-Z]{2,10}USDT)\]', line)
                if symbol_match:
                    symbol = symbol_match.group(1)
                    symbol_stats[symbol]['attempts'] += 1
                    symbol_stats[symbol]['blocks'] += 1
                    symbol_stats[symbol]['reasons'].append(line.strip()[:100])
            
            # Поиск успешных прохождений
            if any(keyword in line.lower() for keyword in ['✅', 'прошел', 'пройден', 'passed', 'разрешен']):
                symbol_match = re.search(r'\[([A-Z]{2,10}USDT)\]', line)
                if symbol_match:
                    symbol = symbol_match.group(1)
                    symbol_stats[symbol]['attempts'] += 1
        
        # Статистика по этапам
        for line in recent_lines:
            for stage in ['validation', 'ai_score', 'volume', 'volatility', 'ema_pattern', 'direction_check', 'quality_score']:
                if stage.lower() in line.lower():
                    if '✅' in line or 'прошел' in line.lower() or 'passed' in line.lower():
                        stage_stats[stage]['passed'] += 1
                    elif '❌' in line or 'блок' in line.lower() or 'blocked' in line.lower():
                        stage_stats[stage]['blocked'] += 1
        
        # Выводим отчет
        print("=" * 70)
        print("📊 СТАТИСТИКА БЛОКИРОВОК СИГНАЛОВ")
        print("=" * 70)
        print("")
        
        if block_reasons:
            print("🔴 ПРИЧИНЫ БЛОКИРОВОК:")
            print("-" * 70)
            total_blocks = sum(block_reasons.values())
            for reason, count in sorted(block_reasons.items(), key=lambda x: x[1], reverse=True):
                pct = (count / total_blocks * 100) if total_blocks > 0 else 0
                print(f"  • {reason.replace('_', ' ').title()}: {count} ({pct:.1f}%)")
            print("")
        else:
            print("⚠️  Блокировки не найдены в логах")
            print("")
        
        if stage_stats:
            print("📈 СТАТИСТИКА ПО ЭТАПАМ:")
            print("-" * 70)
            for stage, stats in sorted(stage_stats.items()):
                total = stats['passed'] + stats['blocked']
                if total > 0:
                    pass_rate = (stats['passed'] / total * 100) if total > 0 else 0
                    print(f"  • {stage.replace('_', ' ').title()}:")
                    print(f"      Прошли: {stats['passed']} | Заблокированы: {stats['blocked']} | Проходимость: {pass_rate:.1f}%")
            print("")
        
        if symbol_stats:
            print("🎯 СТАТИСТИКА ПО СИМВОЛАМ (топ-10):")
            print("-" * 70)
            sorted_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['attempts'], reverse=True)[:10]
            for symbol, stats in sorted_symbols:
                block_rate = (stats['blocks'] / stats['attempts'] * 100) if stats['attempts'] > 0 else 0
                print(f"  • {symbol}: {stats['attempts']} попыток, {stats['blocks']} блокировок ({block_rate:.1f}%)")
            print("")
        
        # Поиск последних блокировок
        print("🔍 ПОСЛЕДНИЕ БЛОКИРОВКИ (топ-20):")
        print("-" * 70)
        recent_blocks = []
        for line in recent_lines[-1000:]:
            if any(keyword in line.lower() for keyword in ['блок', 'отклонен', 'rejected', 'не пройден']):
                # Извлекаем время
                time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                time_str = time_match.group(1) if time_match else "N/A"
                symbol_match = re.search(r'\[([A-Z]{2,10}USDT)\]', line)
                symbol = symbol_match.group(1) if symbol_match else "UNKNOWN"
                recent_blocks.append((time_str, symbol, line.strip()[:150]))
        
        for time_str, symbol, msg in recent_blocks[-20:]:
            print(f"  [{time_str}] {symbol}: {msg}")
        
        print("")
        print("=" * 70)
        
        return {
            'block_reasons': dict(block_reasons),
            'stage_stats': dict(stage_stats),
            'symbol_stats': dict(symbol_stats)
        }
        
    except FileNotFoundError:
        print(f"❌ Файл {log_file} не найден")
        return None
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
        return None

if __name__ == "__main__":
    import glob
    
    # Ищем последний лог файл
    log_files = glob.glob("bot_restart_*.log")
    if log_files:
        latest_log = max(log_files, key=lambda x: os.path.getmtime(x))
        analyze_log_file(latest_log)
    else:
        print("❌ Лог файлы не найдены")
        sys.exit(1)

