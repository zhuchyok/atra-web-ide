import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys
import networkx as nx
import subprocess
import httpx
import asyncio
import logging
import json
import traceback
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import time

logger = logging.getLogger(__name__)

# Корпорация: корень и каталог приложения (дашборд = часть корпорации, ищем модули в корпорации)
_DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))  # knowledge_os/dashboard
CORPORATION_ROOT = os.path.dirname(_DASHBOARD_DIR)            # knowledge_os
CORPORATION_APP_DIR = os.path.join(CORPORATION_ROOT, "app")  # knowledge_os/app — singularity_9_ab_tester, evaluator

# Fallback для Docker (compose монтирует репо в /app/project)
for _candidate in (CORPORATION_APP_DIR, "/app/project/knowledge_os/app"):
    if os.path.isdir(_candidate) and os.path.isfile(os.path.join(_candidate, "evaluator.py")):
        if _candidate not in sys.path:
            sys.path.insert(0, _candidate)
        CORPORATION_APP_DIR = _candidate
        break
if os.path.isdir(CORPORATION_APP_DIR) and CORPORATION_APP_DIR not in sys.path:
    sys.path.insert(0, CORPORATION_APP_DIR)

# Предзагрузка evaluator из app, чтобы singularity_9_ab_tester всегда видел модуль (в т.ч. в Docker)
import logging as _dashboard_logging
_dashboard_log = _dashboard_logging.getLogger("corporation_dashboard")
if "evaluator" not in sys.modules:
    _eval_py = os.path.join(CORPORATION_APP_DIR, "evaluator.py")
    if os.path.isfile(_eval_py):
        import importlib.util
        try:
            _spec = importlib.util.spec_from_file_location("evaluator", _eval_py)
            if _spec and _spec.loader:
                _mod = importlib.util.module_from_spec(_spec)
                sys.modules["evaluator"] = _mod
                _spec.loader.exec_module(_mod)
                _dashboard_log.info("evaluator loaded CORPORATION_APP_DIR=%s", CORPORATION_APP_DIR)
        except Exception as _eval_err:
            _dashboard_log.warning("evaluator load failed CORPORATION_APP_DIR=%s: %s", CORPORATION_APP_DIR, _eval_err, exc_info=True)

