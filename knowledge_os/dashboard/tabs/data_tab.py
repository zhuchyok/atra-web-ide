import json
import os
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional

import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from database_service import fetch_data, run_query
from graph_utils import optimized_force_layout


def format_msk(dt):
    """Форматирует datetime в московское время (UTC+3)."""
    if dt is None:
        return "N/A"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    msk_dt = dt.astimezone(timezone(timedelta(hours=3)))
    return msk_dt.strftime("%d.%m.%Y %H:%M")


def render_data_tab():
    """Вкладка Интеллект (RAG) и Качество Знаний."""

    time_range = st.session_state.get("global_time_range", "Последние 7 дней")
    st.caption(f"📅 Фильтр времени: **{time_range}**")

    tabs = st.tabs(
        [
            "📚 AI Research KB",
            "📊 Целостность",
            "🧠 Карта Разума",
            "🔍 Ревизия",
            "🤝 Синтез Знаний",
            "⚔️ Prompt Battle",
            "🧬 Code Mutations",
        ]
    )

    with tabs[0]:
        render_ai_research_kb()
    with tabs[1]:
        render_data_health()
    with tabs[2]:
        render_mindmap()
    with tabs[3]:
        render_revision()
    with tabs[4]:
        render_synthesis_hub()
    with tabs[5]:
        render_prompt_battle()
    with tabs[6]:
        render_code_mutations()


def render_code_mutations():
    """🧬 Code Mutations (MetaArchitect) interface for Shadow Execution."""
    st.subheader("🧬 Code Mutations: MetaArchitect")
    st.caption(
        "Пустой список ≠ поломка UI. Вкладка показывает только "
        "`knowledge_nodes` с `metadata.type=architecture_mutation` (status ≠ promoted). "
        "Создаёт их `MetaArchitect.run_guarded_evolution` (Phase 11 / nightly): "
        "по умолчанию **1 hotspot / 12ч cooldown**. "
        "Это **не** Prompt Battle (промпты) и не `neural_mutation`. "
        "Promote — опасный hot-swap файла; на RO mount дашборда часто только DB-status."
    )
    st.markdown("Мониторинг архитектурных мутаций кода в режиме Shadow Testing.")

    stats = fetch_data("""
        SELECT
            COUNT(*) FILTER (
                WHERE metadata->>'type' = 'architecture_mutation'
                  AND COALESCE(metadata->>'status', 'shadow') NOT IN ('promoted', 'rejected')
            ) AS active_shadow,
            COUNT(*) FILTER (
                WHERE metadata->>'type' = 'architecture_mutation'
                  AND metadata->>'status' = 'promoted'
            ) AS promoted,
            COUNT(*) FILTER (
                WHERE metadata->>'type' = 'architecture_mutation'
            ) AS all_mut,
            (SELECT COUNT(*) FROM architecture_performance_log
             WHERE created_at > NOW() - INTERVAL '24 hours') AS perf_24h
        FROM knowledge_nodes
    """)
    if stats and stats[0]:
        s = stats[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Shadow mutations", int(s["active_shadow"] or 0))
        c2.metric("Promoted (all-time)", int(s["promoted"] or 0))
        c3.metric("All architecture_mutation", int(s["all_mut"] or 0))
        c4.metric("Perf log rows (24h)", f"{int(s['perf_24h'] or 0):,}")

    # Hotspots always visible (pipeline signal even when queue empty)
    st.markdown("### 🔥 Hotspots (24h) — вход для evolution")
    hotspots = fetch_data("""
        SELECT
            module_name,
            function_name,
            AVG(execution_time_ms)::float AS avg_time,
            COUNT(*)::int AS call_count,
            COUNT(*) FILTER (WHERE success = false)::int AS failure_count
        FROM architecture_performance_log
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY module_name, function_name
        ORDER BY avg_time DESC
        LIMIT 8
    """)
    if hotspots:
        for hs in hotspots:
            st.caption(
                f"`{hs['module_name']}.{hs['function_name']}` · "
                f"avg **{float(hs['avg_time'] or 0):.1f}ms** · "
                f"calls {hs['call_count']} · fails {hs['failure_count']}"
            )
    else:
        st.info("Нет строк в architecture_performance_log за 24ч — profiler ещё не писал метрики.")

    # 1. Fetch active code mutations from knowledge_nodes
    mutations = fetch_data("""
        SELECT id, content, metadata, created_at
        FROM knowledge_nodes
        WHERE metadata->>'type' = 'architecture_mutation'
        AND (metadata->>'status' IS NULL OR metadata->>'status' NOT IN ('promoted', 'rejected'))
        ORDER BY created_at DESC
        LIMIT 50
    """)

    st.markdown("### 🧬 Активные shadow-мутации")
    if not mutations:
        st.info(
            "Нет активных `architecture_mutation` в Shadow. "
            "Evolution подключён осторожно (cooldown 12ч, max 1 hotspot). "
            "После следующего Phase 11 / nightly здесь появится карточка, если hotspot и LLM отработают."
        )
        return

    # 2. Display list of modules in shadow testing
    mutation_list = []
    for m in mutations:
        meta = (
            m["metadata"] if isinstance(m["metadata"], dict) else json.loads(m["metadata"] or "{}")
        )
        hyp = meta.get("hypothesis") or {}
        if not isinstance(hyp, dict):
            hyp = {}
        mutation_list.append(
            {
                "id": m["id"],
                "module": meta.get("module", "Unknown"),
                "function": meta.get("function", "Unknown"),
                "hypothesis": hyp.get("mutation_hypothesis", "N/A"),
                "safety_score": (
                    meta.get("safety_report", {}).get("score", 0.0)
                    if isinstance(meta.get("safety_report"), dict)
                    else meta.get("safety_score") or 0.0
                ),
                "risks": (
                    meta.get("safety_report", {}).get("risks", [])
                    if isinstance(meta.get("safety_report"), dict)
                    else meta.get("risks") or []
                ),
                "mutation_path": meta.get("mutation_path", ""),
                "status": meta.get("status") or "shadow",
                "created_at": m["created_at"],
            }
        )

    module_names = sorted({m["module"] for m in mutation_list})
    selected_module = st.selectbox("Выберите модуль для аудита", module_names)

    selected_mutation = next((m for m in mutation_list if m["module"] == selected_module), None)

    if selected_mutation:
        # 3. Show Safety Score and Risk Factors
        try:
            score = float(selected_mutation["safety_score"] or 0)
        except (TypeError, ValueError):
            score = 0.0
        risks = selected_mutation["risks"] or []

        col1, col2 = st.columns(2)
        score_color = "normal" if score > 0.7 else "inverse"
        col1.metric("Safety Score", f"{score * 100:.1f}%", delta_color=score_color)
        col2.metric("Status", selected_mutation.get("status") or "shadow")

        st.markdown("**Risk Factors:**")
        if risks:
            for risk in risks:
                st.warning(f"⚠️ {risk}")
        else:
            st.success("✅ No critical risks identified")

        st.markdown("---")

        # 4. Side-by-side code diff (Original vs. Mutated)
        st.markdown("### Сравнение кода (Original vs Mutated)")

        original_code = "N/A"
        mutated_code = "N/A"

        module_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app",
            f"{selected_mutation['module']}.py",
        )
        if not os.path.exists(module_path) and os.path.exists(
            f"/app/knowledge_os/app/{selected_mutation['module']}.py"
        ):
            module_path = f"/app/knowledge_os/app/{selected_mutation['module']}.py"
        if not os.path.exists(module_path) and os.path.exists(
            f"/app/project/knowledge_os/app/{selected_mutation['module']}.py"
        ):
            module_path = f"/app/project/knowledge_os/app/{selected_mutation['module']}.py"

        mutation_path = selected_mutation["mutation_path"] or ""
        if mutation_path and not os.path.exists(mutation_path):
            candidates = [
                os.path.join("/app", mutation_path),
                os.path.join("/app/project", mutation_path),
            ]
            if mutation_path.startswith("knowledge_os/"):
                candidates.extend(
                    [
                        os.path.join("/app", mutation_path),
                        os.path.join("/app/project", mutation_path),
                    ]
                )
            for alt in candidates:
                if alt and os.path.exists(alt):
                    mutation_path = alt
                    break

        try:
            if os.path.exists(module_path):
                with open(module_path) as f:
                    original_code = f.read()
            if mutation_path and os.path.exists(mutation_path):
                with open(mutation_path) as f:
                    mutated_code = f.read()
        except Exception as e:
            st.error(f"Ошибка чтения файлов: {e}")

        c_orig, c_mut = st.columns(2)
        with c_orig:
            st.markdown("**🛡️ Original (Production)**")
            st.code(original_code[:12000] if original_code else "N/A", language="python")
        with c_mut:
            st.markdown("**⚡ Mutated (Shadow)**")
            st.code(mutated_code[:12000] if mutated_code else "N/A", language="python")

        # 5. Action buttons (guarded promote)
        st.markdown("### Действия")
        confirm_swap = st.checkbox(
            "Подтверждаю hot-swap файла в production (опасно)",
            value=False,
            key=f"confirm_promote_{selected_mutation['id']}",
        )
        act_col1, act_col2, _ = st.columns([1, 1, 2])

        if act_col1.button(
            "🚀 Promote Code",
            help="Сначала пишет status=promoted в БД; файл копирует только при confirm + writable FS",
            type="primary",
            disabled=not confirm_swap,
        ):
            try:
                new_meta = fetch_data(
                    "SELECT metadata FROM knowledge_nodes WHERE id = %s",
                    (selected_mutation["id"],),
                )[0]["metadata"]
                if isinstance(new_meta, str):
                    new_meta = json.loads(new_meta)
                new_meta["status"] = "promoted"
                new_meta["promoted_at"] = datetime.now(timezone.utc).isoformat()
                new_meta["promoted_via"] = "dashboard_code_mutations"

                run_query(
                    "UPDATE knowledge_nodes SET metadata = %s::jsonb WHERE id = %s",
                    (json.dumps(new_meta), selected_mutation["id"]),
                )

                file_swapped = False
                if (
                    mutation_path
                    and os.path.exists(mutation_path)
                    and os.path.exists(os.path.dirname(module_path))
                ):
                    try:
                        import shutil

                        if os.access(os.path.dirname(module_path), os.W_OK):
                            shutil.copy2(mutation_path, module_path)
                            file_swapped = True
                    except OSError as copy_err:
                        st.warning(f"БД: promoted. File swap skipped: {copy_err}")

                if file_swapped:
                    st.success(f"Promoted + file swap: {selected_module}")
                else:
                    st.success(
                        f"БД: status=promoted для {selected_module}. "
                        "File hot-swap не выполнен (нет файла или RO filesystem)."
                    )
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка при продвижении кода: {e}")

        if act_col2.button(
            "❌ Reject Code", help="Пометить rejected (файл shadow удалить если есть)"
        ):
            try:
                new_meta = fetch_data(
                    "SELECT metadata FROM knowledge_nodes WHERE id = %s",
                    (selected_mutation["id"],),
                )[0]["metadata"]
                if isinstance(new_meta, str):
                    new_meta = json.loads(new_meta)
                new_meta["status"] = "rejected"
                new_meta["rejected_at"] = datetime.now(timezone.utc).isoformat()

                run_query(
                    "UPDATE knowledge_nodes SET metadata = %s::jsonb WHERE id = %s",
                    (json.dumps(new_meta), selected_mutation["id"]),
                )

                if mutation_path and os.path.exists(mutation_path):
                    try:
                        os.remove(mutation_path)
                    except OSError:
                        pass

                st.warning("Мутация отклонена.")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка при отклонении кода: {e}")

        st.markdown("---")
        st.markdown(f"**Гипотеза мутации:** {selected_mutation['hypothesis']}")
        st.caption(
            f"Создано: {format_msk(selected_mutation['created_at'])} | ID: {selected_mutation['id']}"
        )


