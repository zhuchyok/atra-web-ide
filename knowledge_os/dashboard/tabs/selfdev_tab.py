"""Вкладка 🧪 Self-Dev — витрина контура саморазработки.

Показывает: очередь dev_loop-задач, последние выполненные (с отчётами),
коммиты ветки auto/dev-loop и форму постановки задачи агенту-патчеру.
"""
import subprocess

import streamlit as st

from database_service import fetch_data, run_query

BRANCH = "auto/dev-loop"


def _branch_log() -> list:
    try:
        log = subprocess.run(
            ["git", "log", f"main..{BRANCH}", "--oneline", "--no-merges", "-15"],
            cwd="/app/project",
            capture_output=True,
            text=True,
            timeout=10,
        )
        return [l for l in log.stdout.strip().splitlines() if l]
    except Exception:
        return []


def render_selfdev_tab():
    st.header("🧪 Self-Dev — контур саморазработки")
    st.caption(
        "Цикл: задача (source=dev_loop) → Victoria генерирует diff → изолированный worktree "
        f"на ветке `{BRANCH}` → проверки → коммит. Merge в main — только по человеческому ревью."
    )

    tabs = st.tabs(["📋 Очередь и результаты", "🌿 Ветка auto/dev-loop", "➕ Поставить задачу агенту"])

    with tabs[0]:
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

    with tabs[1]:
        st.subheader(f"🌿 Коммиты ветки {BRANCH} (не в main)")
        commits = _branch_log()
        if commits:
            st.caption("Просмотреть diff: git diff main..auto/dev-loop")
            for c in commits:
                st.code(c, language=None)
        else:
            st.info("Ветка чиста относительно main — патчей пока нет.")

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
