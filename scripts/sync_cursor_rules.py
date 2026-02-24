#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматическая синхронизация .cursor/rules/ при изменениях в БД экспертов.

Триггеры:
- Найм (INSERT в experts)
- Увольнение (DELETE из experts)
- Изменение данных (UPDATE experts)
- Объединение ролей

Использование:
1. Вручную: python3 scripts/sync_cursor_rules.py
2. Авто: запускается при изменениях в employees.json
3. Webhook: при изменениях в БД

Работает БЕЗ подключения к БД - только на основе employees.json!
"""

import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
RULES_DIR = PROJECT_ROOT / ".cursor" / "rules"
EMPLOYEES_JSON = PROJECT_ROOT / "configs" / "experts" / "employees.json"

# Расширенные шаблоны для разных ролей
ROLE_TEMPLATES = {
    "Team Lead": {
        "emoji": "👑",
        "responsibilities": """- Координация команды экспертов
- Декомпозиция сложных задач
- Распределение работы по компетенциям
- Контроль качества и сроков
- Финальное утверждение результатов""",
        "tech_stack": """```
Leadership:
├── Team Management
├── Task Decomposition
├── Priority Setting
└── Decision Making
```""",
        "processes": "1. Анализ задачи\n2. Декомпозиция\n3. Распределение\n4. Мониторинг\n5. Контроль качества",
        "interactions": "- Все члены команды\n- Product Manager\n- Stakeholders",
        "example_prompt": "Распредели задачу между экспертами: [описание задачи]",
        "quality_criteria": "- Task completion > 90%\n- On-time delivery > 85%\n- Team satisfaction > 4/5"
    },

    "Backend Developer": {
        "emoji": "💻",
        "responsibilities": """- Разработка REST/GraphQL API
- Микросервисная архитектура
- Интеграция с базами данных
- Асинхронная обработка
- Unit и integration тестирование""",
        "tech_stack": """```python
# Core
Python 3.11+
FastAPI / Django
asyncio / aiohttp

# Data
SQLAlchemy / asyncpg
Redis / Celery

# Testing
pytest / pytest-asyncio
```""",
        "processes": "1. API design\n2. Implementation\n3. Testing\n4. Code review\n5. Deployment",
        "interactions": "- Frontend team\n- DevOps\n- QA\n- Database engineers",
        "example_prompt": "Создай REST API endpoint для управления ордерами с валидацией и тестами",
        "quality_criteria": "- Test coverage >= 80%\n- Type hints (mypy strict)\n- Code review approved\n- Documentation complete"
    },

    "Frontend Developer": {
        "emoji": "🎨",
        "responsibilities": """- Разработка UI компонентов
- State management
- Performance optimization
- Responsive design
- Accessibility (a11y)""",
        "tech_stack": """```typescript
// Core
React 18+ / Next.js
TypeScript 5.x
TailwindCSS

// State
Zustand / TanStack Query

// Testing
Vitest / Playwright
```""",
        "processes": "1. Component design\n2. Implementation\n3. Testing\n4. Accessibility check\n5. Performance audit",
        "interactions": "- Backend team\n- UI/UX designers\n- QA\n- Product Manager",
        "example_prompt": "Создай responsive компонент для отображения портфеля с real-time обновлениями",
        "quality_criteria": "- Lighthouse score >= 90\n- WCAG 2.1 AA\n- Mobile-friendly\n- Test coverage >= 80%"
    },

    "Full-stack Developer": {
        "emoji": "🔧",
        "responsibilities": """- End-to-end разработка функционала
- Backend API + Frontend UI
- Real-time features
- Full feature ownership
- Rapid prototyping""",
        "tech_stack": """```typescript
// Full-stack
Next.js 14 (App Router)
tRPC / GraphQL
Prisma ORM
PostgreSQL / Redis
```""",
        "processes": "1. Feature design\n2. Backend + Frontend\n3. Integration\n4. E2E testing\n5. Deployment",
        "interactions": "- Product team\n- Design team\n- DevOps",
        "example_prompt": "Реализуй фичу [название] от API до UI с тестами",
        "quality_criteria": "- Full-stack tests\n- Type-safe end-to-end\n- Performance optimized"
    },

    "DevOps Engineer": {
        "emoji": "🔧",
        "responsibilities": """- CI/CD пайплайны
