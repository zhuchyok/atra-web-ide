import asyncio
import json
import logging
import os
import signal
import uuid
from datetime import datetime, timezone

import asyncpg

# Сингулярность 10.0: Импорты с поддержкой разных путей (Docker/Local)
try:
    from ai_core import run_smart_agent_async
    from redis_manager import redis_manager
    from services.knowledge_service import knowledge_service
except ImportError:
    try:
        from app.ai_core import run_smart_agent_async
        from app.redis_manager import redis_manager
        from app.services.knowledge_service import knowledge_service
    except ImportError:
        # Fallback для тестов или специфических окружений
        import sys

        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from ai_core import run_smart_agent_async
        from redis_manager import redis_manager
        from services.knowledge_service import knowledge_service

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ExpertWorker")

DB_URL = os.getenv("DATABASE_URL")
STREAM_NAME = "expert_tasks"
GROUP_NAME = "expert_workers"
CONSUMER_NAME = f"worker_{os.uname()[1]}"

# Глобальный пул соединений (Singularity 21.9: Один пул — один процесс)
_db_pool = None


async def get_db_pool():
    """Возвращает глобальный пул соединений с БД"""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            DB_URL,
            min_size=1,
            max_size=5,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )
    return _db_pool


# [SINGULARITY 26.1] AgentScope Actor Model Integration
# Try real agentscope first, fall back to lightweight shim (same interface)
try:
    from agentscope.agents import AgentBase
    from agentscope.message import Msg
    _AGENTSCOPE_REAL = True
    logger.info("✅ [ACTOR] Using real AgentScope library")
except ImportError:
    try:
        from agentscope_shim import AgentBase, Msg
        _AGENTSCOPE_REAL = False
        logger.info("⚡ [ACTOR] Using AgentScope shim (minimal fallback)")
    except ImportError:
        AgentBase = object
        Msg = dict
        _AGENTSCOPE_REAL = False
        logger.warning("⚠️ [ACTOR] No AgentScope or shim available")


class VictoriaExpertActor(AgentBase):
    """
    [AGENT SCOPE] Expert as a Distributed Actor.
    Implements 'Let it crash' philosophy and isolated state.
    [SINGULARITY 26.2] Swarm & Handoff Support.
    [SINGULARITY 26.3] Event Sourcing & State Recovery.
    Works with real agentscope OR with the lightweight agentscope_shim.
    """
    def __init__(self, name: str, role: str, persona: str, task_id: str = None):
        super().__init__(name=name, sys_prompt=persona)
        self.role = role
        self.task_id = task_id
        self._db_pool = None

    async def _get_conn(self):
        if not self._db_pool:
            self._db_pool = await get_db_pool()
        return self._db_pool

    async def record_event(self, event_type: str, payload: dict):
        """Записать событие в лог (Event Sourcing)"""
        pool = await self._get_conn()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO actor_events (actor_name, task_id, event_type, payload) VALUES ($1, $2, $3, $4)",
                self.name, uuid.UUID(self.task_id) if self.task_id else None, event_type, json.dumps(payload)
            )

    async def save_snapshot(self):
        """Сохранить полный снимок состояния"""
        state = self.state_dict()
        pool = await self._get_conn()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO actor_states (actor_name, task_id, state_data) VALUES ($1, $2, $3)",
                self.name, uuid.UUID(self.task_id) if self.task_id else None, json.dumps(state)
            )

    async def recover_state(self):
        """Восстановить состояние из последнего снимка и лога событий"""
        if not self.task_id: return
        pool = await self._get_conn()
        async with pool.acquire() as conn:
            snapshot = await conn.fetchrow(
                "SELECT state_data FROM actor_states WHERE actor_name = $1 AND task_id = $2 ORDER BY created_at DESC LIMIT 1",
                self.name, uuid.UUID(self.task_id)
            )
            if snapshot:
                self.load_state_dict(json.loads(snapshot["state_data"]))
                logger.info(f"🔄 [RECOVERY] {self.name} restored from snapshot.")

    def reply(self, x: dict = None) -> dict:
        # Sync stub for AgentScope pipeline compatibility.
        # Real async processing goes through process_async() called from process_task().
        logger.info(f"🎭 [ACTOR:{self.name}] Processing message (sync stub)...")
        if x and 'content' in x:
            asyncio.create_task(self.record_event("receive_message", {"content": x['content']}))
        res = {"role": "assistant", "content": f"[Actor {self.name}: use process_async() for real work]", "name": self.name}
        asyncio.create_task(self.record_event("reply_generated", res))
        return res

    async def process_async(self, task_description: str, category: str = "general") -> str:
        """Real async task processing via ai_core (the live replacement for stub reply())."""
        await self.record_event("task_started", {"description": task_description[:200]})
        result = await run_smart_agent_async(
            task_description,
            expert_name=self.name,
            category=category,
        )
        text = str(result.get("result") if isinstance(result, dict) else result)
        await self.record_event("task_finished", {"result_len": len(text)})
        return text

    async def initiate_handoff(self, to_expert: str, task: str, context: dict, contract: dict = None):
        """Инициализировать передачу задачи другому эксперту (Singularity 26.2)"""
        try:
            await self.record_event("handoff_initiated", {"to": to_expert, "task": task})
            from explicit_handoffs import get_handoff_manager
            manager = get_handoff_manager()
            if manager:
                handoff = manager.create_handoff(
                    from_agent=self.name,
                    to_agent=to_expert,
                    task=task,
                    context=context,
                    expected_output=f"Result matching contract: {contract}"
                )
                if contract:
                    handoff.validation_schema = contract
                logger.info(f"🚀 [SWARM] {self.name} initiated handoff to {to_expert}")
                return handoff
        except Exception as e:
            logger.error(f"❌ [SWARM] Handoff initiation failed: {e}")
        return None

