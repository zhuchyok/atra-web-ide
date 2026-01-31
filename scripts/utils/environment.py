"""
Централизованное определение окружения (Docker, локальное, и т.д.)
Основано на лучших практиках определения контейнерных окружений
"""

import os
from typing import Optional
from functools import lru_cache

# Кэшируем результат определения Docker
_DOCKER_CACHE: Optional[bool] = None


@lru_cache(maxsize=1)
def is_docker() -> bool:
    """
    Определить, запущено ли приложение в Docker контейнере
    
    Использует несколько методов для надежного определения:
    1. Проверка файла /.dockerenv (стандартный маркер Docker)
    2. Проверка переменной окружения DOCKER_CONTAINER
    3. Проверка cgroup (для Linux контейнеров)
    4. Проверка переменной окружения container (Kubernetes/Podman)
    
    Returns:
        True если запущено в Docker, False иначе
    
    Examples:
        >>> if is_docker():
        ...     db_url = "postgresql://admin:secret@knowledge_postgres:5432/knowledge_os"
        ... else:
        ...     db_url = "postgresql://admin:secret@localhost:5432/knowledge_os"
    """
    global _DOCKER_CACHE
    
    if _DOCKER_CACHE is not None:
        return _DOCKER_CACHE
    
    # Метод 1: Стандартный маркер Docker
    if os.path.exists('/.dockerenv'):
        _DOCKER_CACHE = True
        return True
    
    # Метод 2: Переменная окружения DOCKER_CONTAINER
    docker_container = os.getenv('DOCKER_CONTAINER', '').lower()
    if docker_container in ('true', '1', 'yes'):
        _DOCKER_CACHE = True
        return True
    
    # Метод 3: Проверка cgroup (для Linux контейнеров)
    try:
        if os.path.exists('/proc/self/cgroup'):
            with open('/proc/self/cgroup', 'r') as f:
                cgroup_content = f.read()
                if 'docker' in cgroup_content or 'containerd' in cgroup_content:
                    _DOCKER_CACHE = True
                    return True
    except (IOError, PermissionError):
        pass
    
    # Метод 4: Kubernetes/Podman переменная окружения
    container_env = os.getenv('container', '').lower()
    if container_env in ('docker', 'podman', 'containerd'):
        _DOCKER_CACHE = True
        return True
    
    _DOCKER_CACHE = False
    return False


def get_database_url(default_docker: str = None, default_local: str = None) -> str:
    """
    Получить DATABASE_URL в зависимости от окружения
    
    Args:
        default_docker: URL по умолчанию для Docker (если не указан DATABASE_URL)
        default_local: URL по умолчанию для локального окружения
    
    Returns:
        DATABASE_URL для текущего окружения
    
    Examples:
        >>> db_url = get_database_url(
        ...     default_docker="postgresql://admin:secret@knowledge_postgres:5432/knowledge_os",
        ...     default_local="postgresql://admin:secret@localhost:5432/knowledge_os"
        ... )
    """
    # Если DATABASE_URL явно указан, используем его
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url
    
    # Локальная БД: на хосте — localhost; в Docker — knowledge_postgres (compose задаёт DATABASE_URL)
    if default_local is None:
        default_local = "postgresql://admin:secret@localhost:5432/knowledge_os"
    if default_docker is None:
        default_docker = "postgresql://admin:secret@knowledge_postgres:5432/knowledge_os"
    return default_docker if is_docker() else default_local


def get_mlx_api_url() -> str:
    """
    Получить URL MLX API Server в зависимости от окружения
    
    Returns:
        URL MLX API Server (host.docker.internal для Docker, localhost для локального)
    """
    mlx_url = os.getenv('MLX_API_URL')
    if mlx_url:
        return mlx_url
    
    if is_docker():
        return "http://host.docker.internal:11435"
    else:
        return "http://localhost:11435"


def get_ollama_url() -> str:
    """
    Получить URL Ollama в зависимости от окружения
    
    Returns:
        URL Ollama (host.docker.internal для Docker, localhost для локального)
    """
    ollama_url = os.getenv('OLLAMA_BASE_URL') or os.getenv('OLLAMA_URL')
    if ollama_url:
        return ollama_url
    
    if is_docker():
        return "http://host.docker.internal:11434"
    else:
        return "http://localhost:11434"


def get_victoria_url() -> str:
    """
    Получить URL Victoria Agent в зависимости от окружения
    
    Returns:
        URL Victoria Agent
    """
    victoria_url = os.getenv('VICTORIA_URL')
    if victoria_url:
        return victoria_url
    
    if is_docker():
        return "http://host.docker.internal:8010"
    else:
        return "http://localhost:8010"


def get_veronica_url() -> str:
    """
    Получить URL Veronica Agent в зависимости от окружения
    
    Returns:
        URL Veronica Agent
    """
    veronica_url = os.getenv('VERONICA_URL')
    if veronica_url:
        return veronica_url
    
    if is_docker():
        return "http://host.docker.internal:8011"
    else:
        return "http://localhost:8011"


def reset_cache():
    """Сбросить кэш определения окружения (для тестирования)"""
    global _DOCKER_CACHE
    _DOCKER_CACHE = None
    is_docker.cache_clear()
