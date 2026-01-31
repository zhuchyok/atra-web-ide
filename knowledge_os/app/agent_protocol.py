"""
Agent Communication Protocol - A2A/ACP-style протокол для коммуникации агентов
Основано на Google A2A, IBM ACP, µACP (2026)
"""

import asyncio
import logging
import json
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class ProtocolVerb(Enum):
    """Глаголы протокола (µACP: 4 глагола достаточно)"""
    PING = "ping"      # Проверка доступности
    TELL = "tell"      # Передача информации
    ASK = "ask"        # Запрос информации
    OBSERVE = "observe"  # Наблюдение за состоянием


@dataclass
class AgentMessage:
    """Сообщение между агентами"""
    message_id: str
    from_agent: str
    to_agent: str
    verb: ProtocolVerb
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    requires_response: bool = False


@dataclass
class AgentCapabilities:
    """Возможности агента"""
    agent_name: str
    capabilities: List[str]
    status: str = "available"  # available, busy, offline
    metadata: Dict = field(default_factory=dict)


class AgentProtocol:
    """
    Agent Communication Protocol
    
    Реализует 4 глагола µACP:
    - PING: проверка доступности
    - TELL: передача информации
    - ASK: запрос информации
    - OBSERVE: наблюдение за состоянием
    """
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.capabilities = AgentCapabilities(agent_name=agent_name, capabilities=[])
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.message_handlers: Dict[ProtocolVerb, callable] = {}
        self.registered_agents: Dict[str, AgentCapabilities] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
    
    async def ping(self, target_agent: str, timeout: float = 5.0) -> bool:
        """
        PING - проверить доступность агента
        
        Args:
            target_agent: Имя целевого агента
            timeout: Таймаут ожидания ответа
        
        Returns:
            True если агент доступен
        """
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=self.agent_name,
            to_agent=target_agent,
            verb=ProtocolVerb.PING,
            payload={},
            requires_response=True
        )
        
        # Отправляем PING
        await self._send_message(message)
        
        # Ждем ответ
        try:
            response = await asyncio.wait_for(
                self._wait_for_response(message.message_id),
                timeout=timeout
            )
            return response is not None
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ PING timeout для {target_agent}")
            return False
    
    async def tell(self, target_agent: str, information: Dict[str, Any], require_ack: bool = False) -> bool:
        """
        TELL - передать информацию агенту
        
        Args:
            target_agent: Имя целевого агента
            information: Информация для передачи
            require_ack: Требовать ли подтверждение
        
        Returns:
            True если отправлено успешно
        """
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=self.agent_name,
            to_agent=target_agent,
            verb=ProtocolVerb.TELL,
            payload=information,
            requires_response=require_ack
        )
        
        await self._send_message(message)
        
        if require_ack:
            try:
                response = await asyncio.wait_for(
                    self._wait_for_response(message.message_id),
                    timeout=10.0
                )
                return response is not None
            except asyncio.TimeoutError:
                return False
        
        return True
    
    async def ask(self, target_agent: str, question: str, timeout: float = 30.0) -> Optional[Dict]:
        """
        ASK - запросить информацию у агента
        
        Args:
            target_agent: Имя целевого агента
            question: Вопрос или запрос
            timeout: Таймаут ожидания ответа
        
        Returns:
            Ответ агента или None
        """
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=self.agent_name,
            to_agent=target_agent,
            verb=ProtocolVerb.ASK,
            payload={"question": question},
            requires_response=True
        )
        
        await self._send_message(message)
        
        try:
            response = await asyncio.wait_for(
                self._wait_for_response(message.message_id),
                timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ ASK timeout для {target_agent}")
            return None
    
    async def observe(self, target_agent: str) -> Optional[Dict]:
        """
        OBSERVE - наблюдать за состоянием агента
        
        Args:
            target_agent: Имя целевого агента
        
        Returns:
            Состояние агента или None
        """
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            from_agent=self.agent_name,
            to_agent=target_agent,
            verb=ProtocolVerb.OBSERVE,
            payload={},
            requires_response=True
        )
        
        await self._send_message(message)
        
        try:
            response = await asyncio.wait_for(
                self._wait_for_response(message.message_id),
                timeout=10.0
            )
            return response
        except asyncio.TimeoutError:
            return None
    
    async def register_capabilities(self, capabilities: List[str], metadata: Dict = None):
        """Зарегистрировать возможности агента"""
        self.capabilities.capabilities = capabilities
        if metadata:
            self.capabilities.metadata = metadata
        
        # Уведомляем других агентов (через discovery mechanism)
        logger.info(f"✅ [{self.agent_name}] Зарегистрированы возможности: {capabilities}")
    
    async def handle_message(self, message: AgentMessage) -> Optional[Dict]:
        """Обработать входящее сообщение"""
        logger.debug(f"📥 [{self.agent_name}] Получено сообщение: {message.verb.value} от {message.from_agent}")
        
        # Находим обработчик
        handler = self.message_handlers.get(message.verb)
        
        if handler:
            try:
                response = await handler(message)
                return response
            except Exception as e:
                logger.error(f"❌ Ошибка обработки сообщения: {e}")
                return {"error": str(e)}
        else:
            # Дефолтная обработка
            return await self._default_handler(message)
    
    async def _default_handler(self, message: AgentMessage) -> Dict:
        """Дефолтный обработчик сообщений"""
        if message.verb == ProtocolVerb.PING:
            return {"status": "pong", "agent": self.agent_name}
        
        elif message.verb == ProtocolVerb.TELL:
            return {"status": "acknowledged"}
        
        elif message.verb == ProtocolVerb.ASK:
            # Дефолтный ответ на вопрос
            return {"answer": "I received your question but don't have a specific handler"}
        
        elif message.verb == ProtocolVerb.OBSERVE:
            return {
                "status": self.capabilities.status,
                "capabilities": self.capabilities.capabilities,
                "metadata": self.capabilities.metadata
            }
        
        return {"status": "unknown_verb"}
    
    def register_handler(self, verb: ProtocolVerb, handler: callable):
        """Зарегистрировать обработчик для глагола"""
        self.message_handlers[verb] = handler
        logger.debug(f"✅ Зарегистрирован обработчик для {verb.value}")
    
    async def _send_message(self, message: AgentMessage):
        """Отправить сообщение (заглушка - нужно интегрировать с реальной системой)"""
        # В реальной системе здесь была бы отправка через Event Bus или прямой канал
        logger.debug(f"📤 [{self.agent_name}] Отправка сообщения {message.verb.value} → {message.to_agent}")
        
        # TODO: Интеграция с Event Bus или direct communication
    
    async def _wait_for_response(self, message_id: str) -> Optional[Dict]:
        """Ждать ответа на сообщение"""
        future = asyncio.Future()
        self.pending_requests[message_id] = future
        
        try:
            response = await future
            return response
        finally:
            self.pending_requests.pop(message_id, None)
    
    def _complete_request(self, message_id: str, response: Dict):
        """Завершить ожидающий запрос"""
        if message_id in self.pending_requests:
            self.pending_requests[message_id].set_result(response)


