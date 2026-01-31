"""
Утилиты для scripts
Централизованные утилиты для управления путями и окружением
Основано на лучших практиках Python (PEP 420, PEP 517/518, PEP 484)
"""

from .path_setup import (
    setup_project_paths,
    get_project_root,
    get_knowledge_os_root,
    get_knowledge_os_app,
    get_scripts_root,
    get_backend_root,
    get_frontend_root,
    get_src_root,
    get_all_project_paths,
    verify_paths,
    reset_paths,
)

from .environment import (
    is_docker,
    get_database_url,
    get_mlx_api_url,
    get_ollama_url,
    get_victoria_url,
    get_veronica_url,
    reset_cache as reset_env_cache,
)

__version__ = "1.0.0"
__all__ = [
    # Path management
    'setup_project_paths',
    'get_project_root',
    'get_knowledge_os_root',
    'get_knowledge_os_app',
    'get_scripts_root',
    'get_backend_root',
    'get_frontend_root',
    'get_src_root',
    'get_all_project_paths',
    'verify_paths',
    'reset_paths',
    # Environment detection
    'is_docker',
    'get_database_url',
    'get_mlx_api_url',
    'get_ollama_url',
    'get_victoria_url',
    'get_veronica_url',
    'reset_env_cache',
]
