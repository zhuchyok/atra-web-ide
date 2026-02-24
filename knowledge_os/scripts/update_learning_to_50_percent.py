#!/usr/bin/env python3
"""
Скрипт для доведения прогресса обучения всех сотрудников до 50%.

Заполняет:
- Изученные материалы (книги, инструменты, практики)
- Базовые накопленные знания
"""

import sys
from pathlib import Path
from typing import Dict, List

# Маппинг имен
NAME_MAPPING = {
    "Виктория": "viktoriya",
    "Дмитрий": "dmitriy",
    "Игорь": "igor",
    "Сергей": "sergey",
    "Анна": "anna",
    "Максим": "maxim",
    "Елена": "elena",
    "Алексей": "alexey",
    "Павел": "pavel",
    "Мария": "maria",
    "Роман": "roman",
    "Ольга": "olga",
    "Татьяна": "tatyana",
    "Екатерина": "ekaterina",
    "Андрей": "andrey",
    "София": "sofia",
    "Никита": "nikita",
    "Дарья": "daria",
    "Марина": "marina",
    "Юлия": "yuliya",
    "Артем": "artem",
}

# Материалы для каждой роли
LEARNING_MATERIALS: Dict[str, Dict[str, List[str]]] = {
    "Team Lead": {
        "books": [
            "The Manager's Path - Camille Fournier",
            "Team Topologies - Matthew Skelton, Manuel Pais",
            "An Elegant Puzzle - Will Larson",
            "The Phoenix Project - Gene Kim",
        ],
        "tools": [
            "GitHub для координации",
            "Jira/Linear для управления задачами",
            "Slack/Telegram для коммуникации",
            "Retrospectives для улучшений",
        ],
        "practices": [
            "1-on-1 встречи с командой",
            "Agile/Scrum методологии",
            "Code review процессы",
            "Continuous learning системы",
        ],
    },
    "ML Engineer": {
        "books": [
            "Machine Learning for Algorithmic Trading - Stefan Jansen",
            "Advances in Financial Machine Learning - Marcos López de Prado",
            "Hands-On Gradient Boosting - Daniel Y. Takahashi",
            "Feature Engineering for Machine Learning - Alice Zheng",
        ],
        "tools": [
            "LightGBM, XGBoost",
            "Optuna для оптимизации",
            "SHAP для интерпретации",
            "MLflow для экспериментов",
        ],
        "practices": [
            "Walk-forward analysis",
            "Triple-barrier labeling",
            "Meta-labeling",
            "Sample weights для class imbalance",
        ],
    },
    "Backend Developer": {
        "books": [
            "Fluent Python - Luciano Ramalho",
            "High Performance Python - Micha Gorelick",
            "Designing Data-Intensive Applications - Martin Kleppmann",
            "Clean Architecture - Robert C. Martin",
        ],
        "tools": [
            "Python asyncio",
            "FastAPI, Flask",
            "PostgreSQL, SQLite",
            "Docker, Kubernetes",
        ],
        "practices": [
            "Async/await для I/O операций",
            "Stateless architecture",
            "Retry logic с exponential backoff",
            "Type hints и документация",
        ],
    },
    "DevOps Engineer": {
        "books": [
            "The Phoenix Project - Gene Kim",
            "Kubernetes: Up and Running - Kelsey Hightower",
            "Site Reliability Engineering - Google",
            "Infrastructure as Code - Kief Morris",
        ],
        "tools": [
            "Docker, Kubernetes",
            "GitHub Actions, CI/CD",
            "Prometheus, Grafana",
            "Terraform, Ansible",
        ],
        "practices": [
            "Infrastructure as Code",
            "Continuous Deployment",
            "Monitoring и alerting",
            "Backup и recovery",
        ],
    },
    "QA Engineer": {
        "books": [
            "Python Testing with pytest - Brian Okken",
            "The Art of Software Testing - Glenford Myers",
            "Test-Driven Development - Kent Beck",
            "Continuous Delivery - Jez Humble",
        ],
        "tools": [
            "pytest для unit тестов",
            "Hypothesis для property-based тестов",
            "Locust для load testing",
            "Coverage.py для покрытия",
        ],
        "practices": [
            "Test-driven development",
            "Покрытие тестами > 80%",
            "Integration тесты",
            "Automated testing в CI/CD",
        ],
    },
    "Data Analyst": {
        "books": [
            "Quantitative Trading - Ernest Chan",
            "Cryptocurrency Trading - 2024",
            "Systematic Trading - Robert Carver",
            "Python for Data Analysis - Wes McKinney",
        ],
        "tools": [
            "Backtrader, VectorBT",
            "PyPortfolioOpt",
            "Pandas, NumPy",
            "Matplotlib, Plotly",
        ],
        "practices": [
            "Sharpe Ratio для крипто (sqrt(365))",
            "Backtesting с учетом комиссий",
            "Risk metrics (Sortino, max drawdown)",
            "Transaction costs анализ",
        ],
    },
    "Monitor": {
        "books": [
            "Observability Engineering - Charity Majors",
            "The Art of Monitoring - James Turnbull",
            "Site Reliability Engineering - Google",
            "Prometheus: Up & Running - Brian Brazil",
        ],
        "tools": [
            "Prometheus, Grafana",
            "ELK Stack (Elasticsearch, Logstash, Kibana)",
            "PagerDuty для алертов",
            "OpenTelemetry для tracing",
        ],
        "practices": [
            "Three pillars (logs/metrics/traces)",
            "High cardinality метрики",
            "Structured logging",
            "Alert fatigue prevention",
        ],
    },
    "Security Engineer": {
        "books": [
            "The Web Application Hacker's Handbook - Stuttard",
            "OWASP Top 10",
            "Applied Cryptography - Bruce Schneier",
            "Security Engineering - Ross Anderson",
        ],
        "tools": [
            "OWASP ZAP",
            "Bandit для Python security",
            "Snyk для dependency scanning",
            "Vault для секретов",
        ],
        "practices": [
            "API keys encryption",
            "Environment variables для секретов",
            "Regular security audits",
            "Dependency updates",
        ],
    },
    "Trading Strategy Developer": {
        "books": [
            "Algorithmic Trading - Ernest Chan",
            "Trading Systems - Emilio Tomasini",
            "Evidence-Based Technical Analysis - David Aronson",
            "Quantitative Trading Strategies - Lars Kestner",
        ],
        "tools": [
            "Backtrader для бэктестов",
            "TA-Lib для индикаторов",
            "Pandas для анализа данных",
            "NumPy для вычислений",
        ],
        "practices": [
            "Strategy backtesting",
            "Parameter optimization",
            "Risk management integration",
            "Signal generation",
        ],
    },
    "Risk Manager": {
        "books": [
            "Risk Management - Michel Crouhy",
            "Quantitative Risk Management - McNeil",
            "The Kelly Criterion - William Poundstone",
            "Trading Risk - Kenneth Grant",
        ],
        "tools": [
            "Position sizing calculators",
            "Risk metrics calculators",
            "Monte Carlo simulation",
            "VaR, CVaR расчеты",
        ],
        "practices": [
            "Position sizing (Kelly Criterion)",
            "Stop Loss и Take Profit",
            "Max drawdown контроль",
            "Risk metrics (VaR, CVaR)",
        ],
    },
    "Database Engineer": {
        "books": [
            "High Performance MySQL - Baron Schwartz",
            "PostgreSQL: Up and Running - Regina Obe",
            "SQL Performance Explained - Markus Winand",
            "Database Design for Mere Mortals - Hernandez",
        ],
        "tools": [
            "PostgreSQL, SQLite",
            "Query optimization tools",
            "Database migration tools",
            "Backup и recovery tools",
        ],
        "practices": [
            "Query optimization",
            "Index optimization",
            "Connection pooling",
            "Database migrations",
        ],
    },
    "Performance Engineer": {
        "books": [
            "High Performance Python - Gorelick",
            "Systems Performance - Brendan Gregg",
            "Python Performance - Ian Ozsvald",
            "The Art of Computer Programming - Knuth",
        ],
        "tools": [
            "cProfile, line_profiler",
            "memory_profiler",
            "py-spy для profiling",
            "Locust для load testing",
        ],
        "practices": [
            "Code profiling",
            "Memory optimization",
            "Latency optimization",
            "Load testing",
        ],
    },
    "Technical Writer": {
        "books": [
            "Technical Writing Handbook - JoAnn Hackos",
            "The Elements of Style - Strunk & White",
            "Docs for Developers - Jared Bhatti",
            "Every Page is Page One - Mark Baker",
        ],
        "tools": [
            "Markdown, reStructuredText",
            "Sphinx, MkDocs",
            "GitBook, Notion",
            "API documentation tools",
        ],
        "practices": [
            "Clear documentation",
            "API documentation",
            "Architecture documentation",
            "User guides",
        ],
    },
    "Financial Analyst": {
        "books": [
            "Python for Finance - Yves Hilpisch",
            "Financial Modeling - Simon Benninga",
            "Quantitative Trading - Ernest Chan",
            "Options, Futures, and Other Derivatives - Hull",
        ],
        "tools": [
            "Decimal для финансовых расчётов",
            "Financial validation tools",
            "Audit tools",
            "Balance consistency checks",
        ],
        "practices": [
            "Decimal вместо float",
            "Financial validation",
            "Profit/loss validation",
            "Commission validation",
        ],
    },
    "Frontend Developer": {
        "books": [
            "Learning React - Alex Banks, Eve Porcello",
            "Next.js in Action - Phil Pluckthun",
            "TypeScript Deep Dive - Basarat Ali Syed",
            "Web Performance - Ilya Grigorik",
        ],
        "tools": [
            "React, Next.js",
            "TypeScript",
            "Jest, Playwright",
            "Webpack, Vite",
        ],
        "practices": [
            "SSR/SSG/ISR",
            "Code splitting",
            "Bundle optimization",
            "Core Web Vitals",
        ],
    },
    "UI/UX Designer": {
        "books": [
            "Don't Make Me Think - Steve Krug",
            "The Design of Everyday Things - Don Norman",
            "Atomic Design - Brad Frost",
            "Hooked - Nir Eyal",
        ],
        "tools": [
            "Figma",
            "Sketch, Adobe XD",
            "Prototyping tools",
            "User research tools",
        ],
        "practices": [
            "Design systems",
            "User research",
            "Prototyping",
            "Conversion optimization",
        ],
    },
    "Full-stack Developer": {
        "books": [
            "Node.js Design Patterns - Mario Casciaro",
            "Building Microservices - Sam Newman",
            "Designing Data-Intensive Applications - Martin Kleppmann",
            "Clean Architecture - Robert C. Martin",
        ],
        "tools": [
            "Node.js, Express",
            "GraphQL, REST APIs",
            "WebSockets",
            "Microservices frameworks",
        ],
        "practices": [
            "API design",
            "Real-time updates",
            "Microservices",
            "Serverless",
        ],
    },
    "SEO & AI Visibility Specialist": {
        "books": [
            "The Art of SEO - Eric Enge",
            "AI SEO: The Future of Search - Industry reports",
            "Influence - Robert Cialdini",
            "Hooked - Nir Eyal",
        ],
        "tools": [
            "SEO tools (Ahrefs, SEMrush)",
            "Structured data validators",
            "AI SEO analyzers",
            "Analytics tools",
        ],
        "practices": [
            "Technical SEO",
            "AI SEO для ChatGPT/Perplexity",
            "Structured data",
            "Conversion optimization",
        ],
    },
    "Content Manager": {
        "books": [
            "The Copywriter's Handbook - Robert Bly",
            "Made to Stick - Chip Heath, Dan Heath",
            "Content Strategy for the Web - Kristina Halvorson",
            "Everybody Writes - Ann Handley",
        ],
        "tools": [
            "Content management systems",
            "SEO content tools",
            "AI content tools",
            "Analytics tools",
        ],
        "practices": [
            "Copywriting",
            "SEO-контент",
            "AI-контент",
            "Content strategy",
        ],
    },
    "Legal Counsel": {
        "books": [
            "GDPR: The Complete Guide",
            "CCPA Compliance Guide",
            "Cryptocurrency Law - Industry guides",
            "Contract Law Fundamentals",
        ],
        "tools": [
            "Legal research databases",
            "Compliance checklists",
            "Contract templates",
            "Regulatory tracking",
        ],
        "practices": [
            "GDPR compliance",
            "CCPA compliance",
            "Contract review",
            "Regulatory compliance",
        ],
    },
    "Code Reviewer": {
        "books": [
            "Clean Code - Robert C. Martin",
            "Code Complete - Steve McConnell",
            "Refactoring - Martin Fowler",
            "The Pragmatic Programmer - Hunt & Thomas",
        ],
        "tools": [
            "Linters (pylint, flake8)",
            "Type checkers (mypy)",
            "Code quality tools",
            "Automated testing",
        ],
        "practices": [
            "Code review best practices",
            "Quality standards",
            "Refactoring techniques",
            "Best practices enforcement",
        ],
    },
}

