#!/usr/bin/env python3
"""
Система отслеживания прогресса команды
"""

import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def check_filter_logging():
    """Проверяет, работает ли логирование фильтров"""
    try:
        conn = sqlite3.connect("trading.db")
        cursor = conn.cursor()

        # Проверяем записи за последний час
        since = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("SELECT COUNT(*) FROM filter_checks WHERE created_at >= ?", (since,))
        count = cursor.fetchone()[0]

        conn.close()
        return {
            "status": "✅" if count > 0 else "❌",
            "count": count,
            "message": f"Записей в filter_checks за последний час: {count}",
        }
    except Exception as e:
        return {"status": "❌", "count": 0, "message": f"Ошибка: {e}"}


def check_quality_score():
    """Проверяет, записывается ли quality_score"""
    try:
        conn = sqlite3.connect("trading.db")
        cursor = conn.cursor()

        # Проверяем записи за последние 24 часа
        since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN quality_score > 0 THEN 1 END) as with_score,
                AVG(quality_score) as avg_score
            FROM signals_log
            WHERE created_at >= ? AND quality_score IS NOT NULL
        """,
            (since,),
        )

        row = cursor.fetchone()
        total, with_score, avg_score = row

        conn.close()

        if total == 0:
            return {"status": "⚠️", "message": "Нет сигналов за последние 24 часа"}

        score_rate = (with_score / total * 100) if total > 0 else 0

        if score_rate > 50 and avg_score and avg_score > 0:
            return {
                "status": "✅",
                "message": f"quality_score работает: {score_rate:.1f}% сигналов имеют score, средний: {avg_score:.2f}",
            }
        else:
            return {
                "status": "❌",
                "message": f"quality_score не работает: только {score_rate:.1f}% имеют score > 0, средний: {avg_score or 0:.2f}",
            }
    except Exception as e:
        return {"status": "❌", "message": f"Ошибка: {e}"}


def check_code_changes():
    """Проверяет наличие изменений в коде"""
    try:
        # Проверяем наличие файла логирования фильтров
        filter_logger = Path("src/utils/filter_logger.py")
        has_logger = filter_logger.exists()

        # Проверяем изменения в signal_live.py
        result = subprocess.run(
            ["git", "log", "--oneline", "--since=7 days ago", "--", "signal_live.py"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        has_signal_changes = len(result.stdout.strip()) > 0

        return {
            "filter_logger": {
                "status": "✅" if has_logger else "❌",
                "message": f"filter_logger.py: {'существует' if has_logger else 'не найден'}",
            },
            "signal_changes": {
                "status": "✅" if has_signal_changes else "⚠️",
                "message": f"signal_live.py: {'изменен' if has_signal_changes else 'не изменен за неделю'}",
            },
        }
    except Exception as e:
        return {"error": str(e)}


def check_tests():
    """Проверяет наличие тестов"""
    test_files = [
        Path("tests/test_filter_logging.py"),
        Path("tests/test_quality_score.py"),
        Path("scripts/test_filter_logging.py"),
        Path("scripts/test_quality_score.py"),
    ]

    found_tests = []
    for test_file in test_files:
        if test_file.exists():
            found_tests.append(str(test_file))

    return {
        "status": "✅" if found_tests else "❌",
        "tests": found_tests,
        "message": f"Найдено тестов: {len(found_tests)}",
    }


def check_reports():
    """Проверяет наличие обновленных отчетов"""
    report_files = [
        Path("scripts/full_signal_report.py"),
        Path("scripts/reports/full_signal_report.md"),
    ]

    found_reports = []
    for report_file in report_files:
        if report_file.exists():
            found_reports.append(str(report_file))

    return {
        "status": "✅" if found_reports else "❌",
        "reports": found_reports,
        "message": f"Найдено отчетов: {len(found_reports)}",
    }


def generate_progress_report():
    """Генерирует отчет о прогрессе команды"""
    report = []
    report.append("=" * 80)
    report.append("📊 ОТЧЕТ О ПРОГРЕССЕ КОМАНДЫ")
    report.append("=" * 80)
    report.append(f"Время проверки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # 1. Логирование фильтров
    report.append("=" * 80)
    report.append("1. ЛОГИРОВАНИЕ ФИЛЬТРОВ (Сотрудник 2)")
    report.append("=" * 80)
    filter_check = check_filter_logging()
    report.append(f"{filter_check['status']} {filter_check['message']}")
    report.append("")

    # 2. Quality Score
    report.append("=" * 80)
    report.append("2. QUALITY_SCORE (Сотрудник 3)")
    report.append("=" * 80)
    quality_check = check_quality_score()
    report.append(f"{quality_check['status']} {quality_check['message']}")
    report.append("")

    # 3. Изменения в коде
    report.append("=" * 80)
    report.append("3. ИЗМЕНЕНИЯ В КОДЕ")
    report.append("=" * 80)
    code_check = check_code_changes()
    if "error" not in code_check:
        report.append(
            f"{code_check['filter_logger']['status']} {code_check['filter_logger']['message']}"
        )
        report.append(
            f"{code_check['signal_changes']['status']} {code_check['signal_changes']['message']}"
        )
    else:
        report.append(f"❌ Ошибка: {code_check['error']}")
    report.append("")

    # 4. Тесты
    report.append("=" * 80)
    report.append("4. ТЕСТЫ (Сотрудник 4)")
    report.append("=" * 80)
    tests_check = check_tests()
    report.append(f"{tests_check['status']} {tests_check['message']}")
    if tests_check["tests"]:
        for test in tests_check["tests"]:
            report.append(f"   - {test}")
    report.append("")

    # 5. Отчеты
    report.append("=" * 80)
    report.append("5. ОТЧЕТЫ (Сотрудник 5)")
    report.append("=" * 80)
    reports_check = check_reports()
    report.append(f"{reports_check['status']} {reports_check['message']}")
    if reports_check["reports"]:
        for rep in reports_check["reports"]:
            report.append(f"   - {rep}")
    report.append("")

    # Общий статус
    report.append("=" * 80)
    report.append("ОБЩИЙ СТАТУС")
    report.append("=" * 80)

    all_checks = [
        filter_check["status"],
        quality_check["status"],
        tests_check["status"],
        reports_check["status"],
    ]

    if all(status == "✅" for status in all_checks):
        report.append("✅ ВСЕ ЗАДАЧИ ВЫПОЛНЕНЫ!")
    elif any(status == "✅" for status in all_checks):
        report.append("🟡 ВЫПОЛНЕНО ЧАСТИЧНО")
    else:
        report.append("❌ ЗАДАЧИ НЕ ВЫПОЛНЕНЫ")

    report.append("")

    return "\n".join(report)


if __name__ == "__main__":
    report = generate_progress_report()
    print(report)

    # Сохраняем в файл
    report_file = Path("scripts/reports/team_progress_report.md")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report, encoding="utf-8")
    print(f"\n✅ Отчет сохранен в {report_file}")
