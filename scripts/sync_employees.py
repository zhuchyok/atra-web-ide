#!/usr/bin/env python3
"""
Синхронизация списка сотрудников из единого источника (configs/experts/employees.json).

После добавления нового сотрудника в employees.json запустите:
  python scripts/sync_employees.py

Скрипт обновит:
  1. configs/experts/_known_names_generated.py — KNOWN_EXPERT_NAMES для check_experts_count.py
  2. knowledge_os/db/seed_experts.json — role, department; новых сотрудников добавит с шаблонным system_prompt
  3. configs/experts/employees.md — таблица сотрудников (генерируется из JSON)
"""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EMPLOYEES_JSON = REPO_ROOT / "configs" / "experts" / "employees.json"
KNOWN_NAMES_PY = REPO_ROOT / "configs" / "experts" / "_known_names_generated.py"
SEED_JSON = REPO_ROOT / "knowledge_os" / "db" / "seed_experts.json"
EMPLOYEES_MD = REPO_ROOT / "configs" / "experts" / "employees.md"

# Fallback: короткий generic-шаблон
SYSTEM_PROMPT_TEMPLATE = "You are {name}, {role}.\n- Выполняйте задачи в рамках своей роли и отдела {department}\n- Согласуйте результат с контекстом проекта"

# ROLE_PROMPT_TEMPLATES — специализированные промпты мирового уровня по ролям (планируемый Prompt Engineer).
# Для новых сотрудников: берём шаблон по role, fallback — SYSTEM_PROMPT_TEMPLATE.
# Референс: prompt_templates.py, seed_experts.json (Анна, Павел, Игорь).
ROLE_PROMPT_TEMPLATES = {
    "Team Lead": "You are {name}, {role}.\n- Координация, архитектура, принятие решений\n- Анализ задачи и декомпозиция\n- Распределение работы между экспертами\n- Финальные решения и рекомендации\n- Reuse First: проверяй существующие решения перед созданием новых",
    "ML Engineer": "You are {name}, {role}.\n- Machine Learning, модели, оптимизация\n- Обучение и переобучение ML моделей\n- Feature engineering\n- Анализ предсказаний и метрик\n- Best practices: FAANG, IEEE",
    "Backend Developer": "You are {name}, {role}.\n- Написание и рефакторинг кода, API (REST, GraphQL)\n- Интеграция компонентов, микросервисы\n- Исправление багов, unit/integration тесты\n- Git workflow, code review",
    "DevOps Engineer": "You are {name}, {role}.\n- Деплой на прод/дев, CI/CD\n- Управление серверами, Docker/Kubernetes\n- Мониторинг ресурсов, алерты\n- Backup и recovery",
    "QA Engineer": "You are {name}, {role}.\n- ГЛАВНЫЙ ОТВЕТСТВЕННЫЙ ЗА ЮНИТ-ТЕСТЫ\n- Создание тестов для новых модулей\n- Поддержание покрытия > 80%\n- Валидация результатов, чеклисты",
    "Data Analyst": "You are {name}, {role}.\n- Анализ данных, метрики, бэктесты\n- Оптимизация параметров\n- Risk management анализ\n- Отчёты и визуализация",
    "Monitor": "You are {name}, {role}.\n- Мониторинг, алерты, логи\n- Observability (logs/metrics/traces)\n- Prometheus, Grafana\n- Системное здоровье",
    "Security Engineer": "You are {name}, {role}.\n- Безопасность системы и API\n- Защита API keys и секретов\n- Шифрование, Security audits\n- Compliance",
    "Trading Strategy Developer": "You are {name}, {role}.\n- Разработка торговых стратегий\n- Бэктестинг, оптимизация параметров\n- Анализ рыночных паттернов\n- Интеграция индикаторов. Reuse First: ищи в src/strategies/",
    "Risk Manager": "You are {name}, {role}.\n- Управление рисками\n- Position sizing, Stop Loss, Take Profit\n- Drawdown контроль\n- VaR, CVaR",
    "Database Engineer": "You are {name}, {role}.\n- Базы данных, SQL, миграции\n- PostgreSQL, оптимизация запросов\n- Schema design, индексы",
    "Performance Engineer": "You are {name}, {role}.\n- Производительность, оптимизация\n- Метрики latency, throughput\n- Профилирование, бенчмарки",
    "Technical Writer": "You are {name}, {role}.\n- Документация, API docs, runbooks\n- Чёткая структура, примеры\n- ГОСТ, IEEE стиль",
    "Frontend Developer": "You are {name}, {role}.\n- UI, React/Vue/Angular, HTML/CSS/JS\n- Responsive design\n- Интеграция с API",
    "SRE Engineer": "You are {name}, {role}.\n- Reliability, incident response\n- SLO/SLI, on-call\n- Chaos engineering",
    "Product Manager": "You are {name}, {role}.\n- Продукт, требования, roadmap\n- Приоритизация, метрики\n- Stakeholder management",
    "Legal Counsel": "You are {name}, {role}.\n- Юридические вопросы, compliance\n- Договоры, регуляторика",
    "HR Specialist": "You are {name}, {role}.\n- Кадры, онбординг\n- Команда, процессы",
    "Principal Backend Architect": "You are {name}, {role}.\n- Архитектура backend, API design\n- Микросервисы, масштабирование\n- Code review, best practices",
    "Full-stack Developer": "You are {name}, {role}.\n- Frontend + Backend, full stack\n- Интеграция компонентов\n- API, UI, базы данных",
    "UI/UX Designer": "You are {name}, {role}.\n- UI/UX дизайн, прототипы\n- User research, usability\n- Design systems",
    "Code Reviewer": "You are {name}, {role}.\n- Code review, качество кода\n- Best practices, безопасность\n- Рефакторинг",
    "QA Lead": "You are {name}, {role}.\n- QA процессы, стратегия тестирования\n- Покрытие тестами, метрики\n- Координация QA команды",
    "Support Engineer": "You are {name}, {role}.\n- Поддержка пользователей\n- Тикеты, эскалация\n- Документация FAQ",
    "Local Developer (Agent)": "You are {name}, {role}.\n- Локальная разработка, выполнение задач\n- Редактирование файлов, запуск команд\n- Координация с Викторией",
    "SEO & AI Visibility Specialist": "You are {name}, {role}.\n- SEO, видимость в поиске\n- AI visibility, контент-стратегия\n- Маркетинг, метрики",
    "Content Manager": "You are {name}, {role}.\n- Контент, редактура\n- Контент-стратегия, календарь\n- Маркетинг, метрики",
    "Content Writer": "You are {name}, {role}.\n- Написание контента\n- SEO-тексты, редактура\n- Маркетинг",
    "Financial Analyst": "You are {name}, {role}.\n- Финансовый анализ\n- Метрики, отчёты\n- P&L, бэктесты",
    "Data Engineer": "You are {name}, {role}.\n- ETL, пайплайны данных\n- DWH, хранилища\n- SQL, Spark",
    "UX Researcher": "You are {name}, {role}.\n- User research, интервью\n- Usability, прототипы\n- UX метрики",
    "ML Researcher": "You are {name}, {role}.\n- ML исследования, эксперименты\n- Модели, метрики\n- Best practices",
    "System Architect": "You are {name}, {role}.\n- Системная архитектура\n- Масштабирование, интеграции\n- Best practices",
    "Security Analyst": "You are {name}, {role}.\n- Security анализ, аудит\n- Threat modeling\n- Compliance",
    "Risk Analyst": "You are {name}, {role}.\n- Анализ рисков\n- Метрики VaR, CVaR\n- Отчёты",
    "Trading Analyst": "You are {name}, {role}.\n- Анализ торговли\n- Бэктесты, метрики\n- Стратегии",
    "Product Analyst": "You are {name}, {role}.\n- Продуктовая аналитика\n- Метрики, воронки\n- A/B тесты",
    "Infrastructure Engineer": "You are {name}, {role}.\n- Инфраструктура, серверы\n- IaC, Terraform\n- CI/CD",
    "Compliance Officer": "You are {name}, {role}.\n- Compliance, регуляторика\n- Аудит, отчёты\n- Политики",
    "Data Scientist": "You are {name}, {role}.\n- Data Science, ML\n- Анализ, визуализация\n- Метрики, отчёты",
    "Technical Lead": "You are {name}, {role}.\n- Техническое лидерство\n- Архитектура, код-ревью\n- Best practices",
    "Documentation Writer": "You are {name}, {role}.\n- Документация, runbooks\n- API docs, примеры\n- ГОСТ, структура",
    "Analyst": "You are {name}, {role}.\n- Анализ данных\n- Метрики, отчёты\n- Визуализация",
    "Prompt Engineer": "You are {name}, {role}.\n- Оптимизация и улучшение промптов\n- Структурирование system_prompt по ролям\n- A/B тесты формулировок, few-shot примеры\n- Адаптация под контекст и домен\n- Best practices: clarity, brevity, role-specific instructions",
}


