"""
Filter Manager - Central filter management system
Менеджер фильтров - центральная система управления фильтрами
"""

from typing import Dict, Any, List, Tuple
import logging
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
from .base import FilterManager, BaseFilter
from .anomaly import AnomalyFilter
from .interest_zone import InterestZoneFilter
from .btc_trend import BTCTrendFilter
from .news import NewsFilter
from .whale import WhaleFilter

logger = logging.getLogger(__name__)


class ATRAFilterManager(FilterManager):
    """Расширенный менеджер фильтров для системы ATRA"""

    def __init__(self):
        super().__init__()
        self._initialize_default_filters()

    def _initialize_default_filters(self):
        """Инициализация фильтров по умолчанию"""
        # Добавляем фильтр аномалий
        try:
            self.add_filter(AnomalyFilter())
            logger.info("✅ AnomalyFilter добавлен")
        except Exception as e:
            logger.error("❌ Ошибка добавления AnomalyFilter: %s", e)

        # Добавляем фильтр зон интереса
        try:
            self.add_filter(InterestZoneFilter())
            logger.info("✅ InterestZoneFilter добавлен")
        except Exception as e:
            logger.error("❌ Ошибка добавления InterestZoneFilter: %s", e)

        # Добавляем фильтр тренда BTC
        try:
            self.add_filter(BTCTrendFilter())
            logger.info("✅ BTCTrendFilter добавлен")
        except Exception as e:
            logger.error("❌ Ошибка добавления BTCTrendFilter: %s", e)

        # Добавляем фильтр новостей
        try:
            self.add_filter(NewsFilter())
            logger.info("✅ NewsFilter добавлен")
        except Exception as e:
            logger.error("❌ Ошибка добавления NewsFilter: %s", e)

        # Добавляем фильтр китов
        try:
            self.add_filter(WhaleFilter())
            logger.info("✅ WhaleFilter добавлен")
        except Exception as e:
            logger.error("❌ Ошибка добавления WhaleFilter: %s", e)

        logger.info("✅ Все фильтры по умолчанию инициализированы")

    async def apply_all_filters(self, signal_data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Применить все фильтры к сигналу

        Args:
            signal_data: Данные сигнала

        Returns:
            Tuple[bool, List[str], Dict[str, Any]]:
            (прошел_фильтры, причины_блокировки, дополнительная_информация)
        """
        passed, reasons = await self.apply_filters(signal_data)

        # Сбор дополнительной информации от фильтров
        additional_info = {}
        for filter_instance in self.filters:
            if hasattr(filter_instance, 'get_additional_info'):
                additional_info[filter_instance.name] = filter_instance.get_additional_info(signal_data)

        return passed, reasons, additional_info

    def get_filter_status(self) -> Dict[str, Dict[str, Any]]:
        """Получить статус всех фильтров"""
        status = {}
        for filter_instance in self.filters:
            status[filter_instance.name] = {
                'enabled': filter_instance.enabled,
                'priority': filter_instance.priority,
                'stats': filter_instance.get_stats(),
                'class': filter_instance.__class__.__name__
            }
        return status

    def enable_filter(self, filter_name: str) -> bool:
        """Включить фильтр"""
        filter_instance = self.get_filter(filter_name)
        if filter_instance:
            filter_instance.enabled = True
            return True
        return False

    def disable_filter(self, filter_name: str) -> bool:
        """Отключить фильтр"""
        filter_instance = self.get_filter(filter_name)
        if filter_instance:
            filter_instance.enabled = False
            return True
        return False

    def reset_all_stats(self):
        """Сбросить статистику всех фильтров"""
        for filter_instance in self.filters:
            filter_instance.reset_stats()

    def get_filter_efficiency_report(self) -> Dict[str, Any]:
        """Получить отчет об эффективности фильтров"""
        total_checked = 0
        total_passed = 0
        total_blocked = 0
        total_errors = 0

        filter_stats = {}

        for filter_instance in self.filters:
            stats = filter_instance.get_stats()
            filter_stats[filter_instance.name] = stats

            total_checked += stats.get('total_checked', 0)
            total_passed += stats.get('passed', 0)
            total_blocked += stats.get('blocked', 0)
            total_errors += stats.get('errors', 0)

        overall_pass_rate = (total_passed / total_checked) * 100 if total_checked > 0 else 0

        return {
            'timestamp': get_utc_now(),
            'summary': {
                'total_checked': total_checked,
                'total_passed': total_passed,
                'total_blocked': total_blocked,
                'total_errors': total_errors,
                'overall_pass_rate': overall_pass_rate
            },
            'filters': filter_stats
        }


# Глобальный экземпляр менеджера фильтров
atrafilter_manager = ATRAFilterManager()
