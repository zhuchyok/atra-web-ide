"""
Master Plan Generator - генерация большого стратегического плана
Концепция из agent.md: MASTER_PLAN для стратегий с указанием ролей
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from prompt_templates import format_prompt, get_prompt_template
    from query_orchestrator import QueryOrchestrator
except ImportError:
    QueryOrchestrator = None
    get_prompt_template = None
    format_prompt = None

try:
    from strategy_session_manager import StrategySessionManager
except ImportError:
    StrategySessionManager = None

try:
    from strategy_discovery import StrategyDiscovery
except ImportError:
    StrategyDiscovery = None

try:
    from ai_core import run_smart_agent_async
except ImportError:
    run_smart_agent_async = None


class MasterPlanGenerator:
    """
    Генератор MASTER_PLAN для торговых стратегий

    Функции:
    - Генерация структурированного MASTER_PLAN в Markdown
    - Разделы: Индикаторы, Фильтры, Риск-менеджмент, Оптимизация, Тестирование
    - Указание рекомендуемых ролей для каждого раздела
    - Сохранение плана в БД
    """

    def __init__(
        self,
        query_orch: Optional[QueryOrchestrator] = None,
        session_manager: Optional[StrategySessionManager] = None,
    ):
        """
        Инициализация генератора MASTER_PLAN

        Args:
            query_orch: Query Orchestrator (опционально)
            session_manager: Strategy Session Manager (опционально)
        """
        self.query_orch = query_orch or (
            QueryOrchestrator(session_manager) if QueryOrchestrator else None
        )
        self.session_manager = session_manager

    async def generate_master_plan(self, session_id: str) -> str:
        """
        Генерирует MASTER_PLAN для сессии

        Args:
            session_id: ID сессии

        Returns:
            str: plan_id
        """
        if not self.session_manager:
            logger.warning("⚠️ [MASTER PLAN] SessionManager не доступен")
            return ""

        try:
            # Получаем Discovery summary
            discovery_summary = ""
            if StrategyDiscovery:
                discovery = StrategyDiscovery(self.session_manager, self.query_orch)
                discovery_summary = discovery.get_discovery_summary(session_id)

            # Получаем сессию
            session = self.session_manager.get_session(session_id)
            if not session:
                logger.error(f"❌ [MASTER PLAN] Сессия {session_id} не найдена")
                return ""

            # Формируем промпт для генерации MASTER_PLAN
            master_plan_prompt = self._build_master_plan_prompt(session, discovery_summary)

            # Генерируем MASTER_PLAN через LLM
            master_plan_markdown = ""
            if run_smart_agent_async:
                try:
                    # Используем Query Orchestrator с ролью "Архитектор" (Виктория)
                    master_plan_markdown = await run_smart_agent_async(
                        master_plan_prompt, expert_name="Виктория", category="architecture"
                    )
                except Exception as e:
                    logger.error(f"❌ [MASTER PLAN] Ошибка генерации через LLM: {e}")
                    # Fallback: создаем базовый план
                    master_plan_markdown = self._generate_basic_master_plan(
                        session, discovery_summary
                    )
            else:
                # Fallback: создаем базовый план
                master_plan_markdown = self._generate_basic_master_plan(session, discovery_summary)

            # Сохраняем план в БД
            plan_id = self.session_manager.create_plan(
                session_id=session_id,
                level="master",
                title=f"MASTER_PLAN: {session['title']}",
                markdown=master_plan_markdown,
                role_hint="Виктория",  # Team Lead / Архитектор
            )

            # Обновляем статус сессии
            self.session_manager.update_session_status(session_id, "planning")

            logger.info(f"📋 [MASTER PLAN] Создан MASTER_PLAN {plan_id} для сессии {session_id}")

            return plan_id
        except Exception as e:
            logger.error(f"❌ [MASTER PLAN] Ошибка генерации MASTER_PLAN: {e}")
            return ""

    def _build_master_plan_prompt(self, session: Dict[str, Any], discovery_summary: str) -> str:
        """
        Формирует промпт для генерации MASTER_PLAN

        Args:
            session: Информация о сессии
            discovery_summary: Summary Discovery фазы

        Returns:
            str: Промпт для LLM
        """
        # Услуги сотрудников: список экспертов для назначения на разделы плана (из configs/experts/employees.json)
        expert_services_block = ""
        try:
            from expert_services import get_expert_services_for_planning

            expert_services_block = "\n\n" + get_expert_services_for_planning()
        except ImportError:
            expert_services_block = """
Доступные эксперты по разделам плана:
- индикаторы, фильтры, стратегия: Павел (Trading Strategy Developer)
- риск-менеджмент: Мария (Risk Manager)
- оптимизация, тесты, метрики: Максим (Data Analyst)
- код, архитектура: Игорь (Backend), Виктория (Team Lead)
"""

        prompt = f"""Ты Виктория (Team Lead / Архитектор).

ЗАДАЧА: Сформируй большой стратегический план торговой стратегии в формате Markdown.

ИНФОРМАЦИЯ О ЗАДАЧЕ:
- Название: {session.get("title", "Торговая стратегия")}
- Описание: {session.get("description", "")}

