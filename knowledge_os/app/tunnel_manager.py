"""
Автоматическое управление SSH туннелем для доступа к Ollama на MacBook.
Обеспечивает стабильное соединение с автоматическим переподключением.
Поддерживает autossh для автоматического переподключения.
"""

import asyncio
import logging
import os
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)


class TunnelManager:
    """Управление SSH reverse tunnel для доступа к Ollama."""

    def __init__(
        self, remote_host: str, remote_pass: str, tunnel_port: int = 11435, local_port: int = 11434
    ):
        self.remote_host = remote_host
        self.remote_pass = remote_pass
        self.tunnel_port = tunnel_port
        self.local_port = local_port
        self.tunnel_process: Optional[subprocess.Popen] = None
        self._running = False

    def create_tunnel(self) -> bool:
        """Создать SSH reverse tunnel с использованием autossh (если доступен)."""
        try:
            # Проверяем наличие autossh (предпочтительно)
            use_autossh = False
            try:
                subprocess.run(["which", "autossh"], capture_output=True, check=True)
                use_autossh = True
                logger.info("✅ autossh найден, используем для автоматического переподключения")
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.debug("autossh не найден, используем обычный ssh")

            # Проверяем наличие sshpass
            use_sshpass = False
            try:
                subprocess.run(["which", "sshpass"], capture_output=True, check=True)
                use_sshpass = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.debug("sshpass не найден, используем SSH ключ")

            # Убиваем старые туннели
            subprocess.run(
                ["pkill", "-f", f"ssh.*{self.tunnel_port}:localhost:{self.local_port}"],
                capture_output=True,
            )
            subprocess.run(
                ["pkill", "-f", f"autossh.*{self.tunnel_port}:localhost:{self.local_port}"],
                capture_output=True,
            )
            time.sleep(1)

            # Создаем новый туннель
            if use_autossh:
                # Используем autossh для автоматического переподключения
                base_cmd = [
                    "autossh",
                    "-M",
                    "0",
                ]  # -M 0 отключает мониторинг порта (используем встроенный)
                if use_sshpass:
                    cmd = ["sshpass", "-p", self.remote_pass] + base_cmd
                else:
                    cmd = base_cmd

                cmd.extend(
                    [
                        "-f",
                        "-N",  # Background, no command
                        "-o",
                        "StrictHostKeyChecking=no",
                        "-o",
                        "ServerAliveInterval=60",
                        "-o",
                        "ServerAliveCountMax=3",
                        "-o",
                        "ExitOnForwardFailure=yes",
                        "-R",
                        f"{self.tunnel_port}:localhost:{self.local_port}",
                        self.remote_host,
                    ]
                )
            else:
                # Обычный ssh
                if use_sshpass:
                    cmd = [
                        "sshpass",
                        "-p",
                        self.remote_pass,
                        "ssh",
                        "-o",
                        "StrictHostKeyChecking=no",
                        "-o",
                        "ServerAliveInterval=60",
                        "-o",
                        "ServerAliveCountMax=3",
                        "-f",
                        "-N",
                        "-R",
                        f"{self.tunnel_port}:localhost:{self.local_port}",
                        self.remote_host,
                    ]
                else:
                    # Если нет ни autossh, ни sshpass, просто проверяем доступность
                    logger.info(
                        "ℹ️ Туннель должен быть создан вручную с MacBook (рекомендуется использовать LaunchDaemon)"
                    )
                    return self.check_tunnel()

            self.tunnel_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            # Проверяем, что процесс запустился
            time.sleep(2)
            if self.tunnel_process.poll() is None:
                logger.info(
                    f"✅ SSH tunnel создан: {self.tunnel_port} -> localhost:{self.local_port} (autossh: {use_autossh})"
                )
                return True
            else:
                stderr = (
                    self.tunnel_process.stderr.read().decode() if self.tunnel_process.stderr else ""
                )
                logger.error(f"❌ SSH tunnel не запустился: {stderr}")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка создания tunnel: {e}")
            return False

    def check_tunnel(self) -> bool:
        """Проверить доступность туннеля локально (порт должен быть доступен на localhost)."""
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("localhost", self.tunnel_port))
            sock.close()
            return result == 0
        except Exception:
            # Также проверяем через SSH на сервере (fallback)
            try:
                cmd = [
                    "sshpass",
                    "-p",
                    self.remote_pass,
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "ConnectTimeout=2",
                    self.remote_host,
                    f"curl -s --connect-timeout 2 http://localhost:{self.tunnel_port}/api/tags > /dev/null 2>&1",
                ]
                result = subprocess.run(cmd, capture_output=True, timeout=5)
                return result.returncode == 0
            except Exception:
                return False

    async def monitor_tunnel(self, check_interval: int = 60):
        """Мониторинг и автоматическое переподключение туннеля."""
        self._running = True
        logger.info("🔍 Запущен мониторинг SSH tunnel")

        while self._running:
            if not self.check_tunnel():
                logger.warning("⚠️ Tunnel недоступен, пересоздаю...")
                self.create_tunnel()
            await asyncio.sleep(check_interval)

    def stop(self):
        """Остановить туннель и мониторинг."""
        self._running = False
        if self.tunnel_process:
            self.tunnel_process.terminate()
            self.tunnel_process.wait()
        logger.info("🛑 SSH tunnel остановлен")


# Глобальный экземпляр
_tunnel_manager: Optional[TunnelManager] = None


def get_tunnel_manager() -> Optional[TunnelManager]:
    """Получить глобальный экземпляр TunnelManager."""
    global _tunnel_manager
    if _tunnel_manager is None:
        import os

        remote_host = os.getenv("SSH_REMOTE_HOST", "root@185.177.216.15")
        remote_pass = os.getenv("SSH_REMOTE_PASS", "u44Ww9NmtQj,XG")
        _tunnel_manager = TunnelManager(remote_host, remote_pass)
    return _tunnel_manager


def get_tunnel_status() -> str:
    """Получить статус туннеля."""
    manager = get_tunnel_manager()
    if not manager:
        return "не настроен"
    if manager.check_tunnel():
        return "активен"
    return "неактивен"


async def ensure_tunnel():
    """Убедиться, что туннель активен. Автоматически создает туннель если его нет."""
    manager = get_tunnel_manager()
    if not manager:
        logger.warning("⚠️ TunnelManager не настроен")
        return False

    # Проверяем текущий статус
    if manager.check_tunnel():
        logger.debug("✅ SSH tunnel уже активен")
        return True

    # Туннель не активен - создаем его
    logger.info("🔧 SSH tunnel неактивен, создаю автоматически...")
    try:
        success = manager.create_tunnel()
        if success:
            logger.info("✅ SSH tunnel успешно создан")
            return True
        else:
            logger.warning("⚠️ Не удалось создать SSH tunnel автоматически")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка создания SSH tunnel: {e}")
        return False
