"""
ATRA Web IDE - Конфигурация (Улучшенная версия)
Валидация, безопасность, лучшие практики
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Настройки приложения с валидацией"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Игнорируем лишние переменные
    )
    
    # API Settings
    app_name: str = "ATRA Web IDE"
    debug: bool = False
    api_version: str = "1.0.0"
    
    # Victoria Agent
    victoria_url: str = os.getenv("VICTORIA_URL", "http://localhost:8010")
    victoria_mcp_url: str = os.getenv("VICTORIA_MCP_URL", "http://localhost:8012")
    victoria_timeout: float = float(os.getenv("VICTORIA_TIMEOUT", "60.0"))
    
    # Ollama
    ollama_url: str = os.getenv("OLLAMA_URL") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
    default_model: str = os.getenv("DEFAULT_MODEL", "qwen2.5-coder:32b")
    ollama_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "120.0"))
    
    # Database (Knowledge OS)
    database_url: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://admin:secret@localhost:5432/knowledge_os"
    )
    database_pool_min_size: int = int(os.getenv("DATABASE_POOL_MIN_SIZE", "2"))
    database_pool_max_size: int = int(os.getenv("DATABASE_POOL_MAX_SIZE", "10"))
    
    # Files
    workspace_root: str = os.getenv("WORKSPACE_ROOT", "/tmp/atra-workspace")
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
    allowed_file_extensions: List[str] = [
        ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".txt", 
        ".html", ".css", ".yaml", ".yml", ".toml", ".sh", ".sql"
    ]
    
    # CORS - Безопасность
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: List[str] = ["*"]
    
    # Rate Limiting
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    rate_limit_per_hour: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))
    
    # Security
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv("LOG_FORMAT", "json")  # json или text
    
    # Health Checks
    health_check_enabled: bool = True
    health_check_interval: int = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))  # секунды
    
    # Cache
    cache_enabled: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    cache_ttl: int = int(os.getenv("CACHE_TTL", "300"))  # секунды
    
    def validate(self) -> None:
        """Валидация настроек"""
        errors = []
        
        # Проверка URL
        if not self.victoria_url.startswith(("http://", "https://")):
            errors.append("VICTORIA_URL must start with http:// or https://")
        
        if not self.ollama_url.startswith(("http://", "https://")):
            errors.append("OLLAMA_URL must start with http:// or https://")
        
        # Проверка workspace
        if not self.workspace_root:
            errors.append("WORKSPACE_ROOT cannot be empty")
        
        # Проверка secret key в production
        if not self.debug and self.secret_key == "change-me-in-production":
            logger.warning("⚠️ SECRET_KEY is using default value! Change it in production!")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        logger.info("✅ Configuration validated successfully")


@lru_cache()
def get_settings() -> Settings:
    """Получить настройки (кэшировано)"""
    settings = Settings()
    settings.validate()
    return settings
