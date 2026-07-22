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
        st.markdown("---")
        render_mutation_rollout_reports()


def render_mutation_rollout_reports():
    """📊 Отчеты по внедрению мутаций (Shadow -> Promoted)."""
    st.subheader("🧬 Отчеты по Внедрению Мутаций (Rollout)")

    reports = fetch_data("""
        SELECT content, metadata, created_at
        FROM knowledge_nodes
        WHERE metadata->>'type' = 'mutation_rollout_report'
        ORDER BY created_at DESC LIMIT 5
    """)

    if reports:
        for r in reports:
            meta = r["metadata"]
            if isinstance(meta, str):
                import json

                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}

            with st.expander(
                f"📊 Отчет от {format_msk(r['created_at'])} (Окно: {meta.get('window_hours')}ч)"
            ):
                c1, c2, c3 = st.columns(3)
                c1.metric("Promoted", meta.get("promoted", 0))
                c2.metric("Shadow Created", meta.get("shadow_created", 0))
                c3.metric("Conversion", f"{meta.get('conversion_rate', 0) * 100:.1f}%")

                st.markdown("**Причины блокировки мутаций (Gate Reasons):**")
                reasons = meta.get("gate_reasons", {})
                gr_cols = st.columns(4)
                gr_cols[0].caption(f"Low Tests: {reasons.get('insufficient_tests', 0)}")
                gr_cols[1].caption(f"Low Wins: {reasons.get('insufficient_wins', 0)}")
                gr_cols[2].caption(f"Low Win Rate: {reasons.get('insufficient_win_rate', 0)}")
                gr_cols[3].caption(f"Low Confidence: {reasons.get('insufficient_confidence', 0)}")

                st.caption(
                    f"Пороги: tests>={meta.get('thresholds', {}).get('min_tests')}, "
                    f"win_rate>={meta.get('thresholds', {}).get('win_rate_threshold')}"
                )
    else:
        st.info("Отчетов по внедрению мутаций пока нет. Ожидайте следующего цикла (6ч).")


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

    # Use last activity timestamp to reflect real liquidity movement for older nodes too.
    # Keep two variants: plain for single-table subqueries and aliased for JOIN queries.
    t_filter_activity = get_time_filter(time_range, "COALESCE(updated_at, created_at)")
    t_filter_activity_k = get_time_filter(time_range, "COALESCE(k.updated_at, k.created_at)")

    # Метрики ликвидности (всегда) и экспертов (если есть колонки virtual_budget, performance_score)
    results = fetch_data(f"""
        SELECT
            (SELECT SUM(usage_count * confidence_score) FROM knowledge_nodes WHERE {t_filter_activity}) as total_liquidity,
            (SELECT COUNT(*) FROM knowledge_nodes WHERE usage_count > 0 AND {t_filter_activity}) as active_nodes
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
    roi_data = fetch_data(f"""
        SELECT d.name as domain, SUM(k.usage_count * k.confidence_score) as liquidity_score
        FROM knowledge_nodes k JOIN domains d ON k.domain_id = d.id
        WHERE k.usage_count > 0 AND {t_filter_activity_k}
        GROUP BY d.name ORDER BY liquidity_score DESC LIMIT 10
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
        st.plotly_chart(fig_roi, width="stretch")


def render_structure():
    """🏛️ Рейтинг экспертов и структура."""
    st.subheader("🏛️ Рейтинг Экспертов и Лидеры")

    # Full roster (new experts appear automatically from `experts` table).
    # Podium / table below still use top-10 by usage.
    experts_ranked = fetch_data(
        """
        WITH knowledge_by_expert AS (
            SELECT
                COALESCE(metadata->>'expert', metadata->>'expert_name') AS expert_name,
                COUNT(*) AS nodes_count,
                COALESCE(SUM(usage_count), 0) AS total_usage,
                AVG(confidence_score) AS avg_confidence
            FROM knowledge_nodes
            GROUP BY COALESCE(metadata->>'expert', metadata->>'expert_name')
        ),
        tasks_by_expert AS (
            SELECT
                assignee_expert_id AS expert_id,
                COUNT(*) AS tasks_count,
                COUNT(*) FILTER (WHERE status = 'completed') AS tasks_completed
            FROM tasks
            GROUP BY assignee_expert_id
        )
        SELECT
            e.id,
            e.name,
            e.department,
            e.role,
            e.version,
            e.metadata,
            COALESCE(k.nodes_count, 0) AS nodes_count,
            COALESCE(k.total_usage, 0) AS total_usage,
            k.avg_confidence AS avg_confidence,
            COALESCE(t.tasks_count, 0) AS tasks_count,
            COALESCE(t.tasks_completed, 0) AS tasks_completed
        FROM experts e
        LEFT JOIN knowledge_by_expert k ON k.expert_name = e.name
        LEFT JOIN tasks_by_expert t ON t.expert_id = e.id
        ORDER BY total_usage DESC NULLS LAST, e.name ASC
        """
    )
    leaderboard = (experts_ranked or [])[:10]
    experts_for_dna = sorted(
        experts_ranked or [],
        key=lambda e: (e.get("name") or "").lower(),
    )

    if experts_for_dna:
        # Секция эволюции (прокачки) — все эксперты из БД, не только топ-10
        st.markdown("### 🧬 Эволюция и Управление ДНК")
        st.caption(
            f"Настройка доступна для всех экспертов в реестре (**{len(experts_for_dna)}**). "
            "Новые сотрудники из `experts` появляются здесь автоматически после sync."
        )

        expert_names = [e["name"] for e in experts_for_dna]
        selected_expert = st.selectbox("Выберите эксперта для настройки", expert_names)
        exp_data = next(e for e in experts_for_dna if e["name"] == selected_expert)

        # --- Редактор Эксперта (DNA Editor) ---
        with st.expander(f"🛠️ Настройка личности: {selected_expert}", expanded=False):
            new_role = st.text_input("Роль", value=exp_data["role"])
            new_dept = st.text_input("Департамент", value=exp_data["department"])

            # Получаем полный системный промпт из БД
            full_expert = fetch_data(
                "SELECT system_prompt FROM experts WHERE id = %s",
                (exp_data["id"],),
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
                                try:
                                    resp = requests.post(
                                        "http://knowledge_rest:8002/api/experts/skills/assign",
                                        json={
                                            "expert_id": str(exp_data["id"]),
                                            "skill_name": skill["name"],
                                        },
                                        timeout=10,
                                    )
                                    if resp.status_code == 200:
                                        st.success(
                                            f"✅ Скилл {skill['name']} назначен {selected_expert} и будет применяться автоматически."
                                        )
                                    else:
                                        st.error(f"❌ Ошибка назначения: {resp.text}")
                                except Exception as e:
                                    st.error(f"❌ Ошибка связи с API: {e}")
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

        latest_mutation = fetch_data(
            """
            SELECT created_at, status
            FROM expert_mutations
            WHERE expert_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (exp_data["id"],),
        )
        metadata_last_evolve = (exp_data.get("metadata") or {}).get("last_evolution")
        if latest_mutation:
            mut = latest_mutation[0]
            st.info(
                f"🧬 Последняя автономная мутация: **{format_msk(mut['created_at'])}** "
                f"(статус: {mut.get('status', 'unknown')})"
            )
        elif metadata_last_evolve:
            st.info(f"🧬 Последняя автономная мутация: **{metadata_last_evolve}**")
        else:
            st.info("🧬 Последняя автономная мутация: **Никогда**")
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
            width="stretch",
        )


def _okr_kr_progress(current, target, description: str) -> float:
    """0..100. Inverse KR (failed/stale/меньше) — ниже current лучше."""
    try:
        cur = float(current or 0)
        tgt = float(target or 0)
    except (TypeError, ValueError):
        return 0.0
    desc = (description or "").lower()
    inverse = any(x in desc for x in ("меньше", "failed", "провален", "stale", "зависш"))
    if inverse:
        if tgt <= 0:
            return 100.0 if cur <= 0 else 0.0
        return max(0.0, min(100.0, (1.0 - (cur / tgt)) * 100.0))
    if tgt <= 0:
        return 0.0
    return max(0.0, min(100.0, (cur / tgt) * 100.0))


def render_okr():
    """🎯 Стратегия OKR — active period + Key Results (Grove/Doerr lite)."""
    st.subheader("🎯 Стратегические Цели (OKR)")

    active_period = "2026-H2"
    try:
        import sys
        from pathlib import Path

        _app = Path(__file__).resolve().parents[2] / "app"
        if _app.is_dir() and str(_app) not in sys.path:
            sys.path.insert(0, str(_app))
        from okr_service import get_active_okr_period

        active_period = get_active_okr_period()
    except Exception:
        pass

    st.caption(
        f"Активный период: **{active_period}** (env `ACTIVE_OKR_PERIOD`). "
        "Архивные OKR хранятся, но Board/отчёты читают только active."
    )

    # Refresh metrics best-effort (UPDATE via run_query — fetch_data is read-only)
    from database_service import run_query

    run_query(
        """
        WITH m AS (
            SELECT
              (SELECT COUNT(*)::float FROM knowledge_nodes) AS nodes_total,
              (SELECT COUNT(*)::float FROM knowledge_nodes
                 WHERE metadata->>'cycle' LIKE 'nightly_council%%'
                   AND created_at > NOW() - INTERVAL '7 days') AS council_7d,
              (SELECT COUNT(*)::float FROM knowledge_nodes
                 WHERE metadata->>'type' = 'mentorship_note'
                   AND created_at > NOW() - INTERVAL '7 days') AS mentor_7d,
              (SELECT COUNT(*)::float FROM tasks WHERE embedding IS NOT NULL) AS tasks_embedded,
              (SELECT COUNT(*)::float FROM tasks
                 WHERE status = 'failed'
                   AND updated_at > NOW() - INTERVAL '7 days') AS failed_7d,
              (SELECT COUNT(*)::float FROM tasks
                 WHERE status IN ('pending', 'in_progress')
                   AND updated_at < NOW() - INTERVAL '4 hours') AS stale_4h
        )
        UPDATE key_results kr SET
            current_value = CASE
                WHEN lower(kr.description) LIKE '%%дебат%%' OR lower(kr.description) LIKE '%%council%%'
                    THEN (SELECT council_7d FROM m)
                WHEN lower(kr.description) LIKE '%%ментор%%' OR lower(kr.description) LIKE '%%mentorship%%'
                    THEN (SELECT mentor_7d FROM m)
                WHEN lower(kr.description) LIKE '%%embedding%%'
                    THEN (SELECT tasks_embedded FROM m)
                WHEN lower(kr.description) LIKE '%%провален%%' OR lower(kr.description) LIKE '%%failed%%'
                    THEN (SELECT failed_7d FROM m)
                WHEN lower(kr.description) LIKE '%%stale%%' OR lower(kr.description) LIKE '%%зависш%%'
                    THEN (SELECT stale_4h FROM m)
                WHEN lower(kr.description) LIKE '%%узлов%%'
                    THEN (SELECT nodes_total FROM m)
                ELSE kr.current_value
            END,
            last_updated_at = NOW()
        FROM okrs o
        WHERE kr.okr_id = o.id AND o.period = %s
        """,
        (active_period,),
    )

    rows = fetch_data(
        """
        SELECT o.id AS okr_id, o.objective, o.department, o.period, o.created_at,
               kr.description AS kr_description, kr.current_value, kr.target_value, kr.unit
        FROM okrs o
        LEFT JOIN key_results kr ON kr.okr_id = o.id
        WHERE o.period = %s
        ORDER BY o.created_at ASC, kr.description ASC
        """,
        (active_period,),
    )

    if rows:
        # Group by OKR
        by_okr: dict = {}
        for r in rows:
            oid = r["okr_id"]
            if oid not in by_okr:
                by_okr[oid] = {
                    "objective": r["objective"],
                    "department": r["department"],
                    "period": r["period"],
                    "created_at": r["created_at"],
                    "krs": [],
                }
            if r.get("kr_description"):
                by_okr[oid]["krs"].append(r)

        for okr in by_okr.values():
            krs = okr["krs"]
            avg_pct = (
                sum(
                    _okr_kr_progress(k["current_value"], k["target_value"], k["kr_description"])
                    for k in krs
                )
                / len(krs)
                if krs
                else 0.0
            )
            with st.expander(
                f"🎯 {okr['objective'][:90]}… · {avg_pct:.0f}%",
                expanded=avg_pct < 80,
            ):
                st.markdown(f"**Цель:** {okr['objective']}")
                st.markdown(f"**Отдел:** {okr['department'] or 'Общий'}")
                st.markdown(f"**Период:** {okr['period']}")
                st.caption(f"Создано: {format_msk(okr['created_at'])}")
                st.progress(min(1.0, avg_pct / 100.0))
                if not krs:
                    st.info("Key Results ещё не заданы.")
                for k in krs:
                    pct = _okr_kr_progress(
                        k["current_value"], k["target_value"], k["kr_description"]
                    )
                    st.markdown(
                        f"**KR:** {k['kr_description']}  \n"
                        f"`{k['current_value']}` / `{k['target_value']}` {k['unit'] or ''} · **{pct:.0f}%**"
                    )
                    st.progress(min(1.0, pct / 100.0))
    else:
        st.warning(
            f"Нет OKR за период `{active_period}`. "
            "Запустите seed: `python -m okr_service` в knowledge_os/app или morning report."
        )
        # Show archive briefly
        archive = fetch_data(
            """
            SELECT objective, department, period, created_at
            FROM okrs WHERE period <> %s
            ORDER BY created_at DESC LIMIT 5
            """,
            (active_period,),
        )
        if archive:
            st.caption("Архив (не active):")
            for okr in archive:
                st.markdown(
                    f"- [{okr['period']}] {okr['objective'][:100]} "
                    f"({okr['department'] or '—'})"
                )


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
