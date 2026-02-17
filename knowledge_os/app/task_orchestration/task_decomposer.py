"""
Task Decomposer - decompose complex tasks into subtasks with dependency graph.

Uses TaskComplexityAnalyzer for complexity; if below threshold returns single-node graph.
Otherwise tries LLM (simplified prompt) for plan; on failure uses heuristic fallback.
Optional Tree of Thoughts import; on ImportError uses fallback only.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from .task_complexity_analyzer import TaskComplexityAnalyzer
except ImportError:
    try:
        from task_orchestration.task_complexity_analyzer import TaskComplexityAnalyzer
    except ImportError:
        TaskComplexityAnalyzer = None

try:
    from ai_core import run_smart_agent_async
except ImportError:
    try:
        from app.ai_core import run_smart_agent_async
    except ImportError:
        run_smart_agent_async = None

try:
    from app.tree_of_thoughts import TreeOfThoughts
except ImportError:
    try:
        from tree_of_thoughts import TreeOfThoughts
    except ImportError:
        TreeOfThoughts = None


COMPLEXITY_THRESHOLD = 0.6  # Below this: single subtask


@dataclass
class SubTask:
    """Single subtask in the dependency graph."""
    id: str
    parent_task_id: str
    title: str
    description: str
    category: str = "general"
    estimated_duration_min: int = 30
    dependencies: List[str] = field(default_factory=list)  # task_ids this depends on
    required_models: Optional[List[str]] = None
    priority: str = "medium"


@dataclass
class TaskDependencyGraph:
    """
    Graph of subtasks: subtasks dict and dependencies (task_id -> list of prerequisite ids).
    Semantics: task_id depends on prerequisite ids (prerequisites must complete first).
    """
    subtasks: Dict[str, SubTask] = field(default_factory=dict)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)  # task_id -> [prereq_id, ...]

    def get_execution_order(self) -> List[List[str]]:
        """
        Topological sort. Returns list of levels; each level is list of task_ids that can run in parallel.
        On cycle or invalid refs, returns single level with all ids.
        """
        if not self.subtasks:
            return []
        order: List[List[str]] = []
        in_degree: Dict[str, int] = {tid: 0 for tid in self.subtasks}
        # Count incoming edges: B depends on A => A -> B, so we need reverse graph for "who depends on me"
        rev_edges: Dict[str, List[str]] = {tid: [] for tid in self.subtasks}
        for tid, prereqs in self.dependencies.items():
            if tid not in self.subtasks:
                continue
            for p in prereqs:
                if p in self.subtasks and p != tid:
                    rev_edges[p].append(tid)
                    in_degree[tid] += 1
        # Validate: any dependency not in subtasks? Reset to single level to be safe
        for tid, prereqs in self.dependencies.items():
            if tid not in self.subtasks:
                return [list(self.subtasks.keys())]
            for p in prereqs:
                if p not in self.subtasks and p in self.subtasks.get(tid, SubTask("", "", "", "", dependencies=[])).dependencies:
                    pass
        # Kahn's algorithm
        current = [tid for tid, d in in_degree.items() if d == 0]
        seen = set(current)
        while current:
            order.append(current[:])
            next_level = []
            for tid in current:
                for n in rev_edges[tid]:
                    in_degree[n] -= 1
                    if in_degree[n] == 0 and n not in seen:
                        seen.add(n)
                        next_level.append(n)
            current = next_level
        # If we didn't process all (cycle), return single level
        if len(seen) != len(self.subtasks):
            return [list(self.subtasks.keys())]
        return order

    def estimate_parallel_duration(self) -> Dict[str, Any]:
        """
        Оценка общего времени выполнения с учётом параллелизма.
        Returns: parallel_duration_min, sequential_duration_min, speedup_factor, execution_levels, tasks_per_level.
        """
        order = self.get_execution_order()
        if not order:
            return {
                "parallel_duration_min": 0,
                "sequential_duration_min": 0,
                "speedup_factor": 1.0,
                "execution_levels": 0,
                "tasks_per_level": [],
            }
        level_durations = []
        for level in order:
            level_time = max(
                (self.subtasks[tid].estimated_duration_min for tid in level if tid in self.subtasks),
                default=0,
            )
            level_durations.append(level_time)
        total_parallel = sum(level_durations)
        total_sequential = sum(st.estimated_duration_min for st in self.subtasks.values())
        return {
            "parallel_duration_min": total_parallel,
            "sequential_duration_min": total_sequential,
            "speedup_factor": total_sequential / max(total_parallel, 1),
            "execution_levels": len(order),
            "tasks_per_level": [len(level) for level in order],
        }


class TaskDecomposer:
    """
    Decomposes a task into subtasks with dependency graph.
    Uses TaskComplexityAnalyzer; below threshold returns one subtask; else LLM or heuristic.
    """

    def __init__(self, db_url: Optional[str] = None, complexity_threshold: float = COMPLEXITY_THRESHOLD):
        self._analyzer = TaskComplexityAnalyzer(db_url) if TaskComplexityAnalyzer else None
        self._threshold = complexity_threshold

    def estimate_subtask_duration(self, subtask: SubTask) -> int:
        """
        Оценка времени выполнения подзадачи (в минутах).
        Эвристика: по длине описания и категории; если у subtask уже задан estimated_duration_min — используем его.
        """
        if subtask.estimated_duration_min and subtask.estimated_duration_min > 0:
            return subtask.estimated_duration_min
        desc_len = len((subtask.description or "").strip())
        base = 15
        if desc_len > 500:
            base = 45
        elif desc_len > 200:
            base = 30
        category_mult = {"reasoning": 1.5, "coding": 1.3, "complex": 1.4}.get(subtask.category, 1.0)
        return max(5, min(120, int(base * category_mult)))

    def create_dependency_graph(self, parent_task_id: str, task_description: str) -> "TaskDependencyGraph":
        """
        Returns TaskDependencyGraph. If complexity below threshold, single subtask.
        Else tries LLM plan (JSON); on failure heuristic (1–2 subtasks by length/keywords).
        """
        complexity = 0.5
        if self._analyzer:
            try:
                tc = self._analyzer.estimate_complexity(task_description, category=None)
                complexity = getattr(tc, "complexity_score", 0.5)
            except Exception as e:
                logger.debug("estimate_complexity failed: %s", e)

        if complexity < self._threshold:
            st = SubTask(
                id=f"{parent_task_id}_sub_0",
                parent_task_id=parent_task_id,
                title=task_description[:200].strip() or "Task",
                description=task_description,
                category="general",
                estimated_duration_min=30,
                dependencies=[],
                priority="medium",
            )
            return TaskDependencyGraph(subtasks={st.id: st}, dependencies={st.id: []})

        # Try LLM (async) from sync context: we run in sync API, so use heuristic if no async
        graph = self._decompose_heuristic(parent_task_id, task_description)
        return graph

    async def create_dependency_graph_async(self, parent_task_id: str, task_description: str) -> "TaskDependencyGraph":
        """Async version: tries LLM then heuristic."""
        complexity = 0.5
        if self._analyzer:
            try:
                tc = self._analyzer.estimate_complexity(task_description, category=None)
                complexity = getattr(tc, "complexity_score", 0.5)
            except Exception as e:
                logger.debug("estimate_complexity failed: %s", e)

        if complexity < self._threshold:
            st = SubTask(
                id=f"{parent_task_id}_sub_0",
                parent_task_id=parent_task_id,
                title=task_description[:200].strip() or "Task",
                description=task_description,
                category="general",
                estimated_duration_min=30,
                dependencies=[],
                priority="medium",
            )
            return TaskDependencyGraph(subtasks={st.id: st}, dependencies={st.id: []})

        # Try LLM
        graph = await self._decompose_llm(parent_task_id, task_description)
        if graph is not None:
            return graph
        return self._decompose_heuristic(parent_task_id, task_description)

    async def _decompose_llm(self, parent_task_id: str, task_description: str) -> Optional[TaskDependencyGraph]:
        """Ask LLM for JSON plan; parse and build graph. Returns None on failure."""
        if not run_smart_agent_async:
            return None
        
        # МОНСТР-ЛОГИКА: Детекция огромных файлов или глубокого анализа для рекурсивной декомпозиции
        is_monster_refactor = any(w in task_description.lower() for w in ["отрефактори", "раздели на модули", "рефакторинг"]) and \
                             any(w in task_description.lower() for w in ["app.py", "dashboard", "3000 строк"])
        
        is_deep_analysis = any(w in task_description.lower() for w in ["проанализируй", "аудит", "почему", "выясни причину"]) and \
                          len(task_description) > 500

        if is_monster_refactor:
            logger.info("🐉 [MONSTER DECOMPOSE] Обнаружен запрос на рефакторинг гигантского файла. Применяем рекурсивную стратегию.")
            prompt = f"""
            Вы - Архитектор ИИ. Задача: Отрефакторить гигантский файл (3000+ строк).
            Вместо того чтобы делать всё сразу, разбей задачу на 3 этапа:
            1. СТРУКТУРНЫЙ АНАЛИЗ: Получить карту функций и классов файла.
            2. МОДУЛЬНОЕ РАЗДЕЛЕНИЕ: Создать отдельные задачи для каждой логической части (вкладки, БД-слой и т.д.).
            3. ИНТЕГРАЦИЯ: Обновить основной файл для использования новых модулей.

            Ответь ТОЛЬКО валидным JSON.
            Формат: {{ "subtasks": [ 
                {{ "title": "Анализ структуры app.py", "description": "Проанализируй файл и выдай список всех функций и классов с номерами строк.", "category": "coding", "dependencies": [] }},
                {{ "title": "Выделение модуля БД", "description": "Перенеси всю логику работы с базой данных в tabs/database.py", "category": "coding", "dependencies": [0] }},
                {{ "title": "Выделение модуля Чат", "description": "Перенеси логику чата в tabs/chat.py", "category": "coding", "dependencies": [0] }},
                {{ "title": "Финальная сборка", "description": "Обнови app.py, импортировав созданные модули.", "category": "coding", "dependencies": [1, 2] }}
            ] }}
            
            Задача: {task_description[:1000]}
            JSON:"""
        elif is_deep_analysis:
            logger.info("🧠 [DEEP ANALYSIS DECOMPOSE] Обнаружен запрос на глубокий анализ. Разбиваем на фазы исследования.")
            prompt = f"""
            Вы - Главный Аналитик Singularity. Задача требует глубокого исследования.
            Разбей задачу на 3 фазы:
            1. СБОР ДАННЫХ: Проверка логов, конфигов и эндпоинтов.
            2. АНАЛИЗ ПРИЧИН: Сопоставление данных и поиск корня проблемы.
            3. ОТЧЕТ И РЕШЕНИЕ: Формирование итогового отчета и плана исправлений.

            Ответь ТОЛЬКО валидным JSON.
            Формат: {{ "subtasks": [ 
                {{ "title": "Сбор диагностических данных", "description": "Проверь логи контейнеров и текущие конфиги.", "category": "investigate", "dependencies": [] }},
                {{ "title": "Анализ причин сбоя", "description": "На основе собранных данных определи корень проблемы.", "category": "reasoning", "dependencies": [0] }},
                {{ "title": "Формирование отчета и рекомендаций", "description": "Подготовь финальный отчет с конкретными шагами по исправлению.", "category": "general", "dependencies": [1] }}
            ] }}
            
            Задача: {task_description[:1000]}
            JSON:"""
        else:
            prompt = f"""Разбей задачу на подзадачи. Ответь только валидным JSON без markdown.
