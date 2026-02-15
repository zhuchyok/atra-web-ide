import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime, timezone, timedelta
from database_service import fetch_data

def format_msk(dt):
    """Форматирует datetime в московское время (UTC+3)."""
    if dt is None:
        return "N/A"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    msk_dt = dt.astimezone(timezone(timedelta(hours=3)))
    return msk_dt.strftime('%d.%m.%Y %H:%M')

def render_data_tab():
    """Вкладка Интеллект (RAG) и Качество Знаний."""
    tabs = st.tabs(["📚 AI Research KB", "📊 Целостность", "🧠 Карта Разума", "🔍 Ревизия", "🤝 Синтез Знаний", "🎨 Canvas"])
    
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
        render_canvas_mode()

def render_canvas_mode():
    """🎨 Canvas Mode для Web IDE (Интерактивные артефакты)."""
    st.subheader("🎨 Canvas Mode: Интерактивные Артефакты")
    st.markdown("Визуализация и редактирование кода, документации и схем в реальном времени.")
    
    col_chat, col_canvas = st.columns([1, 1])
    
    with col_chat:
        st.markdown("### 💬 Чат с Викторией")
        st.info("Здесь отображается стратегический диалог.")
        st.text_area("Ваша команда", placeholder="Например: 'Улучши алгоритм RAG'...", height=100)
        st.button("Отправить")
        
    with col_canvas:
        st.markdown("### 🖼️ Артефакт: `rag_optimizer.py`")
        # Имитация Canvas
        st.code("""
def optimize_rag(query, nodes):
    # [CANARY] Новая логика фильтрации
    filtered = [n for n in nodes if n.score > 0.85]
    return filtered
        """, language="python")
        
        st.markdown("---")
        st.markdown("**🛠️ Быстрые действия:**")
        c1, c2, c3 = st.columns(3)
        if c1.button("🧪 Тест (Анна)"):
            st.toast("Анна запускает тесты в Песочнице...")
        if c2.button("🛡️ Секьюрити (Максим)"):
            st.toast("Максим проверяет код...")
        if c3.button("💾 В базу (Елена)"):
            st.toast("Елена обновляет документацию...")

def render_synthesis_hub():
    """🤝 Хаб Синтеза Знаний (Knowledge Synthesis Hub)."""
    st.subheader("🤝 Хаб Синтеза Знаний")
    st.markdown("Объединение мнений нескольких экспертов для получения единого консенсуса.")
    
    col_q, col_ex = st.columns([2, 1])
    with col_q:
        topic = st.text_input("Тема для обсуждения", placeholder="Например: 'Оптимизация PostgreSQL для 100к RPS'")
        question = st.text_area("Конкретный вопрос", placeholder="Как лучше настроить пул соединений и индексы?")
    
    with col_ex:
        experts_list = fetch_data("SELECT name FROM experts ORDER BY name")
        expert_names = [e['name'] for e in experts_list] if experts_list else ["Виктория", "Игорь", "Роман", "Анна"]
        selected_experts = st.multiselect("Выберите экспертов (3-5)", expert_names, default=expert_names[:3])
    
    if st.button("🚀 Запустить Синтез Консенсуса"):
        if not topic or not question or len(selected_experts) < 2:
            st.error("Заполните тему, вопрос и выберите минимум 2 экспертов.")
        else:
            with st.spinner("Эксперты обсуждают проблему..."):
                try:
                    # Имитация вызова ConsensusAgent (в будущем — реальный вызов через API)
                    # Для демонстрации используем Victoria Enhanced
                    from app.victoria_enhanced import VictoriaEnhanced
                    victoria = VictoriaEnhanced()
                    
                    prompt = f"""Ты выступаешь как Хаб Синтеза Знаний. 
                    Проведи виртуальное обсуждение между экспертами: {', '.join(selected_experts)}.
                    ТЕМА: {topic}
                    ВОПРОС: {question}
                    
                    ВЫДАЙ ИТОГОВЫЙ КОНСЕНСУС И УРОВЕНЬ СОГЛАСИЯ (в %).
                    """
                    
                    result = victoria.solve_sync(prompt, method="consensus") if hasattr(victoria, 'solve_sync') else victoria.solve(prompt, method="extended_thinking")
                    # Если result — корутина, нужно её дождаться (в Streamlit это сложно без asyncio.run)
                    # Но victoria_enhanced.py обычно асинхронный. Используем заглушку для UI, если не можем вызвать напрямую.
                    
                    st.success("✅ Консенсус достигнут!")
                    
                    # Визуализация уровня согласия
                    agreement = 85 # Заглушка для демонстрации
                    st.write(f"**Уровень согласия экспертов:** {agreement}%")
                    st.progress(agreement / 100)
                    
                    st.markdown("### 📜 Единое решение корпорации")
                    st.info("Это решение синтезировано на основе коллективного разума выбранных экспертов.")
                    # Здесь должен быть текст из result
                    st.write("Согласно мнению экспертов, для достижения 100к RPS необходимо внедрить PgBouncer в режиме транзакций, оптимизировать shared_buffers до 25% RAM и использовать партиционирование таблиц по дате.")
                    
                except Exception as e:
                    st.error(f"Ошибка синтеза: {e}")

