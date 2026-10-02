"""
Детектор типа задачи для маршрутизации запросов Victoria.
Определяет: simple_chat (приветствия, простые вопросы) → быстрый путь без Enhanced;
veronica / department_heads / enhanced — для выбора обработчика.

Мировая практика (docs/VERONICA_REAL_ROLE.md): Veronica — «руки», не «решатель».
При PREFER_EXPERTS_FIRST=true (по умолчанию) в Veronica идут только простые
одношаговые запросы (покажи файлы, выведи список); остальные execution → enhanced,
чтобы Victoria сначала задействовала экспертов (85 в БД).
"""

import os
from typing import Optional

# Ключевые слова по типам (порядок проверки важен)
SIMPLE_CHAT_KEYWORDS = [
    "привет",
    "здравствуй",
    "приветствую",
    "добрый день",
    "добрый вечер",
    "доброе утро",
    "как дела",
    "что нового",
    "расскажи о себе",
    "кто ты",
    "чем занимаешься",
    "спасибо",
    "пожалуйста",
    "пока",
    "до свидания",
    "удачи",
    "хорошего дня",
    "приветствую",
    "здорово",
    "ок",
    "понятно",
    "ясно",
]

# Простые одношаговые запросы — реальная роль Veronica (руки): только показать/вывести/прочитать
VERONICA_SIMPLE_KEYWORDS = [
    "покажи файлы",
    "выведи список файлов",
    "список файлов",
    "покажи список",
    "прочитай файл",
    "покажи файл",
    "содержимое файла",
    "выведи содержимое",
    "сделай скриншот",
    "проверь как выглядит",
    "нажми на",
    "открой страницу",
    "визуальная проверка",
    "проверь ui",
    "проверь ux",
]

VERONICA_KEYWORDS = [
    "выполни",
    "сделай",
    "напиши код",
    "исправь код",
    "исправь",
    "напиши функцию",
    "запусти",
    "протестируй",
    "проверь код",
    "проверь",
    "собери",
    "установи",
    "настрой",
    "подготовь",
    "создай файл",
    "удали файл",
    "переименуй",
    "перемести файл",
    "покажи файлы",
    "выведи список файлов",
]

DEPARTMENT_HEADS_KEYWORDS = [
    "проанализируй",
    "разработай стратегию",
    "оптимизируй",
    "спроектируй",
    "планируй",
    "исследуй",
    "изучи",
    "оцени",
    "предложи решение",
    "найди проблему",
    "сравни",
    "обобщи",
    "систематизируй",
]

# Запросы куратора, которые должны идти в Enhanced (RAG/эталоны), не в Veronica
CURATOR_STANDARD_KEYWORDS = [
    "статус проекта",
    "какой статус",
    "дашборд",
    "что умеешь",
    "что ты умеешь",
    "status project",
    "project status",
    "dashboard",
    "what can you do",
]


# Исполнительные задачи куратора/Victoria: аудит, дашборд, правки — Enhanced/tools, не in-process Swarm LLM
OPERATIONAL_EXECUTION_MARKERS = (
    "аудит",
    "ре-аудит",
    "deep-analysis",
    "deep analysis",
    "дашборд",
    "dashboard",
    "исправ",
    "проверь",
    "sql",
    "миграц",
    "контейнер",
    "quality gate",
    "оркестрац",
    "эксперт",
)

OPERATIONAL_NO_CLARIFY_MARKERS = (
    "без уточнений",
    "не задавай уточняющие",
    "не задавай встречные вопросы",
    "начинай выполнение сразу",
    "сразу выполняй",
)


def is_operational_execution_goal(goal: str) -> bool:
    """
    Задачи с явным исполнением (аудит дашборда, правки, сверка с БД).
    Маршрут: Victoria Enhanced + инструменты; запрет in-process Swarm (3× ai_core).
    """
    if not (goal or "").strip():
        return False
    g = (goal or "").lower().strip()
    if any(m in g for m in OPERATIONAL_NO_CLARIFY_MARKERS) and any(
        m in g for m in OPERATIONAL_EXECUTION_MARKERS
    ):
        return True
    if "критическая задача" in g and any(m in g for m in ("дашборд", "dashboard", "аудит")):
        return True
    if ("deep-analysis" in g or "deep analysis" in g) and "дашборд" in g:
        return True
    return False


