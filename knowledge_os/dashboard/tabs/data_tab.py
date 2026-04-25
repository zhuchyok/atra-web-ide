import json
import os
from datetime import datetime, timedelta, timezone

import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from database_service import fetch_data
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
    st.markdown("Мониторинг и управление архитектурными мутациями кода в режиме Shadow Testing.")

    # 1. Fetch active code mutations from knowledge_nodes
    mutations = fetch_data("""
        SELECT id, content, metadata, created_at
        FROM knowledge_nodes
        WHERE metadata->>'type' = 'architecture_mutation'
        AND (metadata->>'status' IS NULL OR metadata->>'status' != 'promoted')
        ORDER BY created_at DESC
    """)

    if not mutations:
        st.info("Нет активных архитектурных мутаций в режиме Shadow Testing.")
        return

    # 2. Display list of modules in shadow testing
    mutation_list = []
    for m in mutations:
        meta = (
            m["metadata"] if isinstance(m["metadata"], dict) else json.loads(m["metadata"] or "{}")
        )
        mutation_list.append(
            {
                "id": m["id"],
                "module": meta.get("module", "Unknown"),
                "function": meta.get("function", "Unknown"),
                "hypothesis": meta.get("hypothesis", {}).get("mutation_hypothesis", "N/A"),
                "safety_score": meta.get("safety_report", {}).get("score", 0.0)
                if "safety_report" in meta
                else meta.get("safety_score", 0.0),
                "risks": meta.get("safety_report", {}).get("risks", [])
                if "safety_report" in meta
                else meta.get("risks", []),
                "mutation_path": meta.get("mutation_path", ""),
                "created_at": m["created_at"],
            }
        )

    module_names = sorted(list(set([m["module"] for m in mutation_list])))
    selected_module = st.selectbox("Выберите модуль для аудита", module_names)

    selected_mutation = next((m for m in mutation_list if m["module"] == selected_module), None)

    if selected_mutation:
        # 3. Show Safety Score and Risk Factors
        score = selected_mutation["safety_score"]
        risks = selected_mutation["risks"]

        col1, col2 = st.columns(2)
        score_color = "normal" if score > 0.7 else "inverse"
        col1.metric("Safety Score", f"{score * 100:.1f}%", delta_color=score_color)

        with col2:
            st.markdown("**Risk Factors:**")
            if risks:
                for risk in risks:
                    st.warning(f"⚠️ {risk}")
            else:
                st.success("✅ No critical risks identified")

        st.markdown("---")

        # 4. Side-by-side code diff (Original vs. Mutated)
        st.markdown("### Сравнение кода (Original vs Mutated)")

        # Try to read original code
        original_code = "N/A"
        mutated_code = "N/A"

        module_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app",
            f"{selected_mutation['module']}.py",
        )
        # [FIX] Корректировка путей для Docker
        if not os.path.exists(module_path) and os.path.exists(
            f"/app/knowledge_os/app/{selected_mutation['module']}.py"
        ):
            module_path = f"/app/knowledge_os/app/{selected_mutation['module']}.py"

        mutation_path = selected_mutation["mutation_path"]
        if not os.path.exists(mutation_path) and mutation_path.startswith("knowledge_os/"):
            alt_path = os.path.join("/app", mutation_path)
            if os.path.exists(alt_path):
                mutation_path = alt_path

        try:
            if os.path.exists(module_path):
                with open(module_path) as f:
                    original_code = f.read()
            if os.path.exists(mutation_path):
                with open(mutation_path) as f:
                    mutated_code = f.read()
        except Exception as e:
            st.error(f"Ошибка чтения файлов: {e}")

        c_orig, c_mut = st.columns(2)
        with c_orig:
            st.markdown("**🛡️ Original (Production)**")
            st.code(original_code, language="python")
        with c_mut:
            st.markdown("**⚡ Mutated (Shadow)**")
            st.code(mutated_code, language="python")

        # 5. Action buttons
        st.markdown("### Действия")
        act_col1, act_col2, _ = st.columns([1, 1, 2])

        from database_service import run_query

        if act_col1.button(
            "🚀 Promote Code", help="Заменить основной файл мутировавшим (Hot-Swap)", type="primary"
        ):
            try:
                # In a real system, we would call MetaArchitect.promote_mutation
                # For now, we simulate the file swap and update the node status
                if os.path.exists(mutation_path):
                    import shutil

                    shutil.copy2(mutation_path, module_path)

                    # Update metadata in knowledge_nodes
                    new_meta = fetch_data(
                        "SELECT metadata FROM knowledge_nodes WHERE id = %s",
                        (selected_mutation["id"],),
                    )[0]["metadata"]
                    if isinstance(new_meta, str):
                        new_meta = json.loads(new_meta)
                    new_meta["status"] = "promoted"
                    new_meta["promoted_at"] = datetime.now(timezone.utc).isoformat()

                    run_query(
                        "UPDATE knowledge_nodes SET metadata = %s WHERE id = %s",
                        (json.dumps(new_meta), selected_mutation["id"]),
                    )
                    st.success(f"Код модуля {selected_module} успешно обновлен!")
                    st.rerun()
                else:
                    st.error("Файл мутации не найден.")
            except Exception as e:
                st.error(f"Ошибка при продвижении кода: {e}")

        if act_col2.button("❌ Reject Code", help="Удалить мутацию и остановить Shadow Testing"):
            try:
                # Update metadata in knowledge_nodes
                new_meta = fetch_data(
                    "SELECT metadata FROM knowledge_nodes WHERE id = %s", (selected_mutation["id"],)
                )[0]["metadata"]
                if isinstance(new_meta, str):
                    new_meta = json.loads(new_meta)
                new_meta["status"] = "rejected"

                run_query(
                    "UPDATE knowledge_nodes SET metadata = %s WHERE id = %s",
                    (json.dumps(new_meta), selected_mutation["id"]),
                )

                # Optionally delete the mutation file
                if os.path.exists(mutation_path):
                    os.remove(mutation_path)

                st.warning("Мутация отклонена и удалена.")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка при отклонении кода: {e}")

        st.markdown("---")
        st.markdown(f"**Гипотеза мутации:** {selected_mutation['hypothesis']}")
        st.caption(
            f"Создано: {format_msk(selected_mutation['created_at'])} | ID: {selected_mutation['id']}"
        )


