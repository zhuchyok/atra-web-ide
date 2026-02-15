"""
Plan Decomposer - итеративная декомпозиция MASTER_PLAN на подпланы
Концепция из agent.md: разбиение большого плана на подпланы с указанием ролей
"""

import logging
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

try:
    from query_orchestrator import QueryOrchestrator
    from prompt_templates import get_prompt_template, format_prompt
except ImportError:
    QueryOrchestrator = None
    get_prompt_template = None
    format_prompt = None

try:
    from strategy_session_manager import StrategySessionManager
except ImportError:
    StrategySessionManager = None

try:
    from ai_core import run_smart_agent_async
except ImportError:
    run_smart_agent_async = None


class PlanDecomposer:
    """
    Декомпозер планов для итеративного разбиения MASTER_PLAN на подпланы
    
    Функции:
    - Итеративное разбиение MASTER_PLAN на разделы
    - Декомпозиция каждого раздела на подпланы
    - Генерация вопросов для уточнения (если нужно)
    - Обновление подпланов после ответов
    """
    
    def __init__(self, query_orch: Optional[QueryOrchestrator] = None, session_manager: Optional[StrategySessionManager] = None):
        """
        Инициализация декомпозера планов
        
        Args:
            query_orch: Query Orchestrator (опционально)
            session_manager: Strategy Session Manager (опционально)
        """
        self.query_orch = query_orch or (QueryOrchestrator(session_manager) if QueryOrchestrator else None)
        self.session_manager = session_manager
    
    async def decompose_master_plan(self, session_id: str) -> Dict[str, List[str]]:
        """
        Декомпозирует MASTER_PLAN на подпланы
        
        Args:
            session_id: ID сессии
        
        Returns:
            Dict[str, List[str]]: plan_id -> [subplan_ids]
        """
        if not self.session_manager:
            logger.warning("⚠️ [DECOMPOSER] SessionManager не доступен")
            return {}
        
        try:
            conn = self.session_manager._get_connection()
            cursor = conn.cursor()
            
            # Получаем MASTER_PLAN для сессии
            cursor.execute(
                """
                SELECT id, markdown_body
                FROM strategy_plans
                WHERE session_id = ? AND level = 'master'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                logger.warning(f"⚠️ [DECOMPOSER] MASTER_PLAN не найден для сессии {session_id}")
                return {}
            
            master_plan_id = row['id']
            master_plan_markdown = row['markdown_body']
            
            # Парсим MASTER_PLAN на разделы
            sections = self._parse_sections(master_plan_markdown)
            
            # Обновляем статус сессии
            self.session_manager.update_session_status(session_id, "decomposing")
            
            # Декомпозируем каждый раздел
            decomposition_result = {master_plan_id: []}
            
            for section in sections:
                subplan_ids = await self.decompose_section(
                    section['title'],
                    section['content'],
                    master_plan_id,
                    section.get('role_hint', 'Виктория'),
                    session_id
                )
                decomposition_result[master_plan_id].extend(subplan_ids)
            
            logger.info(f"📋 [DECOMPOSER] Декомпозирован MASTER_PLAN {master_plan_id}: создано {len(decomposition_result[master_plan_id])} подпланов")
            
            return decomposition_result
        except Exception as e:
            logger.error(f"❌ [DECOMPOSER] Ошибка декомпозиции MASTER_PLAN: {e}")
            return {}
    
    def _parse_sections(self, markdown: str) -> List[Dict[str, str]]:
        """
        Парсит Markdown план на разделы
        
        Args:
            markdown: Markdown план
        
        Returns:
            List[Dict[str, str]]: Список разделов с title, content, role_hint
        """
        sections = []
        
        # Парсим разделы по заголовкам ##
        section_pattern = r'##\s+(\d+\.\s+)?(.+?)\n(.*?)(?=\n##\s+|$)'
        matches = re.finditer(section_pattern, markdown, re.DOTALL)
        
        for match in matches:
            title = match.group(2).strip()
            content = match.group(3).strip()
            
            # Извлекаем роль из раздела
            role_match = re.search(r'Роль:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
            role_hint = role_match.group(1).strip() if role_match else "Виктория"
            
            sections.append({
                'title': title,
                'content': content,
                'role_hint': role_hint
            })
        
        logger.debug(f"📋 [DECOMPOSER] Распарсено {len(sections)} разделов")
        
        return sections
    
    async def decompose_section(
        self,
        section_title: str,
        section_content: str,
        parent_plan_id: str,
        role_hint: str,
        session_id: str
    ) -> List[str]:
        """
        Декомпозирует раздел на подпланы
        
        Args:
            section_title: Название раздела
            section_content: Содержимое раздела
            parent_plan_id: ID родительского плана
            role_hint: Рекомендуемая роль
            session_id: ID сессии
        
        Returns:
            List[str]: Список subplan_ids
        """
        if not self.session_manager:
            return []
        
        try:
            # Формируем промпт для декомпозиции раздела
            decomposition_prompt = self._build_decomposition_prompt(section_title, section_content, role_hint)
            
            # Генерируем подплан через LLM
            subplan_markdown = ""
            if run_smart_agent_async:
                try:
                    # Используем Query Orchestrator с нужной ролью
                    subplan_markdown = await run_smart_agent_async(
                        decomposition_prompt,
                        expert_name=role_hint,
                        category="strategy"
                    )
                except Exception as e:
                    logger.error(f"❌ [DECOMPOSER] Ошибка генерации подплана через LLM: {e}")
                    # Fallback: создаем базовый подплан
                    subplan_markdown = self._generate_basic_subplan(section_title, section_content, role_hint)
            else:
                # Fallback: создаем базовый подплан
                subplan_markdown = self._generate_basic_subplan(section_title, section_content, role_hint)
            
            # Сохраняем подплан в БД
            subplan_id = self.session_manager.create_plan(
                session_id=session_id,
                level="sub",
                title=f"Подплан: {section_title}",
                markdown=subplan_markdown,
                role_hint=role_hint,
                parent_plan_id=parent_plan_id
            )
            
            logger.info(f"📋 [DECOMPOSER] Создан подплан {subplan_id} для раздела '{section_title}' (роль: {role_hint})")
            
            # Проверяем, нужны ли уточнения
            questions = await self.check_for_missing_info(subplan_id)
            
            return [subplan_id]
        except Exception as e:
            logger.error(f"❌ [DECOMPOSER] Ошибка декомпозиции раздела: {e}")
            return []
    
    def _build_decomposition_prompt(self, section_title: str, section_content: str, role_hint: str) -> str:
        """
        Формирует промпт для декомпозиции раздела
        
        Args:
            section_title: Название раздела
            section_content: Содержимое раздела
            role_hint: Рекомендуемая роль
        
        Returns:
            str: Промпт для LLM
        """
        prompt = f"""Ты {role_hint}.

ЗАДАЧА: Создай детальный подплан для раздела "{section_title}".

РАЗДЕЛ MASTER_PLAN:
{section_content}

ТРЕБОВАНИЯ К ПОДПЛАНУ:
1. Создай детальный подплан в формате Markdown
2. Разбей раздел на конкретные шаги
3. Укажи, какие задачи нужно выполнить
4. Если данных недостаточно, укажи, какие вопросы нужно задать пользователю

Формат ответа: Только Markdown подплан, без дополнительных пояснений.
"""
        return prompt
    
    def _generate_basic_subplan(self, section_title: str, section_content: str, role_hint: str) -> str:
        """
        Генерирует базовый подплан (fallback)
        
        Args:
            section_title: Название раздела
            section_content: Содержимое раздела
            role_hint: Рекомендуемая роль
        
        Returns:
            str: Базовый подплан в Markdown
        """
        subplan = f"""# Подплан: {section_title}

Роль: {role_hint}

{section_content}

## Шаги выполнения

1. [Шаг 1]
2. [Шаг 2]
3. [Шаг 3]

## Требования к уточнению

- [Если нужны уточнения, указать здесь]
"""
        return subplan
    
    async def check_for_missing_info(self, subplan_id: str) -> Optional[List[str]]:
        """
        Проверяет подплан на недостающую информацию через LLM.
        
        Args:
            subplan_id: ID подплана
        
        Returns:
            Optional[List[str]]: Список вопросов для уточнения, или None если уточнений не нужно
        """
        if not self.session_manager:
            return None
        try:
            conn = self.session_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT markdown_body FROM strategy_plans WHERE id = ?", (subplan_id,))
            row = cursor.fetchone()
            conn.close()
            if not row or not row[0]:
                return None
            subplan_md = row[0]
        except Exception as e:
            logger.debug("❓ [DECOMPOSER] Не удалось загрузить подплан %s: %s", subplan_id, e)
            return None
        if not run_smart_agent_async:
            return None
        prompt = f"""Проанализируй подплан и определи, какой информации не хватает для его выполнения.

ПОДПЛАН (Markdown):
{subplan_md[:4000]}

Верни ТОЛЬКО JSON-массив строк — список вопросов для уточнения (0–5 вопросов). Если информации достаточно, верни пустой массив [].
Пример: ["Какой таймфрейм использовать?", "Есть ли ограничения по риску?"]
Без пояснений, только JSON."""
        try:
            out = await run_smart_agent_async(prompt, expert_name="Виктория", category="reasoning")
            if not out or not out.strip():
                return None
            import json
            raw = out.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            questions = json.loads(raw)
            if isinstance(questions, list) and all(isinstance(q, str) for q in questions) and questions:
                logger.debug("❓ [DECOMPOSER] Подплан %s: сгенерировано %s вопросов", subplan_id, len(questions))
                return questions
        except Exception as e:
            logger.debug("❓ [DECOMPOSER] LLM проверка подплана: %s", e)
        return None
    
    async def refine_subplan(self, subplan_id: str, answers: Dict[str, str]) -> str:
        """
        Уточняет подплан на основе ответов пользователя через LLM и сохраняет в БД.
        
        Args:
            subplan_id: ID подплана
            answers: Словарь {question_id: answer}
        
        Returns:
            str: subplan_id (тот же, план обновлён в БД)
        """
        if not self.session_manager or not answers:
            return subplan_id
        try:
            conn = self.session_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT markdown_body FROM strategy_plans WHERE id = ?", (subplan_id,))
            row = cursor.fetchone()
            conn.close()
            if not row or not row[0]:
                return subplan_id
            subplan_md = row[0]
        except Exception as e:
            logger.debug("📝 [DECOMPOSER] Не удалось загрузить подплан %s: %s", subplan_id, e)
            return subplan_id
        answers_text = "\n".join(f"- {k}: {v}" for k, v in answers.items())
        if not run_smart_agent_async:
            return subplan_id
        prompt = f"""Обнови подплан с учётом ответов пользователя. Сохрани структуру Markdown, добавь уточнения в нужные места.

ТЕКУЩИЙ ПОДПЛАН:
{subplan_md[:4000]}

ОТВЕТЫ ПОЛЬЗОВАТЕЛЯ:
{answers_text}

Верни ТОЛЬКО обновлённый подплан в Markdown, без пояснений."""
        try:
            new_md = await run_smart_agent_async(prompt, expert_name="Виктория", category="strategy")
            if new_md and len(new_md.strip()) > 50:
                conn = self.session_manager._get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE strategy_plans SET markdown_body = ? WHERE id = ?", (new_md.strip(), subplan_id))
                conn.commit()
                conn.close()
                logger.info("📝 [DECOMPOSER] Подплан %s уточнён по ответам", subplan_id)
        except Exception as e:
            logger.debug("📝 [DECOMPOSER] Уточнение подплана: %s", e)
        return subplan_id

