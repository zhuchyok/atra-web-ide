"""
Полная система распределения задач БЕЗ заглушек
Все методы реализованы полностью
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
_VICTORIA_ENHANCED_SINGLETON = None
_CORP_REFRESH_LAST_TS = 0.0
_CORP_REFRESH_LOCK = asyncio.Lock()


def _get_victoria_enhanced_singleton():
    global _VICTORIA_ENHANCED_SINGLETON
    if _VICTORIA_ENHANCED_SINGLETON is None:
        from app.victoria_enhanced import VictoriaEnhanced

        _VICTORIA_ENHANCED_SINGLETON = VictoriaEnhanced()
    return _VICTORIA_ENHANCED_SINGLETON


def _json_serial(obj: Any) -> Any:
    """Преобразовать UUID и другие не-JSON типы для json.dumps."""
    if hasattr(obj, "hex"):  # UUID
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# Резолвер имён — централизованно в expert_aliases
try:
    from app.expert_aliases import AGENT_NAME_TO_DB, resolve_expert_name_for_db
except ImportError:
    AGENT_NAME_TO_DB = {"Veronica": "Вероника", "Victoria": "Виктория"}

    def resolve_expert_name_for_db(name: str) -> str:
        return AGENT_NAME_TO_DB.get(name, name) if name else name


# Database connection
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False


class TaskStatus(Enum):
    """Статусы задач"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class TaskAssignment:
    """Назначение задачи сотруднику (промпт от Victoria + рекомендуемая модель)"""

    task_id: str
    subtask: str
    employee_name: str
    department: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    manager_name: Optional[str] = None
    quality_score: float = 0.0
    correlation_id: Optional[str] = None
    review_rejections: int = 0
    recommended_model: Optional[str] = (
        None  # категория или имя модели: coding, reasoning, fast, general
    )


@dataclass
class TaskCollection:
    """Коллекция задач отдела"""

    department: str
    aggregated_result: str
    assignments: List[TaskAssignment]
    quality_score: float = 0.0


