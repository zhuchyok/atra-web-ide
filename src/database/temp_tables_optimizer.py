"""
Временные таблицы для сложных запросов.
Адаптация пункта 52 из performance_optimization.mdc.
Разделение сложных запросов на простые части с временными таблицами.
"""

import logging
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TempTablesOptimizer:
    """Оптимизатор сложных запросов через временные таблицы"""

    def __init__(self, db):
        """
        Args:
            db: Экземпляр Database
        """
        self.db = db
        self.temp_tables: List[str] = []

    def optimize_complex_query(
        self, complex_query: str, temp_table_prefix: str = "temp_opt"
    ) -> Tuple[str, List[str]]:
        """
        Оптимизирует сложный запрос через временные таблицы.

        Args:
            complex_query: Сложный SQL запрос
            temp_table_prefix: Префикс для временных таблиц

        Returns:
            Кортеж (оптимизированный запрос, список временных таблиц)
        """
        # Это упрощенная версия - в реальности нужен парсинг SQL
        # Для примера разбиваем запросы с множественными JOIN

        import re

        # Проверяем сложность запроса
        join_count = len(re.findall(r"\bJOIN\b", complex_query, re.IGNORECASE))
        subquery_count = len(re.findall(r"\(SELECT", complex_query, re.IGNORECASE))

        if join_count <= 2 and subquery_count == 0:
            # Простой запрос - не оптимизируем
            return complex_query, []

        # Для сложных запросов создаем временные таблицы
        # (это упрощенная версия, полная реализация требует парсинга SQL)

        logger.debug(
            "🔧 [TempTablesOptimizer] Оптимизация сложного запроса (JOIN: %d, подзапросы: %d)",
            join_count,
            subquery_count,
        )

        # В реальности здесь был бы парсинг и разбиение запроса
        # Пока возвращаем исходный запрос
        return complex_query, []

    def create_temp_table(
        self, table_name: str, create_sql: str, data_query: Optional[str] = None
    ) -> bool:
        """
        Создает временную таблицу и заполняет данными.

        Args:
            table_name: Имя временной таблицы
            create_sql: SQL для создания таблицы
            data_query: SQL запрос для заполнения данными

        Returns:
            True при успехе
        """
        try:
            # Создаем временную таблицу
            self.db.execute_with_retry(create_sql, (), is_write=True)

            # Заполняем данными если указан запрос
            if data_query:
                self.db.execute_with_retry(data_query, (), is_write=True)

            self.temp_tables.append(table_name)

            logger.debug("✅ [TempTablesOptimizer] Создана временная таблица %s", table_name)
            return True

        except Exception as e:
            logger.error(
                "❌ [TempTablesOptimizer] Ошибка создания временной таблицы %s: %s", table_name, e
            )
            return False

    def cleanup_temp_tables(self):
        """Удаляет все созданные временные таблицы"""
        for table_name in self.temp_tables:
            try:
                self.db.execute_with_retry(f"DROP TABLE IF EXISTS {table_name}", (), is_write=True)
            except Exception as e:
                logger.warning(
                    "⚠️ [TempTablesOptimizer] Ошибка удаления таблицы %s: %s", table_name, e
                )

        self.temp_tables.clear()
        logger.debug("✅ [TempTablesOptimizer] Очищены временные таблицы")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - очистка временных таблиц"""
        self.cleanup_temp_tables()
