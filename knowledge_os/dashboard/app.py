import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import httpx
import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from components.metrics import render_metric_card
from database_service import (
    check_services,
    db_session,
    fetch_data,
    fetch_intellectual_capital,
    fetch_latest_directive,
    fetch_parallel,
    fetch_sidebar_metrics,
    get_db_connection,
    get_project_slugs,
    quick_db_check,
    search_knowledge_base,
)

logger = logging.getLogger(__name__)
# Suppress known Streamlit bare-mode context noise in container logs.
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").setLevel(logging.ERROR)

# Корпорация: корень и каталог приложения (дашборд = часть корпорации, ищем модули в корпорации)
_DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))  # knowledge_os/dashboard
CORPORATION_ROOT = os.path.dirname(_DASHBOARD_DIR)  # knowledge_os
CORPORATION_APP_DIR = os.path.join(
    CORPORATION_ROOT, "app"
)  # knowledge_os/app — singularity_9_ab_tester, evaluator

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
            _dashboard_log.warning(
                "evaluator load failed CORPORATION_APP_DIR=%s: %s",
                CORPORATION_APP_DIR,
                _eval_err,
                exc_info=True,
            )

# Настройка страницы
st.set_page_config(
    page_title="Intelligence Command Center | ATRA Corporation",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

VECTOR_CORE_URL = os.getenv("VECTOR_CORE_URL", "http://knowledge_vector_core:8001")


def get_embedding(text: str) -> list:
    """Get embedding from VectorCore microservice."""
    try:
        with httpx.Client() as client:
            response = client.post(f"{VECTOR_CORE_URL}/encode", json={"text": text}, timeout=30.0)
            response.raise_for_status()
            return response.json()["embedding"]
    except (httpx.HTTPError, httpx.TimeoutException, httpx.RequestError) as e:
        st.error(f"Ошибка VectorCore (HTTP): {e}")
        return [0.0] * 768  # 768 = nomic-embed-text; knowledge_nodes.embedding vector(768)
    except (ValueError, KeyError, TypeError) as e:
        st.error(f"Ошибка VectorCore (данные): {e}")
        return [0.0] * 768
    except Exception as e:
        st.error(f"Неожиданная ошибка VectorCore: {e}")
        return [0.0] * 768


# Design system: токены (дизайнер) + компоненты (верстальщик)
# Цвета, отступы и типографика — единый источник для всего дашборда

st.markdown(
    """
    <style>
    /* === DESIGN TOKENS (UI/UX) === */
    :root {
        --dash-bg: #05070a;
        --dash-surface: #0d1117;
        --dash-surface-elevated: #161b22;
        --dash-border: #30363d;
        --dash-border-muted: #21262d;
        --dash-text: #c9d1d9;
        --dash-text-muted: #8b949e;
        --dash-text-strong: #ffffff;
        --dash-accent: #58a6ff;
        --dash-accent-dark: #1f6feb;
        --dash-success: #238636;
        --dash-warning: #fab387;
        --dash-danger: #f38ba8;
        --dash-radius: 12px;
        --dash-radius-sm: 8px;
        --dash-space: 16px;
        --dash-space-sm: 12px;
        --dash-space-lg: 24px;
        --dash-font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        --dash-shadow: 0 4px 12px rgba(0,0,0,0.3);
        /* Типографика: единая шкала размеров */
        --dash-text-xs: 0.6875rem;   /* 11px — мета, подписи */
        --dash-text-sm: 0.75rem;     /* 12px — caption, badge */
        --dash-text-base: 0.875rem;   /* 14px — основной текст */
        --dash-text-md: 0.9375rem;    /* 15px — карточки */
        --dash-text-lg: 1rem;         /* 16px — подзаголовки */
        --dash-text-xl: 1.125rem;     /* 18px — заголовки блоков */
        --dash-text-2xl: 1.25rem;     /* 20px — h3 */
        --dash-text-3xl: 1.5rem;      /* 24px — h2 */
        --dash-text-4xl: 1.75rem;    /* 28px — метрики, цифры */
        --dash-text-5xl: 2rem;       /* 32px — крупные акценты */
    }
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        font-family: var(--dash-font);
        font-size: var(--dash-text-base);
        background-color: var(--dash-bg);
        line-height: 1.5;
    }
    .main { background-color: var(--dash-bg); font-size: var(--dash-text-base); }

    /* Глобальные заголовки Streamlit и Markdown */
    h1, [data-testid="stMarkdown"] h1 { font-size: var(--dash-text-3xl) !important; font-weight: 800 !important; letter-spacing: -0.02em; margin-bottom: 0.5rem !important; }
    h2, [data-testid="stMarkdown"] h2 { font-size: var(--dash-text-2xl) !important; font-weight: 700 !important; margin-top: 1rem !important; margin-bottom: 0.5rem !important; }
    h3, [data-testid="stMarkdown"] h3 { font-size: var(--dash-text-xl) !important; font-weight: 600 !important; margin-top: 0.75rem !important; margin-bottom: 0.35rem !important; }
    p, [data-testid="stMarkdown"] p { font-size: var(--dash-text-base) !important; line-height: 1.55 !important; }
    [data-testid="stCaptionContainer"] { font-size: var(--dash-text-sm) !important; color: var(--dash-text-muted) !important; }
    [data-testid="stMetricLabel"] { font-size: var(--dash-text-sm) !important; font-weight: 600 !important; color: var(--dash-text-muted) !important; }

    /* Сайдбар в одной стилистике */
    [data-testid="stSidebar"] {
        background: var(--dash-surface) !important;
        border-right: 1px solid var(--dash-border) !important;
    }
    [data-testid="stSidebar"] .stMarkdown { color: var(--dash-text-muted); }
    [data-testid="stSidebar"] label { color: var(--dash-text) !important; }

    @media (max-width: 768px) {
        .premium-card { padding: var(--dash-space) !important; margin-bottom: var(--dash-space-sm) !important; }
        .stTabs [data-baseweb="tab-list"] { flex-wrap: wrap; gap: 8px !important; }
        .stTabs [data-baseweb="tab"] { font-size: var(--dash-text-sm) !important; padding: 8px var(--dash-space-sm) !important; }
        [data-testid="stSidebar"] { min-width: 200px !important; }
        .expert-header { font-size: var(--dash-text-lg) !important; }
        .card-text { font-size: var(--dash-text-base) !important; }
        .premium-card .premium-value { font-size: var(--dash-text-3xl) !important; }
    }
    @media (max-width: 480px) {
        .premium-card { padding: var(--dash-space-sm) !important; }
        .stTabs [data-baseweb="tab"] { font-size: var(--dash-text-xs) !important; padding: 6px 10px !important; }
        h1, [data-testid="stMarkdown"] h1 { font-size: var(--dash-text-2xl) !important; }
        h2, [data-testid="stMarkdown"] h2 { font-size: var(--dash-text-xl) !important; }
        h3, [data-testid="stMarkdown"] h3 { font-size: var(--dash-text-lg) !important; }
    }

    .premium-card {
        background: linear-gradient(145deg, var(--dash-surface-elevated), var(--dash-surface));
        border: 1px solid var(--dash-border);
        border-radius: var(--dash-radius);
        padding: var(--dash-space-lg);
        margin-bottom: var(--dash-space);
        transition: transform 0.2s, border-color 0.2s;
    }
    .premium-card:hover {
        border-color: var(--dash-accent);
        transform: translateY(-2px);
        box-shadow: var(--dash-shadow);
    }
    .directive-card {
        background: linear-gradient(145deg, rgba(30,30,46,0.95), var(--dash-surface));
        border: 2px solid var(--dash-danger);
        border-radius: var(--dash-radius);
        padding: var(--dash-space-lg);
        margin-bottom: var(--dash-space-lg);
    }
    .domain-badge {
        background: linear-gradient(135deg, var(--dash-accent-dark), var(--dash-accent));
        color: white;
        padding: 4px var(--dash-space-sm);
        border-radius: 20px;
        font-size: var(--dash-text-sm);
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: var(--dash-space-sm);
        display: inline-block;
    }
    .usage-badge {
        background-color: var(--dash-success);
        color: white;
        padding: 4px var(--dash-space-sm);
        border-radius: 20px;
        font-size: var(--dash-text-sm);
        font-weight: 600;
        float: right;
    }
    .card-text {
        color: var(--dash-text);
        font-size: var(--dash-text-md);
        line-height: 1.6;
        margin-top: 10px;
        white-space: pre-wrap;
    }
    .premium-card .premium-value { font-size: var(--dash-text-4xl); font-weight: 800; color: var(--dash-accent); }
    .premium-card .premium-meta { font-size: var(--dash-text-sm); color: var(--dash-text-muted); }
    .liquidity-bar {
        height: 4px;
        background-color: var(--dash-border);
        border-radius: 2px;
        margin-top: 15px;
    }
    .liquidity-fill {
        height: 100%;
        background: linear-gradient(90deg, var(--dash-accent), var(--dash-accent-dark));
        border-radius: 2px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: var(--dash-space-lg); background-color: transparent; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-size: var(--dash-text-base) !important; background: transparent !important; border: none !important; color: var(--dash-text-muted) !important; font-weight: 600 !important; transition: all 0.3s; }
    .stTabs [data-baseweb="tab"]:hover { color: var(--dash-accent) !important; }
    .stTabs [aria-selected="true"] { color: var(--dash-accent) !important; border-bottom: 2px solid var(--dash-accent) !important; }
    .expert-header { font-size: var(--dash-text-xl); font-weight: 800; color: var(--dash-text-strong); margin-bottom: 4px; }
    .expert-role { font-size: var(--dash-text-base); color: var(--dash-text-muted); margin-bottom: var(--dash-space-sm); }

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
        border: 2px solid var(--dash-accent);
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

    [data-testid="stMetricValue"] {
        font-size: var(--dash-text-4xl) !important;
        font-weight: 800 !important;
        letter-spacing: -0.02em;
    }

    /* Скроллбар стилизация */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track { background: var(--dash-surface); }
    ::-webkit-scrollbar-thumb { background: var(--dash-border); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--dash-accent); }
    .stButton > button {
        background: linear-gradient(145deg, var(--dash-accent-dark), var(--dash-accent));
        color: white;
        border: none;
        border-radius: var(--dash-radius-sm);
        padding: 10px 20px;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(88, 166, 255, 0.4);
    }
    .premium-card {
        background: linear-gradient(145deg, rgba(22, 27, 34, 0.9), rgba(13, 17, 23, 0.95)) !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
    }
    .alert-banner {
        background: linear-gradient(90deg, rgba(246, 179, 135, 0.15), rgba(243, 139, 168, 0.1));
        border: 1px solid var(--dash-warning);
        border-radius: var(--dash-radius-sm);
        padding: var(--dash-space-sm) var(--dash-space);
        margin-bottom: var(--dash-space);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--dash-space-sm);
        flex-wrap: wrap;
    }
    .alert-banner.dismissed { display: none !important; }
    .empty-state {
        text-align: center;
        padding: 32px var(--dash-space-lg);
        background: rgba(13, 17, 23, 0.6);
        border: 1px dashed var(--dash-border);
        border-radius: var(--dash-radius);
        color: var(--dash-text-muted);
    }
    .empty-state .empty-icon { font-size: 3rem; margin-bottom: var(--dash-space-sm); opacity: 0.8; }
    .empty-state .empty-title { color: var(--dash-text); font-weight: 600; font-size: var(--dash-text-lg); margin-bottom: 8px; }
    .empty-state .empty-hint { font-size: var(--dash-text-base); line-height: 1.5; }
    .dash-text-xs { font-size: var(--dash-text-xs) !important; }
    .dash-text-sm { font-size: var(--dash-text-sm) !important; }
    .dash-text-base { font-size: var(--dash-text-base) !important; }
    .dash-text-lg { font-size: var(--dash-text-lg) !important; }
    /* Единые размеры для карточек задач и блоков контента */
    [data-testid="stMarkdown"] div[style*="font-size"] { line-height: 1.5; }
    .task-card-title { font-size: var(--dash-text-lg) !important; font-weight: 800; }
    .task-card-meta { font-size: var(--dash-text-sm) !important; color: var(--dash-text-muted); }
    .task-card-desc { font-size: var(--dash-text-base) !important; line-height: 1.55; }
    .block-meta { font-size: var(--dash-text-xs) !important; color: var(--dash-text-muted); }
    /* Таблицы и данные */
    .dash-table { font-size: var(--dash-text-sm); }
    </style>
    """,
    unsafe_allow_html=True,
)


def _toast(message: str, icon: str = "✅"):
    """Всплывающее уведомление (ТЗ: useToast). Использует st.toast если доступен."""
    try:
        if hasattr(st, "toast"):
            st.toast(f"{icon} {message}", icon=icon[:1] if icon else "✅")
        else:
            st.success(message)
    except Exception:
        st.success(message)


def main():
    # Toast с прошлого run (ТЗ: уведомления после действий)
    if st.session_state.get("toast_message"):
        msg, icon = st.session_state.pop("toast_message", (None, "✅"))
        if msg:
            try:
                _toast(msg, icon)
            except Exception:
                pass
    # Инициализация session_state для отслеживания удаленных отчетов
    if "deleted_reports" not in st.session_state:
        st.session_state.deleted_reports = set()

    # Быстрая проверка БД с таймаутом — если не ответила за 10 сек, показываем ошибку и не крутим «Running fetch_data»
    if st.session_state.get("_db_ok") is not True:
        with st.spinner("Подключение к БД..."):
            try:
                with ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(quick_db_check)
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
                st.error(
                    "Таймаут подключения к БД (10 сек). Проверьте PostgreSQL и сеть (в Docker: сервис knowledge_postgres в atra-network)."
                )
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

    # Шапка: логотип, раздел, время UTC, статус, метрики, обновить (всё на своих местах)
    _section = st.session_state.get("dashboard_section", "Обзор")
    col_header1, col_header2, col_header3, col_header4, col_header5 = st.columns([2, 1, 1, 1, 1])

    # ПАРАЛЛЕЛЬНЫЙ СБОР ДАННЫХ ДЛЯ ШАПКИ И МЕТРИК
    with st.spinner(""):
        results = fetch_parallel(
            {
                "tasks_count": ("SELECT COUNT(*) as count FROM tasks", ()),
                "experts_count": ("SELECT COUNT(*) as count FROM experts", ()),
                "intellectual_capital": (
                    "SELECT COUNT(*) as total_nodes, SUM(usage_count) as total_usage FROM knowledge_nodes",
                    (),
                ),
                "last_update": (
                    """
                SELECT
                    GREATEST(
                        COALESCE((SELECT MAX(updated_at) FROM tasks), '1970-01-01'::timestamp),
                        COALESCE((SELECT MAX(created_at) FROM knowledge_nodes), '1970-01-01'::timestamp)
                    ) as last_db_update
            """,
                    (),
                ),
            }
        )

    total_tasks = results.get("tasks_count", [{}])[0].get("count", 0)
    total_experts = results.get("experts_count", [{}])[0].get("count", 0)
    total_nodes = results.get("intellectual_capital", [{}])[0].get("total_nodes", 0)
    last_db_update = results.get("last_update", [{}])[0].get("last_db_update")

    # Получаем время последнего обновления данных из БД
    update_status = "нет данных"
    status_color = "#8b949e"
    if last_db_update:
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

    # Настройка времени: используем московское время (UTC+3)
    moscow_tz = timezone(timedelta(hours=3))
    current_time = datetime.now(moscow_tz).strftime("%H:%M:%S")

    with col_header1:
        st.title("🏢 ATRA Corporation 10.0")
        status_emoji = (
            "🟢" if status_color == "#238636" else "🟡" if status_color == "#fab387" else "🔴"
        )
        st.markdown(
            f"""
            <div class="dash-header-line" style="display: flex; align-items: center; gap: 12px; margin-top: 2px; flex-wrap: wrap;">
                <span style="color: var(--dash-text-muted); font-size: var(--dash-text-sm);">{_section}</span>
                <span style="color: var(--dash-border);">|</span>
                <span style="color: var(--dash-text-muted); font-size: var(--dash-text-sm);">🕐 {current_time} MSK</span>
                <span style="color: {status_color}; font-size: var(--dash-text-xs); font-weight: 600;">{status_emoji} {update_status}</span>
                <span style="display: inline-block; width: 6px; height: 6px; background: {status_color}; border-radius: 50%; animation: pulse 2s infinite;"></span>
            </div>
            <style>@keyframes pulse {{ 0%,100% {{ opacity:1 }} 50% {{ opacity:.6 }} }}</style>
        """,
            unsafe_allow_html=True,
        )
        st.caption("Кэш 60 с · обновить: 🔄 справа")
    with col_header2:
        st.metric("Задач", f"{total_tasks:,}")
    with col_header3:
        st.metric("Узлов знаний", f"{total_nodes:,}")
    with col_header4:
        st.metric("Экспертов", total_experts)
    with col_header5:
        if st.button("🔄", help="Обновить все данные", width="stretch", key="header_refresh"):
            st.cache_data.clear()
            st.session_state["toast_message"] = ("Данные обновлены", "🔄")
            st.rerun()

    st.markdown("---")

    _svc_for_banner = check_services()
    _any_warning = any(s == "⚠️" for s in _svc_for_banner.values())

    # [SINGULARITY 26.9] Stale data detection (>24h)
    _is_stale = False
    if last_db_update:
        if isinstance(last_db_update, datetime):
            if last_db_update.tzinfo is None:
                last_db_update = last_db_update.replace(tzinfo=timezone.utc)
            _is_stale = (datetime.now(timezone.utc) - last_db_update).total_seconds() > 86400

    if (_any_warning or _is_stale) and not st.session_state.get("alert_banner_dismissed"):
        warn_text = ""
        if _any_warning:
            warn_services = [n for n, s in _svc_for_banner.items() if s == "⚠️"]
            hint = []
            if "Victoria Agent" in warn_services:
                hint.append("Victoria (VICTORIA_URL / victoria-agent:8000)")
            if "MLX API" in warn_services:
                hint.append("MLX :11435")
            if "Ollama" in warn_services:
                hint.append("Ollama :11434")
            if "PostgreSQL" in warn_services:
                hint.append("PostgreSQL / pgbouncer")
            hint_s = "; ".join(hint) if hint else "MLX :11435 / Ollama :11434"
            warn_text = f"⚠️ Сервисы недоступны: {', '.join(warn_services)}. Проверьте: {hint_s}."

        if _is_stale:
            stale_msg = f"🕰️ Данные устарели (последнее обновление: {update_status}). Проверьте воркеры (nightly/evolution)."
            warn_text = f"{warn_text} | {stale_msg}" if warn_text else stale_msg

        st.markdown(
            f"""
            <div class="alert-banner" id="alert-banner">
                <span>{warn_text}</span>
            </div>
        """,
            unsafe_allow_html=True,
        )
        col_alert_btn, _ = st.columns([1, 5])
        with col_alert_btn:
            if st.button(
                "Скрыть", key="dismiss_alert_banner", help="Скрыть баннер до следующей перезагрузки"
            ):
                st.session_state["alert_banner_dismissed"] = True
                st.rerun()

    # --- Главная Директива Совета (Top Priority) ---
    latest_directive = fetch_latest_directive()
    if latest_directive and latest_directive[0]:
        d0 = latest_directive[0]
        created = d0.get("created_at")
        created_str = (
            created.strftime("%d.%m %H:%M")
            if hasattr(created, "strftime")
            else (str(created)[:16] if created else "N/A")
        )
        content_safe = d0.get("content") or ""
        st.markdown(
            f"""
            <div class="directive-card">
                <div style="color: var(--dash-danger); font-weight: 800; font-size: var(--dash-text-base); text-transform: uppercase; margin-bottom: 10px;">
                    🚨 СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА ДИРЕКТОРОВ (от {created_str})
                </div>
                <div style="color: #cdd6f4; font-size: var(--dash-text-lg); line-height: 1.6;">{content_safe}</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    # --- Боковая панель: только навигация и ключевые метрики (минимализм, без мутору) ---
    with st.sidebar:
        # --- ЕДИНОЕ ОКНО СТАТУСА (Claude Code Pattern) ---
        services_status = check_services()
        all_ok = all(s == "✅" for s in services_status.values())
        status_text = "СИСТЕМА ОК" if all_ok else "ТРЕБУЕТСЯ ВНИМАНИЕ"
        status_color = "var(--dash-success)" if all_ok else "var(--dash-warning)"

        st.markdown(
            f"""
            <div style="background: {status_color}; color: white; padding: 12px; border-radius: 8px; margin-bottom: 16px; text-align: center; font-weight: 800; font-size: 14px;">
                {status_text}
            </div>
        """,
            unsafe_allow_html=True,
        )

        _sections = [
            "🏠 Обзор (Pulse)",
            "🏛️ Wisdom & Mentorship",
            "🛠️ Задачи и SLA",
            "🎯 Стратегия и ROI",
            "🧠 Интеллект (RAG)",
            "🕵️ Инструменты экспертов",
            "⚙️ Система и Безопасность",
        ]
        section = st.radio("📂 Раздел", _sections, key="nav_section", label_visibility="collapsed")
        st.session_state.dashboard_section = section

        st.markdown("---")
        st.markdown("📅 **Период данных**")
        time_range = st.selectbox(
            "Показывать данные за:",
            [
                "Последние 24 часа",
                "Последние 3 дня",
                "Последние 7 дней",
                "Последние 30 дней",
                "За все время",
            ],
            index=2,
            key="global_time_range_widget",
        )
        st.session_state.global_time_range = time_range

        st.markdown("---")
        # Одна строка: сервисы
        svc_line = "  ".join(f"{s} {n}" for n, s in services_status.items())
        st.caption(f"🔌 {svc_line}")
        st.markdown("---")
        # Ключевые метрики: один компактный блок
        sidebar_data = fetch_sidebar_metrics()
        _task_stats = sidebar_data.get("tasks", [])
        _stats_ic = fetch_intellectual_capital()
        _experts_cnt = sidebar_data.get("experts", [])

        t_total = _task_stats[0]["total"] if _task_stats and _task_stats[0] else 0
        t_done = _task_stats[0]["completed"] if _task_stats and _task_stats[0] else 0
        t_work = _task_stats[0]["in_progress"] if _task_stats and _task_stats[0] else 0
        t_wait = _task_stats[0]["pending"] if _task_stats and _task_stats[0] else 0
        n_nodes = _stats_ic[0]["total_nodes"] if _stats_ic and _stats_ic[0] else 0
        n_exp = _experts_cnt[0]["count"] if _experts_cnt and _experts_cnt[0] else 0

        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("Задач", f"{t_total:,}", f"✅{t_done}")
        with col_s2:
            st.metric("Узлов", f"{n_nodes:,}", "")
        with col_s3:
            st.metric("Экспертов", n_exp, "")
        st.markdown("---")
        # Финансы 24ч — одна строка
        finance_data = sidebar_data.get("finance", [])
        if finance_data and finance_data[0]:
            tok = finance_data[0]["total_tokens"] or 0
            cost = finance_data[0]["total_cost"] or 0
            st.caption(f"💰 24ч: токены {tok:,} · ${cost:.4f}")
        else:
            st.caption("💰 24ч: токены 0")
        st.caption("Обновление: кнопка 🔄 в шапке")
        # Всё остальное — в expander «Подробнее»
        with st.expander("Подробнее"):
            if services_status.get("MLX API") == "⚠️":
                st.caption("⚠️ MLX: порт 11435. `bash scripts/start_mlx_api_server.sh`")
            if services_status.get("Ollama") == "⚠️":
                st.caption("⚠️ Ollama: порт 11434. `ollama serve`")

            failed_tasks = sidebar_data.get("failed_tasks", [])
            for ft in failed_tasks or []:
                st.caption(f"❌ {ft.get('title', '')[:50]} | {ft.get('source', '-')}")

            changes_stats = sidebar_data.get("changes", [])
            if changes_stats and changes_stats[0]:
                cs = changes_stats[0]
                st.caption(
                    f"Задач: 1 мин — {cs.get('last_minute', 0) or 0}, 1 ч — {cs.get('last_hour', 0) or 0}"
                )
            st.caption("Кэш БД 60 с, сервисы 30 с. Принудительное обновление — 🔄 в шапке.")

    # Раздел «Обзор»: dashboard home — только ключевые метрики, директива, поиск (без лишнего)
    if "Обзор" in st.session_state.get("dashboard_section", ""):
        # Карточки метрик в одну строку (как в ТЗ: real-time метрики)
        time_range = st.session_state.get("global_time_range", "Последние 7 дней")
        from database_service import get_time_filter

        t_filter = get_time_filter(time_range, "created_at")

        with st.spinner(""):
            results = fetch_parallel(
                {
                    "tasks": (
                        f"SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress, COUNT(*) FILTER (WHERE status = 'pending') as pending, COUNT(*) FILTER (WHERE status = 'failed') as failed, COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled FROM tasks WHERE {t_filter}",
                        (),
                    ),
                    "experts": ("SELECT COUNT(*) as count FROM experts", ()),
                    "task_sla": (
                        """
                        SELECT
                            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') AS created_24h,
                            COUNT(*) FILTER (WHERE status = 'completed' AND updated_at > NOW() - INTERVAL '24 hours') AS completed_24h,
                            COUNT(*) FILTER (WHERE status = 'failed' AND updated_at > NOW() - INTERVAL '24 hours') AS failed_24h,
                            COUNT(*) FILTER (WHERE status = 'in_progress' AND updated_at < NOW() - INTERVAL '30 minutes') AS stale_in_progress,
                            COUNT(*) FILTER (WHERE status = 'failed' AND (result IS NULL OR LENGTH(TRIM(result)) = 0)) AS failed_without_reason
                        FROM tasks
                        """,
                        (),
                    ),
                }
            )
            _to = results.get("tasks", [])
            _ex = results.get("experts", [])
            _sla = results.get("task_sla", [])

            # Intellectual capital also needs filtering
            _ic = fetch_data(
                f"SELECT COUNT(*) as total_nodes FROM knowledge_nodes WHERE {t_filter}"
            )
            _svc = check_services()

        o_tasks = _to[0]["total"] if _to and _to[0] else 0
        o_in_progress = _to[0]["in_progress"] if _to and _to[0] else 0
        o_pending = _to[0]["pending"] if _to and _to[0] else 0
        o_failed = _to[0].get("failed", 0) if _to and _to[0] else 0
        o_cancelled = _to[0].get("cancelled", 0) if _to and _to[0] else 0
        o_nodes = _ic[0]["total_nodes"] if _ic and _ic[0] else 0
        o_experts = _ex[0]["count"] if _ex and _ex[0] else 0
        o_services_ok = sum(1 for s in _svc.values() if s == "✅")
        o_services_total = len(_svc)
        s_created_24h = _sla[0].get("created_24h", 0) if _sla and _sla[0] else 0
        s_completed_24h = _sla[0].get("completed_24h", 0) if _sla and _sla[0] else 0
        s_failed_24h = _sla[0].get("failed_24h", 0) if _sla and _sla[0] else 0
        s_stale_in_progress = _sla[0].get("stale_in_progress", 0) if _sla and _sla[0] else 0
        s_failed_without_reason = _sla[0].get("failed_without_reason", 0) if _sla and _sla[0] else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_metric_card(
                "Задачи",
                f"{o_tasks:,}",
                delta=f"в работе {o_in_progress} · pending {o_pending} · failed {o_failed}",
            )
        with c2:
            render_metric_card("Узлы знаний", f"{o_nodes:,}")
        with c3:
            render_metric_card("Эксперты", o_experts)
        with c4:
            _svc_color = (
                "var(--dash-success)"
                if o_services_ok == o_services_total
                else "var(--dash-warning)"
            )
            render_metric_card(
                "Сервисы",
                f"{o_services_ok}/{o_services_total}",
                delta="PG · MLX · Ollama",
                delta_color="normal" if o_services_ok == o_services_total else "inverse",
            )

        q1, q2, q3, q4 = st.columns(4)
        with q1:
            render_metric_card(
                "Completed 24h",
                f"{int(s_completed_24h):,}",
                delta=f"created {int(s_created_24h):,}",
            )
        with q2:
            render_metric_card(
                "Failed 24h",
                f"{int(s_failed_24h):,}",
                delta_color="inverse" if int(s_failed_24h) > 0 else "normal",
            )
        with q3:
            render_metric_card(
                "Stale in_progress",
                f"{int(s_stale_in_progress):,}",
                delta=">30m",
                delta_color="inverse" if int(s_stale_in_progress) > 0 else "normal",
            )
        with q4:
            render_metric_card(
                "Failed w/o reason",
                f"{int(s_failed_without_reason):,}",
                delta="contract",
                delta_color="inverse" if int(s_failed_without_reason) > 0 else "normal",
            )

        # Подсказка при устаревших данных (ТЗ: hint если метрики не приходят > 12 сек)
        _last_updated = fetch_data("SELECT MAX(updated_at) as t FROM tasks")
        _last_ts = (
            _last_updated[0]["t"]
            if _last_updated and _last_updated[0] and _last_updated[0].get("t")
            else None
        )
        if _last_ts:
            try:
                if _last_ts.tzinfo is None:
                    _last_ts = _last_ts.replace(tzinfo=timezone.utc)
                diff_sec = (datetime.now(timezone.utc) - _last_ts).total_seconds()
                if diff_sec > 12:
                    st.caption(
                        f"💾 Данные кэшируются. Последнее изменение задач: {int(diff_sec / 60)} мин назад. Нажмите 🔄 в шапке для актуальных цифр."
                    )
            except Exception:
                st.caption("💾 Кэш 60 с. Обновить: 🔄 в шапке.")
        else:
            st.caption("💾 Кэш 60 с. Обновить: 🔄 в шапке.")

        st.markdown("---")

        # Поиск и быстрый переход на одном ряду
        col_search, col_task = st.columns([3, 1])
        with col_search:
            search_query = st.text_input(
                "🔍 Поиск в базе знаний",
                placeholder="Тренды, практики, решения…",
                key="overview_search",
                label_visibility="collapsed",
            )
        with col_task:
            if st.button("📋 Поставить задачу", key="overview_put_task", width="stretch"):
                st.session_state.dashboard_section = "🛠️ Задачи и SLA"
                st.session_state["nav_section"] = "🛠️ Задачи и SLA"
                st.cache_data.clear()
                st.rerun()

        if search_query and len(search_query.strip()) >= 2:
            with st.spinner("Поиск..."):
                try:
                    embedding = get_embedding(search_query.strip())
                    results = search_knowledge_base(embedding)
                    if results:
                        for r in results:
                            similarity_pct = (r.get("similarity") or 0) * 100
                            color = (
                                "#58a6ff"
                                if similarity_pct > 80
                                else "#fab387"
                                if similarity_pct > 60
                                else "#8b949e"
                            )
                            content_preview = (r.get("content") or "")[:200] + (
                                "..." if len(r.get("content") or "") > 200 else ""
                            )
                            st.markdown(
                                f"""
                                <div style="background: #0d1117; padding: 12px; border-radius: 8px; border-left: 3px solid {color}; margin-bottom: 8px;">
                                    <div style="font-size: 11px; color: #8b949e;">{r.get("domain", "N/A")} · <strong style="color: {color};">{similarity_pct:.1f}%</strong></div>
                                    <div style="font-size: 13px; color: #c9d1d9; margin-top: 4px;">{content_preview}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                    else:
                        st.markdown(
                            """
                            <div class="empty-state">
                                <div class="empty-icon">🔍</div>
                                <div class="empty-title">Ничего не найдено</div>
                                <div class="empty-hint">Попробуйте другой запрос или проверьте, что база знаний заполнена (узлы с эмбеддингами).</div>
                            </div>
                        """,
                            unsafe_allow_html=True,
                        )
                except Exception as e:
                    st.error(f"Ошибка поиска: {e}")

        # --- ПУЛЬС КОРПОРАЦИИ (Дополнительные виджеты) ---
        st.markdown("### 💓 Пульс Корпорации")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            # Последние алерты безопасности
            try:
                threats = fetch_data(
                    "SELECT anomaly_type, severity, detected_at FROM anomaly_detection_logs WHERE detected_at > NOW() - INTERVAL '7 days' ORDER BY detected_at DESC LIMIT 3"
                )
                if threats:
                    st.markdown("**🛡️ Безопасность**")
                    for t in threats:
                        st.caption(
                            f"🚨 {t['anomaly_type']} ({t['severity']}) - {t['detected_at'].strftime('%H:%M')}"
                        )
                else:
                    st.success("🛡️ Угроз не обнаружено (7д)")
            except Exception as e:
                st.caption(f"🛡️ Безопасность: данные недоступны ({str(e)[:30]}...)")
        with col_p2:
            # Последние решения совета
            try:
                decisions = fetch_data(
                    f"""
                    SELECT content, created_at, metadata->>'type' as decision_type
                    FROM knowledge_nodes
                    WHERE metadata->>'type' IN ('board_decision', 'board_directive', 'board_consult')
                      AND {t_filter}
                    ORDER BY created_at DESC
                    LIMIT 3
                    """
                )
                if decisions:
                    st.markdown("**🏛️ Решения Совета**")
                    now_utc = datetime.now(timezone.utc)
                    for d in decisions:
                        created_at = d.get("created_at")
                        if created_at and created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)
                        age_hours = (
                            (now_utc - created_at).total_seconds() / 3600 if created_at else None
                        )
                        age_label = (
                            "🟢 свежо" if age_hours is not None and age_hours <= 24 else "🔴 >24ч"
                        )
                        st.caption(
                            f"📜 {d['content'][:50]}... ({d['created_at'].strftime('%d.%m')} · {age_label})"
                        )
                else:
                    st.info("🏛️ Решений совета нет")
            except Exception as e:
                st.caption(f"🏛️ Решения Совета: данные недоступны ({str(e)[:40]}...)")
        with col_p3:
            # Новое в AI Research
            try:
                latest_ai = fetch_data(
                    f"""
                    SELECT metadata->>'file_path' as path
                    FROM knowledge_nodes
                    WHERE domain_id = (SELECT id FROM domains WHERE name = 'AI Research')
                      AND {t_filter}
                      AND NULLIF(BTRIM(metadata->>'file_path'), '') IS NOT NULL
                      AND COALESCE(metadata->>'type', '') <> 'long_term_memory'
                      AND COALESCE(metadata->>'source', '') IN (
                          'external_docs_indexer',
                          'cognitive_code_indexer',
                          'scout_research',
                          'enhanced_scout_research',
                          'enhanced_scout_report'
                      )
                    ORDER BY created_at DESC
                    LIMIT 3
                    """
                )
                if latest_ai:
                    st.markdown("**📚 AI Research**")
                    for ai in latest_ai:
                        raw_path = ai.get("path") if isinstance(ai, dict) else None
                        file_name = raw_path.split("/")[-1] if raw_path else "unknown"
                        st.caption(f"📄 {file_name}")
                else:
                    ai_total = fetch_data(
                        """
                        SELECT COUNT(*) AS total FROM knowledge_nodes
                        WHERE domain_id = (SELECT id FROM domains WHERE name = 'AI Research')
                          AND NULLIF(BTRIM(metadata->>'file_path'), '') IS NOT NULL
                          AND COALESCE(metadata->>'source', '') IN (
                              'external_docs_indexer', 'cognitive_code_indexer',
                              'scout_research', 'enhanced_scout_research', 'enhanced_scout_report'
                          )
                        """
                    )
                    ai_total_count = ai_total[0]["total"] if ai_total else 0
                    st.caption("📚 Нет свежих curated AI Research за период")
                    st.caption(f"Curated документов в базе: {ai_total_count:,}")
            except Exception as e:
                st.caption(f"📚 AI Research: данные недоступны ({str(e)[:40]}...)")

        st.stop()

    elif "Wisdom" in st.session_state.get("dashboard_section", ""):
        from tabs.wisdom_tab import render_wisdom_tab

        render_wisdom_tab()
        st.stop()

    # Раздел «Задачи»: только 2 подвкладки (ленивая загрузка по DASHBOARD_OPTIMIZATION_PLAN)
    elif "Задачи" in st.session_state.get("dashboard_section", ""):
        from tabs.tasks_tab import render_tasks_tab

        render_tasks_tab()
        st.stop()

    elif "Стратегия" in st.session_state.get("dashboard_section", ""):
        from tabs.strategy_tab import render_strategy_tab

        render_strategy_tab()
        st.stop()

    elif "Интеллект" in st.session_state.get("dashboard_section", ""):
        from tabs.data_tab import render_data_tab

        render_data_tab()
        st.stop()

    elif "Инструменты" in st.session_state.get("dashboard_section", ""):
        from tabs.scout_tab import render_scout_tab

        render_scout_tab()
        st.stop()

    elif "Система" in st.session_state.get("dashboard_section", ""):
        from tabs.system_tab import render_system_tab

        render_system_tab()
        st.stop()

    else:
        st.warning("Выберите раздел в боковой панели слева.")
        st.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Критическая ошибка дашборда: {e}")
        st.code(traceback.format_exc())
        st.info("Попробуйте обновить страницу или обратитесь к администратору.")
