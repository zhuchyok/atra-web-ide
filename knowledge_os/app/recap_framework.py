"""
ReCAP Framework - Recursive Context-Aware Reasoning and Planning
Основано на Meta ReCAP: +32% улучшение на multi-step reasoning
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Фаза 3 плана «Логика мысли»: чекпоинты рефлексии и пересмотр плана
VICTORIA_REFLECTION_ENABLED = os.getenv("VICTORIA_REFLECTION_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
VICTORIA_MAX_PLAN_REVISIONS = max(0, min(3, int(os.getenv("VICTORIA_MAX_PLAN_REVISIONS", "1"))))


class PlanningLevel(Enum):
    """Уровни планирования"""

    HIGH_LEVEL = "high_level"  # Высокоуровневое планирование
    MID_LEVEL = "mid_level"  # Средний уровень
    LOW_LEVEL = "low_level"  # Детальное выполнение


@dataclass
class PlanStep:
    """Один шаг плана"""

    step_id: int
    description: str
    level: PlanningLevel
    dependencies: List[int] = field(default_factory=list)
    status: str = "pending"  # pending, executing, completed, failed
    result: Optional[Any] = None
    context: Dict = field(default_factory=dict)


@dataclass
class ReCAPPlan:
    """План ReCAP"""

    goal: str
    high_level_steps: List[PlanStep] = field(default_factory=list)
    mid_level_steps: List[PlanStep] = field(default_factory=list)
    low_level_steps: List[PlanStep] = field(default_factory=list)
    context_history: List[Dict] = field(default_factory=list)
    current_step: Optional[int] = None


class ReCAPFramework:
    """
    ReCAP Framework - Recursive Context-Aware Reasoning and Planning

    Компоненты:
    1. Plan-ahead decomposition - декомпозиция задачи на уровни
    2. Structured context re-injection - структурированная реинъекция контекста
    3. Memory-efficient execution - эффективное использование памяти
    """

    def __init__(
        self,
        model_name: str = "phi3.5:3.8b",
        ollama_url: str = OLLAMA_URL,
        reflection_enabled: bool = VICTORIA_REFLECTION_ENABLED,
        max_plan_revisions: int = VICTORIA_MAX_PLAN_REVISIONS,
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.reflection_enabled = reflection_enabled
        self.max_plan_revisions = max_plan_revisions

    async def solve(self, goal: str, initial_context: Optional[Dict] = None) -> Dict:
        """
        Решить задачу используя ReCAP Framework

        Args:
            goal: Цель задачи
            initial_context: Начальный контекст

        Returns:
            Результат с планом и выполнением
        """
        logger.info(f"🚀 ReCAP: Начинаю решение задачи: {goal[:80]}")
        context = dict(initial_context) if initial_context else {}
        revision_count = 0

        while True:
            # 1. Plan-ahead decomposition (при пересмотре — с контекстом предыдущей неудачи)
            plan = await self._decompose_goal(goal, context if context else None)

            # 2. Structured context re-injection и выполнение (с чекпоинтами рефлексии)
            results, should_replan, failure_info = await self._execute_plan(plan, revision_count)

            if should_replan and failure_info and revision_count < self.max_plan_revisions:
                revision_count += 1
                context["previous_plan_failure"] = failure_info
                logger.info(
                    f"🔄 ReCAP: пересмотр плана (попытка {revision_count}), причина: {failure_info.get('reason', '')[:100]}"
                )
                continue

            # 3. Синтез финального результата
            final_result = await self._synthesize_result(plan, results)
            return {
                "goal": goal,
                "plan": plan,
                "results": results,
                "final_result": final_result,
                "method": "recap",
                "plan_revisions": revision_count,
            }

    async def _decompose_goal(self, goal: str, context: Optional[Dict]) -> ReCAPPlan:
        """Декомпозировать цель на уровни планирования"""

        # 1. High-level planning
        high_level_prompt = self._build_high_level_prompt(goal, context)
        high_level_response = await self._generate_response(high_level_prompt)
        high_level_steps = self._parse_planning_steps(high_level_response, PlanningLevel.HIGH_LEVEL)

        logger.info(f"📋 High-level: {len(high_level_steps)} шагов")

        # 2. Mid-level planning для каждого high-level шага
        mid_level_steps = []
        for hl_step in high_level_steps:
            mid_prompt = self._build_mid_level_prompt(goal, hl_step, context)
            mid_response = await self._generate_response(mid_prompt)
            mid_steps = self._parse_planning_steps(
                mid_response, PlanningLevel.MID_LEVEL, parent_id=hl_step.step_id
            )
            mid_level_steps.extend(mid_steps)
            hl_step.dependencies = [s.step_id for s in mid_steps]

        logger.info(f"📋 Mid-level: {len(mid_level_steps)} шагов")

        # 3. Low-level planning для каждого mid-level шага
        low_level_steps = []
        for ml_step in mid_level_steps:
            low_prompt = self._build_low_level_prompt(goal, ml_step, context)
            low_response = await self._generate_response(low_prompt)
            low_steps = self._parse_planning_steps(
                low_response, PlanningLevel.LOW_LEVEL, parent_id=ml_step.step_id
            )
            low_level_steps.extend(low_steps)
            ml_step.dependencies = [s.step_id for s in low_steps]

        logger.info(f"📋 Low-level: {len(low_level_steps)} шагов")

        return ReCAPPlan(
            goal=goal,
            high_level_steps=high_level_steps,
            mid_level_steps=mid_level_steps,
            low_level_steps=low_level_steps,
        )

    def _is_step_failed_or_empty(self, result: Any) -> bool:
        """Фаза 3: считать шаг провальным при пустом результате или явной ошибке."""
        if result is None:
            return True
        s = (str(result) or "").strip().lower()
        if not s:
            return True
        for kw in ("ошибка", "error", "failed", "не удалось", "не получилось", "exception"):
            if kw in s:
                return True
        return False

    async def _should_revise_plan(
        self, goal: str, plan_summary: str, step_description: str, step_result: Any
    ) -> Tuple[bool, str]:
        """Фаза 3: один вызов LLM — пересмотреть план? да/нет и причина. При ошибке — (False, '')."""
        try:
            import httpx

            prompt = f"""Задача: {goal[:300]}