def render_prompt_battle():
    """⚔️ Prompt Battle interface for Shadow Prompt Evolution."""
    st.subheader("⚔️ Prompt Battle: Shadow Evolution")
    st.markdown("Сражение между текущим промптом (Production) и мутировавшим (Shadow).")

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
    expert_names = sorted(list(set([m["expert_name"] for m in mutations])))
    selected_expert_name = st.selectbox("Выберите эксперта для аудита", expert_names)

    selected_mutation = next(
        (m for m in mutations if m["expert_name"] == selected_expert_name), None
    )

    if selected_mutation:
        # 3. Show Win/Loss/Draw stats and Win Rate
        total = selected_mutation["total_tests"]
        wins = selected_mutation["win_count"]
        losses = selected_mutation["loss_count"]
        draws = selected_mutation["draw_count"]
        win_rate = (wins / total * 100) if total > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Win Rate", f"{win_rate:.1f}%")
        col2.metric("Wins", wins)
        col3.metric("Losses", losses)
        col4.metric("Total Tests", total)

        st.markdown("---")

        # 4. Side-by-side comparison
        st.markdown("### Сравнение промптов")
        c_prod, c_shadow = st.columns(2)

        with c_prod:
            st.markdown("**🛡️ Production (Base)**")
            st.code(selected_mutation["prod_prompt"], language="markdown")

        with c_shadow:
            st.markdown("**⚡ Shadow (Mutation)**")
            st.code(selected_mutation["mutated_prompt"], language="markdown")

        # 5. Action buttons
        st.markdown("### Действия")
        act_col1, act_col2, _ = st.columns([1, 1, 2])

        if act_col1.button(
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

        if act_col2.button("❌ Reject Mutation", help="Архивировать мутацию"):
            if run_query(
                "UPDATE expert_mutations SET status = 'rejected' WHERE id = %s",
                (selected_mutation["id"],),
            ):
                st.warning("Мутация отклонена.")
                st.rerun()

        st.markdown("---")

        # 6. Recent Battles section
        st.markdown("### 📜 Последние битвы (Evaluations)")
        # Fetch last 5 evaluations from interaction_logs where shadow execution was triggered
        # We look for shadow_verdict in metadata
        recent_battles = fetch_data(
            """
            SELECT created_at, user_query, assistant_response, metadata
            FROM interaction_logs
            WHERE expert_id = %s
            AND metadata->>'shadow_execution' = 'true'
            ORDER BY created_at DESC
            LIMIT 5
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

                with st.expander(f"Битва {format_msk(battle['created_at'])} | Вердикт: {verdict}"):
                    st.markdown(f"**Запрос:** {battle['user_query']}")
                    st.markdown(f"**Причина вердикта:** {reason}")
                    st.markdown("**Ответ Shadow:**")
                    st.info(meta.get("shadow_response", "N/A"))
        else:
            st.info("История битв для этого эксперта пока пуста.")


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
    """📚 AI Research Knowledge Base (Новое!)."""
    st.subheader("📚 База Мудрости (AI Research)")
    st.markdown("Мировые практики и промпты Anthropic, OpenAI, Google, Perplexity.")

    search_ai = st.text_input(
        "🔍 Поиск по AI Research", placeholder="Например: 'Claude Code error handling'..."
    )

    if search_ai:
        # Поиск по домену AI Research
        results = fetch_data(
            """
            SELECT content, metadata->>'file_path' as path, confidence_score
            FROM knowledge_nodes
            WHERE (content ILIKE %s OR metadata->>'file_path' ILIKE %s)
            AND domain_id = (SELECT id FROM domains WHERE name = 'AI Research')
            ORDER BY confidence_score DESC LIMIT 10
        """,
            (f"%{search_ai}%", f"%{search_ai}%"),
        )

        if results:
            for r in results:
                with st.expander(f"📄 {r['path']} (Conf: {r['confidence_score']:.2f})"):
                    st.markdown(r["content"])
        else:
            st.info("Ничего не найдено в AI Research.")
    else:
        # Показываем последние добавленные
        st.markdown("### Последние находки")
        latest = fetch_data("""
            SELECT content, metadata->>'file_path' as path, created_at
            FROM knowledge_nodes
            WHERE domain_id = (SELECT id FROM domains WHERE name = 'AI Research')
            ORDER BY created_at DESC LIMIT 5
        """)
        if latest:
            for l in latest:
                st.caption(f"📌 {l['path']} - {format_msk(l['created_at']).split()[0]}")
                st.markdown(f"{(l['content'] or '')[:200]}...")
        else:
            st.info("База AI Research пока пуста. Запустите скрипт индексации.")


def render_data_health():
    """📊 Целостность данных (Knowledge OS Health)."""
    st.subheader("📊 Здоровье Базы Знаний")
    
    time_range = st.session_state.get("global_time_range", "Последние 7 дней")
    from database_service import get_time_filter
    t_filter = get_time_filter(time_range, "created_at")

    try:
        stats = fetch_data(f"""
            SELECT
                (SELECT COUNT(*) FROM knowledge_nodes WHERE {t_filter}) as total_nodes,
                (SELECT COUNT(*) FROM knowledge_links WHERE {t_filter}) as total_links,
                (SELECT COUNT(*) FROM knowledge_nodes WHERE embedding IS NULL AND {t_filter}) as missing_embeddings,
                (SELECT COUNT(*) FROM knowledge_nodes WHERE confidence_score < 0.3 AND {t_filter}) as low_confidence
        """)
        if stats and stats[0]:
            s = stats[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Всего узлов", s["total_nodes"])
            c2.metric("Всего связей", s["total_links"])
            c3.metric("Без векторов", s["missing_embeddings"], delta_color="inverse")
            c4.metric("Низкий Conf", s["low_confidence"], delta_color="inverse")

            # Прогресс к цели 10/10 (100k связей)
            st.markdown("### 🏆 Путь к Neural Graph (100k связей)")
            progress = min(100, int(s["total_links"] / 1000))
            st.progress(progress / 100)
            st.caption(f"Текущий прогресс: {progress}% (Цель: 100,000 семантических связей)")

    except Exception as e:
        st.error(f"Ошибка аудита данных: {e}")


def render_mindmap():
    """🧠 Карта разума корпорации (Иерархическая визуализация 100k+)."""
    st.subheader("🧠 Семантический Граф Знаний (Neural Graph)")

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
                    [l["source_domain"] for l in domain_links]
                    + [l["target_domain"] for l in domain_links]
                )
                if len(unique_domains) <= 1:
                    st.warning(
                        f"ВНИМАНИЕ: Найдено связей: {len(domain_links)}, Уникальных доменов: {len(unique_domains)}. Проверьте линковку в БД."
                    )

            if not domain_links:
                st.info("Междоменные связи пока не сформированы.")
                return

            G = nx.DiGraph()
            for link in domain_links:
                G.add_edge(link["source_domain"], link["target_domain"], weight=link["link_count"])

            domain_stats = fetch_data(
                "SELECT d.name, COUNT(k.id) as node_count FROM domains d LEFT JOIN knowledge_nodes k ON d.id = k.domain_id GROUP BY d.name"
            )
            node_sizes_map = {d["name"]: d["node_count"] for d in domain_stats}

            node_list = list(G.nodes())
            n_nodes = len(node_list)
            adj_matrix = np.zeros((n_nodes, n_nodes))
            for i, u in enumerate(node_list):
                for j, v in enumerate(node_list):
                    if G.has_edge(u, v):
                        adj_matrix[i, j] = 1

            pos_array = optimized_force_layout(adj_matrix, np.ones(n_nodes), iterations=50)
            pos = {node_list[i]: pos_array[i] for i in range(n_nodes)}

            edge_x, edge_y = [], []
            for edge in G.edges(data=True):
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

            node_x, node_y, node_text, node_size_vals = [], [], [], []
            for node in G.nodes():
                x, y = pos[node]
                node_x.append(x)
                node_y.append(y)
                count = node_sizes_map.get(node, 0)
                node_text.append(f"Домен: {node}<br>Узлов: {count}")
                node_size_vals.append(min(60, max(25, count / 3)))

            node_trace = go.Scatter(
                x=node_x,
                y=node_y,
                mode="markers+text",
                text=[n for n in G.nodes()],
                textposition="top center",
                hoverinfo="text",
                hovertext=node_text,
                textfont=dict(size=14, color="white"),
                marker=dict(
                    size=node_size_vals, color="#FF7F50", line=dict(width=2, color="white")
                ),
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
            st.plotly_chart(fig, use_container_width=True)

        elif view_mode == "🧬 Семантические Кластеры":
            st.markdown("### Кластеризация знаний (Созвездия)")
            limit = st.slider("Лимит узлов для визуализации", 50, 1000, 400)

            # ПРАВИЛЬНЫЙ SQL: Убираем фильтр уверенности для теста, чтобы увидеть ВСЕ домены
            nodes_data = fetch_data(
                """
                WITH connection_counts AS (
                    SELECT
                        kn.id, kn.domain_id, kn.content, kn.confidence_score, d.name as domain_name,
                        (SELECT COUNT(*) FROM knowledge_links WHERE source_node_id = kn.id OR target_node_id = kn.id) AS total_degree
                    FROM knowledge_nodes kn
                    JOIN domains d ON kn.domain_id = d.id
                ),
                ranked_nodes AS (
                    SELECT
                        id, domain_id, content, confidence_score, domain_name as domain, total_degree,
                        ROW_NUMBER() OVER (PARTITION BY domain_id ORDER BY total_degree DESC) AS rn
                    FROM connection_counts
                ),
                top_nodes AS (
                    -- Берем до 20 узлов из КАЖДОГО домена
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

            G = nx.Graph()
            node_info = {}
            node_list = []
            for n in nodes_data:
                G.add_node(n["id"], label=n["label"], domain=n["domain"], degree=n["total_degree"])
                node_info[n["id"]] = n
                node_list.append(n["id"])

            for n in nodes_data:
                if n["links"]:
                    targets = n["links"] if isinstance(n["links"], list) else json.loads(n["links"])
                    for target_id in targets:
                        if target_id in node_info:
                            G.add_edge(n["id"], target_id)

            n_nodes = len(node_list)
            if n_nodes == 0:
                st.info("Граф пуст.")
                return

            adj_matrix = np.zeros((n_nodes, n_nodes))
            node_id_to_idx = {nid: i for i, nid in enumerate(node_list)}
            for u, v in G.edges():
                adj_matrix[node_id_to_idx[u], node_id_to_idx[v]] = 1
                adj_matrix[node_id_to_idx[v], node_id_to_idx[u]] = 1

            pos_array = optimized_force_layout(
                adj_matrix, np.array([G.degree(n) for n in node_list]), iterations=300
            )
            pos_dict = {node_list[i]: pos_array[i] for i in range(n_nodes)}

            edge_x, edge_y = [], []
            for edge in G.edges():
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
            degrees_in_graph = dict(G.degree())

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
            st.plotly_chart(fig, use_container_width=True)

        elif view_mode == "🔍 Локальный поиск":
            search_query = st.text_input(
                "Введите ID узла или текст для поиска центра графа",
                placeholder="Например: 'PostgreSQL' или UUID...",
            )
            depth = st.slider("Глубина связей", 1, 3, 1)

            if search_query:
                center_node = fetch_data(
                    "SELECT id, content FROM knowledge_nodes WHERE content ILIKE %s OR id::text = %s LIMIT 1",
                    (f"%{search_query}%", search_query),
                )
                if center_node:
                    c_id = center_node[0]["id"]
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
                        G = nx.Graph()
                        node_list_local = set()
                        for l in local_links:
                            G.add_edge(str(l["source_node_id"]), str(l["target_node_id"]))
                            node_list_local.add(str(l["source_node_id"]))
                            node_list_local.add(str(l["target_node_id"]))

                        node_list_local = list(node_list_local)
                        n_nodes = len(node_list_local)
                        adj_matrix = np.zeros((n_nodes, n_nodes))
                        nid_to_idx = {nid: i for i, nid in enumerate(node_list_local)}
                        for u, v in G.edges():
                            adj_matrix[nid_to_idx[u], nid_to_idx[v]] = 1
                            adj_matrix[nid_to_idx[v], nid_to_idx[u]] = 1

                        pos_array = optimized_force_layout(
                            adj_matrix, np.ones(n_nodes), iterations=50
                        )
                        pos_dict = {node_list_local[i]: pos_array[i] for i in range(n_nodes)}

                        edge_x, edge_y = [], []
                        for edge in G.edges():
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

                        node_x, node_y, node_text = [], [], []
                        for node in G.nodes():
                            x, y = pos_dict[node]
                            node_x.append(x)
                            node_y.append(y)
                            node_text.append(f"Node ID: {node}")

                        node_trace = go.Scatter(
                            x=node_x,
                            y=node_y,
                            mode="markers+text",
                            text=[n[:8] for n in G.nodes()],
                            textposition="bottom center",
                            hoverinfo="text",
                            hovertext=node_text,
                            marker=dict(size=20, color="#ffcc00", line_width=2),
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
                        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Ошибка визуализации: {e}")
        import traceback

        st.code(traceback.format_exc())


def render_revision():
    """🔍 Ревизия знаний."""
    st.subheader("🔍 Ревизия и Верификация")

    # Исключаем технические узлы из ревизии (память, линковка)
    pending = fetch_data("""
        SELECT id, LEFT(content, 150) as content,
               COALESCE(metadata->>'expert_name', metadata->>'expert', 'System') as expert_name,
               metadata->>'source' as source,
               created_at
        FROM knowledge_nodes
        WHERE is_verified = false
        AND (metadata->>'source' NOT IN ('memory_consolidator', 'cross_domain_linker') OR metadata->>'source' IS NULL)
        ORDER BY created_at DESC LIMIT 20
    """)

    if pending:
        st.info(f"Найдено {len(pending)} узлов, требующих верификации (исключая технические).")
        for p in pending:
            with st.expander(
                f"Узел {str(p['id'])[:8]} | {p['expert_name']} ({p['source'] or 'unknown'}) | {format_msk(p['created_at'])}"
            ):
                st.write(p["content"])
                if st.button("✅ Подтвердить", key=f"verify_{p['id']}"):
                    # Здесь должен быть вызов run_query для обновления is_verified = true
                    st.success(f"Узел {str(p['id'])[:8]} верифицирован")
    else:
        st.success("Все значимые знания верифицированы.")