FACT_SEEKING_MARKERS = (
    "порт",
    "ports",
    " health",
    "health ",
    "/health",
    "статус проекта",
    "статус по проекту",
    "статус системы",
    "очеред",
    "pending",
    "in_progress",
    "knowledge_nodes",
    "сколько узл",
    "сколько знан",
    "дашборд",
    "dashboard",
    "localhost",
    "8010",
    "8011",
    "3005",
    "8501",
    "по фактам",
    "живьём",
    "живьем",
    "open webui",
    "openwebui",
    "veronica",
    "victoria agent",
    "throughput",
    "пропуск",
    "stale",
    "застряв",
    "error rate",
    "contract",
    "контракт",
    "1h",
    "1ч",
    "24h",
    "24ч",
    "сутк",
    "churn",
    "/metrics",
    "metrics",
    "p95",
    "p50",
    "ttc",
    "time_to_completed",
    "time-to-completed",
    "duration_seconds",
    "inflight",
    "victoria_async",
)


CANONICAL_ATRA_PORTS = (
    ("victoria", "8010"),
    ("veronica", "8011"),
    ("open webui", "3005"),
    ("webui", "3005"),
    ("dashboard", "8501"),
    ("дашборд", "8501"),
)


def grounded_ports_answer(goal: str) -> Optional[str]:
    """Ответ по портам из реестра, не из головы модели."""
    g = (goal or "").lower()
    if "порт" not in g and "port" not in g:
        return None
    found: list[str] = []
    seen: set[str] = set()
    for name, port in CANONICAL_ATRA_PORTS:
        if name in g and port not in seen:
            found.append(port)
            seen.add(port)
    if len(found) >= 2:
        return ", ".join(found)
    if "порта" in g or "порты" in g or "порт " in g:
        return "8010, 8011, 3005"
    return None


def public_task_title(goal: str, limit: int = 255) -> str:
    """Заголовок задачи без префикса метода Cursor."""
    g = (goal or "").strip() or "Task"
    if "МЕТОД CURSOR" in g:
        for sep in ("ЗАДАЧА:", "ТЕКУЩИЙ ЗАПРОС:", "ЗАПРОС ПОЛЬЗОВАТЕЛЯ:"):
            if sep in g:
                g = g.split(sep, 1)[-1].strip()
                break
        else:
            lines = [
                ln
                for ln in g.splitlines()
                if ln.strip()
                and "МЕТОД CURSOR" not in ln
                and not ln.strip().startswith(("1.", "2.", "3.", "4.", "Источник портов"))
            ]
            g = " ".join(lines).strip() or "Task"
    return g[:limit]


