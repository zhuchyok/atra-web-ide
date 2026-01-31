"""
ATRA Web IDE - Конфигурация (Улучшенная версия)
Валидация, безопасность, лучшие практики
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List, Optional
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
    
    # Project Context
    project_name: str = os.getenv("PROJECT_NAME", "atra-web-ide")  # Контекст проекта для агентов
    main_project: str = os.getenv("MAIN_PROJECT", "atra-web-ide")  # Основной проект корпорации
    
    # Victoria Agent (общий для всех проектов)
    victoria_url: str = os.getenv("VICTORIA_URL", "http://localhost:8010")  # Общий порт для всех проектов
    victoria_mcp_url: str = os.getenv("VICTORIA_MCP_URL", "http://localhost:8012")
    # Тяжёлые модели могут долго запускаться + обработка локальными моделями; 180 сек мало
    victoria_timeout: float = float(os.getenv("VICTORIA_TIMEOUT", "600.0"))
    
    # Ollama / MLX API Server (разные порты: Ollama 11434, MLX 11435)
    ollama_url: str = os.getenv("OLLAMA_URL") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
    default_model: str = os.getenv("DEFAULT_MODEL", "qwen2.5-coder:32b")
    ollama_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "120.0"))
    
    # Database (Knowledge OS)
    database_url: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://admin:secret@localhost:5432/knowledge_os"
    )
    # Knowledge OS REST API (для логирования чата в interaction_logs — Singularity 9.0)
    knowledge_os_api_url: str = os.getenv("KNOWLEDGE_OS_API_URL", "http://localhost:8002")
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
        "http://localhost:3002",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:5173"
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: List[str] = ["*"]
    
    # Rate Limiting
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    rate_limit_per_hour: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))

    # Ограничение одновременных запросов к Victoria (снижение 500 при нагрузке)
    max_concurrent_victoria: int = int(os.getenv("MAX_CONCURRENT_VICTORIA", "50"))
    victoria_concurrent_wait_sec: float = float(os.getenv("VICTORIA_CONCURRENT_WAIT_SEC", "45.0"))
    
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

    # RAG-light (Фаза 2: быстрый ответ на фактуальные вопросы из БЗ)
    rag_light_enabled: bool = os.getenv("RAG_LIGHT_ENABLED", "true").lower() == "true"
    rag_light_threshold: float = float(os.getenv("RAG_LIGHT_THRESHOLD", "0.75"))
    rag_light_max_length: int = int(os.getenv("RAG_LIGHT_MAX_LENGTH", "150"))
    rag_light_timeout_ms: int = int(os.getenv("RAG_LIGHT_TIMEOUT_MS", "200"))
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    # Фаза 4: реранкинг чанков для повышения релевантности
    reranking_enabled: bool = os.getenv("RERANKING_ENABLED", "false").lower() == "true"
    # Фаза 4: query expansion для улучшения retrieval
    query_expansion_enabled: bool = os.getenv("QUERY_EXPANSION_ENABLED", "true").lower() == "true"

    # Agent suggestion (Фаза 2, день 3–4: подсказка перейти в режим Агент)
    agent_suggestion_enabled: bool = os.getenv("AGENT_SUGGESTION_ENABLED", "true").lower() == "true"
    agent_suggestion_threshold: float = float(os.getenv("AGENT_SUGGESTION_THRESHOLD", "0.6"))
    agent_suggestion_delay_ms: int = int(os.getenv("AGENT_SUGGESTION_DELAY_MS", "500"))

    # Фаза 2: опции для продакшена (резерв под расширение)
    rag_light_cache_ttl: int = int(os.getenv("RAG_LIGHT_CACHE_TTL", "300"))  # секунды, in-memory кэш
    # RAG Context Cache (Ollama + MLX): кэш результатов векторного поиска, -150ms при хите
    rag_context_cache_enabled: bool = os.getenv("RAG_CONTEXT_CACHE_ENABLED", "true").lower() == "true"
    rag_cache_ttl_sec: int = int(os.getenv("RAG_CACHE_TTL_SEC", os.getenv("RAG_LIGHT_CACHE_TTL", "300")))
    # Auto-Optimizer: проактивная оптимизация (цикл каждые 5 мин)
    auto_optimizer_enabled: bool = os.getenv("AUTO_OPTIMIZER_ENABLED", "false").lower() == "true"
    auto_optimizer_interval_sec: int = int(os.getenv("AUTO_OPTIMIZER_INTERVAL_SEC", "300"))
    # Data Retention: retention_days для очистки real_time_metrics, semantic_ai_cache (не трогает knowledge_nodes)
    data_retention_days: int = int(os.getenv("DATA_RETENTION_DAYS", "90"))
    metrics_enabled: bool = os.getenv("METRICS_ENABLED", "true").lower() == "true"

    # День 5: Prometheus метрики (экспорт на том же порту приложения)
    metrics_port: int = int(os.getenv("METRICS_PORT", "8080"))
    export_metrics: bool = os.getenv("EXPORT_METRICS", "true").lower() == "true"
    metrics_path: str = os.getenv("METRICS_PATH", "/metrics")

    # Фаза 3: кэш планов
    plan_cache_enabled: bool = os.getenv("PLAN_CACHE_ENABLED", "true").lower() == "true"
    plan_cache_ttl: int = int(os.getenv("PLAN_CACHE_TTL", "3600"))
    plan_cache_redis_enabled: bool = os.getenv("PLAN_CACHE_REDIS_ENABLED", "false").lower() == "true"
    plan_cache_maxsize: int = int(os.getenv("PLAN_CACHE_MAXSIZE", "100"))
    plan_cache_min_gen_time: float = float(os.getenv("PLAN_CACHE_MIN_GEN_TIME", "2.0"))  # кэшировать если генерация > N сек
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Фаза 3, день 3–4: оптимизации RAG-light
    embedding_batch_enabled: bool = os.getenv("EMBEDDING_BATCH_ENABLED", "false").lower() == "true"
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))
    embedding_batch_timeout_ms: int = int(os.getenv("EMBEDDING_BATCH_TIMEOUT_MS", "50"))
    rag_light_prefetch_enabled: bool = os.getenv("RAG_LIGHT_PREFETCH_ENABLED", "false").lower() == "true"
    rag_light_prefetch_file: Optional[str] = os.getenv("RAG_LIGHT_PREFETCH_FILE")
    rag_light_prefetch_max_queries: int = int(os.getenv("RAG_LIGHT_PREFETCH_MAX_QUERIES", "50"))
    # true = fallback на sentence-transformers при недоступности Ollama. Для P95 < 300ms: false + Ollama
    embedding_fallback_enabled: bool = os.getenv("EMBEDDING_FALLBACK_ENABLED", "true").lower() == "true"
    # Прогрев embeddings при старте (фоново, P95 < 300ms)
    rag_embedding_warmup_enabled: bool = os.getenv("RAG_EMBEDDING_WARMUP_ENABLED", "true").lower() == "true"
    local_embedding_model: str = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    keyword_fallback_enabled: bool = os.getenv("KEYWORD_FALLBACK_ENABLED", "true").lower() == "true"

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
