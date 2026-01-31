#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система управления ордерами для торгового бота.

Предоставляет полное управление ордерами:
- Размещение рыночных и лимитных ордеров
- Управление стоп-лосс и тейк-профит
- Трейлинг-стоп с AI-оптимизацией
- Отмена и изменение ордеров
"""

import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

import numpy as np

from src.execution.slippage_manager import get_slippage_manager
from src.shared.utils.datetime_utils import get_utc_now
from src.core.exceptions import (
    OrderError,
    OrderExecutionError,
    ValidationError,
    FinancialError
)

logger = logging.getLogger(__name__)

@dataclass
class Order:
    """Ордер"""
    order_id: str
    symbol: str
    side: str  # 'buy' или 'sell'
    order_type: str  # 'market', 'limit', 'stop', 'stop_limit'
    quantity: Decimal
    price: Decimal
    stop_price: Optional[Decimal] = None
    status: str = 'pending'  # 'pending', 'filled', 'cancelled', 'rejected'
    created_time: datetime = field(default_factory=get_utc_now)
    filled_time: Optional[datetime] = None
    filled_price: Optional[Decimal] = None
    filled_quantity: Decimal = Decimal("0.0")
    commission: Decimal = Decimal("0.0")
    user_id: Optional[str] = None
    position_id: Optional[str] = None
    parent_order_id: Optional[str] = None
    trailing_stop: bool = False
    trailing_distance: Decimal = Decimal("0.0")
    max_price: Decimal = Decimal("0.0")
    min_price: Decimal = Decimal("Infinity")

@dataclass
class OrderBook:
    """Стакан заявок"""
    symbol: str
    bids: List[Tuple[Decimal, Decimal]]  # (price, quantity)
    asks: List[Tuple[Decimal, Decimal]]
    last_update: datetime = field(default_factory=get_utc_now)

class OrderManager:
    """Главный класс управления ордерами"""

    def __init__(self):
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.order_books: Dict[str, OrderBook] = {}  # symbol -> OrderBook
        self.pending_orders: List[Order] = []
        self.filled_orders: List[Order] = []
        self.cancelled_orders: List[Order] = []

        # Настройки ордеров
        self.order_settings = {
            'max_orders_per_symbol': 10,
            'max_orders_per_user': 50,
            'order_timeout': 300,  # 5 минут
            'retry_attempts': 3,
            'slippage_tolerance': Decimal("0.001"),  # 0.1%
            'commission_rate': Decimal("0.001")  # 0.1%
        }

        # Статистика ордеров
        self.order_stats = {
            'total_orders': 0,
            'filled_orders': 0,
            'cancelled_orders': 0,
            'rejected_orders': 0,
            'avg_fill_time': 0.0,
            'fill_rate': 0.0
        }

        # Трейлинг-стоп настройки
        self.trailing_stop_settings = {
            'enabled': True,
            'min_distance': Decimal("0.001"),  # 0.1%
            'max_distance': Decimal("0.05"),   # 5%
            'step_size': Decimal("0.001"),     # 0.1%
            'activation_threshold': Decimal("0.02")  # 2%
        }

    def create_market_order(self,
                          symbol: str,
                          side: str,
                          quantity: Decimal,
                          user_id: str = None,
                          position_id: str = None,
                          volume_24h: Optional[float] = None,
                          order_size_usd: Optional[Decimal] = None,
                          volatility: Optional[float] = None,
                          auto_optimize: bool = True) -> Optional[Order]:
        """
        Создает рыночный ордер с динамическим проскальзыванием
        Автоматически выбирает между market и limit ордерами (H4.1)
        """

        order_id = self._generate_order_id()

        # Получаем текущую цену
        current_price = self._get_current_price(symbol)
        if current_price is None:
            raise OrderExecutionError(
                f"Cannot get current price for {symbol}",
                context={"symbol": symbol, "side": side}
            )

        order_type = 'market'
        price = current_price

        # Автоматическая оптимизация: выбор между market и limit
        if auto_optimize:
            try:
                slippage_manager = get_slippage_manager()

                order_decision = slippage_manager.should_use_limit_order(
                    symbol=symbol,
                    side=side,
                    current_price=float(current_price),
                    volume_24h=volume_24h,
                    order_size_usd=float(order_size_usd or (quantity * current_price)),
                    volatility=volatility
                )

                if order_decision['use_limit']:
                    order_type = 'limit'
                    price = Decimal(str(order_decision['limit_price']))
                    logger.info(
                        "🎯 [ORDER OPTIMIZATION] %s %s: используем LIMIT ордер @ %.4f "
                        "(ожидаемая экономия: %.3f%%) - %s",
                        symbol, side, float(price), order_decision['potential_savings'],
                        order_decision['reason']
                    )
                else:
                    # Используем market с динамическим проскальзыванием
                    dynamic_slippage = Decimal(str(slippage_manager.calculate_dynamic_slippage(
                        symbol=symbol,
                        volume_24h=volume_24h,
                        order_size_usd=float(order_size_usd or (quantity * current_price)),
                        volatility=volatility
                    )))

                    if side == 'buy':
                        price = current_price * (Decimal("1") + dynamic_slippage)
                    else:
                        price = current_price * (Decimal("1") - dynamic_slippage)

                    logger.debug(
                        "📊 [ORDER] %s %s: используем MARKET ордер с проскальзыванием %.3f%%",
                        symbol, side, float(dynamic_slippage) * 100
                    )

            except Exception as e:
                logger.warning(
                    "⚠️ Не удалось оптимизировать ордер для %s: %s, используем базовое проскальзывание",
                    symbol, e
                )
                dynamic_slippage = self.order_settings['slippage_tolerance']
                if side == 'buy':
                    price = current_price * (Decimal("1") + dynamic_slippage)
                else:
                    price = current_price * (Decimal("1") - dynamic_slippage)
        else:
            # Без оптимизации - используем базовое проскальзывание
            dynamic_slippage = self.order_settings['slippage_tolerance']
            if side == 'buy':
                price = current_price * (Decimal("1") + dynamic_slippage)
            else:
                price = current_price * (Decimal("1") - dynamic_slippage)

        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            user_id=user_id,
            position_id=position_id
        )

        # Проверяем лимиты
        if not self._check_order_limits(order):
            raise ValidationError(
                f"Order limits exceeded for {symbol}",
                context={"symbol": symbol, "user_id": user_id}
            )

        # Добавляем ордер
        self.orders[order_id] = order
        self.pending_orders.append(order)
        self.order_stats['total_orders'] += 1

        logger.info(
            "%s order created: %s %s %.4f @ %.4f",
            order_type.upper(), symbol, side, float(quantity), float(price)
        )
        return order

    def create_limit_order(self,
                          symbol: str,
                          side: str,
                          quantity: Decimal,
                          price: Decimal,
                          user_id: str = None,
                          position_id: str = None) -> Optional[Order]:
        """Создает лимитный ордер"""

        order_id = self._generate_order_id()

        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type='limit',
            quantity=quantity,
            price=price,
            user_id=user_id,
            position_id=position_id
        )

        # Проверяем лимиты
        if not self._check_order_limits(order):
            raise ValidationError(
                f"Order limits exceeded for {symbol}",
                context={"symbol": symbol, "user_id": user_id}
            )

        # Проверяем разумность цены
        if not self._check_price_reasonableness(order):
            raise ValidationError(
                f"Order price {float(price)} is unreasonable for {symbol}",
                context={"symbol": symbol, "price": float(price)}
            )

        # Добавляем ордер
        self.orders[order_id] = order
        self.pending_orders.append(order)
        self.order_stats['total_orders'] += 1

        logger.info("Limit order created: %s %s %.4f @ %.4f", symbol, side, float(quantity), float(price))
        return order

    def create_stop_order(self,
                              symbol: str,
                              side: str,
                              quantity: Decimal,
                              stop_price: Decimal,
                              limit_price: Optional[Decimal] = None,
                              user_id: str = None,
                              position_id: str = None) -> Optional[Order]:
        """Создает стоп-ордер"""

        order_id = self._generate_order_id()

        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type='stop_limit' if limit_price else 'stop',
            quantity=quantity,
            price=limit_price or stop_price,
            stop_price=stop_price,
            user_id=user_id,
            position_id=position_id
        )

        # Проверяем лимиты
        if not self._check_order_limits(order):
            raise ValidationError(
                f"Order limits exceeded for {symbol}",
                context={"symbol": symbol, "user_id": user_id}
            )

        # Добавляем ордер
        self.orders[order_id] = order
        self.pending_orders.append(order)
        self.order_stats['total_orders'] += 1

        logger.info("Stop order created: %s %s %.4f @ %.4f", symbol, side, float(quantity), float(stop_price))
        return order

    def create_trailing_stop_order(self,
                                  symbol: str,
                                  side: str,
                                  quantity: Decimal,
                                  trailing_distance: Decimal,
                                  user_id: str = None,
                                  position_id: str = None) -> Optional[Order]:
        """Создает трейлинг-стоп ордер"""

        order_id = self._generate_order_id()

        # Получаем текущую цену
        current_price = self._get_current_price(symbol)
        if current_price is None:
            raise OrderExecutionError(
                f"Cannot get current price for {symbol} to calculate trailing stop",
                context={"symbol": symbol}
            )

        # Рассчитываем начальную стоп-цену
        if side == 'sell':
            stop_price = current_price * (Decimal("1") - trailing_distance)
        else:
            stop_price = current_price * (Decimal("1") + trailing_distance)

        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type='stop',
            quantity=quantity,
            price=stop_price,
            stop_price=stop_price,
            trailing_stop=True,
            trailing_distance=trailing_distance,
            user_id=user_id,
            position_id=position_id
        )

        # Проверяем лимиты
        if not self._check_order_limits(order):
            raise ValidationError(
                f"Order limits exceeded for {symbol}",
                context={"symbol": symbol, "user_id": user_id}
            )

        # Добавляем ордер
        self.orders[order_id] = order
        self.pending_orders.append(order)
        self.order_stats['total_orders'] += 1

        logger.info(
            "Trailing stop order created: %s %s %.4f distance: %.4f",
            symbol, side, float(quantity), float(trailing_distance)
        )
        return order

    def cancel_order(self, order_id: str) -> bool:
        """Отменяет ордер"""

        if order_id not in self.orders:
            raise OrderError(f"Order {order_id} not found", context={"order_id": order_id})

        order = self.orders[order_id]
        if order.status != 'pending':
            raise OrderError(f"Order {order_id} is not pending (status: {order.status})")

        order.status = 'cancelled'
        if order in self.pending_orders:
            self.pending_orders.remove(order)
        self.cancelled_orders.append(order)
        self.order_stats['cancelled_orders'] += 1

        logger.info("Order cancelled: %s", order_id)
        return True

    def modify_order(self, order_id: str, new_price: Optional[Decimal] = None, new_quantity: Optional[Decimal] = None) -> bool:
        """Изменяет ордер"""

        if order_id not in self.orders:
            raise OrderError(f"Order {order_id} not found", context={"order_id": order_id})

        order = self.orders[order_id]
        if order.status != 'pending':
            raise OrderError(f"Order {order_id} is not pending (status: {order.status})")

        # Обновляем параметры
        if new_price is not None:
            order.price = new_price
            if order.stop_price is not None:
                order.stop_price = new_price

        if new_quantity is not None:
            order.quantity = new_quantity

        logger.info("Order modified: %s", order_id)
        return True

    def process_orders(self, market_data: Dict):
        """Обрабатывает ордера с учетом рыночных данных"""

        for order in self.pending_orders.copy():
            try:
                # Обновляем цену для трейлинг-стоп ордеров
                if order.trailing_stop:
                    self._update_trailing_stop(order, market_data)

                # Проверяем условия исполнения
                if self._should_fill_order(order, market_data):
                    self._fill_order(order, market_data)

            except Exception as e:
                logger.error("Error processing order %s: %s", order.order_id, e, exc_info=True)

    def _update_trailing_stop(self, order: Order, market_data: Dict):
        """Обновляет трейлинг-стоп ордер"""

        if not order.trailing_stop:
            return

        symbol = order.symbol
        price_val = market_data.get(symbol, {}).get('price', 0)
        current_price = Decimal(str(price_val)) if price_val else Decimal("0")

        if current_price == Decimal("0"):
            return

        # Обновляем максимальную/минимальную цену
        if order.side == 'sell':
            if current_price > order.max_price:
                order.max_price = current_price
                # Обновляем стоп-цену
                new_stop_price = current_price * (Decimal("1") - order.trailing_distance)
                if order.stop_price is None or new_stop_price > order.stop_price:
                    order.stop_price = new_stop_price
                    order.price = new_stop_price
        else:  # buy
            if current_price < order.min_price:
                order.min_price = current_price
                # Обновляем стоп-цену
                new_stop_price = current_price * (Decimal("1") + order.trailing_distance)
                if order.stop_price is None or new_stop_price < order.stop_price:
                    order.stop_price = new_stop_price
                    order.price = new_stop_price

    def _should_fill_order(self, order: Order, market_data: Dict) -> bool:
        """Проверяет, должен ли ордер быть исполнен"""

        symbol = order.symbol
        price_val = market_data.get(symbol, {}).get('price', 0)
        current_price = Decimal(str(price_val)) if price_val else Decimal("0")

        if current_price == Decimal("0"):
            return False

        if order.order_type == 'market':
            return True

        elif order.order_type == 'limit':
            if order.side == 'buy':
                return current_price <= order.price
            else:
                return current_price >= order.price

        elif order.order_type in ['stop', 'stop_limit']:
            if order.stop_price is None:
                return False
            if order.side == 'buy':
                return current_price >= order.stop_price
            else:
                return current_price <= order.stop_price

        return False

    def _fill_order(self, order: Order, market_data: Dict):
        """Исполняет ордер и записывает проскальзывание"""

        symbol = order.symbol
        price_val = market_data.get(symbol, {}).get('price', 0)
        current_price = Decimal(str(price_val)) if price_val else Decimal("0")

        if current_price == Decimal("0"):
            logger.error("Cannot fill order %s: no current price", order.order_id)
            return

        # Исполняем ордер
        order.status = 'filled'
        order.filled_time = get_utc_now()
        order.filled_price = current_price
        order.filled_quantity = order.quantity

        # Рассчитываем комиссию
        try:
            order.commission = order.filled_quantity * order.filled_price * self.order_settings['commission_rate']
        except Exception as e:
            raise FinancialError(f"Failed to calculate commission for order {order.order_id}: {e}") from e

        # Записываем проскальзывание
        try:
            slippage_manager = get_slippage_manager()

            expected_price = order.price
            actual_price = order.filled_price
            order_size_usd = order.filled_quantity * order.filled_price

            # Получаем дополнительные данные из market_data
            volume_24h = market_data.get(symbol, {}).get('volume_24h')
            volatility = market_data.get(symbol, {}).get('volatility')

            slippage_manager.record_slippage(
                symbol=symbol,
                side=order.side,
                expected_price=float(expected_price),
                actual_price=float(actual_price),
                volume_24h=volume_24h,
                order_size_usd=float(order_size_usd),
                volatility=volatility,
                order_id=order.order_id
            )
        except Exception as e:
            logger.debug("Не удалось записать проскальзывание для %s: %s", order.order_id, e)

        # Перемещаем в исполненные
        if order in self.pending_orders:
            self.pending_orders.remove(order)
        self.filled_orders.append(order)
        self.order_stats['filled_orders'] += 1

        # Обновляем статистику времени исполнения
        fill_time = (order.filled_time - order.created_time).total_seconds()
        self._update_fill_time_stats(fill_time)

        logger.info(
            "Order filled: %s %s %s %.4f @ %.4f",
            order.order_id, order.symbol, order.side, float(order.filled_quantity), float(order.filled_price)
        )

    def _update_fill_time_stats(self, fill_time: float):
        """Обновляет статистику времени исполнения"""

        if self.order_stats['filled_orders'] == 1:
            self.order_stats['avg_fill_time'] = fill_time
        else:
            # Скользящее среднее
            alpha = 0.1
            self.order_stats['avg_fill_time'] = (
                alpha * fill_time +
                (1 - alpha) * self.order_stats['avg_fill_time']
            )

    def _check_order_limits(self, order: Order) -> bool:
        """Проверяет лимиты ордеров"""

        # Проверяем лимит ордеров на символ
        symbol_orders = [o for o in self.pending_orders if o.symbol == order.symbol]
        if len(symbol_orders) >= self.order_settings['max_orders_per_symbol']:
            logger.error("Too many orders for symbol %s", order.symbol)
            return False

        # Проверяем лимит ордеров на пользователя
        if order.user_id:
            user_orders = [o for o in self.pending_orders if o.user_id == order.user_id]
            if len(user_orders) >= self.order_settings['max_orders_per_user']:
                logger.error("Too many orders for user %s", order.user_id)
                return False

        return True

    def _check_price_reasonableness(self, order: Order) -> bool:
        """Проверяет разумность цены ордера"""

        current_price = self._get_current_price(order.symbol)
        if current_price is None:
            return True  # Не можем проверить

        # Проверяем, что цена не слишком далеко от текущей
        price_diff = abs(order.price - current_price) / current_price

        if price_diff > Decimal("0.1"):  # 10% отклонение
            logger.warning(
                "Order price %.4f is far from current price %.4f",
                float(order.price), float(current_price)
            )
            return False

        return True

    def _get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Получает текущую цену символа (интеграция с биржей)"""
        # В реальной системе здесь будет вызов API биржи
        # Для демонстрации пытаемся найти цену в стакане
        if symbol in self.order_books:
            book = self.order_books[symbol]
            if book.asks and book.bids:
                return (book.asks[0][0] + book.bids[0][0]) / Decimal("2")
        return None

    def _generate_order_id(self) -> str:
        """Генерирует уникальный ID ордера"""

        timestamp = int(get_utc_now().timestamp() * 1000)
        random_part = np.random.randint(1000, 9999)
        return f"ORD_{timestamp}_{random_part}"

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Возвращает статус ордера"""

        if order_id not in self.orders:
            return None

        order = self.orders[order_id]
        return {
            'order_id': order.order_id,
            'symbol': order.symbol,
            'side': order.side,
            'order_type': order.order_type,
            'quantity': float(order.quantity),
            'price': float(order.price),
            'status': order.status,
            'created_time': order.created_time.isoformat(),
            'filled_time': order.filled_time.isoformat() if order.filled_time else None,
            'filled_price': float(order.filled_price) if order.filled_price is not None else None,
            'filled_quantity': float(order.filled_quantity),
            'commission': float(order.commission)
        }

    def get_orders_by_user(self, user_id: str) -> List[Dict]:
        """Возвращает ордера пользователя"""

        user_orders = [o for o in self.orders.values() if o.user_id == user_id]
        return [self.get_order_status(o.order_id) for o in user_orders]

    def get_orders_by_symbol(self, symbol: str) -> List[Dict]:
        """Возвращает ордера по символу"""

        symbol_orders = [o for o in self.orders.values() if o.symbol == symbol]
        return [self.get_order_status(o.order_id) for o in symbol_orders]

    def get_order_statistics(self) -> Dict:
        """Возвращает статистику ордеров"""

        # Рассчитываем fill rate
        if self.order_stats['total_orders'] > 0:
            self.order_stats['fill_rate'] = (
                self.order_stats['filled_orders'] / self.order_stats['total_orders']
            ) * 100

        return {
            'order_stats': self.order_stats,
            'pending_orders_count': len(self.pending_orders),
            'filled_orders_count': len(self.filled_orders),
            'cancelled_orders_count': len(self.cancelled_orders),
            'orders_by_symbol': self._get_orders_by_symbol_stats(),
            'orders_by_user': self._get_orders_by_user_stats(),
            'timestamp': get_utc_now().isoformat()
        }

    def _get_orders_by_symbol_stats(self) -> Dict:
        """Статистика ордеров по символам"""

        symbol_stats = defaultdict(lambda: {
            'total_orders': 0,
            'filled_orders': 0,
            'pending_orders': 0,
            'cancelled_orders': 0
        })

        for order in self.orders.values():
            symbol_stats[order.symbol]['total_orders'] += 1
            symbol_stats[order.symbol][f'{order.status}_orders'] += 1

        return dict(symbol_stats)

    def _get_orders_by_user_stats(self) -> Dict:
        """Статистика ордеров по пользователям"""

        user_stats = defaultdict(lambda: {
            'total_orders': 0,
            'filled_orders': 0,
            'pending_orders': 0,
            'cancelled_orders': 0
        })

        for order in self.orders.values():
            if order.user_id:
                user_stats[order.user_id]['total_orders'] += 1
                user_stats[order.user_id][f'{order.status}_orders'] += 1

        return dict(user_stats)

    def cleanup_old_orders(self, max_age_hours: int = 24):
        """Очищает старые ордера"""

        cutoff_time = get_utc_now() - timedelta(hours=max_age_hours)

        old_orders = [
            order for order in self.pending_orders
            if order.created_time < cutoff_time
        ]

        for order in old_orders:
            order.status = 'cancelled'
            if order in self.pending_orders:
                self.pending_orders.remove(order)
            self.cancelled_orders.append(order)
            self.order_stats['cancelled_orders'] += 1

        if old_orders:
            logger.info("Cleaned up %d old orders", len(old_orders))

    def save_state(self, filepath: str = 'order_manager_state.json'):
        """Сохраняет состояние системы"""

        state = {
            'orders': {k: v.__dict__ for k, v in self.orders.items()},
            'order_stats': self.order_stats,
            'order_settings': self.order_settings,
            'trailing_stop_settings': self.trailing_stop_settings
        }

        # Конвертируем datetime и Decimal в строки/float для JSON
        for order_data in state['orders'].values():
            for key, val in order_data.items():
                if isinstance(val, Decimal):
                    order_data[key] = float(val)
                elif isinstance(val, datetime):
                    order_data[key] = val.isoformat()

        # Также настройки
        for key, val in state['order_settings'].items():
            if isinstance(val, Decimal):
                state['order_settings'][key] = float(val)
        
        for key, val in state['trailing_stop_settings'].items():
            if isinstance(val, Decimal):
                state['trailing_stop_settings'][key] = float(val)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

        logger.info("Order manager state saved to %s", filepath)

    def load_state(self, filepath: str = 'order_manager_state.json'):
        """Загружает состояние системы"""

        if not os.path.exists(filepath):
            logger.warning("State file %s not found", filepath)
            return

        with open(filepath, 'r', encoding='utf-8') as f:
            state = json.load(f)

        # Восстанавливаем ордера
        if state.get('orders'):
            self.orders = {}
            for k, v in state['orders'].items():
                if v.get('created_time'):
                    v['created_time'] = datetime.fromisoformat(v['created_time'])
                if v.get('filled_time'):
                    v['filled_time'] = datetime.fromisoformat(v['filled_time'])
                
                # Конвертируем обратно в Decimal
                for field_name in ['quantity', 'price', 'stop_price', 'filled_price', 
                                 'filled_quantity', 'commission', 'trailing_distance', 
                                 'max_price', 'min_price']:
                    if v.get(field_name) is not None:
                        v[field_name] = Decimal(str(v[field_name]))
                
                self.orders[k] = Order(**v)

        # Восстанавливаем настройки (с конвертацией в Decimal)
        if state.get('order_settings'):
            self.order_settings = state['order_settings']
            for key in ['slippage_tolerance', 'commission_rate']:
                if key in self.order_settings:
                    self.order_settings[key] = Decimal(str(self.order_settings[key]))

        if state.get('trailing_stop_settings'):
            self.trailing_stop_settings = state['trailing_stop_settings']
            for key in ['min_distance', 'max_distance', 'step_size', 'activation_threshold']:
                if key in self.trailing_stop_settings:
                    self.trailing_stop_settings[key] = Decimal(str(self.trailing_stop_settings[key]))

        # Восстанавливаем списки ордеров
        self.pending_orders = [o for o in self.orders.values() if o.status == 'pending']
        self.filled_orders = [o for o in self.orders.values() if o.status == 'filled']
        self.cancelled_orders = [o for o in self.orders.values() if o.status == 'cancelled']

        logger.info("Order manager state loaded from %s", filepath)

# Глобальный экземпляр
order_manager = OrderManager()
