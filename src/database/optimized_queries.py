"""
Оптимизированные запросы для часто используемых операций.
Объединяет множественные запросы в один для снижения latency.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_signals_with_stats_optimized(db, symbol: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Оптимизированный запрос для получения сигналов со статистикой
    Объединяет несколько запросов в один для ускорения
    
    Args:
        db: Экземпляр Database
        symbol: Фильтр по символу (опционально)
        limit: Лимит записей
        
    Returns:
        Список сигналов со статистикой
    """
    try:
        with db._lock:
            # Один запрос вместо нескольких
            if symbol:
                query = """
                    SELECT 
                        s.*,
                        COUNT(DISTINCT sl.id) as total_executions,
                        AVG(sl.net_profit) as avg_profit,
                        SUM(CASE WHEN sl.result LIKE 'TP%' THEN 1 ELSE 0 END) as tp_count,
                        SUM(CASE WHEN sl.result LIKE 'SL%' THEN 1 ELSE 0 END) as sl_count
                    FROM signals s
                    LEFT JOIN signals_log sl ON s.symbol = sl.symbol AND s.ts = sl.entry_time
                    WHERE s.symbol = ?
                    GROUP BY s.id
                    ORDER BY s.ts DESC
                    LIMIT ?
                """
                params = (symbol, limit)
            else:
                query = """
                    SELECT 
                        s.*,
                        COUNT(DISTINCT sl.id) as total_executions,
                        AVG(sl.net_profit) as avg_profit,
                        SUM(CASE WHEN sl.result LIKE 'TP%' THEN 1 ELSE 0 END) as tp_count,
                        SUM(CASE WHEN sl.result LIKE 'SL%' THEN 1 ELSE 0 END) as sl_count
                    FROM signals s
                    LEFT JOIN signals_log sl ON s.symbol = sl.symbol AND s.ts = sl.entry_time
                    GROUP BY s.id
                    ORDER BY s.ts DESC
                    LIMIT ?
                """
                params = (limit,)
            
            cursor = db.conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            # Преобразуем в список словарей
            result = [dict(zip(columns, row)) for row in rows]
            return result
            
    except Exception as e:
        logger.error("Ошибка оптимизированного запроса сигналов: %s", e)
        return []


def get_user_performance_batch(db, user_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Оптимизированный batch запрос для получения статистики нескольких пользователей
    Один запрос вместо N запросов
    
    Args:
        db: Экземпляр Database
        user_ids: Список ID пользователей
        
    Returns:
        Словарь {user_id: статистика}
    """
    if not user_ids:
        return {}
    
    try:
        with db._lock:
            # Создаем плейсхолдеры для IN clause
            placeholders = ','.join('?' * len(user_ids))
            
            query = f"""
                SELECT 
                    user_id,
                    COUNT(*) as total_signals,
                    SUM(CASE WHEN result LIKE 'TP%' THEN 1 ELSE 0 END) as tp_count,
                    SUM(CASE WHEN result LIKE 'SL%' THEN 1 ELSE 0 END) as sl_count,
                    SUM(net_profit) as total_profit,
                    AVG(net_profit) as avg_profit
                FROM signals_log
                WHERE user_id IN ({placeholders})
                GROUP BY user_id
            """
            
            cursor = db.conn.execute(query, tuple(user_ids))
            rows = cursor.fetchall()
            
            # Преобразуем в словарь
            result = {}
            for row in rows:
                user_id, total, tp, sl, total_profit, avg_profit = row
                result[user_id] = {
                    'total_signals': total or 0,
                    'tp_count': tp or 0,
                    'sl_count': sl or 0,
                    'total_profit': float(total_profit) if total_profit else 0.0,
                    'avg_profit': float(avg_profit) if avg_profit else 0.0,
                    'winrate': ((tp or 0) / (total or 1)) * 100.0
                }
            
            # Добавляем пустые записи для пользователей без данных
            for user_id in user_ids:
                if user_id not in result:
                    result[user_id] = {
                        'total_signals': 0,
                        'tp_count': 0,
                        'sl_count': 0,
                        'total_profit': 0.0,
                        'avg_profit': 0.0,
                        'winrate': 0.0
                    }
            
            return result
            
    except Exception as e:
        logger.error("Ошибка batch запроса статистики пользователей: %s", e)
        return {user_id: {} for user_id in user_ids}

