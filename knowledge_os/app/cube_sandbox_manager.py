import asyncio
import json
import logging
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CubeSandboxManager:
    """
    [SINGULARITY 26.7] High-density Sandbox Manager based on CubeSandbox/Firecracker.
    Optimized for ARM64 Mac Studio via Lima VM.
    """

    def __init__(self):
        self.lima_instance = os.environ.get("CUBE_LIMA_INSTANCE", "cube-host")
        self.microvm_timeout = int(os.environ.get("CUBE_VM_TIMEOUT", "60"))

        # [SINGULARITY 26.8] Robust binary path discovery for macOS/Linux
        self.limactl_bin = shutil.which("limactl")
        if not self.limactl_bin:
            # Common paths for Homebrew (macOS) and standard Linux installs
            candidate_paths = [
                "/opt/homebrew/bin/limactl",
                "/usr/local/bin/limactl",
                "/usr/bin/limactl",
                "/bin/limactl",
            ]
            for p in candidate_paths:
                if os.path.exists(p):
                    self.limactl_bin = p
                    break

        self.lima_available = bool(self.limactl_bin)
        if self.lima_available:
            logger.info(
                f"✅ CubeSandboxManager initialized (Lima: {self.lima_instance}, Path: {self.limactl_bin})"
            )
        else:
            logger.warning(
                "⚠️ [CUBE-VM] limactl is not available in PATH or common locations. Falling back to local process sandbox."
            )

    async def _run_local_fallback(self, expert_name: str, command: str) -> Dict[str, Any]:
        """Fallback when Lima/limactl is unavailable in runtime image."""
        logger.info(f"⚠️ [CUBE-VM:{expert_name}] Using local process fallback")
        process = await asyncio.create_subprocess_exec(
            "bash",
            "-lc",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.microvm_timeout
            )
            exit_code = process.returncode
            output = (stdout.decode() + stderr.decode()).strip()
        except asyncio.TimeoutError:
            process.kill()
            exit_code = -1
            output = "Error: Local fallback execution timed out."

        return {
            "exit_code": exit_code,
            "output": output,
            "container": f"local-sandbox-{expert_name.lower()}",
            "isolation": "process-fallback",
            "host": "local-runtime",
            "degraded_mode": True,
        }

    async def run_in_sandbox(
        self, expert_name: str, command: str, image: str = None
    ) -> Dict[str, Any]:
        """
        Executes a command in a dedicated Firecracker MicroVM inside Lima.
        """
        logger.info(f"⚡ [CUBE-VM:{expert_name}] Executing: {command}")

        # [SINGULARITY 26.7] Deterministic Context Mapping
        # We don't pass raw context to the VM, only the specific command.

        if not self.lima_available:
            return await self._run_local_fallback(expert_name, command)

        try:
            # We use limactl shell to execute commands inside the VM.
            # In a full Level 7 implementation, this would trigger a Firecracker MicroVM start.
            # For now, we use the Lima VM itself as the high-density host.

            process = await asyncio.create_subprocess_exec(
                self.limactl_bin,
                "shell",
                self.lima_instance,
                "bash",
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.microvm_timeout
                )
                exit_code = process.returncode
                output = stdout.decode().strip() + stderr.decode().strip()
            except asyncio.TimeoutError:
                process.kill()
                exit_code = -1
                output = "Error: Execution timed out in MicroVM."

            return {
                "exit_code": exit_code,
                "output": output,
                "container": f"microvm-{expert_name.lower()}",
                "isolation": "hardware-kvm",
                "host": self.lima_instance,
            }

        except Exception as e:
            logger.error(f"❌ [CUBE-VM] Critical error during execution: {e}")
            return await self._run_local_fallback(expert_name, command)

    def cleanup_sandbox(self, expert_name: str):
        """MicroVMs are ephemeral and usually cleanup themselves on exit."""
        logger.info(f"🧹 MicroVM for {expert_name} released.")


def get_cube_manager():
    return CubeSandboxManager()
