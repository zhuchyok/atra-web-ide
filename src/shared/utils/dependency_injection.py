"""
Dependency Injection Container

Simple DI container for managing dependencies.
"""

from typing import Dict, TypeVar, Callable, Any, Optional
from functools import lru_cache

T = TypeVar('T')


class DIContainer:
    """
    Simple Dependency Injection Container
    
    Manages dependencies and provides them when needed.
    """
    
    def __init__(self):
        """Initialize container"""
        self._services: Dict[type, Any] = {}
        self._factories: Dict[type, Callable] = {}
        self._singletons: Dict[type, Any] = {}
    
    def register(self, service_type: type, instance: Any) -> None:
        """Register a service instance"""
        self._services[service_type] = instance
    
    def register_factory(self, service_type: type, factory: Callable) -> None:
        """Register a factory function"""
        self._factories[service_type] = factory
    
    def register_singleton(self, service_type: type, factory: Callable) -> None:
        """Register a singleton factory"""
        self._factories[service_type] = factory
        self._singletons[service_type] = None
    
    def get(self, service_type: type) -> Any:
        """Get service instance"""
        # Check if already registered
        if service_type in self._services:
            return self._services[service_type]
        
        # Check if singleton exists
        if service_type in self._singletons:
            if self._singletons[service_type] is None:
                self._singletons[service_type] = self._factories[service_type](self)
            return self._singletons[service_type]
        
        # Check if factory exists
        if service_type in self._factories:
            return self._factories[service_type](self)
        
        raise ValueError(f"Service {service_type} not registered")
    
    def resolve(self, service_type: type) -> Any:
        """Alias for get"""
        return self.get(service_type)


# Global container instance
container = DIContainer()

