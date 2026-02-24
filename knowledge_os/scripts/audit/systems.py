#!/usr/bin/env python3
"""
СИСТЕМЫ АУДИТА И МОНИТОРИНГА

Все системы аудита и мониторинга системы
"""

import logging
from datetime import datetime

from src.database.db import Database

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


class AuditSystems:
    """Системы аудита и мониторинга"""

    def __init__(self):
        self.db = Database()

    def log_strategy_pause(self, action, reason, window_hours=24, sl_count=0, net_profit_sum=0.0):
        """Логирует паузы стратегии"""
        try:
            self.db.cursor.execute(
                """
                INSERT INTO audit_strategy_pauses (ts, action, reason, window_hours, sl_count, net_profit_sum)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.utcnow().isoformat(),
                    action,
                    reason,
                    window_hours,
                    sl_count,
                    net_profit_sum,
                ),
            )
            self.db.conn.commit()
            logger.info(f"📊 Аудит паузы стратегии: {action} - {reason}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка аудита паузы стратегии: {e}")
            return False

    def log_soft_blocklist(self, action, symbol, votes=0, reason=""):
        """Логирует мягкий блэклист"""
        try:
            self.db.cursor.execute(
                """
                INSERT INTO audit_soft_blocklist (ts, action, symbol, votes, reason)
                VALUES (?, ?, ?, ?, ?)
            """,
                (datetime.utcnow().isoformat(), action, symbol, votes, reason),
            )
            self.db.conn.commit()
            logger.info(f"📊 Аудит мягкого блэклиста: {action} - {symbol}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка аудита мягкого блэклиста: {e}")
            return False

    def log_active_coin(self, action, symbol, note=""):
        """Логирует активные монеты"""
        try:
            self.db.cursor.execute(
                """
                INSERT INTO audit_active_coins (ts, action, symbol, note)
                VALUES (?, ?, ?, ?)
            """,
                (datetime.utcnow().isoformat(), action, symbol, note),
            )
            self.db.conn.commit()
            logger.info(f"📊 Аудит активных монет: {action} - {symbol}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка аудита активных монет: {e}")
            return False

    def add_to_market_cap_blacklist(self, symbol, market_cap, reason=""):
        """Добавляет в черный список по капитализации"""
        try:
            self.db.cursor.execute(
                """
                INSERT INTO market_cap_blacklist (symbol, market_cap, blacklisted_at, reason)
                VALUES (?, ?, ?, ?)
            """,
                (symbol, market_cap, datetime.utcnow().isoformat(), reason),
            )
            self.db.conn.commit()
            logger.info(f"📊 Добавлено в черный список по капитализации: {symbol}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления в черный список: {e}")
            return False

    def add_signal_event(self, symbol, event, weight=1.0, ttl_sec=3600, meta=""):
        """Добавляет событие сигнала для накопления"""
        try:
            self.db.cursor.execute(
                """
                INSERT INTO signal_accum_events (ts, symbol, event, weight, ttl_sec, meta)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (int(datetime.utcnow().timestamp()), symbol, event, weight, ttl_sec, meta),
            )
            self.db.conn.commit()
            logger.info(f"📊 Событие сигнала добавлено: {symbol} - {event}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления события сигнала: {e}")
            return False

    def add_pending_check(self, symbol, attempts=1, status="pending"):
        """Добавляет проверку в ожидание"""
        try:
            self.db.cursor.execute(
                """
                INSERT INTO pending_check (symbol, attempts, last_check, status)
                VALUES (?, ?, ?, ?)
            """,
                (symbol, attempts, datetime.utcnow().isoformat(), status),
            )
            self.db.conn.commit()
            logger.info(f"📊 Проверка добавлена в ожидание: {symbol}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления проверки: {e}")
            return False

    def save_backtest_result(self, backtest_data):
        """Сохраняет результат бэктеста"""
        try:
            self.db.cursor.execute(
                """
                INSERT INTO backtest_results (
                    symbol, interval, since_days, bars, signals, tp1, tp2, sl, pnl,
                    mae_avg_pct, mfe_avg_pct, avg_duration_sec, started_at, ended_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    backtest_data.get("symbol"),
                    backtest_data.get("interval"),
                    backtest_data.get("since_days"),
                    backtest_data.get("bars"),
                    backtest_data.get("signals"),
                    backtest_data.get("tp1"),
                    backtest_data.get("tp2"),
                    backtest_data.get("sl"),
                    backtest_data.get("pnl"),
                    backtest_data.get("mae_avg_pct"),
                    backtest_data.get("mfe_avg_pct"),
                    backtest_data.get("avg_duration_sec"),
                    backtest_data.get("started_at"),
                    backtest_data.get("ended_at"),
                    datetime.utcnow().isoformat(),
                ),
            )
            self.db.conn.commit()
            logger.info(f"📊 Результат бэктеста сохранен: {backtest_data.get('symbol')}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения результата бэктеста: {e}")
            return False


# Глобальный экземпляр (lazy initialization для предотвращения Database() при импорте)
_audit_systems = None


def get_audit_systems():
    """Получает или создает экземпляр AuditSystems (singleton с lazy init)"""
    global _audit_systems
    if _audit_systems is None:
        _audit_systems = AuditSystems()
    return _audit_systems


# Для обратной совместимости
class _LazyAuditSystems:
    """Lazy proxy для audit_systems"""

    def __getattr__(self, name):
        return getattr(get_audit_systems(), name)


audit_systems = _LazyAuditSystems()


def log_strategy_pause(action, reason, window_hours=24, sl_count=0, net_profit_sum=0.0):
    """Логирует паузы стратегии (глобальная функция)"""
    return get_audit_systems().log_strategy_pause(
        action, reason, window_hours, sl_count, net_profit_sum
    )


def log_soft_blocklist(action, symbol, votes=0, reason=""):
    """Логирует мягкий блэклист (глобальная функция)"""
    return get_audit_systems().log_soft_blocklist(action, symbol, votes, reason)


def log_active_coin(action, symbol, note=""):
    """Логирует активные монеты (глобальная функция)"""
    return get_audit_systems().log_active_coin(action, symbol, note)


def add_to_market_cap_blacklist(symbol, market_cap, reason=""):
    """Добавляет в черный список по капитализации (глобальная функция)"""
    return get_audit_systems().add_to_market_cap_blacklist(symbol, market_cap, reason)


def add_signal_event(symbol, event, weight=1.0, ttl_sec=3600, meta=""):
    """Добавляет событие сигнала для накопления (глобальная функция)"""
    return get_audit_systems().add_signal_event(symbol, event, weight, ttl_sec, meta)


def add_pending_check(symbol, attempts=1, status="pending"):
    """Добавляет проверку в ожидание (глобальная функция)"""
    return get_audit_systems().add_pending_check(symbol, attempts, status)


def save_backtest_result(backtest_data):
    """Сохраняет результат бэктеста (глобальная функция)"""
    return get_audit_systems().save_backtest_result(backtest_data)


if __name__ == "__main__":
    # Тестирование систем аудита
    logger.info("🧪 Тестирование систем аудита")

    # Тест паузы стратегии
    if log_strategy_pause("pause", "Тестовая пауза", 24, 0, 0.0):
        logger.info("✅ Тест паузы стратегии прошел")

    # Тест мягкого блэклиста
    if log_soft_blocklist("block", "TESTUSDT", 3, "Тестовая блокировка"):
        logger.info("✅ Тест мягкого блэклиста прошел")

    # Тест активных монет
    if log_active_coin("add", "BTCUSDT", "Тестовая монета"):
        logger.info("✅ Тест активных монет прошел")

    # Тест черного списка по капитализации
    if add_to_market_cap_blacklist("TESTUSDT", 1000000, "Тестовая капитализация"):
        logger.info("✅ Тест черного списка прошел")

    # Тест события сигнала
    if add_signal_event("BTCUSDT", "test_event", 1.0, 3600, "Тестовое событие"):
        logger.info("✅ Тест события сигнала прошел")

    # Тест проверки в ожидание
    if add_pending_check("BTCUSDT", 1, "pending"):
        logger.info("✅ Тест проверки в ожидание прошел")

    # Тест результата бэктеста
    test_backtest = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "since_days": 30,
        "bars": 720,
        "signals": 15,
        "tp1": 8,
        "tp2": 5,
        "sl": 2,
        "pnl": 1250.0,
        "mae_avg_pct": 2.5,
        "mfe_avg_pct": 4.2,
        "avg_duration_sec": 3600,
        "started_at": datetime.utcnow().isoformat(),
        "ended_at": datetime.utcnow().isoformat(),
    }

    if save_backtest_result(test_backtest):
        logger.info("✅ Тест результата бэктеста прошел")

    logger.info("🎉 Все тесты систем аудита завершены!")
