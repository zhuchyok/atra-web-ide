import logging
import os
import psutil
from typing import Dict, Any, Tuple

logger = logging.getLogger("ResourceGuard")

class ResourceGuard:
    """
    [SINGULARITY 21.25] Global Resource Controller.
    Coordinates autonomous tasks based on Mac Studio hardware load.
    """
    
    def __init__(self, 
                 ram_threshold_pct: float = 85.0, 
                 cpu_threshold_pct: float = 75.0,
                 thermal_threshold: int = 1):
        self.ram_threshold = ram_threshold_pct
        self.cpu_threshold = cpu_threshold_pct
        self.thermal_threshold = thermal_threshold

    async def can_start_autonomous_task(self) -> Tuple[bool, str]:
        """
        Check if an autonomous/background task can be started.
        Returns: (can_start, reason)
        """
        # 1. Check RAM
        ram = psutil.virtual_memory()
        if ram.percent > self.ram_threshold:
            return False, f"RAM usage too high: {ram.percent}% > {self.ram_threshold}%"

        # 2. Check CPU (short interval check)
        cpu_pct = psutil.cpu_percent(interval=0.5)
        if cpu_pct > self.cpu_threshold:
            return False, f"CPU usage too high: {cpu_pct}% > {self.cpu_threshold}%"

        # 3. Check Thermal Level (macOS only)
        if os.uname().sysname == "Darwin":
            try:
                from app.mac_studio_monitor import get_mac_studio_monitor
                monitor = get_mac_studio_monitor()
                stats = await monitor.get_full_stats()
                thermal_level = int(stats.get("hardware", {}).get("temperature", {}).get("thermal_level", "0"))
                if thermal_level >= self.thermal_threshold:
                    return False, f"Thermal level critical: {thermal_level} >= {self.thermal_threshold}"
            except Exception as e:
                logger.debug(f"Thermal check failed: {e}")

        return True, "System healthy"

_guard = None

def get_resource_guard() -> ResourceGuard:
    global _guard
    if _guard is None:
        _guard = ResourceGuard(
            ram_threshold_pct=float(os.getenv("GUARD_RAM_THRESHOLD", "85.0")),
            cpu_threshold_pct=float(os.getenv("GUARD_CPU_THRESHOLD", "75.0")),
            thermal_threshold=int(os.getenv("GUARD_THERMAL_THRESHOLD", "1"))
        )
    return _guard
