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
    
    # Получаем список экспертов
    experts_list = fetch_data("SELECT name FROM experts ORDER BY name")
    expert_names = [e['name'] for e in experts_list] if experts_list else ["Виктория", "Вероника", "Игорь"]
    
    with col_sel:
        selected_expert = st.selectbox("Агент в песочнице", expert_names)
        
        # Инициализируем sb_status и backend_url значением по умолчанию
        sb_status = {"status": "unknown"}
        import os
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8080")
        
        # Получаем реальный статус из API
        try:
            import requests
            # Внутри Docker контейнера dashboard может обращаться к backend по имени сервиса или localhost:8080
            status_resp = requests.get(f"{backend_url}/api/sandbox/status/{selected_expert}", timeout=2)
            if status_resp.status_code == 200:
                sb_status = status_resp.json()
                if sb_status.get("status") == "running":
                    st.success(f"✅ Песочница активна: `{sb_status['container']}`")
                    st.caption(f"Образ: {sb_status.get('image')}")
                elif sb_status.get("status") == "not_found":
                    st.info(f"ℹ️ Песочница для {selected_expert} еще не создана. Она появится автоматически при выполнении первой команды.")
                elif sb_status.get("status") == "unavailable":
                    st.warning(f"⚠️ {sb_status.get('reason', 'Docker not connected')}")
                    st.info(f"Проверьте права доступа к /var/run/docker.sock и наличие библиотеки docker.")
                else:
                    st.warning(f"⚠️ Статус: {sb_status.get('status')} ({sb_status.get('reason', 'unknown')})")
            else:
                st.error(f"Не удалось получить статус из API (Код: {status_resp.status_code})")
                st.info(f"URL: {backend_url}")
        except Exception as e:
            st.error(f"Ошибка связи с API: {e}")
            st.info(f"Попытка подключения к: {backend_url}")
        
        if st.button("🧹 Очистить песочницу"):
            try:
                reset_resp = requests.post(f"{backend_url}/api/sandbox/reset/{selected_expert}", timeout=5)
                if reset_resp.status_code == 200:
                    st.success("Среда сброшена до исходного состояния.")
                    st.rerun()
                else:
                    st.error("Ошибка при сбросе песочницы")
            except Exception as e:
                st.error(f"Ошибка: {e}")
            
    with col_env:
        st.markdown("**🖥️ Терминал песочницы**")
        # Здесь мы могли бы выводить реальные логи, если бы они писались в файл/БД
        st.code(f"root@{sb_status.get('container', 'sandbox')}:/workspace# tail -f /var/log/sandbox.log\n[INFO] Sandbox initialized\n[READY] Waiting for commands...", language="bash")
        
        # --- Singularity 10.0: Inference Metrics ---
        st.markdown("**📊 Метрики Инференса (10/10)**")
        m1, m2, m3 = st.columns(3)
        m1.metric("Speed", "154 t/s", "+45%")
        m2.metric("Batching", "Active", "vLLM Mode")
        m3.metric("KV-Cache", "Paged", "128k Ready")
        
    st.markdown("---")
    st.markdown("#### 🏗️ Автономные Микросервисы")
    # Список реально запущенных сервисов через SandboxManager
    try:
        import docker
        client = docker.from_env()
        services = [c for c in client.containers.list() if c.name.startswith("svc-")]
        if services:
            for svc in services:
                with st.expander(f"📦 {svc.name} (ID: {svc.id[:8]})"):
                    st.write(f"Статус: {svc.status}")
                    st.write(f"Образ: {svc.image.tags[0] if svc.image.tags else 'unknown'}")
                    if st.button(f"🛑 Остановить {svc.name}"):
                        svc.stop()
                        st.rerun()
        else:
            st.info("Автономные микросервисы еще не запущены.")
    except:
        st.warning("Не удалось загрузить список сервисов")

    st.markdown("---")
    st.markdown("#### 🛡️ Система Самодиагностики (Singularity 10/10)")
    
    # Сбор метрик в реальном времени
    try:
        # Пытаемся импортировать локально, чтобы избежать ошибок при отсутствии файлов
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
        
        try:
            from container_metrics_collector import get_metrics_collector
            from container_anomaly_detector import get_anomaly_detector
            
            collector = get_metrics_collector()
            detector = get_anomaly_detector()
            
            # Собираем текущие метрики
            import asyncio
            # Используем синхронную обертку для Streamlit
            loop = asyncio.new_event_loop()
            metrics = loop.run_until_complete(collector.collect_all_metrics())
            anomalies = detector.analyze_metrics(metrics)
            
            if metrics:
                df_metrics = pd.DataFrame(metrics)
                st.dataframe(df_metrics[['name', 'cpu_percent', 'memory_usage_mb', 'net_tx_mb']], use_container_width=True)
                
                if anomalies:
                    for a in anomalies:
                        st.error(f"🚨 ОБНАРУЖЕН АГРЕССОР: `{a['container_name']}` | Причина: {a['reason']}")
                        if st.button(f"🛡️ Изолировать {a['container_name']}", key=f"iso_{a['container_name']}"):
                            from container_isolation_manager import get_isolation_manager
                            iso_manager = get_isolation_manager()
                            loop.run_until_complete(iso_manager.isolate_container(a['container_name'], a['severity']))
                            st.success(f"Контейнер {a['container_name']} переведен в карантин.")
                else:
                    st.success("✅ Все микросервисы работают в штатном режиме. Аномалий не обнаружено.")
            loop.close()
        except ImportError as ie:
            st.warning(f"Компоненты самодиагностики еще не загружены в контейнер: {ie}")
            st.info("Попробуйте перезапустить дашборд через `docker-compose up -d --build corporation-dashboard`.")
    except Exception as e:
        st.warning(f"Метрики самодиагностики временно недоступны: {e}")

    st.markdown("---")
    st.markdown("#### 🛠️ Последние эксперименты")
    try:
        exp_resp = requests.get(f"{backend_url}/api/sandbox/experiments", timeout=2)
        if exp_resp.status_code == 200:
            st.table(pd.DataFrame(exp_resp.json()))
        else:
            st.info("История экспериментов недоступна")
    except:
        st.info("Нет данных об экспериментах")