- Kubernetes deployment
- Infrastructure as Code
- Monitoring и alerting
- Автоматизация""",
        "tech_stack": """```yaml
Orchestration: Kubernetes, Helm
CI/CD: GitLab CI, ArgoCD
IaC: Terraform, Pulumi
Monitoring: Prometheus, Grafana
```""",
        "processes": "1. Pipeline setup\n2. Infrastructure code\n3. Deployment automation\n4. Monitoring setup\n5. Optimization",
        "interactions": "- Development teams\n- SRE\n- Infrastructure\n- Security",
        "example_prompt": "Настрой CI/CD для нового микросервиса с auto-deployment в staging",
        "quality_criteria": "- Deployment time < 15 min\n- Zero-downtime deploys\n- Infrastructure as Code 100%"
    },

    "ML Engineer": {
        "emoji": "🤖",
        "responsibilities": """- ML models в production
- Feature engineering
- Model serving
- A/B тестирование моделей
- MLOps автоматизация""",
        "tech_stack": """```python
# ML
PyTorch / TensorFlow
scikit-learn / XGBoost

# MLOps
MLflow / Weights & Biases
ONNX / TensorRT
```""",
        "processes": "1. Feature engineering\n2. Model training\n3. Validation\n4. Deployment\n5. Monitoring",
        "interactions": "- Data Scientists\n- ML Researchers\n- Backend team\n- DevOps",
        "example_prompt": "Создай ML pipeline для предсказания оттока с автоматическим retraining",
        "quality_criteria": "- Model AUC >= 0.7\n- Inference latency < 50ms\n- Data drift monitored"
    },

    "QA Engineer": {
        "emoji": "🧪",
        "responsibilities": """- Тестирование функционала
- Автоматизация тестов
- Bug reporting
- Regression testing
- Test documentation""",
        "tech_stack": """```python
# Automation
pytest / Playwright
selenium

# API
httpx / tavern

# Tools
Allure / TestRail
```""",
        "processes": "1. Test planning\n2. Test case creation\n3. Execution\n4. Bug reporting\n5. Regression",
        "interactions": "- Developers\n- QA Lead\n- Product Manager",
        "example_prompt": "Напиши автотесты для API endpoint с покрытием edge cases",
        "quality_criteria": "- Test coverage >= 80%\n- Automation ratio >= 70%\n- Bug escape rate < 5%"
    },

    "Data Analyst": {
        "emoji": "📊",
        "responsibilities": """- Анализ бизнес-данных
- Построение отчетов
- SQL-запросы
- Дашборды
- A/B тестирование""",
        "tech_stack": """```python
import pandas as pd
import numpy as np
import plotly.express as px

# SQL & BI
PostgreSQL
Metabase / Tableau
```""",
        "processes": "1. Сбор данных\n2. Очистка\n3. Анализ\n4. Визуализация\n5. Инсайты",
        "interactions": "- Product Manager\n- Data Scientists\n- Business teams",
        "example_prompt": "Проанализируй конверсию воронки и найди узкие места",
        "quality_criteria": "- Data validated\n- Statistical significance\n- Actionable insights"
    },

    "Product Manager": {
        "emoji": "📦",
        "responsibilities": """- Product strategy
- Requirements gathering
- Roadmap planning
- Stakeholder management
- Metrics definition""",
        "tech_stack": """```
Tools:
├── Jira / Linear
├── Figma (mockups)
├── Analytics (Mixpanel)
└── Documentation (Notion)
```""",
        "processes": "1. Discovery\n2. Requirements\n3. Prioritization\n4. Execution\n5. Measurement",
        "interactions": "- Engineering\n- Design\n- Business\n- Users",
        "example_prompt": "Напиши PRD для новой фичи с user stories и acceptance criteria",
        "quality_criteria": "- Requirements clear\n- Metrics defined\n- Stakeholders aligned"
    },

    "UI/UX Designer": {
        "emoji": "🎨",
        "responsibilities": """- Product design
- User research
- Prototyping
- Design system
- Usability testing""",
        "tech_stack": """```
Design:
- Figma
- Adobe XD
- Sketch

Prototyping:
- Framer
- Principle
```""",
        "processes": "1. Research\n2. Wireframes\n3. Design\n4. Prototype\n5. User testing",
        "interactions": "- Product Manager\n- Frontend team\n- UX Researcher",
        "example_prompt": "Спроектируй UX для нового dashboard с фокусом на usability",
        "quality_criteria": "- User-tested\n- Accessibility compliant\n- Design system consistent"
    },

    "Principal AI Coordination Architect": {
        "emoji": "🤖",
        "responsibilities": """- AI Agent координация и оркестрация
