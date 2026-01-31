"""
Материализованные представления для агрегированных данных.
Адаптация пункта 15 из performance_optimization.mdc для SQLite.
Использует VIEW с кэшированием через таблицы для ускорения запросов.
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MaterializedView:
    """Материализованное представление"""
    view_name: str
    base_query: str
    refresh_interval_minutes: int
    last_refreshed: Optional[datetime] = None
    row_count: int = 0


class MaterializedViewManager:
    """Менеджер материализованных представлений"""
    
    def __init__(self, db):
        """
        Args:
            db: Экземпляр Database
        """
        self.db = db
        self.views: Dict[str, MaterializedView] = {}
    
    def create_materialized_view(
        self,
        view_name: str,
        base_query: str,
        refresh_interval_minutes: int = 60
    ) -> bool:
        """
        Создает материализованное представление.
        
        Args:
            view_name: Имя представления
            base_query: Базовый SQL запрос
            refresh_interval_minutes: Интервал обновления в минутах
            
        Returns:
            True при успехе
        """
        try:
            # Создаем таблицу для кэширования результатов
            cache_table = f"{view_name}_cache"
            
            # Выполняем запрос для получения структуры
            # Используем execute_with_retry без prepared statements для материализованных представлений
            sample_result = self.db.execute_with_retry(
                base_query + " LIMIT 1",
                (),
                is_write=False,
                use_prepared=False
            )
            
            if not sample_result:
                logger.warning("⚠️ [MaterializedView] Нет данных для создания представления %s", view_name)
                return False
            
            # Создаем таблицу кэша на основе структуры результата
            # (упрощенная версия, в реальности нужен более сложный парсинг)
            create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {cache_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT,
                    refreshed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            self.db.execute_with_retry(create_table_sql, (), is_write=True)
            
            # Создаем VIEW, который использует кэш
            view_sql = f"""
                CREATE VIEW IF NOT EXISTS {view_name} AS
                SELECT * FROM {cache_table}
            """
            
            self.db.execute_with_retry(view_sql, (), is_write=True)
            
            # Сохраняем метаданные
            self.views[view_name] = MaterializedView(
                view_name=view_name,
                base_query=base_query,
                refresh_interval_minutes=refresh_interval_minutes
            )
            
            # Первоначальное заполнение
            self.refresh_view(view_name)
            
            logger.info("✅ [MaterializedView] Создано представление %s", view_name)
            return True
            
        except Exception as e:
            logger.error("❌ [MaterializedView] Ошибка создания представления %s: %s", view_name, e)
            return False
    
    def refresh_view(self, view_name: str, force: bool = False) -> bool:
        """
        Обновляет материализованное представление.
        
        Args:
            view_name: Имя представления
            force: Принудительное обновление
            
        Returns:
            True при успехе
        """
        if view_name not in self.views:
            logger.warning("⚠️ [MaterializedView] Представление %s не найдено", view_name)
            return False
        
        view = self.views[view_name]
        
        # Проверяем, нужно ли обновление
        if not force and view.last_refreshed:
            time_since_refresh = get_utc_now() - view.last_refreshed
            if time_since_refresh < timedelta(minutes=view.refresh_interval_minutes):
                logger.debug("⏭️ [MaterializedView] Представление %s еще актуально", view_name)
                return True
        
        try:
            cache_table = f"{view_name}_cache"
            
            # Выполняем базовый запрос
            # Используем execute_with_retry без prepared statements для материализованных представлений
            results = self.db.execute_with_retry(
                view.base_query,
                (),
                is_write=False,
                use_prepared=False
            )
            
            # Очищаем старый кэш
            self.db.execute_with_retry(
                f"DELETE FROM {cache_table}",
                (),
                is_write=True
            )
            
            # Сохраняем результаты в кэш
            # (упрощенная версия - сериализуем в JSON)
            for row in results:
                data_json = json.dumps(row, default=str)
                self.db.execute_with_retry(
                    f"INSERT INTO {cache_table} (data, refreshed_at) VALUES (?, CURRENT_TIMESTAMP)",
                    (data_json,),
                    is_write=True
                )
            
            # Обновляем метаданные
            view.last_refreshed = get_utc_now()
            view.row_count = len(results) if results else 0
            
            logger.info(
                "✅ [MaterializedView] Обновлено представление %s (%d строк)",
                view_name, view.row_count
            )
            return True
            
        except Exception as e:
            logger.error("❌ [MaterializedView] Ошибка обновления представления %s: %s", view_name, e)
            return False
    
    def refresh_all_views(self, force: bool = False) -> Dict[str, bool]:
        """
        Обновляет все материализованные представления.
        
        Args:
            force: Принудительное обновление
            
        Returns:
            Словарь {view_name: success}
        """
        results = {}
        for view_name in self.views:
            results[view_name] = self.refresh_view(view_name, force=force)
        return results
    
    def get_view_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику по представлениям.
        
        Returns:
            Словарь со статистикой
        """
        stats = {
            'total_views': len(self.views),
            'views': []
        }
        
        for view_name, view in self.views.items():
            stats['views'].append({
                'name': view_name,
                'refresh_interval_minutes': view.refresh_interval_minutes,
                'last_refreshed': view.last_refreshed.isoformat() if view.last_refreshed else None,
                'row_count': view.row_count
            })
        
        return stats


# Предопределенные материализованные представления для ATRA
def create_common_materialized_views(db) -> MaterializedViewManager:
    """
    Создает стандартные материализованные представления для ATRA.
    
    Args:
        db: Экземпляр Database
        
    Returns:
        Менеджер представлений
    """
    manager = MaterializedViewManager(db)
    
    # Статистика по сигналам за последние 24 часа
    manager.create_materialized_view(
        view_name='v_signals_24h_stats',
        base_query="""
            SELECT 
                symbol,
                COUNT(*) as signal_count,
                SUM(CASE WHEN result = 'TP1' OR result = 'TP2' THEN 1 ELSE 0 END) as win_count,
                SUM(CASE WHEN result = 'SL' THEN 1 ELSE 0 END) as loss_count,
                AVG(net_profit) as avg_profit,
                SUM(net_profit) as total_profit
            FROM signals_log
            WHERE datetime(created_at) > datetime('now', '-24 hours')
            GROUP BY symbol
        """,
        refresh_interval_minutes=30
    )
    
    # Статистика по пользователям
    manager.create_materialized_view(
        view_name='v_users_performance',
        base_query="""
            SELECT 
                user_id,
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as win_trades,
                SUM(CASE WHEN pnl_usd < 0 THEN 1 ELSE 0 END) as loss_trades,
                SUM(pnl_usd) as total_pnl,
                AVG(pnl_usd) as avg_pnl
            FROM trades
            WHERE exit_time IS NOT NULL
            GROUP BY user_id
        """,
        refresh_interval_minutes=60
    )
    
    return manager

