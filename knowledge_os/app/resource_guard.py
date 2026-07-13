import logging
import os
from typing import Any, Dict, Tuple

import psutil

logger = logging.getLogger("ResourceGuard")


class ResourceGuard:
    """
    [SINGULARITY 21.25] Global Resource Controller.
    Coordinates autonomous tasks based on Mac Studio hardware load.
    """

    def __init__(
        self,
        ram_threshold_pct: float = 85.0,
        cpu_threshold_pct: float = 75.0,
        thermal_threshold: int = 1,
    ):
        self.ram_threshold = ram_threshold_pct
        self.cpu_threshold = cpu_threshold_pct
        self.thermal_threshold = thermal_threshold

    async def can_start_autonomous_task(self) -> Tuple[bool, str]:
        """
        Check if an autonomous/background task can be started.
        Returns: (can_start, reason)
        """
        score = await self.get_health_score()
        if score < 0.2:
            return False, f"System health too low: {score:.2f}"
        return True, "System healthy"

    async def get_health_score(self) -> float:
        """
        Returns a normalized health score (0.0 to 1.0).
        1.0 = Perfect health (idle)
        0.0 = Critical load (throttling required)
        """
        # 1. RAM Score
        ram = psutil.virtual_memory()
        ram_headroom = max(0.0, self.ram_threshold - ram.percent)
        ram_score = ram_headroom / self.ram_threshold

        # 2. CPU Score
        cpu_pct = psutil.cpu_percent(interval=0.1)
        cpu_headroom = max(0.0, self.cpu_threshold - cpu_pct)
        cpu_score = cpu_headroom / self.cpu_threshold

        # 3. Thermal Score (macOS only)
        thermal_score = 1.0
        if os.uname().sysname == "Darwin":
            try:
                from app.mac_studio_monitor import get_mac_studio_monitor

                monitor = get_mac_studio_monitor()
                stats = await monitor.get_full_stats()
                thermal_level = int(
                    stats.get("hardware", {}).get("temperature", {}).get("thermal_level", "0")
                )
                # thermal_level: 0=nominal, 1=fair, 2=serious, 3=critical
                thermal_score = max(0.0, 1.0 - (thermal_level / 3.0))
            except Exception:
                pass

        # Weighted average: RAM (40%), CPU (40%), Thermal (20%)
        final_score = (ram_score * 0.4) + (cpu_score * 0.4) + (thermal_score * 0.2)
        return round(max(0.0, min(1.0, final_score)), 2)


_guard = None


def get_resource_guard() -> ResourceGuard:
    global _guard
    if _guard is None:
        _guard = ResourceGuard(
            ram_threshold_pct=float(os.getenv("GUARD_RAM_THRESHOLD", "85.0")),
            cpu_threshold_pct=float(os.getenv("GUARD_CPU_THRESHOLD", "75.0")),
            thermal_threshold=int(os.getenv("GUARD_THERMAL_THRESHOLD", "1")),
        )
    return _guard
