"""
Единый источник текста возможностей Victoria («что ты умеешь» / «кто ты»),
логики работы корпорации («как мы мыслим») и общих фрагментов промптов (русский, краткость).
Используется victoria_server (src/agents/bridge), victoria_enhanced и react_agent (knowledge_os).
Редактировать configs/victoria_capabilities.txt и configs/corporation_thinking.txt.
"""
import os
from typing import Optional

# Единый фрагмент «русский + краткость» для промптов Victoria (куратор, эталоны, регрессия)
PROMPT_RUSSIAN_ONLY = (
    "КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке! "
    "Все ответы, объяснения и комментарии должны быть на русском!"
)
PROMPT_RUSSIAN_AND_BREVITY_LINES = (
    "1. ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке!\n"
    "2. Ответ должен быть КРАТКИМ - максимум 3-5 предложений!\n"
    "3. НЕ генерируй длинные списки, инструкции или повторяющийся текст!\n"
    "4. НЕ повторяй вопрос, НЕ пиши \"Запрос:\" или \"Ответ:\"!"
)

# Мировые практики: один источник истины, библия (план «умнее быстрее», CURATOR_MENTOR_CAUSES)
WORLD_PRACTICES_LINE = (
    "Учитывай лучшие практики: один источник истины (документация), проверяемый результат, актуальная библия (MASTER_REFERENCE)."
)

# Фаза 4 плана «Логика мысли»: при низкой уверенности явно выражать неопределённость (не заменяет anti_hallucination)
PROMPT_UNCERTAINTY_LINE = (
    "При недостатке данных или неуверенности в ответе явно пиши: «здесь я не уверен», «нужны данные …», «рекомендую проверить». Не приукрашивай уверенность."
)


def build_simple_prompt(
    role_instruction: str,
    kb_block: str,
    goal: str,
    *,
    world_practices_line: Optional[str] = None,
    include_uncertainty_line: bool = True,
) -> str:
    """
    Единый шаблон simple-промпта Victoria (план «как я»: один источник истины).
    Используется в victoria_enhanced при сборке ответа методом simple.
    include_uncertainty_line: Фаза 4 — при низкой уверенности явно выражать неопределённость.
    """
    if world_practices_line is None:
        world_practices_line = WORLD_PRACTICES_LINE
    uncertainty_block = f"7. {PROMPT_UNCERTAINTY_LINE}\n" if include_uncertainty_line else ""
    return (
        f"Ты Виктория, Team Lead корпорации ATRA. {role_instruction}\n\n"
        f"КРИТИЧЕСКИ ВАЖНО:\n{PROMPT_RUSSIAN_AND_BREVITY_LINES}\n"
        f"5. Если выше дан контекст из базы знаний — ответь ТОЛЬКО на его основе (дашборд, MASTER_REFERENCE, задачи). Не выдумывай.\n"
        f"6. {world_practices_line}\n"
        f"{uncertainty_block}\n"
        f"{kb_block}Запрос: {goal}\n\n"
        "Ответ (кратко, 3-5 предложений, ОБЯЗАТЕЛЬНО на русском языке):"
    )


_THINKING_FALLBACK = """ПРИНЦИПЫ: Делать как нужно; один источник истины (библия); уточнять при неясности; проверять результат; обновлять библию после изменений.
ПОСЛЕДОВАТЕЛЬНОСТЬ: Понять → Контекст (библия/runbook) → План → Выполнить → Проверить → Зафиксировать."""

_DEFAULT = """Я Виктория, Team Lead Atra Core. Умею:
• Отвечать на вопросы и вести чат (в т.ч. с экспертами и RAG по базе знаний)
• Составлять планы и выполнять задачи: код, файлы, команды в терминале
• Показывать список файлов, читать и анализировать проект
• Делегировать простые запросы в Veronica, сложные — оркестрировать с командой
Режимы: быстрый ответ на простые вопросы или полный цикл (ReAct) для сложных задач."""


def get_capabilities_text() -> str:
    """Прочитать текст из configs/victoria_capabilities.txt или вернуть fallback."""
    path = os.environ.get("VICTORIA_CAPABILITIES_FILE")
    if not path:
        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "victoria_capabilities.txt")
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                out = f.read().strip() or _DEFAULT
                return out
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("[victoria_capabilities] Не удалось прочитать %s: %s", path, e)
    return _DEFAULT


def get_thinking_context() -> str:
    """Прочитать логику корпорации (corporation_thinking.txt) для вставки в промпт Victoria.
    Источник: docs/THINKING_AND_APPROACH.md."""
    import logging
    _log = logging.getLogger(__name__)
    path = os.environ.get("CORPORATION_THINKING_FILE")
    if not path:
        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "corporation_thinking.txt")
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read().strip()
                # Убрать комментарии и пустые строки в начале, оставить блок для промпта
                lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
                if lines:
                    return "\n".join(lines)
                _log.warning("[corporation_thinking] Файл %s пуст или только комментарии, используем fallback", path)
        except Exception as e:
            _log.warning("[corporation_thinking] Не удалось прочитать %s: %s, используем fallback", path, e)
    else:
        _log.debug("[corporation_thinking] Файл не найден: %s, используем fallback", path)
    return _THINKING_FALLBACK