Формат: {{ "subtasks": [ {{ "title": "...", "description": "...", "dependencies": [] }} ] }}
dependencies — массив индексов подзадач (0-based), от которых зависит эта подзадача.
Задача: {task_description[:2000]}
JSON:"""
        try:
            out = await run_smart_agent_async(prompt, max_tokens=1500)
            if not out or not isinstance(out, str):
                return None
            text = out.strip()
            # Strip markdown code block if present
            if "```" in text:
                m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
                if m:
                    text = m.group(1).strip()
            data = json.loads(text)
            subtasks_data = data.get("subtasks") or data.get("tasks") or []
            if not subtasks_data:
                return None
            subtasks: Dict[str, SubTask] = {}
            dependencies: Dict[str, List[str]] = {}
            for i, item in enumerate(subtasks_data):
                tid = f"{parent_task_id}_sub_{i}"
                dep_indices = item.get("dependencies") or []
                prereqs = []
                for j in dep_indices:
                    if isinstance(j, int) and 0 <= j < len(subtasks_data) and j != i:
                        prereqs.append(f"{parent_task_id}_sub_{j}")
                st = SubTask(
                    id=tid,
                    parent_task_id=parent_task_id,
                    title=(item.get("title") or item.get("name") or "")[:500] or f"Subtask {i}",
                    description=(item.get("description") or item.get("desc") or "")[:5000] or "",
                    category=item.get("category", "general"),
                    estimated_duration_min=int(item.get("estimated_duration_min", item.get("duration", 30))),
                    dependencies=prereqs,
                    required_models=item.get("required_models"),
                    priority=item.get("priority", "medium"),
                )
                subtasks[tid] = st
                dependencies[tid] = prereqs
            return TaskDependencyGraph(subtasks=subtasks, dependencies=dependencies)
        except Exception as e:
            logger.debug("LLM decompose failed: %s", e)
            return None

    def _decompose_heuristic(self, parent_task_id: str, task_description: str) -> TaskDependencyGraph:
        """Heuristic: one or two subtasks by length/keywords."""
        desc = (task_description or "").strip()
        if len(desc) < 300:
            st = SubTask(
                id=f"{parent_task_id}_sub_0",
                parent_task_id=parent_task_id,
                title=desc[:200] or "Task",
                description=desc,
                category="general",
                estimated_duration_min=30,
                dependencies=[],
                priority="medium",
            )
            return TaskDependencyGraph(subtasks={st.id: st}, dependencies={st.id: []})
        # Split into two: "analysis" and "implementation" or by first sentence / rest
        parts = re.split(r"\n\n+", desc, maxsplit=1)
        if len(parts) >= 2 and len(parts[0]) > 20 and len(parts[1]) > 20:
            t0 = parts[0][:200].strip() or "Part 1"
            t1 = (parts[1][:200].strip() or "Part 2")[:200]
            d0 = parts[0] + "\n\n[First part]"
            d1 = parts[1]
            id0 = f"{parent_task_id}_sub_0"
            id1 = f"{parent_task_id}_sub_1"
            st0 = SubTask(id=id0, parent_task_id=parent_task_id, title=t0, description=d0, dependencies=[], estimated_duration_min=20, priority="medium")
            st1 = SubTask(id=id1, parent_task_id=parent_task_id, title=t1, description=d1, dependencies=[id0], estimated_duration_min=30, priority="medium")
            return TaskDependencyGraph(
                subtasks={id0: st0, id1: st1},
                dependencies={id0: [], id1: [id0]},
            )
        st = SubTask(
            id=f"{parent_task_id}_sub_0",
            parent_task_id=parent_task_id,
            title=desc[:200] or "Task",
            description=desc,
            category="general",
            estimated_duration_min=max(30, len(desc) // 50),
            dependencies=[],
            priority="medium",
        )
        return TaskDependencyGraph(subtasks={st.id: st}, dependencies={st.id: []})
