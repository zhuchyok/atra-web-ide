#!/usr/bin/env python3

"""
Модуль для управления блоклистом монет с низкой капитализацией.

Автоматически блокирует монеты с капитализацией < 150M на неделю,
затем размораживает их для повторной проверки.
"""

import logging
from typing import Dict, List

from src.database.db import Database

# Глобальный экземпляр базы данных
_db_instance = None


def get_db():
    """Получает экземпляр базы данных (singleton pattern)."""
    global _db_instance  # pylint: disable=global-statement
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


class MarketCapBlacklist:
    """Класс для управления блоклистом капитализации."""

    def __init__(self):
        self.db = get_db()
        self.min_market_cap = 150_000_000  # 150M USD

    def should_blacklist(self, symbol: str, market_cap: float) -> bool:  # pylint: disable=unused-argument,redefined-outer-name
        """
        Определяет, нужно ли заблокировать монету.

        Args:
            symbol: Символ монеты
            market_cap: Капитализация в USD

        Returns:
            True если монету нужно заблокировать
        """
        return market_cap < self.min_market_cap

    def add_to_blacklist(
        self, symbol: str, market_cap: float, reason: str = "low_market_cap"
    ) -> bool:
        """
        Добавляет монету в блоклист.

        Args:
            symbol: Символ монеты
            market_cap: Капитализация в USD
            reason: Причина блокировки

        Returns:
            True если успешно добавлена
        """
        if not self.should_blacklist(symbol, market_cap):
            return False

        result = self.db.add_to_market_cap_blacklist(symbol, market_cap, reason)
        if result:
            logging.info(
                "🚫 Монета %s заблокирована (капитализация: $%.0fM < $150M)",
                symbol,
                market_cap / 1_000_000,
            )
        return result  # pylint: disable=redefined-outer-name

    def is_blacklisted(self, symbol: str) -> bool:
        """
        Проверяет, заблокирована ли монета.

        Args:
            symbol: Символ монеты

        Returns:
            True если монета заблокирована
        """
        return self.db.is_market_cap_blacklisted(symbol)

    def get_blacklist(self) -> List[Dict]:
        """
        Получает список заблокированных монет.

        Returns:
            Список заблокированных монет
        """
        return self.db.get_market_cap_blacklist()

    def unfreeze_expired(self) -> int:
        """
        Размораживает монеты с истекшим сроком блокировки.

        Returns:
            Количество размороженных монет
        """
        unfrozen_count = self.db.unfreeze_market_cap_blacklist()
        if unfrozen_count > 0:
            logging.info("🔄 Разморожено %d монет из блоклиста капитализации", unfrozen_count)
        return unfrozen_count

    def remove_from_blacklist(self, symbol: str) -> bool:
        """
        Удаляет монету из блоклиста.

        Args:
            symbol: Символ монеты

        Returns:
            True если успешно удалена
        """
        result = self.db.remove_from_market_cap_blacklist(symbol)
        if result:
            logging.info("✅ Монета %s удалена из блоклиста капитализации", symbol)
        return result  # pylint: disable=redefined-outer-name

    def update_check_time(self, symbol: str) -> bool:
        """
        Обновляет время последней проверки монеты.

        Args:
            symbol: Символ монеты

        Returns:
            True если успешно обновлено
        """
        return self.db.update_market_cap_blacklist_check(symbol)

    def get_blacklist_stats(self) -> Dict:
        """
        Получает статистику блоклиста.

        Returns:
            Словарь со статистикой
        """
        blacklist = self.get_blacklist()

        total_blacklisted = len(blacklist)
        avg_market_cap = 0
        min_market_cap = float("inf")
        max_market_cap = 0

        if blacklist:
            market_caps = [item["market_cap"] for item in blacklist if item["market_cap"]]
            if market_caps:
                avg_market_cap = sum(market_caps) / len(market_caps)
                min_market_cap = min(market_caps)
                max_market_cap = max(market_caps)

        return {
            "total_blacklisted": total_blacklisted,
            "avg_market_cap": avg_market_cap,
            "min_market_cap": min_market_cap if min_market_cap != float("inf") else 0,
            "max_market_cap": max_market_cap,
            "threshold": self.min_market_cap,
        }


# Глобальный экземпляр для использования в других модулях
market_cap_blacklist = MarketCapBlacklist()


# Удобные функции для быстрого доступа
def is_market_cap_blacklisted(symbol: str) -> bool:
    """Проверяет, заблокирована ли монета по капитализации."""
    return market_cap_blacklist.is_blacklisted(symbol)


def add_to_market_cap_blacklist(
    symbol: str, market_cap: float, reason: str = "low_market_cap"
) -> bool:
    """Добавляет монету в блоклист капитализации."""
    return market_cap_blacklist.add_to_blacklist(symbol, market_cap, reason)


def unfreeze_market_cap_blacklist() -> int:
    """Размораживает монеты с истекшим сроком блокировки."""
    return market_cap_blacklist.unfreeze_expired()


def get_market_cap_blacklist() -> List[Dict]:
    """Получает список заблокированных монет."""
    return market_cap_blacklist.get_blacklist()


def get_blacklist_stats() -> Dict:
    """Получает статистику блоклиста."""
    return market_cap_blacklist.get_blacklist_stats()


if __name__ == "__main__":
    # Тестирование модуля
    print("Тестирование блоклиста капитализации...")

    # Тестируем добавление в блоклист
    test_symbol = "TESTUSDT"
    test_market_cap = 100_000_000  # 100M USD

    print(f"Добавляем {test_symbol} с капитализацией ${test_market_cap:,}")
    success = add_to_market_cap_blacklist(test_symbol, test_market_cap)
    print(f"Результат: {success}")

    # Проверяем, заблокирована ли монета
    is_blacklisted = is_market_cap_blacklisted(test_symbol)
    print(f"Заблокирована ли {test_symbol}: {is_blacklisted}")

    # Получаем статистику
    stats = get_blacklist_stats()
    print(f"Статистика блоклиста: {stats}")

    # Получаем список заблокированных
    blacklisted_coins = get_market_cap_blacklist()  # pylint: disable=redefined-outer-name
    print(f"Заблокированных монет: {len(blacklisted_coins)}")

    # Удаляем тестовую монету
    market_cap_blacklist.remove_from_blacklist(test_symbol)
    print(f"Тестовая монета {test_symbol} удалена из блоклиста")

    print("Тестирование завершено")