- Multi-agent system design
- Inter-agent communication protocols
- Task delegation стратегии
- AI workflow optimization""",
        "tech_stack": """```python
# Agent Systems
LangChain / AutoGPT
Custom Agent Frameworks

# Coordination
Message Queues (Redis, RabbitMQ)
Event-driven Architecture

# AI/ML
LLMs (GPT-4, Claude, Llama)
Vector DBs (Pinecone, Weaviate)
```""",
        "processes": "1. Agent system design\n2. Communication protocol\n3. Task distribution\n4. Monitoring & optimization\n5. Fallback mechanisms",
        "interactions": "- ML Engineers\n- Backend team\n- Product Manager\n- Other AI Architects",
        "example_prompt": "Спроектируй multi-agent систему для автоматизации code review с fallback механизмами",
        "quality_criteria": "- Agent uptime > 99%\n- Task completion > 95%\n- Response time < 5s\n- Graceful degradation"
    },

    "Team Lead": {
        "emoji": "👑",
        "responsibilities": """- Координация команды экспертов
- Декомпозиция сложных задач
- Распределение работы по компетенциям
- Контроль качества и сроков
- Финальное утверждение результатов""",
        "tech_stack": """```
Leadership:
├── Team Management
├── Task Decomposition
├── Priority Setting
└── Decision Making
```""",
        "processes": "1. Анализ задачи\n2. Декомпозиция\n3. Распределение\n4. Мониторинг\n5. Контроль качества",
        "interactions": "- Все члены команды\n- Product Manager\n- Stakeholders",
        "example_prompt": "Распредели задачу между экспертами: [описание задачи]",
        "quality_criteria": "- Task completion > 90%\n- On-time delivery > 85%\n- Team satisfaction > 4/5"
    },

    "Local Developer (Agent)": {
        "emoji": "💻",
        "responsibilities": """- Локальная разработка и тестирование
- Quick prototyping
- Code execution в изолированной среде
- Debugging и troubleshooting
- Integration testing""",
        "tech_stack": """```python
# Development
Python, JavaScript, Go
Docker для изоляции

# Testing
pytest, Jest
Local testing frameworks

# AI Integration
Agent SDK
API clients
```""",
        "processes": "1. Получение задачи\n2. Local development\n3. Testing\n4. Feedback\n5. Integration",
        "interactions": "- Victoria (Team Lead)\n- Remote agents\n- CI/CD system",
        "example_prompt": "Протестируй локально новый API endpoint с edge cases",
        "quality_criteria": "- Tests pass locally\n- No breaking changes\n- Documentation updated"
    },

    "Chief Knowledge Officer": {
        "emoji": "🧠",
        "responsibilities": """- Knowledge management стратегия
- База знаний архитектура
- Knowledge graph дизайн
- Learning systems оптимизация
- Информационные потоки""",
        "tech_stack": """```python
# Knowledge Systems
PostgreSQL + pgvector
Neo4j / Graph DBs
Elasticsearch

# AI/ML
Embedding models
RAG systems
LLM integration
```""",
        "processes": "1. Knowledge audit\n2. System design\n3. Implementation\n4. Optimization\n5. Monitoring",
        "interactions": "- CTO\n- Data Engineers\n- ML Engineers\n- All departments",
        "example_prompt": "Разработай knowledge graph для корпоративной базы знаний с векторным поиском",
        "quality_criteria": "- Search recall > 90%\n- Response time < 200ms\n- Knowledge freshness < 1h"
    },

    "CEO / Executive Director": {
        "emoji": "🎯",
        "responsibilities": """- Стратегическое видение
- Принятие ключевых решений
- Stakeholder management
- Финансовые цели
- Развитие бизнеса""",
        "tech_stack": """```
Business:
├── Strategic Planning
├── Financial Management
├── Leadership
└── Vision Setting
```""",
        "processes": "1. Vision & Strategy\n2. Resource allocation\n3. Decision making\n4. Performance monitoring\n5. Course correction",
        "interactions": "- Board of Directors\n- C-level executives\n- Key stakeholders\n- All departments",
        "example_prompt": "Проанализируй Q4 результаты и предложи стратегию на следующий год",
        "quality_criteria": "- Revenue targets met\n- Strategic goals achieved\n- Team satisfaction > 4/5"
    },

    "Trading Strategy Developer": {
        "emoji": "📈",
        "responsibilities": """- Разработка торговых стратегий
