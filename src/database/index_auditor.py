"""
Аудит индексов для выявления неиспользуемых индексов.
Адаптация пункта 17 из performance_optimization.mdc для SQLite.
"""

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class IndexUsage:
    """Использование индекса"""

    index_name: str
    table_name: str
    sql: str
    size_estimate: int  # Примерный размер в байтах
    is_used: bool = False
    usage_count: int = 0


class IndexAuditor:
    """Аудитор индексов для SQLite"""

    def __init__(self, db):
        """
        Args:
            db: Экземпляр Database
        """
        self.db = db

    def list_indexes(self) -> List[str]:
        """
        Возвращает список всех индексов в базе данных.

        Returns:
            Список имен индексов
        """
        try:
            indexes = self.db.execute_with_retry(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """,
                (),
                is_write=False,
            )
            return [row[0] for row in indexes] if indexes else []
        except Exception as e:
            logger.warning("⚠️ [IndexAuditor] Ошибка получения списка индексов: %s", e)
            return []

    def audit_indexes(self) -> Dict[str, Any]:
        """
        Проводит аудит всех индексов в базе данных.

        Returns:
            Словарь с результатами аудита
        """
        try:
            # Получаем все индексы
            indexes = self.db.execute_with_retry(
                """
                SELECT name, tbl_name, sql
                FROM sqlite_master
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
                ORDER BY tbl_name, name
                """,
                (),
                is_write=False,
            )

            index_usage = []
            total_size = 0

            for index_row in indexes:
                index_name, table_name, index_sql = index_row

                # Оцениваем размер индекса (приблизительно)
                size_estimate = self._estimate_index_size(table_name, index_name)
                total_size += size_estimate

                # Проверяем использование индекса
                # В SQLite нет pg_stat_user_indexes, но можно проверить через EXPLAIN
                is_used = self._check_index_usage(index_name, table_name)

                index_usage.append(
                    IndexUsage(
                        index_name=index_name,
                        table_name=table_name,
                        sql=index_sql or "",
                        size_estimate=size_estimate,
                        is_used=is_used,
                    )
                )

            # Анализируем результаты
            unused_indexes = [idx for idx in index_usage if not idx.is_used]
            used_indexes = [idx for idx in index_usage if idx.is_used]

            result = {
                "total_indexes": len(index_usage),
                "used_indexes": len(used_indexes),
                "unused_indexes": len(unused_indexes),
                "total_size_mb": total_size / (1024 * 1024),
                "unused_size_mb": sum(idx.size_estimate for idx in unused_indexes) / (1024 * 1024),
                "indexes": [
                    {
                        "name": idx.index_name,
                        "table": idx.table_name,
                        "size_mb": idx.size_estimate / (1024 * 1024),
                        "used": idx.is_used,
                    }
                    for idx in index_usage
                ],
                "unused_indexes_list": [
                    {
                        "name": idx.index_name,
                        "table": idx.table_name,
                        "size_mb": idx.size_estimate / (1024 * 1024),
                    }
                    for idx in unused_indexes
                ],
            }

            logger.info(
                "✅ [IndexAuditor] Аудит завершен: %d/%d индексов используются, "
                "неиспользуемые: %.2f MB",
                len(used_indexes),
                len(index_usage),
                result["unused_size_mb"],
            )

            return result

        except Exception as e:
            logger.error("❌ [IndexAuditor] Ошибка аудита индексов: %s", e)
            return {"error": str(e), "total_indexes": 0, "used_indexes": 0, "unused_indexes": 0}

    def _estimate_index_size(self, table_name: str, index_name: str) -> int:
        """
        Оценивает размер индекса (приблизительно).

        Args:
            table_name: Имя таблицы
            index_name: Имя индекса

        Returns:
            Примерный размер в байтах
        """
        try:
            # Получаем количество строк в таблице
            count_result = self.db.execute_with_retry(
                f"SELECT COUNT(*) FROM {table_name}", (), is_write=False
            )

            if not count_result:
                return 0

            row_count = count_result[0][0]

            # Оцениваем размер индекса (примерно 50 байт на строку для простого индекса)
            estimated_size = row_count * 50

            return estimated_size

        except Exception:
            return 0

    def _check_index_usage(self, index_name: str, table_name: str) -> bool:
        """
        Проверяет использование индекса через анализ типичных запросов.

        Args:
            index_name: Имя индекса
            table_name: Имя таблицы

        Returns:
            True если индекс вероятно используется
        """
        try:
            # Получаем структуру индекса
            index_info = self.db.execute_with_retry(
                f"PRAGMA index_info({index_name})", (), is_write=False
            )

            if not index_info:
                return False

            # Извлекаем колонки индекса
            indexed_columns = [row[2] for row in index_info]

            # Проверяем, используются ли эти колонки в типичных запросах
            # (это эвристика, так как SQLite не предоставляет статистику использования)

            # Если индекс на часто используемых колонках (symbol, ts, created_at), считаем используемым
            common_columns = ["symbol", "ts", "created_at", "entry_time", "user_id", "status"]

            if any(col in indexed_columns for col in common_columns):
                return True

            # Если это уникальный индекс или первичный ключ, считаем используемым
            if "UNIQUE" in index_name.upper() or "PRIMARY" in index_name.upper():
                return True

            # Если индекс на внешнем ключе, считаем используемым
            if any("_id" in col.lower() for col in indexed_columns):
                return True

            return False

        except Exception:
            return False

    def suggest_index_removal(self, min_unused_size_mb: float = 10.0) -> List[str]:
        """
        Предлагает индексы для удаления на основе аудита.

        Args:
            min_unused_size_mb: Минимальный размер неиспользуемых индексов для предложения

        Returns:
            Список имен индексов, которые можно удалить
        """
        audit_result = self.audit_indexes()

        if "unused_indexes_list" not in audit_result:
            return []

        suggestions = []
        total_unused_size = 0.0

        for idx_info in audit_result["unused_indexes_list"]:
            if idx_info["size_mb"] >= 1.0:  # Предлагаем удалить только индексы > 1MB
                suggestions.append(idx_info["name"])
                total_unused_size += idx_info["size_mb"]

        if total_unused_size >= min_unused_size_mb:
            logger.info(
                "💡 [IndexAuditor] Предложено удалить %d индексов (%.2f MB)",
                len(suggestions),
                total_unused_size,
            )
            return suggestions

        return []