def format_live_fact_answer(
    goal: str,
    *,
    health: Optional[str] = None,
    queue: Optional[dict] = None,
    nodes: Optional[int] = None,
    ops: Optional[dict] = None,
    ttc: Optional[dict] = None,
) -> Optional[str]:
    """Короткий ответ из живых probe, без LLM."""
    if not is_fact_seeking_question(goal):
        return None
    g = (goal or "").lower()
    bits: list[str] = []
    ports = grounded_ports_answer(goal)
    if ports:
        bits.append(ports)
    if ("health" in g or "жив" in g) and health:
        bits.append(health)
    if queue is not None and any(x in g for x in ("очеред", "pending", "in_progress")):
        bits.append(
            "pending="
            + str(int(queue.get("pending") or 0))
            + " in_progress="
            + str(int(queue.get("in_progress") or 0))
        )
    if nodes is not None and any(
        x in g for x in ("knowledge_nodes", "сколько узл", "сколько знан")
    ):
        bits.append(str(int(nodes)))
    if ops is not None and any(
        x in g
        for x in (
            "throughput",
            "пропуск",
            "stale",
            "застряв",
            "error rate",
            "ошиб",
            "failed",
            "contract",
            "контракт",
            "24h",
            "24ч",
            "сутк",
            "cancel",
            "cancelled",
            "отмен",
            "churn",
        )
    ):
        parts: list[str] = []
        if "throughput_1h" in ops:
            parts.append("throughput_1h=" + str(int(ops.get("throughput_1h") or 0)))
        if "throughput_24h" in ops:
            parts.append("throughput_24h=" + str(int(ops.get("throughput_24h") or 0)))
        if "stale_in_progress" in ops:
            parts.append("stale_in_progress=" + str(int(ops.get("stale_in_progress") or 0)))
        if "failed_1h" in ops:
            parts.append("failed_1h=" + str(int(ops.get("failed_1h") or 0)))
        if "completed_1h" in ops:
            parts.append("completed_1h=" + str(int(ops.get("completed_1h") or 0)))
        if "error_rate_1h" in ops:
            parts.append("error_rate_1h=" + str(float(ops.get("error_rate_1h") or 0.0)))
        if "contract_enforced_24h" in ops:
            parts.append(
                "contract_enforced_24h="
                + str(int(ops.get("contract_enforced_24h") or 0))
                + "/"
                + str(int(ops.get("completed_24h") or 0))
            )
        if "cancelled_1h_total" in ops:
            parts.append("cancelled_1h_total=" + str(int(ops.get("cancelled_1h_total") or 0)))
        if "cancelled_1h_work" in ops:
            parts.append("cancelled_1h_work=" + str(int(ops.get("cancelled_1h_work") or 0)))
        if "cancelled_1h_policy" in ops:
            parts.append("cancelled_1h_policy=" + str(int(ops.get("cancelled_1h_policy") or 0)))
        if "cancelled_24h_total" in ops:
            parts.append("cancelled_24h_total=" + str(int(ops.get("cancelled_24h_total") or 0)))
        if "cancelled_24h_work" in ops:
            parts.append("cancelled_24h_work=" + str(int(ops.get("cancelled_24h_work") or 0)))
        if "cancelled_24h_policy" in ops:
            parts.append("cancelled_24h_policy=" + str(int(ops.get("cancelled_24h_policy") or 0)))
        if "cancelled_24h_uncategorized" in ops:
            parts.append(
                "cancelled_24h_uncategorized="
                + str(int(ops.get("cancelled_24h_uncategorized") or 0))
            )
        if parts:
            bits.append(" ".join(parts))
    if ttc is not None and any(
        x in g
        for x in (
            "/metrics",
            "metrics",
            "p95",
            "p50",
            "ttc",
            "time_to_completed",
            "time-to-completed",
            "duration_seconds",
            "inflight",
            "victoria_async",
        )
    ):
        bits.append(
            "p50="
            + str(float(ttc.get("p50") or 0.0))
            + " p95="
            + str(float(ttc.get("p95") or 0.0))
            + " samples="
            + str(int(ttc.get("samples") or 0))
            + " inflight_max="
            + str(float(ttc.get("inflight_max") or 0.0))
            + " inflight="
            + str(int(ttc.get("inflight_n") or 0))
        )
    is_status_overview = "статус" in g and any(
        x in g for x in ("проект", "систем", "роя", "swarm")
    )
    if is_status_overview and not bits:
        # Сводный статус: компактный срез живых метрик (эталон status_project).
        healthy = (health or "ok") == "ok" and queue is not None and int(queue.get("pending") or 0) == 0
        bits.append(
            "Статус проекта: активная разработка идёт стабильно, сбоев нет."
            if healthy
            else "Статус проекта: активная разработка, но есть проблемы, требующие внимания."
        )
        if health:
            bits.append(f"health={health}")
        if queue is not None:
            bits.append(
                "pending=" + str(int(queue.get("pending") or 0))
                + " in_progress=" + str(int(queue.get("in_progress") or 0))
            )
        if ops is not None:
            bits.append(
                "failed_1h=" + str(int(ops.get("failed_1h") or 0))
                + " completed_24h=" + str(int(ops.get("completed_24h") or 0))
                + " error_rate_1h=" + str(float(ops.get("error_rate_1h") or 0.0))
            )
        if nodes is not None:
            bits.append("knowledge_nodes=" + str(int(nodes)))
    if not bits:
        return None
    return bits[0] if len(bits) == 1 else " ".join(bits)


