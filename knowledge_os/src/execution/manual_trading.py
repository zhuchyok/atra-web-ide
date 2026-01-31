#!/usr/bin/env python3
"""
СИСТЕМА РУЧНОЙ ТОРГОВЛИ

Интерфейс для ручной торговли пользователей
"""

import logging
from src.database.db import Database
from src.shared.utils.datetime_utils import get_utc_now

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class ManualTrading:
    """Система ручной торговли"""

    def __init__(self):
        self.db = Database()

    def save_manual_trade(self, trade_data):
        """Сохраняет ручную сделку"""
        try:
            self.db.cursor.execute("""
                INSERT INTO manual_trades (
                    ts, symbol, buy_exchange, sell_exchange, buy_price, sell_price,
                    amount, notified_profit, notified_profit_pct, withdraw_fee,
                    final_profit, final_profit_pct, status, real_buy_price,
                    real_sell_price, real_amount, real_profit, real_profit_pct,
                    trade_completed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data.get('timestamp', get_utc_now().isoformat()),
                trade_data.get('symbol'),
                trade_data.get('buy_exchange'),
                trade_data.get('sell_exchange'),
                trade_data.get('buy_price'),
                trade_data.get('sell_price'),
                trade_data.get('amount'),
                trade_data.get('notified_profit'),
                trade_data.get('notified_profit_pct'),
                trade_data.get('withdraw_fee'),
                trade_data.get('final_profit'),
                trade_data.get('final_profit_pct'),
                trade_data.get('status', 'pending'),
                trade_data.get('real_buy_price'),
                trade_data.get('real_sell_price'),
                trade_data.get('real_amount'),
                trade_data.get('real_profit'),
                trade_data.get('real_profit_pct'),
                trade_data.get('trade_completed', 0)
            ))
            self.db.conn.commit()
            logger.info("✅ Ручная сделка сохранена: %s", trade_data.get('symbol'))
            return True
        except Exception as e:
            logger.error("❌ Ошибка сохранения ручной сделки: %s", e)
            return False

    def update_trade_status(self, trade_id, status, real_data=None):
        """Обновляет статус сделки"""
        try:
            if real_data:
                self.db.cursor.execute("""
                    UPDATE manual_trades SET
                        status = ?,
                        real_buy_price = ?,
                        real_sell_price = ?,
                        real_amount = ?,
                        real_profit = ?,
                        real_profit_pct = ?,
                        trade_completed = ?
                    WHERE id = ?
                """, (
                    status,
                    real_data.get('real_buy_price'),
                    real_data.get('real_sell_price'),
                    real_data.get('real_amount'),
                    real_data.get('real_profit'),
                    real_data.get('real_profit_pct'),
                    real_data.get('trade_completed', 1),
                    trade_id
                ))
            else:
                self.db.cursor.execute("""
                    UPDATE manual_trades SET status = ? WHERE id = ?
                """, (status, trade_id))

            self.db.conn.commit()
            logger.info("✅ Статус сделки %s обновлен: %s", trade_id, status)
            return True
        except Exception as e:
            logger.error("❌ Ошибка обновления статуса сделки: %s", e)
            return False

    def get_user_trades(self, user_id=None, status=None):
        """Получает сделки пользователя"""
        try:
            if user_id and status:
                self.db.cursor.execute("""
                    SELECT * FROM manual_trades
                    WHERE user_id = ? AND status = ?
                    ORDER BY ts DESC
                """, (user_id, status))
            elif user_id:
                self.db.cursor.execute("""
                    SELECT * FROM manual_trades
                    WHERE user_id = ?
                    ORDER BY ts DESC
                """, (user_id,))
            elif status:
                self.db.cursor.execute("""
                    SELECT * FROM manual_trades
                    WHERE status = ?
                    ORDER BY ts DESC
                """, (status,))
            else:
                self.db.cursor.execute("""
                    SELECT * FROM manual_trades
                    ORDER BY ts DESC
                """)

            all_trades = self.db.cursor.fetchall()
            logger.info("📊 Найдено %s сделок", len(all_trades))
            return all_trades
        except Exception as e:
            logger.error("❌ Ошибка получения сделок: %s", e)
            return []

    def calculate_trade_profit(self, buy_price, sell_price, amount, fees=0.001):
        """Рассчитывает прибыль от сделки"""
        try:
            # Учитываем комиссии
            buy_cost = buy_price * amount * (1 + fees)
            sell_revenue = sell_price * amount * (1 - fees)

            trade_profit = sell_revenue - buy_cost
            profit_pct = (trade_profit / buy_cost) * 100

            return {
                'profit': trade_profit,
                'profit_pct': profit_pct,
                'buy_cost': buy_cost,
                'sell_revenue': sell_revenue
            }
        except Exception as e:
            logger.error("❌ Ошибка расчета прибыли: %s", e)
            return None

# Глобальный экземпляр для использования в других модулях
manual_trading = ManualTrading()

def save_manual_trade(trade_data):
    """Сохраняет ручную сделку (глобальная функция)"""
    return manual_trading.save_manual_trade(trade_data)

def update_trade_status(trade_id, status, real_data=None):
    """Обновляет статус сделки (глобальная функция)"""
    return manual_trading.update_trade_status(trade_id, status, real_data)

def get_user_trades(user_id=None, status=None):
    """Получает сделки пользователя (глобальная функция)"""
    return manual_trading.get_user_trades(user_id, status)

def calculate_trade_profit(buy_price, sell_price, amount, fees=0.001):
    """Рассчитывает прибыль от сделки (глобальная функция)"""
    return manual_trading.calculate_trade_profit(buy_price, sell_price, amount, fees)

if __name__ == "__main__":
    # Тестирование системы ручной торговли
    logger.info("🧪 Тестирование системы ручной торговли")

    # Тестовая сделка
    test_trade = {
        'symbol': 'BTCUSDT',
        'buy_exchange': 'binance',
        'sell_exchange': 'mexc',
        'buy_price': 45000.0,
        'sell_price': 45100.0,
        'amount': 0.1,
        'status': 'pending'
    }

    # Сохраняем тестовую сделку
    if save_manual_trade(test_trade):
        logger.info("✅ Тестовая сделка сохранена")
    else:
        logger.error("❌ Ошибка сохранения тестовой сделки")

    # Получаем все сделки
    trades = get_user_trades()
    logger.info("📊 Всего сделок: %s", len(trades))

    # Рассчитываем прибыль
    profit = calculate_trade_profit(45000, 45100, 0.1)
    if profit:
        logger.info("💰 Прибыль: %.2f USDT (%.2f%%)", profit['profit'], profit['profit_pct'])