- Backtesting и оптимизация
- Risk management
- Market analysis
- Performance monitoring""",
        "tech_stack": """```python
# Trading
import pandas as pd
import numpy as np
from backtesting import Strategy

# Analytics
Technical indicators
Statistical analysis
ML models
```""",
        "processes": "1. Strategy design\n2. Backtesting\n3. Optimization\n4. Paper trading\n5. Live deployment",
        "interactions": "- Quant Developers\n- Risk Manager\n- Trading Analysts\n- Chief Trading Strategist",
        "example_prompt": "Создай и протестируй mean-reversion стратегию для крипто рынка",
        "quality_criteria": "- Sharpe ratio > 1.5\n- Max drawdown < 20%\n- Win rate > 55%"
    },

    "M&A Analyst": {
        "emoji": "💼",
        "responsibilities": """- M&A возможности анализ
- Due diligence
- Valuation models
- Integration planning
- Deal structuring""",
        "tech_stack": """```
Valuation:
- DCF models
- Comparable analysis
- Excel financial modeling

Research:
- Market research
- Competitive analysis
- Financial statement analysis
```""",
        "processes": "1. Target identification\n2. Valuation\n3. Due diligence\n4. Deal structuring\n5. Integration",
        "interactions": "- CEO\n- CFO\n- Legal team\n- Investment banks",
        "example_prompt": "Проведи оценку target company для потенциального приобретения",
        "quality_criteria": "- Valuation accuracy\n- Due diligence completeness\n- Integration plan quality"
    },
}

# Дефолтный шаблон для неизвестных ролей
DEFAULT_TEMPLATE = {
    "emoji": "👤",
    "responsibilities": """- Основная деятельность по роли
- Специализированные задачи
- Координация с командой
- Достижение целей""",
    "tech_stack": "```\nИнструменты и технологии роли\n```",
    "processes": "1. Анализ задачи\n2. Планирование\n3. Выполнение\n4. Контроль качества\n5. Отчетность",
    "interactions": "- Команда проекта\n- Смежные роли\n- Stakeholders",
    "example_prompt": "Выполни задачу в рамках своей роли",
    "quality_criteria": "- Качество работы\n- Соблюдение сроков\n- Документирование"
}


TEMPLATE = """---
description: "{name} - {role}"
alwaysApply: true
priority: {priority}
---

# {emoji} {name_upper} - {role_upper}

## 🎯 ОСНОВНЫЕ ОБЯЗАННОСТИ
{responsibilities}

## 🔧 ТЕХНИЧЕСКИЙ СТЕК / КОМПЕТЕНЦИИ
{tech_stack}

## 📋 КЛЮЧЕВЫЕ ПРОЦЕССЫ
{processes}

## 🎪 ВЗАИМОДЕЙСТВИЕ С ДРУГИМИ РОЛЯМИ
{interactions}

## 💡 ПРИМЕРЫ ПРОМПТОВ

```
@{name} {example_prompt}
```

## ✅ КРИТЕРИИ КАЧЕСТВА
```
{quality_criteria}
```