def is_fact_seeking_question(goal: str) -> bool:
    """Вопрос, на который нельзя отвечать из головы: порты, очередь, health, живой статус."""
    g = (goal or "").lower().strip()
    if not g:
        return False
    if g in ("кто ты", "кто ты?", "что ты умеешь", "что ты умеешь?"):
        return False

    # Объяснительные/творческие цели — не fact-probe, даже если внутри есть
    # слово-маркер («объясни backpressure в очередях задач» ≠ «сколько в очереди»).
    if any(g.startswith(v) for v in ("объясни", "что такое", "напиши", "найди", "расскажи", "сравни", "проанализируй", "разбери")):
        return False
    
    # Исключаем автоматические задачи (лог сканер, медицинские задачи и т.д.)
    # Эти задачи требуют реальной обработки, а не детерминированного ответа
    automated_prefixes = ["[log_scanner]", "[medic]", "[proactive]", "[feedback]"]
    if any(g.startswith(prefix) for prefix in automated_prefixes):
        return False
    
    # Исключаем задачи которые начинаются с маркера ошибки - это задачи на исправление
    if g.startswith("ошибка") or g.startswith("error") or g.startswith("исправь"):
        return False
    
    # Исключаем задачи с "ошибка" в контексте лог сканера или исправления
    # Если goal содержит "ошибка" и "контейнер" или "исправь" - это задача на исправление
    if "ошибка" in g and ("контейнер" in g or "исправь" in g or "log_scanner" in g):
        return False
    
    return any(m in g for m in FACT_SEEKING_MARKERS)


def is_curator_standard_goal(goal: str) -> bool:
    """
    Запрос из списка кураторских эталонов: статус проекта, что умеешь, дашборд.
    Такие запросы не должны делегироваться в Veronica — только Enhanced (simple + RAG).
    """
    if not (goal or "").strip():
        return False
    g = (goal or "").lower().strip()
    if any(kw in g for kw in CURATOR_STANDARD_KEYWORDS):
        return True
    # «какой статус проекта?», «статус по проекту»
    if "статус" in g and ("проект" in g or "дашборд" in g):
        return True
    if "что" in g and "умеешь" in g:
        return True
    return False


# Категории, где ночные A/B-битвы показали выигрыш консилиума над соло
# (battle_20260922_205549: research 4-1, testing 4-0). Список — env, чтобы
# пополнять по данным новых битв без правки кода.
_CONSILIUM_CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    "research": (
        "объясни",
        "что такое",
        "расскажи",
        "чем отличается",
        "найди в интернете",
        "исследуй",
    ),
    "testing": (
        "тест",
        "чеклист",
        "покрытие",
        "smoke",
        "план проверки",
        "план регресса",
    ),
    "analysis": (
        "проанализируй",
        "разбери",
        "анализ",
    ),
    "security": (
        "безопасность",
        "security",
        "уязвимост",
        "вторжение",
        " prompt injection",
        "hardcoded секрет",
    ),
}


def consilium_categories() -> tuple[str, ...]:
    raw = os.getenv("CONSILIUM_CATEGORIES", "research,testing,analysis,security")
    return tuple(x.strip() for x in raw.split(",") if x.strip() in _CONSILIUM_CATEGORY_PATTERNS)


def is_consilium_winnable_goal(goal: str) -> Optional[str]:
    """Категория, где консилиум (дебат) статистически выигрывает у соло — или None.

    Узкие паттерны: research — объяснительные глаголы в начале цели;
    testing — явные маркеры тест-планирования. Классификация нужна ДО
    стратегической LLM, поэтому только regex/keywords.
    """
    g = (goal or "").lower().strip()
    if not g:
        return None
    enabled = consilium_categories()
    if "research" in enabled:
        research_starters = _CONSILIUM_CATEGORY_PATTERNS["research"]
        if any(g.startswith(v) for v in research_starters) or "найди в интернете" in g:
            return "research"
    if "testing" in enabled:
        testing_markers = _CONSILIUM_CATEGORY_PATTERNS["testing"]
        if any(m in g for m in testing_markers):
            return "testing"
    if "analysis" in enabled:
        analysis_starters = _CONSILIUM_CATEGORY_PATTERNS["analysis"]
        if any(g.startswith(v) for v in analysis_starters) or any(v in g for v in analysis_starters):
            return "analysis"
    if "security" in enabled:
        security_markers = _CONSILIUM_CATEGORY_PATTERNS["security"]
        if any(m in g for m in security_markers):
            return "security"
    return None


