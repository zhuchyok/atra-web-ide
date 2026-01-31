"""
Self-Healing Module для Singularity 5.0
Автоматическое исправление и перезапуск сервисов при сбоях
"""

import asyncio
import os
import subprocess
import logging
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncpg

logger = logging.getLogger(__name__)

# Config
DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
TG_TOKEN = os.getenv('TG_TOKEN', '8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU')
CHAT_ID = os.getenv('CHAT_ID', '556251171')

# Настройки self-healing
MAX_FAILURES_BEFORE_RESTART = 3  # Количество провалов перед перезапуском
HEALTH_CHECK_INTERVAL = 60  # Интервал проверки здоровья (секунды)
FAILURE_WINDOW = 300  # Окно времени для подсчета провалов (5 минут)

# URL узлов для проверки
MAC_LLM_URL = os.getenv('MAC_LLM_URL', 'http://localhost:11434')
SERVER_LLM_URL = os.getenv('SERVER_LLM_URL', 'http://localhost:11434')

class SelfHealingManager:
    """
    Менеджер для автоматического исправления сбоев в системе.
    Отслеживает health checks и автоматически перезапускает сервисы при необходимости.
    """
    
    def __init__(self):
        self.failure_counts = {}  # {node_url: [timestamps of failures]}
        self.last_restart = {}  # {node_url: timestamp}
        self.restart_cooldown = 600  # 10 минут между перезапусками
    
    async def check_node_health(self, node_url: str) -> bool:
        """Проверка здоровья узла"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{node_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"⚠️ Node {node_url} health check failed: {e}")
            return False
    
    def record_failure(self, node_url: str):
        """Запись провала health check"""
        current_time = datetime.now()
        
        if node_url not in self.failure_counts:
            self.failure_counts[node_url] = []
        
        # Добавляем текущее время провала
        self.failure_counts[node_url].append(current_time)
        
        # Удаляем старые провалы (старше FAILURE_WINDOW)
        cutoff_time = current_time - timedelta(seconds=FAILURE_WINDOW)
        self.failure_counts[node_url] = [
            ts for ts in self.failure_counts[node_url] 
            if ts > cutoff_time
        ]
    
    def record_success(self, node_url: str):
        """Запись успешного health check (сбрасываем счетчик)"""
        if node_url in self.failure_counts:
            # Оставляем только последние провалы (на случай кратковременных сбоев)
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(seconds=FAILURE_WINDOW)
            self.failure_counts[node_url] = [
                ts for ts in self.failure_counts[node_url] 
                if ts > cutoff_time
            ]
    
    def should_restart(self, node_url: str) -> bool:
        """Определяет, нужно ли перезапускать узел"""
        if node_url not in self.failure_counts:
            return False
        
        # Проверяем количество провалов
        failures = len(self.failure_counts[node_url])
        if failures < MAX_FAILURES_BEFORE_RESTART:
            return False
        
        # Проверяем cooldown (не перезапускаем слишком часто)
        if node_url in self.last_restart:
            time_since_restart = (datetime.now() - self.last_restart[node_url]).total_seconds()
            if time_since_restart < self.restart_cooldown:
                logger.info(f"⏳ Node {node_url} в cooldown, пропускаем перезапуск")
                return False
        
        return True
    
    async def restart_ollama_mac(self) -> bool:
        """Перезапуск Ollama на MacBook"""
        try:
            logger.info("🔄 Перезапуск Ollama на MacBook...")
            
            # Останавливаем Ollama
            subprocess.run(["pkill", "-f", "ollama"], check=False)
            await asyncio.sleep(2)
            
            # Запускаем Ollama (если установлен через Homebrew)
            result = subprocess.run(
                ["brew", "services", "restart", "ollama"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("✅ Ollama перезапущен на MacBook")
                return True
            else:
                # Альтернативный способ: запуск напрямую
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.info("✅ Ollama запущен напрямую на MacBook")
                return True
        except Exception as e:
            logger.error(f"❌ Ошибка перезапуска Ollama на MacBook: {e}")
            return False
    
    async def restart_ollama_server(self) -> bool:
        """Перезапуск Ollama на сервере через SSH"""
        try:
            logger.info("🔄 Перезапуск Ollama на сервере...")
            
            # Команды для перезапуска через SSH
            commands = [
                "pkill -f ollama || true",
                "sleep 2",
                "systemctl restart ollama || service ollama restart || /usr/local/bin/ollama serve &"
            ]
            
            # Выполняем через SSH (требует настройки SSH ключей или пароля)
            # Для безопасности используем переменные окружения
            server = os.getenv('SERVER_HOST', 'localhost')
            ssh_user = os.getenv('SERVER_USER', 'root')
            
            # Пробуем через systemd (если доступен)
            result = subprocess.run(
                ["ssh", f"{ssh_user}@{server}", "systemctl restart ollama"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("✅ Ollama перезапущен на сервере через systemd")
                return True
            else:
                logger.warning("⚠️ Не удалось перезапустить через systemd, требуется ручное вмешательство")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка перезапуска Ollama на сервере: {e}")
            return False
    
    async def restart_node(self, node_url: str) -> bool:
        """Перезапуск узла в зависимости от его типа"""
        if "localhost" in node_url or "127.0.0.1" in node_url:
            return await self.restart_ollama_mac()
        else:
            return await self.restart_ollama_server()
    
    async def send_telegram_alert(self, message: str, priority: str = "high"):
        """Отправка алерта в Telegram"""
        try:
            emoji = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            async with httpx.AsyncClient() as client:
                await client.post(
                    url,
                    data={
                        'chat_id': CHAT_ID,
                        'text': f"{emoji} *SELF-HEALING ALERT*\n\n{message}",
                        'parse_mode': 'Markdown'
                    },
                    timeout=10.0
                )
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
    
    async def heal_node(self, node_url: str, node_name: str) -> bool:
        """Попытка исправить узел"""
        logger.warning(f"🛠️ [SELF-HEALING] Попытка исправить узел {node_name} ({node_url})")
        
        # Перезапускаем узел
        success = await self.restart_node(node_url)
        
        if success:
            # Обновляем время последнего перезапуска
            self.last_restart[node_url] = datetime.now()
            
            # Сбрасываем счетчик провалов
            if node_url in self.failure_counts:
                self.failure_counts[node_url] = []
            
            # Выполняем warmup моделей после перезапуска
            try:
                from model_health_manager import get_model_health_manager
                health_manager = get_model_health_manager(node_url)
                
                # Получаем список моделей для этого узла
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{node_url}/api/tags")
                    if response.status_code == 200:
                        models = response.json().get("models", [])
                        for model in models[:3]:  # Прогреваем первые 3 модели
                            model_name = model.get("name")
                            if model_name:
                                await health_manager.warmup_model(model_name)
                                logger.info(f"🔥 [SELF-HEALING] Модель {model_name} прогрета после перезапуска")
            except Exception as e:
                logger.debug(f"Warmup после перезапуска не удался: {e}")
            
            # Отправляем уведомление
            await self.send_telegram_alert(
                f"✅ Узел {node_name} успешно перезапущен после {MAX_FAILURES_BEFORE_RESTART} провалов health check",
                "high"
            )
            
            logger.info(f"✅ [SELF-HEALING] Узел {node_name} исправлен")
            return True
        else:
            await self.send_telegram_alert(
                f"❌ Не удалось перезапустить узел {node_name}. Требуется ручное вмешательство.",
                "high"
            )
            logger.error(f"❌ [SELF-HEALING] Не удалось исправить узел {node_name}")
            return False
    
    async def check_and_heal(self, nodes: List[Dict]) -> List[Dict]:
        """
        Проверяет здоровье узлов и автоматически исправляет при необходимости.
        Возвращает список узлов с обновленным статусом.
        """
        healed_nodes = []
        
        for node in nodes:
            node_url = node.get('url')
            node_name = node.get('name', 'Unknown')
            
            if not node_url:
                continue
            
            # Проверяем здоровье
            is_healthy = await self.check_node_health(node_url)
            
            if is_healthy:
                self.record_success(node_url)
                node['status'] = 'online'
                node['healed'] = False
            else:
                self.record_failure(node_url)
                node['status'] = 'offline'
                
                # Проверяем, нужно ли перезапускать
                if self.should_restart(node_url):
                    logger.warning(f"⚠️ [SELF-HEALING] Узел {node_name} требует перезапуска")
                    healed = await self.heal_node(node_url, node_name)
                    node['healed'] = healed
                    
                    # Проверяем еще раз после перезапуска
                    await asyncio.sleep(5)  # Даем время на запуск
                    is_healthy_after = await self.check_node_health(node_url)
                    if is_healthy_after:
                        node['status'] = 'online'
                        self.record_success(node_url)
            
            healed_nodes.append(node)
        
        return healed_nodes

async def run_self_healing_cycle():
    """Основной цикл self-healing"""
    logger.info("🛠️ [SELF-HEALING] Запуск цикла самовосстановления...")
    
    manager = SelfHealingManager()
    
    # Список узлов для мониторинга
    nodes = [
        {"name": "MacBook (Normal)", "url": MAC_LLM_URL},
        {"name": "Server (Light)", "url": SERVER_LLM_URL}
    ]
    
    # Проверяем и исправляем узлы
    healed_nodes = await manager.check_and_heal(nodes)
    
    # Логируем результаты
    for node in healed_nodes:
        status_emoji = "✅" if node.get('status') == 'online' else "❌"
        healed_emoji = "🔧" if node.get('healed') else ""
        logger.info(f"{status_emoji} {healed_emoji} {node['name']}: {node.get('status', 'unknown')}")
    
    logger.info("✅ [SELF-HEALING] Цикл завершен")

if __name__ == "__main__":
    asyncio.run(run_self_healing_cycle())

