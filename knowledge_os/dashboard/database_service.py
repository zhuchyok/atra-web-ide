import streamlit as st
import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
import contextlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Connection pool для оптимизации и предотвращения утечек
@st.cache_resource
def _get_connection_pool():
    """Внутренний пул соединений. Используйте db_session()."""
    db_urls = [
        os.getenv("DATABASE_URL"),
        "postgresql://admin:secret@localhost:5432/knowledge_os",
        "postgresql://admin:secret@127.0.0.1:5432/knowledge_os",
        "postgresql://admin:secret@knowledge_postgres:5432/knowledge_os"
    ]
    for db_url in db_urls:
        if db_url:
            try:
                # Пул от 1 до 20 соединений для Mac Studio
                p = pool.ThreadedConnectionPool(1, 20, db_url, cursor_factory=RealDictCursor, connect_timeout=5)
                logger.info(f"✅ Пул соединений (psycopg2) инициализирован для {db_url}")
                return p
            except (psycopg2.Error, psycopg2.OperationalError) as e:
                logger.debug(f"Не удалось создать пул для {db_url}: {e}")
                continue
    return None

def _set_query_timeout(conn, seconds=15):
    """Ограничить время выполнения запросов."""
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{int(seconds) * 1000}'")
    except Exception:
        pass

@contextlib.contextmanager
def db_session():
    """Безопасная сессия работы с БД через пул."""
    p = _get_connection_pool()
    if not p:
        st.error("❌ Критическая ошибка: База данных недоступна. Проверьте PostgreSQL.")
        yield None
        return
    
    conn = None
    try:
        conn = p.getconn()
        _set_query_timeout(conn)
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"🚨 Ошибка в db_session: {e}")
        raise
    finally:
        if conn:
            p.putconn(conn)

def get_db_connection():
    """Обратная совместимость."""
    p = _get_connection_pool()
    if p:
        return p.getconn()
    return None

@st.cache_data(ttl=60, max_entries=100)
def fetch_data(query, params=None, cache_key=None):
    """Оптимизированная функция получения данных через пул сессий."""
    for attempt in range(3):
        try:
            with db_session() as conn:
                if not conn:
                    return []
                with conn.cursor() as cur:
                    cur.execute(query, params or ())
                    return cur.fetchall()
        except (psycopg2.Error, psycopg2.OperationalError, psycopg2.DatabaseError) as e:
            if "deadlock detected" in str(e).lower() and attempt < 2:
                import time
                time.sleep(0.15 * (attempt + 1))
                continue
            logger.error(f"Ошибка БД в fetch_data: {e}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка в fetch_data: {e}")
            return []
    return []

@st.cache_data(ttl=15, max_entries=50)
def fetch_data_tasks(query, params=None, _cache_bust=None):
    """Данные для вкладки Задачи (обновляются чаще)."""
    return fetch_data(query, params)

def run_query(query, params=None):
    """Выполняет SQL запрос на изменение данных через пул."""
    try:
        with db_session() as conn:
            if not conn:
                return False
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                conn.commit()
            return True
    except Exception as e:
        logger.error(f"Ошибка БД при выполнении запроса: {e}")
        return False

