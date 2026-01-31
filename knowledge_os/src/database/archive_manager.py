"""
Менеджер архивации старых данных.
Перемещает данные старше указанного периода в архивные таблицы.
Снижает размер активной БД на 30-80%.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from typing import Optional, Dict, Any, List
import time

logger = logging.getLogger(__name__)


class ArchiveManager:
    """Менеджер архивации данных"""
    
    def __init__(self, db):
        """
        Args:
            db: Экземпляр Database
        """
        self.db = db
        self.archive_retention_days = 730  # 2 года по умолчанию
    
    def archive_old_data(
        self,
        table_name: str,
        date_column: str,
        archive_suffix: str = '_archive',
        retention_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Архивирует старые данные из таблицы.
        
        Args:
            table_name: Имя таблицы для архивации
            date_column: Колонка с датой для фильтрации
            archive_suffix: Суффикс для архивной таблицы
            retention_days: Количество дней для хранения (по умолчанию 730)
            
        Returns:
            Словарь с результатами архивации
        """
        retention_days = retention_days or self.archive_retention_days
        archive_table = f"{table_name}{archive_suffix}"
        cutoff_date = get_utc_now() - timedelta(days=retention_days)
        
        result = {
            'table': table_name,
            'archive_table': archive_table,
            'cutoff_date': cutoff_date.isoformat(),
            'archived_count': 0,
            'success': False,
            'error': None
        }
        
        try:
            with self.db._lock:
                # Проверяем существование таблицы
                table_exists = self.db.execute_with_retry(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                    is_write=False
                )
                
                if not table_exists:
                    result['error'] = f"Таблица {table_name} не существует"
                    return result
                
                # Создаем архивную таблицу если не существует
                self._create_archive_table(table_name, archive_table)
                
                # Подсчитываем количество записей для архивации
                count_query = f"""
                    SELECT COUNT(*) FROM {table_name}
                    WHERE datetime({date_column}) < datetime(?)
                """
                count_result = self.db.execute_with_retry(
                    count_query,
                    (cutoff_date.isoformat(),),
                    is_write=False
                )
                
                if not count_result or count_result[0][0] == 0:
                    result['success'] = True
                    logger.info("✅ [Archive] Нет данных для архивации в %s", table_name)
                    return result
                
                archived_count = count_result[0][0]
                
                # Копируем данные в архивную таблицу
                insert_query = f"""
                    INSERT INTO {archive_table}
                    SELECT * FROM {table_name}
                    WHERE datetime({date_column}) < datetime(?)
                """
                
                self.db.conn.execute(insert_query, (cutoff_date.isoformat(),))
                
                # Удаляем архивированные данные из основной таблицы
                delete_query = f"""
                    DELETE FROM {table_name}
                    WHERE datetime({date_column}) < datetime(?)
                """
                
                self.db.conn.execute(delete_query, (cutoff_date.isoformat(),))
                self.db.conn.commit()
                
                result['archived_count'] = archived_count
                result['success'] = True
                
                logger.info(
                    "✅ [Archive] Архивировано %d записей из %s в %s",
                    archived_count, table_name, archive_table
                )
                
        except sqlite3.Error as e:
            result['error'] = str(e)
            logger.error("❌ [Archive] Ошибка архивации %s: %s", table_name, e)
            if self.db.conn:
                self.db.conn.rollback()
        
        return result
    
    def _create_archive_table(self, source_table: str, archive_table: str):
        """Создает архивную таблицу на основе структуры исходной таблицы"""
        try:
            # Получаем структуру исходной таблицы
            schema = self.db.execute_with_retry(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (source_table,),
                is_write=False
            )
            
            if not schema or not schema[0][0]:
                raise ValueError(f"Не удалось получить схему таблицы {source_table}")
            
            create_sql = schema[0][0]
            
            # Заменяем имя таблицы на архивное
            create_sql = create_sql.replace(
                f"CREATE TABLE {source_table}",
                f"CREATE TABLE IF NOT EXISTS {archive_table}"
            ).replace(
                f"CREATE TABLE IF NOT EXISTS {source_table}",
                f"CREATE TABLE IF NOT EXISTS {archive_table}"
            )
            
            # Создаем архивную таблицу
            self.db.conn.execute(create_sql)
            self.db.conn.commit()
            
            logger.debug("✅ [Archive] Создана архивная таблица %s", archive_table)
            
        except sqlite3.Error as e:
            logger.warning("⚠️ [Archive] Ошибка создания архивной таблицы %s: %s", archive_table, e)
            raise
    
    def archive_all_tables(self, retention_days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Архивирует все таблицы с временными метками.
        
        Args:
            retention_days: Количество дней для хранения
            
        Returns:
            Список результатов архивации для каждой таблицы
        """
        # Таблицы для архивации: (table_name, date_column)
        tables_to_archive = [
            ('signals_log', 'created_at'),
            ('trades', 'created_at'),
            ('signals', 'ts'),
            ('active_signals', 'ts'),
            ('quotes', 'ts'),
            ('arbitrage_events', 'ts'),
        ]
        
        results = []
        
        for table_name, date_column in tables_to_archive:
            try:
                result = self.archive_old_data(
                    table_name=table_name,
                    date_column=date_column,
                    retention_days=retention_days
                )
                results.append(result)
                
                # Небольшая задержка между таблицами
                time.sleep(0.1)
                
            except Exception as e:
                logger.error("❌ [Archive] Ошибка архивации %s: %s", table_name, e)
                results.append({
                    'table': table_name,
                    'success': False,
                    'error': str(e)
                })
        
        # Подсчитываем статистику
        total_archived = sum(r.get('archived_count', 0) for r in results)
        successful = sum(1 for r in results if r.get('success', False))
        
        logger.info(
            "✅ [Archive] Архивация завершена: %d/%d таблиц, всего записей: %d",
            successful, len(tables_to_archive), total_archived
        )
        
        return results
    
    def get_archive_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику по архивированным данным.
        
        Returns:
            Словарь со статистикой
        """
        stats = {
            'archive_tables': [],
            'total_archived_records': 0,
            'active_db_size_mb': 0,
            'archive_db_size_mb': 0
        }
        
        try:
            # Находим все архивные таблицы
            archive_tables = self.db.execute_with_retry(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_archive'",
                (),
                is_write=False
            )
            
            for table_row in archive_tables:
                table_name = table_row[0]
                stats['archive_tables'].append(table_name)
                
                # Подсчитываем количество записей
                count_result = self.db.execute_with_retry(
                    f"SELECT COUNT(*) FROM {table_name}",
                    (),
                    is_write=False
                )
                
                if count_result:
                    count = count_result[0][0]
                    stats['total_archived_records'] += count
            
            # Размер БД (приблизительно)
            try:
                import os
                db_path = self.db.db_path
                if os.path.exists(db_path):
                    stats['active_db_size_mb'] = os.path.getsize(db_path) / (1024 * 1024)
            except Exception:
                pass
            
        except Exception as e:
            logger.warning("⚠️ [Archive] Ошибка получения статистики: %s", e)
        
        return stats

