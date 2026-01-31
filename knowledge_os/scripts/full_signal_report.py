#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Полный отчет о генерации сигналов и фильтрах
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

def generate_full_report(db_path='trading.db', hours=24):
    """Генерирует полный отчет о сигналах и фильтрах"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    
    report = []
    report.append("=" * 80)
    report.append("📊 ПОЛНЫЙ ОТЧЕТ О ГЕНЕРАЦИИ СИГНАЛОВ И ФИЛЬТРАХ")
    report.append("=" * 80)
    report.append(f"Период: последние {hours} часов (с {since})")
    report.append(f"Время отчета: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 1. Общая статистика сигналов
    report.append("=" * 80)
    report.append("1. ОБЩАЯ СТАТИСТИКА ПО СИГНАЛАМ")
    report.append("=" * 80)
    report.append("")
    
    try:
        cursor.execute('SELECT COUNT(*) FROM signals_log WHERE created_at >= ?', (since,))
        total_signals = cursor.fetchone()[0]
        report.append(f"✅ Всего сгенерировано сигналов: {total_signals}")
        report.append("")
        
        # Статистика по символам
        cursor.execute('''
            SELECT symbol, COUNT(*) as count, 
                   AVG(quality_score) as avg_score,
                   MIN(quality_score) as min_score,
                   MAX(quality_score) as max_score
            FROM signals_log 
            WHERE created_at >= ?
            GROUP BY symbol
            ORDER BY count DESC
            LIMIT 30
        ''', (since,))
        
        report.append("ТОП-30 СИМВОЛОВ ПО КОЛИЧЕСТВУ СИГНАЛОВ:")
        report.append(f"{'Символ':<15} {'Кол-во':<10} {'Ср. Score':<12} {'Min':<10} {'Max':<10}")
        report.append("-" * 70)
        
        for row in cursor.fetchall():
            symbol, count, avg_score, min_score, max_score = row
            avg_score = avg_score or 0
            min_score = min_score or 0
            max_score = max_score or 0
            report.append(f"{symbol:<15} {count:<10} {avg_score:<12.2f} {min_score:<10.2f} {max_score:<10.2f}")
        
        report.append("")
        
    except Exception as e:
        report.append(f"⚠️ Ошибка при получении статистики сигналов: {e}")
        report.append("")
    
    # 2. Статистика по фильтрам из filter_checks
    report.append("=" * 80)
    report.append("2. ДЕТАЛЬНАЯ СТАТИСТИКА ПО ФИЛЬТРАМ")
    report.append("=" * 80)
    report.append("")
    
    try:
        cursor.execute('''
            SELECT filter_type, 
                   COUNT(*) as total,
                   SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed,
                   SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed
            FROM filter_checks 
            WHERE created_at >= ?
            GROUP BY filter_type
            ORDER BY failed DESC, total DESC
        ''', (since,))
        
        filter_data = cursor.fetchall()
        
        if filter_data:
            report.append(f"{'Фильтр':<30} {'Всего':<10} {'Прошло':<10} {'Отклонено':<12} {'% отклонения':<15}")
            report.append("-" * 80)
            
            total_checks = 0
            total_passed = 0
            total_failed = 0
            
            for row in filter_data:
                filter_type, total, passed, failed = row
                failed = failed or 0
                passed = passed or 0
                total = total or 0
                fail_rate = (failed / total * 100) if total > 0 else 0
                report.append(f"{filter_type:<30} {total:<10} {passed:<10} {failed:<12} {fail_rate:.1f}%")
                
                total_checks += total
                total_passed += passed
                total_failed += failed
            
            report.append("-" * 80)
            overall_fail_rate = (total_failed / total_checks * 100) if total_checks > 0 else 0
            report.append(f"{'ИТОГО':<30} {total_checks:<10} {total_passed:<10} {total_failed:<12} {overall_fail_rate:.1f}%")
            report.append("")
            
            # Детали по каждому фильтру с отклонениями
            report.append("ДЕТАЛИ ПО ФИЛЬТРАМ С ОТКЛОНЕНИЯМИ:")
            report.append("")
            
            for filter_type, total, passed, failed in filter_data:
                if failed and failed > 0:
                    report.append(f"📊 {filter_type} (отклонено: {failed} из {total}):")
                    
                    cursor.execute('''
                        SELECT symbol, reason, COUNT(*) as count
                        FROM filter_checks 
                        WHERE filter_type = ? AND passed = 0 AND created_at >= ?
                        GROUP BY symbol, reason
                        ORDER BY count DESC
                        LIMIT 10
                    ''', (filter_type, since))
                    
                    details = cursor.fetchall()
                    if details:
                        for sym, reason, count in details:
                            report.append(f"   - {sym}: {reason} ({count} раз)")
                    else:
                        report.append(f"   (нет деталей)")
                    
                    report.append("")
        else:
            report.append("⚠️ Нет данных в filter_checks за указанный период")
            report.append("")
            
    except Exception as e:
        report.append(f"⚠️ Ошибка при получении статистики фильтров: {e}")
        report.append("")
    
    # 3. Анализ качества сигналов
    report.append("=" * 80)
    report.append("3. АНАЛИЗ КАЧЕСТВА СИГНАЛОВ")
    report.append("=" * 80)
    report.append("")
    
    try:
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                AVG(quality_score) as avg_score,
                MIN(quality_score) as min_score,
                MAX(quality_score) as max_score,
                COUNT(CASE WHEN quality_score >= 80 THEN 1 END) as high_quality,
                COUNT(CASE WHEN quality_score >= 50 AND quality_score < 80 THEN 1 END) as medium_quality,
                COUNT(CASE WHEN quality_score < 50 THEN 1 END) as low_quality
            FROM signals_log 
            WHERE created_at >= ? AND quality_score IS NOT NULL
        ''', (since,))
        
        row = cursor.fetchone()
        if row and row[0] and row[0] > 0:
            total, avg, min_s, max_s, high, medium, low = row
            report.append(f"Всего сигналов с оценкой качества: {total}")
            report.append(f"Средний Score: {avg:.2f}")
            report.append(f"Min Score: {min_s:.2f}, Max Score: {max_s:.2f}")
            report.append(f"Высокое качество (>=80): {high} ({high*100/total:.1f}%)")
            report.append(f"Среднее качество (50-79): {medium} ({medium*100/total:.1f}%)")
            report.append(f"Низкое качество (<50): {low} ({low*100/total:.1f}%)")
        else:
            report.append("⚠️ Нет данных о качестве сигналов")
        report.append("")
        
    except Exception as e:
        report.append(f"⚠️ Ошибка при анализе качества: {e}")
        report.append("")
    
    conn.close()
    
    return "\n".join(report)

if __name__ == "__main__":
    report = generate_full_report(hours=24)
    print(report)
    
    # Сохраняем в файл
    from pathlib import Path
    report_file = Path("scripts/reports/full_signal_report.md")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report, encoding='utf-8')
    print(f"\n✅ Отчет сохранен в {report_file}")

