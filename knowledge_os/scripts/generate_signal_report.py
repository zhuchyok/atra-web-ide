#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для генерации подробного отчета о сигналах и фильтрах
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

def get_signal_statistics(db_path='trading.db', hours=24):
    """Получает статистику по сигналам и фильтрам"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    
    report = []
    report.append("=" * 80)
    report.append("📊 ПОДРОБНЫЙ ОТЧЕТ О ГЕНЕРАЦИИ СИГНАЛОВ И ФИЛЬТРАХ")
    report.append("=" * 80)
    report.append(f"Период: последние {hours} часов")
    report.append(f"Время генерации отчета: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 1. Общая статистика по сигналам
    report.append("=" * 80)
    report.append("1. ОБЩАЯ СТАТИСТИКА ПО СИГНАЛАМ")
    report.append("=" * 80)
    
    try:
        cursor.execute('SELECT COUNT(*) FROM signals_log WHERE created_at >= ?', (since,))
        total_signals = cursor.fetchone()[0]
        report.append(f"✅ Всего сгенерировано сигналов: {total_signals}")
    except Exception as e:
        report.append(f"⚠️ Ошибка при получении статистики сигналов: {e}")
        total_signals = 0
    
    try:
        cursor.execute('SELECT COUNT(*) FROM rejected_signals WHERE created_at >= ?', (since,))
        rejected_signals = cursor.fetchone()[0]
        report.append(f"❌ Отклонено сигналов: {rejected_signals}")
        if total_signals > 0:
            rejection_rate = (rejected_signals / total_signals) * 100
            report.append(f"📉 Процент отклонения: {rejection_rate:.2f}%")
    except Exception as e:
        report.append(f"⚠️ Ошибка при получении статистики отклонений: {e}")
        rejected_signals = 0
    
    report.append("")
    
    # 2. Статистика по фильтрам
    report.append("=" * 80)
    report.append("2. ДЕТАЛЬНАЯ СТАТИСТИКА ПО ФИЛЬТРАМ")
    report.append("=" * 80)
    report.append("")
    
    try:
        cursor.execute('''
            SELECT filter_name, symbol, passed, reason, created_at
            FROM filter_performance 
            WHERE created_at >= ?
            ORDER BY created_at DESC
        ''', (since,))
        
        filter_stats = defaultdict(lambda: {
            'total': 0, 
            'passed': 0, 
            'failed': 0, 
            'symbols': defaultdict(int),
            'reasons': defaultdict(int)
        })
        
        for row in cursor.fetchall():
            filter_name, symbol, passed, reason, created_at = row
            filter_stats[filter_name]['total'] += 1
            if passed:
                filter_stats[filter_name]['passed'] += 1
            else:
                filter_stats[filter_name]['failed'] += 1
                if symbol:
                    filter_stats[filter_name]['symbols'][symbol] += 1
                if reason:
                    filter_stats[filter_name]['reasons'][reason] += 1
        
        if filter_stats:
            for filter_name, data in sorted(filter_stats.items(), key=lambda x: x[1]['total'], reverse=True):
                report.append(f"📊 {filter_name}:")
                report.append(f"   Всего проверок: {data['total']}")
                
                if data['total'] > 0:
                    pass_rate = (data['passed'] / data['total']) * 100
                    fail_rate = (data['failed'] / data['total']) * 100
                    report.append(f"   ✅ Прошло: {data['passed']} ({pass_rate:.1f}%)")
                    report.append(f"   ❌ Отклонено: {data['failed']} ({fail_rate:.1f}%)")
                else:
                    report.append(f"   ✅ Прошло: {data['passed']}")
                    report.append(f"   ❌ Отклонено: {data['failed']}")
                
                if data['symbols']:
                    report.append(f"   🔸 Топ символов по отклонениям:")
                    for symbol, count in sorted(data['symbols'].items(), key=lambda x: x[1], reverse=True)[:5]:
                        report.append(f"      - {symbol}: {count} отклонений")
                
                if data['reasons']:
                    report.append(f"   🔸 Причины отклонений:")
                    for reason, count in sorted(data['reasons'].items(), key=lambda x: x[1], reverse=True)[:3]:
                        report.append(f"      - {reason}: {count}")
                
                report.append("")
        else:
            report.append("⚠️ Нет данных по фильтрам за указанный период")
            report.append("")
            
    except Exception as e:
        report.append(f"⚠️ Ошибка при получении статистики фильтров: {e}")
        report.append("")
    
    # 3. Топ причин отклонения
    report.append("=" * 80)
    report.append("3. ТОП ПРИЧИН ОТКЛОНЕНИЯ СИГНАЛОВ")
    report.append("=" * 80)
    report.append("")
    
    try:
        cursor.execute('''
            SELECT reason, COUNT(*) as count
            FROM rejected_signals 
            WHERE created_at >= ?
            GROUP BY reason
            ORDER BY count DESC
            LIMIT 15
        ''', (since,))
        
        reasons = cursor.fetchall()
        if reasons:
            for i, (reason, count) in enumerate(reasons, 1):
                report.append(f"{i}. {reason}: {count} отклонений")
        else:
            report.append("⚠️ Нет данных о причинах отклонения")
        report.append("")
    except Exception as e:
        report.append(f"⚠️ Ошибка при получении причин отклонения: {e}")
        report.append("")
    
    # 4. Статистика по символам
    report.append("=" * 80)
    report.append("4. СТАТИСТИКА ПО СИМВОЛАМ")
    report.append("=" * 80)
    report.append("")
    
    try:
        cursor.execute('''
            SELECT symbol, 
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) as accepted,
                   SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
            FROM signals_log 
            WHERE created_at >= ?
            GROUP BY symbol
            ORDER BY total DESC
            LIMIT 20
        ''', (since,))
        
        symbols = cursor.fetchall()
        if symbols:
            report.append(f"{'Символ':<15} {'Всего':<10} {'Принято':<10} {'Отклонено':<10} {'% отклонения':<15}")
            report.append("-" * 70)
            for symbol, total, accepted, rejected in symbols:
                rejection_pct = (rejected / total * 100) if total > 0 else 0
                report.append(f"{symbol:<15} {total:<10} {accepted or 0:<10} {rejected or 0:<10} {rejection_pct:.1f}%")
        else:
            report.append("⚠️ Нет данных по символам")
        report.append("")
    except Exception as e:
        report.append(f"⚠️ Ошибка при получении статистики по символам: {e}")
        report.append("")
    
    # 5. Последние отклоненные сигналы
    report.append("=" * 80)
    report.append("5. ПОСЛЕДНИЕ ОТКЛОНЕННЫЕ СИГНАЛЫ (топ-10)")
    report.append("=" * 80)
    report.append("")
    
    try:
        cursor.execute('''
            SELECT symbol, reason, created_at
            FROM rejected_signals 
            WHERE created_at >= ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (since,))
        
        recent = cursor.fetchall()
        if recent:
            for symbol, reason, created_at in recent:
                report.append(f"❌ {symbol} - {reason} ({created_at})")
        else:
            report.append("⚠️ Нет недавних отклонений")
        report.append("")
    except Exception as e:
        report.append(f"⚠️ Ошибка при получении последних отклонений: {e}")
        report.append("")
    
    conn.close()
    
    return "\n".join(report)

if __name__ == "__main__":
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    report = get_signal_statistics(hours=hours)
    print(report)
    
    # Сохраняем в файл
    report_file = Path("scripts/reports/signal_statistics_report.md")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report, encoding='utf-8')
    print(f"\n✅ Отчет сохранен в {report_file}")

