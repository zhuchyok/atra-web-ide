"""
Tasks Tab Module - Modular interface for task management.
Follows Singularity 10.0 microservices standards.
"""

import html
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

# Импортируем зависимости из shared/database_service.py (глобально для всех функций)
try:
    from database_service import (
        fetch_data,
        fetch_data_tasks,
        get_db_connection,
        get_project_slugs,
        run_query,
    )
except ImportError:
    # Если запуск идет внутри Docker или структура путей иная
    try:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from database_service import (
            fetch_data,
            fetch_data_tasks,
            get_db_connection,
            get_project_slugs,
            run_query,
        )
    except ImportError:
        logging.error("Could not import DB utilities from database_service.py")

from components.charts import render_task_status_chart
from components.metrics import render_metric_card

logger = logging.getLogger(__name__)


def format_msk(dt):
    """Форматирует datetime в московское время (UTC+3)."""
    if dt is None:
        return "N/A"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    msk_dt = dt.astimezone(timezone(timedelta(hours=3)))
    return msk_dt.strftime("%d.%m.%Y %H:%M")


def render_tasks_tab():
    """Основная функция рендеринга вкладки задач."""
    st.header("🛠️ Управление Задачами")

    time_range = st.session_state.get("global_time_range", "Последние 7 дней")
    st.caption(f"📅 Фильтр времени: **{time_range}** (настройте в боковой панели)")

    tabs = st.tabs(["📋 Список задач", "➕ Поставить задачу", "📊 Аналитика"])

    with tabs[0]:
        _render_tasks_list(time_range)

    with tabs[1]:
        _render_put_task()

    with tabs[2]:
        _render_tasks_analytics(time_range)


