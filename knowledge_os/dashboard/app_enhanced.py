"""
Enhanced Dashboard with Advanced Analytics
Улучшенный Dashboard с расширенной аналитикой
"""

from datetime import timedelta
import numpy as np
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from enhanced_analytics import EnhancedAnalytics

# Настройка страницы
st.set_page_config(
    page_title="Knowledge OS Analytics | Enhanced Dashboard",
    page_icon="📊",
    layout="wide"
)

# Стили (используем те же, что в оригинале)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #05070a;
    }

    .metric-card {
        background: linear-gradient(145deg, #161b22, #0d1117);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }

    .metric-value {
        font-size: 32px;
        font-weight: 800;
        color: #58a6ff;
    }

    .metric-label {
        font-size: 14px;
        color: #8b949e;
        text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)

def main():
    """
    Основная функция запуска Dashboard.
    Отрисовывает интерфейс, вкладки и графики.
    """
    st.title("📊 Knowledge OS - Enhanced Analytics Dashboard")
    st.markdown("---")

    analytics = EnhancedAnalytics()

    # --- ОБЩИЙ ОБЗОР ---
    st.header("📈 Общий обзор системы")

    overview = analytics.get_system_overview()
    if overview:
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Узлов знаний", f"{overview.get('total_nodes', 0):,}")
        with col2:
            st.metric("Экспертов", overview.get('total_experts', 0))
        with col3:
            st.metric("Доменов", overview.get('total_domains', 0))
        with col4:
            st.metric("Средний confidence", f"{overview.get('avg_confidence', 0):.2f}")
        with col5:
            st.metric("Всего использований", f"{overview.get('total_usage', 0):,}")

    st.markdown("---")

    # --- ВКЛАДКИ ---
    tabs = st.tabs([
        "📈 Рост и тренды",
        "🏢 Распределение по доменам",
        "👥 Производительность экспертов",
        "🔍 Эффективность поиска",
        "⭐ Качество знаний",
        "✅ Аналитика задач",
        "🔮 Прогнозы",
        "🕸️ Граф знаний"
    ])

    # 📈 РОСТ И ТРЕНДЫ
    with tabs[0]:
        st.subheader("📈 Рост базы знаний")

        # Выбор периода
        period = st.selectbox("Период", [7, 14, 30, 60, 90], index=2)
        growth_data = analytics.get_knowledge_growth_trend(period)

        if not growth_data.empty:
            col1, col2 = st.columns(2)

            with col1:
                # График роста
                fig = px.line(
                    growth_data,
                    x='date',
                    y='new_nodes',
                    title="Новые узлы знаний",
                    template="plotly_dark",
                    labels={'new_nodes': 'Новых узлов', 'date': 'Дата'}
                )
                fig.update_traces(line_color='#58a6ff', line_width=3)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # График использования
                fig = px.bar(
                    growth_data,
                    x='date',
                    y='total_usage',
                    title="Использование знаний",
                    template="plotly_dark",
                    labels={'total_usage': 'Использований', 'date': 'Дата'}
                )
                fig.update_traces(marker_color='#238636')
                st.plotly_chart(fig, use_container_width=True)

            # Средний confidence по времени
            if 'avg_confidence' in growth_data.columns:
                fig = px.line(
                    growth_data,
                    x='date',
                    y='avg_confidence',
                    title="Средний confidence score",
                    template="plotly_dark",
                    labels={'avg_confidence': 'Confidence', 'date': 'Дата'}
                )
                fig.update_traces(line_color='#f38ba8', line_width=2)
                st.plotly_chart(fig, use_container_width=True)

    # 🏢 РАСПРЕДЕЛЕНИЕ ПО ДОМЕНАМ
    with tabs[1]:
        st.subheader("🏢 Распределение знаний по доменам")

        domain_data = analytics.get_domain_distribution()

        if not domain_data.empty:
            col1, col2 = st.columns(2)

            with col1:
                # Круговая диаграмма
                fig = px.pie(
                    domain_data,
                    values='node_count',
                    names='domain',
                    title="Распределение узлов по доменам",
                    template="plotly_dark",
                    hole=0.4
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Столбчатая диаграмма использования
                fig = px.bar(
                    domain_data.sort_values('total_usage', ascending=False).head(10),
                    x='domain',
                    y='total_usage',
                    title="Топ-10 доменов по использованию",
                    template="plotly_dark",
                    labels={'total_usage': 'Использований', 'domain': 'Домен'}
                )
                fig.update_traces(marker_color='#58a6ff')
                st.plotly_chart(fig, use_container_width=True)

            # Таблица с деталями
            st.subheader("Детальная статистика по доменам")
            st.dataframe(
                domain_data.sort_values('node_count', ascending=False),
                use_container_width=True,
                hide_index=True
            )

    # 👥 ПРОИЗВОДИТЕЛЬНОСТЬ ЭКСПЕРТОВ
    with tabs[2]:
        st.subheader("👥 Производительность экспертов")

        expert_data = analytics.get_expert_performance()

        if not expert_data.empty:
            col1, col2 = st.columns(2)

            with col1:
                # Топ экспертов по использованию
                top_experts = expert_data.nlargest(10, 'total_usage')
                fig = px.bar(
                    top_experts,
                    x='name',
                    y='total_usage',
                    color='department',
                    title="Топ-10 экспертов по использованию знаний",
                    template="plotly_dark",
                    labels={'total_usage': 'Использований', 'name': 'Эксперт'}
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Задачи экспертов
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=expert_data['name'],
                    y=expert_data['tasks_completed'],
                    name='Завершено',
                    marker_color='#238636'
                ))
                fig.add_trace(go.Bar(
                    x=expert_data['name'],
                    y=expert_data['tasks_pending'],
                    name='В ожидании',
                    marker_color='#f38ba8'
                ))
                fig.update_layout(
                    title="Задачи экспертов",
                    template="plotly_dark",
                    barmode='stack',
                    xaxis_title="Эксперт",
                    yaxis_title="Количество задач"
                )
                st.plotly_chart(fig, use_container_width=True)

            # Таблица производительности
            st.subheader("Детальная статистика экспертов")
            st.dataframe(
                expert_data.sort_values('total_usage', ascending=False),
                use_container_width=True,
                hide_index=True
            )

    # 🔍 ЭФФЕКТИВНОСТЬ ПОИСКА
    with tabs[3]:
        st.subheader("🔍 Эффективность поиска")

        search_metrics = analytics.get_search_effectiveness()

        if search_metrics:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Всего узлов",
                    f"{search_metrics.get('total_searchable_nodes', 0):,}"
                )
            with col2:
                st.metric(
                    "Используемых",
                    f"{search_metrics.get('used_nodes', 0):,}"
                )
            with col3:
                st.metric(
                    "Процент использования",
                    f"{search_metrics.get('usage_rate', 0):.1f}%"
                )
            with col4:
                st.metric(
                    "Популярных (>10)",
                    search_metrics.get('popular_nodes', 0)
                )

            # График распределения использования
            usage_data = analytics.fetch_data("""
                SELECT
                    CASE
                        WHEN usage_count = 0 THEN '0'
                        WHEN usage_count BETWEEN 1 AND 5 THEN '1-5'
                        WHEN usage_count BETWEEN 6 AND 10 THEN '6-10'
                        WHEN usage_count BETWEEN 11 AND 50 THEN '11-50'
                        ELSE '50+'
                    END as usage_range,
                    count(*) as count
                FROM knowledge_nodes
                GROUP BY usage_range
                ORDER BY
                    CASE usage_range
                        WHEN '0' THEN 1
                        WHEN '1-5' THEN 2
                        WHEN '6-10' THEN 3
                        WHEN '11-50' THEN 4
                        ELSE 5
                    END
            """)

            if usage_data:
                df = pd.DataFrame(usage_data)
                fig = px.bar(
                    df,
                    x='usage_range',
                    y='count',
                    title="Распределение узлов по использованию",
                    template="plotly_dark",
                    labels={'count': 'Количество узлов', 'usage_range': 'Диапазон использований'}
                )
                fig.update_traces(marker_color='#58a6ff')
                st.plotly_chart(fig, use_container_width=True)

    # ⭐ КАЧЕСТВО ЗНАНИЙ
    with tabs[4]:
        st.subheader("⭐ Качество знаний")

        quality_metrics = analytics.get_quality_metrics()

        if quality_metrics:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Высокое качество (≥0.8)",
                    f"{quality_metrics.get('high_quality', 0):,}",
                    f"{quality_metrics.get('high_quality_pct', 0):.1f}%"
                )
            with col2:
                st.metric(
                    "Среднее качество (0.5-0.8)",
                    f"{quality_metrics.get('medium_quality', 0):,}",
                    f"{quality_metrics.get('medium_quality_pct', 0):.1f}%"
                )
            with col3:
                st.metric(
                    "Низкое качество (<0.5)",
                    f"{quality_metrics.get('low_quality', 0):,}",
                    f"{quality_metrics.get('low_quality_pct', 0):.1f}%"
                )
            with col4:
                st.metric(
                    "Верифицировано",
                    quality_metrics.get('verified', 0)
                )

            # График качества
            quality_data = {
                'Качество': ['Высокое', 'Среднее', 'Низкое'],
                'Количество': [
                    quality_metrics.get('high_quality', 0),
                    quality_metrics.get('medium_quality', 0),
                    quality_metrics.get('low_quality', 0)
                ]
            }
            df = pd.DataFrame(quality_data)
            fig = px.pie(
                df,
                values='Количество',
                names='Качество',
                title="Распределение по качеству",
                template="plotly_dark",
                hole=0.4,
                color='Качество',
                color_discrete_map={
                    'Высокое': '#238636',
                    'Среднее': '#fab387',
                    'Низкое': '#f38ba8'
                }
            )
            st.plotly_chart(fig, use_container_width=True)

            # Статистика тестирования
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Протестировано", quality_metrics.get('tested', 0))
            with col2:
                st.metric("Автоисправлено", quality_metrics.get('auto_fixed', 0))

    # ✅ АНАЛИТИКА ЗАДАЧ
    with tabs[5]:
        st.subheader("✅ Аналитика задач")

        task_metrics = analytics.get_task_analytics()

        if task_metrics:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("В ожидании", task_metrics.get('pending', 0))
            with col2:
                st.metric("В работе", task_metrics.get('in_progress', 0))
            with col3:
                st.metric("Завершено", task_metrics.get('completed', 0))
            with col4:
                st.metric(
                    "Процент завершения",
                    f"{task_metrics.get('completion_rate', 0):.1f}%"
                )

            # Распределение по приоритетам
            priority_data = {
                'Приоритет': ['Urgent', 'High', 'Medium', 'Low'],
                'Количество': [
                    task_metrics.get('urgent', 0),
                    task_metrics.get('high_priority', 0),
                    task_metrics.get('medium_priority', 0),
                    task_metrics.get('low_priority', 0)
                ]
            }
            df = pd.DataFrame(priority_data)
            fig = px.bar(
                df,
                x='Приоритет',
                y='Количество',
                title="Распределение задач по приоритетам",
                template="plotly_dark",
                color='Приоритет',
                color_discrete_map={
                    'Urgent': '#f38ba8',
                    'High': '#fab387',
                    'Medium': '#f9e2af',
                    'Low': '#94e2d5'
                }
            )
            st.plotly_chart(fig, use_container_width=True)

            # Среднее время выполнения
            if task_metrics.get('avg_completion_hours'):
                st.metric(
                    "Среднее время выполнения",
                    f"{task_metrics['avg_completion_hours']:.1f} часов"
                )

    # 🔮 ПРОГНОЗЫ
    with tabs[6]:
        st.subheader("🔮 Прогнозы и тренды")

        forecast = analytics.get_trends_forecast(7)

        if forecast:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Текущий рост (день)",
                    f"{forecast.get('current_daily_growth', 0):.1f} узлов"
                )
            with col2:
                st.metric(
                    "Прогноз на 7 дней",
                    f"{forecast.get('forecast_7_days', 0):.0f} узлов"
                )
            with col3:
                st.metric(
                    "Прогноз на 30 дней",
                    f"{forecast.get('forecast_30_days', 0):.0f} узлов"
                )

            # График прогноза
            growth_data = analytics.get_knowledge_growth_trend(30)
            if not growth_data.empty:
                # Добавляем прогноз
                last_date = growth_data['date'].max()
                forecast_dates = pd.date_range(
                    start=last_date + timedelta(days=1),
                    periods=7,
                    freq='D'
                )
                forecast_values = [forecast.get('current_daily_growth', 0)] * 7

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=growth_data['date'],
                    y=growth_data['new_nodes'],
                    name='Факт',
                    line=dict(color='#58a6ff', width=3)
                ))
                fig.add_trace(go.Scatter(
                    x=forecast_dates,
                    y=forecast_values,
                    name='Прогноз',
                    line=dict(color='#f38ba8', width=2, dash='dash')
                ))
                fig.update_layout(
                    title="Рост базы знаний: факт и прогноз",
                    template="plotly_dark",
                    xaxis_title="Дата",
                    yaxis_title="Новых узлов"
                )
                st.plotly_chart(fig, use_container_width=True)

    # 🕸️ ГРАФ ЗНАНИЙ
    with tabs[7]:
        st.subheader("🕸️ Граф знаний (визуализация связей)")

        limit = st.slider("Количество узлов", 10, 100, 50)

        graph_data = analytics.get_knowledge_graph_data(limit)

        if graph_data['nodes']:
            # Создаем граф с помощью plotly
            node_x = []
            node_y = []
            node_text = []
            node_size = []
            node_color = []

            # Простая визуализация (можно улучшить с networkx)
            n_nodes = len(graph_data['nodes'])
            angles = np.linspace(0, 2*np.pi, n_nodes, endpoint=False)

            for i, node in enumerate(graph_data['nodes']):
                node_x.append(np.cos(angles[i]))
                node_y.append(np.sin(angles[i]))
                node_text.append(node['label'])
                node_size.append(10 + node.get('usage', 0) * 0.5)
                node_color.append(node.get('confidence', 0.5))

            # Рисуем узлы
            node_trace = go.Scatter(
                x=node_x,
                y=node_y,
                mode='markers+text',
                text=node_text,
                textposition="top center",
                hoverinfo='text',
                marker=dict(
                    size=node_size,
                    color=node_color,
                    colorscale='Viridis',
                    showscale=True,
                    line=dict(width=1, color='white'),
                    colorbar=dict(title="Confidence")
                ),
                name='Узлы знаний'
            )

            # Рисуем связи
            edge_traces = []
            for edge in graph_data['edges']:
                source_idx = next((i for i, n in enumerate(graph_data['nodes']) if n['id'] == edge['source']), None)
                target_idx = next((i for i, n in enumerate(graph_data['nodes']) if n['id'] == edge['target']), None)

                if source_idx is not None and target_idx is not None:
                    edge_trace = go.Scatter(
                        x=[node_x[source_idx], node_x[target_idx]],
                        y=[node_y[source_idx], node_y[target_idx]],
                        mode='lines',
                        line=dict(width=1, color='#58a6ff', opacity=0.3),
                        showlegend=False,
                        hoverinfo='none'
                    )
                    edge_traces.append(edge_trace)

            fig = go.Figure(data=[*edge_traces, node_trace])
            fig.update_layout(
                title="Граф знаний",
                template="plotly_dark",
                showlegend=True,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                height=600
            )
            st.plotly_chart(fig, use_container_width=True)

            # Статистика графа
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Узлов", len(graph_data['nodes']))
            with col2:
                st.metric("Связей", len(graph_data['edges']))
            with col3:
                avg_degree = 0
                if graph_data['nodes']:
                    avg_degree = len(graph_data['edges']) / len(graph_data['nodes'])
                st.metric("Средняя степень", f"{avg_degree:.2f}")

if __name__ == "__main__":
    main()
