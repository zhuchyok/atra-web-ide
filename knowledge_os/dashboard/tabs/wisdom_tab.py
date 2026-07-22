import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from database_service import fetch_data, run_query

# Dashboard container mounts app/ on PYTHONPATH; local runs may not.
_APP_DIR = Path(__file__).resolve().parents[2] / "app"
if _APP_DIR.is_dir() and str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

WISDOM_TYPES = ("meta_wisdom", "mentorship_note", "sop_document", "distilled_wisdom", "wisdom_rule")
COUNCIL_CYCLE_PREFIX = "nightly_council%"


def render_metric_card(label, value, delta=None, delta_color="normal"):
    """Локальная копия функции отрисовки метрик, если она не импортирована"""
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def _count(query: str, params=None) -> int:
    rows = fetch_data(query, params)
    if not rows:
        return 0
    return int(rows[0].get("count") or rows[0].get("c") or 0)


def _avg(query: str, params=None) -> float:
    rows = fetch_data(query, params)
    if not rows:
        return 0.0
    val = rows[0].get("avg_score") or rows[0].get("avg") or 0
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_ts(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m %H:%M")
    return str(value or "—")


def _metric_with_fallback(label: str, period_value, all_time_value, unit: str = ""):
    """Show period metric; if zero but history exists, show all-time with caption."""
    period_num = period_value or 0
    all_num = all_time_value or 0
    if isinstance(period_num, float):
        display = f"{period_num:.1f}{unit}"
    else:
        display = f"{period_num}{unit}"
    st.metric(label, display)
    if (not period_num or period_num == 0) and all_num:
        if isinstance(all_num, float):
            st.caption(f"За период пусто · всего: {all_num:.1f}{unit}")
        else:
            st.caption(f"За период пусто · всего: {all_num}{unit}")


def render_wisdom_tab():
    st.markdown("## 🏛 Wisdom & Mentorship Command Center")
    st.markdown("### Эволюция интеллекта и корпоративная мудрость (Singularity 31.2+)")

    time_range = st.session_state.get("global_time_range", "Последние 7 дней")
    st.caption(f"📅 Фильтр времени: **{time_range}**")

    from database_service import get_time_filter

    t_filter = get_time_filter(time_range, "created_at")
    t_filter_tasks = get_time_filter(time_range, "created_at")
    wisdom_types_sql = ", ".join(f"'{t}'" for t in WISDOM_TYPES)

    # 1. Ключевые метрики мудрости
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Prefer task audit_score; fall back to mentorship_note.score (pipeline reality)
        avg_tasks_period = _avg(f"""
            SELECT AVG(
                CASE
                    WHEN (metadata->>'audit_score') ~ '^-?\\d+(\\.\\d+)?$'
                    THEN (metadata->>'audit_score')::float
                    ELSE NULL
                END
            ) as avg_score
            FROM tasks
            WHERE metadata->>'audit_score' IS NOT NULL AND {t_filter_tasks}
        """)
        avg_notes_period = _avg(f"""
            SELECT AVG(
                CASE
                    WHEN (metadata->>'score') ~ '^-?\\d+(\\.\\d+)?$'
                    THEN (metadata->>'score')::float
                    ELSE NULL
                END
            ) as avg_score
            FROM knowledge_nodes
            WHERE metadata->>'type' = 'mentorship_note' AND {t_filter}
        """)
        avg_notes_all = _avg("""
            SELECT AVG(
                CASE
                    WHEN (metadata->>'score') ~ '^-?\\d+(\\.\\d+)?$'
                    THEN (metadata->>'score')::float
                    ELSE NULL
                END
            ) as avg_score
            FROM knowledge_nodes
            WHERE metadata->>'type' = 'mentorship_note'
        """)
        period_score = avg_tasks_period or avg_notes_period
        _metric_with_fallback("Средний балл аудита", period_score, avg_notes_all, "/10")

    with col2:
        sop_period = _count(f"""
            SELECT COUNT(*) as count FROM knowledge_nodes
            WHERE (
                metadata->>'type' = 'sop_document'
                OR domain_id IN (SELECT id FROM domains WHERE name = 'SOP')
            ) AND {t_filter}
        """)
        sop_all = _count("""
            SELECT COUNT(*) as count FROM knowledge_nodes
            WHERE metadata->>'type' = 'sop_document'
               OR domain_id IN (SELECT id FROM domains WHERE name = 'SOP')
        """)
        _metric_with_fallback("Создано SOP", sop_period, sop_all)

    with col3:
        mentor_period = _count(f"""
            SELECT COUNT(*) as count FROM knowledge_nodes
            WHERE (
                metadata->>'type' = 'mentorship_note'
                OR domain_id IN (SELECT id FROM domains WHERE name = 'Mentorship')
            ) AND {t_filter}
        """)
        mentor_all = _count("""
            SELECT COUNT(*) as count FROM knowledge_nodes
            WHERE metadata->>'type' = 'mentorship_note'
               OR domain_id IN (SELECT id FROM domains WHERE name = 'Mentorship')
        """)
        _metric_with_fallback("Советы ментора", mentor_period, mentor_all)

    with col4:
        wisdom_period = _count(f"""
            SELECT COUNT(*) as count FROM knowledge_nodes
            WHERE metadata->>'type' IN ({wisdom_types_sql}) AND {t_filter}
        """)
        total_period = _count(f"SELECT COUNT(*) as count FROM knowledge_nodes WHERE {t_filter}")
        wisdom_all = _count(f"""
            SELECT COUNT(*) as count FROM knowledge_nodes
            WHERE metadata->>'type' IN ({wisdom_types_sql})
        """)
        total_all = _count("SELECT COUNT(*) as count FROM knowledge_nodes")
        density_period = (wisdom_period / max(total_period, 1)) * 100
        density_all = (wisdom_all / max(total_all, 1)) * 100
        _metric_with_fallback("Wisdom Density", density_period, density_all, "%")

    st.markdown("---")

    # 2. Последние советы ментора
    st.markdown("### 🎓 Последние советы ментора")
    mentorship_data = fetch_data("""
        SELECT
            created_at,
            COALESCE(metadata->>'target_expert', metadata->>'expert_name', '—') as expert,
            content,
            CASE
                WHEN (metadata->>'score') ~ '^-?\\d+(\\.\\d+)?$' THEN (metadata->>'score')::float
                ELSE NULL
            END as score,
            metadata->>'type' as node_type
        FROM knowledge_nodes
        WHERE metadata->>'type' = 'mentorship_note'
           OR domain_id IN (SELECT id FROM domains WHERE name = 'Mentorship')
        ORDER BY
            CASE WHEN metadata->>'type' = 'mentorship_note' THEN 0 ELSE 1 END,
            created_at DESC
        LIMIT 8
    """)

    if mentorship_data:
        for note in mentorship_data:
            expert_name = note.get("expert") or "—"
            score_val = note.get("score")
            score_str = f"{score_val:.0f}/10" if score_val is not None else "N/A"
            created_label = _fmt_ts(note.get("created_at"))
            tag = note.get("node_type") or "Mentorship"
            with st.expander(f"📌 {expert_name} — {score_str} · {tag} ({created_label})"):
                st.write(note.get("content") or "—")
    else:
        st.info("Советов ментора пока нет. Запустите аудит: nightly mentorship_engine.")

    st.markdown("---")

    # 3. Реестр SOP
    st.markdown("### 📜 Реестр SOP (Standard Operating Procedures)")
    sop_data = fetch_data("""
        SELECT
            created_at,
            content,
            COALESCE(metadata->>'file_path', metadata->>'path', '—') as file_path,
            metadata->>'type' as node_type
        FROM knowledge_nodes
        WHERE metadata->>'type' = 'sop_document'
           OR domain_id IN (SELECT id FROM domains WHERE name = 'SOP')
        ORDER BY
            CASE WHEN metadata->>'type' = 'sop_document' THEN 0 ELSE 1 END,
            created_at DESC
        LIMIT 10
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
                st.markdown(f"**{first_line[:120]}**")
                st.caption(
                    f"Создано: {created_label} | type={sop.get('node_type') or 'domain:SOP'} | `{file_path}`"
                )
            with col_b:
                if st.button("Открыть", key=f"open_sop_{idx}_{file_path}"):
                    st.info(content_text[:2000] if content_text else f"Путь: {file_path}")
    else:
        st.info("SOP пока не созданы. Генерируются из задач с audit_score ≥ 8.")

    st.markdown("---")

    # 4. Дебаты экспертов
    st.markdown("### 🎭 Дебаты экспертов (Expert Council)")
    try:
        council_stats = fetch_data(
            """
            SELECT
                COUNT(*) as total_debates,
                AVG(
                    CASE
                        WHEN (metadata->>'consensus_score') ~ '^-?\\d+(\\.\\d+)?$'
                        THEN (metadata->>'consensus_score')::float
                        ELSE NULL
                    END
                ) as avg_consensus,
                MAX(created_at) as last_debate
            FROM knowledge_nodes
            WHERE metadata->>'cycle' LIKE %s
               OR metadata->>'type' ILIKE %s
               OR metadata->>'type' ILIKE %s
            """,
            (COUNCIL_CYCLE_PREFIX, "%council%", "%debate%"),
        )

        if council_stats and (council_stats[0].get("total_debates") or 0) > 0:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Всего дебатов", int(council_stats[0]["total_debates"]))
            with c2:
                avg_score = council_stats[0].get("avg_consensus")
                st.metric(
                    "Средний консенсус",
                    f"{avg_score:.2f}" if avg_score is not None else "N/A",
                )
            with c3:
                st.metric("Последний", _fmt_ts(council_stats[0].get("last_debate")))
            st.markdown("---")

        council_data = fetch_data(
            """
            SELECT id, content, created_at,
                   COALESCE(metadata->>'cycle', metadata->>'type', 'council') as cycle,
                   metadata->>'consensus_score' as score
            FROM knowledge_nodes
            WHERE metadata->>'cycle' LIKE %s
               OR metadata->>'type' ILIKE %s
               OR metadata->>'type' ILIKE %s
            ORDER BY created_at DESC LIMIT 10
            """,
            (COUNCIL_CYCLE_PREFIX, "%council%", "%debate%"),
        )
        if council_data:
            for row in council_data:
                score_val = row.get("score")
                score_str = f" | Консенсус: {score_val}" if score_val else ""
                with st.expander(
                    f"📌 {row.get('cycle') or 'council'}{score_str} — {_fmt_ts(row.get('created_at'))}"
                ):
                    st.write(row.get("content") or "—")
        else:
            st.info("Дебаты экспертов пока не проводились (ночной цикл council).")
    except Exception as e:
        st.error(f"Ошибка загрузки дебатов: {e}")

    st.markdown("---")

    # 5. Success Retrieval Audit
    st.markdown("### 📊 Success Retrieval Audit (Efficiency)")
    try:
        audit_data = fetch_data("""
            SELECT
                COALESCE(SUM(
                    CASE
                        WHEN (metadata->>'time_saved_seconds') ~ '^-?\\d+$'
                        THEN (metadata->>'time_saved_seconds')::int
                        ELSE 0
                    END
                ), 0) as total_saved_sec,
                COUNT(*) as total_retrievals,
                AVG(
                    CASE
                        WHEN (metadata->>'examples_found') ~ '^-?\\d+$'
                        THEN (metadata->>'examples_found')::int
                        ELSE NULL
                    END
                ) as avg_examples
            FROM knowledge_nodes
            WHERE metadata->>'type' = 'success_retrieval_audit'
        """)

        if audit_data and (audit_data[0].get("total_retrievals") or 0) > 0:
            total_sec = audit_data[0]["total_saved_sec"] or 0
            total_hours = total_sec / 3600

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Экономия времени (часы)", f"{total_hours:.2f}h")
            with c2:
                st.metric("Всего активаций опыта", int(audit_data[0]["total_retrievals"]))
            with c3:
                avg_ex = audit_data[0].get("avg_examples")
                st.metric(
                    "Среднее кол-во примеров",
                    f"{avg_ex:.1f}" if avg_ex is not None else "N/A",
                )

            savings_over_time = fetch_data("""
                SELECT
                    date_trunc('day', created_at) as day,
                    SUM(
                        CASE
                            WHEN (metadata->>'time_saved_seconds') ~ '^-?\\d+$'
                            THEN (metadata->>'time_saved_seconds')::int
                            ELSE 0
                        END
                    ) / 60.0 as minutes_saved
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
            completed_with_emb = _count(
                "SELECT COUNT(*) as count FROM tasks WHERE status='completed' AND embedding IS NOT NULL"
            )
            st.info(
                "Данных аудита эффективности пока нет. "
                f"Готово примеров для retrieval: **{completed_with_emb}** completed tasks с embedding. "
                "Записи появятся при вызове SuccessRetriever (после фикса записи metadata)."
            )
    except Exception as e:
        st.error(f"Ошибка загрузки аудита: {e}")

    st.markdown("---")

    # 6. Dynamic DNA Control
    st.markdown("### 🧬 Dynamic DNA Control (Automation Center)")
    st.markdown("Управление ДНК экспертов в реальном времени без перезагрузки системы.")

    try:
        experts_list = fetch_data(
            "SELECT id, name, role, specialization_level FROM experts ORDER BY name"
        )
        overrides_n = _count(
            "SELECT COUNT(*) as count FROM expert_dna_overrides WHERE is_active = TRUE"
        )
        st.caption(f"Активных DNA overrides: **{overrides_n}** · экспертов в реестре: **{len(experts_list or [])}**")

        if experts_list:
            expert_names = [e["name"] for e in experts_list]
            selected_expert_name = st.selectbox("Выберите эксперта для тюнинга ДНК:", expert_names)

            selected_expert = next(e for e in experts_list if e["name"] == selected_expert_name)
            expert_id = selected_expert["id"]

            current_override = fetch_data(
                """
                SELECT custom_instructions, version, updated_at
                FROM expert_dna_overrides
                WHERE expert_id = %s AND is_active = TRUE
                ORDER BY updated_at DESC LIMIT 1
            """,
                (expert_id,),
            )

            initial_text = current_override[0]["custom_instructions"] if current_override else ""
            if current_override:
                st.caption(f"Текущий override: v{current_override[0].get('version') or '—'} · {_fmt_ts(current_override[0].get('updated_at'))}")

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

    # 7. Цифровая Конституция
    st.markdown("### 📜 Цифровая Конституция Корпорации")
    try:
        try:
            from digital_constitution import CONSTITUTION_PRINCIPLES
        except ImportError:
            from app.digital_constitution import CONSTITUTION_PRINCIPLES

        cols = st.columns(min(len(CONSTITUTION_PRINCIPLES), 5))
        for i, p in enumerate(CONSTITUTION_PRINCIPLES):
            with cols[i % len(cols)]:
                st.markdown(f"**{p['id']}: {p['name']}**")
                st.caption(p["rule"])
    except Exception as e:
        st.error(f"Ошибка загрузки конституции: {e}")

    st.markdown("---")

    # 8. Прогресс накопления мудрости
    st.markdown("### 📈 Прогресс накопления мудрости")
    wisdom_over_time = fetch_data(f"""
        SELECT
            date_trunc('day', created_at) as day,
            COUNT(*) as count
        FROM knowledge_nodes
        WHERE metadata->>'type' IN ({wisdom_types_sql})
           OR domain_id IN (SELECT id FROM domains WHERE name IN ('Mentorship', 'SOP', 'Wisdom & Heuristics'))
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
            title="Накопление Meta-Knowledge (Wisdom) — всё время",
            labels={"day": "Дата", "cumulative_count": "Накопленное кол-во узлов"},
            template="plotly_dark",
        )
        st.plotly_chart(fig, width="stretch")
        st.caption(
            f"Узлов мудрости (typed): **{wisdom_all}** · Mentorship+SOP+Wisdom domains включены в график."
        )
    else:
        st.info("Пока нет точек для графика накопления мудрости.")
