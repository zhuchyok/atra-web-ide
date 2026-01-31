"""
Финансовая валидация и аудит.

Модуль для проверки правильности всех финансовых расчетов:
- Валидация использования Decimal
- Проверка расчетов прибыли/убытков
- Валидация комиссий
- Проверка консистентности балансов
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Результат валидации"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


@dataclass
class AuditResult:
    """Результат аудита"""
    is_valid: bool
    issues: List[str]
    recommendations: List[str]


class FinancialValidator:
    """Валидатор финансовых расчетов"""
    
    def __init__(self):
        self.tolerance = Decimal("0.00000001")  # Минимальная точность
    
    def validate_decimal_usage(self, value: Any, field_name: str) -> ValidationResult:
        """
        Проверяет, что значение использует Decimal, а не float.
        
        Args:
            value: Значение для проверки
            field_name: Название поля для сообщений об ошибках
        
        Returns:
            ValidationResult с результатами проверки
        """
        errors = []
        warnings = []
        
        if isinstance(value, float):
            errors.append(
                f"{field_name} использует float вместо Decimal. "
                f"Это может привести к потере точности в финансовых расчетах."
            )
        elif not isinstance(value, Decimal):
            if value is None:
                warnings.append(f"{field_name} равно None")
            else:
                errors.append(
                    f"{field_name} имеет неверный тип: {type(value).__name__}. "
                    f"Ожидается Decimal."
                )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def validate_profit_calculation(
        self,
        entry_price: Decimal,
        exit_price: Decimal,
        quantity: Decimal,
        leverage: Decimal,
        trade_mode: str,
        fees: Decimal,
        calculated_profit: Decimal,
    ) -> ValidationResult:
        """
        Проверяет правильность расчета прибыли.
        
        Args:
            entry_price: Цена входа
            exit_price: Цена выхода
            quantity: Количество
            leverage: Плечо
            trade_mode: Режим торговли (spot/futures)
            fees: Комиссии
            calculated_profit: Рассчитанная прибыль для проверки
        
        Returns:
            ValidationResult с результатами проверки
        """
        errors = []
        warnings = []
        
        # Валидация типов
        validations = [
            self.validate_decimal_usage(entry_price, "entry_price"),
            self.validate_decimal_usage(exit_price, "exit_price"),
            self.validate_decimal_usage(quantity, "quantity"),
            self.validate_decimal_usage(leverage, "leverage"),
            self.validate_decimal_usage(fees, "fees"),
            self.validate_decimal_usage(calculated_profit, "calculated_profit"),
        ]
        
        for validation in validations:
            errors.extend(validation.errors)
            warnings.extend(validation.warnings)
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Проверяем расчет
        if trade_mode == "spot":
            price_diff = exit_price - entry_price
            gross_profit = price_diff * quantity
        else:
            price_diff = exit_price - entry_price
            gross_profit = price_diff * quantity * leverage
        
        net_profit = gross_profit - fees
        
        # Проверяем точность расчета
        difference = abs(net_profit - calculated_profit)
        if difference > self.tolerance:
            errors.append(
                f"Несоответствие расчета прибыли. "
                f"Ожидалось: {net_profit}, получено: {calculated_profit}, "
                f"разница: {difference}"
            )
        
        # Проверяем на NaN и infinity
        if calculated_profit.is_nan():
            errors.append("Прибыль не может быть NaN")
        
        if calculated_profit.is_infinite():
            errors.append("Прибыль не может быть бесконечной")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def validate_fee_calculation(
        self,
        price: Decimal,
        quantity: Decimal,
        commission_rate: Decimal,
        calculated_fee: Decimal,
    ) -> ValidationResult:
        """
        Проверяет правильность расчета комиссии.
        
        Args:
            price: Цена
            quantity: Количество
            commission_rate: Ставка комиссии
            calculated_fee: Рассчитанная комиссия для проверки
        
        Returns:
            ValidationResult с результатами проверки
        """
        errors = []
        warnings = []
        
        # Валидация типов
        validations = [
            self.validate_decimal_usage(price, "price"),
            self.validate_decimal_usage(quantity, "quantity"),
            self.validate_decimal_usage(commission_rate, "commission_rate"),
            self.validate_decimal_usage(calculated_fee, "calculated_fee"),
        ]
        
        for validation in validations:
            errors.extend(validation.errors)
            warnings.extend(validation.warnings)
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Проверяем расчет
        expected_fee = price * quantity * commission_rate
        
        # Проверяем точность
        difference = abs(expected_fee - calculated_fee)
        if difference > self.tolerance:
            errors.append(
                f"Несоответствие расчета комиссии. "
                f"Ожидалось: {expected_fee}, получено: {calculated_fee}, "
                f"разница: {difference}"
            )
        
        # Проверяем знак
        if calculated_fee < Decimal("0"):
            errors.append("Комиссия не может быть отрицательной")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def validate_balance_consistency(
        self,
        initial_balance: Decimal,
        transactions: List[Dict[str, Any]],
        expected_balance: Decimal,
    ) -> ValidationResult:
        """
        Проверяет консистентность баланса.
        
        Args:
            initial_balance: Начальный баланс
            transactions: Список транзакций
            expected_balance: Ожидаемый баланс
        
        Returns:
            ValidationResult с результатами проверки
        """
        errors = []
        warnings = []
        
        # Валидация типов
        validations = [
            self.validate_decimal_usage(initial_balance, "initial_balance"),
            self.validate_decimal_usage(expected_balance, "expected_balance"),
        ]
        
        for validation in validations:
            errors.extend(validation.errors)
            warnings.extend(validation.warnings)
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        # Рассчитываем баланс из транзакций
        calculated_balance = initial_balance
        
        for i, tx in enumerate(transactions):
            tx_type = tx.get('type')
            amount = tx.get('amount')
            
            if not isinstance(amount, Decimal):
                errors.append(
                    f"Транзакция {i}: amount должен быть Decimal, "
                    f"получен {type(amount).__name__}"
                )
                continue
            
            if tx_type == 'deposit':
                calculated_balance += amount
            elif tx_type == 'withdrawal':
                calculated_balance -= amount
            elif tx_type == 'trade':
                profit = tx.get('profit', Decimal("0"))
                fees = tx.get('fees', Decimal("0"))
                calculated_balance += profit - fees
            else:
                warnings.append(f"Транзакция {i}: неизвестный тип {tx_type}")
        
        # Проверяем консистентность
        difference = abs(calculated_balance - expected_balance)
        if difference > self.tolerance:
            errors.append(
                f"Несоответствие баланса. "
                f"Рассчитано: {calculated_balance}, ожидалось: {expected_balance}, "
                f"разница: {difference}"
            )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )


class FinancialAuditor:
    """Финансовый аудитор"""
    
    def __init__(self):
        self.validator = FinancialValidator()
    
    def audit_transaction(self, transaction: Dict[str, Any]) -> AuditResult:
        """
        Проводит аудит транзакции.
        
        Args:
            transaction: Транзакция для аудита
        
        Returns:
            AuditResult с результатами аудита
        """
        issues = []
        recommendations = []
        
        # Проверка типов данных
        amount = transaction.get('amount')
        if amount is not None:
            validation = self.validator.validate_decimal_usage(amount, "amount")
            if not validation.is_valid:
                issues.extend(validation.errors)
                recommendations.append("Использовать Decimal для всех финансовых значений")
        
        # Проверка знаков
        if transaction.get('type') == 'withdrawal' and amount is not None:
            if isinstance(amount, Decimal) and amount < Decimal("0"):
                issues.append("Сумма вывода не может быть отрицательной")
        
        # Проверка баланса
        balance_before = transaction.get('balance_before')
        balance_after = transaction.get('balance_after')
        
        if balance_before is not None and balance_after is not None:
            if isinstance(balance_before, Decimal) and isinstance(balance_after, Decimal):
                expected_balance = balance_before + (amount if transaction.get('type') == 'deposit' else -amount if transaction.get('type') == 'withdrawal' else Decimal("0"))
                difference = abs(balance_after - expected_balance)
                if difference > self.validator.tolerance:
                    issues.append(
                        f"Несоответствие баланса. "
                        f"Ожидалось: {expected_balance}, получено: {balance_after}"
                    )
        
        return AuditResult(
            is_valid=len(issues) == 0,
            issues=issues,
            recommendations=recommendations,
        )
    
    def audit_all_transactions(
        self,
        transactions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Проводит аудит всех транзакций.
        
        Args:
            transactions: Список транзакций
        
        Returns:
            Отчет об аудите
        """
        results = [self.audit_transaction(tx) for tx in transactions]
        
        total_issues = sum(len(r.issues) for r in results)
        valid_transactions = sum(1 for r in results if r.is_valid)
        
        return {
            "total_transactions": len(transactions),
            "valid_transactions": valid_transactions,
            "invalid_transactions": len(transactions) - valid_transactions,
            "total_issues": total_issues,
            "results": results,
        }


def get_financial_validator() -> FinancialValidator:
    """Получает валидатор финансовых расчетов (singleton)"""
    global _FINANCIAL_VALIDATOR
    if '_FINANCIAL_VALIDATOR' not in globals():
        _FINANCIAL_VALIDATOR = FinancialValidator()
    return _FINANCIAL_VALIDATOR


def get_financial_auditor() -> FinancialAuditor:
    """Получает финансового аудитора (singleton)"""
    global _FINANCIAL_AUDITOR
    if '_FINANCIAL_AUDITOR' not in globals():
        _FINANCIAL_AUDITOR = FinancialAuditor()
    return _FINANCIAL_AUDITOR

