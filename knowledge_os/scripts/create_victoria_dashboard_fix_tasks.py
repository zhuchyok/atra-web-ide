#!/usr/bin/env python3
"""
Создаёт в БД задачи для локальной Виктории: довести дашборд и все пункты аудита
до рабочего состояния без заглушек. Виктория сама решает, как реализовать.

Запуск:
  cd knowledge_os && .venv/bin/python scripts/create_victoria_dashboard_fix_tasks.py

Требуется: DATABASE_URL (или postgresql://admin:secret@localhost:5432/knowledge_os).
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@localhost:5432/knowledge_os",
)


TASK_UMBRELLA = """
Задача для локальной Виктории (агент): довести дашборд Knowledge OS и все пункты аудита до рабочего состояния без заглушек.

Источник: docs/audits/2026-03-11-dashboard-tabs-audit.md

Требования:
1. Все вкладки и подвкладки дашборда должны работать или показывать явное сообщение при отсутствии данных/таблиц (не падать и не скрывать ошибки голым except).
2. Без заглушек: реальные миграции для недостающих таблиц/колонок, реальная обработка ошибок, реальные импорты с fallback где нужно.
3. Самостоятельно продумать порядок и способ: миграции в db/migrations, правки в dashboard/tabs и app.py, при необходимости обновить CHANGES_FROM_OTHER_CHATS.md.

Конкретные пункты из аудита:
- Обзор → Пульс «Безопасность»: таблица anomaly_detection_logs (миграция или явная обработка отсутствия).
- Wisdom: добавить блок «Дебаты» (expert council) — запрос к knowledge_nodes по metadata->>'cycle' LIKE 'nightly_council%', вывод в UI.
- Стратегия → Финансы и ROI: колонки experts.virtual_budget и experts.performance_score — миграция ALTER TABLE experts ADD COLUMN IF NOT EXISTS.
- Инструменты → Симулятор: таблица simulations отсутствует в миграциях — добавить миграцию CREATE TABLE simulations (id, idea, result, created_at).
- Интеллект → Синтез Знаний: надёжный импорт VictoriaEnhanced (try from victoria_enhanced then from app.victoria_enhanced).
- Интеллект → Prompt Battle: убедиться, что миграция expert_mutations применена; при отсутствии — применить или обработать в UI.
- Code Mutations: пути к файлам в Docker — проверить и при необходимости исправить расчёт путей (WORKSPACE_ROOT, CORPORATION_ROOT).
- Система → Песочница/Самодиагностика: при недоступном backend или отсутствующих модулях — явное сообщение, не падение.

Итог: после выполнения каждая вкладка дашборда либо работает с реальными данными, либо показывает понятное сообщение (таблица недоступна, сервис недоступен). Никаких заглушек и тихих except.
"""


async def main():
    try:
        import asyncpg
    except ImportError:
        print("Требуется asyncpg: pip install asyncpg")
        return 1

    conn = await asyncpg.connect(DB_URL)
    try:
        victoria_id = await conn.fetchval(
            "SELECT id FROM experts WHERE name = $1 LIMIT 1", "Виктория"
        )
        if not victoria_id:
            print("В БД нет эксперта с именем 'Виктория'. Создайте эксперта или укажите другого.")
            return 1

        task_id = await conn.fetchval(
            """
            INSERT INTO tasks (
                title, description, status, priority,
                assignee_expert_id, creator_expert_id, metadata
            )
            VALUES ($1, $2, 'pending', 'urgent', $3, $3, $4)
            RETURNING id
            """,
            "🔧 [Victoria] Дашборд и аудит: всё в рабочий вид без заглушек",
            TASK_UMBRELLA.strip(),
            victoria_id,
            json.dumps(
                {
                    "source": "create_victoria_dashboard_fix_tasks",
                    "audit_doc": "docs/audits/2026-03-11-dashboard-tabs-audit.md",
                    "assignee_hint": "Виктория",
                }
            ),
        )
        print(f"Создана задача для Виктории: id={task_id}")
        print("Описание: довести дашборд и все пункты аудита до рабочего состояния без заглушек.")
        print("Локальная Виктория (Smart Worker или ручной запуск) подхватит задачу из очереди.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
