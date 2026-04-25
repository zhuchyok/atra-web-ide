import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import streamlit as st
from database_service import fetch_data


def format_msk(dt):
    """Форматирует datetime в московское время (UTC+3)."""
    if dt is None:
        return "N/A"
    # Если dt naive (без tz), считаем что это UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    msk_dt = dt.astimezone(timezone(timedelta(hours=3)))
    return msk_dt.strftime("%d.%m.%Y %H:%M")


def render_strategy_tab():
    """Вкладка Стратегия и эксперты."""
    
    time_range = st.session_state.get("global_time_range", "Последние 7 дней")
    st.caption(f"📅 Фильтр времени: **{time_range}**")

    tabs_strategy = st.tabs(
        [
            "💰 Финансы и ROI",
            "🏛️ Структура и Лидеры",
            "🎯 Стратегия OKR",
            "📜 Решения Совета",
            "🚀 AOI Автономность",
        ]
    )

    with tabs_strategy[0]:
        render_finance_and_roi()
    with tabs_strategy[1]:
        render_structure()
    with tabs_strategy[2]:
        render_okr()
    with tabs_strategy[3]:
        render_board_decisions()
    with tabs_strategy[4]:
        render_aoi_status()


def render_aoi_status():
    """📊 Статус Автономной Оркестрации (AOI)."""
    st.subheader("🚀 Автономная Оркестрация Задач (AOI)")

    # Получаем последние инсайты AOI
    aoi_data = fetch_data("""
        SELECT content, created_at
        FROM knowledge_nodes
        WHERE metadata->>'type' = 'aoi_optimization'
        ORDER BY created_at DESC LIMIT 5
    """)

    if aoi_data:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.success("AOI Система: АКТИВНА")
            st.metric("Последний цикл", format_msk(aoi_data[0]["created_at"]).split()[-1])

            # [AUTO-IMPL] Статистика автономных внедрений
            auto_impl_count = fetch_data(
                "SELECT COUNT(*) FROM tasks WHERE metadata->>'auto_impl' = 'true'"
            )
            if auto_impl_count:
                st.metric("Авто-внедрений", auto_impl_count[0]["count"])
        with c2:
            for entry in aoi_data:
                st.caption(f"⏱️ {format_msk(entry['created_at']).split()[-1]} — {entry['content']}")
    else:
        st.warning("AOI Система: Ожидание первого цикла...")


def render_finance_and_roi():
    """💰 Финансы и ROI знаний."""
    st.subheader("📈 Финансовый Учет Интеллекта (Knowledge P&L)")
    
    time_range = st.session_state.get("global_time_range", "Последние 7 дней")
    from database_service import get_time_filter
    t_filter = get_time_filter(time_range, "created_at")

    # Метрики ликвидности (всегда) и экспертов (если есть колонки virtual_budget, performance_score)
    results = fetch_data(f"""
        SELECT
            (SELECT SUM(usage_count * confidence_score) FROM knowledge_nodes WHERE {t_filter}) as total_liquidity,
            (SELECT COUNT(*) FROM knowledge_nodes WHERE usage_count > 0 AND {t_filter}) as active_nodes
    """)
    total_budget = None
    avg_performance = None
    expert_stats = fetch_data(
        "SELECT SUM(virtual_budget) as total_budget, AVG(performance_score) as avg_performance FROM experts"
    )
    if expert_stats and expert_stats[0]:
        total_budget = expert_stats[0].get("total_budget")
        avg_performance = expert_stats[0].get("avg_performance")

    if results and results[0]:
        r = results[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "💎 Ликвидность", f"{r['total_liquidity']:.1f}" if r.get("total_liquidity") else "0"
        )
        c2.metric("✅ Активных узлов", f"{r['active_nodes']:,}" if r.get("active_nodes") else "0")
        c3.metric(
            "💵 Общий бюджет",
            f"${total_budget:.0f}" if total_budget is not None else "N/A (миграция)",
        )
        c4.metric(
            "⭐ Производительность",
            f"{avg_performance:.2f}" if avg_performance is not None else "N/A (миграция)",
        )

    st.markdown("---")

    # ROI Визуализация
    roi_data = fetch_data("""
        SELECT d.name as domain, SUM(k.usage_count * k.confidence_score) as liquidity_score
        FROM knowledge_nodes k JOIN domains d ON k.domain_id = d.id
        WHERE k.usage_count > 0 GROUP BY d.name ORDER BY liquidity_score DESC LIMIT 10
    """)

    if roi_data:
        df_roi = pd.DataFrame(roi_data)
        fig_roi = px.bar(
            df_roi,
            x="domain",
            y="liquidity_score",
            color="liquidity_score",
            title="Топ доменов по ROI знаний",
            template="plotly_dark",
            color_continuous_scale="Viridis",
        )
        st.plotly_chart(fig_roi, use_container_width=True)