async def process_task(task_data: dict):
    """Выполняет задачу и сохраняет результат."""
    task_id = task_data["task_id"]
    expert_name = task_data["expert_name"]
    description = task_data["description"]

    logger.info(f"🛠️ [WORKER] Начало выполнения задачи {task_id} для {expert_name}")
    print(f"DEBUG_PRINT: task_data metadata: {task_data.get('metadata')}")

    # actor объявлен на уровне функции, чтобы блок except мог записать task_failed event
    actor = None

    # [SINGULARITY 24.3] Fix 3: TTL для диалоговых задач — пропускаем устаревшие
    if task_data.get("metadata", {}).get("is_dialogue"):
        created_at_str = task_data.get("created_at")
        if created_at_str:
            try:
                task_created_at = datetime.fromisoformat(created_at_str)
                age_seconds = (datetime.now(timezone.utc) - task_created_at).total_seconds()
                if age_seconds > 300:  # 5 минут
                    logger.warning(f"⏭️ [STALE] Пропускаем диалоговую задачу {task_id} для {expert_name} (возраст: {age_seconds:.0f}s > 300s)")
                    return
            except Exception as age_err:
                logger.debug(f"⚠️ [TTL] Не удалось проверить возраст задачи: {age_err}")

    try:
        # 1. Обновляем статус в БД и Redis
        # Сингулярность 10.0: Проверяем, является ли task_id валидным UUID перед запросом к БД
        is_valid_uuid = False
        try:
            import uuid

            uuid.UUID(str(task_id))
            is_valid_uuid = True
        except ValueError:
            logger.warning(f"⚠️ Task ID {task_id} is not a valid UUID, skipping DB update")

        # [SINGULARITY 21.9] Circuit Breaker: Таймаут задачи
        # Для диалоговых задач — 300s, иначе WORKER_TASK_TOTAL_TIMEOUT (по умолчанию 3600s)
        is_dialogue_task = bool(task_data.get("metadata", {}).get("is_dialogue"))
        
        # [SINGULARITY 24.7] Adaptive Timeout: Reduce timeout for autonomous audit tasks
        is_monster_audit = task_data.get("metadata", {}).get("source") == "victoria_monster_delegation"
        if is_monster_audit:
            TASK_TOTAL_TIMEOUT = 300.0  # 5 минут для аудита (вместо полного лимита)
        else:
            TASK_TOTAL_TIMEOUT = 300.0 if is_dialogue_task else float(os.getenv("WORKER_TASK_TOTAL_TIMEOUT", "3600"))

        # [SINGULARITY 24.3] Если активен флаг dialogue_active — не-диалоговые задачи пропускаем
        # Это гарантирует что воркеры не заблокированы тяжёлыми задачами во время Живого Чата
        if not is_dialogue_task:
            try:
                _flag_client = await redis_manager.get_client()
                _dialogue_active = await _flag_client.get("dialogue_active")
                if _dialogue_active:
                    logger.info(f"⏭️ [PRIORITY] Пропускаем не-диалоговую задачу {task_id} — активен dialogue_active флаг")
                    return
            except Exception:
                pass  # Если Redis недоступен — продолжаем обычно

        # [SINGULARITY 26.2] Swarm MsgHub Context
        is_swarm = bool(task_data.get("metadata", {}).get("is_swarm", False))
        if is_swarm:
            try:
                from agentscope.msghub import msghub
                # Воркер подключается к MsgHub задачи
                logger.info(f"🐝 [SWARM] Expert {expert_name} joining MsgHub for task {task_id}")
            except ImportError:
                pass

        async with asyncio.timeout(TASK_TOTAL_TIMEOUT):
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                if is_valid_uuid:
                    await conn.execute(
                        "UPDATE tasks SET status = 'in_progress', updated_at = NOW() WHERE id = $1",
                        task_id,
                    )

                await redis_manager.update_task_status(
                    task_id, "in_progress", metadata={"expert": expert_name}
                )

                # [SINGULARITY 26.3] Actor Recovery & State Management
                try:
                    actor = VictoriaExpertActor(name=expert_name, role="Expert", persona="", task_id=str(task_id))
                    await actor.recover_state()
                    # Записываем старт НЕМЕДЛЕННО — до LLM-вызова, чтобы событие было даже при падении
                    await actor.record_event("task_started", {
                        "description": description[:200],
                        "category": task_data.get("category", "general"),
                    })
                except Exception as actor_err:
                    logger.warning(f"⚠️ [ACTOR] Recovery failed: {actor_err}")

                # 2. Выполняем через AI Core или ReAct Agent (Singularity 14.0)
                # ... (логика выбора агента) ...
                
                # [SINGULARITY 24.3] Живой Чат: Публикация мысли эксперта
                if task_data.get("metadata", {}).get("is_dialogue"):
                    try:
                        # [SINGULARITY 24.3] Fix: Universal import for EventBus
                        try:
                            from app.event_bus import get_event_bus, Event, EventType
                        except ImportError:
                            from event_bus import get_event_bus, Event, EventType
                            
                        bus = get_event_bus()
                        import uuid
                        await bus.publish(Event(
                            event_id=str(uuid.uuid4()),
                            event_type=EventType.EXPERT_THOUGHT,
                            payload={
                                "dialogue_id": task_data.get("metadata", {}).get("dialogue_id"),
                                "expert_name": expert_name,
                                "thought": f"Приступаю к анализу вопроса: {description[:100]}..."
                            },
                            source=expert_name
                        ))
                    except Exception as e:
                        logger.debug(f"⚠️ [DIALOGUE] Failed to publish thought: {e}")

                # [SINGULARITY 24.3] Fast Path для диалоговых задач — MLX (victoria-wisdom) или Ollama (phi3.5)
                if is_dialogue_task:
                    logger.info(f"🎯 [DIALOGUE FAST PATH] Запуск для {expert_name} (task {task_id})")
                    try:
                        import httpx
                        
                        # [SINGULARITY 25.0] Expert Priority Detection for Dialogue
                        is_vip_expert = False
                        try:
                            async with pool.acquire() as conn:
                                expert_priority = await conn.fetchval(
                                    "SELECT priority FROM experts WHERE name = $1", expert_name
                                )
                                if expert_priority == 'VIP':
                                    is_vip_expert = True
                                    logger.info(f"🌟 [VIP DIALOGUE] Expert {expert_name} has VIP priority")
                        except Exception as e:
                            logger.debug(f"Failed to fetch expert priority for dialogue: {e}")

                        _ollama_base = (
                            os.getenv("OLLAMA_BASE_URL")
                            or os.getenv("OLLAMA_API_URL")
                            or "http://host.docker.internal:11434"
                        )
                        _mlx_base = "http://host.docker.internal:11435"
                        _dialogue_model = os.getenv("DIALOGUE_MODEL", "victoria-wisdom-v3.5")

                        # ... (personas) ...
                        _persona = _expert_personas.get(expert_name, f"Ты — {expert_name}, эксперт корпорации Singularity 21.5.")
                        _system = f"{_persona} Отвечай от первого лица кратко (2-3 предложения), в своём стиле."

                        # Очищаем description от служебного префикса "УЧАСТИЕ В ДИАЛОГЕ [id]: ..."
                        import re as _re
                        _clean_desc = _re.sub(r'^УЧАСТИЕ В ДИАЛОГЕ \[[\w\-]+\]:\s*', '', description).strip()

                        _messages = [
                            {"role": "system", "content": _system},
                            {"role": "user", "content": _clean_desc},
                        ]
                        report_text = None

                        # victoria-wisdom → MLX (в Ollama не работает для чата)
                        # phi3.5/другие → Ollama (MLX накапливает stuck requests для малых моделей)
                        _use_mlx = "victoria-wisdom" in _dialogue_model or "wisdom" in _dialogue_model

                        _headers = {}
                        if is_vip_expert:
                            _headers["X-Request-Priority"] = "high"

                        if _use_mlx:
                            logger.info(f"🎯 [FAST PATH] MLX victoria-wisdom для {expert_name}")
                            try:
                                async with httpx.AsyncClient(timeout=300.0) as _hc:
                                    _resp = await _hc.post(
                                        f"{_mlx_base}/api/chat",
                                        json={"model": _dialogue_model, "messages": _messages, "stream": False, "options": {"num_predict": 100}},
                                        headers=_headers,
                                    )
                                    logger.info(f"🔍 [FAST PATH] MLX status={_resp.status_code} for {expert_name}")
                                    if _resp.status_code == 200:
                                        report_text = _resp.json().get("message", {}).get("content", "")
                                        # Убираем артефакты модели: ведущие точки/пробелы и эхо вопроса
                                        if report_text:
                                            report_text = report_text.strip().lstrip(".\n").strip()
                                            # Regex: удаляем эхо вопроса в начале (с любыми обёртками)
                                            _echo = _re.escape(_clean_desc)
                                            report_text = _re.sub(rf'^[\s\.]*{_echo}[\s\.]*', '', report_text).strip()
                                        logger.info(f"✅ [FAST PATH] MLX ответил для {expert_name} ({len(report_text or '')} chars)")
                                    else:
                                        logger.warning(f"⚠️ [FAST PATH] MLX вернул {_resp.status_code}")
                            except asyncio.CancelledError:
                                raise
                            except Exception as _mlx_err:
                                logger.warning(f"⚠️ [FAST PATH] MLX ошибка: {_mlx_err}")
                        else:
                            # Ollama с retry для небольших моделей (phi3.5 и др.)
                            for _attempt in range(3):
                                try:
                                    async with httpx.AsyncClient(timeout=180.0) as _hc:
                                        _resp = await _hc.post(
                                            f"{_ollama_base}/api/chat",
                                            json={"model": _dialogue_model, "messages": _messages, "stream": False},
                                            headers=_headers,
                                        )
                                        logger.info(f"🔍 [FAST PATH] Ollama status={_resp.status_code} for {expert_name} (attempt {_attempt+1})")
                                        if _resp.status_code == 200:
                                            report_text = _resp.json().get("message", {}).get("content", "")
                                            logger.info(f"✅ [FAST PATH] Ollama ответил для {expert_name} ({len(report_text or '')} chars)")
                                            break
                                        elif _resp.status_code == 503 and _attempt < 2:
                                            logger.info(f"⏳ [FAST PATH] Ollama 503, retry {_attempt+1}/3 через 5s...")
                                            await asyncio.sleep(5)
                                        else:
                                            logger.warning(f"⚠️ [FAST PATH] Ollama вернул {_resp.status_code}: {_resp.text[:100]}")
                                            break
                                except asyncio.CancelledError:
                                    raise
                                except Exception as _oe:
                                    logger.warning(f"⚠️ [FAST PATH] Ollama exception (attempt {_attempt+1}): {_oe}")
                                    if _attempt < 2:
                                        await asyncio.sleep(5)
                        # ... (rest of the code) ...

                        if not report_text:
                            raise ValueError(f"LLM не ответил ({'MLX' if _use_mlx else 'Ollama'})")
                        logger.info(f"✅ [DIALOGUE FAST PATH] {expert_name} ответил ({len(report_text)} chars)")
                    except Exception as fast_err:
                        logger.warning(f"⚠️ [DIALOGUE FAST PATH] Fallback на ai_core: {fast_err}")
                        
                        # [SINGULARITY 24.7] Retry Intelligence: Downgrade model on failure
                        _retry_category = "fast" if "wisdom" in _dialogue_model else "general"
                        report = await run_smart_agent_async(
                            description,
                            expert_name=expert_name,
                            category=_retry_category,
                            is_vip=True,
                        )
                        report_text = str(report.get("result") if isinstance(report, dict) else report)

                elif task_data.get("metadata", {}).get("complex") or expert_name == "Виктория":
                    logger.info(f"🧠 [WORKER] Используем ReAct Agent для сложной задачи {task_id}")
                    try:

                        model_hint = task_data.get("metadata", {}).get("model_hint")
                        print(f"DEBUG_PRINT: Initializing ReActAgent with model: {model_hint or 'victoria-wisdom-v3.5:latest'}")
                        agent = ReActAgent(agent_name=expert_name, model_name=model_hint or "victoria-wisdom-v3.5:latest")
                        print(f"DEBUG_PRINT: Calling agent.run() for task {task_id}")
                        report = await agent.run(goal=description)
                        print(f"DEBUG_PRINT: agent.run() finished for task {task_id}")
                        # [SINGULARITY 21.26] Fix: ReActAgent returns 'response', not 'result'
                        if isinstance(report, dict) and "response" in report:
                            report_text = report["response"]
                        else:
                            report_text = str(report.get("result") if isinstance(report, dict) else report)
                    except Exception as e:
                        logger.error(f"⚠️ Ошибка ReAct Agent, fallback на AI Core: {e}")
                        report = await run_smart_agent_async(
                            description,
                            expert_name=expert_name,
                            category=task_data.get("category", "general"),
                            is_vip=is_dialogue_task,
                        )
                        report_text = str(report.get("result") if isinstance(report, dict) else report)
                else:
                    report = await run_smart_agent_async(
                        description,
                        expert_name=expert_name,
                        category=task_data.get("category", "general"),
                        is_vip=is_dialogue_task,
                    )
                    report_text = str(report.get("result") if isinstance(report, dict) else report)

                # 3. Сохраняем результат
                if isinstance(report_text, dict):
                    report_text = json.dumps(report_text, ensure_ascii=False, indent=2)
                else:
                    report_text = str(report_text)

                # [SINGULARITY 26.2] Swarm Handoff Detection
                if "HANDOFF:" in report_text and "TASK:" in report_text:
                    try:
                        import re as _re
                        _to_expert = _re.search(r'HANDOFF:\s*@?(\w+)', report_text)
                        _task_desc = _re.search(r'TASK:\s*(.+)', report_text, _re.DOTALL)
                        _contract = _re.search(r'CONTRACT:\s*(\{.*\})', report_text, _re.DOTALL)
                        
                        if _to_expert and _task_desc:
                            to_name = _to_expert.group(1)
                            task_msg = _task_desc.group(1).strip()
                            contract_json = None
                            if _contract:
                                try:
                                    contract_json = json.loads(_contract.group(1))
                                except: pass
                            
                            from explicit_handoffs import get_handoff_manager
                            manager = get_handoff_manager()
                            if manager:
                                manager.create_handoff(
                                    from_agent=expert_name,
                                    to_agent=to_name,
                                    task=task_msg,
                                    context={"parent_result": report_text, "parent_task_id": task_id},
                                    expected_output=f"Swarm handoff result for {to_name}"
                                )
                                if contract_json:
                                    # Находим созданный handoff и ставим схему
                                    h_list = manager.get_pending_handoffs(to_name)
                                    if h_list:
                                        h_list[0].validation_schema = contract_json
                                
                                logger.info(f"🐝 [SWARM] {expert_name} successfully initiated handoff to {to_name}")
                    except Exception as he:
                        logger.error(f"❌ [SWARM] Handoff detection failed: {he}")

                if is_valid_uuid:
                    print(f"DEBUG_PRINT: Updating task {task_id} to completed in DB")
                    await conn.execute(
                        """
                        UPDATE tasks SET status = 'completed', result = $2, completed_at = NOW()
                        WHERE id = $1
                    """,
                        task_id,
                        report_text,
                    )

                await redis_manager.update_task_status(task_id, "completed", result=report_text)

                # [SINGULARITY 26.3] Extract reasoning_trace and store in task metadata
                if "<reasoning_trace>" in report_text and is_valid_uuid:
                    try:
                        import re as _re
                        _trace_match = _re.search(r'<reasoning_trace>(.*?)</reasoning_trace>', report_text, _re.DOTALL)
                        if _trace_match:
                            _trace = _trace_match.group(1).strip()
                            await conn.execute(
                                "UPDATE tasks SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb WHERE id = $1",
                                task_id,
                                json.dumps({"reasoning_trace": _trace[:2000]}),
                            )
                            logger.info(f"🧠 [REFLECTION] reasoning_trace saved for task {task_id}")
                    except Exception as _te:
                        logger.debug(f"reasoning_trace extraction failed: {_te}")

                # [SINGULARITY 26.3] Final State Snapshot
                if actor:
                    try:
                        await actor.save_snapshot()
                        await actor.record_event("task_completed", {"result_len": len(report_text)})
                    except Exception:
                        pass

                # Сингулярность 10.0: Снимаем блокировку идемпотентности
                await redis_manager.release_task_lock(task_id)

                # 4. Сохраняем инсайт в базу знаний
                await knowledge_service.save_insight(
                    report_text,
                    expert_name,
                    metadata={"task_id": task_id, "source": "worker_service"},
                )

                # [SINGULARITY 24.3] Живой Чат: Публикация ответа эксперта в EventBus
                if task_data.get("metadata", {}).get("is_dialogue"):
                    try:
                        # [SINGULARITY 24.3] Fix: Universal import for EventBus
                        try:
                            from app.event_bus import get_event_bus, Event, EventType
                        except ImportError:
                            from event_bus import get_event_bus, Event, EventType
                            
                        import uuid
                        
                        bus = get_event_bus()
                        dialogue_id = task_data.get("metadata", {}).get("dialogue_id")
                        
                        await bus.publish(Event(
                            event_id=str(uuid.uuid4()),
                            event_type=EventType.EXPERT_RESPONSE,
                            payload={
                                "dialogue_id": dialogue_id,
                                "expert_name": expert_name,
                                "response": report_text
                            },
                            source=expert_name
                        ))
                        logger.info(f"🎭 [DIALOGUE] Expert {expert_name} published response for {dialogue_id}")
                    except Exception as e:
                        logger.error(f"⚠️ [DIALOGUE] Failed to publish response: {e}")

                logger.info(f"✅ [WORKER] Задача {task_id} успешно завершена")

                # [SINGULARITY 26.4] Детерминированный handoff — без LLM-тегов
                try:
                    from explicit_handoffs import detect_deterministic_handoff
                    auto_handoff = detect_deterministic_handoff(
                        from_agent=expert_name,
                        task_description=description,
                        task_result=report_text[:300],
                        category=task_data.get("category", "general"),
                    )
                    if auto_handoff:
                        logger.info(
                            f"🔀 [AUTO-HANDOFF] {expert_name} → {auto_handoff.to_agent} "
                            f"| ID: {auto_handoff.handoff_id}"
                        )
                        if actor:
                            await actor.record_event("handoff_created", {
                                "to_agent": auto_handoff.to_agent,
                                "handoff_id": auto_handoff.handoff_id,
                            })
                except Exception as _hf_err:
                    logger.debug(f"[HANDOFF] Deterministic check failed (non-critical): {_hf_err}")

    except asyncio.TimeoutError:
        logger.error(
            f"⌛ [CIRCUIT BREAKER] Задача {task_id} прервана по таймауту ({TASK_TOTAL_TIMEOUT}с)"
        )
        error_msg = f"Task timed out after {TASK_TOTAL_TIMEOUT}s (Circuit Breaker)"
        if actor:
            try:
                await actor.record_event("task_failed", {"reason": "timeout", "timeout_sec": TASK_TOTAL_TIMEOUT})
            except Exception:
                pass
        await _handle_task_error(task_id, error_msg, is_valid_uuid)

    except Exception as e:
        logger.error(f"❌ [WORKER] Ошибка задачи {task_id}: {e}", exc_info=True)
        error_msg = str(e)
        if actor:
            try:
                await actor.record_event("task_failed", {"reason": error_msg[:300]})
            except Exception:
                pass
        await _handle_task_error(task_id, error_msg, is_valid_uuid)