План (кратко): {plan_summary[:400]}
Шаг, который провалился или дал пустой результат: {step_description[:200]}
Результат шага: {str(step_result)[:300]}

Нужно ли пересмотреть план с учётом этого провала? Ответь строго одной строкой: ДА <причина> или НЕТ."""
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": 150},
                    },
                )
                if r.status_code != 200:
                    return False, ""
                text = (r.json().get("response") or "").strip().upper()
                if "ДА" in text[:10] or text.startswith("YES"):
                    reason = text.replace("ДА", "").replace("YES", "").strip()[:200]
                    return True, reason or "провал шага"
                return False, ""
        except Exception as e:
            logger.debug("ReCAP _should_revise_plan: %s", e)
            return False, ""

    async def _execute_plan(
        self, plan: ReCAPPlan, revision_count: int = 0
    ) -> Tuple[Dict[int, Any], bool, Optional[Dict]]:
        """Выполнить план с structured context re-injection. Возвращает (results, should_replan, failure_info)."""
        results: Dict[int, Any] = {}
        context_history: List[Dict] = []
        plan_summary = "; ".join(s.description[:80] for s in plan.low_level_steps[:8])

        for hl_step in plan.high_level_steps:
            context = self._build_context(plan, hl_step, context_history, results=results)
            mid_steps = [s for s in plan.mid_level_steps if s.step_id in hl_step.dependencies]

            for ml_step in mid_steps:
                ml_context = self._build_context(
                    plan, ml_step, context_history, parent_context=context, results=results
                )
                low_steps = [s for s in plan.low_level_steps if s.step_id in ml_step.dependencies]

                for ll_step in low_steps:
                    ll_context = self._build_context(
                        plan,
                        ll_step,
                        context_history,
                        parent_context=ml_context,
                        grandparent_context=context,
                        results=results,
                    )
                    result = await self._execute_step(ll_step, ll_context)
                    results[ll_step.step_id] = result
                    ll_step.result = result

                    if (
                        self._is_step_failed_or_empty(result)
                        and self.reflection_enabled
                        and revision_count < self.max_plan_revisions
                    ):
                        revise, reason = await self._should_revise_plan(
                            plan.goal, plan_summary, ll_step.description, result
                        )
                        if revise:
                            ll_step.status = "failed"
                            failure_info = {
                                "step_id": ll_step.step_id,
                                "step_description": ll_step.description,
                                "result": str(result)[:500],
                                "reason": reason or "провал шага",
                            }
                            return results, True, failure_info

                    ll_step.status = "completed"
                    context_history.append(
                        {
                            "step_id": ll_step.step_id,
                            "level": ll_step.level.value,
                            "context": ll_context,
                            "result": result,
                            "timestamp": datetime.now(timezone.utc),
                        }
                    )

                ml_result = self._aggregate_results([results[s.step_id] for s in low_steps])
                results[ml_step.step_id] = ml_result
                ml_step.status = "completed"
                ml_step.result = ml_result

            hl_result = self._aggregate_results([results[s.step_id] for s in mid_steps])
            results[hl_step.step_id] = hl_result
            hl_step.status = "completed"
            hl_step.result = hl_result

        return results, False, None

    def _build_context(
        self,
        plan: ReCAPPlan,
        step: PlanStep,
        context_history: List[Dict],
        parent_context: Optional[Dict] = None,
        grandparent_context: Optional[Dict] = None,
        results: Optional[Dict[int, Any]] = None,
    ) -> Dict:
        """Построить структурированный контекст с реинъекцией.

        Если передан results (словарь step_id -> результат), в блок dependencies
        подставляются реальные результаты выполненных шагов; иначе — "pending".
        """
        context = {
            "goal": plan.goal,
            "current_step": step.description,
            "step_level": step.level.value,
            "step_id": step.step_id,
        }

        # Добавляем родительский контекст
        if parent_context:
            context["parent_context"] = parent_context

        if grandparent_context:
            context["grandparent_context"] = grandparent_context

        # Добавляем релевантную историю (только последние N шагов для эффективности памяти)
        relevant_history = context_history[-5:]  # Memory-efficient: только последние 5
        context["recent_history"] = relevant_history

        # Добавляем зависимости (реальные результаты из results, если есть)
        if step.dependencies:
            context["dependencies"] = [
                {
                    "step_id": dep_id,
                    "result": results.get(dep_id, "pending") if results is not None else "pending",
                }
                for dep_id in step.dependencies
            ]

        return context

    async def _execute_step(self, step: PlanStep, context: Dict) -> Any:
        """Выполнить один шаг плана"""
        logger.info(f"🔄 Выполнение шага {step.step_id}: {step.description[:50]}")

        # Строим промпт для выполнения
        prompt = f"""Выполни следующий шаг плана:

ШАГ: {step.description}
КОНТЕКСТ: {context}

Выполни действие и верни результат."""

        # Генерируем выполнение через модель
        result = await self._generate_response(prompt)

        return result

    def _aggregate_results(self, results: List[Any]) -> Any:
        """Агрегировать результаты нескольких шагов"""
        # Простая агрегация - объединение результатов
        if not results:
            return None

        if len(results) == 1:
            return results[0]

        # Объединяем результаты
        aggregated = "\n".join([str(r) for r in results])
        return aggregated

    async def _synthesize_result(self, plan: ReCAPPlan, results: Dict[int, Any]) -> str:
        """Синтезировать финальный результат из всех шагов"""
        # Собираем результаты high-level шагов
        high_level_results = [
            results[step.step_id] for step in plan.high_level_steps if step.step_id in results
        ]

        # Строим промпт для синтеза
        prompt = f"""Синтезируй финальный результат на основе выполнения плана:

ЦЕЛЬ: {plan.goal}

РЕЗУЛЬТАТЫ ВЫСОКОУРОВНЕВЫХ ШАГОВ:
"""
        for i, (step, result) in enumerate(zip(plan.high_level_steps, high_level_results), 1):
            prompt += f"\n{i}. {step.description}\n   Результат: {result}\n"

        prompt += "\nФИНАЛЬНЫЙ РЕЗУЛЬТАТ:"

        final_result = await self._generate_response(prompt)
        return final_result

    def _build_high_level_prompt(self, goal: str, context: Optional[Dict]) -> str:
        """Построить промпт для high-level планирования"""
        prompt = f"""Разбей задачу на высокоуровневые шаги (3-5 шагов):