---
*Автоматически сгенерировано: {timestamp}*
*Источник: employees.json*
"""


def normalize_filename(name: str) -> str:
    """Нормализовать имя для имени файла."""
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }

    normalized = name.lower()
    for ru, en in translit.items():
        normalized = normalized.replace(ru, en)

    # Заменяем пробелы и спецсимволы
    normalized = normalized.replace(" ", "_").replace("/", "_").replace("&", "and")

    # Убираем множественные underscore
    while "__" in normalized:
        normalized = normalized.replace("__", "_")

    return normalized.strip("_")


def load_employees_json() -> List[Dict]:
    """Загрузить список из employees.json."""
    if EMPLOYEES_JSON.exists():
        with open(EMPLOYEES_JSON) as f:
            data = json.load(f)
            return data.get("employees", [])
    return []


def get_template_for_role(role: str) -> Dict:
    """Получить шаблон для роли."""
    # Точное совпадение
    if role in ROLE_TEMPLATES:
        return ROLE_TEMPLATES[role]

    # Частичное совпадение
    for template_role, template in ROLE_TEMPLATES.items():
        if template_role.lower() in role.lower() or role.lower() in template_role.lower():
            return template

    return DEFAULT_TEMPLATE


def generate_file_content(employee: Dict, priority: int) -> str:
    """Генерировать содержимое файла для эксперта."""
    name = employee["name"]
    role = employee["role"]

    template_data = get_template_for_role(role)

    content = TEMPLATE.format(
        name=name,
        name_upper=name.upper(),
        role=role,
        role_upper=role.upper(),
        priority=priority,
        emoji=template_data["emoji"],
        responsibilities=template_data["responsibilities"],
        tech_stack=template_data["tech_stack"],
        processes=template_data["processes"],
        interactions=template_data["interactions"],
        example_prompt=template_data["example_prompt"],
        quality_criteria=template_data["quality_criteria"],
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    return content


def sync_cursor_rules():
    """Синхронизировать .cursor/rules/ с employees.json."""

    print("=" * 60)
    print("🔄 СИНХРОНИЗАЦИЯ .cursor/rules/")
    print("=" * 60)
    print(f"📂 Проект: {PROJECT_ROOT}")
    print(f"📄 Источник: {EMPLOYEES_JSON}")
    print(f"📁 Цель: {RULES_DIR}")

    # 1. Загрузить текущий список сотрудников
    print("\n📋 Загрузка данных...")
    employees = load_employees_json()

    if not employees:
        print("❌ Файл employees.json пуст или не найден")
        return

    print(f"✅ Найдено сотрудников: {len(employees)}")

    # 2. Создать директорию
    RULES_DIR.mkdir(parents=True, exist_ok=True)

    # 3. Собрать существующие файлы
    existing_files = {f for f in RULES_DIR.glob("*.md") if f.name != "atra.mdc"}
    existing_names = {f.stem.split("_", 1)[1] if "_" in f.stem else f.stem: f for f in existing_files}

    # 4. Обработать каждого сотрудника
    current_files = set()
    stats = {"created": 0, "updated": 0, "skipped": 0}

    for idx, employee in enumerate(employees, start=1):
        name = employee["name"]
        role = employee["role"]
        normalized_name = normalize_filename(name)

        filename = f"{idx:02d}_{normalized_name}.md"
        filepath = RULES_DIR / filename
        current_files.add(filepath)

        # Генерируем содержимое
        content = generate_file_content(employee, priority=idx)

        # Проверяем существование
        if filepath.exists():
            # Читаем существующий
            existing_content = filepath.read_text(encoding="utf-8")

            # Проверяем, изменилась ли роль или имя (не timestamp)
            existing_core = existing_content.split("*Автоматически")[0].strip() if "*Автоматически" in existing_content else existing_content
            new_core = content.split("*Автоматически")[0].strip()

            if existing_core != new_core:
                filepath.write_text(content, encoding="utf-8")
                print(f"🔄 Обновлен  {filename} - {name} ({role})")
                stats["updated"] += 1
            else:
                print(f"⏭️  Пропущен  {filename} - без изменений")
                stats["skipped"] += 1
        else:
            # Создаем новый файл
            filepath.write_text(content, encoding="utf-8")
            print(f"✅ Создан    {filename} - {name} ({role})")
            stats["created"] += 1

    # 5. Найти устаревшие файлы (уволенные), не трогать служебные
    KEEP_FILES = {"README.md", "atra.mdc"}
    obsolete_files = existing_files - current_files - {RULES_DIR / name for name in KEEP_FILES}

    if obsolete_files:
        print(f"\n⚠️  Найдено устаревших файлов: {len(obsolete_files)}")
        for file in sorted(obsolete_files):
            print(f"   🗑️  {file.name}")

        # Автоматически удаляем (или можно сделать подтверждение)
        for file in obsolete_files:
            file.unlink()
            print(f"   ✅ Удален {file.name}")
        stats["deleted"] = len(obsolete_files)

    # 6. Итоговая статистика
    print("\n" + "=" * 60)
    print("📊 СТАТИСТИКА СИНХРОНИЗАЦИИ")
    print("=" * 60)
    print(f"✅ Создано:    {stats['created']}")
    print(f"🔄 Обновлено:  {stats['updated']}")
    print(f"⏭️  Пропущено:  {stats['skipped']}")
    if "deleted" in stats:
        print(f"🗑️  Удалено:    {stats['deleted']}")
    print(f"\n📁 Всего файлов: {len(current_files)}")
    print(f"📂 Папка: {RULES_DIR}")
    print("=" * 60)


def main():
    """Entry point."""
    try:
        sync_cursor_rules()
        return 0
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
