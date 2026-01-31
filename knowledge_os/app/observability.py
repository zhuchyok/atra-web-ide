"""
OpenTelemetry интеграция для трассировки и мониторинга
Поддержка distributed tracing для Victoria Enhanced
"""

import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager
from functools import wraps
import time

logger = logging.getLogger(__name__)

# Попытка импорта OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.debug("ℹ️ OpenTelemetry не установлен (опциональный компонент). Для установки: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp")

class ObservabilityManager:
    """Менеджер observability для трассировки агентов"""
    
    def __init__(self, service_name: str = "atra-enhanced", enable_console: bool = True):
        self.service_name = service_name
        self.enabled = OPENTELEMETRY_AVAILABLE and os.getenv("ENABLE_OTEL", "false").lower() == "true"
        self.tracer = None
        
        if self.enabled:
            self._setup_tracer(enable_console)
        else:
            logger.info("📊 Observability отключен (установите ENABLE_OTEL=true)")
    
    def _setup_tracer(self, enable_console: bool = True):
        """Настройка tracer"""
        try:
            # Создаем resource
            resource = Resource.create({
                "service.name": self.service_name,
                "service.version": "2.0",
                "deployment.environment": os.getenv("ATRA_ENV", "dev")
            })
            
            # Создаем TracerProvider
            provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(provider)
            
            # Console exporter (для разработки)
            if enable_console:
                console_exporter = ConsoleSpanExporter()
                provider.add_span_processor(BatchSpanProcessor(console_exporter))
            
            # OTLP exporter (для production - Jaeger, Tempo и т.д.)
            otlp_endpoint = os.getenv("OTLP_ENDPOINT")
            if otlp_endpoint:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=otlp_endpoint,
                    insecure=os.getenv("OTLP_INSECURE", "false").lower() == "true"
                )
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"📊 OTLP exporter настроен: {otlp_endpoint}")
            
            # Получаем tracer
            self.tracer = trace.get_tracer(self.service_name)
            logger.info("✅ OpenTelemetry tracer настроен")
            
            # Инструментируем HTTPX (для запросов к Ollama)
            try:
                HTTPXClientInstrumentor().instrument()
            except Exception as e:
                logger.warning(f"⚠️ Не удалось инструментировать HTTPX: {e}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка настройки OpenTelemetry: {e}")
            self.enabled = False
    
    @contextmanager
    def trace_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Контекстный менеджер для создания span"""
        if not self.enabled or not self.tracer:
            yield
            return
        
        with self.tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
    
    def trace_function(self, name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
        """Декоратор для трассировки функций"""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                span_name = name or f"{func.__module__}.{func.__name__}"
                with self.trace_span(span_name, attributes):
                    start_time = time.time()
                    try:
                        result = await func(*args, **kwargs)
                        elapsed = time.time() - start_time
                        if self.enabled and self.tracer:
                            span = trace.get_current_span()
                            if span:
                                span.set_attribute("function.duration", elapsed)
                                span.set_attribute("function.success", True)
                        return result
                    except Exception as e:
                        elapsed = time.time() - start_time
                        if self.enabled and self.tracer:
                            span = trace.get_current_span()
                            if span:
                                span.set_attribute("function.duration", elapsed)
                                span.set_attribute("function.success", False)
                                span.set_attribute("function.error", str(e))
                        raise
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                span_name = name or f"{func.__module__}.{func.__name__}"
                with self.trace_span(span_name, attributes):
                    start_time = time.time()
                    try:
                        result = func(*args, **kwargs)
                        elapsed = time.time() - start_time
                        if self.enabled and self.tracer:
                            span = trace.get_current_span()
                            if span:
                                span.set_attribute("function.duration", elapsed)
                                span.set_attribute("function.success", True)
                        return result
                    except Exception as e:
                        elapsed = time.time() - start_time
                        if self.enabled and self.tracer:
                            span = trace.get_current_span()
                            if span:
                                span.set_attribute("function.duration", elapsed)
                                span.set_attribute("function.success", False)
                                span.set_attribute("function.error", str(e))
                        raise
            
            # Определяем синхронная или асинхронная функция
            import inspect
            if inspect.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Добавить событие в текущий span"""
        if not self.enabled or not self.tracer:
            return
        
        span = trace.get_current_span()
        if span:
            span.add_event(name, attributes or {})
    
    def set_attribute(self, key: str, value: Any):
        """Установить атрибут в текущий span"""
        if not self.enabled or not self.tracer:
            return
        
        span = trace.get_current_span()
        if span:
            span.set_attribute(key, str(value))

# Глобальный экземпляр
_observability_manager: Optional[ObservabilityManager] = None

def get_observability_manager() -> ObservabilityManager:
    """Получить глобальный экземпляр ObservabilityManager"""
    global _observability_manager
    if _observability_manager is None:
        _observability_manager = ObservabilityManager()
    return _observability_manager

def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Удобная функция для создания span"""
    manager = get_observability_manager()
    return manager.trace_span(name, attributes)

def trace_function(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """Удобный декоратор для трассировки функций"""
    manager = get_observability_manager()
    return manager.trace_function(name, attributes)
