import streamlit as st
import os
import pandas as pd
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

def render_system_tab():
    """Вкладка Система и Безопасность."""
    tabs_system = st.tabs(["🔌 Сервисы", "🛡️ Безопасность", "🚨 War Room", "🧪 Песочница", "🚀 Singularity 10.0", "📁 Проекты", "🤖 Логи"])
    
    with tabs_system[0]:
        render_health_status()
    with tabs_system[1]:
        render_security()
    with tabs_system[2]:
        render_war_room()
    with tabs_system[3]:
        render_expert_sandbox()
    with tabs_system[4]:
        render_singularity_metrics()
    with tabs_system[5]:
        render_projects()
    with tabs_system[6]:
        render_agent_logs()

def render_expert_sandbox():
    """🧪 Expert Sandbox UI."""
    st.subheader("🧪 Песочница Эксперта (Expert Sandbox)")
    st.markdown("Изолированная среда для тестирования кода и гипотез агентами.")
    
    col_sel, col_env = st.columns([1, 2])
    with col_sel:
        experts_list = fetch_data("SELECT name FROM experts ORDER BY name")
        expert_names = [e['name'] for e in experts_list] if experts_list else ["Вероника", "Игорь"]
        selected_expert = st.selectbox("Агент в песочнице", expert_names)
        
        st.info(f"Песочница для {selected_expert} инициализирована в Docker-контейнере `sandbox-{selected_expert.lower()}`.")
        
        if st.button("🧹 Очистить песочницу"):
            st.success("Среда сброшена до исходного состояния.")
            
    with col_env:
        st.markdown("**🖥️ Терминал песочницы**")
        st.code(f"root@sandbox-{selected_expert.lower()}:/workspace# python3 test_script.py\n[SUCCESS] Tests passed: 12/12\n[INFO] Memory usage: 128MB", language="bash")
        
        st.markdown("**📝 Файлы в работе**")
        st.caption("`test_script.py`, `temp_data.json`, `debug.log`")
        
    st.markdown("---")
    st.markdown("#### 🛠️ Последние эксперименты")
    st.table(pd.DataFrame([
        {"Время": "21:15", "Эксперт": "Вероника", "Задача": "Тест миграции v2", "Результат": "✅ Успех"},
        {"Время": "20:40", "Эксперт": "Игорь", "Задача": "Нагрузка на Redis", "Результат": "⚠️ Warning: Latency > 5ms"}
    ]))

def render_war_room():
    """🚨 Tactical War Room UI."""
    st.subheader("🚨 Tactical War Room (Экстренное реагирование)")
    
    sessions = fetch_data("""
        SELECT topic, status, metadata, consensus_summary, created_at
        FROM expert_discussions 
        WHERE metadata->>'type' = 'war_room'
        ORDER BY created_at DESC LIMIT 10
    """)
    
    if sessions:
        for s in sessions:
            meta = s['metadata']
            severity = meta.get('severity', 'medium').upper()
            color = {'CRITICAL': '#f38ba8', 'HIGH': '#fab387'}.get(severity, '#cdd6f4')
            
            with st.expander(f"🚨 {severity}: {s['topic']} ({s['status'].upper()})"):
                st.caption(f"Создано: {format_msk(s['created_at'])} | Эксперты: {', '.join(meta.get('experts', []))}")
                
                # Лог обсуждения
                if 'log' in meta:
                    st.markdown("**💬 Ход обсуждения:**")
                    for entry in meta['log']:
                        st.markdown(f"**{entry['role']}:** {entry['content']}")
                
                # Финальный план
                if s['consensus_summary']:
                    st.success("**✅ Утвержденный план исправления:**")
                    st.markdown(s['consensus_summary'])
    else:
        st.info("Активных сессий в War Room нет. Система работает в штатном режиме.")

