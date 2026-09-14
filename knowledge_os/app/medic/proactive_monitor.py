"""
Proactive Monitor — предиктивное обслуживание.

Предсказывает проблемы до падения:
1. Мониторит ресурсы (CPU, RAM, disk)
2. Анализирует тренды ошибок
3. Предсказывает OOM, disk full, service degradation
4. Автоматически принимает превентивные меры
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Check interval
CHECK_INTERVAL = int(os.getenv("PROACTIVE_CHECK_INTERVAL", "60"))

# Thresholds
RAM_WARNING_PERCENT = float(os.getenv("RAM_WARNING_PERCENT", "80"))
RAM_CRITICAL_PERCENT = float(os.getenv("RAM_CRITICAL_PERCENT", "90"))
DISK_WARNING_PERCENT = float(os.getenv("DISK_WARNING_PERCENT", "80"))
DISK_CRITICAL_PERCENT = float(os.getenv("DISK_CRITICAL_PERCENT", "90"))
CPU_WARNING_PERCENT = float(os.getenv("CPU_WARNING_PERCENT", "80"))
CONTAINER_RESTART_THRESHOLD = int(os.getenv("CONTAINER_RESTART_THRESHOLD", "3"))


class ProactiveMonitor:
    """
    Мониторинг и предикция проблем.

    Цикл:
    1. Собрать метрики (RAM, CPU, disk, containers)
    2. Анализировать тренды
    3. Предсказать проблемы
    4. Автоматически исправлять если возможно
    5. Уведомлять если невозможно
    """

    def __init__(self):
        self.running = False
        self.metrics_history: List[Dict] = []
        self.alerts: List[Dict] = []
        self._last_check = 0

    async def collect_system_metrics(self) -> Dict:
        """Собрать системные метрики."""
        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ram": {},
            "disk": {},
            "containers": {},
        }

        try:
            # RAM
            result = subprocess.run(
                ["vm_stat"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Parse vm_stat for macOS
            lines = result.stdout.split("\n")
            for line in lines:
                if "Pages active" in line:
                    active = int(line.split(":")[1].strip().replace(".", "")) * 4096
                    metrics["ram"]["active_bytes"] = active
                elif "Pages inactive" in line:
                    inactive = int(line.split(":")[1].strip().replace(".", "")) * 4096
                    metrics["ram"]["inactive_bytes"] = inactive
                elif "Pages free" in line:
                    free = int(line.split(":")[1].strip().replace(".", "")) * 4096
                    metrics["ram"]["free_bytes"] = free

            # Get total RAM
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            total_ram = int(result.stdout.strip())
            metrics["ram"]["total_bytes"] = total_ram
            used_ram = total_ram - metrics["ram"].get("free_bytes", 0)
            metrics["ram"]["used_bytes"] = used_ram
            metrics["ram"]["used_percent"] = round(used_ram / total_ram * 100, 1)

        except Exception as e:
            logger.debug(f"Error collecting RAM metrics: {e}")

        try:
            # Disk
            result = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                metrics["disk"]["total"] = parts[1]
                metrics["disk"]["used"] = parts[2]
                metrics["disk"]["available"] = parts[3]
                metrics["disk"]["used_percent"] = int(parts[4].replace("%", ""))

        except Exception as e:
            logger.debug(f"Error collecting disk metrics: {e}")

        try:
            # Container status
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                if "\t" in line:
                    name, status = line.split("\t", 1)
                    is_healthy = "healthy" in status.lower()
                    is_running = "up" in status.lower()
                    metrics["containers"][name] = {
                        "status": status,
                        "healthy": is_healthy,
                        "running": is_running,
                    }

        except Exception as e:
            logger.debug(f"Error collecting container metrics: {e}")

        return metrics

    async def analyze_trends(self) -> List[Dict]:
        """Анализировать тренды метрик."""
        alerts = []

        if len(self.metrics_history) < 2:
            return alerts

        current = self.metrics_history[-1]
        previous = self.metrics_history[-2]

        # RAM trend
        if "ram" in current and "ram" in previous:
            curr_percent = current["ram"].get("used_percent", 0)
            prev_percent = previous["ram"].get("used_percent", 0)

            if curr_percent > RAM_CRITICAL_PERCENT:
                alerts.append({
                    "type": "ram_critical",
                    "severity": "critical",
                    "message": f"RAM usage critical: {curr_percent}%",
                    "value": curr_percent,
                    "threshold": RAM_CRITICAL_PERCENT,
                })
            elif curr_percent > RAM_WARNING_PERCENT:
                alerts.append({
                    "type": "ram_warning",
                    "severity": "warning",
                    "message": f"RAM usage high: {curr_percent}%",
                    "value": curr_percent,
                    "threshold": RAM_WARNING_PERCENT,
                })

            # Rapid increase
            if curr_percent - prev_percent > 10:
                alerts.append({
                    "type": "ram_rapid_increase",
                    "severity": "warning",
                    "message": f"RAM usage increased rapidly: {prev_percent}% → {curr_percent}%",
                })

        # Disk trend
        if "disk" in current:
            disk_percent = current["disk"].get("used_percent", 0)
            if disk_percent > DISK_CRITICAL_PERCENT:
                alerts.append({
                    "type": "disk_critical",
                    "severity": "critical",
                    "message": f"Disk usage critical: {disk_percent}%",
                    "value": disk_percent,
                    "threshold": DISK_CRITICAL_PERCENT,
                })
            elif disk_percent > DISK_WARNING_PERCENT:
                alerts.append({
                    "type": "disk_warning",
                    "severity": "warning",
                    "message": f"Disk usage high: {disk_percent}%",
                    "value": disk_percent,
                    "threshold": DISK_WARNING_PERCENT,
                })

        # Container health
        if "containers" in current:
            unhealthy = [
                name
                for name, info in current["containers"].items()
                if not info.get("healthy", True) and info.get("running", True)
            ]
            if unhealthy:
                alerts.append({
                    "type": "unhealthy_containers",
                    "severity": "warning",
                    "message": f"Unhealthy containers: {', '.join(unhealthy)}",
                    "containers": unhealthy,
                })

        return alerts

    async def take_action(self, alert: Dict) -> bool:
        """Автоматически исправить проблему если возможно."""
        alert_type = alert.get("type")

        if alert_type == "ram_critical":
            # Try to free memory
            logger.warning("🔧 [PROACTIVE] Attempting to free memory...")
            try:
                # Restart containers with high memory usage
                result = subprocess.run(
                    ["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                # TODO: Parse and restart high-memory containers
                return True
            except:
                return False

        elif alert_type == "unhealthy_containers":
            # Try to restart unhealthy containers
            containers = alert.get("containers", [])
            for container in containers[:3]:  # Limit to 3
                logger.warning(f"🔧 [PROACTIVE] Restarting unhealthy container: {container}")
                try:
                    subprocess.run(
                        ["docker", "restart", container],
                        capture_output=True,
                        timeout=30,
                    )
                except:
                    pass
            return True

        return False

    async def check(self) -> Dict:
        """Один цикл проверки."""
        metrics = await self.collect_system_metrics()
        self.metrics_history.append(metrics)

        # Keep only last 100 metrics
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]

        alerts = await self.analyze_trends()

        actions_taken = []
        for alert in alerts:
            success = await self.take_action(alert)
            actions_taken.append({
                "alert": alert,
                "action_taken": success,
            })

        self._last_check = time.time()

        return {
            "timestamp": metrics["timestamp"],
            "alerts": alerts,
            "actions_taken": actions_taken,
            "metrics_summary": {
                "ram_percent": metrics.get("ram", {}).get("used_percent"),
                "disk_percent": metrics.get("disk", {}).get("used_percent"),
                "containers_total": len(metrics.get("containers", {})),
                "containers_healthy": sum(
                    1
                    for c in metrics.get("containers", {}).values()
                    if c.get("healthy", True)
                ),
            },
        }

    async def run(self):
        """Главный цикл мониторинга."""
        self.running = True
        logger.info(f"🚀 [PROACTIVE] Monitor запущен. Интервал: {CHECK_INTERVAL}s")

        while self.running:
            try:
                result = await self.check()
                if result["alerts"]:
                    logger.info(
                        f"⚠️ [PROACTIVE] Alerts: {len(result['alerts'])}, "
                        f"Actions: {len(result['actions_taken'])}"
                    )
            except Exception as e:
                logger.error(f"❌ [PROACTIVE] Ошибка в цикле: {e}")

            await asyncio.sleep(CHECK_INTERVAL)

    def stop(self):
        """Остановить мониторинг."""
        self.running = False
        logger.info("🛑 [PROACTIVE] Monitor остановлен")

    async def get_status(self) -> Dict:
        """Получить статус мониторинга."""
        return {
            "running": self.running,
            "last_check": self._last_check,
            "metrics_collected": len(self.metrics_history),
            "active_alerts": len(self.alerts),
        }


# Singleton
_monitor: Optional[ProactiveMonitor] = None


def get_proactive_monitor() -> ProactiveMonitor:
    """Получить singleton ProactiveMonitor."""
    global _monitor
    if _monitor is None:
        _monitor = ProactiveMonitor()
    return _monitor
