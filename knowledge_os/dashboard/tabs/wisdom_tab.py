import json

import pandas as pd
import plotly.express as px
import streamlit as st
from database_service import fetch_data, run_query


def render_metric_card(label, value, delta=None, delta_color="normal"):
    """Локальная копия функции отрисовки метрик, если она не импортирована"""
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def render_wisdom_tab():
    st.markdown("## 🏛 Wisdom & Mentorship Command Center")
    st.markdown("### Эволюция интеллекта и корпоративная мудрость (Singularity 31.2+)")

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
            SELECT AVG(
                CASE
                    WHEN (metadata->>'audit_score') ~ '^-?\\d+$' THEN (metadata->>'audit_score')::int
                    ELSE NULL
                END
            ) as avg_score
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
        t_count = total_nodes[0]["count"] if total_nodes else 0
        density = (w_count / max(int(t_count or 0), 1)) * 100
        st.metric("Wisdom Density", f"{density:.1f}%")

    st.markdown("---")

    # 2. Последние советы ментора (Mentorship Notes)
    st.markdown("### 🎓 Последние советы ментора")
    mentorship_data = fetch_data("""
        SELECT
            created_at,
            metadata->>'target_expert' as expert,
            content,
            CASE
                WHEN (metadata->>'score') ~ '^-?\\d+$' THEN (metadata->>'score')::int
                ELSE NULL
            END as score
        FROM knowledge_nodes
        WHERE metadata->>'type' = 'mentorship_note'
        ORDER BY created_at DESC LIMIT 5
    """)

    if mentorship_data:
        for note in mentorship_data:
            expert_name = note.get("expert") or "—"
            score_val = note.get("score")
            score_str = f"{score_val}/10" if score_val is not None else "N/A"
            created_label = (
                note["created_at"].strftime("%d.%m %H:%M")
                if hasattr(note.get("created_at"), "strftime")
                else str(note.get("created_at") or "—")
            )
            with st.expander(f"📌 {expert_name} — Оценка: {score_str} ({created_label})"):
                st.write(note.get("content") or "—")
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
        for idx, sop in enumerate(sop_data):
            col_a, col_b = st.columns([4, 1])
            content_text = sop.get("content") or ""
            first_line = content_text.splitlines()[0] if content_text else "SOP без заголовка"
            created_label = (
                sop["created_at"].strftime("%d.%m.%Y")
                if hasattr(sop.get("created_at"), "strftime")
                else str(sop.get("created_at") or "—")
            )
            file_path = sop.get("file_path") or "—"
            with col_a:
                st.markdown(f"**{first_line}**")
                st.caption(f"Создано: {created_label} | Путь: `{file_path}`")
            with col_b:
                if st.button("Открыть", key=f"open_sop_{idx}_{file_path}"):
                    # В реальном приложении здесь можно было бы выводить содержимое файла
                    st.info(f"SOP доступен по пути: {file_path}")
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
                AVG(
                    CASE
                        WHEN (metadata->>'consensus_score') ~ '^-?\\d+(\\.\\d+)?$'
                        THEN (metadata->>'consensus_score')::float
                        ELSE NULL
                    END
                ) as avg_consensus
            FROM knowledge_nodes
            WHERE metadata->>'cycle' LIKE 'nightly_council%%'
        """)

        if council_stats and council_stats[0]["total_debates"] > 0:
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Всего дебатов", council_stats[0]["total_debates"])
            with c2:
                avg_score = council_stats[0].get("avg_consensus")
                st.metric(
                    "Средний консенсус",
                    f"{avg_score:.2f}" if avg_score is not None else "N/A",
                )
            st.markdown("---")
    except Exception:
        pass

    try:
        council_data = fetch_data("""
            SELECT id, content, created_at, metadata->>'cycle' as cycle, metadata->>'consensus_score' as score
            FROM knowledge_nodes
            WHERE metadata->>'cycle' LIKE 'nightly_council%%'
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
                st.plotly_chart(fig_savings, width="stretch")
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
                WHERE expert_id = %s AND is_active = TRUE
                ORDER BY updated_at DESC LIMIT 1
            """,
                (expert_id,),
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
                    # Деактивируем старые переопределения и добавляем новое
                    deactivated = run_query(
                        "UPDATE expert_dna_overrides SET is_active = FALSE WHERE expert_id = %s",
                        (expert_id,),
                    )
                    inserted = run_query(
                        """
                        INSERT INTO expert_dna_overrides (expert_id, custom_instructions, updated_by)
                        VALUES (%s, %s, %s)
                    """,
                        (expert_id, new_instructions, "Dashboard_Admin"),
                    )

                    if deactivated and inserted:
                        st.success(
                            f"✅ ДНК эксперта {selected_expert_name} обновлена! Изменения вступят в силу при следующем запросе."
                        )
                        st.balloons()
                    else:
                        st.error("❌ Не удалось обновить ДНК эксперта. Проверьте подключение к БД.")
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
        df["count"] = pd.to_numeric(df["count"], errors="coerce").fillna(0).astype(int)
        df["cumulative_count"] = df["count"].cumsum()
        fig = px.line(
            df,
            x="day",
            y="cumulative_count",
            title="Накопление Meta-Knowledge (Wisdom)",
            labels={"day": "Дата", "cumulative_count": "Накопленное кол-во узлов"},
            template="plotly_dark",
        )
        st.plotly_chart(fig, width="stretch")