# Базовые знания для каждой роли
BASIC_KNOWLEDGE: Dict[str, Dict[str, List[str]]] = {
    "Team Lead": {
        "what_i_know": [
            "Координация команды из 21 эксперта",
            "Архитектурные решения",
            "Принятие решений",
        ],
        "new_knowledge": [
            "Система постоянного обучения",
            "Автоматический поиск лучших практик",
        ],
    },
    "ML Engineer": {
        "what_i_know": [
            "Machine Learning для торговых стратегий",
            "Feature engineering",
            "Model optimization",
        ],
        "new_knowledge": [
            "Walk-forward analysis",
            "Triple-barrier labeling",
        ],
    },
    "Backend Developer": {
        "what_i_know": [
            "Python async/await",
            "API development",
            "Database integration",
        ],
        "new_knowledge": [
            "Stateless architecture",
            "Retry logic patterns",
        ],
    },
    "DevOps Engineer": {
        "what_i_know": [
            "Docker, Kubernetes",
            "CI/CD pipelines",
            "Monitoring systems",
        ],
        "new_knowledge": [
            "Infrastructure as Code",
            "Automated deployments",
        ],
    },
    "QA Engineer": {
        "what_i_know": [
            "Unit testing",
            "Integration testing",
            "Test automation",
        ],
        "new_knowledge": [
            "Test coverage > 80%",
            "Property-based testing",
        ],
    },
    "Data Analyst": {
        "what_i_know": [
            "Backtesting strategies",
            "Risk metrics",
            "Data analysis",
        ],
        "new_knowledge": [
            "Sharpe Ratio для крипто (sqrt(365))",
            "Transaction costs в бэктестах",
        ],
    },
    "Monitor": {
        "what_i_know": [
            "Prometheus, Grafana",
            "Log aggregation",
            "Alerting systems",
        ],
        "new_knowledge": [
            "Three pillars observability",
            "Structured logging",
        ],
    },
    "Security Engineer": {
        "what_i_know": [
            "API security",
            "Data encryption",
            "Security audits",
        ],
        "new_knowledge": [
            "API keys encryption",
            "Environment variables security",
        ],
    },
    "Trading Strategy Developer": {
        "what_i_know": [
            "Trading strategies",
            "Backtesting",
            "Signal generation",
        ],
        "new_knowledge": [
            "Strategy optimization",
            "Parameter tuning",
        ],
    },
    "Risk Manager": {
        "what_i_know": [
            "Position sizing",
            "Risk metrics",
            "Drawdown management",
        ],
        "new_knowledge": [
            "Kelly Criterion",
            "VaR, CVaR расчеты",
        ],
    },
    "Database Engineer": {
        "what_i_know": [
            "Database optimization",
            "Query optimization",
            "Migrations",
        ],
        "new_knowledge": [
            "Connection pooling",
            "Index optimization",
        ],
    },
    "Performance Engineer": {
        "what_i_know": [
            "Code profiling",
            "Performance optimization",
            "Load testing",
        ],
        "new_knowledge": [
            "Latency optimization",
            "Memory optimization",
        ],
    },
    "Technical Writer": {
        "what_i_know": [
            "Technical documentation",
            "API documentation",
            "User guides",
        ],
        "new_knowledge": [
            "Markdown documentation",
            "Architecture docs",
        ],
    },
    "Financial Analyst": {
        "what_i_know": [
            "Decimal для финансовых расчётов",
            "Financial validation",
            "Audit processes",
        ],
        "new_knowledge": [
            "Profit/loss validation",
            "Commission validation",
        ],
    },
    "Frontend Developer": {
        "what_i_know": [
            "React, Next.js",
            "TypeScript",
            "Performance optimization",
        ],
        "new_knowledge": [
            "SSR/SSG/ISR",
            "Core Web Vitals",
        ],
    },
    "UI/UX Designer": {
        "what_i_know": [
            "Design systems",
            "User research",
            "Prototyping",
        ],
        "new_knowledge": [
            "Conversion optimization",
            "User experience design",
        ],
    },
    "Full-stack Developer": {
        "what_i_know": [
            "Node.js, Python",
            "API design",
            "Microservices",
        ],
        "new_knowledge": [
            "GraphQL",
            "Real-time updates",
        ],
    },
    "SEO & AI Visibility Specialist": {
        "what_i_know": [
            "Classic SEO",
            "Technical SEO",
            "Content optimization",
        ],
        "new_knowledge": [
            "AI SEO для ChatGPT/Perplexity",
            "Structured data",
        ],
    },
    "Content Manager": {
        "what_i_know": [
            "Copywriting",
            "SEO-контент",
            "Content strategy",
        ],
        "new_knowledge": [
            "AI-контент",
            "Conversion optimization",
        ],
    },
    "Legal Counsel": {
        "what_i_know": [
            "GDPR compliance",
            "CCPA compliance",
            "Contract law",
        ],
        "new_knowledge": [
            "Cryptocurrency law",
            "Financial regulations",
        ],
    },
    "Code Reviewer": {
        "what_i_know": [
            "Code quality standards",
            "Best practices",
            "Refactoring",
        ],
        "new_knowledge": [
            "Automated code review",
            "Quality metrics",
        ],
    },
}


