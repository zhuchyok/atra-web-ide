"""
Оптимизация порядка столбцов в таблицах.
Адаптация пункта 19 из performance_optimization.mdc.
Оптимизация выравнивания для уменьшения размера строк.
"""

import logging
import sqlite3
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ColumnOrderOptimizer:
    """Оптимизатор порядка столбцов"""
    
    # Типы данных с их размерами (для SQLite)
    TYPE_SIZES = {
        'INTEGER': 8,
        'REAL': 8,
        'TEXT': 0,  # Переменный размер
        'BLOB': 0,  # Переменный размер
        'DATETIME': 0,  # Обычно TEXT
        'BOOLEAN': 1,
    }
    
    @staticmethod
    def optimize_column_order(table_name: str, columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Оптимизирует порядок столбцов для лучшего выравнивания.
        
        Правило: фиксированная длина перед переменной.
        
        Args:
            table_name: Имя таблицы
            columns: Список колонок с информацией о типе
            
        Returns:
            Оптимизированный порядок колонок
        """
        # Разделяем колонки на фиксированные и переменные
        fixed_size_columns = []
        variable_size_columns = []
        
        for col in columns:
            col_type = col.get('type', '').upper()
            if col_type in ['INTEGER', 'REAL', 'BOOLEAN']:
                fixed_size_columns.append(col)
            else:
                variable_size_columns.append(col)
        
        # Сортируем фиксированные по размеру (большие первыми для лучшего выравнивания)
        fixed_size_columns.sort(
            key=lambda x: ColumnOrderOptimizer.TYPE_SIZES.get(x.get('type', '').upper(), 0),
            reverse=True
        )
        
        # Оптимизированный порядок: фиксированные, затем переменные
        optimized = fixed_size_columns + variable_size_columns
        
        logger.debug(
            "✅ [ColumnOrderOptimizer] Оптимизирован порядок колонок для %s: "
            "%d фиксированных, %d переменных",
            table_name, len(fixed_size_columns), len(variable_size_columns)
        )
        
        return optimized
    
    @staticmethod
    def analyze_table_column_order(db, table_name: str) -> Dict[str, Any]:
        """
        Анализирует текущий порядок колонок в таблице.
        
        Args:
            db: Экземпляр Database
            table_name: Имя таблицы
            
        Returns:
            Словарь с анализом
        """
        try:
            # Получаем информацию о колонках
            columns_info = db.execute_with_retry(
                f"PRAGMA table_info({table_name})",
                (),
                is_write=False
            )
            
            if not columns_info:
                return {'error': f'Таблица {table_name} не найдена'}
            
            columns = []
            for col_info in columns_info:
                columns.append({
                    'name': col_info[1],
                    'type': col_info[2],
                    'not_null': col_info[3],
                    'default_value': col_info[4],
                    'primary_key': col_info[5]
                })
            
            # Анализируем текущий порядок
            fixed_count = sum(
                1 for col in columns
                if col['type'].upper() in ['INTEGER', 'REAL', 'BOOLEAN']
            )
            variable_count = len(columns) - fixed_count
            
            # Проверяем, оптимизирован ли порядок
            is_optimized = True
            first_variable_idx = None
            
            for i, col in enumerate(columns):
                if col['type'].upper() not in ['INTEGER', 'REAL', 'BOOLEAN']:
                    if first_variable_idx is None:
                        first_variable_idx = i
                elif first_variable_idx is not None:
                    # Нашли фиксированную колонку после переменной - не оптимизировано
                    is_optimized = False
                    break
            
            # Предлагаем оптимизированный порядок
            optimized_order = ColumnOrderOptimizer.optimize_column_order(table_name, columns)
            
            return {
                'table_name': table_name,
                'total_columns': len(columns),
                'fixed_size_columns': fixed_count,
                'variable_size_columns': variable_count,
                'is_optimized': is_optimized,
                'current_order': [col['name'] for col in columns],
                'optimized_order': [col['name'] for col in optimized_order],
                'needs_reorder': not is_optimized
            }
            
        except Exception as e:
            logger.error("❌ [ColumnOrderOptimizer] Ошибка анализа таблицы %s: %s", table_name, e)
            return {'error': str(e)}