def render_structure():
    """🏛️ Рейтинг экспертов и структура."""
    st.subheader("🏛️ Рейтинг Экспертов и Лидеры")

    leaderboard = fetch_data("""
        SELECT e.id, e.name, e.department, e.role, e.version,
               COUNT(k.id) as nodes_count, SUM(k.usage_count) as total_usage,
               AVG(k.confidence_score) as avg_confidence, COUNT(t.id) as tasks_count,
               COUNT(t.id) FILTER (WHERE t.status = 'completed') as tasks_completed
        FROM experts e
        LEFT JOIN knowledge_nodes k ON (k.metadata->>'expert' = e.name OR k.metadata->>'expert_name' = e.name)
        LEFT JOIN tasks t ON t.assignee_expert_id = e.id
        GROUP BY e.id, e.name, e.department, e.role, e.version
        ORDER BY total_usage DESC NULLS LAST LIMIT 10
    """)

    if leaderboard:
        # Секция эволюции (прокачки)
        st.markdown("### 🧬 Эволюция и Управление ДНК")

        expert_names = [e["name"] for e in leaderboard]
        selected_expert = st.selectbox("Выберите эксперта для настройки", expert_names)
        exp_data = next(e for e in leaderboard if e["name"] == selected_expert)

        # --- Редактор Эксперта (DNA Editor) ---
        with st.expander(f"🛠️ Настройка личности: {selected_expert}", expanded=False):
            new_role = st.text_input("Роль", value=exp_data["role"])
            new_dept = st.text_input("Департамент", value=exp_data["department"])

            # Получаем полный системный промпт из БД
            full_expert = fetch_data(
                f"SELECT system_prompt FROM experts WHERE id = '{exp_data['id']}'"
            )
            current_prompt = full_expert[0]["system_prompt"] if full_expert else ""

            new_prompt = st.text_area("Системный промпт (ДНК)", value=current_prompt, height=300)

            if st.button(f"💾 Сохранить изменения для {selected_expert}"):
                import requests

                try:
                    api_url = "http://knowledge_rest:8002/api/experts/update"
                    payload = {
                        "expert_id": str(exp_data["id"]),
                        "system_prompt": new_prompt,
                        "role": new_role,
                        "department": new_dept,
                    }
                    resp = requests.post(api_url, json=payload, timeout=10)
                    if resp.status_code == 200:
                        st.success(f"✅ ДНК {selected_expert} успешно обновлена!")
                        st.rerun()
                    else:
                        st.error(f"❌ Ошибка сохранения: {resp.text}")
                except Exception as e:
                    st.error(f"❌ Ошибка связи с API: {e}")

        # --- Управление Скиллами (Skill Hub) ---
        with st.expander("🎓 Библиотека Скиллов (Skill Hub)", expanded=False):
            try:
                import requests

                skills_resp = requests.get(
                    "http://knowledge_rest:8002/api/experts/skills", timeout=5
                )
                if skills_resp.status_code == 200:
                    all_skills = skills_resp.json()
                    for skill in all_skills:
                        col_s1, col_s2 = st.columns([3, 1])
                        with col_s1:
                            st.markdown(f"**{skill['name']}**")
                            st.caption(skill["description"])
                        with col_s2:
                            if st.button("Применить", key=f"add_skill_{skill['name']}"):
                                st.info(
                                    f"Скилл {skill['name']} будет интегрирован в промпт {selected_expert} при следующей мутации."
                                )
                else:
                    st.warning("Не удалось загрузить список скиллов.")
            except Exception:
                st.error("API скиллов недоступно.")

        # --- Статус Эволюции ---
        st.markdown("---")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric("Версия", f"v{exp_data['version'] or 1.0}")
        with col_m2:
            success_rate = (
                (exp_data["tasks_completed"] / exp_data["tasks_count"] * 100)
                if exp_data["tasks_count"] > 0
                else 100
            )
            st.metric("Успешность (SLA)", f"{success_rate:.1f}%")
        with col_m3:
            st.metric("База знаний", exp_data["nodes_count"])
        with col_m4:
            st.metric("Использований", exp_data["total_usage"] or 0)

        # Авто-предложения по улучшению (Evolution Suggestions)
        st.markdown("#### ✨ Статус Автономной Эволюции")

        last_evolve = (exp_data.get("metadata") or {}).get("last_evolution", "Никогда")
        st.info(f"🧬 Последняя автономная мутация: **{last_evolve}**")
        st.caption(
            "Мутация и инъекция скиллов теперь происходят автоматически в ночном цикле обучения."
        )

        # Логика генерации предложений на основе данных
        suggestions = []
        if success_rate < 90:
            suggestions.append(
                f"⚠️ У {selected_expert} снизился показатель успеха. Система запланировала коррекцию ДНК на ближайшую ночь."
            )
        if exp_data["total_usage"] > 500 and (exp_data["version"] or 1.0) < 2.0:
            suggestions.append(
                f"📈 {selected_expert} накопил огромный опыт. Система готовит масштабную мутацию до версии 2.0."
            )

        for s in suggestions:
            st.warning(s)

        if not suggestions:
            st.success(f"✅ {selected_expert} работает стабильно. Текущих инструкций достаточно.")

        st.markdown("---")
        top3 = leaderboard[:3]
        cols = st.columns(3)
        for i, exp in enumerate(top3):
            with cols[i]:
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
                st.markdown(
                    f"""
                    <div style="text-align: center; background: rgba(88, 166, 255, 0.05); padding: 20px; border-radius: 12px; border: 1px solid var(--dash-accent);">
                        <div style="font-size: 40px;">{medal}</div>
                        <div style="font-weight: 800; font-size: 18px;">{exp["name"]}</div>
                        <div style="font-size: 12px; color: var(--dash-text-muted);">{exp["department"]}</div>
                        <div style="color: var(--dash-accent); font-weight: 800; font-size: 20px; margin-top: 10px;">{exp["total_usage"] or 0}</div>
                        <div style="font-size: 10px; color: var(--dash-text-muted);">использований</div>
                    </div>
                """,
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        df_leaderboard = pd.DataFrame(leaderboard)
        st.dataframe(
            df_leaderboard[
                ["name", "department", "nodes_count", "total_usage", "tasks_completed"]
            ].rename(
                columns={
                    "name": "Эксперт",
                    "department": "Департамент",
                    "nodes_count": "Узлов",
                    "total_usage": "Использований",
                    "tasks_completed": "Завершено",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )


def render_okr():
    """🎯 Стратегия OKR."""
    st.subheader("🎯 Стратегические Цели (OKR)")

    # Пытаемся получить OKR из специальной таблицы (Singularity 10.0)
    okrs = fetch_data(
        "SELECT objective, department, period, created_at FROM okrs ORDER BY created_at DESC"
    )

    if okrs:
        for okr in okrs:
            with st.expander(f"🎯 {okr['objective'][:100]}..."):
                st.markdown(f"**Цель:** {okr['objective']}")
                st.markdown(f"**Отдел:** {okr['department'] or 'Общий'}")
                st.markdown(f"**Период:** {okr['period']}")
                st.caption(f"Дата создания: {format_msk(okr['created_at'])}")
    else:
        # Fallback на knowledge_nodes
        okrs_kn = fetch_data(
            "SELECT content, metadata, created_at FROM knowledge_nodes WHERE metadata->>'type' = 'okr' ORDER BY created_at DESC"
        )
        if okrs_kn:
            for okr in okrs_kn:
                with st.expander(f"🎯 {okr['content'][:100]}..."):
                    st.json(okr["metadata"])
        else:
            st.info("Стратегические цели не заданы.")


def render_board_decisions():
    """🏛️ Решения Совета."""
    st.subheader("📜 Решения Совета Директоров")
    # Ищем оба типа: директивы и консультации
    decisions = fetch_data("""
        SELECT content, created_at, metadata->>'type' as type
        FROM knowledge_nodes
        WHERE metadata->>'type' IN ('board_decision', 'board_directive', 'board_consult')
        ORDER BY created_at DESC LIMIT 20
    """)
    if decisions:
        for d in decisions:
            color = "var(--dash-danger)" if d["type"] == "board_directive" else "var(--dash-accent)"
            label = (
                "ДИРЕКТИВА"
                if d["type"] == "board_directive"
                else "КОНСУЛЬТАЦИЯ"
                if d["type"] == "board_consult"
                else "РЕШЕНИЕ"
            )

            # Очистка контента от префикса, если он есть
            display_content = d["content"]
            if display_content.startswith("🏛 СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА:"):
                display_content = display_content.replace(
                    "🏛 СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА:", ""
                ).strip()
            elif display_content.startswith("🏛 Консультация Совета:"):
                display_content = display_content.replace("🏛 Консультация Совета:", "").strip()

            st.markdown(
                f"""
                <div style="background: rgba(243, 139, 168, 0.05); border-left: 3px solid {color}; padding: 12px; border-radius: 4px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-size: 10px; font-weight: 800; color: {color};">{label}</span>
                        <span style="font-size: 11px; color: var(--dash-text-muted);">{format_msk(d["created_at"])}</span>
                    </div>
                    <div style="font-size: 14px; color: var(--dash-text); margin-top: 4px; white-space: pre-wrap;">{display_content}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        st.info("Решений совета не найдено.")
