import streamlit as st
import json
import subprocess
import traceback
import psycopg2
from datetime import datetime
from database_service import fetch_data, get_db_connection, get_project_slugs, _normalize_metadata

def render_scout_tab():
    """Вкладка Разведка и симуляции."""
    tabs_scout = st.tabs(["🚀 Симулятор", "📢 Маркетинг", "🕵️‍♂️ Разведка"])
    with tabs_scout[0]:
        render_simulator()
    with tabs_scout[1]:
        render_marketing()
    with tabs_scout[2]:
        render_scout()

def render_simulator():
    """🚀 Симулятор бизнес-идей."""
    st.subheader("🚀 Бизнес-симулятор Singularity")
    with st.form("simulation_form"):
        idea = st.text_area("Опишите вашу идею или стратегию для анализа:", placeholder="Например: Запуск нового SaaS для автоматизации юристов на базе нашей Knowledge OS")
        project_sim = st.selectbox("Проект", ["— Не указан / внутренняя —"] + get_project_slugs(), key="sim_project")
        submit = st.form_submit_button("Запустить Симуляцию Совета Директоров")
        if submit and idea:
            project_ctx_sim = None if project_sim == "— Не указан / внутренняя —" else project_sim
            sim_id = None
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO simulations (idea) VALUES (%s) RETURNING id", (idea,))
                    row = cur.fetchone()
                    if row:
                        sim_id = row['id']
                    conn.commit()
    
            if sim_id is None:
                st.error("❌ Не удалось создать запись симуляции в БД.")
            else:
                try:
                    result = subprocess.run(
                        ["docker", "exec", "-d", "knowledge_os_worker",
                         "python3", "/app/knowledge_os/app/simulator.py", str(sim_id)],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        st.success(f"✅ Симуляция #{sim_id} запущена. Результат появится ниже через 1-2 минуты.")
                    else:
                        st.warning(f"⚠️ Ошибка запуска через Docker: {result.stderr or 'неизвестно'}")
                        _create_simulation_task(sim_id, idea, project_ctx_sim)
                except Exception as e:
                    _create_simulation_task(sim_id, idea, project_ctx_sim)

    st.markdown("---")
    st.subheader("История Симуляций")
    
    def delete_simulation(sim_id):
        """Удаляет симуляцию из базы данных."""
        if sim_id is None or sim_id == "N/A":
            st.error("❌ Некорректный id симуляции")
            return False
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM simulations WHERE id = %s", (sim_id,))
                    deleted = cur.rowcount
                    conn.commit()
            return deleted > 0
        except Exception as e:
            st.error(f"❌ Ошибка удаления симуляции: {e}")
            return False

    history = fetch_data("SELECT id, idea, result, created_at FROM simulations ORDER BY created_at DESC LIMIT 10")
    if history:
        for sim in history:
            sim_id = sim.get('id', 'N/A')
            sim_date = sim.get('created_at', datetime.now())
            sim_date_str = sim_date.strftime('%d.%m %H:%M') if isinstance(sim_date, datetime) else str(sim_date)
            sim_idea = sim.get('idea', 'Нет описания')
            sim_result = sim.get('result')
            
            if not sim_result and sim_id != 'N/A':
                task_for_sim = fetch_data(
                    "SELECT result FROM tasks WHERE status = 'completed' AND metadata->>'simulation_id' = %s ORDER BY updated_at DESC LIMIT 1",
                    (str(sim_id),)
                )
                if task_for_sim and task_for_sim[0].get('result'):
                    sim_result = task_for_sim[0]['result']
                    try:
                        with get_db_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute("UPDATE simulations SET result = %s WHERE id = %s AND (result IS NULL OR result = '')", (sim_result, sim_id))
                                conn.commit()
                    except Exception:
                        pass

            delete_key = f"delete_sim_{sim_id}"
            with st.expander(f"📌 #{sim_id} | {sim_date_str} | {sim_idea[:50]}..."):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**Идея:** {sim_idea}")
                    if sim_result:
                        st.markdown(f"**Результат:**\n{sim_result}")
                    else:
                        st.info("⌛ Симуляция еще выполняется или не завершена.")
                with col2:
                    if st.button("🗑️ Удалить", key=delete_key, type="secondary", use_container_width=True):
                        if delete_simulation(sim_id):
                            st.success("✅ Симуляция удалена")
                            st.cache_data.clear()
                            st.rerun()
    else:
        st.info("Пока нет симуляций")

def _create_simulation_task(sim_id, idea, project_context):
    """Создать задачу для Виктории, если прямой запуск не удался."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata, project_context)
                    SELECT %s, %s, 'pending',
                        (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                        (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                        %s, %s
                    WHERE EXISTS (SELECT 1 FROM experts WHERE name = 'Виктория')
                """, (f"🚀 Симуляция бизнес-идеи #{sim_id}", f"Провести симуляцию бизнес-идеи: {idea}", 
                      json.dumps({"source": "dashboard_simulator", "simulation_id": sim_id, "idea": idea}), project_context))
                conn.commit()
        st.info("📋 Задача создана в системе. Виктория обработает её автоматически.")
    except Exception as e:
        st.error(f"❌ Ошибка создания задачи: {e}")

