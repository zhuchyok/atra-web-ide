import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import docker
from cube_sandbox_manager import get_cube_manager

logger = logging.getLogger(__name__)


def _resolve_host_sandbox_shared_dir() -> Optional[str]:
    """Resolve a Docker Desktop-safe *host* bind path for sandbox_shared.

    When the Docker API is called from inside a container, ``abspath(...)`` yields
    ``/app/...`` paths. Docker Desktop then tries to mount that path from the Mac
    host → containers stuck in ``Created`` with "mounts denied".
    """
    explicit = (os.environ.get("HOST_SANDBOX_SHARED_DIR") or "").strip()
    if explicit:
        return explicit

    host_root = (os.environ.get("HOST_PROJECT_ROOT") or "").rstrip("/")
    if host_root:
        return f"{host_root}/knowledge_os/sandbox_shared"

    # knowledge_os/app/sandbox_manager.py → knowledge_os/sandbox_shared
    candidate = Path(__file__).resolve().parents[1] / "sandbox_shared"
    path = str(candidate)
    if path.startswith("/app/") or path == "/app":
        logger.error(
            "Sandbox bind path %s is container-local; set HOST_PROJECT_ROOT or "
            "HOST_SANDBOX_SHARED_DIR on the host before creating sandbox-* containers",
            path,
        )
        return None
    return path


class SandboxManager:
    """
    [SINGULARITY 26.7] Hybrid Sandbox Factory.
    Routes tasks to Docker (legacy) or CubeSandbox (high-density ARM64 KVM).
    """

    def __init__(self):
        # Initialize Docker client (legacy support)
        try:
            self.docker_client = docker.from_env()
            logger.info("✅ SandboxManager: Docker client ready")
        except Exception as e:
            self.docker_client = None
            logger.warning(f"⚠️ SandboxManager: Docker not available: {e}")

        # Initialize CubeSandbox (Level 7 backend)
        self.cube_manager = get_cube_manager()
        self.use_cube = os.environ.get("USE_CUBE_SANDBOX", "true").lower() == "true"

        # [SINGULARITY 28.5] Enforce MicroVM isolation for Swarm
        self.enforce_microvm = os.environ.get("ENFORCE_MICROVM_ISOLATION", "true").lower() == "true"

        # [SINGULARITY 28.5] Tmpfs support for MicroVMs
        self.use_tmpfs = os.environ.get("CUBE_USE_TMPFS", "true").lower() == "true"

        self.network_name = "atra-sandbox-net"
        self.host_shared_dir = _resolve_host_sandbox_shared_dir()
        self._ensure_docker_network()

    @property
    def client(self):
        """Alias for docker_client for backward compatibility."""
        return self.docker_client

    def _ensure_docker_network(self):
        """Legacy Docker network setup."""
        if not self.docker_client:
            return
        try:
            self.docker_client.networks.get(self.network_name)
        except docker.errors.NotFound:
            self.docker_client.networks.create(self.network_name, driver="bridge")
            logger.info(f"🌐 Created Docker network {self.network_name}")

    def get_container_name(self, expert_name: str) -> str:
        return f"sandbox-{expert_name.lower().replace(' ', '-')}"

    async def run_in_sandbox(
        self, expert_name: str, command: str, image: str = "python:3.11-slim"
    ) -> Dict[str, Any]:
        """
        [SINGULARITY 26.7] Routing logic: CubeSandbox vs Docker.
        [SINGULARITY 28.5] Enforced isolation and resource management.
        """
        # [SINGULARITY 28.5] Resource Quotas (Simulated via command prefix for now)
        # In a real CubeSandbox implementation, these would be MicroVM flags
        mem_limit = "256M"
        cpu_limit = "0.5"

        # 1. Try CubeSandbox (High-density ARM64 KVM)
        if self.use_cube:
            try:
                # [SINGULARITY 28.5] Wrap command with resource limits and tmpfs context
                # Using 'timeout' and 'nice' as basic OS-level isolation
                isolated_command = f"timeout 60s nice -n 10 {command}"

                result = await self.cube_manager.run_in_sandbox(expert_name, isolated_command)
                if "error" not in result:
                    return {
                        **result,
                        "limits": {"memory": mem_limit, "cpu": cpu_limit},
                        "storage": "tmpfs-simulated",
                    }
            except Exception as e:
                logger.error(f"⚠️ CubeSandbox failed, falling back to Docker: {e}")

        # 2. Fallback to Docker (Legacy)
        if self.enforce_microvm and self.use_cube:
            logger.warning(
                f"🚨 [ISOLATION] Enforced MicroVM failed for {expert_name}, blocking fallback for safety."
            )
            return {"error": "Enforced MicroVM isolation failed"}
        if not self.docker_client:
            return {"error": "No sandbox backend available (Docker/Cube)"}

        container_name = self.get_container_name(expert_name)
        mount_path = self.host_shared_dir or _resolve_host_sandbox_shared_dir()
        if not mount_path:
            return {
                "error": (
                    "Sandbox host bind path unavailable. Set HOST_PROJECT_ROOT or "
                    "HOST_SANDBOX_SHARED_DIR (Docker Desktop cannot mount /app/...)."
                )
            }
        try:
            Path(mount_path).mkdir(parents=True, exist_ok=True)
        except OSError as mkdir_err:
            # Inside container the host path may not exist locally; Docker still
            # needs the path string. Creation on host is best-effort.
            logger.debug("sandbox shared mkdir skipped for %s: %s", mount_path, mkdir_err)

        try:
            try:
                container = self.docker_client.containers.get(container_name)
                if container.status != "running":
                    try:
                        container.start()
                    except Exception as start_err:
                        # Broken Created containers from bad /app bind mounts.
                        logger.warning(
                            "Sandbox %s start failed (%s); recreating with host path %s",
                            container_name,
                            start_err,
                            mount_path,
                        )
                        try:
                            container.remove(force=True)
                        except Exception:
                            pass
                        raise docker.errors.NotFound("recreate after bad mount") from start_err
            except docker.errors.NotFound:
                logger.info(f"🚀 Creating Docker sandbox for {expert_name}...")
                container = self.docker_client.containers.run(
                    image,
                    command="tail -f /dev/null",
                    name=container_name,
                    detach=True,
                    network=self.network_name,
                    mem_limit="512m",
                    nano_cpus=1000000000,
                    restart_policy={"Name": "unless-stopped"},
                    working_dir="/workspace",
                    volumes={mount_path: {"bind": "/workspace", "mode": "rw"}},
                )

            logger.info(f"🧪 [DOCKER-SANDBOX:{expert_name}] Executing: {command}")
            exec_result = container.exec_run(command, workdir="/workspace")

            return {
                "exit_code": exec_result.exit_code,
                "output": exec_result.output.decode("utf-8", errors="replace"),
                "container": container_name,
                "isolation": "container-cgroups",
            }

        except Exception as e:
            logger.error(f"❌ Docker sandbox error for {expert_name}: {e}")
            return {"error": str(e)}

    def cleanup_sandbox(self, expert_name: str):
        """Cleanup both backends."""
        self.cube_manager.cleanup_sandbox(expert_name)

        if self.docker_client:
            container_name = self.get_container_name(expert_name)
            try:
                container = self.docker_client.containers.get(container_name)
                container.stop()
                container.remove()
                logger.info(f"🧹 Docker sandbox {container_name} removed")
            except docker.errors.NotFound:
                pass


# Global instance
_manager = None


def get_sandbox_manager():
    global _manager
    if _manager is None:
        _manager = SandboxManager()
    return _manager
