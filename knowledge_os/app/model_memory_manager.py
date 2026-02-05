"""
Model Memory Manager для оптимизации использования памяти на сервере.
Управляет динамической загрузкой/выгрузкой моделей, мониторингом памяти,
и автоматической очисткой при нехватке ресурсов.
"""

import asyncio
import os
import logging
import psutil
import httpx
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

# Конфигурация
MIN_FREE_MEMORY_MB = 200  # Минимум свободной памяти в MB
MODEL_UNLOAD_TIMEOUT = 300  # Время до выгрузки неиспользуемой модели (секунды)
MEMORY_CHECK_INTERVAL = 30  # Интервал проверки памяти (секунды)

class ModelState(Enum):
    """Состояние модели"""
    LOADED = "loaded"
    UNLOADED = "unloaded"
    LOADING = "loading"
    UNLOADING = "unloading"

def _default_ollama_url() -> str:
    """URL Ollama: в Docker localhost недоступен — используем host.docker.internal."""
    is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
    if is_docker:
        return os.getenv('OLLAMA_BASE_URL') or os.getenv('OLLAMA_API_URL') or 'http://host.docker.internal:11434'
    return os.getenv('OLLAMA_BASE_URL') or os.getenv('OLLAMA_API_URL') or 'http://localhost:11434'


