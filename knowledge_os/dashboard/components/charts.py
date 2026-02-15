import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def render_task_status_chart(df):
    """Render task status distribution pie chart."""
    if df.empty:
        st.info("Нет данных для отображения графиков")
        return
        
    status_counts = df['status'].value_counts().reset_index()
    status_counts.columns = ['status', 'count']
    
    # Singularity colors
    colors = {
        'completed': '#00f2ff', # Accent teal
        'pending': '#ffcc00',   # Warning yellow
        'failed': '#ff4b4b',    # Error red
        'in_progress': '#00ccff', # Progress blue
        'deferred': '#808080'   # Gray
    }
    
    fig = px.pie(
        status_counts, 
        values='count', 
        names='status',
        title="Распределение задач по статусам",
        color='status',
        color_discrete_map=colors,
        hole=0.4
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#c9d1d9',
        margin=dict(t=40, b=0, l=0, r=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_department_budgets_chart(df_dept):
    """Render department budgets bar chart."""
    if df_dept.empty:
        return
        
    fig = px.bar(
        df_dept, 
        x='department', 
        y='virtual_budget', 
        color='virtual_budget',
        template="plotly_dark",
        labels={'department': 'Департамент', 'virtual_budget': 'Бюджет ($)'},
        color_continuous_scale='Viridis'
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#c9d1d9',
        xaxis_tickangle=-45,
        height=400,
        margin=dict(t=40, b=0, l=0, r=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_roi_scatter_chart(df_finance):
    """Render ROI scatter chart (Budget vs Performance)."""
    if df_finance.empty:
        return
        
    fig = px.scatter(
        df_finance, 
        x='virtual_budget', 
        y='performance_score', 
        size='ROI', 
        hover_data=['name', 'department'],
        title="Бюджет vs Производительность", 
        template="plotly_dark",
        labels={'virtual_budget': 'Бюджет ($)', 'performance_score': 'Производительность'},
        color_discrete_sequence=['#00f2ff']
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#c9d1d9',
        margin=dict(t=40, b=0, l=0, r=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_expert_workload_chart(df):
    """Render expert workload bar chart."""
    if df.empty:
        return
        
    expert_counts = df['assignee'].value_counts().reset_index()
    expert_counts.columns = ['expert', 'count']
    
    fig = px.bar(
        expert_counts,
        x='expert',
        y='count',
        title="Загрузка экспертов",
        color_discrete_sequence=['#00f2ff']
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#c9d1d9',
        xaxis_title="",
        yaxis_title="Кол-во задач",
        margin=dict(t=40, b=0, l=0, r=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)