# Настройка страницы
st.set_page_config(
    page_title="Intelligence Command Center | ATRA Corporation",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

VECTOR_CORE_URL = os.getenv("VECTOR_CORE_URL", "http://localhost:8001")

def get_embedding(text: str) -> list:
    """Get embedding from VectorCore microservice."""
    try:
        with httpx.Client() as client:
            response = client.post(f"{VECTOR_CORE_URL}/encode", json={"text": text}, timeout=30.0)
            response.raise_for_status()
            return response.json()["embedding"]
    except (httpx.HTTPError, httpx.TimeoutException, httpx.RequestError) as e:
        st.error(f"Ошибка VectorCore (HTTP): {e}")
        return [0.0] * 384
    except (ValueError, KeyError, TypeError) as e:
        st.error(f"Ошибка VectorCore (данные): {e}")
        return [0.0] * 384
    except Exception as e:
        st.error(f"Неожиданная ошибка VectorCore: {e}")
        return [0.0] * 384

# Стили для премиального вида

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #05070a;
    }
    
    .main { background-color: #05070a; }
    
    /* Адаптивность для мобильных устройств */
    @media (max-width: 768px) {
        .premium-card {
            padding: 16px !important;
            margin-bottom: 12px !important;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            flex-wrap: wrap;
            gap: 8px !important;
        }
        
        .stTabs [data-baseweb="tab"] {
            font-size: 12px !important;
            padding: 8px 12px !important;
        }
        
        [data-testid="stSidebar"] {
            min-width: 200px !important;
        }
        
        .expert-header {
            font-size: 16px !important;
        }
        
        .card-text {
            font-size: 13px !important;
        }
    }
    
    @media (max-width: 480px) {
        .premium-card {
            padding: 12px !important;
        }
        
        .stTabs [data-baseweb="tab"] {
            font-size: 11px !important;
            padding: 6px 10px !important;
        }
        
        h1 {
            font-size: 24px !important;
        }
        
        h2 {
            font-size: 20px !important;
        }
        
        h3 {
            font-size: 18px !important;
        }
    }
    
    .premium-card {
        background: linear-gradient(145deg, #161b22, #0d1117);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 16px;
        transition: transform 0.2s, border-color 0.2s;
    }
    
    .premium-card:hover {
        border-color: #58a6ff;
        transform: translateY(-2px);
    }
    
    .directive-card {
        background: linear-gradient(145deg, #1e1e2e, #11111b);
        border: 2px solid #f38ba8;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
    }
    
    .domain-badge {
        background-color: #1f6feb;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 12px;
        display: inline-block;
    }
    
    .usage-badge {
        background-color: #238636;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        float: right;
    }
    
    .card-text {
        color: #c9d1d9;
        font-size: 15px;
        line-height: 1.6;
        margin-top: 10px;
        white-space: pre-wrap;
    }
    
    .liquidity-bar {
        height: 4px;
        background-color: #30363d;
        border-radius: 2px;
        margin-top: 15px;
    }
    
    .liquidity-fill {
        height: 100%;
        background: linear-gradient(90deg, #58a6ff, #1f6feb);
        border-radius: 2px;
    }

    .stTabs [data-baseweb="tab-list"] { gap: 24px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: transparent !important; border: none !important; color: #8b949e !important; font-weight: 600 !important; transition: all 0.3s; }
    .stTabs [data-baseweb="tab"]:hover { color: #58a6ff !important; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom: 2px solid #58a6ff !important; }
    
    .expert-header { font-size: 18px; font-weight: 800; color: #ffffff; margin-bottom: 4px; }
    .expert-role { font-size: 14px; color: #8b949e; margin-bottom: 12px; }
    
    /* Анимации для карточек */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .premium-card {
        animation: fadeIn 0.3s ease-in;
    }
    
    /* Анимация пульсации для индикатора активности */
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.7; transform: scale(1.1); }
    }
    
    /* Анимация обновления данных */
    @keyframes slideIn {
        from { opacity: 0; transform: translateX(-10px); }
        to { opacity: 1; transform: translateX(0); }
    }
    
    /* Индикатор загрузки */
    .loading-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border: 2px solid #58a6ff;
        border-top-color: transparent;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    
    /* Плавное появление метрик */
    [data-testid="stMetricValue"] {
        animation: slideIn 0.5s ease-out;
    }
    
    /* Улучшенные метрики */
    [data-testid="stMetricValue"] {
        font-size: 28px !important;
        font-weight: 800 !important;
    }
    
    /* Скроллбар стилизация */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #0d1117;
    }
    ::-webkit-scrollbar-thumb {
        background: #30363d;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #58a6ff;
    }
    
    /* Улучшенные кнопки */
    .stButton > button {
        background: linear-gradient(145deg, #1f6feb, #58a6ff);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(88, 166, 255, 0.4);
    }
    </style>
    """, unsafe_allow_html=True)

# Connection pool для оптимизации (кэш сбрасывается при «connection closed» после рестарта Postgres)
@st.cache_resource
def _cached_db_connection():
    """Внутреннее кэшированное подключение. Используйте get_db_connection()."""
    db_urls = [
        os.getenv("DATABASE_URL"),
        "postgresql://admin:secret@localhost:5432/knowledge_os",
        "postgresql://admin:secret@127.0.0.1:5432/knowledge_os"
    ]
    for db_url in db_urls:
        if db_url:
            try:
                conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=3)
                _set_query_timeout(conn)
                return conn
            except (psycopg2.Error, psycopg2.OperationalError, ConnectionError, TimeoutError) as e:
                logger.debug(f"Не удалось подключиться к {db_url}: {e}")
                continue
    try:
        conn = psycopg2.connect(
            "postgresql://admin:secret@localhost:5432/knowledge_os",
            cursor_factory=RealDictCursor,
            connect_timeout=3
        )
        _set_query_timeout(conn)
        return conn
    except (psycopg2.Error, psycopg2.OperationalError) as e:
        st.error(f"❌ Критическая ошибка: Не удалось подключиться к базе данных. Проверьте, что PostgreSQL запущен.")
        raise


def get_db_connection():
    """Подключение к БД. При «connection closed» после рестарта Postgres сбрасывает кэш и переподключается."""
    try:
        conn = _cached_db_connection()
        if conn.closed:
            raise psycopg2.OperationalError("connection already closed")
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError) as e:
        err = str(e).lower()
        if "closed" in err or "connection" in err or "server closed" in err or "terminated" in err:
            _cached_db_connection.clear()
            return _cached_db_connection()
        raise


def _set_query_timeout(conn, seconds=15):
    """Ограничить время выполнения запросов — чтобы дашборд не зависал на «Running fetch_data»."""
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{int(seconds) * 1000}'")
    except Exception:
        pass

@st.cache_data(ttl=60)  # Кэш на 60 секунд для оптимизации
def fetch_data(query, params=None, cache_key=None):
    """Оптимизированная функция получения данных с кэшированием"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    except (psycopg2.Error, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
        st.error(f"Ошибка БД: {e}")
        return []
    except Exception as e:
        st.error(f"Неожиданная ошибка БД: {e}")
        return []


@st.cache_data(ttl=15)  # Короткий кэш для вкладки «Задачи» — новые задачи видны в течение 15 сек
def fetch_data_tasks(query, params=None):
    """Данные для вкладки Задачи (обновляются чаще)."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    except (psycopg2.Error, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
        st.error(f"Ошибка БД: {e}")
        return []
    except Exception as e:
        st.error(f"Неожиданная ошибка БД: {e}")
        return []

def run_query(query, params=None):
    """Выполняет SQL запрос на изменение данных. Без плейсхолдеров вызывайте run_query(query) без params."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            if params is not None and params != ():
                cur.execute(query, params)
            else:
                cur.execute(query)
            conn.commit()
        return True
    except (psycopg2.Error, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
        st.error(f"Ошибка БД при выполнении запроса: {e}")
        return False
    except Exception as e:
        st.error(f"Неожиданная ошибка выполнения запроса: {e}")
        return False


def _normalize_metadata(metadata):
    """Приводит metadata к dict (из БД может прийти JSON-строка)."""
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            return json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}

def _quick_db_check():
    """Проверка подключения к БД (отдельное подключение, без кэша; вызывается с таймаутом).
    Возвращает (True,) при успехе или (False, сообщение_об_ошибке)."""
    db_url = os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:5432/knowledge_os"
    try:
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=3)
        try:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '5000'")
                cur.execute("SELECT 1")
                cur.fetchone()
            return (True,)
        finally:
            conn.close()
    except Exception as e:
        return (False, str(e))


def main():
    # Инициализация session_state для отслеживания удаленных отчетов
    if 'deleted_reports' not in st.session_state:
        st.session_state.deleted_reports = set()

    # Быстрая проверка БД с таймаутом — если не ответила за 10 сек, показываем ошибку и не крутим «Running fetch_data»
    if st.session_state.get("_db_ok") is not True:
        with st.spinner("Подключение к БД..."):
            try:
                with ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(_quick_db_check)
                    result = fut.result(timeout=10)
                ok = result[0] if result else False
                err_msg = result[1] if isinstance(result, tuple) and len(result) > 1 else None
                if not ok:
                    hint = "Проверьте, что PostgreSQL запущен и DATABASE_URL верный."
                    if err_msg and "too many clients" in err_msg.lower():
                        hint = "Слишком много подключений к БД. Перезапустите PostgreSQL: `docker restart knowledge_postgres` или увеличьте max_connections."
                    st.error(f"Не удалось подключиться к базе данных. {hint}")
                    if err_msg:
                        st.code(err_msg, language=None)
                    st.stop()
                st.session_state["_db_ok"] = True
            except FuturesTimeoutError:
                st.error("Таймаут подключения к БД (10 сек). Проверьте PostgreSQL и сеть (в Docker: сервис knowledge_postgres в atra-network).")
                if st.button("Повторить"):
                    del st.session_state["_db_ok"]
                    st.rerun()
                st.stop()
            except Exception as e:
                st.error(f"Ошибка БД: {e}")
                if st.button("Повторить"):
                    del st.session_state["_db_ok"]
                    st.rerun()
                st.stop()

    # Получаем время последнего обновления данных из БД
    last_update_data = fetch_data("""
        SELECT 
            GREATEST(
                COALESCE((SELECT MAX(updated_at) FROM tasks), '1970-01-01'::timestamp),
                COALESCE((SELECT MAX(created_at) FROM knowledge_nodes), '1970-01-01'::timestamp),
                COALESCE((SELECT MAX(created_at) FROM interaction_logs), '1970-01-01'::timestamp)
            ) as last_db_update
    """)
    
    last_db_update = None
    if last_update_data and last_update_data[0] and last_update_data[0].get('last_db_update'):
        last_db_update = last_update_data[0]['last_db_update']
        if isinstance(last_db_update, datetime):
            if last_db_update.tzinfo is None:
                last_db_update = last_db_update.replace(tzinfo=timezone.utc)
            time_since_update = datetime.now(timezone.utc) - last_db_update
            minutes_ago = int(time_since_update.total_seconds() / 60)
            hours_ago = int(time_since_update.total_seconds() / 3600)
            
            if minutes_ago < 1:
                update_status = "только что"
                status_color = "#238636"
            elif minutes_ago < 60:
                update_status = f"{minutes_ago} мин назад"
                status_color = "#fab387" if minutes_ago > 30 else "#238636"
            elif hours_ago < 24:
                update_status = f"{hours_ago} ч назад"
                status_color = "#fab387"
            else:
                days_ago = int(time_since_update.total_seconds() / 86400)
                update_status = f"{days_ago} дн назад"
                status_color = "#f38ba8"
        else:
            update_status = "неизвестно"
            status_color = "#8b949e"
    else:
        update_status = "нет данных"
        status_color = "#8b949e"
    
    current_time = datetime.now(timezone.utc).strftime('%H:%M:%S')
    
    # Автообновление (опционально, через query params; совместимость со старыми Streamlit)
    query_params = getattr(st, "query_params", None)
    auto_refresh_interval = query_params.get("refresh", None) if query_params is not None else None
    if auto_refresh_interval:
        try:
            interval = int(auto_refresh_interval)
            if interval > 0:
                time.sleep(interval)
                st.rerun()
        except (ValueError, TypeError):
            pass
    
    # Главный заголовок с метриками в реальном времени
    col_header1, col_header2, col_header3, col_header4, col_header5 = st.columns([2, 1, 1, 1, 1])
    with col_header1:
        st.title("🏢 ATRA Corporation | Intelligence Command Center")
        # Анимированный индикатор активности с информацией о последнем обновлении БД
        status_emoji = "🟢" if status_color == "#238636" else "🟡" if status_color == "#fab387" else "🔴"
        st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 8px; margin-top: 4px; flex-wrap: wrap;">
                <span style="color: #8b949e; font-size: 12px;">🕐 Страница загружена: {current_time} UTC</span>
                <span style="color: {status_color}; font-size: 12px; font-weight: 600;">{status_emoji} БД: {update_status}</span>
                <span style="display: inline-block; width: 8px; height: 8px; background: {status_color}; border-radius: 50%; animation: pulse 2s infinite;"></span>
                <span style="color: {status_color}; font-size: 11px; font-weight: 600;">LIVE</span>
            </div>
            <style>
                @keyframes pulse {{
                    0%, 100% {{ opacity: 1; transform: scale(1); }}
                    50% {{ opacity: 0.7; transform: scale(1.2); }}
                }}
            </style>
        """, unsafe_allow_html=True)
        
        # Информация о кэшировании
        st.caption(f"💾 Данные кэшируются на 60 сек. Нажмите 🔄 для принудительного обновления.")
    with col_header2:
        # Быстрая статистика (кэшированная)
        with st.spinner(""):
            tasks_data = fetch_data("SELECT COUNT(*) as count FROM tasks")
            total_tasks = tasks_data[0]['count'] if tasks_data and tasks_data[0] else 0
            st.metric("Задач", f"{total_tasks:,}")
    with col_header3:
        with st.spinner(""):
            nodes_data = fetch_data("SELECT COUNT(*) as count FROM knowledge_nodes")
            total_nodes = nodes_data[0]['count'] if nodes_data and nodes_data[0] else 0
            st.metric("Узлов знаний", f"{total_nodes:,}")
    with col_header4:
        with st.spinner(""):
            experts_data = fetch_data("SELECT COUNT(*) as count FROM experts")
            total_experts = experts_data[0]['count'] if experts_data and experts_data[0] else 0
            st.metric("Экспертов", total_experts)
    with col_header5:
        # Кнопка принудительного обновления
        if st.button("🔄", help="Обновить все данные", use_container_width=True, key="header_refresh"):
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("---")

    # --- Главная Директива Совета (Top Priority) ---
    latest_directive = fetch_data("""
        SELECT content, created_at FROM knowledge_nodes 
        WHERE metadata->>'type' = 'board_directive' 
        ORDER BY created_at DESC LIMIT 1
    """)
    if latest_directive and latest_directive[0]:
        d0 = latest_directive[0]
        created = d0.get('created_at')
        created_str = created.strftime('%d.%m %H:%M') if hasattr(created, 'strftime') else (str(created)[:16] if created else 'N/A')
        content_safe = d0.get('content') or ''
        st.markdown(f"""
            <div class="directive-card">
                <div style="color: #f38ba8; font-weight: 800; font-size: 14px; text-transform: uppercase; margin-bottom: 10px;">
                    🚨 СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА ДИРЕКТОРОВ (от {created_str})
                </div>
                <div style="color: #cdd6f4; font-size: 16px; line-height: 1.6;">{content_safe}</div>
            </div>
        """, unsafe_allow_html=True)

    # --- Боковая панель (улучшенная) ---
    with st.sidebar:
        st.header("🌐 Статус Холдинга")
        
        # Статус системы с индикаторами
        col_status1, col_status2 = st.columns(2)
        with col_status1:
            st.success("✅ СИСТЕМА: ONLINE")
        with col_status2:
            st.info("🤖 ЯДРО: AUTONOMOUS")
        
        # Проверка доступности сервисов (с кэшированием для оптимизации)
        st.markdown("### 🔌 Статус сервисов")
        
        @st.cache_data(ttl=30)  # Кэш на 30 секунд для проверки сервисов
        def check_services():
            """Проверка статуса сервисов с кэшированием"""
            services = {"PostgreSQL": "✅", "Victoria Agent": "✅"}
            
            # Определяем, работаем ли мы в контейнере
            # В контейнере используем host.docker.internal для доступа к хосту
            import os
            is_container = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER') == 'true'
            host_url = "http://host.docker.internal" if is_container else "http://localhost"
            
            # Проверка MLX API (быстрая проверка)
            try:
                mlx_response = httpx.get(f"{host_url}:11435/health", timeout=3, follow_redirects=True)
                # MLX API может возвращать 200 с JSON ошибкой rate limit, или 429
                # В любом случае, если сервер отвечает - он работает
                if mlx_response.status_code in [200, 429]:
                    try:
                        data = mlx_response.json()
                        # Проверяем статус в ответе
                        if data.get('status') == 'healthy' or 'service' in data:
                            services["MLX API"] = "✅"
                        elif 'error' in data:
                            # Если есть ошибка, но это rate limit - сервис работает
                            error_msg = str(data.get('error', '')).lower()
                            if 'rate limit' in error_msg or '429' in error_msg:
                                services["MLX API"] = "✅"
                            else:
                                # Другая ошибка - возможно проблема
                                services["MLX API"] = "⚠️"
                        else:
                            # Любой другой ответ со статусом 200/429 - сервис работает
                            services["MLX API"] = "✅"
                    except (ValueError, KeyError, TypeError):
                        # Если не JSON, но статус 200/429 - сервис отвечает, значит работает
                        services["MLX API"] = "✅"
                else:
                    services["MLX API"] = "⚠️"
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
                # Если не удалось подключиться, пробуем localhost (на случай если не в контейнере)
                try:
                    mlx_response = httpx.get("http://localhost:11435/health", timeout=3)
                    # Любой ответ (200, 429) означает, что сервис работает
                    if mlx_response.status_code in [200, 429]:
                        services["MLX API"] = "✅"
                    else:
                        services["MLX API"] = "⚠️"
                except (httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.debug(f"MLX API fallback failed: {e}")
                    services["MLX API"] = "⚠️"
            except (httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError) as e:
                logger.debug(f"MLX API connection failed: {e}")
                services["MLX API"] = "⚠️"
            
            # Проверка Ollama (быстрая проверка)
            try:
                ollama_response = httpx.get(f"{host_url}:11434/api/tags", timeout=2)
                services["Ollama"] = "✅" if ollama_response.status_code == 200 else "⚠️"
            except Exception as e:
                # Если не удалось подключиться, пробуем localhost (на случай если не в контейнере)
                try:
                    ollama_response = httpx.get("http://localhost:11434/api/tags", timeout=2)
                    services["Ollama"] = "✅" if ollama_response.status_code == 200 else "⚠️"
                except (httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError) as e:
                    logger.debug(f"Ollama fallback failed: {e}")
                    services["Ollama"] = "⚠️"
            
            return services
        
        services_status = check_services()
        for service, status in services_status.items():
            st.markdown(f"{status} {service}")
        if services_status.get("MLX API") == "⚠️":
            st.caption("⚠️ MLX API выключен или недоступен (порт 11435). С хоста: `scripts/start_mlx_api_server.sh` или проверка: `curl -s http://localhost:11435/health`. Из Docker дашборд проверяет host.docker.internal:11435.")
        st.markdown("---")
        
        # Финансовая статистика (ROI) - с кэшированием
        st.markdown("### 💰 Финансовый P&L (24ч)")
        finance_data = fetch_data("""
            SELECT 
                SUM(token_usage) as total_tokens, 
                SUM(cost_usd) as total_cost,
                COUNT(*) FILTER (WHERE metadata->>'model_type' = 'local' OR metadata->>'model_type' IS NULL) as local_models,
                COUNT(*) FILTER (WHERE metadata->>'model_type' NOT IN ('local', 'cursor-agent') AND metadata->>'model_type' IS NOT NULL) as cloud_models
            FROM interaction_logs 
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        if finance_data and finance_data[0]:
            fd = finance_data[0]
            total_tokens = fd['total_tokens'] or 0
            total_cost = fd['total_cost'] or 0.0
            local_models = fd['local_models'] or 0
            cloud_models = fd['cloud_models'] or 0
            
            # Виртуальная стоимость для локальных моделей (энергозатраты)
            # Примерно $0.0001 за 1000 токенов (очень примерная оценка)
            virtual_cost_local = (total_tokens / 1000) * 0.0001 if local_models > 0 else 0.0
            total_cost_display = total_cost + virtual_cost_local
            
            st.metric("Расход токенов", f"{total_tokens:,}")
            
            if total_cost > 0:
                st.metric("Виртуальные затраты", f"${total_cost_display:.4f}", 
                         help="Включает облачные модели + виртуальные затраты на локальные модели")
            else:
                st.metric("Виртуальные затраты", f"${total_cost_display:.4f}", 
                         help="Локальные модели (Ollama/MLX) - виртуальная стоимость (энергозатраты)")
            
            # Информация о типах моделей
            if local_models > 0 or cloud_models > 0:
                model_info = []
                if local_models > 0:
                    model_info.append(f"🆓 Локальные: {local_models}")
                if cloud_models > 0:
                    model_info.append(f"☁️ Облачные: {cloud_models}")
                if model_info:
                    st.caption(" | ".join(model_info))
        else:
            st.metric("Расход токенов", "0")
            st.metric("Виртуальные затраты", "$0.0000")
        
        st.markdown("---")
        
        # Интеллектуальный Капитал - оптимизировано (один запрос вместо нескольких)
        st.header("📊 Интеллектуальный Капитал")
        stats_data = fetch_data("""
            SELECT 
                COUNT(*) as total_nodes,
                SUM(usage_count) as total_usage,
                AVG(confidence_score) as avg_confidence,
                COUNT(*) FILTER (WHERE is_verified = true) as verified_nodes
            FROM knowledge_nodes
        """)
        if stats_data and stats_data[0]:
            stats = stats_data[0]
            st.metric("Узлов знаний", f"{stats['total_nodes']:,}")
            st.metric("Использований", f"{stats['total_usage'] or 0:,}")
            st.metric("Средний confidence", f"{stats['avg_confidence']:.2f}" if stats.get('avg_confidence') else "N/A")
            st.metric("Проверено", f"{stats['verified_nodes']:,}")
        
        st.markdown("---")
        
        # Быстрая статистика задач (оптимизированный запрос)
        st.header("🛠️ Задачи")
        task_stats = fetch_data("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'failed') as failed
            FROM tasks
        """)
        if task_stats and task_stats[0]:
            ts = task_stats[0]
            st.metric("✅ Завершено", f"{ts['completed']:,}")
            st.metric("🔄 В работе", f"{ts['in_progress']:,}")
            st.metric("⏳ Ожидает", f"{ts['pending']:,}")
            if ts.get('failed', 0) > 0:
                st.metric("❌ Ошибок", f"{ts['failed']:,}")
                # Детали failed-задач: заголовок и источник
                failed_tasks = fetch_data("""
                    SELECT id, title, metadata->>'source' as source, metadata->>'severity' as severity, updated_at
                    FROM tasks WHERE status = 'failed'
                    ORDER BY updated_at DESC LIMIT 10
                """)
                if failed_tasks:
                    with st.expander("Показать детали ошибок"):
                        for ft in failed_tasks:
                            src = ft.get('source') or '-'
                            sev = ft.get('severity') or '-'
                            st.caption(f"**{ft.get('title', '')[:70]}** | источник: {src} | severity: {sev}")
        
        st.markdown("---")

        st.subheader("🔍 Семантический поиск")
        search_q = st.text_input("Спросите систему...", placeholder="Например: тренды маркетинга 2025", key="semantic_search")
        if search_q:
            with st.spinner("🔍 Поиск в базе знаний..."):
                embedding = get_embedding(search_q)
                results = fetch_data("""
                    SELECT k.content, d.name as domain, (1 - (k.embedding <=> %s::vector)) as similarity
                    FROM knowledge_nodes k JOIN domains d ON k.domain_id = d.id
                    WHERE k.embedding IS NOT NULL
                    ORDER BY similarity DESC LIMIT 5
                """, (str(embedding),))

                if results:
                    for i, r in enumerate(results):
                        similarity_pct = (r['similarity'] * 100) if r.get('similarity') is not None else 0
                        color = "#58a6ff" if similarity_pct > 80 else "#fab387" if similarity_pct > 60 else "#8b949e"
                        content_preview = (r.get('content') or '')[:200]
                        if len((r.get('content') or '')) > 200:
                            content_preview += "..."
                        domain_name = r.get('domain') or 'N/A'
                        st.markdown(f"""
                            <div style="background: #0d1117; padding: 12px; border-radius: 8px; border-left: 3px solid {color}; margin-bottom: 8px;">
                                <div style="font-size: 11px; color: #8b949e;">
                                    {domain_name} | Сходство: <strong style="color: {color};">{similarity_pct:.1f}%</strong>
                                </div>
                                <div style="font-size: 13px; color: #c9d1d9; margin-top: 4px;">{content_preview}</div>
                            </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("Ничего не найдено. Попробуйте другой запрос.")
        
        st.markdown("---")
        
        # Быстрые действия
        st.subheader("⚡ Быстрые действия")
        
        col_action1, col_action2, col_action3 = st.columns(3)
        with col_action1:
            if st.button("🔄 Обновить все данные", use_container_width=True, key="refresh_all"):
                st.cache_data.clear()
                st.success("✅ Кэш очищен! Данные обновятся при следующем запросе.")
                st.rerun()
        
        with col_action2:
            if st.button("📊 Экспорт данных", use_container_width=True, key="export_data"):
                st.info("Функция экспорта в разработке")
        
        with col_action3:
            # Автообновление (Streamlit не выполняет <script> в markdown — используйте кнопку 🔄)
            auto_refresh = st.checkbox("🔄 Автообновление", value=False, key="auto_refresh")
            if auto_refresh:
                refresh_interval = st.selectbox("Интервал (сек)", [30, 60, 120, 300], index=1, key="refresh_interval")
                st.caption(f"Для обновления данных нажмите кнопку 🔄 «Обновить все данные» выше (автоперезагрузка страницы в Streamlit недоступна).")
        
        # Информация о кэшировании
        st.markdown("---")
        st.markdown("### ℹ️ О кэшировании и обновлении")
        
        # Статистика изменений за последние минуты
        changes_stats = fetch_data("""
            SELECT 
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 minute') as last_minute,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '5 minutes') as last_5min,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as last_hour,
                MAX(created_at) as last_task_created,
                MAX(updated_at) as last_task_updated
            FROM tasks
        """)
        
        if changes_stats and changes_stats[0]:
            cs = changes_stats[0]
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("📝 Задач за 1 мин", cs.get('last_minute', 0) or 0)
            with col_stat2:
                st.metric("📝 Задач за 5 мин", cs.get('last_5min', 0) or 0)
            with col_stat3:
                st.metric("📝 Задач за час", cs.get('last_hour', 0) or 0)
            
            # Время последнего изменения
            if cs.get('last_task_updated') or cs.get('last_task_created'):
                last_change = cs.get('last_task_updated') or cs.get('last_task_created')
                if last_change:
                    if isinstance(last_change, datetime):
                        if last_change.tzinfo is None:
                            last_change = last_change.replace(tzinfo=timezone.utc)
                        time_diff = datetime.now(timezone.utc) - last_change
                        minutes_diff = int(time_diff.total_seconds() / 60)
                        
                        if minutes_diff < 5:
                            change_status = f"🟢 Активно (изменено {minutes_diff} мин назад)"
                        elif minutes_diff < 60:
                            change_status = f"🟡 Недавно (изменено {minutes_diff} мин назад)"
                        else:
                            hours_diff = int(time_diff.total_seconds() / 3600)
                            change_status = f"🔴 Неактивно (изменено {hours_diff} ч назад)"
                        
                        st.caption(f"**Последнее изменение:** {change_status}")
        
        # Статистика активности системы
        activity_stats = fetch_data("""
            SELECT 
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as tasks_1h,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as tasks_24h,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as tasks_7d
            FROM knowledge_nodes
        """)
        
        if activity_stats and activity_stats[0]:
            as_data = activity_stats[0]
            st.markdown("### 📊 Активность системы")
            col_act1, col_act2, col_act3 = st.columns(3)
            with col_act1:
                st.metric("📚 Узлов за час", as_data.get('tasks_1h', 0) or 0)
            with col_act2:
                st.metric("📚 Узлов за 24ч", as_data.get('tasks_24h', 0) or 0)
            with col_act3:
                st.metric("📚 Узлов за 7 дней", as_data.get('tasks_7d', 0) or 0)
        
        st.info("""
        **Как работает обновление данных:**
        
        - 📊 **Данные из БД**: Кэшируются на 60 секунд
        - 🔌 **Проверка сервисов**: Кэшируется на 30 секунд
        - 🔄 **Автоматическое обновление**: При перезагрузке страницы
        - ⚡ **Принудительное обновление**: Кнопка "🔄 Обновить все данные"
        - 🔄 **Автообновление**: Включите чекбокс для автоматического обновления
        
        **Что обновляется:**
        - ✅ Количество задач, узлов знаний, экспертов
        - ✅ Финансовые метрики (токены, затраты)
        - ✅ Статус сервисов (MLX API, Ollama)
        - ✅ Все метрики в вкладках
        
        **Примечание:** Данные обновляются автоматически каждые 60 секунд при перезагрузке страницы.
        """)

    # Вкладки ---
    tabs = st.tabs([
        "🚀 Симулятор",
        "📈 Финансы ИИ",
        "📡 Радар",
        "🕵️ Рекрутинг",
        "🛡️ Иммунитет",
        "🎭 Аудит Кода",
        "📢 Маркетинг",
        "🕵️‍♂️ Разведка",
        "💎 Ликвидность (ROI)", 
        "🏛️ Структура", 
        "🎯 Стратегия OKR", 
        "🎓 Академия ИИ", 
        "🛠️ Задачи",
        "📊 Аналитика", 
        "🕸️ Карта Разума", 
        "⚖️ Ревизия",
        "📊 SLA Мониторинг",
        "🛡️ Безопасность",
        "⚡ Энергия",
        "🚀 Singularity 9.0",
        "📋 Поставить задачу",
        "🤖 Агент"
    ])

    # 🚀 СИМУЛЯТОР (Hypothesis 2)
    with tabs[0]:
        st.subheader("🚀 Симулятор Бизнес-Идей")
        with st.form("simulation_form"):
            idea = st.text_area("Опишите вашу идею или стратегию для анализа:", placeholder="Например: Запуск нового SaaS для автоматизации юристов на базе нашей Knowledge OS")
            submit = st.form_submit_button("Запустить Симуляцию Совета Директоров")
            if submit and idea:
                # Вставляем идею и получаем ID
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
                    # Запускаем скрипт симуляции в фоне через docker exec (путь в контейнере knowledge_os_worker)
                    try:
                        result = subprocess.run(
                            ["docker", "exec", "-d", "knowledge_os_worker",
                             "python3", "/app/knowledge_os/app/simulator.py", str(sim_id)],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            st.success(f"✅ Симуляция #{sim_id} запущена. Результат появится ниже через 1-2 минуты.")
                        else:
                            st.warning(f"⚠️ Запуск симуляции: {result.stderr or 'неизвестно'}")
                            try:
                                conn = get_db_connection()
                                with conn.cursor() as cur:
                                    cur.execute("""
                                        INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                                        SELECT %s, %s, 'pending',
                                            (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                                            (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                                            %s
                                        WHERE EXISTS (SELECT 1 FROM experts WHERE name = 'Виктория')
                                    """, (f"🚀 Симуляция бизнес-идеи #{sim_id}", f"Провести симуляцию бизнес-идеи: {idea}", json.dumps({"source": "dashboard_simulator", "simulation_id": sim_id, "idea": idea})))
                                    conn.commit()
                                st.info("📋 Задача создана в системе. Виктория обработает её автоматически.")
                            except Exception as e:
                                st.error(f"❌ Ошибка создания задачи: {e}")
                    except FileNotFoundError:
                        try:
                            conn = get_db_connection()
                            with conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                                    SELECT %s, %s, 'pending',
                                        (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                                        (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                                        %s
                                    WHERE EXISTS (SELECT 1 FROM experts WHERE name = 'Виктория')
                                """, (f"🚀 Симуляция бизнес-идеи #{sim_id}", f"Провести симуляцию бизнес-идеи: {idea}", json.dumps({"source": "dashboard_simulator", "simulation_id": sim_id, "idea": idea})))
                                conn.commit()
                            st.success("✅ Задача создана в системе. Виктория обработает её автоматически через worker.")
                        except Exception as e:
                            st.error(f"❌ Ошибка создания задачи: {e}")
                    except Exception as e:
                        st.error(f"❌ Ошибка запуска симуляции: {e}")

        st.markdown("---")
        st.subheader("История Симуляций")
        st.caption("💡 Вы можете удалить ненужные симуляции, нажав кнопку 🗑️ Удалить")
        
        # Функция удаления симуляции
        def delete_simulation(sim_id: int):
            """Удаляет симуляцию из базы данных"""
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM simulations WHERE id = %s", (sim_id,))
                    conn.commit()
                return True
            except Exception as e:
                st.error(f"❌ Ошибка удаления симуляции: {e}")
                return False
        
        history = fetch_data("SELECT id, idea, result, created_at FROM simulations ORDER BY created_at DESC LIMIT 10")
        if history:
            for sim in history:
                sim_id = sim.get('id', 'N/A')
                sim_date = sim.get('created_at', datetime.now())
                if isinstance(sim_date, datetime):
                    sim_date_str = sim_date.strftime('%d.%m %H:%M')
                else:
                    sim_date_str = str(sim_date)
                sim_idea = sim.get('idea', 'Нет описания')
                sim_result = sim.get('result')
                # Если в симуляции нет результата — проверяем связанную задачу (task мог завершиться, а simulations.result не обновился)
                if not sim_result and sim_id != 'N/A':
                    task_for_sim = fetch_data(
                        "SELECT result FROM tasks WHERE status = 'completed' AND metadata->>'simulation_id' = %s ORDER BY updated_at DESC LIMIT 1",
                        (str(sim_id),)
                    )
                    if task_for_sim and task_for_sim[0].get('result'):
                        sim_result = task_for_sim[0]['result']
                        # Синхронизируем в simulations, чтобы в следующий раз результат был уже в БД
                        try:
                            conn = get_db_connection()
                            with conn.cursor() as cur:
                                cur.execute("UPDATE simulations SET result = %s WHERE id = %s AND (result IS NULL OR result = '')", (sim_result, sim_id))
                                conn.commit()
                        except Exception:
                            pass
                if not sim_result:
                    sim_result = None
                
                # Создаем уникальный ключ для кнопки удаления
                delete_key = f"delete_sim_{sim_id}"
                
                with st.expander(f"📌 #{sim_id} | {sim_date_str} | {sim_idea[:50]}..."):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**Идея:** {sim_idea}")
                        if sim_result:
                            st.markdown(f"**Результат:**\n{sim_result}")
                        else:
                            st.info("⌛ Симуляция еще выполняется или не завершена. Проверьте вкладку «Задачи» — если задача завершена, результат подтянется при обновлении.")
                    with col2:
                        if st.button("🗑️ Удалить", key=delete_key, type="secondary", use_container_width=True):
                            if delete_simulation(sim_id):
                                st.success("✅ Симуляция удалена")
                                st.rerun()
                            else:
                                st.error("❌ Не удалось удалить симуляцию")
        else:
            st.info("Пока нет симуляций")

    # 📈 ФИНАНСЫ ИИ (улучшенная версия)
    with tabs[1]:
        st.subheader("📈 Финансовый Учет Интеллекта (Knowledge P&L)")
        
        # Метрики вверху (оптимизированные запросы)
        finance_metrics = fetch_data("""
            SELECT 
                COUNT(*) as total_experts,
                COUNT(*) FILTER (WHERE virtual_budget IS NOT NULL) as experts_with_budget,
                SUM(virtual_budget) as total_budget,
                AVG(performance_score) as avg_performance
            FROM experts
        """)
        
        if finance_metrics and finance_metrics[0]:
            fm = finance_metrics[0]
            metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
            with metrics_col1:
                st.metric("👥 Всего экспертов", f"{fm['total_experts']}")
            with metrics_col2:
                st.metric("💰 С бюджетом", f"{fm['experts_with_budget']}")
            with metrics_col3:
                st.metric("💵 Общий бюджет", f"${fm['total_budget']:.2f}" if fm['total_budget'] else "$0.00")
            with metrics_col4:
                st.metric("⭐ Средняя производительность", f"{fm['avg_performance']:.2f}" if fm['avg_performance'] else "N/A")
        
        st.markdown("---")
        
        # Визуализации
        exp_finance = fetch_data("SELECT name, department, virtual_budget, performance_score FROM experts WHERE virtual_budget IS NOT NULL ORDER BY virtual_budget DESC")
        if exp_finance:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown("### 💰 Бюджеты Департаментов")
                dept_budgets = pd.DataFrame(exp_finance).groupby('department')['virtual_budget'].sum().reset_index()
                dept_budgets = dept_budgets.sort_values('virtual_budget', ascending=False)
                fig_dept = px.bar(
                    dept_budgets, x='department', y='virtual_budget', 
                    color='virtual_budget',
                    template="plotly_dark",
                    labels={'department': 'Департамент', 'virtual_budget': 'Бюджет ($)'},
                    color_continuous_scale='Viridis'
                )
                fig_dept.update_layout(xaxis_tickangle=-45, height=400)
                st.plotly_chart(fig_dept, use_container_width=True)
            
            with col2:
                st.markdown("### 🏆 Топ Прибыльных Экспертов")
                df_finance = pd.DataFrame(exp_finance)
                df_finance['ROI'] = (df_finance['virtual_budget'] * df_finance['performance_score']).round(2)
                df_finance = df_finance.sort_values('ROI', ascending=False).head(20)
                
                # Интерактивная таблица
                st.dataframe(
                    df_finance[['name', 'department', 'virtual_budget', 'performance_score', 'ROI']].rename(columns={
                        'name': 'Эксперт',
                        'department': 'Департамент',
                        'virtual_budget': 'Бюджет',
                        'performance_score': 'Производительность',
                        'ROI': 'ROI'
                    }),
                    hide_index=True,
                    use_container_width=True
                )
                
                # График производительности
                fig_perf = px.scatter(
                    df_finance.head(15), x='virtual_budget', y='performance_score',
                    size='ROI', hover_data=['name', 'department'],
                    title="📊 Бюджет vs Производительность",
                    template="plotly_dark",
                    labels={'virtual_budget': 'Бюджет ($)', 'performance_score': 'Производительность'}
                )
                st.plotly_chart(fig_perf, use_container_width=True)

    # 📡 РАДАР (Hypothesis 4)
    with tabs[2]:
        st.subheader("📡 Интеллектуальный Радар Аномалий")
        anomalies = fetch_data("SELECT description, severity, status, created_at FROM anomalies ORDER BY created_at DESC LIMIT 20")
        if anomalies:
            for anom in anomalies:
                color = "#f38ba8" if anom.get('severity') == 'high' else "#fab387"
                created_at = anom.get('created_at')
                anom_created_str = created_at.strftime('%d.%m %H:%M') if hasattr(created_at, 'strftime') else (str(created_at)[:16] if created_at else 'N/A')
                st.markdown(f"""
                    <div style="background: #161b22; border-left: 5px solid {color}; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                        <span style="float: right; color: #8b949e; font-size: 12px;">{anom_created_str}</span>
                        <div style="color: {color}; font-weight: 800; font-size: 14px; text-transform: uppercase;">КРИТИЧНОСТЬ: {anom.get('severity', 'N/A')}</div>
                        <div style="color: #c9d1d9; margin-top: 5px;">{anom.get('description') or ''}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ Аномалий не обнаружено. Радар чист.")

    # 🕵️ РЕКРУТИНГ (Singularity 3.0)
    with tabs[3]:
        st.subheader("🕵️ Автономный Рекрутинг Экспертов")
        hired_experts = fetch_data("""
            SELECT name, role, department, metadata->>'hired_at' as hired_at 
            FROM experts 
            WHERE metadata->>'is_autonomous' = 'true'
            ORDER BY created_at DESC
        """)
        if hired_experts:
            for exp in hired_experts:
                st.markdown(f"""
                    <div class="premium-card">
                        <span class="domain-badge">{exp['department']}</span>
                        <div class="expert-header">👤 {exp['name']}</div>
                        <div class="expert-role">{exp['role']}</div>
                        <div style="font-size: 11px; color: #8b949e;">Нанят автономно: {exp['hired_at']}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Пока не было автономных наймов.")

    # 🛡️ ИММУНИТЕТ (Singularity 3.0)
    with tabs[4]:
        st.subheader("🛡️ Иммунитет: Результаты Стресс-Тестов")
        attacks = fetch_data("""
            SELECT content, expert_consensus->>'adversarial_attack' as attack, 
                   metadata->>'survived' as survived, confidence_score
            FROM knowledge_nodes 
            WHERE metadata->>'adversarial_tested' = 'true'
            ORDER BY created_at DESC LIMIT 15
        """)
        for at in attacks:
            survived = at.get('survived') == 'true'
            status = "✅ ВЫДЕРЖАЛО" if survived else "💀 УНИЧТОЖЕНО"
            color = "#a6e3a1" if survived else "#f38ba8"
            content_preview = (at.get('content') or '')[:150]
            st.markdown(f"""
                <div style="background: #0d1117; border-left: 5px solid {color}; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                    <div style="color: {color}; font-weight: 800;">{status} (Score: {at.get('confidence_score', 'N/A')})</div>
                    <div style="color: #c9d1d9; font-size: 14px; margin-top: 5px;"><b>Знание:</b> {content_preview}{'...' if len(at.get('content') or '') > 150 else ''}</div>
                    <div style="color: #8b949e; font-size: 13px; margin-top: 5px; font-style: italic;"><b>Атака:</b> {at.get('attack') or 'N/A'}</div>
                </div>
            """, unsafe_allow_html=True)

    # 🎭 АУДИТ КОДА (Singularity 3.0)
    with tabs[5]:
        st.subheader("🎭 Когнитивное Зеркало: Аудит Системы")
        audit_tasks = fetch_data("""
            SELECT title, description, metadata->>'severity' as severity, status
            FROM tasks 
            WHERE metadata->>'source' = 'code_auditor'
            ORDER BY created_at DESC LIMIT 10
        """)
        for task in audit_tasks:
            color = "#f38ba8" if task['severity'] == 'high' else "#fab387" if task['severity'] == 'medium' else "#94e2d5"
            st.markdown(f"""
                <div style="background: #11111b; border: 1px solid {color}; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
                    <span style="color: {color}; font-weight: 800; float: right;">{task['severity'].upper()}</span>
                    <div style="font-weight: 700; color: #cdd6f4;">{task['title']}</div>
                    <div style="font-size: 14px; color: #c9d1d9; margin-top: 8px;">{task['description']}</div>
                    <div style="font-size: 12px; color: #8b949e; margin-top: 5px;">Статус: {task['status']}</div>
                </div>
            """, unsafe_allow_html=True)

    # 📢 МАРКЕТИНГ (Новый отдел)
    with tabs[6]:
        st.header("📢 Генератор Рекламных Кампаний")
        with st.form("ad_gen_form"):
            product_desc = st.text_area("Описание вашего продукта/услуги", placeholder="Например: Магазин фермерских продуктов с доставкой в МСК")
            submitted = st.form_submit_button("Создать рекламную стратегию")
            if submitted and product_desc:
                with st.spinner("Отдел маркетинга (Артем, Лиза, Кристина) готовит стратегию..."):
                    strategy_done = False
                    try:
                        script_path = "/app/knowledge_os/app/ad_generator.py"
                        if not os.path.isfile(script_path):
                            script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "ad_generator.py")
                        cmd = ["python3", script_path, product_desc]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                                                cwd=os.path.dirname(os.path.dirname(__file__)) if not script_path.startswith("/app") else "/app")
                        if result.returncode == 0 and (result.stdout or "").strip():
                            st.markdown("### 📋 Финальный План Кампании")
                            st.markdown(result.stdout)
                            st.success("Стратегия успешно сохранена в базу знаний!")
                            strategy_done = True
                        elif result.stderr:
                            st.warning(f"Скрипт вернул предупреждение: {(result.stderr or '')[:300]}")
                    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                        st.warning(f"Запуск скрипта недоступен: {e}")
                    except Exception as e:
                        st.warning(f"Ошибка запуска генератора: {e}")
                    if not strategy_done:
                        try:
                            conn = get_db_connection()
                            with conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                                    SELECT %s, %s, 'pending',
                                        (SELECT id FROM experts WHERE name = 'Артем' LIMIT 1),
                                        (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                                        %s
                                    WHERE EXISTS (SELECT 1 FROM experts WHERE name = 'Артем')
                                """, (
                                    "📢 Рекламная стратегия",
                                    f"Создать рекламную стратегию для продукта/услуги: {product_desc[:200]}",
                                    json.dumps({"source": "dashboard_marketing", "product_desc": product_desc})
                                ))
                                conn.commit()
                            st.info("📋 Задача создана. Отдел маркетинга (Артем) обработает её через worker.")
                        except Exception as e2:
                            st.error(f"Не удалось создать задачу для маркетинга: {e2}")

    # 🕵️‍♂️ РАЗВЕДКА (ENHANCED)
    with tabs[7]:
        st.header("🕵️‍♂️ Бизнес-Разведка: Максимальный Анализ Рынков")
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
            
            run_scout = st.form_submit_button("🕵️ Запустить максимальную разведку", use_container_width=True)
            
            if run_scout:
                st.info(f"🕵️ Глеб Enhanced отправлен на задание в {location}...")
                # Создаем задачу в БД - правильный способ для Docker окружения
                # Worker автоматически обработает задачу через scout_task_processor
                try:
                    conn = get_db_connection()
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
                            INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                            SELECT 
                                %s, %s, 'pending', 
                                (SELECT id FROM experts WHERE name = 'Глеб' LIMIT 1),
                                (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                                %s
                            WHERE EXISTS (SELECT 1 FROM experts WHERE name = 'Глеб')
                            RETURNING id
                        """, (task_title, task_desc, task_metadata))
                        task_row = cur.fetchone()
                        conn.commit()
                        
                        if task_row:
                            mode = "Enhanced (максимум)" if use_enhanced else "базовая"
                            # Извлекаем ID из результата
                            task_id = task_row[0] if isinstance(task_row, (tuple, list)) else (task_row.get('id') if isinstance(task_row, dict) else None)
                            st.success(f"✅ {mode} разведка запущена! Задача создана. Worker обработает её автоматически. Отчет появится через 5-10 минут.")
                            if use_enhanced:
                                st.info("""
                                📊 Enhanced разведка включает:
                                - Множественные источники данных (конкуренты, цены, отзывы, услуги, тренды)
                                - Структурированный анализ конкурентов
                                - Глубокий анализ через локальные модели (SWOT, Porter, PEST)
                                - Детальные отчеты с рекомендациями
                                """)
                        else:
                            st.warning("⚠️ Задача не создана. Проверьте, что эксперт Глеб существует в системе.")
                except Exception as e:
                    st.error(f"❌ Ошибка создания задачи: {e}")
                    st.code(traceback.format_exc())

        st.markdown("---")
        st.subheader("📊 Последние отчеты разведки")
        st.caption("💡 Вы можете удалить ненужные отчеты, нажав кнопку 🗑️ Удалить рядом с каждым отчетом")
        
        # Показываем статистику (базовые + enhanced)
        scout_stats = fetch_data("""
            SELECT 
                COUNT(*) FILTER (WHERE metadata->>'source' = 'scout_research') as basic_reports,
                COUNT(*) FILTER (WHERE metadata->>'source' IN ('enhanced_scout_research', 'enhanced_scout_report')) as enhanced_reports,
                COUNT(*) as total_reports,
                MAX(created_at) as last_report
            FROM knowledge_nodes 
            WHERE metadata->>'source' IN ('scout_research', 'enhanced_scout_research', 'enhanced_scout_report')
        """)
        
        if scout_stats and scout_stats[0]:
            stats = scout_stats[0]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Всего отчетов", stats.get('total_reports', 0))
            with col2:
                st.metric("Базовые", stats.get('basic_reports', 0))
            with col3:
                st.metric("Enhanced", stats.get('enhanced_reports', 0), 
                         delta=f"{stats.get('enhanced_reports', 0)} детальных")
            with col4:
                if stats.get('last_report'):
                    last_date = stats['last_report']
                    if isinstance(last_date, datetime):
                        last_date_str = last_date.strftime('%d.%m.%Y %H:%M')
                    else:
                        last_date_str = str(last_date)
                    st.metric("Последний отчет", last_date_str)
        
        # Показываем последние отчеты (приоритет Enhanced) - включаем ID для удаления
        scout_reports = fetch_data("""
            SELECT id, content, created_at, metadata 
            FROM knowledge_nodes 
            WHERE metadata->>'source' IN ('scout_research', 'enhanced_scout_research', 'enhanced_scout_report')
            ORDER BY 
                CASE 
                    WHEN metadata->>'source' = 'enhanced_scout_report' THEN 1
                    WHEN metadata->>'source' = 'enhanced_scout_research' THEN 2
                    ELSE 3
                END,
                created_at DESC 
            LIMIT 20
        """)
        
        if scout_reports:
            # Фильтруем удаленные отчеты из session_state
            scout_reports = [r for r in scout_reports if str(r.get('id', '')) not in st.session_state.deleted_reports]
            
            # Разделяем на Enhanced и базовые отчеты (metadata может быть строкой JSON из БД)
            enhanced_reports = [
                r for r in scout_reports
                if _normalize_metadata(r.get('metadata')).get('source') in ('enhanced_scout_report', 'enhanced_scout_research')
            ]
            basic_reports = [
                r for r in scout_reports
                if _normalize_metadata(r.get('metadata')).get('source') == 'scout_research'
            ]
            
            # Функция удаления отчета
            def delete_scout_report(report_id):
                """Удаляет отчет разведки из базы данных"""
                try:
                    if report_id is None:
                        return False
                    
                    # Преобразуем ID в строку, если это UUID
                    report_id_str = str(report_id) if report_id else None
                    if not report_id_str:
                        return False
                    
                    # Убираем лишние пробелы и проверяем формат UUID
                    report_id_str = report_id_str.strip()
                    
                    # Проверяем, не был ли отчет уже удален в этой сессии
                    if report_id_str in st.session_state.deleted_reports:
                        return False  # Уже удален, не показываем ошибку
                    
                    conn = get_db_connection()
                    with conn.cursor() as cur:
                        # Используем параметризованный запрос для безопасности
                        # ID может быть UUID (строка) или int
                        # Пробуем удалить по UUID
                        cur.execute("DELETE FROM knowledge_nodes WHERE id::text = %s", (report_id_str,))
                        rows_deleted = cur.rowcount
                        conn.commit()
                    
                    if rows_deleted > 0:
                        # Добавляем в список удаленных для этой сессии
                        st.session_state.deleted_reports.add(report_id_str)
                        return True
                    else:
                        # Отчет не найден - возможно уже удален
                        st.session_state.deleted_reports.add(report_id_str)  # Помечаем как удаленный
                        return False
                except Exception as e:
                    st.error(f"❌ Ошибка удаления отчета: {e}")
                    st.code(traceback.format_exc())
                    return False
            
            # Показываем Enhanced отчеты отдельно (приоритет)
            if enhanced_reports:
                st.markdown("### 🚀 Enhanced Отчеты (Детальные)")
                for rep in enhanced_reports[:5]:  # Показываем топ-5 Enhanced
                    # Извлекаем ID и преобразуем в строку (может быть UUID объект)
                    rep_id_raw = rep.get('id')
                    rep_id = str(rep_id_raw) if rep_id_raw is not None else None
                    rep_date = rep.get('created_at', datetime.now())
                    if isinstance(rep_date, datetime):
                        date_str = rep_date.strftime('%d.%m.%Y %H:%M')
                    else:
                        date_str = str(rep_date)[:16]
                    
                    metadata = _normalize_metadata(rep.get('metadata'))
                    business = metadata.get('business_target', 'Не указано')
                    location = metadata.get('location', 'Не указано')
                    competitors_count = metadata.get('competitors_count', 0)
                    sources_count = metadata.get('sources_count', 0)
                    model_used = metadata.get('model_used', 'N/A')
                    is_full_report = metadata.get('source') == 'enhanced_scout_report'
                    
                    report_type = "📊 Полный отчет" if is_full_report else "🔍 Сбор данных"
                    
                    # Создаем уникальный ключ для кнопки удаления
                    delete_key = f"delete_enhanced_{rep_id}"
                    
                    with st.expander(f"{report_type} | {date_str} | 🏢 {business} | 📍 {location} | 👥 {competitors_count} конкурентов | 📚 {sources_count} источников"):
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.markdown(f"""
                            **Модель анализа:** {model_used}  
                            **Конкурентов найдено:** {competitors_count}  
                            **Источников собрано:** {sources_count}
                            """)
                        with col2:
                            if st.button("🗑️ Удалить", key=delete_key, type="secondary", use_container_width=True):
                                if delete_scout_report(rep_id):
                                    st.success("✅ Отчет удален")
                                    # Очищаем кэш для обновления данных
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    # Не показываем ошибку, если отчет уже был удален
                                    st.cache_data.clear()
                                    st.rerun()
                        
                        rep_content = rep.get('content', 'Нет содержимого')
                        st.markdown(rep_content)
            
            # Показываем базовые отчеты
            if basic_reports:
                st.markdown("### 📋 Базовые Отчеты")
                # Группируем по дате
                reports_by_date = {}
                for rep in basic_reports:
                    rep_date = rep.get('created_at', datetime.now())
                    if isinstance(rep_date, datetime):
                        date_key = rep_date.strftime('%d.%m.%Y')
                    else:
                        date_key = str(rep_date)[:10]
                    
                    if date_key not in reports_by_date:
                        reports_by_date[date_key] = []
                    reports_by_date[date_key].append(rep)
                
                for date_key in sorted(reports_by_date.keys(), reverse=True)[:3]:  # Показываем последние 3 дня
                    with st.expander(f"📅 {date_key} ({len(reports_by_date[date_key])} отчетов)"):
                        for rep in reports_by_date[date_key][:5]:  # Максимум 5 на дату
                            # Извлекаем ID и преобразуем в строку (может быть UUID объект)
                            rep_id_raw = rep.get('id')
                            rep_id = str(rep_id_raw) if rep_id_raw is not None else None
                            rep_date = rep.get('created_at', datetime.now())
                            if isinstance(rep_date, datetime):
                                rep_time = rep_date.strftime('%H:%M')
                            else:
                                rep_time = str(rep_date)[11:16]
                            
                            metadata = _normalize_metadata(rep.get('metadata'))
                            business = metadata.get('business_target', 'Не указано')
                            location = metadata.get('location', 'Не указано')
                            # Создаем уникальный ключ для кнопки удаления
                            delete_key = f"delete_basic_{rep_id}"
                            
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.markdown(f"**🕐 {rep_time} | 🏢 {business} | 📍 {location}**")
                            with col2:
                                if st.button("🗑️ Удалить", key=delete_key, type="secondary", use_container_width=True):
                                    if delete_scout_report(rep_id):
                                        st.success("✅ Отчет удален")
                                        # Очищаем кэш для обновления данных
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        # Не показываем ошибку, если отчет уже был удален
                                        st.cache_data.clear()
                                        st.rerun()
                            
                            rep_content = rep.get('content', 'Нет содержимого')
                            if len(rep_content) > 500:
                                st.markdown(rep_content[:500] + "...")
                                with st.expander("Показать полностью"):
                                    st.markdown(rep_content)
                            else:
                                st.markdown(rep_content)
                            st.markdown("---")
        else:
            st.info("📭 Пока нет отчетов разведки. Запустите разведку выше.")

    # 💎 ЛИКВИДНОСТЬ (ROI) - улучшенная версия
    with tabs[8]:
        st.subheader("📉 Ликвидность Знаний (ROI)")
        
        # Метрики ликвидности
        liquidity_stats = fetch_data("""
            SELECT 
                SUM(usage_count * confidence_score) as total_liquidity,
                AVG(usage_count * confidence_score) as avg_liquidity,
                MAX(usage_count * confidence_score) as max_liquidity,
                COUNT(*) FILTER (WHERE usage_count > 0) as active_nodes
            FROM knowledge_nodes
        """)
        
        if liquidity_stats and liquidity_stats[0]:
            ls = liquidity_stats[0]
            col_liq1, col_liq2, col_liq3, col_liq4 = st.columns(4)
            with col_liq1:
                st.metric("💰 Общая ликвидность", f"{ls['total_liquidity']:.1f}" if ls['total_liquidity'] else "0")
            with col_liq2:
                st.metric("📊 Средняя ликвидность", f"{ls['avg_liquidity']:.2f}" if ls['avg_liquidity'] else "0")
            with col_liq3:
                st.metric("🔥 Максимальная", f"{ls['max_liquidity']:.1f}" if ls['max_liquidity'] else "0")
            with col_liq4:
                st.metric("✅ Активных узлов", f"{ls['active_nodes']:,}" if ls['active_nodes'] else "0")
        
        st.markdown("---")
        
        # Топ ликвидных узлов
        roi_data = fetch_data("""
            SELECT 
                k.content, d.name as domain, k.usage_count, k.confidence_score,
                (k.usage_count * k.confidence_score) as liquidity_score,
                k.created_at
            FROM knowledge_nodes k 
            JOIN domains d ON k.domain_id = d.id
            WHERE k.usage_count > 0
            ORDER BY liquidity_score DESC, usage_count DESC 
            LIMIT 20
        """)
        
        if roi_data:
            # Визуализация распределения ликвидности
            df_roi = pd.DataFrame(roi_data)
            col_viz, col_list = st.columns([1, 1])
            
            with col_viz:
                st.markdown("### 📊 Распределение ликвидности")
                fig_roi = px.bar(
                    df_roi.head(10), x='domain', y='liquidity_score',
                    color='liquidity_score',
                    title="Топ-10 по ликвидности",
                    template="plotly_dark",
                    labels={'domain': 'Домен', 'liquidity_score': 'Ликвидность'},
                    color_continuous_scale='Viridis'
                )
                fig_roi.update_layout(xaxis_tickangle=-45, height=400)
                st.plotly_chart(fig_roi, use_container_width=True)
            
            with col_list:
                st.markdown("### 💎 Топ ликвидных узлов")
                for i, node in enumerate(roi_data[:10]):
                    max_score = roi_data[0].get('liquidity_score') or 1
                    liq_pct = min(100, ((node.get('liquidity_score') or 0) / max_score) * 100) if max_score > 0 else 0
                    liq_color = "#238636" if liq_pct > 80 else "#fab387" if liq_pct > 50 else "#8b949e"
                    node_content = (node.get('content') or '')[:200]
                    conf_score = node.get('confidence_score')
                    liq_score = node.get('liquidity_score')
                    conf_str = f"{conf_score:.2f}" if conf_score is not None else "N/A"
                    liq_str = f"{liq_score:.2f}" if liq_score is not None else "N/A"
                    st.markdown(f"""
                        <div class="premium-card" style="margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <span class="domain-badge">{node.get('domain', 'N/A')}</span>
                                <span class="usage-badge">#{i+1} | {node.get('usage_count', 0)} исп.</span>
                            </div>
                            <div class="card-text" style="font-size: 13px;">{node_content}{'...' if len(node.get('content') or '') > 200 else ''}</div>
                            <div style="margin-top: 12px;">
                                <div style="display: flex; justify-content: space-between; font-size: 11px; color: #8b949e; margin-bottom: 4px;">
                                    <span>Confidence: {conf_str}</span>
                                    <span>Ликвидность: {liq_str}</span>
                                </div>
                                <div class="liquidity-bar">
                                    <div class="liquidity-fill" style="width: {liq_pct}%; background: linear-gradient(90deg, {liq_color}, #58a6ff);"></div>
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

    # 🏛️ СТРУКТУРА (улучшенная версия)
    with tabs[9]:
        st.subheader("🏛️ Рейтинг Экспертов и Структура")
        
        # Переключатель: показывать топ-10 или всех
        show_all_experts = st.checkbox("📊 Показать всех экспертов (не только топ-10)", value=False, key="show_all_leaderboard")
        
        # Топ экспертов с улучшенной визуализацией
        query = """
            SELECT 
                e.name, e.department, 
                COUNT(k.id) as nodes_count, 
                SUM(k.usage_count) as total_usage,
                AVG(k.confidence_score) as avg_confidence,
                COUNT(t.id) as tasks_count,
                COUNT(t.id) FILTER (WHERE t.status = 'completed') as tasks_completed
            FROM experts e 
            LEFT JOIN knowledge_nodes k ON k.metadata->>'expert' = e.name
            LEFT JOIN tasks t ON t.assignee_expert_id = e.id
            GROUP BY e.id, e.name, e.department 
            ORDER BY total_usage DESC NULLS LAST, nodes_count DESC NULLS LAST
        """
        if not show_all_experts:
            query += " LIMIT 10"
        
        leaderboard = fetch_data(query)
        
        if leaderboard:
            # Визуализация топ-5
            top5 = leaderboard[:5]
            cols = st.columns(len(top5))
            for i, exp in enumerate(top5):
                with cols[i]:
                    medal = '🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else '⭐' if i==3 else '👤'
                    st.markdown(f"""
                        <div style="text-align: center; background: linear-gradient(145deg, #161b22, #0d1117); padding: 20px; border-radius: 12px; border: 2px solid {'#fbbf24' if i < 3 else '#30363d'}; transition: transform 0.2s;">
                            <div style="font-size: 32px; margin-bottom: 8px;">{medal}</div>
                            <div style="font-weight: 800; color: white; font-size: 16px; margin-bottom: 4px;">{exp['name']}</div>
                            <div style="font-size: 11px; color: #8b949e; margin-bottom: 8px;">{exp['department']}</div>
                            <div style="margin-top: 10px; color: #58a6ff; font-weight: 600; font-size: 14px;">{exp['total_usage'] or 0} исп.</div>
                            <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">{exp['nodes_count'] or 0} узлов</div>
                        </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Детальная таблица (топ-10 или всех, в зависимости от переключателя)
            st.markdown(f"### 📊 Детальная статистика экспертов {'(все)' if show_all_experts else '(топ-10)'}")
            df_leaderboard = pd.DataFrame(leaderboard)
            df_leaderboard['completion_rate'] = (df_leaderboard['tasks_completed'] / df_leaderboard['tasks_count'].replace(0, 1) * 100).round(1)
            df_leaderboard = df_leaderboard.fillna(0)
            df_leaderboard['completion_rate'] = df_leaderboard['completion_rate'].replace([float('inf'), float('-inf')], 0)
            
            st.dataframe(
                df_leaderboard[['name', 'department', 'nodes_count', 'total_usage', 'avg_confidence', 'tasks_count', 'tasks_completed', 'completion_rate']].rename(columns={
                    'name': 'Эксперт',
                    'department': 'Департамент',
                    'nodes_count': 'Узлов',
                    'total_usage': 'Использований',
                    'avg_confidence': 'Средний confidence',
                    'tasks_count': 'Задач',
                    'tasks_completed': 'Завершено',
                    'completion_rate': 'Процент завершения'
                }),
                hide_index=True,
                use_container_width=True
            )
        
        st.markdown("---")
        
        # Структура по департаментам с поиском
        st.markdown("### 🏢 Структура по департаментам")
        dept_search = st.text_input("🔍 Поиск департамента", placeholder="Введите название...", key="dept_search")
        
        experts = fetch_data("SELECT name, role, department, system_prompt, performance_score FROM experts ORDER BY department, name")
        if experts:
            df_experts = pd.DataFrame(experts)
            if dept_search:
                df_experts = df_experts[df_experts['department'].str.contains(dept_search, case=False, na=False)]
            
            for dept in df_experts['department'].unique():
                dept_experts = df_experts[df_experts['department'] == dept]
                with st.expander(f"📁 {dept} ({len(dept_experts)} экспертов)"):
                    for _, exp in dept_experts.iterrows():
                        perf_score = exp.get('performance_score', 0) or 0
                        perf_color = "#238636" if perf_score > 0.8 else "#fab387" if perf_score > 0.5 else "#8b949e"
                        st.markdown(f"""
                            <div class="premium-card">
                                <div style="display: flex; justify-content: space-between; align-items: start;">
                                    <div>
                                        <div class="expert-header">👤 {exp['name']}</div>
                                        <div class="expert-role">{exp['role']}</div>
                                    </div>
                                    <div style="color: {perf_color}; font-weight: 600;">⭐ {perf_score:.2f}</div>
                                </div>
                                <details style="margin-top: 12px;">
                                    <summary style="color: #8b949e; cursor: pointer;">📋 System Prompt</summary>
                                    <div class="card-text" style="background: #0d1117; padding: 16px; border-radius: 8px; font-family: monospace; font-size: 12px; margin-top: 8px;">{exp['system_prompt']}</div>
                                </details>
                            </div>
                        """, unsafe_allow_html=True)

    # 🎯 СТРАТЕГИЯ OKR
    with tabs[10]:
        try:
            # Определяем актуальный период OKR из БД
            okr_period_data = fetch_data("SELECT o.period FROM okrs o ORDER BY o.created_at DESC LIMIT 1")
            okr_period = "2026-Q1"
            if okr_period_data and len(okr_period_data) > 0:
                try:
                    first_row = okr_period_data[0]
                    if first_row and isinstance(first_row, dict) and first_row.get('period'):
                        okr_period = first_row['period'] or "2026-Q1"
                except (IndexError, KeyError, TypeError):
                    pass
            st.subheader(f"🎯 Стратегия OKR {okr_period}")
            run_query("""
                UPDATE key_results 
                SET current_value = (SELECT count(*) FROM knowledge_nodes)
                WHERE description ILIKE '%Объем базы знаний%' OR description ILIKE '%узлов%'
            """)
            run_query("""
                UPDATE key_results 
                SET current_value = (SELECT COALESCE(sum(usage_count), 0) FROM knowledge_nodes)
                WHERE description ILIKE '%Использование%' OR description ILIKE '%ROI%'
            """)
            okr_data = fetch_data("SELECT o.objective, kr.description, kr.current_value, kr.target_value, kr.unit FROM okrs o JOIN key_results kr ON o.id = kr.okr_id ORDER BY o.objective")
            if okr_data and len(okr_data) > 0:
                df_okr = pd.DataFrame(okr_data)
                for obj in df_okr['objective'].unique():
                    st.markdown(f"### 🚀 {obj}")
                    for _, kr in df_okr[df_okr['objective'] == obj].iterrows():
                        try:
                            current_val_raw = kr.get('current_value')
                            target_val_raw = kr.get('target_value')
                            try:
                                current_val = float(current_val_raw) if current_val_raw is not None else 0.0
                            except (ValueError, TypeError):
                                current_val = 0.0
                            try:
                                target_val = float(target_val_raw) if target_val_raw is not None else 0.0
                            except (ValueError, TypeError):
                                target_val = 0.0
                            progress = (current_val / target_val) if target_val != 0 else 0.0
                            progress = min(max(progress, 0.0), 1.0)
                            unit = str(kr.get('unit') or '')
                            desc = str(kr.get('description') or 'N/A')
                            st.write(f"**{desc}** ({current_val:.1f}/{target_val:.1f} {unit})")
                            st.progress(progress)
                        except Exception as e:
                            st.warning(f"⚠️ Ошибка отображения метрики: {e}")
            else:
                st.info("Данные OKR пока отсутствуют")
        except Exception as okr_err:
            st.error(f"Ошибка раздела OKR: {okr_err}")
            st.info("Проверьте наличие таблиц okrs и key_results в БД. При необходимости выполните миграции.")

    # 🎓 АКАДЕМИЯ ИИ
    with tabs[11]:
        st.subheader("🎓 Академия ИИ и Дебаты")
        st.caption("Логи обучения и дебаты заполняются при запуске Nightly Learner (knowledge_os/app/nightly_learner.py). Он не стартует автоматически с docker-compose — запустите вручную или по cron. Подробнее: docs/LEARNING_HYPOTHESES_DEBATES_STATUS.md")
        col_logs, col_debates = st.columns([2, 1])
        with col_logs:
            logs = fetch_data("SELECT e.name, l.topic, l.summary, l.learned_at FROM expert_learning_logs l JOIN experts e ON l.expert_id = e.id ORDER BY l.learned_at DESC LIMIT 10")
            if logs:
                for log in logs:
                    with st.chat_message("assistant"):
                        st.write(f"**{log.get('name', 'Unknown')}**: {log.get('topic', 'N/A')}")
                        if log.get('summary'):
                            st.info(log['summary'])
            else:
                st.info("Пока нет записей об обучении")
        with col_debates:
            debates = fetch_data("SELECT topic, consensus_summary FROM expert_discussions ORDER BY created_at DESC LIMIT 5")
            if debates:
                for d in debates:
                    with st.expander(f"🗣️ {d.get('topic', 'Без темы')}"):
                        st.markdown(d.get('consensus_summary', 'Нет консенсуса'))
            else:
                st.info("Пока нет дебатов")

    # 🛠️ ЗАДАЧИ (улучшенная версия)
    with tabs[12]:
        st.subheader("🛠️ Автономные Задачи и Оркестрация")
        
        # Статистика задач вверху (короткий кэш 15 сек — новые задачи видны без ручного обновления)
        task_overview = fetch_data_tasks("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                CASE 
                    WHEN COUNT(*) FILTER (WHERE updated_at IS NOT NULL AND created_at IS NOT NULL) > 0 
                    THEN ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) FILTER (WHERE updated_at IS NOT NULL AND created_at IS NOT NULL) / 3600, 1)
                    ELSE 0
                END as avg_hours
            FROM tasks
        """)
        
        st.caption("Данные обновляются каждые 15 сек. Кнопка «Обновить» — принудительно сейчас.")
        if task_overview and task_overview[0]:
            to = task_overview[0]
            if to['total'] == 0:
                st.info("Задач пока нет. Они появляются при: создании задачи через вкладки «Аудит Кода», «Разведка», «Маркетинг»; делегировании Victoria; работе worker. Убедитесь, что дашборд и агенты используют одну БД (DATABASE_URL).")
            col_stat1, col_stat2, col_stat3, col_stat4, col_stat5 = st.columns(5)
            with col_stat1:
                st.metric("Всего", f"{to['total']:,}")
            with col_stat2:
                completion_rate = (to['completed'] / to['total'] * 100) if to['total'] > 0 else 0.0
                st.metric("✅ Завершено", f"{to['completed']:,}", f"{completion_rate:.1f}%")
            with col_stat3:
                st.metric("🔄 В работе", f"{to['in_progress']:,}")
            with col_stat4:
                st.metric("⏳ Ожидает", f"{to['pending']:,}")
            with col_stat5:
                st.metric("⏱️ Среднее время", f"{to['avg_hours']:.1f}ч" if to['avg_hours'] else "N/A")
        else:
            st.warning("Не удалось загрузить статистику задач. Проверьте подключение к БД (DATABASE_URL).")
        
        st.markdown("---")
        
        # Фильтры и управление (улучшенные)
        col_filter1, col_filter2, col_action = st.columns([2, 2, 1])
        with col_filter1:
            status_filter = st.selectbox("Фильтр по статусу", ["Все", "pending", "in_progress", "completed", "cancelled", "failed"], key="task_status_filter")
        with col_filter2:
            experts_list = fetch_data_tasks("SELECT DISTINCT name FROM experts ORDER BY name")
            expert_names = [e['name'] for e in experts_list] if experts_list else []
            expert_filter = st.selectbox("Фильтр по эксперту", ["Все"] + expert_names, key="task_expert_filter")
        with col_action:
            if st.button("🔄 Обновить", key="refresh_tasks", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        
        # Кнопка очистки старых завершенных задач
        if st.button("🗑️ Очистить старые завершенные задачи (>30 дней)", key="cleanup_old_tasks"):
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            DELETE FROM tasks 
                            WHERE status = 'completed' 
                            AND updated_at < NOW() - INTERVAL '30 days'
                        """)
                        deleted = cur.rowcount
                        conn.commit()
                st.success(f"✅ Удалено {deleted} старых задач")
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка очистки: {e}")
        
        # Запрос задач с фильтрами (улучшенный, с защитой от SQL injection)
        status_condition = ""
        status_param = None
        if status_filter != "Все":
            status_condition = "AND t.status = %s"
            status_param = status_filter
        
        expert_condition = ""
        expert_param = None
        if expert_filter != "Все":
            expert_condition = "AND COALESCE(e.name, 'Не назначен') = %s"
            expert_param = expert_filter
        
        # Поиск по задачам (с защитой от SQL injection)
        search_query = st.text_input("🔍 Поиск по задачам", placeholder="Введите ключевые слова...", key="task_search")
        search_condition = ""
        search_params = []
        if search_query:
            # Используем параметризованный запрос для безопасности
            search_condition = "AND (t.title ILIKE %s OR t.description ILIKE %s)"
            search_pattern = f"%{search_query}%"
            search_params = [search_pattern, search_pattern]
        
        # Безопасный запрос с LEFT JOIN на случай отсутствия assignee
        # Используем параметризованные запросы для безопасности
        query_parts = ["SELECT t.id, t.title, t.description, t.status, t.result, t.created_at, t.updated_at, COALESCE(e.name, 'Не назначен') as assignee, COALESCE(e.department, 'N/A') as department FROM tasks t LEFT JOIN experts e ON t.assignee_expert_id = e.id WHERE 1=1"]
        query_params = []
        
        if status_condition and status_param:
            query_parts.append(status_condition)
            query_params.append(status_param)
        if expert_condition and expert_param:
            query_parts.append(expert_condition)
            query_params.append(expert_param)
        if search_condition and search_params:
            query_parts.append(search_condition)
            query_params.extend(search_params)
        
        query_parts.append("ORDER BY t.created_at DESC LIMIT 100")
        tasks_query = " ".join(query_parts)
        
        tasks = fetch_data_tasks(tasks_query, tuple(query_params) if query_params else None)
        
        if tasks:
            # Статистика найденных задач
            st.caption(f"📊 Найдено задач: {len(tasks)}")
            
            # Группировка по статусам для визуализации
            if len(tasks) > 0:
                df_tasks = pd.DataFrame(tasks)
                status_counts = df_tasks['status'].value_counts()
                
                # Мини-график распределения статусов
                col_chart, col_list = st.columns([1, 2])
                with col_chart:
                    fig_status = px.pie(
                        values=status_counts.values,
                        names=status_counts.index,
                        title="Распределение по статусам",
                        template="plotly_dark",
                        color_discrete_map={
                            'completed': '#238636',
                            'in_progress': '#fab387',
                            'pending': '#f38ba8',
                            'failed': '#da3633'
                        }
                    )
                    st.plotly_chart(fig_status, use_container_width=True)
            
            # Список задач с улучшенным дизайном
            for task in tasks:
                status_color = {
                    'pending': '#f38ba8',
                    'completed': '#238636',
                    'in_progress': '#fab387',
                    'failed': '#da3633',
                    'cancelled': '#8b949e'
                }.get(task['status'], '#8b949e')
                
                status_icon = {
                    'pending': '⏳',
                    'completed': '✅',
                    'in_progress': '🔄',
                    'failed': '❌',
                    'cancelled': '🚫'
                }.get(task['status'], '❓')
                
                created_date = task['created_at'].strftime('%d.%m.%Y %H:%M') if task.get('created_at') else 'N/A'
                updated_date = task['updated_at'].strftime('%d.%m.%Y %H:%M') if task.get('updated_at') else 'N/A'
                
                # Определяем, старая ли задача (более 7 дней без обновления)
                is_old = False
                if task.get('updated_at'):
                    if isinstance(task['updated_at'], datetime):
                        now = datetime.now(timezone.utc)
                        updated = task['updated_at']
                        if updated.tzinfo is None:
                            updated = updated.replace(tzinfo=timezone.utc)
                        if now.tzinfo is None:
                            now = now.replace(tzinfo=timezone.utc)
                        if now - updated > timedelta(days=7):
                            is_old = True
                
                old_badge = " ⚠️ СТАРАЯ" if is_old else ""
                department = task.get('department', 'N/A')
                
                st.markdown(f"""
                    <div style="background: linear-gradient(145deg, #11111b, #0d1117); border: 1px solid {status_color}; padding: 18px; border-radius: 12px; margin-bottom: 12px; transition: all 0.3s; {'opacity: 0.7;' if is_old else ''}">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                            <div style="flex: 1;">
                                <div style="font-weight: 800; color: #cdd6f4; font-size: 16px; margin-bottom: 6px;">{status_icon} {task['title']}</div>
                                <div style="font-size: 12px; color: #8b949e;">
                                    👤 {task['assignee']} | 📁 {department} | 📅 {created_date}
                                </div>
                            </div>
                            <span style="color: {status_color}; font-weight: 800; font-size: 12px; padding: 4px 12px; background: rgba(88, 166, 255, 0.1); border-radius: 12px;">{task['status'].upper()}{old_badge}</span>
                        </div>
                        <div style="font-size: 14px; color: #c9d1d9; margin-top: 10px; line-height: 1.6;">{(task.get('description') or '')[:300]}{'...' if len(task.get('description') or '') > 300 else ''}</div>
                        <div style="font-size: 11px; color: #6e7681; margin-top: 8px;">Обновлено: {updated_date}</div>
                    </div>
                """, unsafe_allow_html=True)
                if task.get('result'):
                    with st.expander("✅ Отчет эксперта (полный текст)", expanded=(len((task.get('result') or '')) < 2000)):
                        st.markdown(task.get('result') or '')
        else: 
            st.info("Активных автономных задач пока нет.")

    # 📊 АНАЛИТИКА (улучшенная)
    with tabs[13]:
        st.subheader("📈 Расширенная Аналитика")
        
        # Период анализа
        period = st.selectbox("Период анализа", ["7 дней", "30 дней", "90 дней", "Все время"], key="analytics_period")
        days_map = {"7 дней": 7, "30 дней": 30, "90 дней": 90, "Все время": None}
        days = days_map[period]
        date_filter = f"WHERE created_at > NOW() - INTERVAL '{days} days'" if days else ""
        
        # Метрики вверху
        col_met1, col_met2, col_met3, col_met4 = st.columns(4)
        
        # Рост узлов знаний
        growth_data = fetch_data(f"""
            SELECT created_at::date as date, count(*) as count 
            FROM knowledge_nodes 
            {date_filter}
            GROUP BY 1 ORDER BY 1
        """)
        
        if growth_data:
            df_growth = pd.DataFrame(growth_data)
            total_growth = df_growth['count'].sum() if not df_growth.empty else 0
            with col_met1:
                st.metric("Всего узлов", f"{total_growth:,}")
            
            # График роста
            if not df_growth.empty:
                fig_growth = px.line(
                    df_growth, x='date', y='count', 
                    title="📈 Рост базы знаний",
                    template="plotly_dark",
                    labels={'date': 'Дата', 'count': 'Количество узлов'},
                    line_shape='spline'
                )
                fig_growth.update_traces(line_color='#58a6ff', line_width=3)
                st.plotly_chart(fig_growth, use_container_width=True)
        
        # Распределение по доменам
        col_dist1, col_dist2 = st.columns(2)
        with col_dist1:
            dist_filter = f"WHERE k.created_at > NOW() - INTERVAL '{days} days'" if days else ""
            dist_data = fetch_data(f"""
                SELECT d.name, count(*) as count 
                FROM knowledge_nodes k 
                JOIN domains d ON k.domain_id = d.id 
                {dist_filter}
                GROUP BY 1 
                ORDER BY 2 DESC 
                LIMIT 15
            """)
            if dist_data:
                df_dist = pd.DataFrame(dist_data)
                fig_pie = px.pie(
                    df_dist, names='name', values='count', 
                    hole=0.4, 
                    title="🎯 Распределение по доменам",
                    template="plotly_dark"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        
        with col_dist2:
            # Топ доменов по использованию
            usage_filter = f"WHERE k.created_at > NOW() - INTERVAL '{days} days'" if days else ""
            usage_data = fetch_data(f"""
                SELECT d.name, SUM(k.usage_count) as total_usage, AVG(k.confidence_score) as avg_confidence
                FROM domains d 
                LEFT JOIN knowledge_nodes k ON d.id = k.domain_id
                {usage_filter}
                GROUP BY d.id, d.name
                HAVING SUM(k.usage_count) > 0
                ORDER BY total_usage DESC
                LIMIT 10
            """)
            if usage_data:
                df_usage = pd.DataFrame(usage_data)
                fig_bar = px.bar(
                    df_usage, x='name', y='total_usage',
                    title="🔥 Топ доменов по использованию",
                    template="plotly_dark",
                    labels={'name': 'Домен', 'total_usage': 'Использований'},
                    color='total_usage',
                    color_continuous_scale='Viridis'
                )
                fig_bar.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_bar, use_container_width=True)
        
        # Динамика задач
        st.markdown("### 📊 Динамика задач")
        task_trends = fetch_data_tasks(f"""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as created,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress
            FROM tasks
            {date_filter}
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 30
        """)
        if task_trends:
            df_tasks = pd.DataFrame(task_trends)
            fig_tasks = go.Figure()
            fig_tasks.add_trace(go.Scatter(x=df_tasks['date'], y=df_tasks['created'], name='Создано', line=dict(color='#58a6ff', width=2)))
            fig_tasks.add_trace(go.Scatter(x=df_tasks['date'], y=df_tasks['completed'], name='Завершено', line=dict(color='#238636', width=2)))
            fig_tasks.add_trace(go.Scatter(x=df_tasks['date'], y=df_tasks['in_progress'], name='В работе', line=dict(color='#fab387', width=2)))
            fig_tasks.update_layout(
                title="📈 Динамика задач",
                template="plotly_dark",
                xaxis_title="Дата",
                yaxis_title="Количество",
                hovermode='x unified'
            )
            st.plotly_chart(fig_tasks, use_container_width=True)

    # 🕸️ КАРТА РАЗУМА
    with tabs[14]:
        st.subheader("🕸️ Карта Разума")
        db_nodes = fetch_data("SELECT k.id, k.content, d.name as domain FROM knowledge_nodes k JOIN domains d ON k.domain_id = d.id LIMIT 100")
        if db_nodes and len(db_nodes) > 0:
            G = nx.Graph()
            for n in db_nodes:
                node_id = n.get('id')
                node_domain = n.get('domain', 'Unknown')
                node_content = n.get('content', '')
                if node_id and node_domain:
                    G.add_node(node_domain, type='domain')
                    G.add_node(str(node_id), text=node_content[:50] if node_content else '', type='node')
                    G.add_edge(str(node_id), node_domain)
            
            try:
                pos = nx.spring_layout(G, k=1, iterations=50)
            except Exception:
                # Fallback если граф пустой или ошибка
                pos = {n: (0, 0) for n in G.nodes()}
            
            node_x = [pos.get(n, (0, 0))[0] for n in G.nodes()]
            node_y = [pos.get(n, (0, 0))[1] for n in G.nodes()]
            node_text = []
            node_size = []
            node_color = []
            
            for n in G.nodes():
                node_type = G.nodes[n].get('type', 'node')
                if node_type == 'domain':
                    node_text.append(f"<b>{n}</b>")
                    node_size.append(20)
                    node_color.append('#ff7f0e') # Orange for domains
                else:
                    node_text.append(G.nodes[n].get('text', ''))
                    node_size.append(10)
                    node_color.append('#58a6ff') # Blue for nodes

            node_trace = go.Scatter(
                x=node_x, 
                y=node_y, 
                mode='markers+text',
                text=[t if '<b>' in t else '' for t in node_text], # Only show labels for domains to avoid clutter
                textposition="top center",
                hovertext=node_text,
                hoverinfo='text',
                hovertemplate='%{hovertext}<extra></extra>',
                marker=dict(
                    size=node_size,
                    color=node_color,
                    line=dict(width=1, color='white')
                )
            )
            
            # Добавляем линии связей
            edge_x = []
            edge_y = []
            for edge in G.edges():
                try:
                    x0, y0 = pos.get(edge[0], (0, 0))
                    x1, y1 = pos.get(edge[1], (0, 0))
                    edge_x.extend([x0, x1, None])
                    edge_y.extend([y0, y1, None])
                except (KeyError, IndexError):
                    continue
                
            edge_trace = go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=0.5, color='#888'),
                hoverinfo='none',
                mode='lines'
            )

            if len(G.nodes()) > 0:
                fig = go.Figure(data=[edge_trace, node_trace],
                             layout=go.Layout(
                                title='Визуализация связей базы знаний',
                                template="plotly_dark",
                                showlegend=False,
                                hovermode='closest',
                                margin=dict(b=20,l=5,r=5,t=40),
                                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                height=600
                            ))
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Недостаточно данных для построения графа")
        else:
            st.info("Нет узлов для визуализации")

    # ⚖️ РЕВИЗИЯ
    with tabs[15]:
        st.subheader("⚖️ Ревизия")
        
        # Статистика необработанных узлов
        stats = fetch_data("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT d.name) as domains_count
            FROM knowledge_nodes k 
            JOIN domains d ON k.domain_id = d.id 
            WHERE k.is_verified = FALSE
        """)
        
        if stats and len(stats) > 0:
            total_unverified = stats[0]['total']
            domains_count = stats[0]['domains_count']
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Необработанных узлов", total_unverified)
            col2.metric("Доменов", domains_count)
            
            # Кнопка массовой обработки
            if total_unverified > 0:
                if st.button("🚀 Запустить автоматическую обработку (50 узлов)", type="primary"):
                    try:
                        eval_path = "/app/knowledge_os/app/evaluator.py"
                        if not os.path.isfile(eval_path):
                            eval_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "evaluator.py")
                        result = subprocess.run(
                            ["python3", eval_path, "50"],
                            capture_output=True,
                            text=True,
                            timeout=600,
                            cwd=os.path.dirname(os.path.dirname(__file__)) if not eval_path.startswith("/app") else "/app"
                        )
                        if result.returncode == 0:
                            st.success("✅ Обработка запущена. Проверьте логи для деталей.")
                        else:
                            st.warning(f"⚠️ Обработка завершилась с ошибками: {(result.stderr or 'неизвестно')[:500]}")
                        st.rerun()
                    except FileNotFoundError:
                        st.warning("Скрипт evaluator не найден. Запустите обработку вручную из контейнера worker.")
                    except subprocess.TimeoutExpired:
                        st.warning("Обработка заняла более 10 минут и была прервана.")
                    except Exception as e:
                        st.error(f"❌ Ошибка запуска evaluator: {e}")
        
        # Фильтрация по доменам
        domains = fetch_data("""
            SELECT DISTINCT d.name as domain 
            FROM knowledge_nodes k 
            JOIN domains d ON k.domain_id = d.id 
            WHERE k.is_verified = FALSE
            ORDER BY d.name
        """)
        domains = domains if domains else []
        domain_names = [d['domain'] for d in domains if d.get('domain')]
        
        selected_domain = st.selectbox(
            "Фильтр по домену:",
            ["Все домены"] + domain_names,
            key="reviziya_domain_filter"
        )
        
        # Пагинация
        page_size = st.slider("Узлов на странице:", 10, 100, 20, key="reviziya_page_size")
        page_num = st.number_input("Страница:", min_value=1, value=1, key="reviziya_page")
        offset = (page_num - 1) * page_size
        
        # Запрос с фильтрацией и пагинацией
        domain_filter = ""
        params = [page_size, offset]
        if selected_domain != "Все домены":
            domain_filter = " AND d.name = %s"
            params = [selected_domain, page_size, offset]
        
        query = f"""
            SELECT k.id, k.content, d.name as domain, k.created_at
            FROM knowledge_nodes k 
            JOIN domains d ON k.domain_id = d.id 
            WHERE k.is_verified = FALSE{domain_filter}
            ORDER BY k.created_at ASC
            LIMIT %s OFFSET %s
        """
        
        review_nodes = fetch_data(query, tuple(params))
        
        if not review_nodes:
            st.info("✅ Нет необработанных узлов!")
        else:
            st.write(f"**Показано {len(review_nodes)} из {total_unverified} узлов**")
            
            # Массовое одобрение (с проверкой на пустой список; id может быть UUID)
            if st.button("✅ Одобрить все показанные узлы", type="secondary"):
                if review_nodes:
                    ids = [node['id'] for node in review_nodes if node.get('id') is not None]
                    if ids:
                        id_strs = [str(i) for i in ids]
                        placeholders = ','.join(['%s'] * len(id_strs))
                        if run_query(f"UPDATE knowledge_nodes SET is_verified = TRUE WHERE id::text IN ({placeholders})", tuple(id_strs)):
                            st.success(f"✅ Одобрено {len(ids)} узлов!")
                            st.rerun()
                    else:
                        st.warning("Нет узлов для одобрения")
                else:
                    st.warning("Нет узлов для одобрения")
            
            # Список узлов
            for node in review_nodes:
                node_id = node.get('id')
                node_domain = node.get('domain', 'N/A')
                node_date = node.get('created_at', 'N/A')
                if isinstance(node_date, datetime):
                    node_date = node_date.strftime('%Y-%m-%d %H:%M')
                
                with st.expander(f"📌 {node_domain} | ID: {node_id} | {node_date}"):
                    st.write(node.get('content', 'Нет содержимого'))
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if st.button("✅ Одобрить", key=f"v_{node_id}"):
                            # id может быть UUID — передаём как есть; psycopg2 адаптирует
                            id_param = str(node_id) if node_id is not None and not isinstance(node_id, (str, int)) else node_id
                            if run_query("UPDATE knowledge_nodes SET is_verified = TRUE WHERE id::text = %s", (str(id_param),)):
                                st.success("✅ Узел одобрен!")
                                st.rerun()
    
    # 📊 SLA МОНИТОРИНГ
    try:
        with tabs[16]:
            st.subheader("📊 SLA Мониторинг")
            try:
                # Исправляем путь импорта - используем абсолютный путь
                app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../app'))
                if app_dir not in sys.path:
                    sys.path.insert(0, app_dir)
                # Альтернативный путь для контейнера
                fallback_path = '/app/knowledge_os/app'
                if fallback_path not in sys.path:
                    sys.path.insert(0, fallback_path)
                
                from sla_monitor import get_sla_monitor
                sla_monitor = get_sla_monitor()
                
                # Запускаем async функцию в синхронном контексте
                # Используем глобальный asyncio, импортированный в начале файла
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    compliance = loop.run_until_complete(sla_monitor.check_sla_compliance())
                    loop.close()
                except RuntimeError:
                    # Если уже есть event loop, используем его
                    compliance = asyncio.run(sla_monitor.check_sla_compliance())
                
                if compliance:
                    for metric_name, metric_data in compliance.items():
                        value = metric_data.get('value', 0)
                        target = metric_data.get('target', 0)
                        compliant = metric_data.get('compliant', False)
                        
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.text(metric_name.replace('_', ' ').title())
                        with col2:
                            st.metric("Значение", f"{value:.3f}", f"Цель: {target:.3f}")
                        with col3:
                            status = "✅" if compliant else "❌"
                            st.markdown(f"### {status}")
                    # Пояснение: когда все четыре зелёные — SLA в норме
                    non_compliant = [k for k, v in compliance.items() if not v.get('compliant', True)]
                    if non_compliant and any(m in non_compliant for m in ('cache_hit_rate', 'token_savings')):
                        st.caption("💡 Cache Hit Rate и Token Savings считаются из таблицы semantic_ai_cache. Они станут ненулевыми, когда кэш ответов и запись tokens_saved (ai_core, semantic_cache) будут использоваться.")
                else:
                    st.info("Метрики SLA пока недоступны")
            except Exception as e:
                st.error(f"Ошибка загрузки SLA метрик: {e}")
    except IndexError:
        pass
    
    # 🛡️ БЕЗОПАСНОСТЬ
    try:
        with tabs[17]:
            st.subheader("🛡️ Threat Detection")
            try:
                # Исправлено: используем anomaly_detection_logs (где логируются угрозы)
                threats = fetch_data("""
                    SELECT 
                        anomaly_type as threat_type,
                        severity,
                        description as detected_in,
                        detected_at as timestamp,
                        FALSE as resolved
                    FROM anomaly_detection_logs
                    WHERE anomaly_type IN ('data_leak', 'prompt_injection', 'model_poisoning', 'resource_exhaustion')
                    ORDER BY detected_at DESC
                    LIMIT 20
                """)
                
                if threats:
                    for threat in threats:
                        severity_color = {
                            'critical': '#f38ba8',
                            'high': '#fab387',
                            'medium': '#f9e2af',
                            'low': '#a6e3a1'
                        }.get(threat['severity'], '#cdd6f4')
                        
                        resolved = "✅" if threat.get('resolved') else "❌"
                        st.markdown(f"""
                            <div style="background: #161b22; border-left: 5px solid {severity_color}; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                                <span style="float: right; color: #8b949e; font-size: 12px;">{resolved}</span>
                                <div style="color: {severity_color}; font-weight: 800; font-size: 14px;">{threat['threat_type']} - {threat['severity']}</div>
                                <div style="color: #c9d1d9; margin-top: 5px;">Обнаружено в: {threat.get('detected_in', 'unknown')}</div>
                            </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("Угроз не обнаружено")
            except Exception as e:
                st.error(f"Ошибка загрузки угроз: {e}")
    except IndexError:
        pass
    
    # ⚡ ЭНЕРГИЯ
    try:
        with tabs[18]:
            st.subheader("⚡ Energy Management")
            try:
                # Исправляем путь импорта - используем абсолютный путь
                app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../app'))
                if app_dir not in sys.path:
                    sys.path.insert(0, app_dir)
                # Альтернативный путь: прямое добавление /app/knowledge_os/app
                fallback_path = '/app/knowledge_os/app'
                if fallback_path not in sys.path:
                    sys.path.insert(0, fallback_path)
                
                from energy_manager import get_energy_manager
                energy_manager = get_energy_manager()
                
                col1, col2 = st.columns(2)
                with col1:
                    battery_status = "🔋 От батареи" if energy_manager.is_battery_powered else "🔌 От сети"
                    st.metric("Источник питания", battery_status)
                with col2:
                    efficient_mode = "✅ Да" if energy_manager.should_use_efficient_model() else "❌ Нет"
                    st.metric("Энергоэффективный режим", efficient_mode)
            except Exception as e:
                st.error(f"Ошибка загрузки energy manager: {e}")
    except IndexError:
        pass
    
    # 🚀 SINGULARITY 9.0 МЕТРИКИ
    try:
        with tabs[19]:
            st.subheader("🚀 Singularity 9.0 Метрики")
            
            try:
                # Дашборд корпорации: ищем модули только в папке корпорации (knowledge_os/app).
                app_dir = CORPORATION_APP_DIR
                if not os.path.isdir(app_dir):
                    st.warning(f"⚠️ Папка корпорации не найдена: {app_dir}")
                    st.info("📊 Метрики Singularity 9.0 недоступны. Проверьте, что дашборд запущен из репозитория с knowledge_os/app.")
                    return
                required_files = ("singularity_9_ab_tester.py",)  # evaluator.py опционален — модуль загрузится с get_pool=None
                missing = [f for f in required_files if not os.path.isfile(os.path.join(app_dir, f))]
                if missing:
                    st.warning(f"⚠️ В папке корпорации не найден: {', '.join(missing)} (каталог: {app_dir})")
                    st.info("📊 Метрики Singularity 9.0 недоступны. Добавьте knowledge_os/app в путь дашборда.")
                    return
                if app_dir not in sys.path:
                    sys.path.insert(0, app_dir)
                else:
                    sys.path.remove(app_dir)
                    sys.path.insert(0, app_dir)
                tester = None
                try:
                    from singularity_9_ab_tester import Singularity9ABTester
                    tester = Singularity9ABTester()
                    _dashboard_log.info("singularity_9_ab_tester loaded CORPORATION_APP_DIR=%s", app_dir)
                except ImportError as e:
                    err_msg = str(e)
                    _dashboard_log.warning("Singularity 9.0 import failed CORPORATION_APP_DIR=%s: %s", app_dir, e, exc_info=True)
                    if "evaluator" in err_msg.lower():
                        st.warning("⚠️ Модуль evaluator недоступен — метрики Singularity 9.0 будут пустыми. Запустите дашборд из каталога с knowledge_os/app или смонтируйте app в контейнер.")
                    else:
                        st.warning(f"⚠️ Модуль singularity_9_ab_tester недоступен: {e}")
                    st.caption(f"Каталог поиска: {app_dir}")
                    tester = None
                except Exception as e:
                    _dashboard_log.warning("Singularity 9.0 load exception CORPORATION_APP_DIR=%s: %s", app_dir, e, exc_info=True)
                    st.error(f"❌ Ошибка при загрузке модуля: {e}")
                    st.caption(f"Каталог: {app_dir}")
                    tester = None
                
                if tester is None:
                    st.info("📊 Метрики Singularity 9.0 временно недоступны. Модуль не загружен.")
                    return
                
                # Собираем метрики для всех гипотез
                results = {}
                error_message = None
                
                if tester is None:
                    return
                
                with st.spinner("Сбор метрик..."):
                    try:
                        # Пробуем создать новый event loop
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            results = loop.run_until_complete(tester.validate_metrics())
                            loop.close()
                        except RuntimeError as e:
                            # Если уже есть event loop, используем asyncio.run
                            try:
                                results = asyncio.run(tester.validate_metrics())
                            except RuntimeError:
                                # Если event loop уже запущен, создаем новый в отдельном потоке
                                import concurrent.futures
                                with concurrent.futures.ThreadPoolExecutor() as executor:
                                    future = executor.submit(asyncio.run, tester.validate_metrics())
                                    results = future.result(timeout=30)
                    except ImportError as e:
                        error_message = f"Модуль не найден: {e}"
                    except Exception as e:
                        error_message = f"Ошибка сбора метрик: {str(e)}"
                        st.code(traceback.format_exc())
                
                # Отображаем метрики для каждой гипотезы
                hypotheses = [
                    ("tacit_knowledge", "🎨 Tacit Knowledge Extractor", "style_similarity_score", 0.85, "Требуются данные с style_similarity в interaction_logs"),
                    ("emotion_modulation", "😊 Emotional Response Modulation", "satisfaction_delta", 0.15, "Требуются данные с satisfaction_delta в interaction_logs"),
                    ("code_smell_predictor", "🐛 Code-Smell Predictor", "precision", 0.70, "Требуются данные в code_smell_predictions"),
                    ("predictive_compression", "⚡ Predictive Compression", "latency_reduction", 0.30, "Требуются данные с latency_reduction в interaction_logs")
                ]
                
                if error_message:
                    st.error(f"❌ {error_message}")
                
                if not results:
                    st.warning("⚠️ Метрики не собраны. Возможные причины:")
                    st.info("""
                    - Модуль **evaluator** недоступен (No module named 'evaluator') — запустите дашборд из каталога с knowledge_os/app или смонтируйте app в контейнер.
                    - Данные для A/B тестирования еще не собраны
                    - Компоненты Singularity 9.0 еще не активированы
                    - Недостаточно данных в БД для расчета метрик
                    
                    **Для активации метрик:**
                    1. Убедитесь, что в PYTHONPATH/sys.path есть knowledge_os/app (с evaluator.py и asyncpg)
                    2. Убедитесь, что компоненты Singularity 9.0 включены
                    3. Дождитесь накопления данных; проверьте таблицы: interaction_logs, code_smell_predictions
                    """)
                
                for hypothesis_key, hypothesis_name, metric_name, target_value, description in hypotheses:
                    if hypothesis_key in results:
                        result = results[hypothesis_key]
                        achieved = result.get("achieved", False)
                        metric_value = result.get("metric_value", 0.0)
                        sample_size = result.get("sample_size", 0)
                        
                        status = "✅" if achieved else "⚠️"
                        color = "#238636" if achieved else "#fab387"
                        
                        st.markdown(f"""
                            <div style="background: #0d1117; padding: 16px; border-radius: 8px; border-left: 4px solid {color}; margin-bottom: 16px;">
                                <div style="font-size: 18px; font-weight: 600; color: #c9d1d9; margin-bottom: 8px;">
                                    {status} {hypothesis_name}
                                </div>
                                <div style="font-size: 14px; color: #8b949e; margin-bottom: 4px;">
                                    Метрика: {metric_name}
                                </div>
                                <div style="font-size: 24px; font-weight: 800; color: {color}; margin-bottom: 4px;">
                                    {metric_value:.2%}
                                </div>
                                <div style="font-size: 12px; color: #8b949e;">
                                    Целевое значение: {target_value:.2%} | Выборка: {sample_size:,}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # Прогресс-бар
                        progress = min(metric_value / target_value, 1.0) if target_value > 0 else 0.0
                        st.progress(progress)
                    else:
                        with st.expander(f"⚠️ {hypothesis_name}: Метрики пока недоступны"):
                            st.info(f"""
                            **Описание:** {description}
                            
                            **Целевая метрика:** {metric_name} ≥ {target_value:.2%}
                            
                            **Что нужно:**
                            - Активировать компонент Singularity 9.0
                            - Накопить данные для расчета метрик
                            - Проверить наличие записей в соответствующих таблицах БД
                            """)
                
            except Exception as e:
                st.error(f"Ошибка загрузки метрик Singularity 9.0: {e}")
                st.code(traceback.format_exc())
    except IndexError:
        pass

    # 📋 ПОСТАВИТЬ ЗАДАЧУ КОРПОРАЦИИ (мировые практики: Jira/Asana/Linear — чёткая форма, валидация, автоназначение)
    try:
        with tabs[20]:
            st.header("📋 Поставить задачу корпорации")
            st.markdown("""
            <div style="background: linear-gradient(145deg, #1e1e2e, #11111b); border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 16px;">
            <p style="color: #c9d1d9; margin: 0 0 12px 0; line-height: 1.6;">
                <strong>Как это работает (мировые практики):</strong>
            </p>
            <ul style="color: #c9d1d9; margin: 0 0 8px 0; padding-left: 20px; line-height: 1.6;">
                <li>Задача попадает в очередь. Оркестратор назначит исполнителя по специализации и загрузке (или укажете сами).</li>
                <li>Одна задача — один ответственный; сложные задачи разбиваются на подзадачи (родитель/дочерние), каждая со своим исполнителем.</li>
                <li>Тип задачи (Авто / Простая / Сложная / Несколько отделов) задаёт стратегию: декомпозиция и выбор экспертов.</li>
                <li>Smart Worker выполнит задачу и сохранит отчёт. Результат — во вкладке <strong>🛠️ Задачи</strong>.</li>
            </ul>
            <p style="color: #8b949e; margin: 12px 0 0 0; font-size: 0.9em;">По аналогии с Jira, Asana, Linear: чёткая формулировка, приоритет, привязка к домену и автоназначение.</p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("""
            <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px;">
            <strong style="color: #58a6ff;">💡 Совет:</strong> <span style="color: #c9d1d9;">Опишите задачу ясно (≥50 символов) — так оркестратор точнее подберёт эксперта и при необходимости разобьёт её на подзадачи.</span>
            </div>
            """, unsafe_allow_html=True)

            experts_for_task = []
            try:
                experts_for_task = fetch_data_tasks("SELECT id, name, role, department FROM experts WHERE is_active = true ORDER BY name")
            except Exception:
                try:
                    experts_for_task = fetch_data_tasks("SELECT id, name, role, department FROM experts ORDER BY name")
                except Exception:
                    pass
            expert_options = ["Автоназначение (оркестратор выберет эксперта)"]
            expert_id_map = {None: None}
            if experts_for_task:
                for e in experts_for_task:
                    label = f"{e.get('name', '')} — {e.get('role', '')} ({e.get('department', '')})"
                    expert_options.append(label)
                    expert_id_map[label] = e.get('id')

            domains_for_task = []
            try:
                domains_for_task = fetch_data("SELECT id, name FROM domains ORDER BY name") or []
            except Exception:
                pass
            domain_options = ["Без привязки к домену"]
            domain_id_map = {None: None}
            if domains_for_task:
                for d in domains_for_task:
                    domain_options.append(d.get('name', ''))
                    domain_id_map[d.get('name', '')] = d.get('id')

            with st.form("submit_task_form", clear_on_submit=True):
                col_t, col_p = st.columns([2, 1])
                with col_t:
                    task_title = st.text_input(
                        "Название задачи *",
                        placeholder="Кратко: что нужно сделать (до 500 символов)",
                        max_chars=500,
                        help="Обязательное поле. Будет видно в списке задач и у исполнителя."
                    )
                with col_p:
                    task_priority = st.selectbox(
                        "Приоритет *",
                        options=["medium", "high", "urgent", "low"],
                        format_func=lambda x: {"urgent": "Срочно", "high": "Высокий", "medium": "Средний", "low": "Низкий"}.get(x, x),
                        index=1,
                        help="Влияет на порядок обработки оркестратором и воркером."
                    )
                task_description = st.text_area(
                    "Описание задачи *",
                    placeholder="Подробно опишите задачу: контекст, ожидаемый результат, ограничения. Чем яснее формулировка — тем точнее выполнение.",
                    height=160,
                    max_chars=10000,
                    help="Обязательное поле. Рекомендуется ≥ 50 символов для точного автоназначения. Исполнитель будет опираться на это описание."
                )
                task_type_choice = st.selectbox(
                    "Тип задачи (опционально)",
                    options=["auto", "simple", "complex", "multi_dept"],
                    format_func=lambda x: {"auto": "Авто (оркестратор решит)", "simple": "Простая", "complex": "Сложная", "multi_dept": "Несколько отделов"}.get(x, x),
                    index=0,
                    help="Влияет на стратегию оркестратора: декомпозиция и назначение экспертов."
                )
                col_a, col_d = st.columns(2)
                with col_a:
                    assignee_choice = st.selectbox(
                        "Исполнитель",
                        options=expert_options,
                        help="«Автоназначение» — оркестратор выберет эксперта по домену и загрузке."
                    )
                with col_d:
                    domain_choice = st.selectbox(
                        "Домен (опционально)",
                        options=domain_options,
                        help="Привязка к домену помогает оркестратору при автоназначении."
                    )
                submitted = st.form_submit_button("Отправить задачу в корпорацию")
                if submitted:
                    title_clean = (task_title or "").strip()
                    desc_clean = (task_description or "").strip()
                    if not title_clean:
                        st.error("Укажите название задачи.")
                    elif not desc_clean:
                        st.error("Укажите описание задачи.")
                    else:
                        try:
                            assignee_id = None if assignee_choice == expert_options[0] else expert_id_map.get(assignee_choice)
                            domain_id = None if domain_choice == domain_options[0] else domain_id_map.get(domain_choice)
                            creator_id = None
                            creator_row = fetch_data("SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1")
                            if creator_row and creator_row[0]:
                                creator_id = creator_row[0].get('id')
                            if not creator_id and experts_for_task and experts_for_task[0]:
                                creator_id = experts_for_task[0].get('id')
                            metadata = {"source": "dashboard_submit", "submitted_at": datetime.now(timezone.utc).isoformat()}
                            conn = get_db_connection()
                            with conn.cursor() as cur:
                                insert_with_task_type = True
                                try:
                                    if domain_id is not None:
                                        cur.execute("""
                                            INSERT INTO tasks (title, description, status, priority, assignee_expert_id, creator_expert_id, domain_id, metadata, task_type)
                                            VALUES (%s, %s, 'pending', %s, %s, %s, %s, %s, %s)
                                            RETURNING id
                                        """, (title_clean[:500], desc_clean[:10000], task_priority, assignee_id, creator_id, domain_id, json.dumps(metadata), task_type_choice))
                                    else:
                                        cur.execute("""
                                            INSERT INTO tasks (title, description, status, priority, assignee_expert_id, creator_expert_id, metadata, task_type)
                                            VALUES (%s, %s, 'pending', %s, %s, %s, %s, %s)
                                            RETURNING id
                                        """, (title_clean[:500], desc_clean[:10000], task_priority, assignee_id, creator_id, json.dumps(metadata), task_type_choice))
                                except Exception as col_err:
                                    if "task_type" in str(col_err).lower() or "column" in str(col_err).lower():
                                        conn.rollback()
                                        insert_with_task_type = False
                                    else:
                                        raise
                                if not insert_with_task_type:
                                    if domain_id is not None:
                                        cur.execute("""
                                            INSERT INTO tasks (title, description, status, priority, assignee_expert_id, creator_expert_id, domain_id, metadata)
                                            VALUES (%s, %s, 'pending', %s, %s, %s, %s, %s)
                                            RETURNING id
                                        """, (title_clean[:500], desc_clean[:10000], task_priority, assignee_id, creator_id, domain_id, json.dumps(metadata)))
                                    else:
                                        cur.execute("""
                                            INSERT INTO tasks (title, description, status, priority, assignee_expert_id, creator_expert_id, metadata)
                                            VALUES (%s, %s, 'pending', %s, %s, %s, %s)
                                            RETURNING id
                                        """, (title_clean[:500], desc_clean[:10000], task_priority, assignee_id, creator_id, json.dumps(metadata)))
                                row = cur.fetchone()
                                conn.commit()
                                if row:
                                    task_id = row[0] if isinstance(row, (tuple, list)) else (row.get('id') if isinstance(row, dict) else None)
                                    st.success(f"✅ Задача создана. ID: `{task_id}`. Оркестратор назначит исполнителя (если не указан), воркер выполнит задачу. Результат — во вкладке **🛠️ Задачи**.")
                                else:
                                    st.warning("Задача не создана. Проверьте подключение к БД и наличие экспертов.")
                        except Exception as e:
                            st.error(f"Ошибка создания задачи: {e}")
                            st.code(traceback.format_exc())

            st.subheader("Последние поставленные задачи")
            try:
                last_tasks = fetch_data_tasks("""
                    SELECT id, title, status, created_at
                    FROM tasks
                    WHERE metadata->>'source' = 'dashboard_submit'
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                if not last_tasks:
                    last_tasks = fetch_data_tasks("""
                        SELECT id, title, status, created_at
                        FROM tasks
                        ORDER BY created_at DESC
                        LIMIT 10
                    """) or []
                if last_tasks:
                    df_last = pd.DataFrame(last_tasks)
                    df_last["created_at"] = pd.to_datetime(df_last["created_at"], utc=True).dt.strftime("%Y-%m-%d %H:%M")
                    st.dataframe(df_last[["id", "title", "status", "created_at"]].rename(columns={"id": "ID", "title": "Название", "status": "Статус", "created_at": "Дата"}), use_container_width=True, hide_index=True)
                else:
                    st.caption("Пока нет задач. Создайте первую задачу выше.")
            except Exception as e:
                st.caption(f"Не удалось загрузить список: {e}")
    except IndexError:
        pass

    # 🤖 АГЕНТ — чат с Викторией (Web IDE)
    try:
        with tabs[21]:
            st.header("🤖 Агент — чат с Викторией")
            st.markdown("""
            <div style="background: linear-gradient(145deg, #1e1e2e, #11111b); border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 16px;">
            <p style="color: #c9d1d9; margin: 0 0 12px 0; line-height: 1.6;">
                Полноценный чат с <strong>Викторией</strong> (Team Lead корпорации): планирование, шаги агента, делегирование Веронике и экспертам — в <strong>ATRA Web IDE</strong>.
            </p>
            <p style="color: #8b949e; margin: 12px 0 0 0; font-size: 0.9em;">Откройте Web IDE по кнопке ниже. Вкладка «Агент» там первая — сразу откроется чат.</p>
            </div>
            """, unsafe_allow_html=True)
            web_ide_url = os.environ.get("WEB_IDE_URL", "http://localhost:3000")
            st.link_button("🚀 Открыть чат с агентом (Web IDE)", web_ide_url, type="primary", use_container_width=True)
            st.caption(f"Ссылка: {web_ide_url} — убедитесь, что Web IDE запущен (docker-compose up -d в корне проекта).")
    except IndexError:
        pass

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Критическая ошибка дашборда: {e}")
        st.code(traceback.format_exc())
        st.info("Попробуйте обновить страницу или обратитесь к администратору.")