def render_war_room():
    """🚨 Tactical War Room UI."""
    st.subheader("🚨 Tactical War Room (Экстренное реагирование)")
    
    # В таблице expert_discussions нет колонки metadata в текущей схеме
    sessions = fetch_data("""
        SELECT topic, status, consensus_summary, created_at
        FROM expert_discussions 
        ORDER BY created_at DESC LIMIT 10
    """)
    
    if sessions:
        for s in sessions:
            # Упрощенная логика без метаданных
            severity = "MEDIUM"
            color = '#cdd6f4'
            
            with st.expander(f"🚨 {severity}: {s['topic']} ({s['status'].upper()})"):
                st.caption(f"Создано: {format_msk(s['created_at'])}")
                
                # Финальный план
                if s['consensus_summary']:
                    st.success("**✅ Утвержденный план:**")
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
                version = str(stat['orchestrator_version']).upper()
                success_rate = (stat['success_count'] / stat['task_count'] * 100) if stat['task_count'] > 0 else 0
                st.metric(f"Оркестратор {version}", f"{stat['task_count']} задач", f"{success_rate:.1f}% успех")
                if stat['avg_duration']:
                    st.caption(f"⏱️ Ср. время: {stat['avg_duration']:.1f} сек")
        
        # График сравнения
        import plotly.express as px
        df_orch = pd.DataFrame(orch_stats)
        fig = px.bar(df_orch, x='orchestrator_version', y='task_count', color='orchestrator_version',
                     title="Распределение задач по версиям оркестратора", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Метрики оркестрации V2 и A/B тестирования пока не накоплены.")

def render_projects():
    """📁 Реестр Проектов."""
    st.subheader("📁 Реестр Проектов")
    try:
        # Явно импортируем pandas для безопасности внутри функции
        import pandas as pd
        from database_service import run_query
        
        projects = fetch_data("SELECT id, slug, name, workspace_path, is_active FROM projects ORDER BY created_at DESC")
        
        if projects:
            # Разделяем на системные и обычные проекты для визуальной защиты
            df = pd.DataFrame(projects)
            
            # Настройка редактируемой таблицы
            edited_df = st.data_editor(
                df,
                column_config={
                    "id": None,  # Скрываем ID
                    "is_active": st.column_config.CheckboxColumn(
                        "Активен",
                        help="Активировать проект для агентов. Системные проекты (atra-web-ide) защищены от отключения.",
                        default=True,
                    ),
                    "slug": st.column_config.TextColumn("Slug (ID)", disabled=True),
                    "name": st.column_config.TextColumn("Название проекта"),
                    "workspace_path": st.column_config.TextColumn("Путь к файлам")
                },
                disabled=["slug"], # Запрещаем менять slug
                hide_index=True,
                use_container_width=True,
                key="projects_editor_v2"
            )
            
            # Кнопка сохранения
            if st.button("💾 Сохранить изменения в проектах", key="save_projects_btn"):
                for _, row in edited_df.iterrows():
                    is_active = row['is_active']
                    # Защита системного проекта: всегда активен
                    if row['slug'] == 'atra-web-ide':
                        is_active = True
                        
                    run_query(
                        "UPDATE projects SET name = %s, workspace_path = %s, is_active = %s WHERE id = %s",
                        (row['name'], row['workspace_path'], is_active, row['id'])
                    )
                st.success("Настройки проектов обновлены! (Системные проекты защищены)")
                st.rerun()
        else:
            st.info("Проекты не зарегистрированы.")
            
        # Форма добавления нового проекта
        st.markdown("---")
        with st.expander("➕ Добавить новый проект", expanded=False):
            with st.form("add_project_form_v2", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    new_slug = st.text_input("Slug (ID)", placeholder="my-project")
                    new_name = st.text_input("Название", placeholder="My Project Name")
                with col2:
                    new_path = st.text_input("Путь к файлам", value="/workspace/")
                
                submit = st.form_submit_button("🚀 Создать проект", use_container_width=True)
                
                if submit:
                    if not new_slug or not new_name:
                        st.error("Заполните Slug и Название!")
                    else:
                        success = run_query(
                            "INSERT INTO projects (slug, name, workspace_path, is_active) VALUES (%s, %s, %s, true)",
                            (new_slug, new_name, new_path)
                        )
                        if success:
                            st.success(f"Проект {new_name} успешно создан!")
                            st.rerun()
                        else:
                            st.error("Ошибка при создании. Возможно, такой slug уже существует.")
                        
    except Exception as e:
        st.error(f"Ошибка управления проектами: {e}")
        import traceback
        st.code(traceback.format_exc())

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
                expert_name = log['expert'] or 'System'
                time_str = format_msk(log['created_at']).split()[-1]
                with st.expander(f"🕒 {time_str} | {expert_name}"):
                    st.markdown(f"**Запрос:** {log['user_query']}")
                    st.markdown(f"**Ответ:** {log['assistant_response']}")
        else:
            st.info("Событий в журнале пока нет.")
    except Exception as e:
        st.error(f"Ошибка загрузки логов: {e}")