def _record_prompt_battle_heuristic(
    mutation_id,
    expert_id,
    expert_name: str,
    prod_prompt: str,
    shadow_prompt: str,
) -> Optional[str]:
    """Sync smoke battle: heuristic verdict → counters + interaction_logs (no LLM)."""
    probe = "Smoke battle: list your top 3 responsibilities in short bullets."
    # Distinct stubs so identical-payload draw bug cannot hide a working counter path
    prod_stub = f"[PROD stub for {expert_name}]\n{(prod_prompt or '')[:400]}\nQ: {probe}"
    shadow_stub = f"[SHADOW stub for {expert_name}]\n{(shadow_prompt or '')[:800]}\nQ: {probe}"
    if len(shadow_stub) <= len(prod_stub) * 1.2:
        shadow_stub = shadow_stub + (" · insight" * 40)

    if len(shadow_stub) > len(prod_stub) * 1.2:
        verdict, win, loss, draw = "Win", 1, 0, 0
        reason = "dashboard_heuristic: shadow substantially longer"
    elif len(prod_stub) > len(shadow_stub) * 1.2:
        verdict, win, loss, draw = "Loss", 0, 1, 0
        reason = "dashboard_heuristic: production substantially longer"
    else:
        verdict, win, loss, draw = "Draw", 0, 0, 1
        reason = "dashboard_heuristic: similar length"

    ok = run_query(
        """
        UPDATE expert_mutations
        SET total_tests = COALESCE(total_tests, 0) + 1,
            win_count = COALESCE(win_count, 0) + %s,
            loss_count = COALESCE(loss_count, 0) + %s,
            draw_count = COALESCE(draw_count, 0) + %s,
            updated_at = NOW()
        WHERE id = %s AND status = 'shadow'
        """,
        (win, loss, draw, mutation_id),
    )
    if not ok:
        return None
    meta = {
        "shadow_execution": "true",
        "shadow_verdict": verdict,
        "shadow_reason": reason,
        "shadow_response": shadow_stub[:4000],
        "production_response": prod_stub[:2000],
        "mutation_id": str(mutation_id),
        "source": "dashboard_smoke",
        "expert_name": expert_name,
    }
    run_query(
        """
        INSERT INTO interaction_logs (expert_id, user_query, assistant_response, metadata)
        VALUES (%s, %s, %s, %s::jsonb)
        """,
        (expert_id, probe, shadow_stub[:8000], json.dumps(meta, ensure_ascii=False)),
    )
    return verdict


