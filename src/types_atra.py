"""
Type definitions for ATRA trading system
Типизация для торговой системы ATRA
"""

from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
import pandas as pd


# =============================================================================
# DATA TYPES
# =============================================================================

# DataFrame с данными рынка
MarketData = pd.DataFrame

# Словарь с данными сигнала
SignalData = Dict[str, Any]

# Словарь с техническими индикаторами
IndicatorData = Dict[str, Union[float, int, bool]]

# Словарь с данными пользователя
UserData = Dict[str, Any]

# =============================================================================
# SIGNAL TYPES
# =============================================================================

class SignalResult:
    """Результат генерации сигнала"""

    def __init__(
        self,
        signal: Optional[str],
        reason: str,
        strength: str = "medium",
        confidence: str = "medium"
    ):
        self.signal = signal  # "LONG", "SHORT" или None
        self.reason = reason
        self.strength = strength  # "high", "medium", "low"
        self.confidence = confidence  # "high", "medium", "low"
        from src.shared.utils.datetime_utils import get_utc_now
        self.timestamp = get_utc_now()

    def __bool__(self) -> bool:
        return self.signal is not None

    def __str__(self) -> str:
        return f"SignalResult(signal={self.signal}, strength={self.strength}, confidence={self.confidence})"


class TradeSignal:
    """Полные данные торгового сигнала"""

    def __init__(
        self,
        symbol: str,
        signal_type: str,  # "LONG" или "SHORT"
        entry_price: float,
        stop_loss_price: float,
        take_profit_1: float,
        take_profit_2: float,
        risk_pct: float,
        leverage: float,
        recommended_qty_coins: float,
        recommended_qty_usdt: float,
        risk_amount_usdt: float,
        strength: str = "medium",
        reason: str = "",
        indicators: Optional[IndicatorData] = None,
        trend_analysis: Optional[Dict[str, Any]] = None,
        user_id: str = "",
        filter_mode: str = "strict"
    ):
        self.symbol = symbol
        self.signal_type = signal_type
        self.entry_price = entry_price
        self.stop_loss_price = stop_loss_price
        self.take_profit_1 = take_profit_1
        self.take_profit_2 = take_profit_2
        self.risk_pct = risk_pct
        self.leverage = leverage
        self.recommended_qty_coins = recommended_qty_coins
        self.recommended_qty_usdt = recommended_qty_usdt
        self.risk_amount_usdt = risk_amount_usdt
        self.strength = strength
        self.reason = reason
        self.indicators = indicators or {}
        self.trend_analysis = trend_analysis or {}
        self.user_id = user_id
        self.filter_mode = filter_mode
        from src.shared.utils.datetime_utils import get_utc_now
        self.timestamp = get_utc_now().isoformat()
        self.confidence = self._calculate_confidence()
        
        # Self-validation: проверяем инварианты после создания
        try:
            from src.core.self_validation import get_validation_manager
            from src.core.invariants import register_all_invariants
            register_all_invariants()
            manager = get_validation_manager()
            results = manager.validate_object(self, "TradeSignal")
            # Логируем нарушения, но не прерываем создание (fail-soft)
            for result in results:
                if not result.passed:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"TradeSignal invariant violated: {result.message}")
        except Exception:
            pass  # Игнорируем ошибки валидации при создании

    def _calculate_confidence(self) -> str:
        """Расчет уверенности в сигнале"""
        score = 0

        # Оценка по силе сигнала
        if self.strength == "high":
            score += 3
        elif self.strength == "medium":
            score += 2
        else:
            score += 1

        # Оценка по риску (меньший риск = выше уверенность)
        if self.risk_pct <= 2.0:
            score += 2
        elif self.risk_pct <= 4.0:
            score += 1

        # Оценка по плечу (умеренное плечо = выше уверенность)
        if 1.0 <= self.leverage <= 5.0:
            score += 2
        elif self.leverage <= 10.0:
            score += 1

        # Определение уровня уверенности
        if score >= 6:
            return "high"
        elif score >= 4:
            return "medium"
        else:
            return "low"

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "symbol": self.symbol,
            "signal": self.signal_type,
            "entry_price": self.entry_price,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "risk_pct": self.risk_pct,
            "leverage": self.leverage,
            "recommended_qty_coins": self.recommended_qty_coins,
            "recommended_qty_usdt": self.recommended_qty_usdt,
            "risk_amount_usdt": self.risk_amount_usdt,
            "strength": self.strength,
            "reason": self.reason,
            "indicators": self.indicators,
            "trend_analysis": self.trend_analysis,
            "user_id": self.user_id,
            "filter_mode": self.filter_mode,
            "timestamp": self.timestamp,
            "confidence": self.confidence
        }

    def __str__(self) -> str:
        return f"TradeSignal({self.symbol} {self.signal_type}@{self.entry_price}, risk={self.risk_pct}%, lev={self.leverage}x)"