async def _handle_task_error(task_id, error_msg, is_valid_uuid):
    """Вспомогательная функция для обработки ошибок задачи"""
    try:
        await redis_manager.update_task_status(task_id, "failed", result=error_msg)
        if is_valid_uuid:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'failed',
                        result = $2,
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('last_error', $3::text)
                    WHERE id = $1
                """,
                    task_id,
                    error_msg,
                    error_msg[:200],
                )
        await redis_manager.release_task_lock(task_id)
    except Exception as e:
        logger.error(f"⚠️ Не удалось сохранить ошибку в БД/Redis: {e}")


async def worker_loop():
    """Основной цикл воркера: слушает Redis Stream."""
    client = await redis_manager.get_client()

    # Создаем группу потребителей, если её нет
    try:
        await client.xgroup_create(f"stream:{STREAM_NAME}", GROUP_NAME, mkstream=True)
    except Exception:
        pass  # Группа уже существует

    # Запускаем систему самообучения корпорации (Singularity 14.0)
    try:
        from corporation_self_learning import get_corporation_learner

        learner = get_corporation_learner()
        # Запускаем в фоне (интервал 6 часов)
        asyncio.create_task(learner.start_continuous_learning(interval_hours=6))
        logger.info("🧠 [SINGULARITY 10.0] Collective Learning system started")
    except Exception as e:
        logger.warning(f"⚠️ [SINGULARITY 10.0] Could not start collective learning: {e}")

    logger.info(f"🚀 [WORKER] Воркер запущен. Слушаю поток {STREAM_NAME}...")

    # [SINGULARITY 24.3] Живой Чат: Инициализация EventBus и Redis Bridge
    try:
        # [SINGULARITY 24.3] Fix: Universal import for EventBus
        try:
            from app.event_bus import get_event_bus
        except ImportError:
            from event_bus import get_event_bus
            
        from event_bus_redis_bridge import start_redis_bridge
        bus = get_event_bus()
        await bus.start()
        await start_redis_bridge(bus)
        logger.info("🌉 [WORKER] EventBus Redis Bridge запущен для Живого Чата")
    except Exception as e:
        logger.warning(f"⚠️ [WORKER] Не удалось запустить EventBus Bridge: {e}")

    # [FULL FIX 2026-04-08] Get DB pool once for the worker lifetime
    db_pool = await get_db_pool()

    # [FULL FIX 2026-04-08 / Sergey] Cleanup stale event_bus_stream consumer groups on startup.
    # Each restart/reconnect creates a new group. After months they accumulate (248+).
    # Safe cleanup: groups with 0 pending and 0 consumers are orphaned.
    try:
        eb_groups = await client.xinfo_groups("event_bus_stream")
        stale_eb_groups = [
            g["name"] for g in eb_groups
            if g.get("pending", 0) == 0 and g.get("consumers", 0) == 0
        ]
        if stale_eb_groups:
            for gname in stale_eb_groups:
                try:
                    await client.xgroup_destroy("event_bus_stream", gname)
                except Exception:
                    pass
            logger.info(f"🧹 [WORKER] Cleaned up {len(stale_eb_groups)} stale event_bus_stream groups")
    except Exception as e:
        logger.warning(f"⚠️ [WORKER] event_bus_stream cleanup skipped: {e}")

    while True:
        try:
            # [FULL FIX 2026-04-08] Three-phase pending management:
            # Phase 1: Kill zombie messages (>10 deliveries) → ACK Redis + mark PostgreSQL failed
            # Phase 2: Xclaim legitimately stale messages (idle >5min, deliveries ≤10)
            # Phase 3: xreadgroup("0") reads OUR pending (including just-xclaimed) + new + autoclaim

            pending_info = await client.xpending(f"stream:{STREAM_NAME}", GROUP_NAME)
            if pending_info["pending"] > 0:
                p_range = await client.xpending_range(f"stream:{STREAM_NAME}", GROUP_NAME, "-", "+", 10)
                if p_range:
                    # Phase 1: Zombies → DLQ + PostgreSQL sync
                    zombie_msg_ids = [p["message_id"] for p in p_range if p["times_delivered"] > 10]
                    if zombie_msg_ids:
                        zombie_task_ids = []
                        for zmid in zombie_msg_ids:
                            try:
                                raw = await client.xrange(f"stream:{STREAM_NAME}", zmid, zmid)
                                if raw:
                                    _, zdata = raw[0]
                                    raw_payload = zdata.get("payload") or zdata.get(b"payload")
                                    if raw_payload:
                                        zpayload = json.loads(raw_payload) if isinstance(raw_payload, (str, bytes)) else raw_payload
                                        task_id = zpayload.get("task_id")
                                        if task_id:
                                            zombie_task_ids.append(task_id)
                            except Exception as ze:
                                logger.warning(f"⚠️ [DLQ] Could not read zombie payload {zmid}: {ze}")
                        logger.warning(f"💀 [DLQ] Killing {len(zombie_msg_ids)} zombie messages, task_ids={zombie_task_ids}")
                        await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, *zombie_msg_ids)
                        if zombie_task_ids:
                            async with db_pool.acquire() as conn:
                                updated = await conn.execute(
                                    """UPDATE tasks
                                       SET status = 'failed', updated_at = NOW(),
                                           metadata = jsonb_set(
                                               COALESCE(metadata::jsonb, '{}'::jsonb),
                                               '{dlq_reason}',
                                               '"zombie_redis_exceeded_delivery_limit"'
                                           )
                                       WHERE id = ANY($1::uuid[])
                                         AND status IN ('pending', 'in_progress')""",
                                    zombie_task_ids,
                                )
                            logger.warning(f"💀 [DLQ] PostgreSQL updated: {updated} zombie tasks → failed")

                    # Phase 2: Xclaim legitimately stale (idle >5min, not zombies)
                    claimable = [
                        p["message_id"] for p in p_range
                        if p["times_delivered"] <= 10 and p["time_since_delivered"] > 300000
                    ]
                    if claimable:
                        logger.info(f"🛠️ [WORKER] Claiming {len(claimable)} stale tasks for {CONSUMER_NAME}")
                        await client.xclaim(f"stream:{STREAM_NAME}", GROUP_NAME, CONSUMER_NAME, 300000, claimable)

            # Phase 3a: Read OUR pending messages (id="0" — includes just-xclaimed ones)
            pending_mine = await client.xreadgroup(
                GROUP_NAME, CONSUMER_NAME, {f"stream:{STREAM_NAME}": "0"}, count=5
            )

            # Phase 3b: Autoclaim stale messages from OTHER consumers (idle >5min)
            stale_messages = await redis_manager.autoclaim_tasks(
                STREAM_NAME, GROUP_NAME, CONSUMER_NAME, min_idle_time_ms=300000
            )

            # Phase 3c: New messages (blocking 5s)
            messages = await client.xreadgroup(
                GROUP_NAME, CONSUMER_NAME, {f"stream:{STREAM_NAME}": ">"}, count=1, block=5000
            )

            all_messages = []
            if pending_mine:
                all_messages.extend(pending_mine)
            if stale_messages:
                all_messages.append((f"stream:{STREAM_NAME}", stale_messages))
            if messages:
                all_messages.extend(messages)

            if not all_messages:
                continue

            for stream, msgs in all_messages:
                for msg_id, data in msgs:
                    try:
                        # Belt-and-suspenders: drop any zombie that slipped through Phase 1
                        info = await client.xpending_range(
                            f"stream:{STREAM_NAME}", GROUP_NAME, msg_id, msg_id, 1
                        )
                        if info and info[0]["times_delivered"] > 10:
                            logger.error(f"💀 [DLQ] Message {msg_id} slipped through Phase 1. Dropping.")
                            await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, msg_id)
                            continue

                        raw_payload = data.get(b"payload") or data.get("payload")
                        if isinstance(raw_payload, (str, bytes)):
                            payload = json.loads(raw_payload)
                        else:
                            payload = {
                                k.decode() if isinstance(k, bytes) else k: v.decode()
                                if isinstance(v, bytes)
                                else v
                                for k, v in data.items()
                            }

                        await process_task(payload)
                        await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, msg_id)
                    except Exception as e:
                        logger.error(f"❌ [WORKER] Ошибка обработки сообщения {msg_id}: {e}")

        except Exception as e:
            logger.error(f"⚠️ [WORKER] Ошибка в цикле: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("🛑 [WORKER] Остановка по сигналу пользователя")