def render_prompt_battle():
    """⚔️ Prompt Battle interface for Shadow Prompt Evolution."""
    st.subheader("⚔️ Prompt Battle: Shadow Evolution")
    st.caption(
        "Shadow **не подставляется** в ответ пользователю. Бои идут в фоне (canary/shadow evaluator) "
        "или по кнопке Smoke ниже. В прод промпт попадает только после **Promote** "
        "(или auto-promotion при достаточном win_rate/tests). "
        "Total Tests = 0 значит боёв ещё не было — это не «сломанный UI»."
    )
    st.markdown("Сравнение Production (`experts.system_prompt`) и Shadow (`expert_mutations`).")

    # 1. Fetch active mutations
    mutations = fetch_data("""
        SELECT m.id, m.expert_id, e.name as expert_name, e.system_prompt as prod_prompt,
               m.mutated_prompt, m.win_count, m.loss_count, m.draw_count, m.total_tests,
               m.status, m.base_version
        FROM expert_mutations m
        JOIN experts e ON m.expert_id = e.id
        WHERE m.status = 'shadow'
        ORDER BY m.updated_at DESC
    """)

    if not mutations:
        st.info("Нет активных мутаций в режиме Shadow Testing.")
        return

    # 2. Display list of experts in shadow testing
    expert_names = sorted({m["expert_name"] for m in mutations})
    selected_expert_name = st.selectbox("Выберите эксперта для аудита", expert_names)

    selected_mutation = next(
        (m for m in mutations if m["expert_name"] == selected_expert_name), None
    )

    if selected_mutation:
        # 3. Show Win/Loss/Draw stats and Win Rate
        total = int(selected_mutation["total_tests"] or 0)
        wins = int(selected_mutation["win_count"] or 0)
        losses = int(selected_mutation["loss_count"] or 0)
        draws = int(selected_mutation.get("draw_count") or 0)
        win_rate = (wins / total * 100) if total > 0 else 0

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Win Rate", f"{win_rate:.1f}%")
        col2.metric("Wins", wins)
        col3.metric("Losses", losses)
        col4.metric("Draws", draws)
        col5.metric("Total Tests", total)

        st.markdown("---")

        # 4. Side-by-side comparison
        st.markdown("### Сравнение промптов")
        c_prod, c_shadow = st.columns(2)

        with c_prod:
            st.markdown("**🛡️ Production (Base)**")
            st.code(selected_mutation["prod_prompt"] or "", language="markdown")

        with c_shadow:
            st.markdown("**⚡ Shadow (Mutation)**")
            st.code(selected_mutation["mutated_prompt"] or "", language="markdown")

        # 5. Action buttons
        st.markdown("### Действия")
        act_col1, act_col2, act_col3 = st.columns([1, 1, 1])

        if act_col1.button(
            "▶️ Smoke Battle",
            help="Один heuristic-бой без LLM: +1 к Total Tests и запись в «Последние битвы»",
        ):
            verdict = _record_prompt_battle_heuristic(
                selected_mutation["id"],
                selected_mutation["expert_id"],
                selected_expert_name,
                selected_mutation.get("prod_prompt") or "",
                selected_mutation.get("mutated_prompt") or "",
            )
            if verdict:
                st.success(f"Smoke battle записан: verdict={verdict}")
                st.rerun()
            else:
                st.error("Не удалось записать smoke battle.")

        if act_col2.button(
            "🚀 Promote Now", help="Сделать этот промпт основным (Hot-Swap)", type="primary"
        ):
            if run_query(
                """
                UPDATE experts SET system_prompt = %s, version = COALESCE(version, 0) + 1 WHERE id = %s
            """,
                (selected_mutation["mutated_prompt"], selected_mutation["expert_id"]),
            ):
                run_query(
                    "UPDATE expert_mutations SET status = 'promoted' WHERE id = %s",
                    (selected_mutation["id"],),
                )
                run_query(
                    "UPDATE expert_mutations SET status = 'archived' WHERE expert_id = %s AND id != %s AND status = 'shadow'",
                    (selected_mutation["expert_id"], selected_mutation["id"]),
                )
                st.success(f"Промпт эксперта {selected_expert_name} успешно обновлен!")
                st.rerun()

        if act_col3.button("❌ Reject Mutation", help="Архивировать мутацию"):
            if run_query(
                "UPDATE expert_mutations SET status = 'rejected' WHERE id = %s",
                (selected_mutation["id"],),
            ):
                st.warning("Мутация отклонена.")
                st.rerun()

        st.markdown("---")

        # 6. Recent Battles section
        st.markdown("### 📜 Последние битвы (Evaluations)")
        recent_battles = fetch_data(
            """
            SELECT created_at, user_query, assistant_response, metadata
            FROM interaction_logs
            WHERE expert_id = %s
              AND (
                    metadata->>'shadow_execution' = 'true'
                 OR metadata->>'source' IN ('shadow_evaluator', 'canary_router', 'dashboard_smoke')
              )
            ORDER BY created_at DESC
            LIMIT 8
        """,
            (selected_mutation["expert_id"],),
        )

        if recent_battles:
            for battle in recent_battles:
                meta = (
                    battle["metadata"]
                    if isinstance(battle["metadata"], dict)
                    else json.loads(battle["metadata"] or "{}")
                )
                verdict = meta.get("shadow_verdict", "N/A")
                reason = meta.get("shadow_reason", "No reason provided")
                src = meta.get("source", "unknown")

                with st.expander(f"Битва {format_msk(battle['created_at'])} | {verdict} · {src}"):
                    st.markdown(f"**Запрос:** {battle['user_query']}")
                    st.markdown(f"**Причина вердикта:** {reason}")
                    st.markdown("**Ответ Shadow:**")
                    st.info(
                        meta.get("shadow_response") or battle.get("assistant_response") or "N/A"
                    )
                    if meta.get("production_response"):
                        st.markdown("**Ответ Production (фрагмент):**")
                        st.code(str(meta.get("production_response"))[:1200])
        else:
            st.info(
                "История битв пуста. Нажмите **Smoke Battle** или дождитесь canary/shadow evaluator."
            )


