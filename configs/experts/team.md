# Команда экспертов ATRA

**Полный список сотрудников:** единый источник — [`configs/experts/employees.json`](employees.json). После добавления нового сотрудника в JSON запустите **`python scripts/sync_employees.py`** — обновятся seed, KNOWN_EXPERT_NAMES и таблица в [employees.md](employees.md).

## Основные роли

| Эксперт | Роль | Область |
|---------|------|---------|
| **Виктория** | Team Lead | Координация, архитектура, решения |
| **Дмитрий** | ML Engineer | ML, модели, feature engineering |
| **Игорь** | Backend Developer | Код, рефакторинг, тесты, Git |
| **Сергей** | DevOps Engineer | Деплой, серверы, мониторинг, backup |
| **Анна** | QA Engineer | Юнит-тесты, покрытие >80%, валидация |
| **Максим** | Data Analyst | Метрики, бэктесты, риск, отчёты |
| **Елена** | Monitor | Логи, алерты, Prometheus, Grafana |
| **Алексей** | Security Engineer | Безопасность, API keys, аудит |
| **Павел** | Trading Strategy Developer | Стратегии, бэктест, индикаторы |
| **Мария** | Risk Manager | Риски, position sizing, drawdown |
| **Роман** | Database Engineer | БД, миграции, оптимизация запросов |
| **Ольга** | Performance Engineer | Профилирование, latency, нагрузка |
| **Татьяна** | Technical Writer | Документация, API docs, отчёты |

## Алиасы (expert_aliases)

- Виктория: вика, викуся
- Владимир: вова, володя
- Дмитрий: дима, димон
- Мария: маша, маруся
- Максим: макс, максик
- Сергей: серёжа, серж
- Елена: лена
- Анна: аня, нюра
- Алексей: лёша, алёша
- Павел: паша
- Игорь: игорёк, гошa
- Роман: рома
- Ольга: оля
- Татьяна: таня

## Связь с .cursor/rules

Роли Cursor (файлы в `.cursor/rules/`) соответствуют экспертам:

| Эксперт | Роль | Файл правила |
|---------|------|----------------|
| Виктория | Team Lead | — |
| Дмитрий | ML Engineer | `10_ml_engineer.md` |
| Игорь | Backend Developer | `09_backend_developer.md` |
| Сергей | DevOps Engineer | `03_devops_engineer.md` |
| Анна | QA Engineer | `08_qa_engineer.md` |
| Максим | Data Analyst | `14_financial_analyst.md` |
| Елена | Monitor | `11_sre_monitor.md` |
| Алексей | Security Engineer | `12_security_engineer.md` |
| Павел | Trading Strategy | `01_quant_developer.md` |
| Мария | Risk Manager | `05_risk_manager.md` |
| Роман | Database Engineer | `04_data_engineer.md` |
| Ольга | Performance Engineer | `07_system_architect.md` |
| Татьяна | Technical Writer | `13_technical_writer.md` |
| **Оркестратор** (системная роль) | Orchestrator | `22_orchestrator.md` |

Полный индекс ролей: `.cursor/README.md`. Роль **Оркестратор** — координация задач (приём, анализ сложности, декомпозиция, подбор экспертов, назначение исполнителей); в runtime реализуется Victoria / Enhanced Orchestrator.

## Полный список сотрудников (58)

Все сотрудники с ролями и отделами перечислены в **[`configs/experts/employees.md`](employees.md)**.  
**При добавлении нового сотрудника** добавляйте его в `employees.md` с именем, ролью и отделом.

## Использование в промптах

Формулировать через команду экспертов:
- "Какие эксперты должны обсудить [проблему]? Что бы сказали [Эксперт1], [Эксперт2], [Эксперт3]?"
- "Как [Эксперт] подойдёт к диагностике и решению?"
- В Cursor: `@qa_engineer`, `@backend_developer`, `@ml_engineer`, `@sre_monitor`, `@security_engineer`, `@technical_writer`, `@orchestrator` и др. (см. `.cursor/README.md`).

См. `docs/mac-studio/VICTORIA_*`, `docs/EXPERT_TEAM_PROMPTS_GUIDE` в atra.
