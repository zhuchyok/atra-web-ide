"""
[SINGULARITY 20.0] Self-Healing Infrastructure.
Automatically monitors and restarts critical SSH/VNC tunnels.
"""

import asyncio
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

TUNNELS = [
    {
        "name": "Frontend Tunnel (185:3002)",
        "check_cmd": "curl -sf --connect-timeout 2 http://185.177.216.15:3002",
        "restart_script": "bash scripts/setup_tunnel_185_autostart.sh",
    },
    {
        "name": "VNC Tunnel (185:5909)",
        "check_cmd": "nc -zv 185.177.216.15 5909",
        "restart_script": "pkill -f 'ssh.*590' || true && ssh -f -N -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -R 5909:127.0.0.1:5900 root@185.177.216.15",
    },
]


async def check_and_heal_tunnels():
    """Checks all tunnels and restarts them if they are down."""
    logger.info("🛠️ [SELF-HEALING] Checking infrastructure health...")

    for tunnel in TUNNELS:
        try:
            # Check if tunnel is alive
            process = await asyncio.create_subprocess_shell(
                tunnel["check_cmd"], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await process.wait()

            if process.returncode != 0:
                logger.warning(
                    f"🚨 [SELF-HEALING] Tunnel '{tunnel['name']}' is DOWN. Restarting..."
                )
                # Run restart command
                subprocess.Popen(tunnel["restart_script"], shell=True)
                logger.info(f"✅ [SELF-HEALING] Restart command sent for '{tunnel['name']}'")
            else:
                logger.info(f"🟢 [SELF-HEALING] Tunnel '{tunnel['name']}' is healthy.")

        except Exception as e:
            logger.error(f"❌ [SELF-HEALING] Error checking tunnel '{tunnel['name']}': {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(check_and_heal_tunnels())
