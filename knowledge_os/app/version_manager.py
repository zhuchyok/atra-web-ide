"""
Version Manager для версионирования системы и rollback.
"""

import logging
import os
import json
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class VersionManager:
    """Менеджер версий системы"""
    
    def __init__(self):
        self.current_version = os.getenv("SINGULARITY_VERSION", "6.0")
        self.versions_dir = os.path.join(os.path.dirname(__file__), "../versions")
        os.makedirs(self.versions_dir, exist_ok=True)
        
    def get_current_version(self) -> str:
        """Получить текущую версию"""
        return self.current_version
    
    def list_versions(self) -> List[Dict]:
        """Список доступных версий"""
        versions = []
        for item in os.listdir(self.versions_dir):
            version_path = os.path.join(self.versions_dir, item)
            if os.path.isdir(version_path):
                versions.append({
                    "version": item,
                    "path": version_path
                })
        return versions

# Глобальный экземпляр
_version_manager: Optional[VersionManager] = None

def get_version_manager() -> VersionManager:
    """Получить глобальный экземпляр VersionManager"""
    global _version_manager
    if _version_manager is None:
        _version_manager = VersionManager()
    return _version_manager