def _is_simple_veronica_request(goal: str) -> bool:
    """
    Запрос — одношаговое действие (показать/вывести/прочитать).
    Только такие запросы по задумке идут сразу в Veronica (руки); остальные — в enhanced (эксперты).
    """
    if not goal or len(goal.strip()) > 120:
        return False
    goal_lower = goal.lower().strip()
    if any(kw in goal_lower for kw in VERONICA_SIMPLE_KEYWORDS):
        return True
    # Короткая фраза типа «покажи файлы в src»
    if len(goal_lower) <= 50 and (
        "покажи" in goal_lower or "выведи" in goal_lower or "список" in goal_lower
    ):
        return True
    return False


def detect_task_type(goal: str, context: str = "") -> str:
    """
    Определяет тип задачи для маршрутизации:
    - simple_chat: приветствия, простые вопросы → быстрый путь (agent.run без Enhanced)
    - veronica: только простые одношаговые запросы (покажи файлы, выведи список) при PREFER_EXPERTS_FIRST
    - department_heads: аналитические/стратегические
    - enhanced: сложные задачи, execution через экспертов (по умолчанию для «сделай/напиши код»)
    """
    if not (goal or "").strip():
        return "simple_chat"
    goal_lower = goal.lower().strip()
    prefer_experts_first = os.getenv("PREFER_EXPERTS_FIRST", "true").lower() in ("true", "1", "yes")

    # Кураторские эталоны и operational execution — Enhanced (RAG/tools), не Veronica/Swarm
    if is_curator_standard_goal(goal) or is_operational_execution_goal(goal):
        return "enhanced"

    # Простые одношаговые запросы → Veronica (реальная роль: руки)
    if _is_simple_veronica_request(goal):
        return "veronica"

    # Исполнительные ключевые слова: при PREFER_EXPERTS_FIRST — в enhanced (эксперты первыми)
    for word in VERONICA_KEYWORDS:
        if word in goal_lower:
            if prefer_experts_first:
                return "enhanced"
            return "veronica"
    # Эвристики: код — при PREFER_EXPERTS_FIRST в enhanced
    if _is_code_related(goal_lower):
        return "enhanced" if prefer_experts_first else "veronica"

    # Аналитические
    for word in DEPARTMENT_HEADS_KEYWORDS:
        if word in goal_lower:
            return "department_heads"
    # Очень короткие фразы — чаще всего приветствие
    if len(goal_lower) <= 25 and any(k in goal_lower for k in SIMPLE_CHAT_KEYWORDS):
        return "simple_chat"
    # Явные приветствия
    for word in SIMPLE_CHAT_KEYWORDS:
        if word in goal_lower:
            return "simple_chat"
    # Эвристики: анализ
    if _is_analysis_related(goal_lower):
        return "department_heads"
    return "enhanced"


def _is_code_related(goal: str) -> bool:
    code_indicators = [
        "python",
        "javascript",
        "java",
        "код",
        "функция",
        "класс",
        "метод",
        "библиотека",
        "импорт",
        "компиляция",
        "дебаг",
        "тест",
        "lint",
    ]
    return any(i in goal for i in code_indicators)


def _is_analysis_related(goal: str) -> bool:
    analysis_indicators = [
        "данные",
        "анализ",
        "отчет",
        "отчёт",
        "график",
        "диаграмма",
        "статистика",
        "тренд",
        "паттерн",
        "корреляция",
        "прогноз",
        "рекомендация",
        "метрика",
        "insight",
    ]
    return any(i in goal for i in analysis_indicators)


def should_use_enhanced(goal: str, project_context: Optional[str], use_enhanced_env: bool) -> bool:
    """
    Решает, использовать ли Enhanced для данного запроса.
    Если env USE_VICTORIA_ENHANCED=true, но запрос — simple_chat, возвращаем False
    (быстрый ответ через agent.run без тяжёлого Enhanced).
    Operational/curator execution goals всегда идут в Enhanced (даже если env выключен),
    чтобы не попадать в зависающий in-process Swarm.
    """
    task_type = detect_task_type(goal or "", project_context or "")
    if task_type == "simple_chat":
        return False
    force_operational = os.getenv("VICTORIA_FORCE_ENHANCED_OPERATIONAL", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    if force_operational and (
        is_operational_execution_goal(goal) or is_curator_standard_goal(goal)
    ):
        return True
    if not use_enhanced_env:
        return False
    return True