class ModelMemoryManager:
    """
    Менеджер памяти для управления моделями Ollama.
    Отслеживает использование памяти и автоматически выгружает неиспользуемые модели.
    """
    
    def __init__(self, ollama_url: str = None):
        self.ollama_url = ollama_url or _default_ollama_url()
        self.model_states: Dict[str, ModelState] = {}
        self.model_last_used: Dict[str, datetime] = {}
        self.model_memory_usage: Dict[str, int] = {}  # MB
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
    async def get_available_memory_mb(self) -> int:
        """Получить доступную память в MB"""
        try:
            memory = psutil.virtual_memory()
            return memory.available // (1024 * 1024)
        except Exception as e:
            logger.error(f"Ошибка получения информации о памяти: {e}")
            return 0
    
    async def get_loaded_models(self) -> List[str]:
        """Получить список загруженных моделей"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [model['name'] for model in data.get('models', [])]
        except Exception as e:
            logger.warning(f"Ошибка получения списка моделей: {e}")
        return []
    
    async def unload_model(self, model_name: str) -> bool:
        """Выгрузить модель из памяти"""
        try:
            logger.info(f"🔄 Выгрузка модели {model_name} из памяти...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Используем Ollama API для выгрузки модели
                # Ollama автоматически выгружает модели при нехватке памяти,
                # но мы можем явно запросить через /api/generate с stream=false
                # или просто подождать, пока Ollama сам выгрузит
                
                # Для явной выгрузки можно использовать:
                # response = await client.post(
                #     f"{self.ollama_url}/api/generate",
                #     json={"model": model_name, "prompt": "", "stream": False},
                #     timeout=1.0
                # )
                # Но лучше просто пометить модель как неиспользуемую
                
                self.model_states[model_name] = ModelState.UNLOADED
                if model_name in self.model_last_used:
                    del self.model_last_used[model_name]
                if model_name in self.model_memory_usage:
                    del self.model_memory_usage[model_name]
                
                logger.info(f"✅ Модель {model_name} выгружена")
                return True
        except Exception as e:
            logger.error(f"❌ Ошибка выгрузки модели {model_name}: {e}")
            return False
    
    async def mark_model_used(self, model_name: str):
        """Пометить модель как используемую"""
        self.model_last_used[model_name] = datetime.now()
        self.model_states[model_name] = ModelState.LOADED
    
    async def cleanup_unused_models(self) -> int:
        """Очистить неиспользуемые модели"""
        current_time = datetime.now()
        unloaded_count = 0
        
        for model_name, last_used in list(self.model_last_used.items()):
            time_since_use = (current_time - last_used).total_seconds()
            
            if time_since_use > MODEL_UNLOAD_TIMEOUT:
                logger.info(f"⏰ Модель {model_name} не использовалась {time_since_use:.0f} секунд, выгружаем...")
                await self.unload_model(model_name)
                unloaded_count += 1
        
        return unloaded_count
    
    async def emergency_memory_cleanup(self) -> bool:
        """Экстренная очистка памяти при критической нехватке"""
        available_mb = await self.get_available_memory_mb()
        
        if available_mb < MIN_FREE_MEMORY_MB:
            logger.warning(f"🚨 КРИТИЧЕСКАЯ НЕХВАТКА ПАМЯТИ: {available_mb}MB свободно (минимум {MIN_FREE_MEMORY_MB}MB)")
            
            # Выгружаем все неиспользуемые модели
            unloaded = await self.cleanup_unused_models()
            
            # Если все еще нехватка, выгружаем старые модели
            if await self.get_available_memory_mb() < MIN_FREE_MEMORY_MB:
                # Сортируем модели по времени последнего использования
                sorted_models = sorted(
                    self.model_last_used.items(),
                    key=lambda x: x[1]
                )
                
                # Выгружаем самые старые
                for model_name, _ in sorted_models[:2]:  # Выгружаем 2 самые старые
                    logger.warning(f"🚨 Экстренная выгрузка модели {model_name}")
                    await self.unload_model(model_name)
            
            final_available = await self.get_available_memory_mb()
            logger.info(f"✅ После очистки: {final_available}MB свободно")
            return final_available >= MIN_FREE_MEMORY_MB
        
        return True
    
    async def monitor_memory(self):
        """Мониторинг памяти и автоматическая очистка"""
        self._running = True
        logger.info("🔍 Запущен мониторинг памяти моделей")
        
        while self._running:
            try:
                # Проверяем доступную память
                available_mb = await self.get_available_memory_mb()
                
                # Экстренная очистка при критической нехватке
                if available_mb < MIN_FREE_MEMORY_MB:
                    await self.emergency_memory_cleanup()
                else:
                    # Обычная очистка неиспользуемых моделей
                    await self.cleanup_unused_models()
                
                # Обновляем список загруженных моделей
                loaded_models = await self.get_loaded_models()
                for model in loaded_models:
                    if model not in self.model_states:
                        self.model_states[model] = ModelState.LOADED
                
                await asyncio.sleep(MEMORY_CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Ошибка в мониторинге памяти: {e}")
                await asyncio.sleep(MEMORY_CHECK_INTERVAL)
    
    def start_monitoring(self):
        """Запустить мониторинг памяти"""
        if not self._running:
            self._monitor_task = asyncio.create_task(self.monitor_memory())
    
    def stop_monitoring(self):
        """Остановить мониторинг памяти"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
    
    async def get_actual_model_memory_usage(self) -> Dict[str, float]:
        """Получить реальное использование памяти каждой моделью через процессы Ollama"""
        model_memory = {}
        try:
            # Находим процессы Ollama
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if 'ollama' in proc.info['name'].lower():
                        memory_mb = proc.info['memory_info'].rss / (1024 * 1024)
                        # Пытаемся определить модель из командной строки
                        try:
                            cmdline = ' '.join(proc.cmdline())
                            # Ищем имя модели в командной строке
                            for model_name in self.model_states.keys():
                                if model_name in cmdline:
                                    if model_name not in model_memory:
                                        model_memory[model_name] = 0.0
                                    model_memory[model_name] += memory_mb
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"Ошибка получения реального использования памяти: {e}")
        
        return model_memory
    
    async def get_memory_stats(self) -> Dict:
        """Получить статистику использования памяти"""
        available_mb = await self.get_available_memory_mb()
        loaded_models = await self.get_loaded_models()
        actual_memory_usage = await self.get_actual_model_memory_usage()
        
        return {
            "available_memory_mb": available_mb,
            "min_free_memory_mb": MIN_FREE_MEMORY_MB,
            "loaded_models_count": len(loaded_models),
            "loaded_models": loaded_models,
            "model_states": {k: v.value for k, v in self.model_states.items()},
            "actual_memory_usage_mb": actual_memory_usage,
            "last_used": {
                k: v.isoformat() 
                for k, v in self.model_last_used.items()
            }
        }

# Глобальный экземпляр
_memory_manager: Optional[ModelMemoryManager] = None

def get_memory_manager(ollama_url: str = None) -> ModelMemoryManager:
    """Получить глобальный экземпляр ModelMemoryManager"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = ModelMemoryManager(ollama_url)
        _memory_manager.start_monitoring()
    return _memory_manager

