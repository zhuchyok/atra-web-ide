import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from app.event_bus import Event, EventBus, EventType
except ImportError:
    from event_bus import Event, EventBus, EventType
from consensus_agent import AgentResponse, ConsensusAgent

logger = logging.getLogger(__name__)


class DialogueController:
    """
    Dialogue Controller - Оркестратор автономных диалогов экспертов.
    Работает независимо от Cursor Agent.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.active_dialogues: Dict[str, Dict[str, Any]] = {}
        self.consensus_agent = ConsensusAgent(
            model_name=os.getenv("VICTORIA_MODEL", "victoria-wisdom-v3.5:latest")
        )

    def start(self):
        """Запуск контроллера и подписка на события"""
        # [SINGULARITY 24.3] DEBUG: Log subscriptions
        import os

        logger.info(
            f"🎭 [DIALOGUE] (PID: {os.getpid()}) Subscribing to events on EventBus ID: {id(self.event_bus)}"
        )

        self.event_bus.subscribe(EventType.DIALOGUE_REQUEST, self.handle_dialogue_request)
        self.event_bus.subscribe(EventType.EXPERT_RESPONSE, self.handle_expert_response)

        # [SINGULARITY 24.3] Victoria Agent тоже должен слушать консенсус
        self.event_bus.subscribe(EventType.DIALOGUE_CONSENSUS, self.handle_dialogue_consensus_local)

        logger.info("🎭 DialogueController started and subscribed to events")

    async def handle_dialogue_consensus_local(self, event: Event):
        """Локальный обработчик консенсуса (для логов)"""
        payload = event.payload
        dialogue_id = payload.get("dialogue_id")
        score = payload.get("consensus_score", 0)
        logger.info(
            f"🏆 [DIALOGUE] Local EventBus received consensus for {dialogue_id} (Score: {score:.2f})"
        )

    async def handle_dialogue_request(self, event: Event):
        """Обработка запроса на новый диалог"""
        data = event.payload
        query = data.get("query")
        dialogue_id = data.get("dialogue_id") or str(uuid.uuid4())

        # Если это запрос к конкретному эксперту, игнорируем (его обработает VictoriaEventHandlers)
        if data.get("is_expert_specific"):
            return

        # [SINGULARITY 24.3] Идемпотентность: не обрабатываем один и тот же диалог дважды
        if dialogue_id in self.active_dialogues:
            logger.debug(f"Dialogue {dialogue_id} already active, skipping")
            return

        if not query:
            logger.warning("Empty query in DIALOGUE_REQUEST")
            return

        logger.info(f"💬 New dialogue request [{dialogue_id}]: {query[:50]}...")

        # 1. Выбор экспертов
        experts = await self._select_experts(query)

        # 2. Инициализация состояния диалога
        self.active_dialogues[dialogue_id] = {
            "query": query,
            "experts": experts,
            "responses": {},
            "start_time": datetime.now(timezone.utc),
            "status": "collecting",
        }

        # 3. Рассылка запросов экспертам через EventBus
        for expert in experts:
            await self.event_bus.publish(
                Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.DIALOGUE_REQUEST,
                    payload={
                        "dialogue_id": dialogue_id,
                        "expert_name": expert,
                        "query": query,
                        "is_expert_specific": True,
                        "metadata": {"is_dialogue": True, "dialogue_id": dialogue_id},
                    },
                    source="DialogueController",
                    correlation_id=event.event_id,
                )
            )
            logger.debug(f"📤 Sent dialogue request to expert: {expert}")

        # [SINGULARITY 24.3] Fix 1: Таймаут сбора ответов — если эксперты не ответили за N секунд,
        # запускаем консенсус принудительно с тем, что есть (даже с 0 ответов).
        # Это гарантирует, что DIALOGUE_CONSENSUS ВСЕГДА будет опубликован.
        # Increased default timeout to reduce false fallback consensus
        # when experts have already started processing (EXPERT_THOUGHT emitted)
        # but LLM generation needs extra time under load.
        COLLECTION_TIMEOUT = int(os.getenv("DIALOGUE_COLLECTION_TIMEOUT", "300"))

        async def _collect_with_timeout():
            await asyncio.sleep(COLLECTION_TIMEOUT)
            dialogue = self.active_dialogues.get(dialogue_id)
            if dialogue and dialogue["status"] == "collecting":
                n_got = len(dialogue["responses"])
                n_exp = len(dialogue["experts"])
                logger.warning(
                    f"⏰ [DIALOGUE] Collection timeout for {dialogue_id}: got {n_got}/{n_exp} responses, starting consensus"
                )
                await self._reach_consensus(dialogue_id)

        asyncio.create_task(_collect_with_timeout())

    async def handle_expert_response(self, event: Event):
        """Обработка ответа от конкретного эксперта"""
        data = event.payload
        dialogue_id = data.get("dialogue_id")
        expert_name = data.get("expert_name")
        response_text = data.get("response")

        if not dialogue_id or dialogue_id not in self.active_dialogues:
            return

        dialogue = self.active_dialogues[dialogue_id]
        if expert_name not in dialogue["experts"]:
            return

        # [SINGULARITY 24.3] DEBUG: Log expert response receipt
        logger.info(
            f"📥 [DIALOGUE] Received response from {expert_name} for dialogue {dialogue_id} ({len(response_text) if response_text else 0} chars)"
        )

        # [SINGULARITY 24.3] Проверка на пустой ответ
        if not response_text or len(response_text.strip()) < 5:
            logger.warning(f"⚠️ [DIALOGUE] Empty or too short response from {expert_name}, ignoring")
            return

        # [SINGULARITY 24.3] Нормализация ответа (очистка от лишних Markdown-тегов, если нужно)
        normalized_response = response_text.strip()
        if normalized_response.startswith("```") and normalized_response.endswith("```"):
            # Если ответ полностью в блоке кода, извлекаем содержимое
            lines = normalized_response.split("\n")
            if len(lines) > 2:
                normalized_response = "\n".join(lines[1:-1]).strip()

        dialogue["responses"][expert_name] = normalized_response

        # 4. Проверка: собраны ли все ответы?
        if len(dialogue["responses"]) >= len(dialogue["experts"]):
            logger.info(
                f"🏁 [DIALOGUE] All {len(dialogue['experts'])} responses collected for {dialogue_id}, starting consensus"
            )
            await self._reach_consensus(dialogue_id)
        else:
            logger.info(
                f"⏳ [DIALOGUE] Collected {len(dialogue['responses'])}/{len(dialogue['experts'])} responses for {dialogue_id}"
            )

    async def _select_experts(self, query: str) -> List[str]:
        """Интеллектуальный выбор экспертов для диалога"""
        query_lower = query.lower()
        experts = set()

        # Базовая логика по ключевым словам
        if any(w in query_lower for w in ["код", "python", "api", "backend", "ошибка"]):
            experts.add("Игорь")
        if any(w in query_lower for w in ["база", "sql", "postgres", "данные"]):
            experts.add("Роман")
        if any(w in query_lower for w in ["нейросеть", "модель", "mlx", "ollama", "ai"]):
            experts.add("Дмитрий")
        if any(w in query_lower for w in ["тест", "баг", "качество", "qa"]):
            experts.add("Анна")
        if any(w in query_lower for w in ["дизайн", "интерфейс", "фронтенд", "svelte"]):
            experts.add("Елена")

        # Если ничего не подошло или для веса - добавляем Игоря и Дмитрия как универсалов
        if not experts:
            experts.update(["Игорь", "Дмитрий"])
        elif len(experts) < 2:
            if "Игорь" not in experts:
                experts.add("Игорь")
            else:
                experts.add("Дмитрий")

        # [SINGULARITY 31.2] Runtime liveness routing:
        # choose only experts that currently have active heartbeats.
        live_experts = await self._get_live_experts()
        if live_experts:
            selected = [name for name in experts if name in live_experts]
            if len(selected) < 2:
                # Prefer operationally reliable experts first, then any remaining live workers.
                fallback_priority = ["Виктория", "Анна", "Роман", "Игорь", "Дмитрий", "Максим"]
                for name in fallback_priority:
                    if name in live_experts and name not in selected:
                        selected.append(name)
                    if len(selected) >= 2:
                        break
                if len(selected) < 2:
                    for name in sorted(live_experts):
                        if name not in selected:
                            selected.append(name)
                        if len(selected) >= 2:
                            break
            if selected:
                experts = set(selected)

        return list(experts)

    async def _get_live_experts(self) -> List[str]:
        """Get experts that currently publish runtime heartbeats in Redis."""
        try:
            import redis.asyncio as redis

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            client = redis.from_url(redis_url, decode_responses=False)
            heartbeat_key = "runtime:expert_heartbeats"
            names = await client.hkeys(heartbeat_key)
            await client.aclose()
            live = []
            for name in names or []:
                if isinstance(name, bytes):
                    live.append(name.decode("utf-8", errors="ignore"))
                else:
                    live.append(str(name))
            return [n for n in live if n]
        except Exception as e:
            logger.warning(f"Failed to read live experts from Redis: {e}")
            return []

    async def _reach_consensus(self, dialogue_id: str):
        """Синтез финального ответа через ConsensusAgent"""
        dialogue = self.active_dialogues.get(dialogue_id)
        if not dialogue or dialogue["status"] != "collecting":
            return

        dialogue["status"] = "consensus"
        logger.info(f"🤝 [DIALOGUE] Starting consensus for {dialogue_id}")

        # [SINGULARITY 24.3] Fix 1b: Если ответов нет — пропускаем ConsensusAgent (он тоже требует LLM)
        if not dialogue["responses"]:
            logger.warning(
                f"⚠️ [DIALOGUE] No expert responses for {dialogue_id}, publishing empty consensus"
            )
            await self.event_bus.publish(
                Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.DIALOGUE_CONSENSUS,
                    payload={
                        "dialogue_id": dialogue_id,
                        "query": dialogue["query"],
                        "final_answer": "⚠️ Эксперты не успели ответить (LLM сервисы перегружены). Попробуйте снова.",
                        "consensus_score": 0.0,
                        "agreement_level": 0,
                        "expert_responses": {},
                    },
                    source="DialogueController",
                )
            )
            return

        # [SINGULARITY 24.3] Прямой консенсус без ConsensusAgent (Ollama для embeddings недоступна)
        # Синтезируем ответ из имеющихся expert_responses напрямую
        try:
            responses_list = dialogue["responses"]
            n_experts = len(dialogue["experts"])
            n_got = len(responses_list)

            # Собираем итоговый ответ: объединяем мнения экспертов
            if len(responses_list) == 1:
                expert_name = list(responses_list.keys())[0]
                final_answer = f"**{expert_name}**: {list(responses_list.values())[0]}"
                score = 0.5
            elif len(responses_list) >= 2:
                parts = [f"**{n}**: {r}" for n, r in responses_list.items()]
                final_answer = "\n\n".join(parts)
                # Простая оценка согласованности: если ответы похожи по длине — выше
                lengths = [len(r) for r in responses_list.values()]
                avg_len = sum(lengths) / len(lengths)
                variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
                score = max(0.3, 1.0 - min(1.0, variance / (avg_len**2 + 1)))
            else:
                final_answer = "Эксперты не предоставили ответов."
                score = 0.0

            await self.event_bus.publish(
                Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.DIALOGUE_CONSENSUS,
                    payload={
                        "dialogue_id": dialogue_id,
                        "query": dialogue["query"],
                        "final_answer": final_answer,
                        "consensus_score": round(score, 2),
                        "agreement_level": round(n_got / max(n_experts, 1), 2),
                        "expert_responses": responses_list,
                    },
                    source="DialogueController",
                )
            )
            logger.info(
                f"✅ [DIALOGUE] Direct consensus for {dialogue_id}: {n_got}/{n_experts} experts, score={score:.2f}"
            )

        except Exception as e:
            logger.error(f"❌ [DIALOGUE] Consensus failed for {dialogue_id}: {e}")
            # Fallback: просто склеить ответы
            fallback_answer = "\n\n".join(
                [f"**{n}**: {r}" for n, r in dialogue["responses"].items()]
            )
            await self.event_bus.publish(
                Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.DIALOGUE_CONSENSUS,
                    payload={
                        "dialogue_id": dialogue_id,
                        "final_answer": f"⚠️ [FALLBACK] Консенсус не достигнут ({type(e).__name__}). Ответы экспертов:\n\n{fallback_answer}",
                        "consensus_score": 0,
                        "agreement_level": 0,
                    },
                    source="DialogueController",
                )
            )
        finally:
            # [SINGULARITY 24.3] Очищаем состояние диалога после завершения (успешного или нет)
            # чтобы освободить память и позволить новые запросы с тем же ID (если нужно)
            # Но для headless теста лучше пока оставить для отладки или использовать TTL
            pass


def start_dialogue_controller(event_bus: EventBus):
    controller = DialogueController(event_bus)
    controller.start()
    return controller