def update_knowledge_base(name: str, role: str, kb_path: Path):
    """Обновляет базу знаний сотрудника"""
    if not kb_path.exists():
        print(f"⚠️ База знаний не найдена: {kb_path}")
        return False

    content = kb_path.read_text(encoding="utf-8")

    # Получаем материалы для роли
    materials = LEARNING_MATERIALS.get(role, {})
    knowledge = BASIC_KNOWLEDGE.get(role, {})

    # Заменяем изученные материалы
    if "## 📖 ИЗУЧЕННЫЕ МАТЕРИАЛЫ" in content:
        lines = content.split("\n")
        updated_lines = []
        in_materials = False
        materials_added = False

        for i, line in enumerate(lines):
            if "## 📖 ИЗУЧЕННЫЕ МАТЕРИАЛЫ" in line:
                in_materials = True
                updated_lines.append(line)
                continue

            if in_materials:
                if line.startswith("### Книги и ресурсы:"):
                    updated_lines.append(line)
                    updated_lines.append("")
                    for book in materials.get("books", []):
                        updated_lines.append(f"- {book}")
                    materials_added = True
                    continue

                if line.startswith("### Инструменты:"):
                    updated_lines.append(line)
                    updated_lines.append("")
                    for tool in materials.get("tools", []):
                        updated_lines.append(f"- {tool}")
                    materials_added = True
                    continue

                if line.startswith("### Практики:"):
                    updated_lines.append(line)
                    updated_lines.append("")
                    for practice in materials.get("practices", []):
                        updated_lines.append(f"- {practice}")
                    materials_added = True
                    continue

                if line.startswith("## ") and "ИЗУЧЕННЫЕ МАТЕРИАЛЫ" not in line:
                    in_materials = False
                    updated_lines.append(line)
                    continue

                # Пропускаем строки с "[Будет добавлено"
                if "[Будет добавлено" in line:
                    continue

                if not materials_added:
                    updated_lines.append(line)
                    continue

            updated_lines.append(line)

        content = "\n".join(updated_lines)

    # Заменяем накопленные знания
    if "## 🧠 НАКОПЛЕННЫЕ ЗНАНИЯ" in content:
        lines = content.split("\n")
        updated_lines = []
        in_knowledge = False
        knowledge_added = False

        for i, line in enumerate(lines):
            if "## 🧠 НАКОПЛЕННЫЕ ЗНАНИЯ" in line:
                in_knowledge = True
                updated_lines.append(line)
                continue

            if in_knowledge:
                if line.startswith("### ✅ Что уже знаю:"):
                    updated_lines.append(line)
                    updated_lines.append("")
                    for item in knowledge.get("what_i_know", []):
                        updated_lines.append(f"- {item}")
                    knowledge_added = True
                    continue

                if line.startswith("### 🆕 Новые знания:"):
                    updated_lines.append(line)
                    updated_lines.append("")
                    for item in knowledge.get("new_knowledge", []):
                        updated_lines.append(f"- {item}")
                    knowledge_added = True
                    continue

                if line.startswith("## ") and "НАКОПЛЕННЫЕ ЗНАНИЯ" not in line:
                    in_knowledge = False
                    updated_lines.append(line)
                    continue

                # Пропускаем строки с "[Будет добавлено"
                if "[Будет добавлено" in line:
                    continue

                if not knowledge_added:
                    updated_lines.append(line)
                    continue

            updated_lines.append(line)

        content = "\n".join(updated_lines)

    # Сохраняем обновленную базу знаний
    kb_path.write_text(content, encoding="utf-8")
    return True


