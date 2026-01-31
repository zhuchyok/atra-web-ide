"""
Мониторинг ресурсов системы: RAM, CPU, температура
Особенно важно для MLX API Server, который может вылетать при перегрузке
"""
import os
import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    # Устанавливаем psutil при первом использовании
    import subprocess
    import sys
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'psutil>=5.9.0'], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import psutil
        PSUTIL_AVAILABLE = True
    except:
        pass

logger = logging.getLogger(__name__)

class ResourceMonitor:
    """Мониторинг ресурсов системы"""
    
    def __init__(self):
        self.mlx_url = os.getenv('MLX_API_URL', 'http://localhost:11435')
        self.ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self._mlx_health_cache = {}
        self._cache_ttl = 5  # 5 секунд кэш
        
    async def get_system_resources(self) -> Dict:
        """Получить системные ресурсы (RAM, CPU)"""
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil недоступен, мониторинг ресурсов ограничен")
            return {
                'ram': {'used_percent': 0, 'used_gb': 0, 'total_gb': 0, 'available_gb': 0},
                'cpu': {'percent': 0, 'count': 0},
                'temperature': None,
                'disk': {'used_percent': 0},
                'timestamp': datetime.now().isoformat()
            }
        
        try:
            # RAM
            memory = psutil.virtual_memory()
            ram_used_percent = memory.percent
            ram_used_gb = memory.used / (1024**3)
            ram_total_gb = memory.total / (1024**3)
            
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # Температура (macOS)
            temperature = None
            try:
                if hasattr(psutil, "sensors_temperatures"):
                    temps = psutil.sensors_temperatures()
                    if temps:
                        # Берем первую доступную температуру
                        for name, entries in temps.items():
                            if entries:
                                temperature = entries[0].current
                                break
            except Exception:
                pass
            
            # Диск
            disk = psutil.disk_usage('/')
            disk_used_percent = disk.percent
            
            return {
                'ram': {
                    'used_percent': ram_used_percent,
                    'used_gb': round(ram_used_gb, 2),
                    'total_gb': round(ram_total_gb, 2),
                    'available_gb': round((memory.total - memory.used) / (1024**3), 2)
                },
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count
                },
                'temperature': temperature,
                'disk': {
                    'used_percent': disk_used_percent
                },
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            return {}
    
    async def get_mlx_health(self) -> Dict:
        """Получить health MLX API Server с мониторингом ресурсов"""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.mlx_url}/health")
                if response.status_code == 200:
                    data = response.json()
                    
                    # Добавляем системные ресурсы
                    system_resources = await self.get_system_resources()
                    
                    return {
                        'status': 'healthy',
                        'active_requests': data.get('active_requests', 0),
                        'max_concurrent': data.get('max_concurrent', 5),
                        'models_cached': data.get('models_cached', 0),
                        'system': system_resources,
                        'mlx_memory_usage': data.get('memory_usage_percent', 0),
                        'mlx_cpu_usage': data.get('cpu_usage_percent', 0),
                        'temperature': system_resources.get('temperature'),
                        'is_overloaded': (
                            data.get('active_requests', 0) >= data.get('max_concurrent', 5) or
                            system_resources.get('ram', {}).get('used_percent', 0) > 90 or
                            system_resources.get('cpu', {}).get('percent', 0) > 90
                        )
                    }
        except Exception as e:
            logger.warning(f"MLX health check failed: {e}")
            return {
                'status': 'unavailable',
                'error': str(e)
            }
    
    async def get_ollama_health(self) -> Dict:
        """Получить health Ollama"""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                # Проверяем процессы
                response = await client.get(f"{self.ollama_url}/api/ps")
                if response.status_code == 200:
                    data = response.json()
                    processes = data.get('processes', [])
                    
                    # Добавляем системные ресурсы
                    system_resources = await self.get_system_resources()
                    
                    return {
                        'status': 'healthy',
                        'active_processes': len(processes),
                        'system': system_resources,
                        'is_overloaded': (
                            system_resources.get('ram', {}).get('used_percent', 0) > 90 or
                            system_resources.get('cpu', {}).get('percent', 0) > 90
                        )
                    }
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return {
                'status': 'unavailable',
                'error': str(e)
            }
    
    def should_throttle_mlx(self, health: Dict) -> bool:
        """Определить, нужно ли ограничить нагрузку на MLX"""
        if health.get('status') != 'healthy':
            return True
        
        # Ограничиваем если:
        # - MLX перегружен (все слоты заняты)
        # - RAM > 85%
        # - CPU > 85%
        # - Температура > 80°C (если доступна)
        system = health.get('system', {})
        ram_percent = system.get('ram', {}).get('used_percent', 0)
        cpu_percent = system.get('cpu', {}).get('percent', 0)
        temp = system.get('temperature')
        
        return (
            health.get('is_overloaded', False) or
            ram_percent > 85 or
            cpu_percent > 85 or
            (temp and temp > 80)
        )

# Singleton
_monitor_instance = None

def get_resource_monitor() -> ResourceMonitor:
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = ResourceMonitor()
    return _monitor_instance
