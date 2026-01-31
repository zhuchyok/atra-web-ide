"""
Валидация конфигураций системы

Регистрация правил валидации для всех конфигураций
"""

import logging
from src.core.config_validator import (
    ConfigValidator,
    get_config_validator
)
from src.shared.config.settings import (
    RiskSettings,
    SignalSettings,
    DatabaseSettings,
    ExchangeSettings
)

logger = logging.getLogger(__name__)


def register_config_validations():
    """Регистрация правил валидации для всех конфигураций"""
    validator = get_config_validator()
    
    # ========================================================================
    # RiskSettings валидация
    # ========================================================================
    
    validator.add_rule(
        RiskSettings,
        "max_risk_per_trade",
        "range",
        "max_risk_per_trade must be between 0.1 and 10.0",
        validator=lambda x: 0.1 <= float(x) <= 10.0
    )
    
    validator.add_rule(
        RiskSettings,
        "max_portfolio_risk",
        "range",
        "max_portfolio_risk must be between 1.0 and 50.0",
        validator=lambda x: 1.0 <= float(x) <= 50.0
    )
    
    validator.add_rule(
        RiskSettings,
        "max_positions",
        "range",
        "max_positions must be between 1 and 100",
        validator=lambda x: 1 <= int(x) <= 100
    )
    
    # ========================================================================
    # SignalSettings валидация
    # ========================================================================
    
    validator.add_rule(
        SignalSettings,
        "signal_expiry_minutes",
        "range",
        "signal_expiry_minutes must be between 1 and 1440 (24 hours)",
        validator=lambda x: 1 <= int(x) <= 1440
    )
    
    validator.add_rule(
        SignalSettings,
        "min_confidence",
        "range",
        "min_confidence must be between 0.0 and 1.0",
        validator=lambda x: 0.0 <= float(x) <= 1.0
    )
    
    # ========================================================================
    # DatabaseSettings валидация
    # ========================================================================
    
    validator.add_rule(
        DatabaseSettings,
        "pool_size",
        "range",
        "pool_size must be between 1 and 100",
        validator=lambda x: 1 <= int(x) <= 100
    )
    
    validator.add_rule(
        DatabaseSettings,
        "timeout",
        "range",
        "timeout must be between 1 and 300 seconds",
        validator=lambda x: 1 <= int(x) <= 300
    )
    
    # ========================================================================
    # ExchangeSettings валидация
    # ========================================================================
    
    validator.add_rule(
        ExchangeSettings,
        "exchange_name",
        "custom",
        "exchange_name must be one of: bitget, binance, bybit, okx",
        validator=lambda x, config: x.lower() in ["bitget", "binance", "bybit", "okx"]
    )
    
    logger.info("Config validations registered")


# Автоматическая регистрация при импорте
try:
    register_config_validations()
except Exception as e:
    logger.warning(f"Failed to register config validations: {e}")