def render_marketing():
    """📢 Маркетинг и генерация контента."""
    st.subheader("📢 Генератор Рекламы и Контента")
    with st.form("ad_gen_form"):
        product_desc = st.text_area("Описание вашего продукта/услуги", placeholder="Например: Магазин фермерских продуктов с доставкой в МСК")
        project_marketing = st.selectbox("Проект", ["— Не указан / внутренняя —"] + get_project_slugs(), key="marketing_project")
        submitted = st.form_submit_button("Создать рекламную стратегию")
        if submitted and product_desc:
            project_ctx_marketing = None if project_marketing == "— Не указан / внутренняя —" else project_marketing
            with st.spinner("Отдел маркетинга готовит стратегию..."):
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata, project_context)
                                SELECT %s, %s, 'pending',
                                    (SELECT id FROM experts WHERE name = 'Артем' LIMIT 1),
                                    (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                                    %s, %s
                                WHERE EXISTS (SELECT 1 FROM experts WHERE name = 'Артем')
                            """, (
                                "📢 Рекламная стратегия",
                                f"Создать рекламную стратегию для продукта/услуги: {product_desc[:200]}",
                                json.dumps({"source": "dashboard_marketing", "product_desc": product_desc}),
                                project_ctx_marketing
                            ))
                            conn.commit()
                    st.info("📋 Задача создана. Отдел маркетинга (Артем) обработает её через worker.")
                except Exception as e:
                    st.error(f"Не удалось создать задачу для маркетинга: {e}")

def render_scout():
    """🕵️‍♂️ Разведка и мониторинг рынка."""
    st.markdown("""
    <div style="background: linear-gradient(145deg, #1e1e2e, #11111b); border: 2px solid #f38ba8; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
        <h3 style="color: #f38ba8; margin-top: 0;">🌟 Enhanced Разведка (Максимум)</h3>
        <p style="color: #c9d1d9;">
            <strong>Что делает:</strong><br>
            ✅ Собирает данные со <strong>всех существующих источников</strong><br>
            ✅ Использует <strong>мировые практики</strong> competitive intelligence<br>
            ✅ Глубокий анализ через <strong>локальные модели</strong> (SWOT, Porter's Five Forces, PEST)<br>
            ✅ Детальные отчеты с <strong>структурированными данными</strong><br>
            ✅ Анализ конкурентов, ценообразования, отзывов, трендов
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("enhanced_scout_form"):
        col1, col2 = st.columns(2)
        with col1:
            target_biz = st.text_input("Ваша компания", value="Столичные окна")
        with col2:
            location = st.text_input("Локация", value="Чебоксары и Новочебоксарск")
    
        extra_competitors = st.text_input(
            "Дополнительные конкуренты (через запятую)", 
            value="",
            help="Укажите конкретных конкурентов для глубокого анализа"
        )
    
        use_enhanced = st.checkbox(
            "🚀 Использовать Enhanced разведку (максимум источников + глубокий анализ)", 
            value=True,
            help="Включает множественные источники, структурированный анализ и детальные отчеты"
        )
        project_scout = st.selectbox("Проект", ["— Не указан / внутренняя —"] + get_project_slugs(), key="scout_project")
        run_scout = st.form_submit_button("🕵️ Запустить максимальную разведку", use_container_width=True)
    
        if run_scout:
            project_ctx_scout = None if project_scout == "— Не указан / внутренняя —" else project_scout
            st.info(f"🕵️ Глеб Enhanced отправлен на задание в {location}...")
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        task_desc = f"Провести {'Enhanced ' if use_enhanced else ''}разведку конкурентов для '{target_biz}' в {location}"
                        if extra_competitors and extra_competitors.strip():
                            task_desc += f". Дополнительные конкуренты: {extra_competitors.strip()}"
                
                        task_title = f"🕵️ {'Enhanced ' if use_enhanced else ''}Разведка: {target_biz}"
                        task_metadata = json.dumps({
                            "source": "dashboard_scout", 
                            "business": target_biz, 
                            "location": location,
                            "enhanced": use_enhanced,
                            "extra_competitors": extra_competitors.strip() if extra_competitors and extra_competitors.strip() else None
                        })
                
                        cur.execute("""
                            INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata, project_context)
                            SELECT 
                                %s, %s, 'pending', 
                                (SELECT id FROM experts WHERE name = 'Глеб' LIMIT 1),
                                (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                                %s, %s
                            WHERE EXISTS (SELECT 1 FROM experts WHERE name = 'Глеб')
                            RETURNING id
                        """, (task_title, task_desc, task_metadata, project_ctx_scout))
                        task_row = cur.fetchone()
                        conn.commit()
                
                        if task_row:
                            st.success(f"✅ Разведка запущена! Задача создана.")
                        else:
                            st.warning("⚠️ Задача не создана. Проверьте эксперта Глеб.")
            except Exception as e:
                st.error(f"❌ Ошибка создания задачи: {e}")

    st.markdown("---")
    st.subheader("📊 Последние отчеты разведки")
    
    def delete_scout_report(report_id):
        """Удаляет отчет разведки из базы данных"""
        try:
            if report_id is None: return False
            report_id_str = str(report_id).strip()
            if not report_id_str: return False
            
            if 'deleted_reports' not in st.session_state:
                st.session_state.deleted_reports = set()
            
            if report_id_str in st.session_state.deleted_reports:
                return False

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM knowledge_nodes WHERE id::text = %s", (report_id_str,))
                    rows_deleted = cur.rowcount
                    conn.commit()
            
            if rows_deleted > 0:
                st.session_state.deleted_reports.add(report_id_str)
                return True
            return False
        except Exception as e:
            st.error(f"❌ Ошибка удаления отчета: {e}")
            return False

    scout_reports = fetch_data("""
        SELECT id, LEFT(content, 500) as content, created_at, metadata 
        FROM knowledge_nodes 
        WHERE metadata->>'source' IN ('scout_research', 'enhanced_scout_research', 'enhanced_scout_report')
        ORDER BY created_at DESC LIMIT 20
    """)

    if scout_reports:
        if 'deleted_reports' not in st.session_state:
            st.session_state.deleted_reports = set()
        scout_reports = [r for r in scout_reports if str(r.get('id', '')) not in st.session_state.deleted_reports]
        
        for rep in scout_reports:
            rep_id = str(rep.get('id'))
            rep_date = rep.get('created_at', datetime.now())
            date_str = rep_date.strftime('%d.%m.%Y %H:%M') if isinstance(rep_date, datetime) else str(rep_date)[:16]
            
            metadata = _normalize_metadata(rep.get('metadata'))
            business = metadata.get('business_target', 'Не указано')
            location = metadata.get('location', 'Не указано')
            
            delete_key = f"delete_scout_{rep_id}"
            with st.expander(f"📊 Отчет | {date_str} | 🏢 {business} | 📍 {location}"):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(rep.get('content', 'Нет содержимого'))
                with col2:
                    if st.button("🗑️ Удалить", key=delete_key, type="secondary", use_container_width=True):
                        if delete_scout_report(rep_id):
                            st.success("✅ Отчет удален")
                            st.cache_data.clear()
                            st.rerun()
    else:
        st.info("📭 Пока нет отчетов разведки.")
