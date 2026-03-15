import asyncio
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MacStudioMonitor:
    """
    Специализированный монитор для Mac Studio.
    Собирает данные о нагрузке CPU/GPU/ANE, температуре и загруженных моделях.
    """

    def __init__(self):
        self.last_stats = {}
        self._is_macos = os.uname().sysname == "Darwin"

    async def get_full_stats(self) -> Dict[str, Any]:
        """Собрать все метрики Mac Studio."""
        tasks = [self.get_hardware_stats(), self.get_loaded_models()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        hw_stats = (
            results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])}
        )
        models_stats = (
            results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])}
        )

        # Автоматическое управление нагрузкой
        throttling_actions = await self._check_and_manage_load(hw_stats, models_stats)

        stats = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hardware": hw_stats,
            "models": models_stats,
            "throttling": throttling_actions,
            "status": "online",
        }
        self.last_stats = stats
        return stats

    async def _check_and_manage_load(self, hw_stats: Dict, models_stats: Dict) -> Dict[str, Any]:
        """Проверить пороги и выполнить действия по управлению нагрузкой."""
        actions = {"triggered": False, "details": []}

        # 1. Проверка температуры (Thermal Level)
        thermal_level = hw_stats.get("temperature", {}).get("thermal_level", "0")
        try:
            level = int(thermal_level)
        except:
            level = 0

        if level >= 1:  # Throttling or Critical
            actions["triggered"] = True
            actions["details"].append(f"Thermal level {level} detected")
            await self._unload_excess_models(models_stats)

        # 2. Проверка RAM
        ram_percent = hw_stats.get("ram", {}).get("percent", 0)
        if ram_percent > 92:
            actions["triggered"] = True
            actions["details"].append(f"RAM usage critical: {ram_percent}%")
            await self._unload_excess_models(models_stats)

        return actions

    async def _unload_excess_models(self, models_stats: Dict):
        """Выгрузить все модели кроме бессмертных при перегреве/перегрузке."""
        import httpx
        from app.ollama_keep_alive_policy import IMMORTAL_MODELS

        ollama_models = models_stats.get("ollama", [])
        for model in ollama_models:
            name = model.get("name", "")
            # Если модель не в списке бессмертных — выгружаем
            is_immortal = any(immortal in name for immortal in IMMORTAL_MODELS)
            if not is_immortal:
                logger.info(f"🔥 [THERMAL PROTECTION] Unloading model {name} due to high load/temp")
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        # В Ollama выгрузка — это запрос с keep_alive=0
                        await client.post(
                            "http://localhost:11434/api/generate",
                            json={"model": name, "keep_alive": 0},
                        )
                except Exception as e:
                    logger.error(f"Failed to unload model {name}: {e}")

    async def get_hardware_stats(self) -> Dict[str, Any]:
        """Получить данные о нагрузке и температуре через powermetrics."""
        if not self._is_macos:
            return {"error": "Not a macOS system"}

        # powermetrics требует sudo для некоторых данных, но мы попробуем собрать доступное
        # или используем sysctl для температуры
        stats = {
            "cpu": await self._get_cpu_usage(),
            "gpu": await self._get_gpu_usage(),
            "temperature": await self._get_temperature(),
            "ram": await self._get_ram_usage(),
        }
        return stats

    async def _get_cpu_usage(self) -> Dict[str, Any]:
        try:
            import psutil

            return {"percent": psutil.cpu_percent(interval=0.1), "load_avg": os.getloadavg()}
        except:
            return {"percent": 0}

    async def _get_gpu_usage(self) -> Dict[str, Any]:
        """Попытка получить нагрузку GPU через powermetrics (короткий замер)."""
        try:
            # Запускаем powermetrics на 1 секунду для сбора статистики
            # Примечание: может потребоваться настройка прав или использование упрощенного метода
            cmd = ["sudo", "powermetrics", "-n", "1", "--samplers", "gpu_power", "-i", "100"]
            # Если sudo недоступен без пароля, этот метод может не сработать в фоне
            # В качестве альтернативы можно использовать iostat или другие утилиты
            return {"active": "unknown", "note": "Requires sudo for precise GPU metrics"}
        except:
            return {"active": "unknown"}

    async def _get_temperature(self) -> Dict[str, Any]:
        """Получить температуру через доступные утилиты."""
        # Пытаемся использовать sysctl или внешние утилиты
        try:
            # На Mac Studio часто используется 'osx-cpu-temp' или 'smcFanControl'
            # Если их нет, пробуем через системные вызовы
            process = await asyncio.create_subprocess_exec(
                "sysctl",
                "-n",
                "machdep.xcpm.cpu_thermal_level",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            thermal_level = stdout.decode().strip()

            return {
                "thermal_level": thermal_level,
                "unit": "level (0-2)",
                "note": "0=normal, 1=throttling, 2=critical",
            }
        except:
            return {"error": "Could not read temperature"}

    async def _get_ram_usage(self) -> Dict[str, Any]:
        try:
            import psutil

            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "percent": mem.percent,
            }
        except:
            return {"percent": 0}

    async def get_loaded_models(self) -> Dict[str, Any]:
        """Получить список загруженных моделей в Ollama и MLX."""
        stats = {"ollama": await self._get_ollama_models(), "mlx": await self._get_mlx_models()}
        return stats

    async def _get_ollama_models(self) -> List[Dict]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get("http://localhost:11434/api/ps")
                if resp.status_code == 200:
                    return resp.json().get("models", [])
        except:
            pass
        return []

    async def _get_mlx_models(self) -> List[str]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get("http://localhost:11435/health")
                if resp.status_code == 200:
                    data = resp.json()
                    # Если MLX API возвращает список кэшированных моделей
                    return data.get("cached_models", [])
        except:
            pass
        return []


_mac_monitor = None


def get_mac_studio_monitor() -> MacStudioMonitor:
    global _mac_monitor
    if _mac_monitor is None:
        _mac_monitor = MacStudioMonitor()
    return _mac_monitor


if __name__ == "__main__":
    # Тестовый запуск
    async def test():
        monitor = MacStudioMonitor()
        stats = await monitor.get_full_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    asyncio.run(test())
