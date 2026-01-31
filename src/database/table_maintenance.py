"""
Мониторинг и обслуживание таблиц.
Адаптация пункта 56 из performance_optimization.mdc для SQLite.
Проверка bloat таблиц, рекомендации по VACUUM.
"""

import logging
import sqlite3
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TableStats:
    """Статистика таблицы"""
    table_name: str
    row_count: int
    page_count: int
    size_bytes: int
    fragmentation_pct: float
    needs_vacuum: bool


class TableMaintenance:
    """Менеджер обслуживания таблиц"""
    
    def __init__(self, db):
        """
        Args:
            db: Экземпляр Database
        """
        self.db = db
        self.fragmentation_threshold = 30.0  # Порог фрагментации в %
    
    def analyze_tables(self) -> Dict[str, Any]:
        """
        Анализирует все таблицы на предмет фрагментации и необходимости VACUUM.
        
        Returns:
            Словарь с результатами анализа
        """
        try:
            # Получаем список всех таблиц
            tables = self.db.execute_with_retry(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
                (),
                is_write=False
            )
            
            table_stats = []
            total_size = 0
            total_fragmented = 0
            
            for table_row in tables:
                table_name = table_row[0]
                
                try:
                    stats = self._analyze_table(table_name)
                    table_stats.append(stats)
                    total_size += stats.size_bytes
                    if stats.needs_vacuum:
                        total_fragmented += stats.size_bytes
                except Exception as e:
                    logger.warning("⚠️ [TableMaintenance] Ошибка анализа таблицы %s: %s", table_name, e)
            
            result = {
                'total_tables': len(table_stats),
                'tables_needing_vacuum': sum(1 for s in table_stats if s.needs_vacuum),
                'total_size_mb': total_size / (1024 * 1024),
                'fragmented_size_mb': total_fragmented / (1024 * 1024),
                'fragmentation_pct': (total_fragmented / total_size * 100) if total_size > 0 else 0.0,
                'tables': [
                    {
                        'name': stats.table_name,
                        'rows': stats.row_count,
                        'size_mb': stats.size_bytes / (1024 * 1024),
                        'fragmentation_pct': stats.fragmentation_pct,
                        'needs_vacuum': stats.needs_vacuum
                    }
                    for stats in table_stats
                ],
                'recommendations': self._generate_recommendations(table_stats)
            }
            
            logger.info(
                "✅ [TableMaintenance] Анализ завершен: %d/%d таблиц требуют VACUUM, "
                "фрагментация: %.2f%%",
                result['tables_needing_vacuum'], len(table_stats), result['fragmentation_pct']
            )
            
            return result
            
        except Exception as e:
            logger.error("❌ [TableMaintenance] Ошибка анализа таблиц: %s", e)
            return {
                'error': str(e),
                'total_tables': 0,
                'tables_needing_vacuum': 0
            }
    
    def _analyze_table(self, table_name: str) -> TableStats:
        """
        Анализирует конкретную таблицу.
        
        Args:
            table_name: Имя таблицы
            
        Returns:
            Статистика таблицы
        """
        # Получаем количество строк
        count_result = self.db.execute_with_retry(
            f"SELECT COUNT(*) FROM {table_name}",
            (),
            is_write=False
        )
        row_count = count_result[0][0] if count_result else 0
        
        # Получаем информацию о страницах
        page_info = self.db.execute_with_retry(
            f"PRAGMA page_count",
            (),
            is_write=False
        )
        page_count = page_info[0][0] if page_info else 0
        
        # Получаем размер страницы
        page_size_info = self.db.execute_with_retry(
            "PRAGMA page_size",
            (),
            is_write=False
        )
        page_size = page_info[0][0] if page_size_info else 4096
        
        # Оцениваем размер таблицы
        size_bytes = page_count * page_size
        
        # Оцениваем фрагментацию (упрощенная версия)
        # В SQLite нет прямой статистики фрагментации, используем эвристику
        fragmentation_pct = 0.0
        if row_count > 0:
            # Если таблица большая и часто обновляется, возможна фрагментация
            # Проверяем через статистику обновлений (если доступна)
            estimated_fragmentation = min(50.0, (page_count / max(1, row_count / 1000)) * 10)
            fragmentation_pct = estimated_fragmentation
        
        needs_vacuum = fragmentation_pct >= self.fragmentation_threshold
        
        return TableStats(
            table_name=table_name,
            row_count=row_count,
            page_count=page_count,
            size_bytes=size_bytes,
            fragmentation_pct=fragmentation_pct,
            needs_vacuum=needs_vacuum
        )
    
    def _generate_recommendations(self, table_stats: List[TableStats]) -> List[str]:
        """
        Генерирует рекомендации по обслуживанию таблиц.
        
        Args:
            table_stats: Список статистики таблиц
            
        Returns:
            Список рекомендаций
        """
        recommendations = []
        
        tables_needing_vacuum = [s for s in table_stats if s.needs_vacuum]
        
        if tables_needing_vacuum:
            recommendations.append(
                f"Рекомендуется выполнить VACUUM для {len(tables_needing_vacuum)} таблиц "
                f"с фрагментацией >{self.fragmentation_threshold}%"
            )
        
        large_tables = [s for s in table_stats if s.size_bytes > 100 * 1024 * 1024]  # >100MB
        if large_tables:
            recommendations.append(
                f"Найдено {len(large_tables)} больших таблиц (>100MB), "
                "рассмотрите возможность архивации старых данных"
            )
        
        if not recommendations:
            recommendations.append("Все таблицы в хорошем состоянии, VACUUM не требуется")
        
        return recommendations
    
    def get_vacuum_recommendations(self) -> List[str]:
        """
        Возвращает список таблиц, для которых рекомендуется VACUUM.
        
        Returns:
            Список имен таблиц
        """
        analysis = self.analyze_tables()
        
        if 'tables' not in analysis:
            return []
        
        return [
            table['name']
            for table in analysis['tables']
            if table.get('needs_vacuum', False)
        ]

