"""
Settings - Configuration Management

Centralized configuration using Pydantic for validation.
"""

from pydantic import BaseSettings, Field
from typing import Optional
from decimal import Decimal


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    db_path: str = Field(default="trading.db", env="DB_PATH")
    pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    timeout: int = Field(default=30, env="DB_TIMEOUT")


class ExchangeSettings(BaseSettings):
    """Exchange configuration"""
    exchange_name: str = Field(default="bitget", env="EXCHANGE_NAME")
    api_key: Optional[str] = Field(default=None, env="EXCHANGE_API_KEY")
    api_secret: Optional[str] = Field(default=None, env="EXCHANGE_API_SECRET")
    sandbox: bool = Field(default=False, env="EXCHANGE_SANDBOX")


class RiskSettings(BaseSettings):
    """Risk management configuration"""
    max_risk_per_trade: Decimal = Field(default=Decimal("2.0"), env="MAX_RISK_PER_TRADE")
    max_portfolio_risk: Decimal = Field(default=Decimal("10.0"), env="MAX_PORTFOLIO_RISK")
    max_positions: int = Field(default=10, env="MAX_POSITIONS")


class SignalSettings(BaseSettings):
    """Signal generation configuration"""
    signal_expiry_minutes: int = Field(default=60, env="SIGNAL_EXPIRY_MINUTES")
    min_confidence: Decimal = Field(default=Decimal("0.7"), env="MIN_CONFIDENCE")
    ml_enabled: bool = Field(default=True, env="ML_ENABLED")


class TelegramSettings(BaseSettings):
    """Telegram bot configuration"""
    token: Optional[str] = Field(default=None, env="TELEGRAM_TOKEN")
    chat_id: Optional[str] = Field(default=None, env="TELEGRAM_CHAT_ID")
    enabled: bool = Field(default=True, env="TELEGRAM_ENABLED")


class Settings(BaseSettings):
    """Main application settings"""
    
    database: DatabaseSettings = DatabaseSettings()
    exchange: ExchangeSettings = ExchangeSettings()
    risk: RiskSettings = RiskSettings()
    signal: SignalSettings = SignalSettings()
    telegram: TelegramSettings = TelegramSettings()
    
    environment: str = Field(default="dev", env="ATRA_ENV")
    debug: bool = Field(default=False, env="DEBUG")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Валидация конфигурации при импорте
try:
    from ...core.config_validations import register_config_validations
    from ...core.config_validator import get_config_validator
    register_config_validations()
    validator = get_config_validator()
    # Валидируем настройки при старте
    validator.validate_and_raise(settings.risk)
    validator.validate_and_raise(settings.signal)
    validator.validate_and_raise(settings.database)
    validator.validate_and_raise(settings.exchange)
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Config validation failed: {e}")

