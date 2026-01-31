#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор отчетов для тестов
"""

import os
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from scripts.test_utils import TestResult, TestStatus, ensure_directory, save_json_report
from scripts.test_config import REPORT_CONFIG, PROJECT_ROOT


def generate_markdown_report(results: List[TestResult], output_path: str = None) -> str:
    """Генерирует отчет в формате Markdown"""
    if output_path is None:
        output_path = os.path.join(
            REPORT_CONFIG["output_dir"],
            REPORT_CONFIG["markdown_report"]
        )
    
    # Подсчет статистики
    total = len(results)
    passed = sum(1 for r in results if r.status == TestStatus.PASS)
    failed = sum(1 for r in results if r.status == TestStatus.FAIL)
    warnings = sum(1 for r in results if r.status == TestStatus.WARNING)
    skipped = sum(1 for r in results if r.status == TestStatus.SKIP)
    
    # Группировка по категориям
    categories = {}
    for result in results:
        # Определяем категорию по имени теста
        category = "Общие"
        if "БД" in result.name or "база" in result.name.lower() or "database" in result.name.lower():
            category = "База данных"
        elif "файл" in result.name.lower() or "модуль" in result.name.lower() or "file" in result.name.lower():
            category = "Файлы и модули"
        elif "конфиг" in result.name.lower() or "config" in result.name.lower() or "окружение" in result.name.lower():
            category = "Конфигурация"
        elif "биржа" in result.name.lower() or "exchange" in result.name.lower():
            category = "Биржа"
        elif "лог" in result.name.lower() or "logging" in result.name.lower():
            category = "Логирование"
        elif "производительность" in result.name.lower() or "performance" in result.name.lower():
            category = "Производительность"
        elif "метрик" in result.name.lower() or "metric" in result.name.lower():
            category = "Метрики"
        
        if category not in categories:
            categories[category] = []
        categories[category].append(result)
    
    # Генерация Markdown
    markdown = []
    markdown.append("# ОТЧЕТ О ТЕСТИРОВАНИИ")
    markdown.append("")
    markdown.append(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    markdown.append(f"**Всего проверок:** {total}")
    markdown.append("")
    markdown.append("## Сводка")
    markdown.append("")
    markdown.append("| Статус | Количество | Процент |")
    markdown.append("|--------|-----------|---------|")
    markdown.append(f"| ✅ Успешно | {passed} | {passed/total*100:.1f}% |" if total > 0 else "| ✅ Успешно | 0 | 0% |")
    markdown.append(f"| ❌ Провалено | {failed} | {failed/total*100:.1f}% |" if total > 0 else "| ❌ Провалено | 0 | 0% |")
    markdown.append(f"| ⚠️  Предупреждения | {warnings} | {warnings/total*100:.1f}% |" if total > 0 else "| ⚠️  Предупреждения | 0 | 0% |")
    markdown.append(f"| ⏭️  Пропущено | {skipped} | {skipped/total*100:.1f}% |" if total > 0 else "| ⏭️  Пропущено | 0 | 0% |")
    markdown.append("")
    
    # Детали по категориям
    for category, category_results in categories.items():
        markdown.append(f"## {category}")
        markdown.append("")
        
        for result in category_results:
            status_icon = {
                TestStatus.PASS: "✅",
                TestStatus.FAIL: "❌",
                TestStatus.WARNING: "⚠️",
                TestStatus.SKIP: "⏭️"
            }
            icon = status_icon.get(result.status, "❓")
            
            markdown.append(f"### {icon} {result.name}")
            markdown.append("")
            markdown.append(f"**Статус:** {result.status.value}")
            markdown.append(f"**Сообщение:** {result.message}")
            
            if result.duration > 0:
                markdown.append(f"**Время выполнения:** {result.duration:.3f} с")
            
            if result.details:
                markdown.append("")
                markdown.append("**Детали:**")
                markdown.append("```json")
                import json
                markdown.append(json.dumps(result.details, indent=2, ensure_ascii=False))
                markdown.append("```")
            
            if result.metrics:
                markdown.append("")
                markdown.append("**Метрики:**")
                for key, value in result.metrics.items():
                    markdown.append(f"- {key}: {value}")
            
            if result.recommendations:
                markdown.append("")
                markdown.append("**Рекомендации:**")
                for rec in result.recommendations:
                    markdown.append(f"- {rec}")
            
            markdown.append("")
    
    # Проваленные проверки
    failed_results = [r for r in results if r.status == TestStatus.FAIL]
    if failed_results:
        markdown.append("## ❌ Проваленные проверки")
        markdown.append("")
        for result in failed_results:
            markdown.append(f"### {result.name}")
            markdown.append(f"- **Ошибка:** {result.message}")
            if result.recommendations:
                markdown.append("- **Рекомендации:**")
                for rec in result.recommendations:
                    markdown.append(f"  - {rec}")
            markdown.append("")
    
    # Предупреждения
    warning_results = [r for r in results if r.status == TestStatus.WARNING]
    if warning_results:
        markdown.append("## ⚠️  Предупреждения")
        markdown.append("")
        for result in warning_results:
            markdown.append(f"### {result.name}")
            markdown.append(f"- **Предупреждение:** {result.message}")
            markdown.append("")
    
    markdown_text = "\n".join(markdown)
    
    # Сохранение файла
    ensure_directory(os.path.dirname(output_path) if os.path.dirname(output_path) else ".")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    
    return markdown_text


def generate_console_report(results: List[TestResult]):
    """Выводит отчет в консоль"""
    from scripts.test_utils import print_test_summary
    print_test_summary(results)
    
    # Дополнительная информация
    print("\n" + "=" * 60)
    print("ДЕТАЛЬНАЯ ИНФОРМАЦИЯ")
    print("=" * 60)
    
    for result in results:
        if result.status != TestStatus.PASS:
            print(f"\n{result.name}:")
            print(f"  Статус: {result.status.value}")
            print(f"  Сообщение: {result.message}")
            if result.recommendations:
                print("  Рекомендации:")
                for rec in result.recommendations:
                    print(f"    - {rec}")


def generate_all_reports(results: List[TestResult], output_dir: str = None) -> Dict[str, str]:
    """Генерирует все типы отчетов"""
    if output_dir is None:
        output_dir = REPORT_CONFIG["output_dir"]
    
    ensure_directory(output_dir)
    
    reports = {}
    
    # JSON отчет
    json_path = os.path.join(output_dir, REPORT_CONFIG["json_report"])
    if save_json_report(results, json_path):
        reports["json"] = json_path
    
    # Markdown отчет
    markdown_path = os.path.join(output_dir, REPORT_CONFIG["markdown_report"])
    markdown_content = generate_markdown_report(results, markdown_path)
    reports["markdown"] = markdown_path
    
    # Консольный отчет
    if REPORT_CONFIG.get("console_output", True):
        generate_console_report(results)
        reports["console"] = "stdout"
    
    return reports


if __name__ == "__main__":
    # Тестирование генератора отчетов
    from scripts.test_utils import TestResult, TestStatus
    
    test_results = [
        TestResult(
            name="Тест 1",
            status=TestStatus.PASS,
            message="Успешно",
            duration=0.5
        ),
        TestResult(
            name="Тест 2",
            status=TestStatus.FAIL,
            message="Ошибка",
            recommendations=["Рекомендация 1", "Рекомендация 2"]
        )
    ]
    
    reports = generate_all_reports(test_results)
    print(f"\nОтчеты сгенерированы: {reports}")

