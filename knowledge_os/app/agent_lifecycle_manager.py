#!/usr/bin/env python3
"""
Agent Lifecycle Manager - управление жизненным циклом агентов.
Регистрация, версионирование, валидация перед деплоем.

Источник: Microsoft Multi-Agent Reference Architecture (2025)
Эффект: Улучшенная управляемость и безопасность деплоя
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Статус агента"""

    DRAFT = "draft"
    REGISTERED = "registered"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    DEPRECATED = "deprecated"
    FAILED = "failed"


@dataclass
class AgentVersion:
    """Версия агента"""

    version: str  # Semantic versioning: 1.0.0
    agent_id: str
    config: Dict
    code_hash: str  # Хеш кода для проверки изменений
    created_at: str
    status: AgentStatus
    validation_results: Optional[Dict] = None
    deployed_at: Optional[str] = None


class AgentLifecycleManager:
    """
    Управление жизненным циклом агентов:
    1. Registration - регистрация агентов
    2. Versioning - версионирование
    3. Validation - валидация перед деплоем
    4. Deployment - безопасный деплой
    """

    def __init__(self):
        self.registered_agents: Dict[str, List[AgentVersion]] = {}
        self.agent_registry: Dict[str, Dict] = {}

    def register_agent(
        self, agent_id: str, agent_name: str, config: Dict, code_path: Optional[str] = None
    ) -> AgentVersion:
        """
        Регистрация нового агента

        Args:
            agent_id: Уникальный ID агента
            agent_name: Имя агента
            config: Конфигурация агента
            code_path: Путь к коду агента (для хеширования)

        Returns:
            Зарегистрированная версия
        """
        logger.info(f"📝 Регистрирую агента: {agent_name} ({agent_id})")

        # Вычисляем хеш кода если путь указан
        code_hash = ""
        if code_path:
            try:
                with open(code_path, "rb") as f:
                    code_hash = hashlib.sha256(f.read()).hexdigest()[:16]
            except Exception as e:
                logger.warning(f"Не удалось вычислить хеш кода: {e}")

        # Определяем версию
        if agent_id in self.registered_agents:
            # Инкрементируем версию
            last_version = self.registered_agents[agent_id][-1]
            version_parts = last_version.version.split(".")
            patch = int(version_parts[2]) + 1
            new_version = f"{version_parts[0]}.{version_parts[1]}.{patch}"
        else:
            new_version = "1.0.0"

        # Создаем версию
        agent_version = AgentVersion(
            version=new_version,
            agent_id=agent_id,
            config=config,
            code_hash=code_hash,
            created_at=datetime.now(timezone.utc).isoformat(),
            status=AgentStatus.REGISTERED,
        )

        # Сохраняем в реестр
        if agent_id not in self.registered_agents:
            self.registered_agents[agent_id] = []
        self.registered_agents[agent_id].append(agent_version)

        # Сохраняем метаданные
        self.agent_registry[agent_id] = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "versions": [v.version for v in self.registered_agents[agent_id]],
        }

        logger.info(f"✅ Агент зарегистрирован: {agent_name} v{new_version}")

        return agent_version

    async def validate_agent(self, agent_id: str, version: str) -> Dict[str, Any]:
        """
        Валидация агента перед деплоем

        Args:
            agent_id: ID агента
            version: Версия для валидации

        Returns:
            Результаты валидации
        """
        logger.info(f"🔍 Валидирую агента: {agent_id} v{version}")

        # Находим версию
        agent_versions = self.registered_agents.get(agent_id, [])
        agent_version = next((v for v in agent_versions if v.version == version), None)

        if not agent_version:
            return {
                "valid": False,
                "errors": [f"Версия {version} не найдена для агента {agent_id}"],
            }

        validation_results = {"valid": True, "errors": [], "warnings": [], "checks": {}}

        # Проверка 1: Конфигурация
        config = agent_version.config
        if not config.get("name"):
            validation_results["errors"].append("Отсутствует имя агента")
            validation_results["valid"] = False

        if not config.get("capabilities"):
            validation_results["warnings"].append("Не указаны capabilities")

        validation_results["checks"]["config"] = len(validation_results["errors"]) == 0

        # Проверка 2: Зависимости
        dependencies = config.get("dependencies", [])
        validation_results["checks"]["dependencies"] = len(dependencies) > 0

        # Проверка 3: Тесты (если есть)
        if config.get("test_path"):
            validation_results["checks"]["tests"] = True
        else:
            validation_results["warnings"].append("Не указан путь к тестам")

        # Проверка 4: Документация
        if config.get("documentation"):
            validation_results["checks"]["documentation"] = True
        else:
            validation_results["warnings"].append("Отсутствует документация")

        # Обновляем статус
        if validation_results["valid"]:
            agent_version.status = AgentStatus.VALIDATED
            agent_version.validation_results = validation_results
            logger.info(f"✅ Агент валидирован: {agent_id} v{version}")
        else:
            agent_version.status = AgentStatus.FAILED
            logger.warning(f"❌ Агент не прошел валидацию: {agent_id} v{version}")

        return validation_results

    async def deploy_agent(self, agent_id: str, version: str) -> bool:
        """
        Безопасный деплой агента

        Args:
            agent_id: ID агента
            version: Версия для деплоя

        Returns:
            True если деплой успешен
        """
        logger.info(f"🚀 Деплою агента: {agent_id} v{version}")

        # Проверяем валидацию
        agent_versions = self.registered_agents.get(agent_id, [])
        agent_version = next((v for v in agent_versions if v.version == version), None)

        if not agent_version:
            logger.error(f"Версия {version} не найдена для агента {agent_id}")
            return False

        if agent_version.status != AgentStatus.VALIDATED:
            logger.warning("Агент не валидирован, выполняю валидацию...")
            validation = await self.validate_agent(agent_id, version)
            if not validation["valid"]:
                logger.error("Валидация не пройдена, деплой отменен")
                return False

        # Выполняем деплой (симуляция)
        try:
            # Здесь должна быть реальная логика деплоя
            agent_version.status = AgentStatus.DEPLOYED
            agent_version.deployed_at = datetime.now(timezone.utc).isoformat()

            logger.info(f"✅ Агент успешно задеплоен: {agent_id} v{version}")
            return True
        except Exception as e:
            logger.error(f"Ошибка деплоя: {e}")
            agent_version.status = AgentStatus.FAILED
            return False

    def get_agent_versions(self, agent_id: str) -> List[AgentVersion]:
        """Получить все версии агента"""
        return self.registered_agents.get(agent_id, [])

    def get_latest_version(self, agent_id: str) -> Optional[AgentVersion]:
        """Получить последнюю версию агента"""
        versions = self.get_agent_versions(agent_id)
        return versions[-1] if versions else None

    def get_registry(self) -> Dict:
        """Получить реестр всех агентов"""
        return self.agent_registry

    def save_registry(self, filepath: str):
        """Сохранить реестр в файл"""
        registry_data = {
            "agents": self.agent_registry,
            "versions": {
                agent_id: [
                    {
                        "version": v.version,
                        "status": v.status.value,
                        "created_at": v.created_at,
                        "deployed_at": v.deployed_at,
                    }
                    for v in versions
                ]
                for agent_id, versions in self.registered_agents.items()
            },
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(registry_data, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 Реестр сохранен в {filepath}")


# Пример использования
async def main():
    manager = AgentLifecycleManager()

    # Регистрация агента
    victoria_config = {
        "name": "Виктория",
        "capabilities": ["reasoning", "planning", "coordination"],
        "dependencies": ["react_agent", "extended_thinking"],
        "documentation": "Victoria Enhanced Agent",
    }

    version = manager.register_agent(
        agent_id="victoria-001",
        agent_name="Виктория",
        config=victoria_config,
        code_path="victoria_enhanced.py",
    )

    # Валидация
    validation = await manager.validate_agent("victoria-001", version.version)
    print(f"Валидация: {validation}")

    # Деплой
    deployed = await manager.deploy_agent("victoria-001", version.version)
    print(f"Деплой: {deployed}")

    # Сохранение реестра
    manager.save_registry("agent_registry.json")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