ЗАДАЧА: {goal}

"""
        if context:
            prev = context.get("previous_plan_failure")
            if isinstance(prev, dict):
                prompt += f"ПРЕДЫДУЩАЯ ПОПЫТКА НЕ УДАЛАСЬ (учти при новом плане): шаг «{prev.get('step_description', '')[:150]}» — {prev.get('reason', 'провал')}. Избегай повторения.\n\n"
            prompt += f"КОНТЕКСТ: {context}\n\n"

        prompt += """Создай план из высокоуровневых шагов. Каждый шаг должен быть:
1. Четко определен
2. Независим от других (где возможно)
3. Ведет к достижению цели

ФОРМАТ:
1. [Описание шага 1]
2. [Описание шага 2]
...

ВЫСОКОУРОВНЕВЫЙ ПЛАН:"""

        return prompt

    def _build_mid_level_prompt(
        self, goal: str, high_level_step: PlanStep, context: Optional[Dict]
    ) -> str:
        """Построить промпт для mid-level планирования"""
        prompt = f"""Разбей высокоуровневый шаг на средние шаги (2-4 шага):

ЦЕЛЬ: {goal}
ВЫСОКОУРОВНЕВЫЙ ШАГ: {high_level_step.description}

"""
        if context:
            prompt += f"КОНТЕКСТ: {context}\n\n"

        prompt += """Создай средние шаги для выполнения этого высокоуровневого шага.

ФОРМАТ:
1. [Описание среднего шага 1]
2. [Описание среднего шага 2]
...

СРЕДНИЕ ШАГИ:"""

        return prompt

    def _build_low_level_prompt(
        self, goal: str, mid_level_step: PlanStep, context: Optional[Dict]
    ) -> str:
        """Построить промпт для low-level планирования"""
        prompt = f"""Разбей средний шаг на детальные действия (1-3 действия):

ЦЕЛЬ: {goal}
СРЕДНИЙ ШАГ: {mid_level_step.description}

"""
        if context:
            prompt += f"КОНТЕКСТ: {context}\n\n"

        prompt += """Создай детальные действия для выполнения этого среднего шага.

ФОРМАТ:
1. [Детальное действие 1]
2. [Детальное действие 2]
...

ДЕТАЛЬНЫЕ ДЕЙСТВИЯ:"""

        return prompt

    def _parse_planning_steps(
        self, response: str, level: PlanningLevel, parent_id: Optional[int] = None
    ) -> List[PlanStep]:
        """Парсить шаги планирования из ответа"""
        import re

        steps = []
        # Ищем нумерованные шаги
        pattern = r"(\d+)\.\s*(.+?)(?=\d+\.|$)"
        matches = re.finditer(pattern, response, re.DOTALL)

        step_id_base = {
            PlanningLevel.HIGH_LEVEL: 1000,
            PlanningLevel.MID_LEVEL: 2000,
            PlanningLevel.LOW_LEVEL: 3000,
        }.get(level, 0)

        for i, match in enumerate(matches, 1):
            step_num = int(match.group(1))
            description = match.group(2).strip()

            step = PlanStep(step_id=step_id_base + i, description=description, level=level)

            if parent_id:
                step.dependencies = [parent_id]

            steps.append(step)

        return steps

    async def _generate_response(self, prompt: str, max_tokens: int = 2048) -> str:
        """Генерировать ответ через модель"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.5, "num_predict": max_tokens},
                    },
                )

                if response.status_code == 200:
                    return response.json().get("response", "")
                else:
                    logger.error(f"Ошибка генерации: {response.status_code}")
                    return ""
        except Exception as e:
            logger.error(f"Ошибка запроса к модели: {e}")
            return ""


async def main():
    """Пример использования"""
    framework = ReCAPFramework(model_name="phi3.5:3.8b")

    result = await framework.solve(
        "Создай систему мониторинга производительности для веб-приложения"
    )

    print("Результат ReCAP:")
    print(f"Цель: {result['goal']}")
    print(f"High-level шагов: {len(result['plan'].high_level_steps)}")
    print(f"Mid-level шагов: {len(result['plan'].mid_level_steps)}")
    print(f"Low-level шагов: {len(result['plan'].low_level_steps)}")
    print(f"\nФинальный результат:\n{result['final_result']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