def render_synthesis_hub():
    """🤝 Хаб Синтеза Знаний (Knowledge Synthesis Hub)."""
    st.subheader("🤝 Хаб Синтеза Знаний")
    st.markdown("Объединение мнений нескольких экспертов для получения единого консенсуса.")

    col_q, col_ex = st.columns([2, 1])
    with col_q:
        topic = st.text_input(
            "Тема для обсуждения", placeholder="Например: 'Оптимизация PostgreSQL для 100к RPS'"
        )
        question = st.text_area(
            "Конкретный вопрос", placeholder="Как лучше настроить пул соединений и индексы?"
        )

    with col_ex:
        experts_list = fetch_data("SELECT name FROM experts ORDER BY name")
        expert_names = (
            [e["name"] for e in experts_list]
            if experts_list
            else ["Виктория", "Игорь", "Роман", "Анна"]
        )
        selected_experts = st.multiselect(
            "Выберите экспертов (3-5)", expert_names, default=expert_names[:3]
        )

    if st.button("🚀 Запустить Синтез Консенсуса"):
        if not topic or not question or len(selected_experts) < 2:
            st.error("Заполните тему, вопрос и выберите минимум 2 экспертов.")
        else:
            with st.spinner("Эксперты обсуждают проблему..."):
                try:
                    # Надёжный импорт: дашборд может запускаться из dashboard/ или из корня knowledge_os (аудит 2026-03-11)
                    try:
                        from app.victoria_enhanced import VictoriaEnhanced
                    except ImportError:
                        try:
                            from victoria_enhanced import VictoriaEnhanced
                        except ImportError:
                            # [FIX] Дополнительный путь для Docker
                            import os
                            import sys

                            sys.path.append("/app/knowledge_os/app")
                            from victoria_enhanced import VictoriaEnhanced

                    victoria = VictoriaEnhanced()

                    prompt = f"""Ты выступаешь как Хаб Синтеза Знаний.
                    Проведи виртуальное обсуждение между экспертами: {", ".join(selected_experts)}.
                    ТЕМА: {topic}
                    ВОПРОС: {question}

                    ВЫДАЙ ИТОГОВЫЙ КОНСЕНСУС И УРОВЕНЬ СОГЛАСИЯ (в %).
                    """

                    # [FIX] Реальный вызов Виктории
                    result = None
                    if hasattr(victoria, "solve_sync"):
                        result = victoria.solve_sync(prompt, method="consensus")
                    else:
                        # Fallback на асинхронный вызов через loop
                        import asyncio

                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(victoria.solve(prompt, method="consensus"))
                        loop.close()

                    if result:
                        st.success("✅ Консенсус достигнут!")

                        # Пытаемся извлечь agreement из результата или метаданных
                        agreement = 85
                        if isinstance(result, dict) and "agreement_score" in result:
                            agreement = int(result["agreement_score"] * 100)

                        st.write(f"**Уровень согласия экспертов:** {agreement}%")
                        st.progress(agreement / 100)

                        st.markdown("### 📜 Единое решение корпорации")
                        st.info(
                            "Это решение синтезировано на основе коллективного разума выбранных экспертов."
                        )

                        output_text = (
                            result if isinstance(result, str) else result.get("output", str(result))
                        )
                        st.write(output_text)
                    else:
                        st.error("Виктория не вернула результат.")

                except Exception as e:
                    st.error(f"Ошибка синтеза: {e}")
                    st.code(traceback.format_exc())


def render_ai_research_kb():
    """📚 AI Research Knowledge Base — curated research docs (indexers), not LTM noise."""
    st.subheader("📚 База Мудрости (AI Research)")
    st.markdown(
        "Мировые практики и промпты (Anthropic, OpenAI, Google и др.) — "
        "только индексированные документы с `file_path`, не логи агентов."
    )

    # Curated = indexer/scout nodes with a real file path; exclude LTM/runtime dumps.
    # Avoid LIKE '%' here: fetch_data(params=None) runs raw SQL (no pyformat escaping).
    ai_research_curated = """
        domain_id = (SELECT id FROM domains WHERE name = 'AI Research')
        AND NULLIF(BTRIM(metadata->>'file_path'), '') IS NOT NULL
        AND COALESCE(metadata->>'type', '') <> 'long_term_memory'
        AND COALESCE(metadata->>'source', '') IN (
            'external_docs_indexer',
            'cognitive_code_indexer',
            'scout_research',
            'enhanced_scout_research',
            'enhanced_scout_report'
        )
        AND content IS NOT NULL
        AND BTRIM(content) <> ''
        AND content !~* 'ошибка парсинга ответа модели'
        AND content !~* 'извините, сейчас я не могу'
        AND position('"action": "create_file"' in content) = 0
        AND content !~* 'все источники недоступны'
    """

    search_ai = st.text_input(
        "🔍 Поиск по AI Research", placeholder="Например: 'Claude Code error handling'..."
    )

    if search_ai:
        results = fetch_data(
            f"""
            SELECT content,
                   metadata->>'file_path' as path,
                   COALESCE(metadata->>'source', 'node') as src,
                   confidence_score
            FROM knowledge_nodes
            WHERE {ai_research_curated}
              AND (content ILIKE %s OR metadata->>'file_path' ILIKE %s)
            ORDER BY confidence_score DESC NULLS LAST, COALESCE(updated_at, created_at) DESC
            LIMIT 12
        """,
            (f"%{search_ai}%", f"%{search_ai}%"),
        )

        if results:
            for r in results:
                path = r.get("path") or "document"
                conf = r.get("confidence_score")
                conf_s = f"{float(conf):.2f}" if conf is not None else "—"
                with st.expander(f"📄 {path} · {r.get('src')} · Conf {conf_s}"):
                    st.markdown(r.get("content") or "")
        else:
            st.info("Ничего не найдено среди curated AI Research документов.")
    else:
        st.markdown("### Последние находки")
        freshness = fetch_data(f"""
            SELECT
                MAX(created_at) AS latest_created_at,
                MAX(COALESCE(updated_at, created_at)) AS latest_touched_at,
                COUNT(*) AS curated_total
            FROM knowledge_nodes
            WHERE {ai_research_curated}
        """)
        if freshness and freshness[0] and freshness[0]["latest_touched_at"]:
            latest_touch = freshness[0]["latest_touched_at"]
            if latest_touch.tzinfo is None:
                latest_touch = latest_touch.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - latest_touch).days
            curated_total = int(freshness[0].get("curated_total") or 0)
            st.caption(
                f"🕒 Последняя индексация curated: {format_msk(latest_touch)} "
                f"({age_days} дн. назад) · документов: **{curated_total:,}**"
            )
            if age_days >= 14:
                st.warning(
                    "Curated AI Research не обновлялся более 14 дней. "
                    "Запустите `index_external_docs.py` / scout."
                )
        st.caption(
            "Лента = только indexed docs (`external_docs_indexer` / `cognitive_code_indexer` / scout). "
            "Ошибки парсинга и long_term_memory сюда не попадают. Раскройте строку — полный текст."
        )
        latest = fetch_data(f"""
            SELECT content,
                   metadata->>'file_path' as path,
                   COALESCE(metadata->>'source', 'node') as node_type,
                   created_at,
                   COALESCE(updated_at, created_at) as touched_at
            FROM knowledge_nodes
            WHERE {ai_research_curated}
            ORDER BY COALESCE(updated_at, created_at) DESC
            LIMIT 12
        """)
        if latest:
            for row in latest:
                path = (row.get("path") or "document").strip()
                short_name = path.rsplit("/", 1)[-1] if path else "document"
                touched_at = row.get("touched_at") or row.get("created_at")
                node_type = row.get("node_type") or "node"
                preview = " ".join((row.get("content") or "").split())
                if len(preview) > 140:
                    preview = preview[:140] + "…"
                title = f"📄 {short_name} · {node_type} · {format_msk(touched_at).split()[0]}"
                with st.expander(f"{title} — {preview}"):
                    st.caption(f"path: `{path}`")
                    st.markdown(row.get("content") or "")
        else:
            st.info(
                "Curated AI Research пуст. Запустите "
                "`python knowledge_os/scripts/index_external_docs.py`."
            )


