import logging
import os
import time
from typing import Any, Dict, List, Optional

import docker

logger = logging.getLogger(__name__)


class SandboxManager:
    """
    Управляет изолированными Docker-песочницами для экспертов.
    Реализует жизненный цикл: Create -> Execute -> Monitor -> Destroy.
    """

    def __init__(self):
        try:
            self.client = docker.from_env()
            logger.info("✅ SandboxManager: Подключен к Docker")
        except Exception as e:
            self.client = None
            logger.error(f"❌ SandboxManager: Ошибка подключения к Docker: {e}")

        self.network_name = "atra-sandbox-net"
        self.host_shared_dir = os.environ.get("HOST_SANDBOX_SHARED_DIR")
        self._ensure_network()

    def _ensure_network(self):
        """Создает изолированную сеть для песочниц, если её нет."""
        if not self.client:
            return
        try:
            self.client.networks.get(self.network_name)
        except docker.errors.NotFound:
            self.client.networks.create(self.network_name, driver="bridge")
            logger.info(f"🌐 Создана сеть {self.network_name}")

    def get_container_name(self, expert_name: str) -> str:
        return f"sandbox-{expert_name.lower().replace(' ', '-')}"

    async def run_in_sandbox(
        self, expert_name: str, command: str, image: str = "python:3.11-slim"
    ) -> Dict[str, Any]:
        """
        Запускает команду в песочнице эксперта.
        Если контейнера нет — создает его.
        """
        if not self.client:
            return {"error": "Docker client not available"}

        container_name = self.get_container_name(expert_name)
        
        # Определяем путь для монтирования
        # Если задан HOST_SANDBOX_SHARED_DIR, используем его (для Docker-in-Docker на macOS)
        # Иначе используем абсолютный путь в текущей ФС
        mount_path = self.host_shared_dir or os.path.abspath("./knowledge_os/sandbox_shared")

        try:
            try:
                container = self.client.containers.get(container_name)
                if container.status != "running":
                    container.start()
            except docker.errors.NotFound:
                logger.info(f"🚀 Создание новой песочницы для {expert_name}... Mount: {mount_path}")
                container = self.client.containers.run(
                    image,
                    command="tail -f /dev/null",  # Держим контейнер запущенным
                    name=container_name,
                    detach=True,
                    network=self.network_name,
                    mem_limit="512m",  # Увеличено для микросервисов
                    nano_cpus=1000000000,  # 1.0 CPU для 10/10
                    working_dir="/workspace",
                    volumes={
                        mount_path: {
                            "bind": "/workspace",
                            "mode": "rw",
                        }
                    },
                )

            # Выполнение команды
            logger.info(f"🧪 [SANDBOX:{expert_name}] Выполнение: {command}")
            exec_result = container.exec_run(command, workdir="/workspace")

            return {
                "exit_code": exec_result.exit_code,
                "output": exec_result.output.decode("utf-8", errors="replace"),
                "container": container_name,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка песочницы {expert_name}: {e}")
            return {"error": str(e)}

    async def deploy_microservice(
        self, name: str, code: str, requirements: List[str] = None
    ) -> Dict[str, Any]:
        """
        Singularity 10.0: Автономный деплой микросервиса.
        Создает Dockerfile, собирает образ и запускает сервис.
        """
        if not self.client:
            return {"error": "No Docker"}

        svc_dir = f"./knowledge_os/sandbox_shared/services/{name}"
        os.makedirs(svc_dir, exist_ok=True)

        # 1. Пишем код и зависимости
        with open(f"{svc_dir}/app.py", "w") as f:
            f.write(code)
        with open(f"{svc_dir}/requirements.txt", "w") as f:
            f.write("\n".join(requirements or ["fastapi", "uvicorn"]))

        # 2. Генерируем Dockerfile
        dockerfile = """
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
        """
        with open(f"{svc_dir}/Dockerfile", "w") as f:
            f.write(dockerfile)

        # 3. Сборка и запуск
        logger.info(f"🏗️ [AUTONOMOUS] Сборка сервиса {name}...")
        try:
            image, _ = self.client.images.build(path=svc_dir, tag=f"atra-svc-{name}")
            container = self.client.containers.run(
                image,
                name=f"svc-{name}",
                detach=True,
                network=self.network_name,
                restart_policy={"Name": "always"},
            )
            return {
                "status": "deployed",
                "container": container.id[:12],
                "url": f"http://{name}:8000",
            }
        except Exception as e:
            return {"error": str(e)}

    def cleanup_sandbox(self, expert_name: str):
        """Удаляет контейнер песочницы."""
        if not self.client:
            return
        container_name = self.get_container_name(expert_name)
        try:
            container = self.client.containers.get(container_name)
            container.stop()
            container.remove()
            logger.info(f"🧹 Песочница {container_name} удалена")
        except docker.errors.NotFound:
            pass


# Глобальный экземпляр
_manager = None


def get_sandbox_manager():
    global _manager
    if _manager is None:
        _manager = SandboxManager()
    return _manager
