import logging
from typing import Dict, Any
from src.core.contracts import precondition, postcondition

logger = logging.getLogger(__name__)


class PositionSizeValidator:
    """Валидатор размера позиций для безопасности."""

    def __init__(self):
        # Лимиты безопасности
        self.MIN_ORDER_USDT = 5.0  # Минимум 5 USDT
        self.MAX_ORDER_USDT = 50000.0  # Максимум 50k USDT
        self.MAX_POSITION_PCT_OF_BALANCE = 25.0  # Макс 25% баланса на одну позицию
        self.MAX_TOTAL_EXPOSURE_PCT = 80.0  # Макс 80% баланса в позициях

    @precondition(
        lambda self, amount_usdt, user_balance, current_exposure_usdt: (
            amount_usdt >= 0 and
            user_balance >= 0 and
            current_exposure_usdt >= 0
        ),
        "Invalid input: amounts must be non-negative"
    )
    @postcondition(
        lambda result, self, amount_usdt, user_balance, current_exposure_usdt: (
            isinstance(result, dict) and
            'allowed' in result and
            'adjusted_amount' in result and
            'reason' in result and
            isinstance(result['allowed'], bool) and
            isinstance(result['adjusted_amount'], (int, float)) and
            result['adjusted_amount'] >= 0
        ),
        "Invalid output: result must be dict with 'allowed', 'adjusted_amount', 'reason'"
    )
    async def validate_order_size(self, amount_usdt: float, user_balance: float,
                                  current_exposure_usdt: float = 0.0) -> Dict[str, Any]:
        """
        Валидирует размер ордера перед исполнением.
        
        Returns:
            {
                'allowed': bool,
                'adjusted_amount': float,
                'reason': str
            }
        """
        try:
            # 1. Минимум
            if amount_usdt < self.MIN_ORDER_USDT:
                return {
                    'allowed': False,
                    'adjusted_amount': 0.0,
                    'reason': f'Сумма меньше минимума ({self.MIN_ORDER_USDT} USDT)'
                }

            # 2. Максимум абсолютный
            if amount_usdt > self.MAX_ORDER_USDT:
                return {
                    'allowed': True,
                    'adjusted_amount': self.MAX_ORDER_USDT,
                    'reason': f'Сумма скорректирована до максимума ({self.MAX_ORDER_USDT} USDT)'
                }

            # 3. Процент от баланса
            if user_balance > 0:
                max_position_usdt = user_balance * (self.MAX_POSITION_PCT_OF_BALANCE / 100.0)
                if amount_usdt > max_position_usdt:
                    return {
                        'allowed': True,
                        'adjusted_amount': max_position_usdt,
                        'reason': f'Сумма скорректирована до {self.MAX_POSITION_PCT_OF_BALANCE}% баланса'
                    }

            # 4. Общая экспозиция
            if user_balance > 0:
                max_total_exposure = user_balance * (self.MAX_TOTAL_EXPOSURE_PCT / 100.0)
                new_total_exposure = current_exposure_usdt + amount_usdt
                if new_total_exposure > max_total_exposure:
                    available_room = max(0.0, max_total_exposure - current_exposure_usdt)
                    if available_room < self.MIN_ORDER_USDT:
                        return {
                            'allowed': False,
                            'adjusted_amount': 0.0,
                            'reason': f'Превышен лимит общей экспозиции ({self.MAX_TOTAL_EXPOSURE_PCT}% баланса)'
                        }
                    return {
                        'allowed': True,
                        'adjusted_amount': available_room,
                        'reason': 'Сумма скорректирована по лимиту экспозиции'
                    }

            # Всё ОК
            return {
                'allowed': True,
                'adjusted_amount': amount_usdt,
                'reason': 'Размер позиции валиден'
            }

        except Exception as e:
            logger.error("❌ Ошибка валидации размера: %s", e)
            return {
                'allowed': False,
                'adjusted_amount': 0.0,
                'reason': f'Ошибка валидации: {e}'
            }


_validator_instance = None


def get_position_validator():
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = PositionSizeValidator()
    return _validator_instance