СОБРАННЫЕ ТРЕБОВАНИЯ (Discovery фаза):
{discovery_summary if discovery_summary else "Нет дополнительных требований"}
{expert_services_block}

ТРЕБОВАНИЯ К ПЛАНУ:
1. Создай структурированный план в формате Markdown с разделами:
   - Индикаторы (какие индикаторы использовать)
   - Фильтры (какие фильтры применять)
   - Риск-менеджмент (SL/TP, размер позиции, максимальный риск)
   - Оптимизация (параметры для оптимизации)
   - Тестирование (бэктесты, валидация)

2. Для каждого раздела укажи рекомендуемого эксперта из списка выше (имя и роль).

3. Не вдавайся в излишнюю детализацию - детализация будет на следующем шаге (декомпозиция).

4. Формат раздела:
   ```markdown
   ## [Название раздела]
   Роль: [Имя эксперта]

   [Описание раздела]
   ```

Формат ответа: Только Markdown план, без дополнительных пояснений.
"""
        return prompt

    def _generate_basic_master_plan(self, session: Dict[str, Any], discovery_summary: str) -> str:
        """
        Генерирует базовый MASTER_PLAN (fallback, если LLM недоступен)

        Args:
            session: Информация о сессии
            discovery_summary: Summary Discovery фазы

        Returns:
            str: Базовый MASTER_PLAN в Markdown
        """
        title = session.get("title", "Торговая стратегия")

        master_plan = f"""# MASTER_PLAN: {title}

## 1. Индикаторы
Роль: Павел (Trading Strategy Developer)

- Определить набор индикаторов для анализа
- Настроить параметры индикаторов
- Интегрировать индикаторы в сигнальную систему

## 2. Фильтры
Роль: Павел (Trading Strategy Developer)

- Определить фильтры для отбора сигналов
- Настроить параметры фильтров (strict/soft)
- Интегрировать фильтры в сигнальную систему

## 3. Риск-менеджмент
Роль: Мария (Risk Manager)

- Определить размер позиции
- Настроить Stop Loss и Take Profit
- Установить максимальный риск на сделку
- Контроль максимального drawdown

## 4. Оптимизация
Роль: Максим (Data Analyst)

- Определить параметры для оптимизации
- Провести бэктесты
- Оптимизировать параметры стратегии

## 5. Тестирование
Роль: Максим (Data Analyst)

- Провести валидацию стратегии
- Проверить метрики производительности
- Подготовить отчет о результатах

---

**Discovery Summary:**
{discovery_summary if discovery_summary else "Нет дополнительных требований"}
"""
        return master_plan

    async def update_master_plan(self, plan_id: str, changes: Dict[str, Any]) -> bool:
        """
        Обновляет MASTER_PLAN.

        Поддерживаемые ключи в changes:
        - markdown: полная замена содержимого плана
        - title: новое название
        - status: новый статус (active/archived и т.д.)
        - role_hint: рекомендуемая роль
        - amend_instruction: текст инструкции для LLM — план дорабатывается по инструкции (например «добавь раздел про риск»)

        Returns:
            True если план обновлён, иначе False.
        """
        if not self.session_manager:
            logger.warning("⚠️ [MASTER PLAN] SessionManager не доступен")
            return False
        plan = self.session_manager.get_plan(plan_id)
        if not plan:
            logger.warning(f"⚠️ [MASTER PLAN] План {plan_id} не найден")
            return False
        current_md = (plan.get("markdown_body") or "").strip()
        updated = False
        if "markdown" in changes and changes["markdown"] is not None:
            updated = self.session_manager.update_plan(
                plan_id, markdown=str(changes["markdown"]).strip()
            )
        if "title" in changes and changes["title"] is not None:
            updated = (
                self.session_manager.update_plan(plan_id, title=str(changes["title"])) or updated
            )
        if "status" in changes and changes["status"] is not None:
            updated = (
                self.session_manager.update_plan(plan_id, status=str(changes["status"])) or updated
            )
        if "role_hint" in changes and changes["role_hint"] is not None:
            updated = (
                self.session_manager.update_plan(plan_id, role_hint=str(changes["role_hint"]))
                or updated
            )
        if "amend_instruction" in changes and changes["amend_instruction"]:
            instruction = str(changes["amend_instruction"]).strip()
            if run_smart_agent_async and instruction:
                try:
                    prompt = f"""Текущий MASTER_PLAN (Markdown):

{current_md}

Инструкция по доработке: {instruction}

Верни ТОЛЬКО обновлённый полный MASTER_PLAN в Markdown, без пояснений до или после."""
                    new_md = await run_smart_agent_async(
                        prompt, expert_name="Виктория", category="architecture"
                    )
                    if new_md and len(new_md.strip()) > 50:
                        updated = (
                            self.session_manager.update_plan(plan_id, markdown=new_md.strip())
                            or updated
                        )
                        logger.info(f"📝 [MASTER PLAN] План {plan_id} доработан по инструкции LLM")
                except Exception as e:
                    logger.error(f"❌ [MASTER PLAN] Ошибка доработки плана через LLM: {e}")
        if updated:
            logger.info(f"📝 [MASTER PLAN] Обновление плана {plan_id} применено")
        return updated
