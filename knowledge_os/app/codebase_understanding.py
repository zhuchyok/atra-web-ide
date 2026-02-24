"""
Codebase Understanding - анализ существующего кода перед изменениями
Концепция из agent.md: reuse first политика - переиспользование существующего кода
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from query_orchestrator import QueryOrchestrator
except ImportError:
    QueryOrchestrator = None


class CodebaseUnderstanding:
    """
    Анализ существующего кода для переиспользования

    Функции:
    - Сканирование существующих стратегий/фильтров/индикаторов
    - Поиск похожих решений
    - Классификация: reuse / reuse+refactor / deprecate / new
    - Предложение переиспользования перед созданием нового кода
    """

    # Паттерны для поиска торговых компонентов
    STRATEGY_PATTERNS = [
        r"class.*Strategy.*:",
        r"def.*strategy.*\(",
        r"strategy.*=.*\(",
    ]

    FILTER_PATTERNS = [
        r"class.*Filter.*:",
        r"def.*filter.*\(",
        r"filter.*=.*\(",
    ]

    INDICATOR_PATTERNS = [
        r"def.*rsi.*\(",
        r"def.*macd.*\(",
        r"def.*ema.*\(",
        r"def.*sma.*\(",
        r"def.*bb.*\(",
        r"def.*atr.*\(",
    ]

    # Директории для сканирования
    SCAN_DIRECTORIES = [
        "src/strategies",
        "src/filters",
        "src/data/technical.py",
        "rust-atra/src",
    ]

    def __init__(self, query_orch: Optional[QueryOrchestrator] = None, project_root: str = "."):
        """
        Инициализация анализатора кодовой базы

        Args:
            query_orch: Query Orchestrator (опционально)
            project_root: Корень проекта (по умолчанию текущая директория)
        """
        self.query_orch = query_orch
        self.project_root = Path(project_root)
        self._codebase_cache: Dict[str, List[Dict[str, Any]]] = {}

    def _scan_codebase(self, file_patterns: List[str]) -> List[Dict[str, Any]]:
        """
        Сканирует кодовую базу на наличие компонентов

        Args:
            file_patterns: Паттерны файлов для сканирования

        Returns:
            List[Dict[str, Any]]: Список найденных компонентов
        """
        components = []

        for scan_dir in self.SCAN_DIRECTORIES:
            scan_path = self.project_root / scan_dir
            if not scan_path.exists():
                continue

            # Сканируем Python файлы
            for py_file in scan_path.rglob("*.py"):
                try:
                    with open(py_file, encoding="utf-8") as f:
                        content = f.read()
                        file_path = str(py_file.relative_to(self.project_root))

                        # Ищем стратегии
                        for pattern in self.STRATEGY_PATTERNS:
                            matches = re.finditer(pattern, content, re.IGNORECASE)
                            for match in matches:
                                components.append(
                                    {
                                        "type": "strategy",
                                        "file": file_path,
                                        "line": content[: match.start()].count("\n") + 1,
                                        "match": match.group(0),
                                    }
                                )

                        # Ищем фильтры
                        for pattern in self.FILTER_PATTERNS:
                            matches = re.finditer(pattern, content, re.IGNORECASE)
                            for match in matches:
                                components.append(
                                    {
                                        "type": "filter",
                                        "file": file_path,
                                        "line": content[: match.start()].count("\n") + 1,
                                        "match": match.group(0),
                                    }
                                )

                        # Ищем индикаторы
                        for pattern in self.INDICATOR_PATTERNS:
                            matches = re.finditer(pattern, content, re.IGNORECASE)
                            for match in matches:
                                components.append(
                                    {
                                        "type": "indicator",
                                        "file": file_path,
                                        "line": content[: match.start()].count("\n") + 1,
                                        "match": match.group(0),
                                    }
                                )
                except Exception as e:
                    logger.debug(f"⚠️ [CODEBASE] Ошибка сканирования {py_file}: {e}")

        logger.debug(f"📋 [CODEBASE] Найдено компонентов: {len(components)}")
        return components

    async def analyze_existing_code(
        self, task_description: str, file_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Анализирует существующий код перед изменениями

        Args:
            task_description: Описание задачи
            file_patterns: Паттерны файлов для анализа (опционально)

        Returns:
            Dict[str, Any]: Результаты анализа с найденными компонентами
        """
        # Сканируем кодовую базу
        components = self._scan_codebase(file_patterns or [])

        # Классифицируем найденные компоненты по релевантности к задаче
        relevant_components = self._find_relevant_components(task_description, components)

        # Группируем по типам
        by_type = {
            "strategies": [c for c in relevant_components if c["type"] == "strategy"],
            "filters": [c for c in relevant_components if c["type"] == "filter"],
            "indicators": [c for c in relevant_components if c["type"] == "indicator"],
        }

        result = {
            "total_components": len(components),
            "relevant_components": len(relevant_components),
            "by_type": by_type,
            "recommendations": await self._generate_recommendations(
                task_description, relevant_components
            ),
        }

        logger.info(
            f"📋 [CODEBASE] Анализ завершен: найдено {len(relevant_components)} релевантных компонентов"
        )

        return result

    def _find_relevant_components(
        self, task_description: str, components: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Находит релевантные компоненты для задачи

        Args:
            task_description: Описание задачи
            components: Список компонентов

        Returns:
            List[Dict[str, Any]]: Релевантные компоненты
        """
        task_lower = task_description.lower()
        relevant = []

        # Простой поиск по ключевым словам
        keywords = task_lower.split()

        for component in components:
            # Проверяем совпадение по типу
            if component["type"] in task_lower:
                relevant.append(component)
                continue

            # Проверяем совпадение по имени файла
            file_lower = component["file"].lower()
            if any(kw in file_lower for kw in keywords if len(kw) > 3):
                relevant.append(component)

        return relevant

    async def _generate_recommendations(
        self, task_description: str, relevant_components: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Генерирует рекомендации по переиспользованию

        Args:
            task_description: Описание задачи
            relevant_components: Релевантные компоненты

        Returns:
            List[Dict[str, str]]: Рекомендации
        """
        recommendations = []

        for component in relevant_components[:5]:  # Максимум 5 рекомендаций
            classification = await self._classify_component(component, task_description)

            recommendations.append(
                {
                    "file": component["file"],
                    "line": component["line"],
                    "type": component["type"],
                    "classification": classification,
                    "action": self._get_action_for_classification(classification),
                }
            )

        return recommendations

    def _classify_component_heuristic(
        self, component: Dict[str, Any], task_description: str
    ) -> str:
        """Эвристическая классификация без LLM."""
        task_lower = task_description.lower()
        component_type = component["type"]
        if component_type in task_lower:
            return "reuse"
        if any(kw in task_lower for kw in ["улучшить", "оптимизировать", "модифицировать"]):
            return "reuse+refactor"
        return "reuse"

    async def _classify_component(self, component: Dict[str, Any], task_description: str) -> str:
        """
        Классифицирует компонент: reuse / reuse+refactor / deprecate / new (с LLM при возможности).
        """
        try:
            from ai_core import run_smart_agent_async
        except ImportError:
            return self._classify_component_heuristic(component, task_description)
        prompt = f"""Классифицируй компонент кода по отношению к задаче. Ответь ОДНИМ словом: reuse, reuse+refactor, deprecate или new.

Задача: {task_description[:500]}
Компонент: тип={component.get("type")}, файл={component.get("file")}, фрагмент={str(component.get("match", ""))[:200]}

Ответ (только одно слово):"""
        try:
            out = await run_smart_agent_async(prompt, expert_name="Виктория", category="general")
            if out:
                c = out.strip().lower().split()[0] if out.strip() else ""
                if c in ("reuse", "reuse+refactor", "deprecate", "new"):
                    return c
        except Exception as e:
            logger.debug("classify_component LLM: %s", e)
        return self._classify_component_heuristic(component, task_description)

    def _get_action_for_classification(self, classification: str) -> str:
        """
        Получает действие для классификации

        Args:
            classification: Классификация компонента

        Returns:
            str: Рекомендуемое действие
        """
        actions = {
            "reuse": "Использовать существующий компонент 'как есть'",
            "reuse+refactor": "Улучшить и использовать существующий компонент",
            "deprecate": "Признать устаревшим и заменить",
            "new": "Создать новый компонент",
        }

        return actions.get(classification, "Требуется анализ")

    async def classify_code_match(self, code_file: str, task: str) -> str:
        """
        Классифицирует совпадение кода с задачей (LLM при возможности, иначе эвристика).
        """
        try:
            from ai_core import run_smart_agent_async
        except ImportError:
            pass
        else:
            prompt = f"""По файлу кода и задаче ответь ОДНИМ словом: reuse, reuse+refactor, deprecate или new.

Файл: {code_file}
Задача: {task[:500]}

Ответ (только одно слово):"""
            try:
                out = await run_smart_agent_async(
                    prompt, expert_name="Виктория", category="general"
                )
                if out:
                    c = out.strip().lower().split()[0] if out.strip() else ""
                    if c in ("reuse", "reuse+refactor", "deprecate", "new"):
                        return c
            except Exception as e:
                logger.debug("classify_code_match LLM: %s", e)
        task_lower = task.lower()
        file_lower = code_file.lower()
        if any(kw in file_lower for kw in task_lower.split() if len(kw) > 3):
            if any(kw in task_lower for kw in ["улучшить", "оптимизировать", "модифицировать"]):
                return "reuse+refactor"
            return "reuse"
        return "new"

    async def suggest_reuse(self, strategy_name: str, task: str) -> Optional[Dict[str, str]]:
        """
        Предлагает переиспользование существующей стратегии

        Args:
            strategy_name: Название стратегии
            task: Описание задачи

        Returns:
            Optional[Dict[str, str]]: Предложение по переиспользованию или None
        """
        # Сканируем кодовую базу
        components = self._scan_codebase([])

        # Ищем стратегии с похожим названием
        for component in components:
            if component["type"] == "strategy":
                file_lower = component["file"].lower()
                strategy_lower = strategy_name.lower()

                # Если найдена похожая стратегия
                if strategy_lower in file_lower or any(
                    word in file_lower for word in strategy_lower.split()
                ):
                    return {
                        "file": component["file"],
                        "line": str(component["line"]),
                        "recommendation": "reuse",
                        "action": f"Использовать существующую стратегию из {component['file']}",
                    }

        return None
