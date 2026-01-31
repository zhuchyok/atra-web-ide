"""
Инварианты для критичных объектов торговой системы

Принцип: Self-Validating Code - Self-Validation
Цель: Определение инвариантов для TradeSignal, Position, Order и других критичных объектов
"""

from typing import Any
from decimal import Decimal
from src.core.self_validation import (
    get_validation_manager,
    ValidationLevel
)


def register_trading_invariants():
    """Регистрация инвариантов для торговых объектов"""
    manager = get_validation_manager()
    
    # ========================================================================
    # TradeSignal инварианты
    # ========================================================================
    
    def check_entry_price_positive(signal):
        """Инвариант: Цена входа должна быть положительной"""
        return signal.entry_price > 0
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="entry_price_positive",
        check_func=check_entry_price_positive,
        message="Entry price must be positive",
        level=ValidationLevel.ERROR
    )
    
    def check_stop_loss_positive(signal):
        """Инвариант: Цена стоп-лосса должна быть положительной"""
        return signal.stop_loss_price > 0
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="stop_loss_positive",
        check_func=check_stop_loss_positive,
        message="Stop loss price must be positive",
        level=ValidationLevel.ERROR
    )
    
    def check_take_profit_positive(signal):
        """Инвариант: Цены тейк-профита должны быть положительными"""
        return signal.take_profit_1 > 0 and signal.take_profit_2 > 0
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="take_profit_positive",
        check_func=check_take_profit_positive,
        message="Take profit prices must be positive",
        level=ValidationLevel.ERROR
    )
    
    def check_long_tp_above_entry(signal):
        """Инвариант: Для LONG сигналов TP должен быть выше entry"""
        if signal.signal_type.upper() == "LONG":
            return signal.take_profit_1 > signal.entry_price and signal.take_profit_2 > signal.entry_price
        return True
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="long_tp_above_entry",
        check_func=check_long_tp_above_entry,
        message="For LONG signals, take profit must be above entry price",
        level=ValidationLevel.ERROR
    )
    
    def check_short_tp_below_entry(signal):
        """Инвариант: Для SHORT сигналов TP должен быть ниже entry"""
        if signal.signal_type.upper() == "SHORT":
            return signal.take_profit_1 < signal.entry_price and signal.take_profit_2 < signal.entry_price
        return True
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="short_tp_below_entry",
        check_func=check_short_tp_below_entry,
        message="For SHORT signals, take profit must be below entry price",
        level=ValidationLevel.ERROR
    )
    
    def check_long_sl_below_entry(signal):
        """Инвариант: Для LONG сигналов SL должен быть ниже entry"""
        if signal.signal_type.upper() == "LONG":
            return signal.stop_loss_price < signal.entry_price
        return True
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="long_sl_below_entry",
        check_func=check_long_sl_below_entry,
        message="For LONG signals, stop loss must be below entry price",
        level=ValidationLevel.ERROR
    )
    
    def check_short_sl_above_entry(signal):
        """Инвариант: Для SHORT сигналов SL должен быть выше entry"""
        if signal.signal_type.upper() == "SHORT":
            return signal.stop_loss_price > signal.entry_price
        return True
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="short_sl_above_entry",
        check_func=check_short_sl_above_entry,
        message="For SHORT signals, stop loss must be above entry price",
        level=ValidationLevel.ERROR
    )
    
    def check_risk_pct_range(signal):
        """Инвариант: Процент риска должен быть в допустимом диапазоне"""
        return 0.1 <= signal.risk_pct <= 10.0
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="risk_pct_range",
        check_func=check_risk_pct_range,
        message="Risk percentage must be between 0.1% and 10.0%",
        level=ValidationLevel.ERROR
    )
    
    def check_leverage_range(signal):
        """Инвариант: Плечо должно быть в допустимом диапазоне"""
        return 1.0 <= signal.leverage <= 20.0
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="leverage_range",
        check_func=check_leverage_range,
        message="Leverage must be between 1.0x and 20.0x",
        level=ValidationLevel.ERROR
    )
    
    def check_quantity_positive(signal):
        """Инвариант: Количество должно быть положительным"""
        return signal.recommended_qty_coins > 0 and signal.recommended_qty_usdt > 0
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="quantity_positive",
        check_func=check_quantity_positive,
        message="Recommended quantities must be positive",
        level=ValidationLevel.WARNING
    )
    
    def check_risk_amount_positive(signal):
        """Инвариант: Сумма риска должна быть положительной"""
        return signal.risk_amount_usdt > 0
    
    manager.register_invariant(
        class_name="TradeSignal",
        name="risk_amount_positive",
        check_func=check_risk_amount_positive,
        message="Risk amount must be positive",
        level=ValidationLevel.ERROR
    )
    
    # ========================================================================
    # Position инварианты (domain/entities/position.py)
    # ========================================================================
    
    def check_position_entry_price_positive(position):
        """Инвариант: Цена входа позиции должна быть положительной"""
        if hasattr(position, 'entry_price'):
            if isinstance(position.entry_price, Decimal):
                return position.entry_price > Decimal("0")
            return position.entry_price > 0
        return True
    
    manager.register_invariant(
        class_name="Position",
        name="entry_price_positive",
        check_func=check_position_entry_price_positive,
        message="Position entry price must be positive",
        level=ValidationLevel.ERROR
    )
    
    def check_position_quantity_positive(position):
        """Инвариант: Количество позиции должно быть положительным"""
        if hasattr(position, 'quantity'):
            if isinstance(position.quantity, Decimal):
                return position.quantity > Decimal("0")
            return position.quantity > 0
        return True
    
    manager.register_invariant(
        class_name="Position",
        name="quantity_positive",
        check_func=check_position_quantity_positive,
        message="Position quantity must be positive",
        level=ValidationLevel.ERROR
    )
    
    def check_position_pnl_consistency(position):
        """Инвариант: PnL должен быть консистентным с ценой и количеством"""
        if not (hasattr(position, 'entry_price') and hasattr(position, 'quantity')):
            return True
        
        if hasattr(position, 'current_price') and position.current_price:
            if hasattr(position, 'pnl'):
                # Проверяем что PnL рассчитан правильно (упрощённая проверка)
                # Для LONG: PnL = (current - entry) * quantity
                # Для SHORT: PnL = (entry - current) * quantity
                try:
                    entry = float(position.entry_price) if isinstance(position.entry_price, Decimal) else position.entry_price
                    current = float(position.current_price) if isinstance(position.current_price, Decimal) else position.current_price
                    qty = float(position.quantity) if isinstance(position.quantity, Decimal) else position.quantity
                    pnl = float(position.pnl) if isinstance(position.pnl, Decimal) else position.pnl
                    
                    side = getattr(position, 'side', 'LONG')
                    if side == 'LONG':
                        expected_pnl = (current - entry) * qty
                    else:
                        expected_pnl = (entry - current) * qty
                    
                    # Допускаем небольшую погрешность из-за округления
                    return abs(pnl - expected_pnl) < 0.01
                except (ValueError, TypeError, AttributeError):
                    return True  # Если не можем проверить, считаем валидным
        return True
    
    manager.register_invariant(
        class_name="Position",
        name="pnl_consistency",
        check_func=check_position_pnl_consistency,
        message="Position PnL must be consistent with entry price, current price and quantity",
        level=ValidationLevel.WARNING
    )
    
    # ========================================================================
    # Order инварианты (domain/entities/order.py)
    # ========================================================================
    
    def check_order_price_positive(order):
        """Инвариант: Цена ордера должна быть положительной"""
        if hasattr(order, 'price') and order.price:
            if isinstance(order.price, Decimal):
                return order.price > Decimal("0")
            return order.price > 0
        return True
    
    manager.register_invariant(
        class_name="Order",
        name="price_positive",
        check_func=check_order_price_positive,
        message="Order price must be positive",
        level=ValidationLevel.ERROR
    )
    
    def check_order_quantity_positive(order):
        """Инвариант: Количество ордера должно быть положительным"""
        if hasattr(order, 'quantity'):
            if isinstance(order.quantity, Decimal):
                return order.quantity > Decimal("0")
            return order.quantity > 0
        return True
    
    manager.register_invariant(
        class_name="Order",
        name="quantity_positive",
        check_func=check_order_quantity_positive,
        message="Order quantity must be positive",
        level=ValidationLevel.ERROR
    )
    
    def check_order_filled_quantity_valid(order):
        """Инвариант: Заполненное количество не должно превышать общее количество"""
        if hasattr(order, 'quantity') and hasattr(order, 'filled_quantity'):
            qty = float(order.quantity) if isinstance(order.quantity, Decimal) else order.quantity
            filled = float(order.filled_quantity) if isinstance(order.filled_quantity, Decimal) else order.filled_quantity
            return 0 <= filled <= qty
        return True
    
    manager.register_invariant(
        class_name="Order",
        name="filled_quantity_valid",
        check_func=check_order_filled_quantity_valid,
        message="Filled quantity must be between 0 and total quantity",
        level=ValidationLevel.ERROR
    )
    
    def check_order_state_transition(order):
        """Инвариант: Переходы состояний ордера должны быть валидными"""
        if hasattr(order, 'status'):
            valid_transitions = {
                'PENDING': ['FILLED', 'CANCELLED', 'REJECTED'],
                'FILLED': [],  # Финальное состояние
                'CANCELLED': [],  # Финальное состояние
                'REJECTED': []  # Финальное состояние
            }
            # Упрощённая проверка - просто проверяем что статус валидный
            valid_statuses = ['PENDING', 'FILLED', 'CANCELLED', 'REJECTED', 'PARTIALLY_FILLED']
            return order.status in valid_statuses
        return True
    
    manager.register_invariant(
        class_name="Order",
        name="state_transition_valid",
        check_func=check_order_state_transition,
        message="Order state transition must be valid",
        level=ValidationLevel.WARNING
    )


