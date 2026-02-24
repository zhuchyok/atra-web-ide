import asyncio
import getpass
import json
import os
from datetime import datetime

import asyncpg
import pandas as pd
import streamlit as st

# Page config
st.set_page_config(page_title="ATRA Federated Intelligence", page_icon="🧠", layout="wide")

# Styling
st.markdown(
    """
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e4451; }
    .status-online { color: #00ff00; font-weight: bold; }
    .status-offline { color: #ff4b4b; font-weight: bold; }
    </style>
""",
    unsafe_allow_html=True,
)


async def get_routing_metrics(conn):
    """Получение метрик гибридного роутинга"""
    try:
        # Проверяем, есть ли колонки для метрик роутинга
        columns_exist = (
            await conn.fetchval("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'semantic_ai_cache'
            AND column_name IN ('routing_source', 'performance_score', 'tokens_saved')
        """)
            == 3
        )

        if not columns_exist:
            return {}

        # Статистика по источникам роутинга за последние 24 часа
        routing_stats = await conn.fetch("""
            SELECT
                routing_source,
                COUNT(*) as count,
                AVG(performance_score) as avg_performance,
                SUM(tokens_saved) as total_tokens_saved,
                AVG(tokens_saved) as avg_tokens_saved
            FROM semantic_ai_cache
            WHERE routing_source IS NOT NULL
            AND last_used_at > NOW() - INTERVAL '24 hours'
            GROUP BY routing_source
        """)

        # Общая статистика за сегодня
        today_stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total_requests,
                SUM(tokens_saved) as total_tokens_saved_today,
                AVG(performance_score) as avg_performance_today
            FROM semantic_ai_cache
            WHERE routing_source IS NOT NULL
            AND last_used_at > CURRENT_DATE
        """)

        # Статистика по узлам
        node_stats = {}
        for stat in routing_stats:
            source = stat["routing_source"]
            if source:
                node_stats[source] = {
                    "count": stat["count"],
                    "avg_performance": round(float(stat["avg_performance"] or 0), 3),
                    "total_tokens_saved": stat["total_tokens_saved"] or 0,
                    "avg_tokens_saved": round(float(stat["avg_tokens_saved"] or 0), 0),
                }

        return {
            "nodes": node_stats,
            "today": {
                "total_requests": today_stats["total_requests"] or 0,
                "total_tokens_saved": today_stats["total_tokens_saved"] or 0,
                "avg_performance": round(float(today_stats["avg_performance"] or 0), 3),
            },
        }
    except Exception as e:
        return {}


async def get_stats():
    # Единая локальная БД (в Docker задаётся DATABASE_URL через compose)
    _db = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    DB_URL_LOCAL = os.getenv("DATABASE_URL_LOCAL", _db)
    DB_URL_REMOTE = os.getenv("DATABASE_URL_REMOTE", _db)  # та же локальная БД

    data = {"local": {}, "remote": {}, "online": False, "routing": {}}

    # 1. Local Data
    try:
        conn = await asyncpg.connect(DB_URL_LOCAL)
        data["local"]["nodes"] = await conn.fetchval("SELECT count(*) FROM knowledge_nodes")
        data["local"]["experts"] = await conn.fetch(
            "SELECT name, role, department, metadata FROM experts ORDER BY (metadata->'hierarchy'->>'level')::int ASC NULLS LAST, name ASC"
        )
        data["local"]["tasks"] = await conn.fetch(
            "SELECT status, count(*) as count FROM tasks GROUP BY status"
        )
        data["local"]["cache"] = await conn.fetch(
            "SELECT query_text, usage_count, expert_name FROM semantic_ai_cache ORDER BY usage_count DESC LIMIT 10"
        )

        # Получаем метрики роутинга
        data["routing"] = await get_routing_metrics(conn)

        await conn.close()
    except Exception as e:
        st.error(f"Local DB Error: {e}")

    # 2. Remote Data (Federation)
    try:
        conn = await asyncpg.connect(DB_URL_REMOTE, timeout=2)
        data["remote"]["nodes"] = await conn.fetchval("SELECT count(*) FROM knowledge_nodes")
        data["remote"]["experts_count"] = await conn.fetchval("SELECT count(*) FROM experts")
        data["remote"]["tasks"] = await conn.fetch(
            "SELECT status, count(*) as count FROM tasks GROUP BY status"
        )
        data["online"] = True
        await conn.close()
    except:
        data["online"] = False

    return data


def main():
    st.title("🧠 ATRA Singularity: Federated Dashboard")

    # Run async collector
    data = asyncio.run(get_stats())

    # Header Status
    status_class = "status-online" if data["online"] else "status-offline"
    status_text = "🟢 GLOBAL SYNC ACTIVE" if data["online"] else "🔴 BUNKER MODE (OFFLINE)"

    st.markdown(
        f"**Node:** {getpass.getuser()}'s MacBook Pro (M4) | **Status:** <span class='{status_class}'>{status_text}</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    # --- TOP ROW: GLOBAL + LOCAL METRICS ---
    col1, col2, col3, col4 = st.columns(4)

    total_nodes = data["local"].get("nodes", 0) + (
        data["remote"].get("nodes", 0) if data["online"] else 0
    )
    total_experts = len(data["local"].get("experts", []))

    col1.metric(
        "Общие знания (L1+L2)",
        total_nodes,
        delta=f"+{data['remote'].get('nodes', 0)} с сервера" if data["online"] else "OFFLINE",
    )
    col2.metric("Активные эксперты", total_experts, delta="Synced")

    # Calculate savings
    cache_data = data["local"].get("cache", [])
    cache_hits = sum(row["usage_count"] for row in cache_data)
    total_savings = cache_hits * 1500

    col3.metric("Кэш-хиты (MacBook)", cache_hits, delta="0 Tokens Used")
    col4.metric("Экономия токенов", f"{total_savings:,}")

    # --- SECOND ROW: TEAM HIERARCHY ---
    st.write("### 👥 Иерархия и структура сотрудников (Federated View)")

    experts = data["local"].get("experts", [])
    levels = {
        0: "👑 Координаторы (Level 0)",
        1: "👔 Лиды отделов (Level 1)",
        2: "🛠 Специалисты (Level 2)",
    }

    # Вспомогательная функция для безопасного получения metadata
    def get_metadata_dict(metadata):
        """Преобразует metadata в словарь, если это строка JSON"""
        if metadata is None:
            return {}
        if isinstance(metadata, str):
            try:
                return json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                return {}
        if isinstance(metadata, dict):
            return metadata
        return {}

    for lvl, label in levels.items():
        st.write(f"**{label}**")
        lvl_experts = []
        for e in experts:
            metadata = get_metadata_dict(e.get("metadata"))
            hierarchy = metadata.get("hierarchy", {})
            if hierarchy.get("level") == lvl:
                lvl_experts.append(e)
        if lvl_experts:
            cols = st.columns(5)
            for i, exp in enumerate(lvl_experts):
                with cols[i % 5]:
                    st.info(f"**{exp['name']}**  \n{exp['role']}")
        else:
            st.caption("Данные на этом уровне отсутствуют локально")
        st.divider()

    # --- THIRD ROW: HYBRID ROUTING METRICS (Singularity 5.0) ---
    routing_data = data.get("routing", {})
    if routing_data and routing_data.get("today", {}).get("total_requests", 0) > 0:
        st.write("### 🚀 Hybrid Intelligence Metrics (Singularity 5.0)")

        rcol1, rcol2, rcol3, rcol4 = st.columns(4)
        today = routing_data.get("today", {})

        rcol1.metric("Запросов сегодня", today.get("total_requests", 0))
        rcol2.metric("Токенов сэкономлено", f"{today.get('total_tokens_saved', 0):,}")
        rcol3.metric("Средний Performance", f"{today.get('avg_performance', 0):.2f}")

        # Расчет экономии в USD (примерно $0.002 за 1K токенов)
        tokens_saved = today.get("total_tokens_saved", 0)
        usd_saved = (tokens_saved / 1000) * 0.002
        rcol4.metric("Экономия (USD)", f"${usd_saved:.2f}")

        # Детализация по узлам
        nodes = routing_data.get("nodes", {})
        if nodes:
            st.write("#### 📊 Распределение по узлам (24 часа)")
            node_df_data = []
            for node_name, node_stats in nodes.items():
                node_df_data.append(
                    {
                        "Узел": node_name.replace("local_", "").replace("_", " ").title(),
                        "Запросов": node_stats.get("count", 0),
                        "Performance": node_stats.get("avg_performance", 0),
                        "Токенов сэкономлено": node_stats.get("total_tokens_saved", 0),
                    }
                )

            if node_df_data:
                node_df = pd.DataFrame(node_df_data)
                st.dataframe(node_df, use_container_width=True)

                # График распределения запросов
                st.bar_chart(node_df.set_index("Узел")[["Запросов", "Токенов сэкономлено"]])
    else:
        st.info("📊 Метрики роутинга пока недоступны (требуется миграция БД или нет данных)")

    # --- FOURTH ROW: TASK SYNC ---
    c1, c2 = st.columns(2)

    with c1:
        st.write("### ⚙️ Задачи: MacBook (L1)")
        tasks_local = data["local"].get("tasks")
        if tasks_local:
            df_tasks = pd.DataFrame([dict(r) for r in tasks_local])
            st.bar_chart(df_tasks.set_index("status"))
        else:
            st.success("Локальная очередь пуста.")

    with c2:
        st.write("### 🌐 Задачи: Global Server (L2)")
        tasks_remote = data["remote"].get("tasks")
        if data["online"] and tasks_remote:
            df_remote = pd.DataFrame([dict(r) for r in tasks_remote])
            st.bar_chart(df_remote.set_index("status"))
        elif not data["online"]:
            st.error("Сервер оффлайн.")
        else:
            st.warning("Серверные задачи отсутствуют.")

    # Sidebar
    st.sidebar.image("https://img.icons8.com/color/512/brain.png", width=100)
    st.sidebar.title("Singularity v5.0")
    st.sidebar.markdown("**Predictive & Adaptive Intelligence**")
    st.sidebar.markdown("**Дашборд:** [http://localhost:8501/](http://localhost:8501/)")
    st.sidebar.info("Локальная БД (Mac Studio). Все данные — на этом сервере.")

    # Routing status
    if routing_data and routing_data.get("nodes"):
        st.sidebar.write("### 🚀 Hybrid Routing")
        for node_name, node_stats in routing_data["nodes"].items():
            st.sidebar.metric(
                node_name.replace("local_", "").title(), f"{node_stats.get('count', 0)} requests"
            )

    if st.sidebar.button("Принудительная синхронизация"):
        st.sidebar.write("🔄 Запуск синхронизации...")
        # Conceptual: trigger script here

    st.sidebar.write(f"Обновлено: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
