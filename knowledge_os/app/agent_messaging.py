"""
Agent-to-Agent Messaging System (Singularity 31.3)

Предоставляет direct agent-to-agent communication через Redis Pub/Sub + Streams.
Агенты могут отправлять и получать сообщения напрямую, без HTTP или БД.

Каналы:
- Pub/Sub: agent:messages:{agent_name} — direct message (fire-and-forget)
- Stream:  stream:agent:messages:{agent_name} — guaranteed delivery
- Pub/Sub: agent:presence — heartbeat (online/offline/capabilities)
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://host.docker.internal:6379/0")
AGENT_HEARTBEAT_INTERVAL = int(os.getenv("AGENT_HEARTBEAT_INTERVAL", "30"))
AGENT_PRESENCE_TTL = int(os.getenv("AGENT_PRESENCE_TTL", "90"))

# Глобальный реестр обработчиков сообщений
_message_handlers: Dict[str, List[Callable]] = {}
_registered_agents: Dict[str, Dict[str, Any]] = {}
_presence_task: Optional[asyncio.Task] = None


class AgentMessage:
    """Стандартный конверт для сообщений между агентами."""

    def __init__(
        self,
        from_agent: str,
        to_agent: str = "*",
        verb: str = "TELL",
        payload: Any = None,
        correlation_id: Optional[str] = None,
        requires_response: bool = False,
    ):
        self.msg_id = str(uuid.uuid4())
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.verb = verb
        self.payload = payload
        self.correlation_id = correlation_id or self.msg_id
        self.requires_response = requires_response
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "verb": self.verb,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "requires_response": self.requires_response,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        msg = cls(
            from_agent=data.get("from_agent", ""),
            to_agent=data.get("to_agent", "*"),
            verb=data.get("verb", "TELL"),
            payload=data.get("payload"),
            correlation_id=data.get("correlation_id"),
            requires_response=data.get("requires_response", False),
        )
        msg.msg_id = data.get("msg_id", msg.msg_id)
        msg.timestamp = data.get("timestamp", msg.timestamp)
        return msg


async def _get_redis():
    try:
        import redis.asyncio as aioredis

        return aioredis.from_url(REDIS_URL, decode_responses=True)
    except ImportError:
        logger.warning("[AGENT_MSG] redis.asyncio not available")
        return None


def register_handler(agent_name: str, handler: Callable):
    """Зарегистрировать обработчик входящих сообщений для агента."""
    if agent_name not in _message_handlers:
        _message_handlers[agent_name] = []
    _message_handlers[agent_name].append(handler)
    logger.info(f"[AGENT_MSG] Handler registered for '{agent_name}'")


def unregister_handler(agent_name: str, handler: Callable):
    """Отменить регистрацию обработчика."""
    if agent_name in _message_handlers:
        _message_handlers[agent_name] = [h for h in _message_handlers[agent_name] if h != handler]


async def send_message(
    from_agent: str,
    to_agent: str,
    verb: str = "TELL",
    payload: Any = None,
    correlation_id: Optional[str] = None,
    requires_response: bool = False,
    guaranteed: bool = False,
) -> Optional[str]:
    """
    Отправить сообщение агенту.

    Args:
        from_agent: Отправитель
        to_agent: Получатель ("*" для broadcast)
        verb: PING, TELL, ASK, OBSERVE
        payload: Данные сообщения
        correlation_id: ID для трекинга
        requires_response: Ожидается ли ответ
        guaranteed: Использовать Stream (гарантированная доставка) вместо Pub/Sub

    Returns:
        msg_id если отправлено, None если ошибка
    """
    msg = AgentMessage(
        from_agent=from_agent,
        to_agent=to_agent,
        verb=verb,
        payload=payload,
        correlation_id=correlation_id,
        requires_response=requires_response,
    )
    r = await _get_redis()
    if not r:
        return None

    data = json.dumps(msg.to_dict(), ensure_ascii=False)
    try:
        if guaranteed:
            channel = f"stream:agent:messages:{to_agent}"
            await r.xadd(channel, {"msg": data}, maxlen=5000)
        else:
            channel = f"agent:messages:{to_agent}" if to_agent != "*" else "agent:messages"
            await r.publish(channel, data)

        logger.info(f"[AGENT_MSG] {from_agent} → {to_agent} ({verb}): {str(payload)[:80]}")
        return msg.msg_id
    except Exception as e:
        logger.warning(f"[AGENT_MSG] Send failed: {e}")
        return None
    finally:
        await r.aclose()


async def listen(agent_name: str, loop_forever: bool = True):
    """
    Запустить слушатель входящих сообщений для агента.

    Подписывается на agent:messages:{agent_name} (Pub/Sub) +
    stream:agent:messages:{agent_name} (Stream).
    """
    r = await _get_redis()
    if not r:
        return

    pubsub = r.pubsub()
    channel = f"agent:messages:{agent_name}"
    broadcast_channel = "agent:messages"
    await pubsub.subscribe(channel, broadcast_channel)
    logger.info(f"[AGENT_MSG] '{agent_name}' listening on {channel}")

    async def _process_message(data: Dict[str, Any]):
        raw = data.get("data")
        if not raw or isinstance(raw, int):
            return
        try:
            msg_dict = json.loads(raw)
            msg = AgentMessage.from_dict(msg_dict)

            # Call registered handlers
            handlers = _message_handlers.get(agent_name, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(msg)
                    else:
                        handler(msg)
                except Exception as e:
                    logger.warning(f"[AGENT_MSG] Handler error: {e}")
        except json.JSONDecodeError:
            pass

    try:
        while True:
            try:
                message = await pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    await _process_message(message)
            except asyncio.TimeoutError:
                pass
            if not loop_forever:
                break
            await asyncio.sleep(0.01)
    finally:
        await pubsub.unsubscribe(channel, broadcast_channel)
        await r.aclose()


async def publish_presence(agent_name: str, capabilities: Optional[List[str]] = None):
    """Публиковать heartbeat присутствия агента."""
    r = await _get_redis()
    if not r:
        return
    try:
        payload = json.dumps(
            {
                "agent": agent_name,
                "capabilities": capabilities or [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
            }
        )
        await r.publish("agent:presence", payload)
        # Also set a key with TTL for discovery
        await r.setex(f"agent:alive:{agent_name}", AGENT_PRESENCE_TTL, payload)
    except Exception as e:
        logger.debug(f"[AGENT_MSG] Presence publish failed: {e}")
    finally:
        await r.aclose()


async def discover_agents() -> List[Dict[str, Any]]:
    """Найти всех живых агентов через presence keys."""
    r = await _get_redis()
    if not r:
        return []
    try:
        keys = await r.keys("agent:alive:*")
        agents = []
        for key in keys:
            data = await r.get(key)
            if data:
                try:
                    agents.append(json.loads(data))
                except json.JSONDecodeError:
                    pass
        return agents
    except Exception as e:
        logger.warning(f"[AGENT_MSG] Discovery failed: {e}")
        return []
    finally:
        await r.aclose()


async def start_presence_broadcast(agent_name: str, capabilities: Optional[List[str]] = None):
    """Запустить фоновую публикацию presence."""
    global _presence_task

    async def _broadcast():
        while True:
            try:
                await publish_presence(agent_name, capabilities)
            except Exception:
                pass
            await asyncio.sleep(AGENT_HEARTBEAT_INTERVAL)

    if _presence_task and not _presence_task.done():
        _presence_task.cancel()
    _presence_task = asyncio.create_task(_broadcast())
    logger.info(f"[AGENT_MSG] Presence broadcast started for '{agent_name}'")
    return _presence_task


def get_agent_messaging():
    """Получить экземпляр (совместимость с существующим паттерном get_*)."""
    return {
        "send_message": send_message,
        "listen": listen,
        "register_handler": register_handler,
        "unregister_handler": unregister_handler,
        "publish_presence": publish_presence,
        "discover_agents": discover_agents,
        "start_presence_broadcast": start_presence_broadcast,
    }
