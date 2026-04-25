"""
Tasks Tab Module - Modular interface for task management.
Follows Singularity 10.0 microservices standards.
"""

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
    task_overview = fetch_data_tasks(
        f"""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'failed') as failed,
            CASE
                WHEN COUNT(*) FILTER (WHERE updated_at IS NOT NULL AND created_at IS NOT NULL) > 0
                THEN ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) FILTER (WHERE updated_at IS NOT NULL AND created_at IS NOT NULL) / 3600, 1)
                ELSE 0
            END as avg_hours
        FROM tasks
        WHERE {t_filter}
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
        if st.button("🔄 Обновить", key="refresh_tasks", use_container_width=True):
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

    if status_filter == "Ручная проверка (deferred)":
        query_parts.append(
            "AND t.status = 'completed' AND t.metadata->>'deferred_to_human' = 'true'"
        )
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

        # --- ATRA CANVAS: Интеграция комментариев экспертов ---
        st.markdown("### 💬 Активные обсуждения и советы")
        try:
            recent_comments = fetch_data_tasks("""
                SELECT c.comment_text, c.expert_name, c.file_path, c.created_at, e.role
                FROM file_comments c
                LEFT JOIN experts e ON c.expert_id = e.id
                WHERE c.status = 'active'
                ORDER BY c.created_at DESC
                LIMIT 5
            """)
            if recent_comments:
                for comm in recent_comments:
                    st.markdown(
                        f"""
                        <div style="background: rgba(88, 166, 255, 0.05); border-left: 3px solid var(--dash-accent); padding: 10px; border-radius: 4px; margin-bottom: 8px;">
                            <div style="font-size: 11px; color: var(--dash-text-muted);">
                                <b>{comm["expert_name"]}</b> ({comm["role"] or "Expert"}) · {comm["file_path"]}
                            </div>
                            <div style="font-size: 13px; color: var(--dash-text); margin-top: 4px;">{comm["comment_text"]}</div>
                        </div>
                    """,
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Нет активных комментариев в коде.")
        except Exception as e:
            logger.debug(f"Comments fetch failed: {e}")

        for task in tasks:
            _render_task_card(task)
    else:
        st.info("Задач не найдено.")


def _render_task_card(task):
    """Render a single task card."""
    status_color = {
        "pending": "#f38ba8",
        "completed": "#238636",
        "in_progress": "#fab387",
        "failed": "#da3633",
        "cancelled": "#8b949e",
    }.get(task["status"], "#8b949e")

    status_icon = {
        "pending": "⏳",
        "completed": "✅",
        "in_progress": "🔄",
        "failed": "❌",
        "cancelled": "🚫",
    }.get(task["status"], "❓")

    created_date = format_msk(task.get("created_at"))

    st.markdown(
        f"""
        <div style="background: linear-gradient(145deg, #11111b, #0d1117); border: 1px solid {status_color}; padding: 18px; border-radius: 12px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                <div style="flex: 1;">
                    <div class="task-card-title" style="color: #cdd6f4; margin-bottom: 6px;">{status_icon} {task["title"]}</div>
                    <div class="task-card-meta">
                        👤 {task["assignee"]} | 📁 {task["department"]} | 📅 {created_date}
                    </div>
                </div>
                <span class="task-card-meta" style="color: {status_color}; font-weight: 800; padding: 4px 12px; background: rgba(88, 166, 255, 0.1); border-radius: 12px;">{task["status"].upper()}</span>
            </div>
            <div class="task-card-desc" style="color: var(--dash-text); margin-top: 10px;">{(task.get("description") or "")[:300]}...</div>
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

        submitted = st.form_submit_state = st.form_submit_button("🚀 Создать задачу")
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
                    e.name,
                    AVG(EXTRACT(EPOCH FROM (t.completed_at - t.created_at))) as avg_time_sec,
                    COUNT(t.id) as total_tasks
                FROM experts e
                JOIN tasks t ON t.assignee_expert_id = e.id
                WHERE t.status = 'completed' AND t.completed_at IS NOT NULL AND {t_filter}
                GROUP BY e.id, e.name
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
                SELECT e.name as expert, COUNT(t.id) as task_count
                FROM tasks t
                JOIN experts e ON t.assignee_expert_id = e.id
                WHERE {t_filter}
                GROUP BY e.name
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
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Ошибка аналитики: {e}")