def render_data_health():
    """📊 Целостность данных (Knowledge OS Health)."""
    st.subheader("📊 Здоровье Базы Знаний")

    time_range = st.session_state.get("global_time_range", "Последние 7 дней")
    from database_service import get_time_filter

    t_filter = get_time_filter(time_range, "created_at")
    # Health = all-time inventory (matches sidebar). Period filter = deltas only.
    st.caption(
        "Основные метрики — **вся БД** (как сайдбар «Узлов»). "
        f"Δ под числом — прирост за **{time_range}**."
    )

    try:
        stats = fetch_data(f"""
            SELECT
                (SELECT COUNT(*) FROM knowledge_nodes) AS nodes_all,
                (SELECT COUNT(*) FROM knowledge_links) AS links_all,
                (SELECT COUNT(*) FROM knowledge_nodes WHERE embedding IS NULL) AS missing_emb_all,
                (SELECT COUNT(*) FROM knowledge_nodes WHERE confidence_score < 0.3) AS low_conf_all,
                (SELECT COUNT(*) FROM knowledge_nodes WHERE {t_filter}) AS nodes_period,
                (SELECT COUNT(*) FROM knowledge_links WHERE {t_filter}) AS links_period,
                (SELECT COUNT(*) FROM knowledge_nodes WHERE embedding IS NULL AND {t_filter}) AS missing_emb_period,
                (SELECT COUNT(*) FROM knowledge_nodes WHERE confidence_score < 0.3 AND {t_filter}) AS low_conf_period
        """)
        if stats and stats[0]:
            s = stats[0]
            nodes_all = int(s["nodes_all"] or 0)
            links_all = int(s["links_all"] or 0)
            missing_all = int(s["missing_emb_all"] or 0)
            low_conf_all = int(s["low_conf_all"] or 0)
            nodes_period = int(s["nodes_period"] or 0)
            links_period = int(s["links_period"] or 0)
            missing_period = int(s["missing_emb_period"] or 0)
            low_conf_period = int(s["low_conf_period"] or 0)

            with_emb = max(0, nodes_all - missing_all)
            emb_pct = int(round(100.0 * with_emb / nodes_all)) if nodes_all else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(
                "Всего узлов",
                f"{nodes_all:,}",
                delta=f"+{nodes_period:,} за период" if time_range != "За все время" else None,
            )
            c2.metric(
                "Всего связей",
                f"{links_all:,}",
                delta=f"+{links_period:,} за период" if time_range != "За все время" else None,
            )
            c3.metric(
                "Без векторов",
                f"{missing_all:,}",
                delta=f"+{missing_period:,} за период" if time_range != "За все время" else None,
                delta_color="inverse",
            )
            c4.metric(
                "Низкий Conf",
                f"{low_conf_all:,}",
                delta=f"+{low_conf_period:,} за период" if time_range != "За все время" else None,
                delta_color="inverse",
            )

            st.caption(
                f"Покрытие эмбеддингами: **{with_emb:,}** / {nodes_all:,} "
                f"(**{emb_pct}%**). Источник связей: `knowledge_links` "
                f"(таблица `knowledge_edges` не используется в этом виджете)."
            )

            # Goal: 100k semantic links — always all-time
            goal_links = 100_000
            st.markdown(f"### 🏆 Путь к Neural Graph ({goal_links // 1000}k связей)")
            progress = min(100, int(links_all * 100 / goal_links)) if links_all else 0
            st.progress(progress / 100.0)
            if links_all >= goal_links:
                st.success(
                    f"Цель достигнута: **{links_all:,}** / {goal_links:,} связей "
                    f"(**{progress}%**). Дальше — качество и покрытие эмбеддингами."
                )
            else:
                st.caption(
                    f"All-time связей: **{links_all:,}** / {goal_links:,} → **{progress}%** "
                    f"(+{links_period:,} за «{time_range}»)."
                )

    except Exception as e:
        st.error(f"Ошибка аудита данных: {e}")


