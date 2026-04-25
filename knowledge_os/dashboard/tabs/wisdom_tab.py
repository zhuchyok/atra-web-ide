import json

import pandas as pd
import plotly.express as px
import streamlit as st
from database_service import fetch_data


def render_metric_card(label, value, delta=None, delta_color="normal"):
    """Локальная копия функции отрисовки метрик, если она не импортирована"""
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def render_wisdom_tab():
    st.markdown("## 🏛 Wisdom & Mentorship Command Center")
    st.markdown("### Эволюция интеллекта и корпоративная мудрость (Singularity 20.0)")
    
    time_range = st.session_state.get("global_time_range", "Последние 7 дней")
    st.caption(f"📅 Фильтр времени: **{time_range}**")
    
    from database_service import get_time_filter
    t_filter = get_time_filter(time_range, "created_at")
    t_filter_tasks = get_time_filter(time_range, "created_at")

    # 1. Ключевые метрики мудрости
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Средний балл аудита
        avg_score = fetch_data(f"""
            SELECT AVG((metadata->>'audit_score')::int) as avg_score
            FROM tasks
            WHERE metadata->>'audit_score' IS NOT NULL AND {t_filter_tasks}
        """)
        score = avg_score[0]["avg_score"] if avg_score and avg_score[0]["avg_score"] else 0
        st.metric("Средний балл аудита", f"{score:.1f}/10")

    with col2:
        # Количество SOP
        sop_count = fetch_data(f"""
            SELECT COUNT(*) as count FROM knowledge_nodes 
            WHERE metadata->>'type' = 'sop_document' AND {t_filter}
        """)
        count = sop_count[0]["count"] if sop_count else 0
        st.metric("Создано SOP", count)

    with col3:
        # Количество Mentorship Notes
        mentorship_count = fetch_data(f"""
            SELECT COUNT(*) as count FROM knowledge_nodes 
            WHERE metadata->>'type' = 'mentorship_note' AND {t_filter}
        """)
        count = mentorship_count[0]["count"] if mentorship_count else 0
        st.metric("Советы ментора", count)

    with col4:
        # Wisdom Density (Meta-nodes vs Total nodes)
        wisdom_nodes = fetch_data(f"""
            SELECT COUNT(*) as count FROM knowledge_nodes 
            WHERE metadata->>'type' IN ('meta_wisdom', 'mentorship_note', 'sop_document') AND {t_filter}
        """)
        total_nodes = fetch_data(f"SELECT COUNT(*) as count FROM knowledge_nodes WHERE {t_filter}")
        w_count = wisdom_nodes[0]["count"] if wisdom_nodes else 0
        t_count = total_nodes[0]["count"] if total_nodes else 1
        density = (w_count / t_count) * 100
        st.metric("Wisdom Density", f"{density:.1f}%")

    st.markdown("---")

    # 2. Последние советы ментора (Mentorship Notes)
    st.markdown("### 🎓 Последние советы ментора")
    mentorship_data = fetch_data("""
        SELECT
            created_at,
            metadata->>'target_expert' as expert,
            content,
            (metadata->>'score')::int as score
        FROM knowledge_nodes
        WHERE metadata->>'type' = 'mentorship_note'
        ORDER BY created_at DESC LIMIT 5
    """)

    if mentorship_data:
        for note in mentorship_data:
            with st.expander(
                f"📌 {note['expert']} — Оценка: {note['score']}/10 ({note['created_at'].strftime('%d.%m %H:%M')})"
            ):
                st.write(note["content"])
    else:
        st.info("Советов ментора пока нет. Запустите аудит задач.")

    st.markdown("---")

    # 3. Реестр SOP (Standard Operating Procedures)
    st.markdown("### 📜 Реестр SOP (Standard Operating Procedures)")
    sop_data = fetch_data("""
        SELECT
            created_at,
            content,
            metadata->>'file_path' as file_path
        FROM knowledge_nodes
        WHERE metadata->>'type' = 'sop_document'
        ORDER BY created_at DESC LIMIT 10
    """)

    if sop_data:
        for sop in sop_data:
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.markdown(f"**{sop['content'].splitlines()[0]}**")
                st.caption(
                    f"Создано: {sop['created_at'].strftime('%d.%m.%Y')} | Путь: `{sop['file_path']}`"
                )
            with col_b:
                if st.button("Открыть", key=f"open_sop_{sop['file_path']}"):
                    # В реальном приложении здесь можно было бы выводить содержимое файла
                    st.info(f"SOP доступен по пути: {sop['file_path']}")
    else:
        st.info("SOP пока не созданы. Виктория создает их для задач с оценкой 8+.")

    st.markdown("---")

    # 4. Дебаты экспертов (Expert Council / nightly_council)
    st.markdown("### 🎭 Дебаты экспертов (Expert Council)")

    # Добавляем метрики консенсуса, если они есть
    try:
        council_stats = fetch_data("""
            SELECT
                COUNT(*) as total_debates,
                AVG((metadata->>'consensus_score')::float) as avg_consensus
            FROM knowledge_nodes
            WHERE metadata->>'cycle' LIKE 'nightly_council%'
            AND metadata->>'consensus_score' IS NOT NULL
        """)

        if council_stats and council_stats[0]["total_debates"] > 0:
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Всего дебатов", council_stats[0]["total_debates"])
            with c2:
                avg_score = council_stats[0]["avg_consensus"] or 0
                st.metric("Средний консенсус", f"{avg_score:.2f}")
            st.markdown("---")
    except Exception:
        pass

    try:
        council_data = fetch_data("""
            SELECT id, content, created_at, metadata->>'cycle' as cycle, metadata->>'consensus_score' as score
            FROM knowledge_nodes
            WHERE metadata->>'cycle' LIKE 'nightly_council%'
            ORDER BY created_at DESC LIMIT 10
        """)
        if council_data:
            for row in council_data:
                score_val = row.get("score")
                score_str = f" | Консенсус: {score_val}" if score_val else ""
                with st.expander(
                    f"📌 {row['cycle'] or 'council'}{score_str} — {row['created_at'].strftime('%d.%m %H:%M') if hasattr(row['created_at'], 'strftime') else row['created_at']}"
                ):
                    st.write(row["content"] or "—")
        else:
            st.info("Дебаты экспертов пока не проводились (ночной цикл council).")
    except Exception as e:
        st.error(f"Ошибка загрузки дебатов: {e}")

    st.markdown("---")

    # 7. [SINGULARITY 21.18] Success Retrieval Audit
    st.markdown("### 📊 Success Retrieval Audit (Efficiency)")
    try:
        audit_data = fetch_data("""
            SELECT
                SUM((metadata->>'time_saved_seconds')::int) as total_saved_sec,
                COUNT(*) as total_retrievals,
                AVG((metadata->>'examples_found')::int) as avg_examples
            FROM knowledge_nodes
            WHERE metadata->>'type' = 'success_retrieval_audit'
        """)

        if audit_data and audit_data[0]["total_retrievals"] > 0:
            total_sec = audit_data[0]["total_saved_sec"] or 0
            total_hours = total_sec / 3600

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Экономия времени (часы)", f"{total_hours:.2f}h")
            with c2:
                st.metric("Всего активаций опыта", audit_data[0]["total_retrievals"])
            with c3:
                st.metric("Среднее кол-во примеров", f"{audit_data[0]['avg_examples']:.1f}")

            # График экономии по дням
            savings_over_time = fetch_data("""
                SELECT
                    date_trunc('day', created_at) as day,
                    SUM((metadata->>'time_saved_seconds')::int) / 60 as minutes_saved
                FROM knowledge_nodes
                WHERE metadata->>'type' = 'success_retrieval_audit'
                GROUP BY 1 ORDER BY 1
            """)
            if savings_over_time:
                df_savings = pd.DataFrame(savings_over_time)
                fig_savings = px.bar(
                    df_savings,
                    x="day",
                    y="minutes_saved",
                    title="Экономия времени (минуты в день)",
                    template="plotly_dark",
                    color_discrete_sequence=[st.get_option("theme.primaryColor") or "#58a6ff"],
                )
                st.plotly_chart(fig_savings, use_container_width=True)
        else:
            st.info("Данные аудита эффективности пока не накоплены.")
    except Exception as e:
        st.error(f"Ошибка загрузки аудита: {e}")

    st.markdown("---")

    # 6. [SINGULARITY 21.18] Dynamic DNA Control
    st.markdown("### 🧬 Dynamic DNA Control (Automation Center)")
    st.markdown("Управление ДНК экспертов в реальном времени без перезагрузки системы.")

    try:
        experts_list = fetch_data(
            "SELECT id, name, role, specialization_level FROM experts ORDER BY name"
        )
        if experts_list:
            expert_names = [e["name"] for e in experts_list]
            selected_expert_name = st.selectbox("Выберите эксперта для тюнинга ДНК:", expert_names)

            selected_expert = next(e for e in experts_list if e["name"] == selected_expert_name)
            expert_id = selected_expert["id"]

            # Загружаем текущее переопределение
            current_override = fetch_data(
                """
                SELECT custom_instructions, version
                FROM expert_dna_overrides
                WHERE expert_id = $1 AND is_active = TRUE
                ORDER BY updated_at DESC LIMIT 1
            """,
                expert_id,
            )

            initial_text = current_override[0]["custom_instructions"] if current_override else ""

            with st.form(key=f"dna_form_{expert_id}"):
                st.markdown(f"**Эксперт:** {selected_expert_name} ({selected_expert['role']})")
                st.markdown(f"**Уровень:** {selected_expert['specialization_level']}")

                new_instructions = st.text_area(
                    "Динамические инструкции (DNA Override):",
                    value=initial_text,
                    height=200,
                    help="Эти инструкции будут приоритетнее любых .mdc файлов.",
                )

                submit_button = st.form_submit_button(label="🚀 Обновить ДНК Мгновенно")

                if submit_button:
                    import asyncpg
                    from database_service import get_db_connection

                    async def update_dna():
                        conn = await get_db_connection()
                        try:
                            # Деактивируем старые
                            await conn.execute(
                                "UPDATE expert_dna_overrides SET is_active = FALSE WHERE expert_id = $1",
                                expert_id,
                            )
                            # Вставляем новую
                            await conn.execute(
                                """
                                INSERT INTO expert_dna_overrides (expert_id, custom_instructions, updated_by)
                                VALUES ($1, $2, $3)
                            """,
                                expert_id,
                                new_instructions,
                                "Dashboard_Admin",
                            )
                            return True
                        finally:
                            await conn.close()

                    if asyncio.run(update_dna()):
                        st.success(
                            f"✅ ДНК эксперта {selected_expert_name} обновлена! Изменения вступят в силу при следующем запросе."
                        )
                        st.balloons()
        else:
            st.warning("Список экспертов пуст.")
    except Exception as e:
        st.error(f"Ошибка DNA Control: {e}")

    st.markdown("---")

    # 5. Цифровая Конституция (Constitutional AI)
    st.markdown("### 📜 Цифровая Конституция Корпорации")
    try:
        from digital_constitution import CONSTITUTION_PRINCIPLES

        cols = st.columns(len(CONSTITUTION_PRINCIPLES))
        for i, p in enumerate(CONSTITUTION_PRINCIPLES):
            with cols[i]:
                st.markdown(f"**{p['id']}: {p['name']}**")
                st.caption(p["rule"])
    except Exception as e:
        st.error(f"Ошибка загрузки конституции: {e}")

    # 4. График прогресса интеллекта
    st.markdown("### 📈 Прогресс накопления мудрости")
    wisdom_over_time = fetch_data(f"""
        SELECT
            date_trunc('day', created_at) as day,
            COUNT(*) as count
        FROM knowledge_nodes
        WHERE metadata->>'type' IN ('meta_wisdom', 'mentorship_note', 'sop_document') AND {t_filter}
        GROUP BY 1 ORDER BY 1
    """)

    if wisdom_over_time:
        df = pd.DataFrame(wisdom_over_time)
        fig = px.line(
            df,
            x="day",
            y="count",
            title="Накопление Meta-Knowledge (Wisdom)",
            labels={"day": "Дата", "count": "Кол-во узлов"},
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)
