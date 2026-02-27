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

    # 1. Ключевые метрики мудрости
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Средний балл аудита
        avg_score = fetch_data("""
            SELECT AVG((metadata->>'audit_score')::int) as avg_score
            FROM tasks
            WHERE metadata->>'audit_score' IS NOT NULL
        """)
        score = avg_score[0]["avg_score"] if avg_score and avg_score[0]["avg_score"] else 0
        st.metric("Средний балл аудита", f"{score:.1f}/10")

    with col2:
        # Количество SOP
        sop_count = fetch_data(
            "SELECT COUNT(*) as count FROM knowledge_nodes WHERE metadata->>'type' = 'sop_document'"
        )
        count = sop_count[0]["count"] if sop_count else 0
        st.metric("Создано SOP", count)

    with col3:
        # Количество Mentorship Notes
        mentorship_count = fetch_data(
            "SELECT COUNT(*) as count FROM knowledge_nodes WHERE metadata->>'type' = 'mentorship_note'"
        )
        count = mentorship_count[0]["count"] if mentorship_count else 0
        st.metric("Советы ментора", count)

    with col4:
        # Wisdom Density (Meta-nodes vs Total nodes)
        wisdom_nodes = fetch_data(
            "SELECT COUNT(*) as count FROM knowledge_nodes WHERE metadata->>'type' IN ('meta_wisdom', 'mentorship_note', 'sop_document')"
        )
        total_nodes = fetch_data("SELECT COUNT(*) as count FROM knowledge_nodes")
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
    wisdom_over_time = fetch_data("""
        SELECT
            date_trunc('day', created_at) as day,
            COUNT(*) as count
        FROM knowledge_nodes
        WHERE metadata->>'type' IN ('meta_wisdom', 'mentorship_note', 'sop_document')
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
