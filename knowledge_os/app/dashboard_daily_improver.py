"""
Dashboard Daily Improver — ежедневный анализ и улучшение дашборда экспертами (Singularity 10.0)

Сначала анализирует дашборд (код и паттерны), затем создаёт задачи на улучшение.
Эксперты (Frontend, UX, QA, Performance, Product): ошибки, недочёты, производительность.
Мировые практики: Streamlit best practices, Grafana/McKinsey dashboards.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"
_DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

# Один элемент: (title_short, priority, assignee_hint, description, auto_apply_safe)
# auto_apply_safe: только для низкорисковых механических правок (max_entries)
ChecklistItem = Tuple[str, str, str, str, bool]


def _analyze_dashboard_code() -> List[ChecklistItem]:
    """
    Анализирует код дашборда и возвращает список предложений по улучшению.
    Сканирует app.py на паттерны: кэш без max_entries, запросы без LIMIT/LEFT(content,N),
    отсутствие st.fragment, пустые состояния, дублирование.
    """
    findings: List[ChecklistItem] = []
    app_py = _DASHBOARD_DIR / "app.py"
    if not app_py.exists():
        logger.warning("Dashboard app.py not found at %s", app_py)
        return findings

    try:
        text = app_py.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("Could not read dashboard app.py: %s", e)
        return findings

    # 1) st.cache_data без max_entries — риск неограниченного роста кэша (auto_apply_safe)
    if "st.cache_data" in text and "max_entries" not in text and "max_entries=" not in text:
        findings.append(
            (
                "Проверить max_entries в st.cache_data",
                "medium",
                "Frontend/Performance",
                "DASHBOARD_OPTIMIZATION_PLAN: задать max_entries (например 100) в st.cache_data, иначе кэш растёт без ограничения.",
                True,  # auto_apply_safe — механическая замена
            )
        )

    # 2) Запросы к knowledge_nodes с полным content (без LEFT/substring)
    if "knowledge_nodes" in text and (
        "LEFT(content" not in text
        and "content," in text
        or re.search(r"SELECT\s+[^F]*content\s+FROM\s+.*knowledge_nodes", text, re.I | re.S)
    ):
        if "LEFT(content" not in text and "substring(content" not in text:
            findings.append(
                (
                    "Проверить LEFT(content,N) в запросах к knowledge_nodes",
                    "medium",
                    "Backend",
                    "Избегать загрузки полного content: использовать LEFT(content, N) или substring для больших полей.",
                    False,
                )
            )

    # 3) Lazy load вкладок (st.fragment) — Streamlit best practice
    if "st.tabs" in text and "st.fragment" not in text:
        findings.append(
            (
                "Проверить lazy load вкладок (st.fragment)",
                "low",
                "Frontend",
                "Streamlit best practices: рассмотреть st.fragment для тяжёлых вкладок, чтобы не грузить всё при открытии.",
                False,
            )
        )

    # 4) Пустые состояния: наличие try/except и fallback при пустых данных
    fetch_or_query = "fetch_data" in text or "get_db_connection" in text
    if fetch_or_query:
        if (
            "st.info" not in text
            and "st.warning" not in text
            and "пуст" not in text.lower()
            and "нет дан" not in text.lower()
        ):
            findings.append(
                (
                    "Проверить пустые состояния и fallback при отсутствии данных",
                    "high",
                    "QA",
                    "Ошибки: добавить явные пустые состояния (st.info/st.empty) и fallback при отсутствии данных в запросах.",
                    False,
                )
            )

    # 5) Дублирование метрик: несколько st.metric с похожими названиями
    metric_count = len(re.findall(r"st\.metric\s*\(", text))
    if metric_count > 10:
        findings.append(
            (
                "Проверить дублирование метрик между вкладками",
                "low",
                "Product",
                "Недочёты: много st.metric — проверить дублирование между вкладками и вынести общие в переиспользуемые блоки.",
                False,
            )
        )

    return findings


def _apply_max_entries_patch(app_py_path: Path) -> bool:
    """
    Безопасный патч: добавить max_entries=100 в st.cache_data без max_entries.
    Только для декораторов @st.cache_data и @st.cache_data(...).
    Не трогает st.cache_data.clear().
    Living Organism §3, AUTO_APPLY_DASHBOARD.
    """
    try:
        text = app_py_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("Could not read %s for auto-apply: %s", app_py_path, e)
        return False

    if "max_entries" in text:
        return False  # уже есть

    original = text

    # @st.cache_data без скобок → @st.cache_data(max_entries=100)
    text = re.sub(r"@st\.cache_data\b(?!\()", "@st.cache_data(max_entries=100)", text)

    # @st.cache_data() пустые скобки → @st.cache_data(max_entries=100)
    text = re.sub(r"@st\.cache_data\s*\(\s*\)", "@st.cache_data(max_entries=100)", text)

    # @st.cache_data(...) с аргументами — добавить max_entries перед закрывающей )
    def _add_max_entries(match: re.Match) -> str:
        inner = match.group(1)
        if "max_entries" in inner:
            return match.group(0)
        return f"@st.cache_data({inner}, max_entries=100)"

    text = re.sub(r"@st\.cache_data\s*\(([^)]*)\)", _add_max_entries, text)

    if text != original:
        try:
            app_py_path.write_text(text, encoding="utf-8")
            logger.info("[DASHBOARD_IMPROVER] auto-applied max_entries to %s", app_py_path)
            return True
        except Exception as e:
            logger.warning("Could not write %s after auto-apply: %s", app_py_path, e)
            return False
    return False


def _get_fallback_checklist() -> List[ChecklistItem]:
    """Чеклист по умолчанию, если анализ не вернул предложений."""
    return [
        (
            "Проверить max_entries в st.cache_data",
            "medium",
            "Frontend/Performance",
            "DASHBOARD_OPTIMIZATION_PLAN: max_entries=100",
            True,
        ),
        (
            "Проверить LEFT(content,N) в запросах к knowledge_nodes",
            "medium",
            "Backend",
            "Избегать загрузки полного content",
            False,
        ),
        (
            "Проверить lazy load вкладок (st.fragment)",
            "low",
            "Frontend",
            "Streamlit best practices",
            False,
        ),
        (
            "Проверить пустые состояния и fallback при отсутствии данных",
            "high",
            "QA",
            "Ошибки: пустые состояния",
            False,
        ),
        (
            "Проверить дублирование метрик между вкладками",
            "low",
            "Product",
            "Недочёты: дублирование",
            False,
        ),
    ]


async def _create_dashboard_improvement_tasks(conn, checklist: List[ChecklistItem]) -> int:
    """Создаёт задачи на улучшение дашборда в tasks по переданному чеклисту (из анализа или fallback)."""
    try:
        import asyncpg
    except ImportError:
        return 0

    tasks_created = 0
    if not checklist:
        return 0

    victoria_id = await conn.fetchval(
        "SELECT id FROM experts WHERE name ILIKE $1 LIMIT 1", "Виктория"
    )
    if not victoria_id:
        logger.warning("Expert Victoria not found, skipping dashboard tasks")
        return 0
    domain_id = await conn.fetchval(
        "SELECT id FROM domains WHERE name ILIKE $1 LIMIT 1", "Dashboard"
    )
    if not domain_id:
        await conn.execute(
            "INSERT INTO domains (name, description) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING",
            "Dashboard",
            "Dashboard improvements and analytics",
        )
        domain_id = await conn.fetchval(
            "SELECT id FROM domains WHERE name ILIKE $1 LIMIT 1", "Dashboard"
        )

    for item in checklist:
        title, priority, assignee_hint, description = item[0], item[1], item[2], item[3]
        full_title = f"📊 Дашборд: {title}"
        # Избегаем дублирования: не создаём если такая задача уже есть за последние 24ч
        existing = await conn.fetchval(
            """
            SELECT 1 FROM tasks
            WHERE title = $1 AND created_at > NOW() - INTERVAL '24 hours'
            LIMIT 1
        """,
            full_title,
        )
        if existing:
            continue
        metadata = json.dumps(
            {"source": "dashboard_daily_improver", "assignee_hint": assignee_hint}
        )
        await conn.execute(
            """
            INSERT INTO tasks (title, description, status, priority, creator_expert_id, domain_id, metadata)
            VALUES ($1, $2, 'pending', $3, $4, $5, $6::jsonb)
        """,
            full_title,
            description,
            priority,
            victoria_id,
            domain_id,
            metadata,
        )
        tasks_created += 1

    return tasks_created


async def _log_improvement_to_knowledge(conn, summary: str) -> bool:
    """Сохраняет лог цикла улучшений в knowledge_nodes (domain: Dashboard)."""
    try:
        domain_id = await conn.fetchval(
            "SELECT id FROM domains WHERE name ILIKE $1 LIMIT 1", "Dashboard"
        )
        if not domain_id:
            return False
        metadata = json.dumps(
            {"source": "dashboard_daily_improver", "cycle": datetime.now().isoformat()}
        )
        content_kn = summary[:2000]
        embedding = None
        try:
            from semantic_cache import get_embedding

            embedding = await get_embedding(content_kn[:8000])
        except Exception:
            pass
        if embedding is not None:
            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref, embedding)
                VALUES ($1, $2, $3::jsonb, 0.8, 'dashboard_improvement_cycle', $4::vector)
            """,
                domain_id,
                content_kn,
                metadata,
                str(embedding),
            )
        else:
            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
                VALUES ($1, $2, $3::jsonb, 0.8, 'dashboard_improvement_cycle')
            """,
                domain_id,
                content_kn,
                metadata,
            )
        return True
    except Exception as e:
        logger.warning("Could not log to knowledge_nodes: %s", e)
        return False


async def run_dashboard_improvement_cycle() -> Dict[str, Any]:
    """
    Запускает цикл ежедневного улучшения дашборда.
    1) Анализирует код дашборда (_analyze_dashboard_code).
    2) Если AUTO_APPLY_DASHBOARD=true — для безопасных правок (max_entries) применяет патч.
    3) Создаёт задачи по оставшимся пунктам (критичные или после неуспешного auto-apply).
    4) Логирует результат в knowledge_nodes.
    """
    try:
        import asyncpg
    except ImportError:
        logger.warning("asyncpg not available for dashboard_daily_improver")
        return {"tasks_created": 0, "logged": False, "from_analysis": False, "auto_applied": False}

    auto_applied = False
    try:
        analysis_findings = _analyze_dashboard_code()
        from_analysis = len(analysis_findings) > 0
        if not analysis_findings:
            checklist = _get_fallback_checklist()
            analysis_note = "used fallback checklist (analysis returned empty or file not found)"
        else:
            checklist = analysis_findings
            analysis_note = f"analysis found {len(checklist)} improvement(s)"

        # Auto-apply safe patches (Living Organism §3)
        if os.getenv("AUTO_APPLY_DASHBOARD", "").lower() in ("1", "true", "yes"):
            for item in checklist:
                if (
                    len(item) >= 5
                    and item[4]
                    and item[0] == "Проверить max_entries в st.cache_data"
                ):
                    app_py = _DASHBOARD_DIR / "app.py"
                    if app_py.exists():
                        if _apply_max_entries_patch(app_py):
                            auto_applied = True
                            # Убираем этот пункт из чеклиста — задача не нужна
                            checklist = [
                                c
                                for c in checklist
                                if not (
                                    len(c) >= 5
                                    and c[4]
                                    and c[0] == "Проверить max_entries в st.cache_data"
                                )
                            ]
                        break

        logger.info("[DASHBOARD_IMPROVER] %s", analysis_note)

        conn = await asyncpg.connect(_DB_URL)
        try:
            tasks_created = await _create_dashboard_improvement_tasks(conn, checklist)
            summary = f"Dashboard improvement cycle: {analysis_note}; {tasks_created} tasks created; auto_applied={auto_applied} at {datetime.now().isoformat()}"
            logged = await _log_improvement_to_knowledge(conn, summary)
            logger.info("[DASHBOARD_IMPROVER] %s", summary)
            return {
                "tasks_created": tasks_created,
                "logged": logged,
                "from_analysis": from_analysis,
                "auto_applied": auto_applied,
            }
        finally:
            await conn.close()
    except Exception as e:
        logger.error("dashboard_daily_improver failed: %s", e, exc_info=True)
        return {"tasks_created": 0, "logged": False, "from_analysis": False, "auto_applied": False}