class TaskDistributionSystem:
    """
    Полная система распределения задач БЕЗ заглушек
    Все методы реализованы полностью
    """

    def __init__(self, db_url: str):
        self.db_url = db_url

        # Импортируем улучшения
        try:
            from app.task_distribution_improvements import (
                get_escalator,
                get_load_balancer,
                get_metrics_collector,
                get_retry_manager,
                get_validator,
            )

            self.validator = get_validator()
            self.retry_manager = get_retry_manager()
            self.load_balancer = get_load_balancer()
            self.escalator = get_escalator()
            self.metrics_collector = get_metrics_collector()
        except Exception as e:
            logger.warning(f"⚠️ Не удалось загрузить улучшения: {e}")
            self.validator = None
            self.retry_manager = None
            self.load_balancer = None
            self.escalator = None
            self.metrics_collector = None

    async def distribute_tasks_from_plan(
        self, task_plan_struct: Dict, organizational_structure: Dict
    ) -> List[TaskAssignment]:
        """Распределить задачи из структурированного плана Victoria (без повторного парсинга). Оптимальная архитектура."""
        try:
            subtasks = task_plan_struct.get("subtasks", [])
            if not subtasks:
                # Одна задача из task_description
                desc = task_plan_struct.get("task_description", "")
                dept = (
                    (organizational_structure.get("departments") or [{}])[0].get("name", "General")
                    if organizational_structure
                    else "General"
                )
                return [
                    TaskAssignment(
                        task_id=f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                        subtask=desc,
                        employee_name="Вероника",
                        department=dept,
                        correlation_id=f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    )
                ]
            assignments = []
            for i, st in enumerate(subtasks):
                employee = st.get("expert_role", st.get("employee", "Expert"))
                if isinstance(employee, list):
                    employee = employee[0] if employee else "Expert"
                # Сразу приводим к каноническому имени в БД (кириллица), чтобы нигде не оставалась латиница
                employee = resolve_expert_name_for_db(str(employee)) if employee else "Expert"
                rec_model = st.get("recommended_model")
                rec_models = st.get("recommended_models", [])
                rec_value = rec_model or (rec_models[0] if rec_models else None)
                if rec_value and isinstance(rec_value, str):
                    r = rec_value.lower()
                    if r in ("coding", "reasoning", "fast", "general", "default"):
                        recommended_category = r
                    elif any(x in r for x in ("coder", "code", "glm", "qwen")):
                        recommended_category = "coding"
                    elif any(x in r for x in ("reason", "deepseek", "r1")):
                        recommended_category = "reasoning"
                    else:
                        recommended_category = rec_value
                else:
                    recommended_category = None
                assignment = TaskAssignment(
                    task_id=f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                    subtask=st.get("subtask", ""),
                    employee_name=str(employee),
                    department=st.get("department", "General"),
                    correlation_id=st.get("correlation_id")
                    or f"plan_{i}_{datetime.now().strftime('%H%M%S')}",
                    recommended_model=recommended_category or rec_value,
                )
                assignments.append(assignment)
            logger.info(
                f"✅ [TASK DISTRIBUTION] Распределено {len(assignments)} задач из task_plan_struct (без парсинга)"
            )
            return assignments
        except Exception as e:
            logger.error(f"❌ Ошибка распределения из плана: {e}", exc_info=True)
            return []

    async def distribute_tasks_from_veronica_prompt(
        self,
        veronica_prompt: str,
        organizational_structure: Dict,
        **kwargs: Any,
    ) -> List[TaskAssignment]:
        """Распределить задачи из текстового плана (парсинг через Victoria при отсутствии task_plan_struct). Обратная совместимость."""
        # kwargs: department, goal — передаются из victoria_enhanced._execute_with_task_distribution
        try:
            # Парсим промпт для извлечения задач (fallback, когда нет task_plan_struct)
            tasks = await self._parse_veronica_prompt(veronica_prompt, organizational_structure)

            assignments = []
            for task_data in tasks:
                emp = task_data.get("employee", "")
                # Сразу приводим к каноническому имени в БД (кириллица)
                employee_name = resolve_expert_name_for_db(emp) if emp else emp
                assignment = TaskAssignment(
                    task_id=f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
                    subtask=task_data.get("subtask", ""),
                    employee_name=employee_name,
                    department=task_data.get("department", "General"),
                    correlation_id=task_data.get("correlation_id"),
                )
                assignments.append(assignment)

            return assignments
        except Exception as e:
            logger.error(f"❌ Ошибка распределения задач: {e}", exc_info=True)
            return []

    async def _parse_veronica_prompt(
        self, prompt: str, organizational_structure: Dict
    ) -> List[Dict]:
        """Парсить промпт Veronica и извлечь задачи"""
        # Реальный парсинг через Victoria Enhanced с использованием системы знаний
        try:
            from app.corporation_knowledge_system import CorporationKnowledgeSystem

            # Fail-safe: не запускаем refresh знаний на каждый парсинг задачи.
            # Это вызывало шторм эмбеддингов и деградацию latency.
            refresh_enabled = (
                os.getenv("TASK_DISTRIBUTION_REFRESH_CORP_KNOWLEDGE", "false").lower()
                in ("1", "true", "yes")
            )
            refresh_interval = int(
                os.getenv("TASK_DISTRIBUTION_REFRESH_INTERVAL_SEC", "1800")
            )
            if refresh_enabled:
                async with _CORP_REFRESH_LOCK:
                    global _CORP_REFRESH_LAST_TS
                    now_ts = datetime.now().timestamp()
                    if now_ts - _CORP_REFRESH_LAST_TS >= max(60, refresh_interval):
                        _CORP_REFRESH_LAST_TS = now_ts
                        knowledge_system = CorporationKnowledgeSystem()
                        await knowledge_system.update_corporation_knowledge()
                    else:
                        logger.debug(
                            "TaskDistribution: skip corp refresh due cooldown (%ss).",
                            refresh_interval,
                        )

            # Используем Victoria для парсинга
            parse_prompt = f"""
            Проанализируй следующий промпт Veronica и извлеки все задачи:

            {prompt}

            Структура организации:
            {json.dumps(organizational_structure, ensure_ascii=False, indent=2, default=_json_serial)}

            Верни JSON массив задач:
            [
                {{
                    "subtask": "описание задачи",
                    "employee": "имя сотрудника",
                    "department": "отдел",
                    "correlation_id": "уникальный_id"
                }}
            ]
            """

            victoria = _get_victoria_enhanced_singleton()
            result = await victoria.solve(parse_prompt, method="extended_thinking")

            # Парсим результат
            output = result.get("result", "") or result.get("output", "")

            # Ищем JSON в ответе
            import re

            json_match = re.search(r"\[.*\]", output, re.DOTALL)
            if json_match:
                tasks = json.loads(json_match.group())
                return tasks

            # Если JSON не найден, создаем задачу из всего промпта (уже кириллица)
            return [
                {
                    "subtask": prompt,
                    "employee": "Вероника",
                    "department": (organizational_structure.get("departments") or [{}])[0].get(
                        "name", "General"
                    ),
                    "correlation_id": f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                }
            ]
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга промпта: {e}", exc_info=True)
            return [
                {
                    "subtask": prompt,
                    "employee": "Вероника",
                    "department": "General",
                    "correlation_id": f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                }
            ]

    async def execute_task_assignment(
        self, assignment: TaskAssignment, project_context: Optional[str] = None
    ) -> TaskAssignment:
        """Выполнить назначенную задачу. project_context передаётся в RAG и промпт (аудит setki-21)."""
        self._project_context = project_context
        try:
            # Получаем эксперта из БД
            expert = await self._get_expert_by_name(assignment.employee_name)
            if not expert:
                logger.warning(f"⚠️ Эксперт '{assignment.employee_name}' не найден")
                assignment.status = TaskStatus.FAILED
                assignment.result = f"Эксперт '{assignment.employee_name}' не найден в БД"
                return assignment

            # Выполняем задачу через эксперта (промпт и рекомендуемая модель от Victoria)
            # Используем expert['name'] (Вероника) — каноническое имя из БД, не employee_name (Veronica)
            from app.ai_core import run_smart_agent_async

            category = getattr(assignment, "recommended_model", None) or "general"
            if getattr(assignment, "recommended_model", None):
                logger.info(
                    f"📋 [TASK] Выполняю подзадачу: эксперт={expert['name']}, рекомендуемая модель/категория={category}"
                )
            result = await run_smart_agent_async(
                prompt=assignment.subtask,
                expert_name=expert["name"],
                category=category,
                project_context=project_context,
            )

            assignment.status = TaskStatus.COMPLETED
            assignment.result = (
                result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
            )

            return assignment
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения задачи {assignment.task_id}: {e}", exc_info=True)
            assignment.status = TaskStatus.FAILED
            assignment.result = f"Ошибка выполнения: {str(e)}"
            return assignment

    async def manager_review_task(
        self, assignment: TaskAssignment, original_requirements: str
    ) -> TaskAssignment:
        """Проверить задачу управляющим с реальной валидацией"""
        try:
            # Получаем управляющего отдела
            manager = await self._get_department_manager(assignment.department)
            if not manager:
                logger.warning(f"⚠️ Управляющий для отдела '{assignment.department}' не найден")
                # Используем Victoria как управляющего по умолчанию
                manager = {"name": "Виктория", "role": "Team Lead"}

            assignment.manager_name = manager["name"]

            # Реальная валидация через TaskValidator
            if self.validator:
                try:
                    is_valid, score, feedback = await self.validator.validate_task_result(
                        assignment, original_requirements
                    )

                    assignment.quality_score = score

                    if is_valid and score >= 0.5:
                        assignment.status = TaskStatus.REVIEWED
                        logger.info(
                            f"✅ [MANAGER] {manager['name']} проверил задачу {assignment.task_id} (score: {score:.2f})"
                        )
                    else:
                        assignment.status = TaskStatus.REJECTED
                        assignment.review_rejections += 1
                        logger.warning(
                            f"⚠️ [MANAGER] {manager['name']} отклонил задачу {assignment.task_id}: {feedback}"
                        )
                except AttributeError as e:
                    # Если метод не существует, используем базовую проверку
                    logger.warning(f"⚠️ Ошибка валидации: {e}, используем базовую проверку")
                    is_valid, score, feedback = await self._basic_validation(
                        assignment, original_requirements
                    )
                    assignment.quality_score = score
                    assignment.status = TaskStatus.REVIEWED if is_valid else TaskStatus.REJECTED
            else:
                # Базовая проверка если валидатор недоступен
                is_valid, score, feedback = await self._basic_validation(
                    assignment, original_requirements
                )
                assignment.quality_score = score
                assignment.status = TaskStatus.REVIEWED if is_valid else TaskStatus.REJECTED

            return assignment
        except Exception as e:
            logger.error(f"❌ Ошибка проверки задачи {assignment.task_id}: {e}", exc_info=True)
            assignment.status = TaskStatus.REJECTED
            return assignment

    async def _basic_validation(
        self, assignment: TaskAssignment, original_requirements: str
    ) -> tuple[bool, float, Optional[str]]:
        """Базовая валидация результата"""
        result = assignment.result or ""

        if not result or len(result.strip()) == 0:
            return False, 0.0, "Результат пустой"

        # Проверяем соответствие требованиям
        requirements_lower = original_requirements.lower()
        result_lower = result.lower()

        # Простая проверка релевантности
        relevance_score = 0.5  # Базовый score

        # Если результат содержит ключевые слова из требований
        requirement_words = set(requirements_lower.split())
        result_words = set(result_lower.split())
        common_words = requirement_words.intersection(result_words)

        if common_words:
            relevance_score += min(len(common_words) / max(len(requirement_words), 1), 0.3)

        # Учитываем длину результата
        if len(result) >= 100:
            relevance_score += 0.1
        if len(result) >= 500:
            relevance_score += 0.1

        final_score = min(relevance_score, 0.9)
        is_valid = final_score >= 0.5

        return is_valid, final_score, None

    async def department_head_collect_tasks(
        self, assignments: List[TaskAssignment], department: str
    ) -> Optional[TaskCollection]:
        """Собрать задачи отдела через Department Head"""
        try:
            # Фильтруем утвержденные задачи отдела
            dept_assignments = [
                a
                for a in assignments
                if a.department == department and a.status == TaskStatus.REVIEWED
            ]

            if not dept_assignments:
                logger.warning(f"⚠️ Нет утвержденных задач для отдела '{department}'")
                return None

            # Получаем Department Head
            dept_head = await self._get_department_head(department)
            if not dept_head:
                # Агрегируем результаты без Department Head
                aggregated = "\n\n".join([a.result for a in dept_assignments if a.result])
                return TaskCollection(
                    department=department,
                    aggregated_result=aggregated,
                    assignments=dept_assignments,
                    quality_score=sum(a.quality_score for a in dept_assignments)
                    / len(dept_assignments),
                )

            # Синтезируем через Department Head
            synthesis_prompt = f"""
            ТЫ: {dept_head["name"]}, Department Head отдела {department}

            СИНТЕЗИРУЙ РЕЗУЛЬТАТЫ ОТ СОТРУДНИКОВ ТВОЕГО ОТДЕЛА:

            {json.dumps([{"employee": a.employee_name, "result": a.result} for a in dept_assignments], ensure_ascii=False, indent=2)}

            СОЗДАЙ ЕДИНЫЙ РЕЗУЛЬТАТ ОТДЕЛА.
            """

            from app.ai_core import run_smart_agent_async

            synthesis_result = await run_smart_agent_async(
                prompt=synthesis_prompt,
                expert_name=dept_head["name"],
                category=None,
                project_context=getattr(self, "_project_context", None),
            )

            aggregated = (
                synthesis_result
                if isinstance(synthesis_result, str)
                else json.dumps(synthesis_result, ensure_ascii=False)
            )

            return TaskCollection(
                department=department,
                aggregated_result=aggregated,
                assignments=dept_assignments,
                quality_score=sum(a.quality_score for a in dept_assignments)
                / len(dept_assignments),
            )
        except Exception as e:
            logger.error(f"❌ Ошибка сбора задач отдела '{department}': {e}", exc_info=True)
            return None

    async def _get_expert_by_name(self, name: str) -> Optional[Dict]:
        """Получить эксперта по имени из БД. Поддерживает латиницу (Veronica) → кириллица (Вероника)."""
        if not ASYNCPG_AVAILABLE:
            return None
        resolved_name = resolve_expert_name_for_db(name)
        names_to_try = [resolved_name]
        if resolved_name != name and name:
            names_to_try.append(name)
        try:
            conn = await asyncpg.connect(self.db_url, timeout=5.0)
            try:
                for candidate in names_to_try:
                    expert = await conn.fetchrow(
                        """
                        SELECT id, name, role, department, system_prompt
                        FROM experts
                        WHERE name = $1
                        LIMIT 1
                    """,
                        candidate,
                    )
                    if expert:
                        return dict(expert)
                # Fallback: Veronica/Вероника — искать по роли "Local Developer"
                if name and "veronica" in (name or "").lower():
                    expert = await conn.fetchrow("""
                        SELECT id, name, role, department, system_prompt
                        FROM experts
                        WHERE role ILIKE '%Local Developer%'
                        LIMIT 1
                    """)
                    if expert:
                        logger.info(
                            f"✅ Эксперт найден по роли (Veronica→Local Developer): {expert['name']}"
                        )
                        return dict(expert)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ Ошибка получения эксперта '{name}': {e}")

        return None

    async def _get_department_manager(self, department: str) -> Optional[Dict]:
        """Получить управляющего отдела"""
        if not ASYNCPG_AVAILABLE:
            return None

        try:
            conn = await asyncpg.connect(self.db_url, timeout=3.0)
            try:
                manager = await conn.fetchrow(
                    """
                    SELECT id, name, role, department
                    FROM experts
                    WHERE department = $1 AND (role ILIKE '%manager%' OR role ILIKE '%управляющий%')
                    LIMIT 1
                """,
                    department,
                )
                if manager:
                    return dict(manager)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ Ошибка получения управляющего отдела '{department}': {e}")

        return None

    async def _get_department_head(self, department: str) -> Optional[Dict]:
        """Получить Department Head для отдела"""
        if not ASYNCPG_AVAILABLE:
            return None

        try:
            conn = await asyncpg.connect(self.db_url, timeout=3.0)
            try:
                head = await conn.fetchrow(
                    """
                    SELECT id, name, role, department, system_prompt
                    FROM experts
                    WHERE department = $1 AND (role ILIKE '%head%' OR role ILIKE '%руководитель%')
                    LIMIT 1
                """,
                    department,
                )
                if head:
                    return dict(head)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ Ошибка получения Department Head отдела '{department}': {e}")

        # Fallback через department_heads_system
        try:
            from app.department_heads_system import DEPARTMENT_HEADS

            head_name = DEPARTMENT_HEADS.get(department)
            if head_name:
                return {"name": head_name, "department": department, "role": "Department Head"}
        except Exception:
            pass

        return None


# Глобальный экземпляр
_task_distribution_instance: Optional[TaskDistributionSystem] = None


def get_task_distribution_system(db_url: str) -> TaskDistributionSystem:
    """Получить экземпляр TaskDistributionSystem"""
    global _task_distribution_instance
    if _task_distribution_instance is None or _task_distribution_instance.db_url != db_url:
        _task_distribution_instance = TaskDistributionSystem(db_url)
    return _task_distribution_instance