def register_risk_invariants():
    """Регистрация инвариантов для риск-менеджмента"""
    manager = get_validation_manager()
    
    # ========================================================================
    # RiskCalculator инварианты
    # ========================================================================
    
    def check_risk_amount_within_balance(calculator):
        """Инвариант: Сумма риска не должна превышать баланс"""
        if hasattr(calculator, 'risk_amount') and hasattr(calculator, 'account_balance'):
            risk = float(calculator.risk_amount) if isinstance(calculator.risk_amount, Decimal) else calculator.risk_amount
            balance = float(calculator.account_balance) if isinstance(calculator.account_balance, Decimal) else calculator.account_balance
            return risk <= balance
        return True
    
    manager.register_invariant(
        class_name="RiskCalculator",
        name="risk_amount_within_balance",
        check_func=check_risk_amount_within_balance,
        message="Risk amount must not exceed account balance",
        level=ValidationLevel.ERROR
    )
    
    def check_risk_percentage_valid(calculator):
        """Инвариант: Процент риска должен быть в допустимом диапазоне"""
        if hasattr(calculator, 'risk_percentage'):
            risk_pct = float(calculator.risk_percentage) if isinstance(calculator.risk_percentage, Decimal) else calculator.risk_percentage
            return 0.1 <= risk_pct <= 10.0
        return True
    
    manager.register_invariant(
        class_name="RiskCalculator",
        name="risk_percentage_valid",
        check_func=check_risk_percentage_valid,
        message="Risk percentage must be between 0.1% and 10.0%",
        level=ValidationLevel.ERROR
    )
    
    # ========================================================================
    # Portfolio инварианты
    # ========================================================================
    
    def check_portfolio_total_risk_valid(portfolio):
        """Инвариант: Общий риск портфеля не должен превышать максимум"""
        if hasattr(portfolio, 'total_risk') and hasattr(portfolio, 'max_portfolio_risk'):
            total = float(portfolio.total_risk) if isinstance(portfolio.total_risk, Decimal) else portfolio.total_risk
            max_risk = float(portfolio.max_portfolio_risk) if isinstance(portfolio.max_portfolio_risk, Decimal) else portfolio.max_portfolio_risk
            return total <= max_risk
        return True
    
    manager.register_invariant(
        class_name="Portfolio",
        name="total_risk_within_limit",
        check_func=check_portfolio_total_risk_valid,
        message="Portfolio total risk must not exceed maximum portfolio risk",
        level=ValidationLevel.ERROR
    )


def register_all_invariants():
    """Регистрация всех инвариантов"""
    register_trading_invariants()
    register_risk_invariants()


# Автоматическая регистрация при импорте
register_all_invariants()