# =============================================================================
# FILTER TYPES
# =============================================================================

class FilterResult:
    """Результат работы фильтра"""

    def __init__(self, passed: bool, reason: str = "", details: Dict[str, Any] = None):
        self.passed = passed
        self.reason = reason
        self.details = details or {}
        from src.shared.utils.datetime_utils import get_utc_now
        self.timestamp = get_utc_now()

    def __bool__(self) -> bool:
        return self.passed

    def __str__(self) -> str:
        return f"FilterResult(passed={self.passed}, reason='{self.reason}')"


# =============================================================================
# DCA TYPES
# =============================================================================

class DCAResult:
    """Результат DCA анализа"""

    def __init__(
        self,
        can_dca: bool,
        reason: str,
        new_qty: float = 0.0,
        total_qty: float = 0.0,
        new_avg_price: float = 0.0,
        profit_targets: Optional[Dict[str, float]] = None,
        dca_count: int = 0,
        loss_pct: float = 0.0
    ):
        self.can_dca = can_dca
        self.reason = reason
        self.new_qty = new_qty
        self.total_qty = total_qty
        self.new_avg_price = new_avg_price
        self.profit_targets = profit_targets or {}
        self.dca_count = dca_count
        self.loss_pct = loss_pct

    def __bool__(self) -> bool:
        return self.can_dca


# =============================================================================
# API RESPONSE TYPES
# =============================================================================

class APIResponse:
    """Стандартизированный ответ API"""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        error: str = "",
        status_code: int = 200
    ):
        self.success = success
        self.data = data
        self.error = error
        self.status_code = status_code
        from src.shared.utils.datetime_utils import get_utc_now
        self.timestamp = get_utc_now()

    def __bool__(self) -> bool:
        return self.success


# =============================================================================
# CONFIGURATION TYPES
# =============================================================================

# Типы конфигурации
FilterConfig = Dict[str, Any]
IndicatorConfig = Dict[str, Union[int, float, bool]]
RiskConfig = Dict[str, Union[int, float, bool]]
LeverageConfig = Dict[str, Union[int, float, bool]]

# Общий тип конфигурации
SystemConfig = Dict[str, Union[
    FilterConfig,
    IndicatorConfig,
    RiskConfig,
    LeverageConfig
]]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def validate_signal_data(signal: TradeSignal) -> bool:
    """Валидация данных сигнала"""
    try:
        # Проверка обязательных полей
        required_fields = [
            "symbol", "signal_type", "entry_price", "stop_loss_price",
            "take_profit_1", "take_profit_2", "risk_pct", "leverage"
        ]

        for field in required_fields:
            if not hasattr(signal, field):
                print(f"Отсутствует обязательное поле: {field}")
                return False

            value = getattr(signal, field)
            if value is None:
                print(f"Поле {field} равно None")
                return False

        # Проверка числовых значений
        if signal.entry_price <= 0:
            print("Цена входа должна быть положительной")
            return False

        if signal.stop_loss_price <= 0:
            print("Цена стоп-лосса должна быть положительной")
            return False

        if not (0.1 <= signal.risk_pct <= 10.0):
            print("Процент риска должен быть в диапазоне 0.1-10.0")
            return False

        if not (1.0 <= signal.leverage <= 20.0):
            print("Плечо должно быть в диапазоне 1.0-20.0")
            return False

        return True

    except Exception as e:
        print(f"Ошибка валидации сигнала: {e}")
        return False


def create_signal_from_dict(data: Dict[str, Any]) -> TradeSignal:
    """Создание сигнала из словаря"""
    try:
        return TradeSignal(
            symbol=data["symbol"],
            signal_type=data["signal"],
            entry_price=data["entry_price"],
            stop_loss_price=data["stop_loss_price"],
            take_profit_1=data["take_profit_1"],
            take_profit_2=data["take_profit_2"],
            risk_pct=data["risk_pct"],
            leverage=data["leverage"],
            recommended_qty_coins=data["recommended_qty_coins"],
            recommended_qty_usdt=data["recommended_qty_usdt"],
            risk_amount_usdt=data["risk_amount_usdt"],
            strength=data.get("strength", "medium"),
            reason=data.get("reason", ""),
            indicators=data.get("indicators", {}),
            trend_analysis=data.get("trend_analysis", {}),
            user_id=data.get("user_id", ""),
            filter_mode=data.get("filter_mode", "strict")
        )
    except KeyError as e:
        raise ValueError(f"Отсутствует обязательное поле в данных сигнала: {e}")


# =============================================================================
# TYPE ALIASES
# =============================================================================

# Для обратной совместимости
SignalDict = SignalData
MarketDataFrame = MarketData
FilterConfigDict = FilterConfig
IndicatorDict = IndicatorData
UserConfigDict = UserData