def _render_tasks_list(time_range):
    st.subheader("🛠️ Автономные Задачи и Оркестрация")
    st.caption(
        "**Почему бывает «с экспертом» и «без»:** Victoria пишет метрический трек "
        "`orchestration_tracking` (без assignee) и отдельно делегирует эксперту "
        "(`victoria_monster_delegation`). Треки по умолчанию скрыты. "
        "**DEGRADED** = soft rule-fallback без LLM (не авария контейнера)."
    )

    from database_service import get_time_filter

    t_filter = get_time_filter(time_range, "created_at")

    # Статистика задач вверху (кэш 15 сек — чтобы увидеть рост «Завершено», нажмите «Обновить»)
    row_cap, row_btn = st.columns([4, 1])
    with row_cap:
        st.caption(
            "Данные кэшируются на 15 сек; страница сама не перезагружается. Нажмите «Обновить» для актуальных цифр."
        )
    with row_btn:
        if st.button(
            "🔄 Обновить",
            key="refresh_tasks_stats",
            help="Обновить счётчики (Всего, Завершено, В работе, Ожидает)",
        ):
            st.session_state["tasks_refresh_ts"] = time.time()
            st.cache_data.clear()
            st.rerun()

    # Принудительный сброс кэша: разный _cache_bust даёт новый запрос к БД после «Обновить»
    _cache_bust = st.session_state.get("tasks_refresh_ts", 0)
    # Exclude Victoria orchestration_tracking rows from work-queue KPIs (metrics-only twins).
    _work_queue = "AND COALESCE(metadata->>'source', '') <> 'orchestration_tracking'"
    task_overview = fetch_data_tasks(
        f"""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'failed') as failed,
            COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
            COUNT(*) FILTER (
                WHERE status = 'cancelled'
                  AND (
                    COALESCE(result, '') LIKE '%%[DEGRADED_RULE_FALLBACK]%%'
                    OR COALESCE(metadata->>'quality_degraded', '') IN ('true', 'True', '1')
                    OR COALESCE(metadata->>'completion_kind', '') = 'rule_fallback_degraded'
                  )
            ) as degraded,
            CASE
                WHEN COUNT(*) FILTER (
                    WHERE status = 'completed'
                      AND COALESCE(completed_at, updated_at) IS NOT NULL
                      AND created_at IS NOT NULL
                ) > 0
                THEN ROUND(
                    AVG(EXTRACT(EPOCH FROM (COALESCE(completed_at, updated_at) - created_at)))
                    FILTER (
                        WHERE status = 'completed'
                          AND COALESCE(completed_at, updated_at) IS NOT NULL
                          AND created_at IS NOT NULL
                    ) / 3600,
                    1
                )
                ELSE 0
            END as avg_hours
        FROM tasks
        WHERE {t_filter}
          {_work_queue}
    """,
        _cache_bust=_cache_bust,
    )

    recent_done = fetch_data_tasks(
        """
        SELECT COUNT(*) as cnt, MAX(updated_at) as last_at
        FROM tasks WHERE status = 'completed' AND updated_at > NOW() - INTERVAL '15 minutes'
    """,
        _cache_bust=_cache_bust,
    )

    if task_overview and task_overview[0]:
        to = task_overview[0]
        if to["total"] == 0:
            st.markdown(
                """
                <div class="empty-state">
                    <div class="empty-icon">📋</div>
                    <div class="empty-title">Задач пока нет</div>
                    <div class="empty-hint">Создайте задачу через «Поставить задачу», «Разведка», «Маркетинг» или «Аудит Кода». Убедитесь, что дашборд и воркер используют один DATABASE_URL.</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

        col_stat1, col_stat2, col_stat3, col_stat4, col_stat5 = st.columns(5)
        with col_stat1:
            render_metric_card("Всего", f"{to['total']:,}")
        with col_stat2:
            completion_rate = (to["completed"] / to["total"] * 100) if to["total"] > 0 else 0.0
            render_metric_card(
                "✅ Завершено", f"{to['completed']:,}", delta=f"{completion_rate:.1f}%"
            )
        with col_stat3:
            render_metric_card("🔄 В работе", f"{to['in_progress']:,}")
            if to["in_progress"] and to["in_progress"] > 15:
                st.caption("Ожидаемый макс: **15** на один воркер.")
        with col_stat4:
            render_metric_card("⏳ Ожидает", f"{to['pending']:,}")
        with col_stat5:
            render_metric_card(
                "⏱️ Среднее время", f"{to['avg_hours']:.1f}ч" if to["avg_hours"] else "N/A"
            )

        failed_n = to.get("failed") or 0
        cancelled_n = to.get("cancelled") or 0
        degraded_n = to.get("degraded") or 0
        if failed_n or cancelled_n:
            st.caption(
                f"❌ failed: **{failed_n}** · 🚫 cancelled: **{cancelled_n}** "
                f"(из них ⚠️ DEGRADED rule-fallback: **{degraded_n}** — не путать с аварией)"
            )

        if recent_done and recent_done[0]:
            rd = recent_done[0]
            cnt15 = rd.get("cnt") or 0
            last_at = rd.get("last_at")
            last_str = ""
            if last_at:
                try:
                    if hasattr(last_at, "strftime"):
                        last_str = last_at.strftime("%H:%M") if last_at else ""
                    else:
                        last_str = str(last_at)[:16]
                except Exception:
                    last_str = str(last_at)[:16]
            st.caption(
                f"📈 За последние 15 мин завершено: **{cnt15}** задач. Последнее завершение: {last_str or '—'}."
            )

    st.markdown("---")

    # Фильтры
    project_slugs = get_project_slugs()
    col_filter1, col_filter2, col_filter3, col_action = st.columns([2, 2, 2, 1])
    with col_filter1:
        status_filter = st.selectbox(
            "Фильтр по статусу",
            [
                "Все",
                "pending",
                "in_progress",
                "completed",
                "cancelled",
                "degraded (rule-fallback)",
                "failed",
                "Ручная проверка (deferred)",
            ],
            key="task_status_filter",
        )
    with col_filter2:
        experts_list = fetch_data_tasks("SELECT DISTINCT name FROM experts ORDER BY name")
        expert_names = [e["name"] for e in experts_list] if experts_list else []
        expert_filter = st.selectbox(
            "Фильтр по эксперту", ["Все"] + expert_names, key="task_expert_filter"
        )
    with col_filter3:
        project_filter = st.selectbox("Проект", ["Все"] + project_slugs, key="task_project_filter")
    with col_action:
        if st.button("🔄 Обновить", key="refresh_tasks", width="stretch"):
            st.cache_data.clear()
            st.rerun()

    # Поиск
    search_query = st.text_input(
        "🔍 Поиск по задачам", placeholder="Введите ключевые слова...", key="task_search"
    )

    # Запрос данных
    from database_service import get_time_filter

    t_filter = get_time_filter(time_range, "t.created_at")

    query_parts = [
        f"SELECT t.id, t.title, t.description, t.status, t.result, t.created_at, t.updated_at, COALESCE(e.name, 'Не назначен') as assignee, COALESCE(e.department, 'N/A') as department, t.metadata, t.project_context FROM tasks t LEFT JOIN experts e ON t.assignee_expert_id = e.id WHERE {t_filter}"
    ]
    query_params = []

    show_tracking = st.checkbox(
        "Показать метрические треки Victoria (orchestration_tracking)",
        value=False,
        key="tasks_show_orchestration_tracking",
        help="Служебные строки A/B — не рабочие задачи. По умолчанию скрыты, чтобы не путать с «Делегировано: Expert».",
    )
    if not show_tracking:
        query_parts.append("AND COALESCE(t.metadata->>'source', '') <> 'orchestration_tracking'")

    if status_filter == "Ручная проверка (deferred)":
        query_parts.append(
            "AND t.status = 'completed' AND t.metadata->>'deferred_to_human' = 'true'"
        )
    elif status_filter == "degraded (rule-fallback)":
        query_parts.append(
            """
            AND t.status = 'cancelled'
            AND (
                COALESCE(t.result, '') LIKE %s
                OR COALESCE(t.metadata->>'quality_degraded', '') IN ('true', 'True', '1')
                OR COALESCE(t.metadata->>'completion_kind', '') = 'rule_fallback_degraded'
            )
            """
        )
        query_params.append("%[DEGRADED_RULE_FALLBACK]%")
    elif status_filter != "Все":
        query_parts.append("AND t.status = %s")
        query_params.append(status_filter)

    if expert_filter != "Все":
        query_parts.append("AND COALESCE(e.name, 'Не назначен') = %s")
        query_params.append(expert_filter)

    if project_filter != "Все":
        query_parts.append("AND t.project_context = %s")
        query_params.append(project_filter)

    if search_query:
        query_parts.append("AND (t.title ILIKE %s OR t.description ILIKE %s)")
        search_pattern = f"%{search_query}%"
        query_params.extend([search_pattern, search_pattern])

    order_col = (
        "t.updated_at"
        if status_filter in ("completed", "Ручная проверка (deferred)")
        else "t.created_at"
    )
    query_parts.append(f"ORDER BY {order_col} DESC LIMIT 100")

    tasks = fetch_data_tasks(" ".join(query_parts), tuple(query_params) if query_params else None)

    if tasks:
        df_tasks = pd.DataFrame(tasks)
        col_chart, col_list = st.columns([1, 2])
        with col_chart:
            render_task_status_chart(df_tasks)

        # --- ATRA CANVAS: Интеграция обсуждений из нескольких источников ---
        st.markdown("### 💬 Активные обсуждения и советы")
        try:
            recent_comments = fetch_data_tasks("""
                SELECT *
                FROM (
                    SELECT
                        'file_comment'::text AS source,
                        c.comment_text AS comment_text,
                        COALESCE(c.expert_name, e.name, 'Эксперт') AS expert_name,
                        COALESCE(e.role, 'Expert') AS role,
                        COALESCE(c.file_path, '—') AS location,
                        c.created_at
                    FROM (
                        SELECT *
                        FROM file_comments
                        WHERE status = 'active'
                        ORDER BY created_at DESC
                        LIMIT 5
                    ) c
                    LEFT JOIN experts e ON c.expert_id = e.id

                    UNION ALL

                    SELECT
                        'board'::text AS source,
                        LEFT(COALESCE(b.directive_text, ''), 700) AS comment_text,
                        'Совет Директоров' AS expert_name,
                        'Board' AS role,
                        'board_decisions' AS location,
                        b.created_at
                    FROM (
                        SELECT directive_text, created_at
                        FROM board_decisions
                        ORDER BY created_at DESC
                        LIMIT 3
                    ) b

                    UNION ALL

                    SELECT
                        'discussion'::text AS source,
                        LEFT(COALESCE(d.consensus_summary, ''), 700) AS comment_text,
                        'Экспертная дискуссия' AS expert_name,
                        'Discussion' AS role,
                        COALESCE(d.topic, 'expert_discussions') AS location,
                        d.created_at
                    FROM (
                        SELECT topic, consensus_summary, created_at
                        FROM expert_discussions
                        WHERE COALESCE(consensus_summary, '') <> ''
                        ORDER BY created_at DESC
                        LIMIT 3
                    ) d
                ) all_comments
                ORDER BY created_at DESC
                LIMIT 10
            """)
            if recent_comments:
                now_utc = datetime.now(timezone.utc)
                all_stale = True
                for comm in recent_comments:
                    created_at = comm.get("created_at")
                    age_hours = None
                    if created_at:
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)
                        age_hours = (now_utc - created_at).total_seconds() / 3600
                    is_stale = age_hours is None or age_hours > 24
                    all_stale = all_stale and is_stale
                    stale_badge = "🔴 устарело >24ч" if is_stale else f"🟢 свежо {int(age_hours)}ч"
                    source_label = {
                        "file_comment": "Комментарий",
                        "board": "Совет",
                        "discussion": "Дискуссия",
                    }.get(comm.get("source"), "Сигнал")

                    st.markdown(
                        f"""
                        <div style="background: rgba(88, 166, 255, 0.05); border-left: 3px solid var(--dash-accent); padding: 10px; border-radius: 4px; margin-bottom: 8px;">
                            <div style="font-size: 11px; color: var(--dash-text-muted);">
                                <b>{source_label}</b> · <b>{comm["expert_name"]}</b> ({comm["role"] or "Expert"}) · {comm["location"]} · {stale_badge}
                            </div>
                            <div style="font-size: 13px; color: var(--dash-text); margin-top: 4px;">{comm["comment_text"]}</div>
                        </div>
                    """,
                        unsafe_allow_html=True,
                    )
                if all_stale:
                    st.warning(
                        "Все обсуждения/советы в этом блоке старше 24 часов. "
                        "Интерфейс работает, но источник данных давно не обновлялся."
                    )
            else:
                st.caption(
                    "Нет обсуждений: file_comments, board_decisions и expert_discussions пусты."
                )
        except Exception as e:
            logger.debug(f"Comments fetch failed: {e}")

        for task in tasks:
            _render_task_card(task)
    else:
        st.info("Задач не найдено.")


def _is_degraded_cancelled(task) -> bool:
    """Soft rule-fallback: status cancelled but work often done (not a hard failure)."""
    if (task.get("status") or "") != "cancelled":
        return False
    result = task.get("result") or ""
    if "[DEGRADED_RULE_FALLBACK]" in result:
        return True
    meta = task.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except (json.JSONDecodeError, TypeError):
            meta = {}
    if not isinstance(meta, dict):
        return False
    return bool(
        meta.get("quality_degraded")
        or meta.get("completion_kind") == "rule_fallback_degraded"
        or meta.get("llm_unavailable_fallback")
    )


def _render_task_card(task):
    """Render a single task card."""
    degraded = _is_degraded_cancelled(task)
    status_key = "degraded" if degraded else (task.get("status") or "")

    status_color = {
        "pending": "#f38ba8",
        "completed": "#238636",
        "in_progress": "#fab387",
        "failed": "#da3633",
        "cancelled": "#8b949e",
        "degraded": "#d29922",
    }.get(status_key, "#8b949e")

    status_icon = {
        "pending": "⏳",
        "completed": "✅",
        "in_progress": "🔄",
        "failed": "❌",
        "cancelled": "🚫",
        "degraded": "⚠️",
    }.get(status_key, "❓")

    status_label = "DEGRADED" if degraded else (task.get("status") or "unknown").upper()
    created_date = format_msk(task.get("created_at"))
    title_safe = html.escape(str(task.get("title") or ""))
    assignee_safe = html.escape(str(task.get("assignee") or "Не назначен"))
    dept_safe = html.escape(str(task.get("department") or "N/A"))
    desc_safe = html.escape((task.get("description") or "")[:300])
    result_preview = (task.get("result") or "").replace("[DEGRADED_RULE_FALLBACK]", "").strip()
    result_safe = html.escape(result_preview[:180])
    if len(result_preview) > 180:
        result_safe += "…"
    result_snip = (
        f'<div class="task-card-meta" style="margin-top:8px;color:#8b949e;">'
        f"Результат: {result_safe}"
        f"</div>"
        if result_preview
        else ""
    )
    degraded_hint = (
        '<div class="task-card-meta" style="margin-top:6px;color:#d29922;">'
        "Rule-fallback (не KPI-успех эксперта; ответ мог быть получен без LLM)"
        "</div>"
        if degraded
        else ""
    )

    st.markdown(
        f"""
        <div style="background: linear-gradient(145deg, #11111b, #0d1117); border: 1px solid {status_color}; padding: 18px; border-radius: 12px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                <div style="flex: 1;">
                    <div class="task-card-title" style="color: #cdd6f4; margin-bottom: 6px;">{status_icon} {title_safe}</div>
                    <div class="task-card-meta">
                        👤 {assignee_safe} | 📁 {dept_safe} | 📅 {html.escape(created_date)}
                    </div>
                </div>
                <span class="task-card-meta" style="color: {status_color}; font-weight: 800; padding: 4px 12px; background: rgba(88, 166, 255, 0.1); border-radius: 12px;">{html.escape(status_label)}</span>
            </div>
            <div class="task-card-desc" style="color: var(--dash-text); margin-top: 10px;">{desc_safe}...</div>
            {degraded_hint}
            {result_snip}
        </div>
    """,
        unsafe_allow_html=True,
    )


def _render_put_task():
    """Render the 'Put Task' interface."""
    st.subheader("➕ Поставить новую задачу")
    with st.form("put_task_form"):
        title = st.text_input("Название задачи", placeholder="Например: Проверить логи сервера")
        description = st.text_area(
            "Описание задачи", placeholder="Детальное описание того, что нужно сделать..."
        )

        col1, col2 = st.columns(2)
        with col1:
            priority = st.selectbox("Приоритет", ["low", "medium", "high", "urgent"], index=1)
        with col2:
            experts_list = fetch_data("SELECT id, name FROM experts ORDER BY name")
            expert_names = {e["name"]: e["id"] for e in experts_list} if experts_list else {}
            assignee = st.selectbox(
                "Исполнитель (необязательно)", ["Автоматически"] + list(expert_names.keys())
            )

        project_slugs = get_project_slugs()
        project_ctx = st.selectbox("Проект", project_slugs if project_slugs else ["atra-web-ide"])

        submitted = st.form_submit_button("🚀 Создать задачу")
        if submitted:
            if not title or not description:
                st.error("Название и описание обязательны")
            else:
                assignee_id = expert_names.get(assignee) if assignee != "Автоматически" else None
                metadata = {"source": "dashboard_submit"}

                success = run_query(
                    """
                    INSERT INTO tasks (title, description, status, priority, assignee_expert_id, metadata, project_context)
                    VALUES (%s, %s, 'pending', %s, %s, %s, %s)
                """,
                    (title, description, priority, assignee_id, json.dumps(metadata), project_ctx),
                )

                if success:
                    st.success("✅ Задача успешно создана!")
                    st.cache_data.clear()
                else:
                    st.error("❌ Ошибка при создании задачи")


def _render_tasks_analytics(time_range):
    """Дополнительная аналитика задач и SLA."""
    st.subheader("📊 Аналитика производительности и SLA")

    from database_service import get_time_filter

    t_filter = get_time_filter(time_range, "t.created_at")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### ⏱️ Мониторинг SLA (Среднее время)")
        try:
            sla_data = fetch_data(f"""
                SELECT
                    COALESCE(e.name, 'Не назначен') as name,
                    AVG(EXTRACT(EPOCH FROM (COALESCE(t.completed_at, t.updated_at) - t.created_at))) as avg_time_sec,
                    COUNT(t.id) as total_tasks
                FROM tasks t
                LEFT JOIN experts e ON t.assignee_expert_id = e.id
                WHERE t.status = 'completed'
                  AND COALESCE(t.completed_at, t.updated_at) IS NOT NULL
                  AND {t_filter}
                GROUP BY COALESCE(e.name, 'Не назначен')
                ORDER BY avg_time_sec ASC
            """)
            if sla_data:
                df_sla = pd.DataFrame(sla_data)
                # Явное преобразование в числовой тип для Plotly/Streamlit
                df_sla["avg_time_min"] = (
                    pd.to_numeric(df_sla["avg_time_sec"], errors="coerce").fillna(0) / 60
                )
                df_sla["avg_time_min"] = df_sla["avg_time_min"].round(1)
                st.bar_chart(df_sla.set_index("name")["avg_time_min"])
            else:
                st.info("Недостаточно данных для расчета SLA.")
        except Exception as e:
            st.error(f"Ошибка SLA: {e}")

    with col2:
        st.markdown("### 🏆 Нагрузка по экспертам")
        try:
            data = fetch_data(f"""
                SELECT COALESCE(e.name, 'Не назначен') as expert, COUNT(t.id) as task_count
                FROM tasks t
                LEFT JOIN experts e ON t.assignee_expert_id = e.id
                WHERE {t_filter}
                GROUP BY COALESCE(e.name, 'Не назначен')
                ORDER BY task_count DESC
            """)
            if data:
                df = pd.DataFrame(data)
                fig = px.bar(
                    df,
                    x="expert",
                    y="task_count",
                    title="Задачи по экспертам",
                    color_discrete_sequence=["#58a6ff"],
                )
                st.plotly_chart(fig, width="stretch")
        except Exception as e:
            st.error(f"Ошибка аналитики: {e}")