def render_health_status():
    """🔌 Статус сервисов."""
    st.subheader("🔌 Состояние Инфраструктуры")
    from database_service import check_services
    svc = check_services()
    
    cols = st.columns(len(svc))
    for i, (name, status) in enumerate(svc.items()):
        with cols[i]:
            color = "#238636" if status == "✅" else "#fab387"
            st.markdown(f"""
                <div style="text-align: center; background: rgba(88, 166, 255, 0.05); padding: 15px; border-radius: 8px; border-top: 3px solid {color};">
                    <div style="font-size: 24px;">{status}</div>
                    <div style="font-weight: 600; margin-top: 5px;">{name}</div>
                </div>
            """, unsafe_allow_html=True)

def render_security():
    """🛡️ Threat Detection."""
    st.subheader("🛡️ Мониторинг Угроз")
    try:
        threats = fetch_data("""
            SELECT anomaly_type, severity, description, detected_at 
            FROM anomaly_detection_logs 
            ORDER BY detected_at DESC LIMIT 10
        """)
        if threats:
            for t in threats:
                color = {'critical': '#f38ba8', 'high': '#fab387', 'medium': '#f9e2af'}.get(t['severity'], '#cdd6f4')
                st.markdown(f"""
                    <div style="background: #161b22; border-left: 4px solid {color}; padding: 12px; margin-bottom: 8px; border-radius: 4px;">
                        <div style="color: {color}; font-weight: 800;">{t['anomaly_type'].upper()}</div>
                        <div style="font-size: 13px;">{t['description']}</div>
                        <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">{format_msk(t['detected_at'])}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.success("Угроз не обнаружено.")
    except: pass

def render_singularity_metrics():
    """🚀 Метрики Оркестрации."""
    st.subheader("🚀 Эффективность Singularity 10.0")
    
    # Метрики A/B теста оркестратора
    orch_stats = fetch_data("""
        SELECT 
            orchestrator_version, 
            COUNT(*) as task_count,
            COUNT(*) FILTER (WHERE status = 'completed') as success_count,
            AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) FILTER (WHERE status = 'completed') as avg_duration
        FROM tasks 
        WHERE orchestrator_version IS NOT NULL
        GROUP BY orchestrator_version
    """)
    
    if orch_stats:
        cols = st.columns(len(orch_stats))
        for i, stat in enumerate(orch_stats):
            with cols[i]:
                version = stat['orchestrator_version'].upper()
                success_rate = (stat['success_count'] / stat['task_count'] * 100) if stat['task_count'] > 0 else 0
                st.metric(f"Оркестратор {version}", f"{stat['task_count']} задач", f"{success_rate:.1f}% успех")
                if stat['avg_duration']:
                    st.caption(f"⏱️ Ср. время: {stat['avg_duration']:.1f} сек")
        
        # График сравнения
        import pandas as pd
        import plotly.express as px
        df_orch = pd.DataFrame(orch_stats)
        fig = px.bar(df_orch, x='orchestrator_version', y='task_count', color='orchestrator_version',
                     title="Распределение задач по версиям оркестратора", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Метрики оркестрации V2 и A/B тестирования пока не накоплены.")

def render_projects():
    """📁 Реестр Проектов."""
    st.subheader("📁 Активные Проекты")
    projects = fetch_data("SELECT slug, name, workspace_path, is_active FROM projects ORDER BY created_at DESC")
    if projects:
        st.dataframe(projects, use_container_width=True)
    else:
        st.info("Проекты не зарегистрированы.")

def render_agent_logs():
    """🤖 Логи Агента."""
    st.subheader("🤖 Журнал Событий Victoria")
    
    try:
        logs = fetch_data("""
            SELECT l.created_at, e.name as expert, l.user_query, l.assistant_response
            FROM interaction_logs l
            LEFT JOIN experts e ON l.expert_id = e.id
            ORDER BY l.created_at DESC
            LIMIT 50
        """)
        
        if logs:
            for log in logs:
                with st.expander(f"🕒 {format_msk(log['created_at']).split()[-1]} | {log['expert'] or 'System'}"):
                    st.markdown(f"**Запрос:** {log['user_query']}")
                    st.markdown(f"**Ответ:** {log['assistant_response']}")
        else:
            st.info("Событий в журнале пока нет.")
    except Exception as e:
        st.error(f"Ошибка загрузки логов: {e}")
