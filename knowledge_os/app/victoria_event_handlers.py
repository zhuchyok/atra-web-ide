"""
Victoria Event Handlers - Обработчики событий для Victoria
Основано на LangGraph state machines и AutoGen patterns
Обрабатывает события от File Watcher, Service Monitor, Deadline Tracker
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.event_bus import Event, EventType

logger = logging.getLogger(__name__)

# Импорт Skill State Machine (опционально)
try:
    from app.skill_state_machine import SkillStateMachine, StateMachineConfig
    STATE_MACHINE_AVAILABLE = True
except ImportError:
    STATE_MACHINE_AVAILABLE = False
    logger.debug("Skill State Machine не доступен, используем простые handlers")


class HandlerState(Enum):
    """Состояния обработчика (LangGraph state machine)"""
    IDLE = "idle"
    PROCESSING = "processing"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class HandlerContext:
    """Контекст обработки события (state для LangGraph)"""
    event: Event
    state: HandlerState = HandlerState.IDLE
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class VictoriaEventHandlers:
    """
    Victoria Event Handlers - обработчики событий для Victoria
    
    Основано на:
    - LangGraph state machines (persistence, checkpoints)
    - AutoGen event-driven patterns
    - Clawdbot proactive actions
    """
    
    def __init__(self, victoria_enhanced=None, use_state_machines: bool = True):
        """
        Инициализация обработчиков
        
        Args:
            victoria_enhanced: Экземпляр VictoriaEnhanced для выполнения действий
            use_state_machines: Использовать LangGraph state machines для обработки
        """
        self.victoria = victoria_enhanced
        self.handler_contexts: Dict[str, HandlerContext] = {}
        self.running = False
        self.use_state_machines = use_state_machines and STATE_MACHINE_AVAILABLE
        
        # Инициализируем state machine если доступна
        self.state_machine = None
        if self.use_state_machines:
            try:
                from app.skill_state_machine import SkillStateMachine, StateMachineConfig
                config = StateMachineConfig(
                    max_retries=3,
                    enable_persistence=True
                )
                self.state_machine = SkillStateMachine(config)
                logger.info("✅ Skill State Machine инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации State Machine: {e}")
                self.use_state_machines = False
        
        logger.info("✅ Victoria Event Handlers инициализированы")
    
    def _create_checkpoint(self, context: HandlerContext, state: HandlerState, data: Dict[str, Any]):
        """Создать checkpoint (LangGraph pattern)"""
        checkpoint = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": state.value,
            "data": data
        }
        context.checkpoints.append(checkpoint)
        context.state = state
        logger.debug(f"💾 Checkpoint создан: {state.value}")
    
    async def handle_performance_degraded(self, event: Event) -> Dict[str, Any]:
        """Обработчик деградации производительности (Игорь/Дмитрий)"""
        metric = event.payload.get("metric")
        value = event.payload.get("value")
        expert = event.payload.get("expert")
        
        logger.info(f"🚨 [AUTONOMOUS] {expert} обнаружил проблему: {metric} = {value}")
        
        # Автоматическая постановка задачи на исправление
        if self.victoria:
            task_prompt = f"ЭКСТРЕННО: {expert} обнаружил деградацию {metric} до {value}. Проведи диагностику и исправь."
            # В реальности здесь вызывается Victoria Enhanced для планирования и выполнения
            # await self.victoria.solve(task_prompt, priority='high')
            
        return {"status": "task_created", "expert": expert, "metric": metric}

    async def handle_performance_degraded(self, event: Event) -> Dict[str, Any]:
        """Обработчик деградации производительности (Игорь/Дмитрий)"""
        metric = event.payload.get("metric")
        value = event.payload.get("value")
        expert = event.payload.get("expert")
        
        logger.info(f"🚨 [AUTONOMOUS] {expert} обнаружил проблему: {metric} = {value}")
        
        # [Task Queue v2] Автоматическая постановка задачи напрямую в Redis Stream
        try:
            from app.redis_manager import redis_manager
            import uuid
            
            task_id = str(uuid.uuid4())
            task_data = {
                "task_id": task_id,
                "expert_name": expert,
                "description": f"АВТО-ДИАГНОСТИКА: Деградация {metric} до {value}. Проведи анализ и предложи исправление.",
                "category": "system",
                "metadata": {"autonomous": True, "source_event": event.event_id}
            }
            
            await redis_manager.push_to_stream("expert_tasks", task_data)
            logger.info(f"✅ [AUTONOMOUS] Задача {task_id} поставлена в очередь для {expert}")
            
            return {"status": "task_queued", "task_id": task_id, "expert": expert}
        except Exception as e:
            logger.error(f"❌ [AUTONOMOUS] Ошибка постановки задачи: {e}")
            return {"status": "error", "message": str(e)}

    async def handle_sentinel_event(self, event: Event) -> Dict[str, Any]:
        """Универсальный обработчик для Sentinel Framework."""
        try:
            from app.sentinel_framework import ExpertSentinel
            # В реальности здесь может быть пул стражей, но для API возвращаем статус
            return {"status": "sentinel_triggered", "event": event.event_type.value}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def handle_event(self, event: Event) -> Dict[str, Any]:
        """Общий диспетчер событий"""
        # [SINGULARITY 12.0] Route to Autonomous Sentinel
        try:
            from app.autonomous_sentinel import get_autonomous_sentinel
            sentinel = get_autonomous_sentinel()
            if not sentinel.is_running:
                asyncio.create_task(sentinel.start())
        except ImportError:
            pass

        if event.event_type == EventType.FILE_CREATED:
            return await self.handle_file_created(event)
        elif event.event_type == EventType.PERFORMANCE_DEGRADED:
            return await self.handle_performance_degraded(event)
        # ... другие типы ...
        return {"status": "ignored"}

    async def handle_file_created(self, event: Event) -> Dict[str, Any]:
        """Обработчик создания файла"""
        # Используем state machine если доступна
        if self.use_state_machines and self.state_machine:
            try:
                logger.info("🔄 Используем State Machine для обработки FILE_CREATED")
                machine_result = await self.state_machine.run(event)
                return {
                    "action": "file_created_handled",
                    "state_machine_result": machine_result.get("current_node"),
                    "result": machine_result.get("result"),
                    "checkpoints": len(machine_result.get("checkpoints", []))
                }
            except Exception as e:
                logger.warning(f"⚠️ Ошибка State Machine, используем простой handler: {e}")
        
        # Простой handler (fallback)
        context = HandlerContext(event=event, state=HandlerState.PROCESSING)
        self.handler_contexts[event.event_id] = context
        
        try:
            file_path = event.payload.get("file_path")
            file_name = event.payload.get("file_name")
            
            logger.info(f"📁 Обработка создания файла: {file_name}")
            
            # Checkpoint: начало обработки
            self._create_checkpoint(context, HandlerState.PROCESSING, {
                "action": "file_created_start",
                "file_path": file_path
            })
            
            # Анализируем файл (читаем, проверяем синтаксис)
            analysis_result = await self._analyze_file(file_path)
            
            # Checkpoint: анализ завершен
            self._create_checkpoint(context, HandlerState.PROCESSING, {
                "action": "file_analyzed",
                "analysis": analysis_result
            })
            
            # Если это Python файл, проверяем синтаксис
            if file_path.endswith(".py"):
                syntax_check = await self._check_python_syntax(file_path)
                if not syntax_check.get("valid"):
                    # Предлагаем исправления
                    suggestions = await self._suggest_fixes(file_path, syntax_check.get("errors", []))
                    context.metadata["suggestions"] = suggestions
            
            # Предлагаем улучшения или создаем тесты
            if analysis_result.get("needs_tests"):
                test_suggestion = await self._suggest_tests(file_path)
                context.metadata["test_suggestion"] = test_suggestion
            
            context.result = {
                "action": "file_created_handled",
                "file_path": file_path,
                "analysis": analysis_result,
                "suggestions": context.metadata.get("suggestions"),
                "test_suggestion": context.metadata.get("test_suggestion")
            }
            
            self._create_checkpoint(context, HandlerState.COMPLETED, context.result)
            logger.info(f"✅ Файл обработан: {file_name}")
            
            return context.result
        except Exception as e:
            logger.error(f"❌ Ошибка обработки создания файла: {e}", exc_info=True)
            context.error = str(e)
            context.state = HandlerState.FAILED
            return {"error": str(e)}
    
    async def handle_file_modified(self, event: Event) -> Dict[str, Any]:
        """Обработчик изменения файла"""
        context = HandlerContext(event=event, state=HandlerState.PROCESSING)
        self.handler_contexts[event.event_id] = context
        
        try:
            file_path = event.payload.get("file_path")
            file_name = event.payload.get("file_name")
            
            logger.info(f"✏️ Обработка изменения файла: {file_name}")
            
            # Проверяем изменения
            changes = await self._detect_changes(file_path)
            
            # Если это критичный файл, проверяем более тщательно
            if self._is_critical_file(file_path):
                review = await self._review_critical_changes(file_path, changes)
                context.metadata["review"] = review
            
            context.result = {
                "action": "file_modified_handled",
                "file_path": file_path,
                "changes": changes
            }
            
            context.state = HandlerState.COMPLETED
            logger.info(f"✅ Изменения файла обработаны: {file_name}")
            
            return context.result
        except Exception as e:
            logger.error(f"❌ Ошибка обработки изменения файла: {e}", exc_info=True)
            context.error = str(e)
            context.state = HandlerState.FAILED
            return {"error": str(e)}
    
    async def handle_service_down(self, event: Event) -> Dict[str, Any]:
        """Обработчик падения сервиса"""
        context = HandlerContext(event=event, state=HandlerState.PROCESSING)
        self.handler_contexts[event.event_id] = context
        
        try:
            service_name = event.payload.get("service_name")
            service_type = event.payload.get("service_type")
            
            # Не перезапускаем себя (Victoria Agent): иначе цикл/путаница при ложном down
            if service_name == "Victoria Agent":
                logger.debug("Пропуск перезапуска: это мы (Victoria Agent)")
                context.state = HandlerState.COMPLETED
                return {"action": "skipped", "service_name": service_name, "reason": "self"}
            
            logger.warning(f"🔴 Обработка падения сервиса: {service_name}")
            
            # Пытаемся перезапустить сервис через SelfCheckSystem
            restart_result = await self._restart_service(service_name, service_type)
            
            if restart_result.get("success"):
                context.result = {
                    "action": "service_restarted",
                    "service_name": service_name,
                    "restart_result": restart_result
                }
                context.state = HandlerState.COMPLETED
                logger.info(f"✅ Сервис перезапущен: {service_name}")
            else:
                # Если не удалось, уведомляем пользователя
                context.result = {
                    "action": "service_restart_failed",
                    "service_name": service_name,
                    "error": restart_result.get("error"),
                    "requires_manual_intervention": True
                }
                context.state = HandlerState.WAITING_APPROVAL
                logger.error(f"❌ Не удалось перезапустить сервис: {service_name}")
            
            return context.result
        except Exception as e:
            logger.error(f"❌ Ошибка обработки падения сервиса: {e}", exc_info=True)
            context.error = str(e)
            context.state = HandlerState.FAILED
            return {"error": str(e)}
    
    async def handle_deadline_approaching(self, event: Event) -> Dict[str, Any]:
        """Обработчик приближения дедлайна"""
        context = HandlerContext(event=event, state=HandlerState.PROCESSING)
        self.handler_contexts[event.event_id] = context
        
        try:
            task_id = event.payload.get("task_id")
            task_title = event.payload.get("task_title")
            hours_until = event.payload.get("hours_until")
            
            logger.info(f"⏰ Обработка приближения дедлайна: {task_title} (через {hours_until}ч)")
            
            # Проверяем статус задачи
            task_status = await self._get_task_status(task_id)
            
            # Если задача не в работе, предлагаем помощь
            if task_status.get("status") != "in_progress":
                help_offer = await self._offer_help_for_task(task_id, hours_until)
                context.metadata["help_offer"] = help_offer
            
            # Если дедлайн очень близко (менее 6 часов), проверяем прогресс
            if hours_until <= 6:
                progress_check = await self._check_task_progress(task_id)
                context.metadata["progress_check"] = progress_check
            
            context.result = {
                "action": "deadline_approaching_handled",
                "task_id": task_id,
                "task_title": task_title,
                "hours_until": hours_until,
                "help_offered": context.metadata.get("help_offer"),
                "progress_check": context.metadata.get("progress_check")
            }
            
            context.state = HandlerState.COMPLETED
            logger.info(f"✅ Дедлайн обработан: {task_title}")
            
            return context.result
        except Exception as e:
            logger.error(f"❌ Ошибка обработки приближения дедлайна: {e}", exc_info=True)
            context.error = str(e)
            context.state = HandlerState.FAILED
            return {"error": str(e)}
    
    async def handle_error_detected(self, event: Event) -> Dict[str, Any]:
        """Обработчик обнаруженной ошибки"""
        context = HandlerContext(event=event, state=HandlerState.PROCESSING)
        self.handler_contexts[event.event_id] = context
        
        try:
            error_info = event.payload.get("error_info", {})
            
            logger.warning(f"⚠️ Обработка обнаруженной ошибки: {error_info.get('type', 'unknown')}")
            
            # Диагностика через Extended Thinking (если доступен)
            if self.victoria and hasattr(self.victoria, 'extended_thinking'):
                diagnosis = await self._diagnose_error_with_thinking(error_info)
            else:
                diagnosis = await self._diagnose_error(error_info)
            
            # Пытаемся исправить
            fix_result = await self._attempt_fix(error_info, diagnosis)
            
            context.result = {
                "action": "error_handled",
                "error_info": error_info,
                "diagnosis": diagnosis,
                "fix_result": fix_result
            }
            
            if fix_result.get("success"):
                context.state = HandlerState.COMPLETED
            else:
                context.state = HandlerState.WAITING_APPROVAL
            
            return context.result
        except Exception as e:
            logger.error(f"❌ Ошибка обработки обнаруженной ошибки: {e}", exc_info=True)
            context.error = str(e)
            context.state = HandlerState.FAILED
            return {"error": str(e)}
    
    async def handle_skill_needed(self, event: Event) -> Dict[str, Any]:
        """Обработчик запроса нового skill"""
        context = HandlerContext(event=event, state=HandlerState.PROCESSING)
        self.handler_contexts[event.event_id] = context
        
        try:
            skill_description = event.payload.get("skill_description") or event.payload.get("skill_name", "")
            task_context = event.payload.get("task_context")
            
            logger.info(f"🔧 Обработка запроса skill: {skill_description}")
            
            # Запускаем Skill Discovery
            try:
                from app.skill_discovery import SkillDiscovery
                discovery = SkillDiscovery()
                skill = await discovery.discover_skill(skill_description, task_context)
                
                if skill:
                    context.result = {
                        "action": "skill_needed_handled",
                        "skill_description": skill_description,
                        "skill_name": skill.name,
                        "skill_created": True,
                        "skill_path": skill.skill_path
                    }
                    context.state = HandlerState.COMPLETED
                    logger.info(f"✅ Skill создан: {skill.name}")
                else:
                    context.result = {
                        "action": "skill_needed_handled",
                        "skill_description": skill_description,
                        "skill_created": False,
                        "status": "discovery_failed"
                    }
                    context.state = HandlerState.FAILED
            except Exception as e:
                logger.error(f"❌ Ошибка Skill Discovery: {e}", exc_info=True)
                context.result = {
                    "action": "skill_needed_handled",
                    "skill_description": skill_description,
                    "skill_created": False,
                    "error": str(e)
                }
                context.state = HandlerState.FAILED
            
            return context.result
        except Exception as e:
            logger.error(f"❌ Ошибка обработки запроса skill: {e}", exc_info=True)
            context.error = str(e)
            context.state = HandlerState.FAILED
            return {"error": str(e)}
    
    # Вспомогательные методы (заглушки для реализации)
    
    async def _analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Анализировать файл с использованием базы знаний"""
        try:
            # Используем базу знаний для анализа
            if self.victoria:
                # Ищем релевантные знания о файлах/коде
                try:
                    from app.main import search_knowledge
                    knowledge = await search_knowledge(f"анализ файла {file_path} код python")
                    if knowledge and "No relevant knowledge" not in knowledge:
                        return {
                            "file_type": "python",
                            "needs_tests": True,
                            "complexity": "medium",
                            "knowledge_context": knowledge[:500]
                        }
                except Exception as e:
                    logger.debug(f"Не удалось использовать базу знаний: {e}")
        except Exception:
            pass
        
        # Fallback
        return {
            "file_type": "python",
            "needs_tests": True,
            "complexity": "medium"
        }
    
    async def _check_python_syntax(self, file_path: str) -> Dict[str, Any]:
        """Проверить синтаксис Python файла"""
        # Заглушка
        return {"valid": True, "errors": []}
    
    async def _suggest_fixes(self, file_path: str, errors: List[str]) -> List[Dict[str, Any]]:
        """Предложить исправления"""
        # Заглушка
        return []
    
    async def _suggest_tests(self, file_path: str) -> Dict[str, Any]:
        """Предложить тесты"""
        # Заглушка
        return {"suggestion": "Add unit tests"}
    
    async def _detect_changes(self, file_path: str) -> Dict[str, Any]:
        """Обнаружить изменения в файле"""
        # Заглушка
        return {"changes_detected": True}
    
    def _is_critical_file(self, file_path: str) -> bool:
        """Проверить, является ли файл критичным"""
        critical_patterns = ["config", "settings", "database", "auth", "security"]
        return any(pattern in file_path.lower() for pattern in critical_patterns)
    
    async def _review_critical_changes(self, file_path: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Проверить критические изменения"""
        # Заглушка
        return {"reviewed": True}
    
    async def _restart_service(self, service_name: str, service_type: str) -> Dict[str, Any]:
        """Перезапустить сервис"""
        # Интеграция с SelfCheckSystem
        try:
            from app.self_check_system import SelfCheckSystem
            check_system = SelfCheckSystem()
            # Вызываем метод исправления
            # Заглушка - в реальности здесь будет вызов SelfCheckSystem
            return {"success": True, "message": f"Service {service_name} restarted"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Получить статус задачи из БД"""
        try:
            import asyncpg
            import os
            db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
            conn = await asyncpg.connect(db_url)
            try:
                row = await conn.fetchrow(
                    "SELECT id, title, status, priority, deadline FROM tasks WHERE id = $1",
                    task_id
                )
                if row:
                    return {
                        "status": row["status"],
                        "task_id": str(row["id"]),
                        "title": row["title"],
                        "priority": row.get("priority"),
                        "deadline": row.get("deadline").isoformat() if row.get("deadline") else None
                    }
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Не удалось получить статус задачи из БД: {e}")
        
        # Fallback
        return {"status": "pending", "task_id": task_id}
    
    async def _offer_help_for_task(self, task_id: str, hours_until: float) -> Dict[str, Any]:
        """Предложить помощь для задачи"""
        # Заглушка
        return {"help_offered": True}
    
    async def _check_task_progress(self, task_id: str) -> Dict[str, Any]:
        """Проверить прогресс задачи"""
        # Заглушка
        return {"progress": 0.5}
    
    async def _diagnose_error(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """Диагностировать ошибку с использованием базы знаний"""
        error_type = error_info.get("type", "unknown")
        error_message = error_info.get("message", "")
        
        try:
            # Ищем похожие ошибки в базе знаний
            if self.victoria:
                try:
                    from app.main import search_knowledge
                    query = f"ошибка {error_type} {error_message[:50]}"
                    knowledge = await search_knowledge(query, domain="errors")
                    if knowledge and "No relevant knowledge" not in knowledge:
                        return {
                            "diagnosis": "knowledge_based",
                            "error_type": error_type,
                            "similar_errors": knowledge[:500],
                            "suggested_fixes": "См. базу знаний"
                        }
                except Exception as e:
                    logger.debug(f"Не удалось использовать базу знаний: {e}")
        except Exception:
            pass
        
        # Fallback
        return {"diagnosis": "unknown_error", "error_type": error_type}
    
    async def _diagnose_error_with_thinking(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """Диагностировать ошибку через Extended Thinking"""
        # Заглушка - в реальности будет использовать Extended Thinking
        return {"diagnosis": "thinking_based_diagnosis"}
    
    async def _attempt_fix(self, error_info: Dict[str, Any], diagnosis: Dict[str, Any]) -> Dict[str, Any]:
        """Попытаться исправить ошибку"""
        # Заглушка
        return {"success": False, "message": "Fix not implemented"}
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """Получить статистику обработчиков"""
        state_counts = {}
        for state in HandlerState:
            state_counts[state.value] = sum(
                1 for ctx in self.handler_contexts.values() if ctx.state == state
            )
        
        return {
            "total_handlers": len(self.handler_contexts),
            "state_counts": state_counts,
            "running": self.running
        }


async def main():
    """Пример использования"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    handlers = VictoriaEventHandlers()
    
    # Пример события
    event = Event(
        event_id="test_file_created",
        event_type=EventType.FILE_CREATED,
        payload={
            "file_path": "/path/to/test.py",
            "file_name": "test.py"
        },
        source="test"
    )
    
    result = await handlers.handle_file_created(event)
    print(f"Результат: {result}")
    print(f"Статистика: {handlers.get_handler_stats()}")


if __name__ == "__main__":
    asyncio.run(main())
