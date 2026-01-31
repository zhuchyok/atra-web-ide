#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Анализ времени и условий для повышения Win Rate
Исключение худших периодов торговли

Ответственный: Максим (Data Analyst)
"""

import logging
import sqlite3
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)


class TimeAnalysis:
    """
    Анализ Win Rate по времени и условиям
    
    Мировая практика: исключение худших периодов торговли
    """
    
    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
        self.worst_hours = set()  # Часы с низким Win Rate
        self.worst_weekdays = set()  # Дни недели с низким Win Rate
        self.worst_regimes = set()  # Рыночные режимы с низким Win Rate
        # 🔧 Временно отключаем блокировку до накопления статистики
        self.enable_blocking = False  # Блокировка отключена до анализа данных
    
    def analyze_win_rate_by_time(self, days: int = 30) -> Dict[str, Any]:
        """
        Анализирует Win Rate по времени
        
        Ответственный: Максим (Data Analyst)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            since = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Получаем закрытые сделки
            query = """
                SELECT 
                    exit_time,
                    result,
                    net_profit,
                    symbol
                FROM signals_log
                WHERE exit_time IS NOT NULL
                  AND exit_time >= ?
                  AND result IS NOT NULL
            """
            
            cursor.execute(query, (since.isoformat(),))
            rows = cursor.fetchall()
            
            # 🔧 ИСПРАВЛЕНО: Улучшенная обработка отсутствия данных
            if not rows:
                logger.info(f"📊 [TimeAnalysis] Нет данных за последние {days} дней (ожидаемо для новой системы)")
                return {
                    'error': 'No data',
                    'message': f'Недостаточно данных для анализа (требуется минимум 30 закрытых сделок)',
                    'days_analyzed': days,
                    'total_trades': 0,
                    'hourly': {},
                    'weekday': {},
                    'worst_hours': [],
                    'worst_weekdays': [],
                    'recommendations': [
                        f'⚠️ Накопите минимум 30 закрытых сделок для анализа времени',
                        '💡 Блокировка по времени отключена до накопления данных'
                    ]
                }
            
            # Анализ по часам
            hourly_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pnl': 0.0})
            
            # Анализ по дням недели
            weekday_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pnl': 0.0})
            
            for row in rows:
                exit_time_str = row['exit_time']
                result = row['result']
                pnl = float(row['net_profit'] or 0)
                
                try:
                    exit_time = datetime.fromisoformat(exit_time_str)
                    if exit_time.tzinfo is None:
                        exit_time = exit_time.replace(tzinfo=timezone.utc)
                    
                    hour = exit_time.hour
                    weekday = exit_time.weekday()  # 0 = Monday, 6 = Sunday
                    
                    if pnl > 0:
                        hourly_stats[hour]['wins'] += 1
                        weekday_stats[weekday]['wins'] += 1
                    else:
                        hourly_stats[hour]['losses'] += 1
                        weekday_stats[weekday]['losses'] += 1
                    
                    hourly_stats[hour]['pnl'] += pnl
                    weekday_stats[weekday]['pnl'] += pnl
                except Exception as e:
                    logger.debug(f"Ошибка парсинга времени: {e}")
                    continue
            
            # Рассчитываем Win Rate
            hourly_wr = {}
            for hour, stats in hourly_stats.items():
                total = stats['wins'] + stats['losses']
                if total > 0:
                    wr = (stats['wins'] / total * 100)
                    hourly_wr[hour] = {
                        'win_rate': wr,
                        'total': total,
                        'pnl': stats['pnl']
                    }
            
            weekday_wr = {}
            for weekday, stats in weekday_stats.items():
                total = stats['wins'] + stats['losses']
                if total > 0:
                    wr = (stats['wins'] / total * 100)
                    weekday_wr[weekday] = {
                        'win_rate': wr,
                        'total': total,
                        'pnl': stats['pnl']
                    }
            
            # Определяем худшие периоды (Win Rate < 30%)
            worst_hours = [h for h, data in hourly_wr.items() if data['win_rate'] < 30 and data['total'] >= 3]
            worst_weekdays = [d for d, data in weekday_wr.items() if data['win_rate'] < 30 and data['total'] >= 3]
            
            self.worst_hours = set(worst_hours)
            self.worst_weekdays = set(worst_weekdays)
            
            # 🔧 ИСПРАВЛЕНО: Автоматическое включение блокировки при наличии данных
            if len(rows) >= 30:
                if not self.enable_blocking:
                    self.enable_blocking = True
                    logger.info(
                        f"✅ [TimeAnalysis] Блокировка по времени автоматически включена "
                        f"(найдено {len(rows)} сделок, худшие часы: {sorted(worst_hours)}, "
                        f"худшие дни: {sorted(worst_weekdays)})"
                    )
            else:
                if self.enable_blocking:
                    logger.info(
                        f"⚠️ [TimeAnalysis] Блокировка по времени отключена "
                        f"(недостаточно данных: {len(rows)}/30 сделок)"
                    )
                    self.enable_blocking = False
            
            conn.close()
            
            return {
                'hourly': hourly_wr,
                'weekday': weekday_wr,
                'worst_hours': worst_hours,
                'worst_weekdays': worst_weekdays,
                'total_trades': len(rows),
                'enable_blocking': self.enable_blocking,
                'recommendations': self._generate_recommendations(hourly_wr, weekday_wr)
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа времени: {e}", exc_info=True)
            return {'error': str(e)}
    
    def _generate_recommendations(
        self,
        hourly_wr: Dict[int, Dict[str, Any]],
        weekday_wr: Dict[int, Dict[str, Any]]
    ) -> List[str]:
        """Генерирует рекомендации на основе анализа"""
        recommendations = []
        
        if self.worst_hours:
            recommendations.append(
                f"⚠️ Избегать торговли в часы: {sorted(self.worst_hours)} (Win Rate < 30%)"
            )
        
        if self.worst_weekdays:
            weekday_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            worst_names = [weekday_names[d] for d in sorted(self.worst_weekdays)]
            recommendations.append(
                f"⚠️ Избегать торговли в дни: {', '.join(worst_names)} (Win Rate < 30%)"
            )
        
        return recommendations
    
    def should_trade_now(self, current_time: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Проверяет, можно ли торговать сейчас
        
        Returns:
            (allowed, reason)
        """
        # 🔧 Временно отключаем блокировку до накопления статистики
        if not self.enable_blocking:
            return True, "OK (блокировка отключена до анализа данных)"
        
        if current_time is None:
            from src.shared.utils.datetime_utils import get_utc_now
            current_time = get_utc_now()
        
        hour = current_time.hour
        weekday = current_time.weekday()
        
        if hour in self.worst_hours:
            return False, f"Час {hour}:00 имеет низкий Win Rate"
        
        if weekday in self.worst_weekdays:
            weekday_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            return False, f"{weekday_names[weekday]} имеет низкий Win Rate"
        
        return True, "OK"


# Singleton instance
_time_analysis_instance: Optional[TimeAnalysis] = None


def get_time_analysis(db_path: str = "trading.db") -> TimeAnalysis:
    """Получить экземпляр анализа времени"""
    global _time_analysis_instance
    if _time_analysis_instance is None:
        _time_analysis_instance = TimeAnalysis(db_path)
    return _time_analysis_instance