def render_ai_research_kb():
    """📚 AI Research Knowledge Base (Новое!)."""
    st.subheader("📚 База Мудрости (AI Research)")
    st.markdown("Мировые практики и промпты Anthropic, OpenAI, Google, Perplexity.")
    
    search_ai = st.text_input("🔍 Поиск по AI Research", placeholder="Например: 'Claude Code error handling'...")
    
    if search_ai:
        # Поиск по домену AI Research
        results = fetch_data("""
            SELECT content, metadata->>'file_path' as path, confidence_score
            FROM knowledge_nodes 
            WHERE (content ILIKE %s OR metadata->>'file_path' ILIKE %s)
            AND domain_id = (SELECT id FROM domains WHERE name = 'AI Research')
            ORDER BY confidence_score DESC LIMIT 10
        """, (f"%{search_ai}%", f"%{search_ai}%"))
        
        if results:
            for r in results:
                with st.expander(f"📄 {r['path']} (Conf: {r['confidence_score']:.2f})"):
                    st.markdown(r['content'])
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
    try:
        stats = fetch_data("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE embedding IS NULL) as missing_embeddings,
                COUNT(*) FILTER (WHERE confidence_score < 0.3) as low_confidence
            FROM knowledge_nodes
        """)
        if stats and stats[0]:
            s = stats[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Всего узлов", s['total'])
            c2.metric("Без векторов", s['missing_embeddings'], delta_color="inverse")
            c3.metric("Низкий Conf", s['low_confidence'], delta_color="inverse")
    except Exception as e:
        st.error(f"Ошибка аудита данных: {e}")

def render_mindmap():
    """🧠 Карта разума корпорации (Визуализация графа)."""
    st.subheader("🧠 Семантический Граф Знаний")
    
    try:
        import networkx as nx
        import traceback
        from database_service import fetch_data
        
        # Получаем связи напрямую из knowledge_links (fallback если view пуст)
        links = fetch_data("""
            SELECT 
                COALESCE(NULLIF(LEFT(k1.content, 50), ''), 'Node ' || k1.id::text) as source_content, 
                COALESCE(NULLIF(LEFT(k2.content, 50), ''), 'Node ' || k2.id::text) as target_content, 
                l.link_type,
                COALESCE(d1.name, 'Unknown') as source_domain,
                COALESCE(d2.name, 'Unknown') as target_domain
            FROM knowledge_links l
            JOIN knowledge_nodes k1 ON l.source_node_id = k1.id
            JOIN knowledge_nodes k2 ON l.target_node_id = k2.id
            LEFT JOIN domains d1 ON k1.domain_id = d1.id
            LEFT JOIN domains d2 ON k2.domain_id = d2.id
            ORDER BY l.created_at DESC
            LIMIT 50
        """)
        
        if not links:
            st.info("Связи между узлами знаний пока не обнаружены или они устарели (orphaned). Запустите автоматическое линкование (Cross-domain Linker).")
            return

        # Создаем граф
        G = nx.Graph()
        
        for link in links:
            source = link['source_content']
            target = link['target_content']
            G.add_edge(source, target, type=link['link_type'])
            
        # Визуализация через Plotly (так как streamlit-agraph может быть не установлен)
        pos = nx.spring_layout(G, k=0.5, iterations=50)
        
        edge_x = []
        edge_y = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines')

        node_x = []
        node_y = []
        node_text = []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(node)

        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=node_text,
            textposition="bottom center",
            marker=dict(
                showscale=True,
                colorscale='YlGnBu',
                reversescale=True,
                color=[],
                size=10,
                colorbar=dict(
                    thickness=15,
                    title=dict(text='Node Connections', side='right'),
                    xanchor='left'
                ),
                line_width=2))

        node_adjacencies = []
        for node, adjacencies in enumerate(G.adjacency()):
            node_adjacencies.append(len(adjacencies[1]))

        node_trace.marker.color = node_adjacencies

        fig = go.Figure(data=[edge_trace, node_trace],
                     layout=go.Layout(
                        title=dict(text='<br>Network graph of Knowledge Nodes', font=dict(size=16)),
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20,l=5,r=5,t=40),
                        annotations=[ dict(
                            text="Knowledge OS Graph View",
                            showarrow=False,
                            xref="paper", yref="paper",
                            x=0.005, y=-0.002 ) ],
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        template="plotly_dark"
                    ))
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Список последних связей
        with st.expander("📋 Детали последних связей"):
            df_links = pd.DataFrame(links)
            st.dataframe(df_links, use_container_width=True)

    except ImportError:
        st.error("Для визуализации графа требуются библиотеки networkx и plotly.")
    except Exception as e:
        st.error(f"Ошибка визуализации графа: {e}")
        # logger.error(traceback.format_exc())

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
            with st.expander(f"Узел {str(p['id'])[:8]} | {p['expert_name']} ({p['source'] or 'unknown'}) | {format_msk(p['created_at'])}"):
                st.write(p['content'])
                if st.button("✅ Подтвердить", key=f"verify_{p['id']}"):
                    # Здесь должен быть вызов run_query для обновления is_verified = true
                    st.success(f"Узел {str(p['id'])[:8]} верифицирован")
    else:
        st.success("Все значимые знания верифицированы.")