def fetch_parallel(queries_dict):
    """Параллельное выполнение запросов."""
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(queries_dict), 5)) as executor:
        futures = {executor.submit(fetch_data, val[0], val[1] if len(val) > 1 else ()): key 
                   for key, val in queries_dict.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                logger.error(f"Ошибка в fetch_parallel для {key}: {e}")
                results[key] = []
    return results

def check_services():
    """Проверка статуса сервисов с кэшированием"""
    services = {"PostgreSQL": "✅", "Victoria Agent": "✅"}
    is_container = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER') == 'true'
    host_url = "http://host.docker.internal" if is_container else "http://localhost"
    
    # MLX API
    try:
        import httpx
        mlx_response = httpx.get(f"{host_url}:11435/health", timeout=8, follow_redirects=True)
        if mlx_response.status_code in [200, 429, 503]:
            try:
                data = mlx_response.json()
                if data.get('status') in ['healthy', 'overloaded'] or 'service' in data:
                    services["MLX API"] = "✅"
                elif 'error' in data:
                    error_msg = str(data.get('error', '')).lower()
                    services["MLX API"] = "✅" if any(kw in error_msg for kw in ['rate limit', '429', 'overload', '503', 'concurrent']) else "⚠️"
                else:
                    services["MLX API"] = "✅"
            except (ValueError, KeyError, TypeError):
                services["MLX API"] = "✅"
        else:
            services["MLX API"] = "⚠️"
    except Exception:
        try:
            import httpx
            r = httpx.get("http://localhost:11435/health", timeout=8)
            services["MLX API"] = "✅" if r.status_code in [200, 429, 503] else "⚠️"
        except Exception:
            services["MLX API"] = "⚠️"
            
    # Ollama
    try:
        import httpx
        ollama_response = httpx.get(f"{host_url}:11434/api/tags", timeout=2)
        services["Ollama"] = "✅" if ollama_response.status_code == 200 else "⚠️"
    except Exception:
        try:
            import httpx
            r = httpx.get("http://localhost:11434/api/tags", timeout=2)
            services["Ollama"] = "✅" if r.status_code == 200 else "⚠️"
        except Exception:
            services["Ollama"] = "⚠️"
            
    return services

@st.cache_data(ttl=60, max_entries=5)
def fetch_intellectual_capital():
    """Интеллектуальный Капитал: полный запрос или fallback при отсутствии usage_count/is_verified."""
    conn = None
    try:
        p = _get_connection_pool()
        if not p: return []
        conn = p.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_nodes,
                    COALESCE(SUM(usage_count), 0) as total_usage,
                    AVG(confidence_score) as avg_confidence,
                    COUNT(*) FILTER (WHERE is_verified = true) as verified_nodes
                FROM knowledge_nodes
            """)
            res = cur.fetchall()
            p.putconn(conn)
            return res
    except Exception as e:
        if conn:
            try: conn.rollback()
            except: pass
            p.putconn(conn)
        logger.error(f"Ошибка в fetch_intellectual_capital: {e}")
        return []

def quick_db_check():
    """Быстрая проверка соединения с БД."""
    try:
        with db_session() as conn:
            if not conn: return False, "No connection"
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True, None
    except Exception as e:
        return False, str(e)

def _normalize_metadata(metadata):
    """Приводит metadata к dict (из БД может прийти JSON-строка)."""
    if metadata is None: return {}
    if isinstance(metadata, dict): return metadata
    if isinstance(metadata, str):
        try:
            import json
            return json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}

def get_project_slugs():
    """Список slug проектов."""
    try:
        r = fetch_data("SELECT slug FROM projects WHERE is_active = true ORDER BY slug")
        return [x["slug"] for x in r] if r else []
    except Exception:
        return []

def fetch_latest_directive():
    """Получить последнюю директиву совета."""
    return fetch_data("""
        SELECT content, created_at FROM knowledge_nodes 
        WHERE metadata->>'type' IN ('board_directive', 'board_consult')
        ORDER BY created_at DESC LIMIT 1
    """)

def fetch_sidebar_metrics():
    """Получить метрики для боковой панели."""
    return fetch_parallel({
        "tasks": ("SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE status = 'completed') as completed, COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress, COUNT(*) FILTER (WHERE status = 'pending') as pending FROM tasks", ()),
        "experts": ("SELECT COUNT(*) as count FROM experts", ()),
        "finance": ("SELECT COALESCE(SUM(token_usage), 0) as total_tokens, COALESCE(SUM(cost_usd), 0) as total_cost FROM interaction_logs WHERE created_at > NOW() - INTERVAL '24 hours'", ()),
        "failed_tasks": ("SELECT id, title, metadata->>'source' as source FROM tasks WHERE status = 'failed' ORDER BY updated_at DESC LIMIT 5", ()),
        "changes": ("SELECT COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 minute') as last_minute, COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as last_hour FROM tasks", ())
    })

def search_knowledge_base(embedding):
    """Поиск в базе знаний по эмбеддингу."""
    return fetch_data("""
        SELECT LEFT(k.content, 300) as content, d.name as domain, (1 - (k.embedding <=> %s::vector)) as similarity
        FROM knowledge_nodes k JOIN domains d ON k.domain_id = d.id
        WHERE k.embedding IS NOT NULL
        ORDER BY similarity DESC LIMIT 5
    """, (str(embedding),))
