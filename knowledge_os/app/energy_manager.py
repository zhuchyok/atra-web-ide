"""
Energy Manager для энергоэффективных вычислений.
Мониторинг температуры и переключение на энергоэффективные модели.
"""

import logging
import subprocess
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class EnergyManager:
    """Менеджер энергоэффективности"""
    
    def __init__(self):
        self.is_battery_powered = self._check_battery()
        self.temperature_threshold = 80  # градусов Цельсия
        
    def _check_battery(self) -> bool:
        """Проверить, работает ли от батареи (MacBook)"""
        try:
            result = subprocess.run(
                ["pmset", "-g", "batt"],
                capture_output=True,
                text=True,
                timeout=2
            )
            return "AC Power" not in result.stdout
        except Exception:
            return False
    
    def get_temperature(self) -> Optional[float]:
        """Получить температуру CPU (MacBook)"""
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.xcpm.cpu_thermal_level"],
                capture_output=True,
                text=True,
                timeout=2
            )
            # Это возвращает уровень, не температуру напрямую
            # Для реальной температуры нужны другие методы
            return None
        except Exception:
            return None
    
    def should_use_efficient_model(self) -> bool:
        """Определить, нужно ли использовать энергоэффективную модель"""
        if self.is_battery_powered:
            return True
        
        temp = self.get_temperature()
        if temp and temp > self.temperature_threshold:
            return True
        
        return False
    
    def get_efficient_model(self, task_type: str) -> str:
        """Получить энергоэффективную модель для задачи"""
        # Легкие модели для экономии энергии
        efficient_models = {
            "coding": "phi3:mini",
            "reasoning": "phi3:mini",
            "fast": "tinyllama",
            "default": "phi3:mini"
        }
        return efficient_models.get(task_type, "phi3:mini")

# Глобальный экземпляр
_energy_manager: Optional[EnergyManager] = None

def get_energy_manager() -> EnergyManager:
    """Получить глобальный экземпляр EnergyManager"""
    global _energy_manager
    if _energy_manager is None:
        _energy_manager = EnergyManager()
    return _energy_manager