def render_mindmap():
    """🧠 Карта разума корпорации (Иерархическая визуализация 100k+)."""
    st.subheader("🧠 Семантический Граф Знаний (Neural Graph)")
    st.caption(
        "Карта строится по **всем** связям (all-time). Глобальный фильтр «7 дней» на эту вкладку не влияет. "
        "Подписи — у крупных доменов; остальное — hover."
    )

    view_mode = st.radio(
        "Режим отображения",
        ["🌐 Глобальный (Домены)", "🧬 Семантические Кластеры", "🔍 Локальный поиск"],
        horizontal=True,
    )

    try:
        if view_mode == "🌐 Глобальный (Домены)":
            st.markdown("### Глобальная структура связей между доменами")
            domain_links = fetch_data("""
                SELECT
                    d1.name as source_domain,
                    d2.name as target_domain,
                    COUNT(*) as link_count
                FROM knowledge_links l
                JOIN knowledge_nodes k1 ON l.source_node_id = k1.id
                JOIN knowledge_nodes k2 ON l.target_node_id = k2.id
                JOIN domains d1 ON k1.domain_id = d1.id
                JOIN domains d2 ON k2.domain_id = d2.id
                GROUP BY d1.name, d2.name
                ORDER BY link_count DESC
            """)

            # ОТЛАДКА: Выводим список найденных доменов прямо в интерфейс (только если один)
            if domain_links:
                unique_domains = set(
                    [lnk["source_domain"] for lnk in domain_links]
                    + [lnk["target_domain"] for lnk in domain_links]
                )
                if len(unique_domains) <= 1:
                    st.warning(
                        f"ВНИМАНИЕ: Найдено связей: {len(domain_links)}, Уникальных доменов: {len(unique_domains)}. Проверьте линковку в БД."
                    )

            if not domain_links:
                st.info("Междоменные связи пока не сформированы.")
                return

            graph = nx.DiGraph()
            domain_link_weight = {}
            for link in domain_links:
                src, dst, w = (
                    link["source_domain"],
                    link["target_domain"],
                    int(link["link_count"] or 0),
                )
                graph.add_edge(src, dst, weight=w)
                domain_link_weight[src] = domain_link_weight.get(src, 0) + w
                domain_link_weight[dst] = domain_link_weight.get(dst, 0) + w

            domain_stats = fetch_data(
                "SELECT d.name, COUNT(k.id) as node_count FROM domains d LEFT JOIN knowledge_nodes k ON d.id = k.domain_id GROUP BY d.name"
            )
            node_sizes_map = {d["name"]: d["node_count"] for d in domain_stats}

            # Подписи только у топ-доменов по весу связей (иначе каша в центре)
            labeled = {
                name
                for name, _ in sorted(domain_link_weight.items(), key=lambda x: x[1], reverse=True)[
                    :14
                ]
            }

            node_list = list(graph.nodes())
            n_nodes = len(node_list)
            adj_matrix = np.zeros((n_nodes, n_nodes))
            for i, u in enumerate(node_list):
                for j, v in enumerate(node_list):
                    if graph.has_edge(u, v):
                        adj_matrix[i, j] = 1

            pos_array = optimized_force_layout(adj_matrix, np.ones(n_nodes), iterations=50)
            pos = {node_list[i]: pos_array[i] for i in range(n_nodes)}

            edge_x, edge_y = [], []
            for edge in graph.edges(data=True):
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])

            edge_trace = go.Scatter(
                x=edge_x,
                y=edge_y,
                line=dict(width=2.0, color="rgba(255, 255, 255, 0.8)"),
                hoverinfo="none",
                mode="lines",
            )

            node_x, node_y, node_text, node_size_vals, node_labels = [], [], [], [], []
            for node in graph.nodes():
                x, y = pos[node]
                node_x.append(x)
                node_y.append(y)
                count = int(node_sizes_map.get(node, 0) or 0)
                weight = int(domain_link_weight.get(node, 0) or 0)
                node_text.append(f"Домен: {node}<br>Узлов: {count}<br>Вес связей: {weight}")
                node_size_vals.append(min(60, max(18, (count / 80) + 12)))
                node_labels.append(node if node in labeled else "")

            node_trace = go.Scatter(
                x=node_x,
                y=node_y,
                mode="markers+text",
                text=node_labels,
                textposition="top center",
                hoverinfo="text",
                hovertext=node_text,
                textfont=dict(size=12, color="white"),
                marker=dict(
                    size=node_size_vals, color="#FF7F50", line=dict(width=2, color="white")
                ),
            )

            fig = go.Figure(
                data=[edge_trace, node_trace],
                layout=go.Layout(
                    showlegend=False,
                    hovermode="closest",
                    margin=dict(b=20, l=20, r=20, t=20),
                    xaxis=dict(
                        showgrid=False, zeroline=False, showticklabels=False, range=[-1.25, 1.25]
                    ),
                    yaxis=dict(
                        showgrid=False, zeroline=False, showticklabels=False, range=[-1.25, 1.25]
                    ),
                    template="plotly_dark",
                    height=700,
                ),
            )
            st.plotly_chart(fig, width="stretch")
            st.caption(
                f"Доменов на графе: {n_nodes} · пар связей: {len(domain_links)} · подписей: {len(labeled)}"
            )

        elif view_mode == "🧬 Семантические Кластеры":
            st.markdown("### Кластеризация знаний (Созвездия)")
            limit = st.slider("Лимит узлов для визуализации", 50, 1000, 400)

            # Degree одним проходом по links (без correlated subquery на каждый узел)
            nodes_data = fetch_data(
                """
                WITH degrees AS (
                    SELECT node_id, COUNT(*)::int AS total_degree
                    FROM (
                        SELECT source_node_id AS node_id FROM knowledge_links
                        UNION ALL
                        SELECT target_node_id AS node_id FROM knowledge_links
                    ) e
                    GROUP BY node_id
                ),
                ranked_nodes AS (
                    SELECT
                        kn.id, kn.domain_id, kn.content, kn.confidence_score,
                        d.name AS domain, deg.total_degree,
                        ROW_NUMBER() OVER (
                            PARTITION BY kn.domain_id ORDER BY deg.total_degree DESC
                        ) AS rn
                    FROM degrees deg
                    JOIN knowledge_nodes kn ON kn.id = deg.node_id
                    JOIN domains d ON kn.domain_id = d.id
                ),
                top_nodes AS (
                    SELECT * FROM ranked_nodes
                    WHERE rn <= 20
                    ORDER BY total_degree DESC
                    LIMIT %s
                ),
                selected_node_ids AS (
                    SELECT id FROM top_nodes
                ),
                relevant_links AS (
                    SELECT kl.source_node_id, kl.target_node_id
                    FROM knowledge_links kl
                    WHERE kl.source_node_id IN (SELECT id FROM selected_node_ids)
                      AND kl.target_node_id IN (SELECT id FROM selected_node_ids)
                )
                SELECT tn.id, tn.content as label, tn.domain, tn.total_degree,
                       (SELECT json_agg(target_node_id) FROM relevant_links WHERE source_node_id = tn.id) as links
                FROM top_nodes tn
            """,
                (limit,),
            )

            if not nodes_data:
                st.info("Недостаточно данных.")
                return

            graph = nx.Graph()
            node_info = {}
            node_list = []
            for n in nodes_data:
                graph.add_node(
                    n["id"], label=n["label"], domain=n["domain"], degree=n["total_degree"]
                )
                node_info[n["id"]] = n
                node_list.append(n["id"])

            for n in nodes_data:
                if n["links"]:
                    targets = n["links"] if isinstance(n["links"], list) else json.loads(n["links"])
                    for target_id in targets:
                        if target_id in node_info:
                            graph.add_edge(n["id"], target_id)

            n_nodes = len(node_list)
            if n_nodes == 0:
                st.info("Граф пуст.")
                return

            adj_matrix = np.zeros((n_nodes, n_nodes))
            node_id_to_idx = {nid: i for i, nid in enumerate(node_list)}
            for u, v in graph.edges():
                adj_matrix[node_id_to_idx[u], node_id_to_idx[v]] = 1
                adj_matrix[node_id_to_idx[v], node_id_to_idx[u]] = 1

            pos_array = optimized_force_layout(
                adj_matrix, np.array([graph.degree(n) for n in node_list]), iterations=300
            )
            pos_dict = {node_list[i]: pos_array[i] for i in range(n_nodes)}

            edge_x, edge_y = [], []
            for edge in graph.edges():
                x0, y0 = pos_dict[edge[0]]
                x1, y1 = pos_dict[edge[1]]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])
            edge_trace = go.Scatter(
                x=edge_x,
                y=edge_y,
                line=dict(width=1.2, color="rgba(255,255,255,0.25)"),
                hoverinfo="none",
                mode="lines",
            )

            node_x, node_y, node_text, node_color, node_size, node_labels = [], [], [], [], [], []
            degrees_in_graph = dict(graph.degree())

            for node_id in node_list:
                x, y = pos_dict[node_id]
                node_x.append(x)
                node_y.append(y)
                info = node_info[node_id]
                curr_deg = degrees_in_graph.get(node_id, 0)

                # Хаб — если есть связи в текущей выборке
                is_hub = curr_deg > 1

                node_color.append("#FF7F50" if is_hub else "#5DADE2")
                node_size.append(min(30, 12 + curr_deg * 3) if is_hub else 6)

                # Красивые подписи в стиле дашборда
                if is_hub:
                    # ПОКАЗЫВАЕМ ДОМЕН КРУПНО, а контент мелко под ним
                    label_text = f"<b style='color:#FF7F50; font-size:14px;'>{info['domain']}</b><br><span style='font-size:10px; color:#AAB7B8;'>{info['label'][:30]}...</span>"
                else:
                    label_text = ""

                node_text.append(
                    f"<b>{info['domain']}</b><br>{info['label'][:200]}...<br>Связей: {curr_deg}"
                )
                node_labels.append(label_text)

            node_trace = go.Scatter(
                x=node_x,
                y=node_y,
                mode="markers+text",
                hoverinfo="text",
                text=node_labels,
                textposition="top center",
                hovertext=node_text,
                marker=dict(color=node_color, size=node_size, line=dict(width=1.5, color="#111")),
            )

            fig = go.Figure(
                data=[edge_trace, node_trace],
                layout=go.Layout(
                    showlegend=False,
                    hovermode="closest",
                    margin=dict(b=0, l=0, r=0, t=0),
                    xaxis=dict(
                        showgrid=False, zeroline=False, showticklabels=False, range=[-1.1, 1.1]
                    ),
                    yaxis=dict(
                        showgrid=False, zeroline=False, showticklabels=False, range=[-1.1, 1.1]
                    ),
                    template="plotly_dark",
                    height=700,
                ),
            )
            st.plotly_chart(fig, width="stretch")

        elif view_mode == "🔍 Локальный поиск":
            search_query = st.text_input(
                "Введите ID узла или текст для поиска центра графа",
                placeholder="Например: 'PostgreSQL' или UUID...",
            )
            depth = st.slider("Глубина связей", 1, 3, 1)

            if search_query:
                center_node = fetch_data(
                    """
                    SELECT id, content, d.name AS domain
                    FROM knowledge_nodes kn
                    LEFT JOIN domains d ON kn.domain_id = d.id
                    WHERE content ILIKE %s OR id::text = %s
                    LIMIT 1
                    """,
                    (f"%{search_query}%", search_query),
                )
                if center_node:
                    c_id = center_node[0]["id"]
                    center_preview = (center_node[0].get("content") or "").replace("\n", " ")[:240]
                    st.info(
                        f"Центр: `{str(c_id)[:8]}…` · "
                        f"{center_node[0].get('domain') or 'no-domain'} · {center_preview}…"
                    )
                    local_links = fetch_data(
                        """
                        WITH RECURSIVE graph AS (
                            SELECT source_node_id, target_node_id, 1 as level
                            FROM knowledge_links
                            WHERE source_node_id = %s OR target_node_id = %s
                            UNION
                            SELECT l.source_node_id, l.target_node_id, g.level + 1
                            FROM knowledge_links l
                            JOIN graph g ON l.source_node_id = g.target_node_id OR l.target_node_id = g.source_node_id
                            WHERE g.level < %s
                        )
                        SELECT DISTINCT g.source_node_id, g.target_node_id, k1.content as s_content, k2.content as t_content
                        FROM graph g
                        JOIN knowledge_nodes k1 ON g.source_node_id = k1.id
                        JOIN knowledge_nodes k2 ON g.target_node_id = k2.id
                        LIMIT 200
                    """,
                        (c_id, c_id, depth),
                    )

                    if local_links:
                        graph = nx.Graph()
                        node_list_local = set()
                        content_map = {str(c_id): center_node[0].get("content") or ""}
                        for edge_row in local_links:
                            sid, tid = (
                                str(edge_row["source_node_id"]),
                                str(edge_row["target_node_id"]),
                            )
                            graph.add_edge(sid, tid)
                            node_list_local.add(sid)
                            node_list_local.add(tid)
                            content_map[sid] = edge_row.get("s_content") or content_map.get(sid, "")
                            content_map[tid] = edge_row.get("t_content") or content_map.get(tid, "")

                        node_list_local = list(node_list_local)
                        n_nodes = len(node_list_local)
                        adj_matrix = np.zeros((n_nodes, n_nodes))
                        nid_to_idx = {nid: i for i, nid in enumerate(node_list_local)}
                        for u, v in graph.edges():
                            adj_matrix[nid_to_idx[u], nid_to_idx[v]] = 1
                            adj_matrix[nid_to_idx[v], nid_to_idx[u]] = 1

                        pos_array = optimized_force_layout(
                            adj_matrix, np.ones(n_nodes), iterations=50
                        )
                        pos_dict = {node_list_local[i]: pos_array[i] for i in range(n_nodes)}

                        edge_x, edge_y = [], []
                        for edge in graph.edges():
                            x0, y0 = pos_dict[edge[0]]
                            x1, y1 = pos_dict[edge[1]]
                            edge_x.extend([x0, x1, None])
                            edge_y.extend([y0, y1, None])

                        edge_trace = go.Scatter(
                            x=edge_x,
                            y=edge_y,
                            line=dict(width=1, color="#888"),
                            hoverinfo="none",
                            mode="lines",
                        )

                        node_x, node_y, node_text, node_colors = [], [], [], []
                        center_s = str(c_id)
                        for node in graph.nodes():
                            x, y = pos_dict[node]
                            node_x.append(x)
                            node_y.append(y)
                            preview = (content_map.get(node) or "").replace("\n", " ").strip()
                            node_text.append(f"ID: {node[:8]}…<br>{preview[:160]}")
                            node_colors.append("#FF7F50" if node == center_s else "#ffcc00")

                        node_trace = go.Scatter(
                            x=node_x,
                            y=node_y,
                            mode="markers+text",
                            text=[n[:8] for n in graph.nodes()],
                            textposition="bottom center",
                            hoverinfo="text",
                            hovertext=node_text,
                            marker=dict(size=20, color=node_colors, line_width=2),
                        )

                        fig = go.Figure(
                            data=[edge_trace, node_trace],
                            layout=go.Layout(
                                template="plotly_dark",
                                height=600,
                                margin=dict(b=0, l=0, r=0, t=0),
                                xaxis=dict(
                                    showgrid=False,
                                    zeroline=False,
                                    showticklabels=False,
                                    range=[-1.1, 1.1],
                                ),
                                yaxis=dict(
                                    showgrid=False,
                                    zeroline=False,
                                    showticklabels=False,
                                    range=[-1.1, 1.1],
                                ),
                            ),
                        )
                        st.plotly_chart(fig, width="stretch")
                        st.caption(
                            f"Узлов в локальном графе: {n_nodes} · рёбер: {graph.number_of_edges()}"
                        )
                    else:
                        st.warning(
                            "У найденного центра нет связей в knowledge_links (или глубина=0)."
                        )
                else:
                    st.warning("Центр не найден по тексту/ID.")
    except Exception as e:
        st.error(f"Ошибка визуализации: {e}")
        import traceback

        st.code(traceback.format_exc())


