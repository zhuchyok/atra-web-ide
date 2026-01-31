"""
Агрессивные оптимизации для массовых операций.
Объединяет множественные запросы в batch для максимального ускорения.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def bulk_insert_signals_optimized(db, signals: List[Dict[str, Any]], batch_size: int = 1000) -> int:
    """
    Оптимизированная массовая вставка сигналов
    Использует executemany_optimized для максимальной скорости
    
    Args:
        db: Экземпляр Database
        signals: Список сигналов для вставки
        batch_size: Размер батча
        
    Returns:
        Количество вставленных записей
    """
    if not signals:
        return 0
    
    try:
        # Подготавливаем данные для batch вставки
        query = """
            INSERT INTO signals (ts, exchange, symbol, rsi, ema_fast, ema_slow, price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        params_list = [
            (
                signal.get('ts'),
                signal.get('exchange'),
                signal.get('symbol'),
                signal.get('rsi'),
                signal.get('ema_fast'),
                signal.get('ema_slow'),
                signal.get('price')
            )
            for signal in signals
        ]
        
        # Разбиваем на батчи для избежания переполнения
        total_inserted = 0
        for i in range(0, len(params_list), batch_size):
            batch = params_list[i:i + batch_size]
            if db.executemany_optimized(query, batch):
                total_inserted += len(batch)
        
        return total_inserted
        
    except Exception as e:
        logger.error("Ошибка массовой вставки сигналов: %s", e)
        return 0


def bulk_insert_signals_log_optimized(db, logs: List[Dict[str, Any]], batch_size: int = 500) -> int:
    """
    Оптимизированная массовая вставка логов сигналов
    Использует executemany_optimized для максимальной скорости
    
    Args:
        db: Экземпляр Database
        logs: Список логов для вставки
        batch_size: Размер батча
        
    Returns:
        Количество вставленных записей
    """
    if not logs:
        return 0
    
    try:
        # Определяем колонки из первого элемента
        first_log = logs[0]
        columns = [k for k in first_log.keys() if first_log[k] is not None]
        
        # Исключаем None значения и формируем запрос
        query = f"""
            INSERT INTO signals_log ({', '.join(columns)})
            VALUES ({', '.join(['?'] * len(columns))})
        """
        
        # Подготавливаем параметры
        params_list = [
            tuple(log.get(col) for col in columns)
            for log in logs
        ]
        
        # Разбиваем на батчи
        total_inserted = 0
        for i in range(0, len(params_list), batch_size):
            batch = params_list[i:i + batch_size]
            if db.executemany_optimized(query, batch):
                total_inserted += len(batch)
        
        return total_inserted
        
    except Exception as e:
        logger.error("Ошибка массовой вставки логов сигналов: %s", e)
        return 0


def bulk_update_user_data_optimized(db, user_data_dict: Dict[str, Dict[str, Any]]) -> int:
    """
    Оптимизированное массовое обновление данных пользователей
    Использует batch операции для максимальной скорости
    
    Args:
        db: Экземпляр Database
        user_data_dict: Словарь {user_id: data}
        
    Returns:
        Количество обновленных записей
    """
    if not user_data_dict:
        return 0
    
    try:
        # Используем быструю сериализацию
        try:
            from src.data.serialization import serialize_fast
            import base64
            use_msgpack = True
        except ImportError:
            use_msgpack = False
            import json
        
        # Подготавливаем batch операции
        queries = []
        for user_id, data in user_data_dict.items():
            try:
                if use_msgpack:
                    data_serialized = serialize_fast(data)
                    data_json = base64.b64encode(data_serialized).decode('utf-8')
                else:
                    data_json = json.dumps(data, ensure_ascii=False)
                
                query = """
                    INSERT INTO users_data (user_id, data, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated_at=CURRENT_TIMESTAMP
                """
                queries.append((query, (str(user_id), data_json)))
            except Exception as e:
                logger.warning("Ошибка сериализации данных пользователя %s: %s", user_id, e)
                continue
        
        # Выполняем batch операции
        if queries:
            db.execute_batch(queries, is_write=True)
            return len(queries)
        
        return 0
        
    except Exception as e:
        logger.error("Ошибка массового обновления данных пользователей: %s", e)
        return 0