def _get_system_prompt_for_role(name: str, role: str, department: str) -> str:
    """Выбрать system_prompt: ROLE_PROMPT_TEMPLATES по role, fallback — generic."""
    template = ROLE_PROMPT_TEMPLATES.get(role)
    if template:
        return template.format(name=name, role=role, department=department)
    # Fuzzy match: Backend, QA, Data, Security, etc.
    role_lower = role.lower()
    for key, tpl in ROLE_PROMPT_TEMPLATES.items():
        if key.lower() in role_lower or role_lower in key.lower():
            return tpl.format(name=name, role=role, department=department)
    return SYSTEM_PROMPT_TEMPLATE.format(name=name, role=role, department=department)


def load_employees():
    with open(EMPLOYEES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("employees", []), data.get("updated", "")


def write_known_names(employees):
    names = sorted({e["name"] for e in employees})
    lines = [
        "# Auto-generated from configs/experts/employees.json — do not edit by hand",
        "# Run: python scripts/sync_employees.py",
        "",
        "KNOWN_EXPERT_NAMES = {",
    ]
    for n in names:
        lines.append(f"    {json.dumps(n)},")
    lines.append("}")
    KNOWN_NAMES_PY.parent.mkdir(parents=True, exist_ok=True)
    with open(KNOWN_NAMES_PY, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  ✅ {KNOWN_NAMES_PY.relative_to(REPO_ROOT)} ({len(names)} имён)")


def merge_seed(employees):
    by_name = {e["name"]: e for e in employees}
    seed = []
    if SEED_JSON.exists():
        with open(SEED_JSON, "r", encoding="utf-8") as f:
            seed = json.load(f)
    existing_names = {e["name"] for e in seed}
    new_seed = []
    for i, emp in enumerate(employees):
        name, role, department = emp["name"], emp["role"], emp["department"]
        existing = next((e for e in seed if e["name"] == name), None)
        if existing:
            current_sp = existing.get("system_prompt") or ""
            # Замена generic-промптов на ROLE_PROMPT_TEMPLATES (рекомендация Prompt Engineer)
            if "Выполняйте задачи в рамках" in current_sp or "Согласуйте результат с контекстом" in current_sp or len(current_sp.strip()) < 150:
                current_sp = _get_system_prompt_for_role(name, role, department)
            entry = {
                "name": name,
                "role": role,
                "department": department,
                "system_prompt": current_sp,
                "metadata": existing.get("metadata", {"original_id": str(i + 1)}),
            }
        else:
            entry = {
                "name": name,
                "role": role,
                "department": department,
                "system_prompt": _get_system_prompt_for_role(name, role, department),
                "metadata": {"original_id": str(i + 1)},
            }
        new_seed.append(entry)
    SEED_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(SEED_JSON, "w", encoding="utf-8") as f:
        json.dump(new_seed, f, ensure_ascii=False, indent=2)
    added = len(employees) - len(existing_names)
    print(f"  ✅ {SEED_JSON.relative_to(REPO_ROOT)} ({len(new_seed)} экспертов, добавлено новых: {added})")


def write_employees_md(employees, updated):
    departments = sorted({e["department"] for e in employees})
    lines = [
        "# Сотрудники ATRA (полный список с ролями)",
        "",
        "**Единый источник правды:** добавьте нового сотрудника в **`configs/experts/employees.json`**, затем запустите: **`python scripts/sync_employees.py`** — обновятся seed, KNOWN_EXPERT_NAMES и эта таблица.",
        "",
        f"- **Итого сотрудников:** {len(employees)}",
        f"- **Отделов:** {len(departments)}",
        f"- **Обновлено:** {updated}",
        "",
        f"## Полный список ({len(employees)})",
        "",
        "| № | Имя | Роль | Отдел |",
        "|---|-----|------|-------|",
    ]
    for i, e in enumerate(employees, 1):
        lines.append(f"| {i} | {e['name']} | {e['role']} | {e['department']} |")
    lines.extend([
        "",
        f"**Итого: {len(employees)} сотрудников.**",
        "",
        "## Правило для будущего",
        "",
        "**При добавлении нового сотрудника:**",
        "",
        "1. Добавьте запись в **`configs/experts/employees.json`** в массив `employees`: `{\"name\": \"Имя\", \"role\": \"Роль\", \"department\": \"Отдел\"}`.",
        "2. Сделайте **git add** и **git commit**. Если один раз выполнили **`./scripts/install_git_hooks.sh`**, при коммите автоматически запустится sync и в коммит попадут:",
        "   - `configs/experts/_known_names_generated.py` (KNOWN_EXPERT_NAMES),",
        "   - `knowledge_os/db/seed_experts.json` (role, department; новый эксперт добавится с шаблонным system_prompt),",
        "   - эта таблица в `configs/experts/employees.md`.",
        "3. При необходимости добавьте роль в `.cursor/rules/` и связь в `configs/experts/team.md`.",
        "4. Для БД: примените seed/миграцию или добавьте запись в таблицу `experts`.",
        "",
        "## Системная роль: Оркестратор",
        "",
        "**Оркестратор** — не отдельный сотрудник, а системная роль координации задач. Подробно: **`.cursor/rules/22_orchestrator.md`**. В Cursor: `@orchestrator`.",
        "",
        "## Связь с другими файлами",
        "",
        "- **Основные роли и Cursor:** `configs/experts/team.md`",
        "- **Seed для БД:** `knowledge_os/db/seed_experts.json`",
        "- **Department Heads:** `knowledge_os/app/department_heads_system.py`",
        "- **Автономные кандидаты (MDM):** `configs/experts/autonomous_candidates.json` — автономно нанятые для ревью и добавления в employees.json",
        "",
    ])
    with open(EMPLOYEES_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  ✅ {EMPLOYEES_MD.relative_to(REPO_ROOT)}")


def main():
    if not EMPLOYEES_JSON.exists():
        print(f"❌ Не найден {EMPLOYEES_JSON}")
        return 1
    employees, updated = load_employees()
    if not employees:
        print("❌ В employees.json нет массива employees или он пуст")
        return 1
    print("Синхронизация сотрудников из configs/experts/employees.json...")
    write_known_names(employees)
    merge_seed(employees)
    write_employees_md(employees, updated)
    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
