#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализ логов бота для получения статистики по фильтрам
"""

import re
from collections import defaultdict
from datetime import datetime

def analyze_logs(log_file='bot.log', lines_count=10000):
    """Анализирует логи бота для получения статистики по фильтрам"""
    
    filter_stats = defaultdict(lambda: {'passed': 0, 'failed': 0, 'symbols': defaultdict(int)})
    symbol_stats = defaultdict(lambda: {'total': 0, 'passed': 0, 'failed': 0, 'filters_failed': defaultdict(int)})
    filter_patterns = [
        (r'\[([A-Z]+USDT)\]\s+(\w+):\s+✅\s+ПРОЙДЕН', 'passed'),
        (r'\[([A-Z]+USDT)\]\s+(\w+):\s+❌\s+НЕ ПРОЙДЕН', 'failed'),
        (r'📊\s+\[([A-Z]+USDT)\]\s+(\w+):\s+✅\s+ПРОЙДЕН', 'passed'),
        (r'📊\s+\[([A-Z]+USDT)\]\s+(\w+):\s+❌\s+НЕ ПРОЙДЕН', 'failed'),
    ]
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            # Берем последние N строк
            lines = all_lines[-lines_count:]
            
            for line in lines:
                for pattern, status in filter_patterns:
                    match = re.search(pattern, line)
                    if match:
                        symbol = match.group(1)
                        filter_name = match.group(2)
                        
                        if status == 'passed':
                            filter_stats[filter_name]['passed'] += 1
                            symbol_stats[symbol]['passed'] += 1
                        else:
                            filter_stats[filter_name]['failed'] += 1
                            filter_stats[filter_name]['symbols'][symbol] += 1
                            symbol_stats[symbol]['failed'] += 1
                            symbol_stats[symbol]['filters_failed'][filter_name] += 1
                        
                        symbol_stats[symbol]['total'] += 1
                        break
                
                # Также ищем общие паттерны
                if 'Score' in line and 'USDT' in line:
                    symbol_match = re.search(r'\[([A-Z]+USDT)\]', line)
                    if symbol_match:
                        symbol = symbol_match.group(1)
                        symbol_stats[symbol]['total'] += 1
    
    except Exception as e:
        print(f"Ошибка при чтении логов: {e}")
        return None, None
    
    return filter_stats, symbol_stats

def generate_report(filter_stats, symbol_stats):
    """Генерирует отчет на основе статистики"""
    
    report = []
    report.append("=" * 80)
    report.append("📊 ПОДРОБНЫЙ ОТЧЕТ О ГЕНЕРАЦИИ СИГНАЛОВ И ФИЛЬТРАХ")
    report.append("=" * 80)
    report.append(f"Время генерации отчета: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Статистика по фильтрам
    report.append("=" * 80)
    report.append("1. ДЕТАЛЬНАЯ СТАТИСТИКА ПО ФИЛЬТРАМ")
    report.append("=" * 80)
    report.append("")
    
    if filter_stats:
        total_checks = sum(s['passed'] + s['failed'] for s in filter_stats.values())
        report.append(f"Всего проверок фильтров: {total_checks}")
        report.append("")
        
        for filter_name, stats in sorted(filter_stats.items(), key=lambda x: x[1]['failed'], reverse=True):
            total = stats['passed'] + stats['failed']
            if total > 0:
                pass_rate = (stats['passed'] / total) * 100
                fail_rate = (stats['failed'] / total) * 100
                
                report.append(f"📊 {filter_name}:")
                report.append(f"   Всего проверок: {total}")
                report.append(f"   ✅ Прошло: {stats['passed']} ({pass_rate:.1f}%)")
                report.append(f"   ❌ Отклонено: {stats['failed']} ({fail_rate:.1f}%)")
                
                if stats['symbols']:
                    report.append(f"   🔸 Топ символов по отклонениям:")
                    for symbol, count in sorted(stats['symbols'].items(), key=lambda x: x[1], reverse=True)[:5]:
                        report.append(f"      - {symbol}: {count} отклонений")
                
                report.append("")
    else:
        report.append("⚠️ Нет данных по фильтрам в логах")
        report.append("")
    
    # Статистика по символам
    report.append("=" * 80)
    report.append("2. СТАТИСТИКА ПО СИМВОЛАМ")
    report.append("=" * 80)
    report.append("")
    
    if symbol_stats:
        report.append(f"{'Символ':<15} {'Всего':<10} {'Прошло':<10} {'Отклонено':<12} {'% отклонения':<15} {'Топ фильтр'}")
        report.append("-" * 80)
        
        for symbol, stats in sorted(symbol_stats.items(), key=lambda x: x[1]['failed'], reverse=True)[:30]:
            if stats['total'] > 0:
                rejection_pct = (stats['failed'] / stats['total'] * 100) if stats['total'] > 0 else 0
                top_filter = max(stats['filters_failed'].items(), key=lambda x: x[1])[0] if stats['filters_failed'] else '-'
                report.append(f"{symbol:<15} {stats['total']:<10} {stats['passed']:<10} {stats['failed']:<12} {rejection_pct:.1f}%{'':<10} {top_filter}")
    else:
        report.append("⚠️ Нет данных по символам в логах")
    
    report.append("")
    
    return "\n".join(report)

if __name__ == "__main__":
    filter_stats, symbol_stats = analyze_logs('bot.log', 10000)
    report = generate_report(filter_stats, symbol_stats)
    print(report)
    
    # Сохраняем в файл
    with open('scripts/reports/filter_analysis_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    print("\n✅ Отчет сохранен в scripts/reports/filter_analysis_report.md")