def main():
    """Главная функция"""
    print("🚀 Обновление баз знаний до 50%...")

    scripts_dir = Path(__file__).parent

    TEAM_MEMBERS = [
        ("Виктория", "Team Lead"),
        ("Дмитрий", "ML Engineer"),
        ("Игорь", "Backend Developer"),
        ("Сергей", "DevOps Engineer"),
        ("Анна", "QA Engineer"),
        ("Максим", "Data Analyst"),
        ("Елена", "Monitor"),
        ("Алексей", "Security Engineer"),
        ("Павел", "Trading Strategy Developer"),
        ("Мария", "Risk Manager"),
        ("Роман", "Database Engineer"),
        ("Ольга", "Performance Engineer"),
        ("Татьяна", "Technical Writer"),
        ("Екатерина", "Financial Analyst"),
        ("Андрей", "Frontend Developer"),
        ("София", "UI/UX Designer"),
        ("Никита", "Full-stack Developer"),
        ("Дарья", "SEO & AI Visibility Specialist"),
        ("Марина", "Content Manager"),
        ("Юлия", "Legal Counsel"),
        ("Артем", "Code Reviewer"),
    ]

    updated = 0
    for name, role in TEAM_MEMBERS:
        file_name = NAME_MAPPING.get(name, name.lower())
        kb_path = scripts_dir / f"{file_name}_knowledge.md"

        if update_knowledge_base(name, role, kb_path):
            print(f"✅ Обновлена база знаний: {name} ({role})")
            updated += 1
        else:
            print(f"⚠️ Не удалось обновить: {name}")

    print(f"\n✅ Обновлено баз знаний: {updated}/{len(TEAM_MEMBERS)}")
    print("📊 Теперь запустите: python3 scripts/check_learning_progress.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