# Глобальный реестр агентов (для discovery)
_agent_registry: Dict[str, AgentProtocol] = {}


def register_agent(agent_name: str, protocol: AgentProtocol):
    """Зарегистрировать агента в глобальном реестре"""
    _agent_registry[agent_name] = protocol
    logger.info(f"✅ Агент {agent_name} зарегистрирован в реестре")


def get_agent(agent_name: str) -> Optional[AgentProtocol]:
    """Получить агента из реестра"""
    return _agent_registry.get(agent_name)


async def main():
    """Пример использования"""
    # Создаем протоколы для агентов
    victoria_protocol = AgentProtocol("Victoria")
    veronica_protocol = AgentProtocol("Veronica")
    
    # Регистрируем
    register_agent("Victoria", victoria_protocol)
    register_agent("Veronica", veronica_protocol)
    
    # Регистрируем возможности
    await victoria_protocol.register_capabilities(
        ["planning", "coordination", "analysis"],
        {"role": "team_lead"}
    )
    
    await veronica_protocol.register_capabilities(
        ["execution", "file_operations", "code_generation"],
        {"role": "developer"}
    )
    
    # Примеры использования
    # PING
    is_available = await victoria_protocol.ping("Veronica")
    print(f"Veronica доступна: {is_available}")
    
    # TELL
    await victoria_protocol.tell("Veronica", {"task": "Выполни задачу X"})
    
    # ASK
    answer = await victoria_protocol.ask("Veronica", "Какой статус задачи?")
    print(f"Ответ: {answer}")
    
    # OBSERVE
    status = await victoria_protocol.observe("Veronica")
    print(f"Статус Veronica: {status}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
