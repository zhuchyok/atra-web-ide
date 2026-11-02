"""Вкладка 🧪 Self-Dev — витрина контура саморазработки.

Показывает: очередь dev_loop-задач, последние выполненные (с отчётами),
патчи на диске и форму постановки задачи агенту-патчеру.
"""
import json
from pathlib import Path

import streamlit as st

from database_service import fetch_data, run_query

BRANCH = "auto/dev-loop"
PATCH_DIR = Path("/app/project/logs/self_dev_patches")


def _load_patch_metas(limit: int = 10) -> list[dict]:
    if not PATCH_DIR.exists():
        return []
    rows = []
    for mf in sorted(PATCH_DIR.glob("*.json"))[-limit:]:
        try:
            meta = json.loads(mf.read_text())
        except Exception:
            continue
        meta["_stem"] = mf.stem
        rows.append(meta)
    return list(reversed(rows))


def render_selfdev_tab():
    st.header("🧪 Self-Dev — контур саморазработки")
    st.caption(
        "Цикл: задача (source=dev_loop) → Victoria генерирует diff → изолированный worktree "
        f"на ветке `{BRANCH}` → проверки → коммит. Merge в main — только по человеческому ревью."
    )

    tabs = st.tabs(["📋 Очередь и результаты", "🌿 Ветка auto/dev-loop", "➕ Поставить задачу агенту"])

    with tabs[0]:
        stats = fetch_data(
            """SELECT status, count(*) AS n FROM tasks
               WHERE metadata->>'source'='dev_loop'
                 AND created_at > NOW() - INTERVAL '30 days'
               GROUP BY 1"""
        )
        if stats:
            cols = st.columns(len(stats))
            for i, row in enumerate(stats):
                with cols[i]:
                    st.metric(row["status"], row["n"])
        else:
            st.caption("За 30 дней dev_loop-задач не было.")

        queue = fetch_data(
            """SELECT id, title, created_at FROM tasks
               WHERE metadata->>'source'='dev_loop' AND status='pending'
               ORDER BY created_at ASC LIMIT 20"""
        )
        st.subheader("⏳ Очередь (патчер заберёт при следующем запуске)")
        if queue:
            for q in queue:
                st.markdown(f"- **{q['title']}** — {q['created_at'].strftime('%d.%m %H:%M')}")
        else:
            st.info("Очередь пуста.")

        done = fetch_data(
            """SELECT title, status, result, updated_at FROM tasks
               WHERE metadata->>'source'='dev_loop' AND status <> 'pending'
               ORDER BY updated_at DESC LIMIT 10"""
        )
        st.subheader("🔁 Последние результаты")
        for d in done or []:
            icon = "✅" if d["status"] == "completed" else "❌"
            result = (d.get("result") or "")[:300]
            with st.expander(f"{icon} {d['title'][:80]} — {d['updated_at'].strftime('%d.%m %H:%M')}"):
                st.caption(result or "без отчёта")
        if not done:
            st.info("Выполненных dev_loop-задач пока нет.")

        _render_patches()

    with tabs[1]:
        _render_patches()
        st.caption(
            "git в образе dashboard не установлен — ветка не читается из контейнера. "
            "Источник истины для ревью: файлы в logs/self_dev_patches."
        )

    with tabs[2]:
        st.subheader("➕ Поставить задачу агенту-патчеру")
        st.caption(
            "Опиши маленькое изменение (файл-два). Агент сгенерирует патч, прогонит проверки "
            "и положит его в ветку на ревью. Запрещено: секреты, .env, CI, launchd, миграции БД."
        )
        with st.form("selfdev_task_form"):
            title = st.text_input("Название", placeholder="Например: добавить docstring в tabs/plan_cache.py")
            description = st.text_area(
                "Что сделать", placeholder="Подробно: какой файл, что изменить, как проверить..."
            )
            valid = bool(title.strip()) and bool(description.strip())
            submitted = st.form_submit_button("🧪 В очередь self-dev", type="primary", disabled=not valid)
            if submitted:
                if not valid:
                    st.error("Заполните название и описание")
                else:
                    ok = run_query(
                        """
                        INSERT INTO tasks (title, description, status, priority, metadata, project_context)
                        VALUES (%s, %s, 'pending', 'low', '{"source":"dev_loop"}', 'atra-web-ide')
                        """,
                        (title.strip(), description.strip()),
                    )
                    if ok:
                        st.success("✅ Задача поставлена в очередь self-dev — патчер заберёт её в течение 2 часов.")
                        st.cache_data.clear()
                    else:
                        st.error("Не удалось создать задачу")


def _render_patches():
    st.subheader("📦 Патчи на ревью (logs/self_dev_patches)")
    st.caption("Файлы — первоисточник (ветку могут трогать синхронизаторы). Применить: git am <файл.patch>")
    metas = _load_patch_metas()
    if metas:
        for meta in metas:
            with st.expander(f"🧪 {str(meta.get('title', '?'))[:80]} — {str(meta.get('created', ''))[:16]}"):
                st.caption(meta.get("report", ""))
                st.code(meta.get("_stem", "") + ".patch", language=None)
    else:
        st.info("Патчей пока нет.")