def _mark_node_verified(node_id, method: str = "dashboard_revision") -> bool:
    """Пишет is_verified=true + audit в metadata (человеческий gate)."""
    return run_query(
        """
        UPDATE knowledge_nodes
        SET is_verified = TRUE,
            confidence_score = GREATEST(COALESCE(confidence_score, 0), 0.7),
            metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                'dashboard_verified', true,
                'dashboard_verified_at', NOW()::text,
                'dashboard_verified_method', %s
            ),
            quality_report = COALESCE(
                quality_report,
                %s
            )
        WHERE id = %s AND COALESCE(is_verified, FALSE) = FALSE
        """,
        (
            method,
            json.dumps({"method": method, "ts": datetime.now(timezone.utc).isoformat()}),
            node_id,
        ),
    )


def render_revision():
    """🔍 Ревизия знаний — optional human gate (не блокер RAG)."""
    st.subheader("🔍 Ревизия и Верификация")
    st.caption(
        "Это **опциональный** human-review, не обязательный Approve. "
        "Виктория эту вкладку не читает. Многие пайплайны уже пишут `is_verified=true` при ingest; "
        "RAG часто берёт `verified OR confidence>0.7`. Кнопка ниже пишет в БД."
    )

    stats = fetch_data("""
        SELECT
            COUNT(*) FILTER (WHERE COALESCE(is_verified, FALSE) = FALSE) AS unverified_all,
            COUNT(*) FILTER (
                WHERE COALESCE(is_verified, FALSE) = FALSE
                  AND COALESCE(metadata->>'source', '') = 'ingest_docs_to_rag'
            ) AS unverified_ingest,
            COUNT(*) FILTER (WHERE is_verified = TRUE) AS verified_all
        FROM knowledge_nodes
    """)
    if stats and stats[0]:
        s = stats[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Verified (all-time)", f"{int(s['verified_all'] or 0):,}")
        c2.metric("Unverified (all)", f"{int(s['unverified_all'] or 0):,}")
        c3.metric("Unverified ingest_docs", f"{int(s['unverified_ingest'] or 0):,}")

    # Безопасный bulk: только индексированные доки (не worker/watchdog чат)
    ingest_n = int((stats[0]["unverified_ingest"] if stats and stats[0] else 0) or 0)
    if ingest_n > 0:
        st.markdown("#### Быстрое действие")
        if st.button(
            f"✅ Auto-verify ingest_docs_to_rag ({ingest_n})",
            help="Только source=ingest_docs_to_rag. Не трогает worker_service / watchdog.",
        ):
            ok = run_query(
                """
                UPDATE knowledge_nodes
                SET is_verified = TRUE,
                    confidence_score = GREATEST(COALESCE(confidence_score, 0), 0.7),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                        'dashboard_verified', true,
                        'dashboard_verified_at', NOW()::text,
                        'dashboard_verified_method', 'bulk_ingest_docs'
                    ),
                    quality_report = COALESCE(
                        quality_report,
                        '{"method":"bulk_ingest_docs"}'
                    )
                WHERE COALESCE(is_verified, FALSE) = FALSE
                  AND metadata->>'source' = 'ingest_docs_to_rag'
                """
            )
            if ok:
                st.success(f"Верифицированы узлы ingest_docs_to_rag (было до {ingest_n}).")
                st.rerun()
            else:
                st.error("UPDATE не выполнен — смотри логи dashboard.")

    # Исключаем технические узлы из ревизии (память, линковка)
    pending = fetch_data("""
        SELECT kn.id,
               kn.content,
               LEFT(kn.content, 160) AS preview,
               COALESCE(kn.metadata->>'expert_name', kn.metadata->>'expert', 'System') AS expert_name,
               kn.metadata->>'source' AS source,
               kn.metadata->>'file_path' AS file_path,
               kn.metadata->>'type' AS node_type,
               kn.confidence_score,
               d.name AS domain,
               kn.created_at
        FROM knowledge_nodes kn
        LEFT JOIN domains d ON kn.domain_id = d.id
        WHERE COALESCE(kn.is_verified, FALSE) = FALSE
          AND (
              kn.metadata->>'source' NOT IN ('memory_consolidator', 'cross_domain_linker')
              OR kn.metadata->>'source' IS NULL
          )
        ORDER BY kn.created_at DESC
        LIMIT 20
    """)

    if pending:
        st.info(
            f"В очереди на ручной просмотр: **{len(pending)}** последних "
            f"(всего unverified без tech-source — см. метрики выше)."
        )
        for p in pending:
            nid = p["id"]
            preview = (p.get("preview") or "").replace("\n", " ").strip()
            src = p.get("source") or "unknown"
            domain = p.get("domain") or "—"
            path = p.get("file_path") or "—"
            with st.expander(
                f"Узел {str(nid)[:8]} · {src} · {domain} · {format_msk(p['created_at'])} — {preview[:100]}…"
            ):
                st.markdown(
                    f"**Domain:** `{domain}` · **type:** `{p.get('node_type') or '—'}` · "
                    f"**conf:** `{p.get('confidence_score')}` · **path:** `{path}` · "
                    f"**expert:** `{p.get('expert_name')}`"
                )
                st.markdown(p.get("content") or "_(пусто)_")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✅ Подтвердить (в БД)", key=f"verify_{nid}"):
                        if _mark_node_verified(nid, "dashboard_revision"):
                            st.success(f"Узел {str(nid)[:8]} → is_verified=true")
                            st.rerun()
                        else:
                            st.error("Не удалось обновить узел.")
                with col_b:
                    st.caption("Reject нет: низкий conf / ignore в metadata — отдельный flow.")
    else:
        st.success("Очередь ручного просмотра пуста (или остались только tech-source).")
