"""
Base classes for signal filters
Базовые классы для фильтров сигналов
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now


class FilterResult:
    """Результат работы фильтра"""

    def __init__(self, passed: bool, reason: str = "", details: Dict[str, Any] = None):
        self.passed = passed
        self.reason = reason
        self.details = details or {}
        self.timestamp = get_utc_now()

    def __bool__(self):
        return self.passed

    def __str__(self):
        return f"FilterResult(passed={self.passed}, reason='{self.reason}')"


class BaseFilter(ABC):
    """Базовый класс для всех фильтров сигналов"""

    def __init__(self, name: str, enabled: bool = True, priority: int = 1):
        self.name = name
        self.enabled = enabled
        self.priority = priority
        self.filter_stats = {
            'total_checked': 0,
            'passed': 0,
            'blocked': 0,
            'errors': 0
        }

    @abstractmethod
    async def filter_signal(self, signal_data: Dict[str, Any]) -> FilterResult:
        """
        Основной метод фильтрации сигнала

        Args:
            signal_data: Данные сигнала для фильтрации

        Returns:
            FilterResult: Результат фильтрации
        """

    def update_stats(self, result: FilterResult):
        """Обновить статистику фильтра"""
        self.filter_stats['total_checked'] += 1
        if result.passed:
            self.filter_stats['passed'] += 1
        else:
            self.filter_stats['blocked'] += 1

    def get_stats(self) -> Dict[str, int]:
        """Получить статистику фильтра"""
        stats = self.filter_stats.copy()
        stats['pass_rate'] = (stats['passed'] / stats['total_checked']) * 100 if stats['total_checked'] > 0 else 0
        return stats

    def reset_stats(self):
        """Сбросить статистику"""
        self.filter_stats = {
            'total_checked': 0,
            'passed': 0,
            'blocked': 0,
            'errors': 0
        }


class FilterManager:
    """Менеджер фильтров"""

    def __init__(self):
        self.filters: List[BaseFilter] = []
        self.filter_history: List[Dict[str, Any]] = []

    def add_filter(self, filter_instance: BaseFilter):
        """Добавить фильтр"""
        self.filters.append(filter_instance)
        # Сортировка по приоритету
        self.filters.sort(key=lambda x: x.priority)

    def remove_filter(self, filter_name: str):
        """Удалить фильтр по имени"""
        self.filters = [f for f in self.filters if f.name != filter_name]

    def get_filter(self, filter_name: str) -> BaseFilter:
        """Получить фильтр по имени"""
        for filter_instance in self.filters:
            if filter_instance.name == filter_name:
                return filter_instance
        return None

    async def apply_filters(self, signal_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Применить все фильтры к сигналу

        Args:
            signal_data: Данные сигнала

        Returns:
            Tuple[bool, List[str]]: (прошел_все_фильтры, список_причин_блокировки)
        """
        all_passed = True
        block_reasons = []

        # Импортируем утилиту логирования
        try:
            from src.utils.filter_logger import log_filter_check_async  # pylint: disable=import-outside-toplevel
            logging_available = True
        except ImportError:
            logging_available = False
            # Логирование недоступно, продолжаем без него

        for filter_instance in self.filters:
            if not filter_instance.enabled:
                continue

            try:
                result = await filter_instance.filter_signal(signal_data)
                filter_instance.update_stats(result)

                # Логирование результата в память
                self.filter_history.append({
                    'timestamp': get_utc_now(),
                    'filter_name': filter_instance.name,
                    'signal_symbol': signal_data.get('symbol', 'unknown'),
                    'passed': result.passed,
                    'reason': result.reason
                })

                # Логирование в БД
                if logging_available:
                    symbol = signal_data.get('symbol', 'unknown')
                    filter_name = filter_instance.name
                    try:
                        log_filter_check_async(
                            symbol=symbol,
                            filter_type=filter_name,
                            passed=result.passed,
                            reason=result.reason if not result.passed else None
                        )
                    except Exception:
                        # Игнорируем ошибки логирования, чтобы не прерывать работу фильтров
                        pass

                if not result.passed:
                    all_passed = False
                    block_reasons.append(f"{filter_instance.name}: {result.reason}")

            except Exception as e:
                filter_instance.filter_stats['errors'] += 1
                block_reasons.append(f"{filter_instance.name}: Ошибка - {str(e)}")
                all_passed = False

        return all_passed, block_reasons

    def get_all_stats(self) -> Dict[str, Dict[str, int]]:
        """Получить статистику всех фильтров"""
        return {f.name: f.get_stats() for f in self.filters}

    def get_filter_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Получить историю применения фильтров"""
        return self.filter_history[-limit:] if limit > 0 else self.filter_history


# Глобальный экземпляр менеджера фильтров
filter_manager = FilterManager()
