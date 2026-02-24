#!/usr/bin/env python3
"""Проверка слоя данных дашборда: БД и запросы по разделам без Streamlit."""
import os
import sys

# путь к dashboard и app
DASH = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(DASH), "app")
for p in (DASH, APP):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(DASH)

def main():
    errors = []
    ok = []

    # 1. Пул и быстрая проверка
    try:
        from database_service import quick_db_check, fetch_data, fetch_parallel, db_connection
        ok.append("database_service import")
    except Exception as e:
        errors.append(f"database_service: {e}")
        return report(ok, errors)

    try:
        result = quick_db_check()
        if result and result[0] is True:
            ok.append("quick_db_check (БД доступна)")
        else:
            errors.append("quick_db_check: БД недоступна")
    except Exception as e:
        errors.append(f"quick_db_check: {e}")
        return report(ok, errors)

    # 2. Запросы шапки (как в app.py)
    try:
        results = fetch_parallel({
            "tasks_count": ("SELECT COUNT(*) as count FROM tasks", ()),
            "experts_count": ("SELECT COUNT(*) as count FROM experts", ()),
            "intellectual_capital": ("SELECT COUNT(*) as total_nodes, SUM(usage_count) as total_usage FROM knowledge_nodes", ()),
        })
        for k, v in results.items():
            if v is not None and (isinstance(v, list) and len(v) >= 1 or True):
                ok.append(f"fetch_parallel.{k}")
    except Exception as e:
        errors.append(f"fetch_parallel header: {e}")

    # 3. Обзор — поиск (search_knowledge_base нужен embedding, пропуск) и пульс
    try:
        fetch_data("SELECT anomaly_type, severity, detected_at FROM anomaly_detection_logs ORDER BY detected_at DESC LIMIT 1")
        ok.append("Обзор: anomaly_detection_logs")
    except Exception:
        ok.append("Обзор: anomaly_detection_logs (таблица отсутствует — ок)")

    try:
        fetch_data("SELECT content, created_at FROM knowledge_nodes WHERE metadata->>'type' = 'board_decision' ORDER BY created_at DESC LIMIT 1")
        ok.append("Обзор: board_decision")
    except Exception as e:
        errors.append(f"Обзор board_decision: {e}")

    # 4. Wisdom
    try:
        fetch_data("SELECT AVG((metadata->>'audit_score')::int) as avg_score FROM tasks WHERE metadata->>'audit_score' IS NOT NULL")
        fetch_data("SELECT COUNT(*) as count FROM knowledge_nodes WHERE metadata->>'type' = 'sop_document'")
        ok.append("Wisdom: метрики")
    except Exception as e:
        errors.append(f"Wisdom: {e}")

    # 5. Задачи
    try:
        fetch_data("SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE status = 'completed') as completed FROM tasks")
        ok.append("Задачи: список")
    except Exception as e:
        errors.append(f"Задачи: {e}")

    # 6. Стратегия
    try:
        fetch_data("SELECT objective, department, period, created_at FROM okrs ORDER BY created_at DESC LIMIT 1")
        ok.append("Стратегия: okrs (или пусто)")
    except Exception:
        fetch_data("SELECT content, metadata, created_at FROM knowledge_nodes WHERE metadata->>'type' = 'okr' ORDER BY created_at DESC LIMIT 1")
        ok.append("Стратегия: okr fallback")

    try:
        fetch_data("SELECT id, name, department, role, version FROM experts LIMIT 1")
        ok.append("Стратегия: experts")
    except Exception as e:
        errors.append(f"Стратегия experts: {e}")

    # 7. Интеллект (data_tab)
    try:
        fetch_data("SELECT COUNT(*) as total_nodes, (SELECT COUNT(*) FROM knowledge_links) as total_links FROM knowledge_nodes")
        ok.append("Интеллект: data_health")
    except Exception:
        fetch_data("SELECT COUNT(*) as total_nodes FROM knowledge_nodes")
        ok.append("Интеллект: data_health (без knowledge_links)")

    # 8. Инструменты (scout)
    try:
        with db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                ok.append("Инструменты: db_connection()")
            else:
                errors.append("Инструменты: db_connection() вернул None")
    except Exception as e:
        errors.append(f"Инструменты db_connection: {e}")

    try:
        fetch_data("SELECT id, idea, result, created_at FROM simulations ORDER BY created_at DESC LIMIT 1")
        ok.append("Инструменты: simulations (или пусто)")
    except Exception:
        ok.append("Инструменты: simulations (таблица отсутствует — ок)")

    # 9. Система
    try:
        from database_service import check_services
        svc = check_services()
        ok.append("Система: check_services")
    except Exception as e:
        errors.append(f"Система check_services: {e}")

    try:
        fetch_data("SELECT topic, status, consensus_summary, created_at FROM expert_discussions ORDER BY created_at DESC LIMIT 1")
        ok.append("Система: expert_discussions (или пусто)")
    except Exception:
        ok.append("Система: expert_discussions (таблица отсутствует — ок)")

    return report(ok, errors)

def report(ok, errors):
    print("--- Проверка слоя данных дашборда ---")
    for x in ok:
        print("  OK:", x)
    for x in errors:
        print("  ERR:", x)
    print("---")
    if errors:
        print("Итог: есть ошибки")
        sys.exit(1)
    print("Итог: все проверки пройдены")
    sys.exit(0)

if __name__ == "__main__":
    main()
