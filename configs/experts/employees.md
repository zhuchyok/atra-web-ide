# Сотрудники ATRA (полный список с ролями)

**Единый источник правды:** добавьте нового сотрудника в **`configs/experts/employees.json`**, затем запустите: **`python scripts/sync_employees.py`** — обновятся seed, KNOWN_EXPERT_NAMES и эта таблица.

- **Итого сотрудников:** 85
- **Отделов:** 40
- **Обновлено:** 2026-02-01

## Полный список (85)

| № | Имя | Роль | Отдел |
|---|-----|------|-------|
| 1 | Виктория | Team Lead | Leadership |
| 2 | Дмитрий | ML Engineer | ML/AI |
| 3 | Игорь | Backend Developer | Backend |
| 4 | Сергей | DevOps Engineer | DevOps/Infra |
| 5 | Анна | QA Engineer | QA |
| 6 | Максим | Data Analyst | Strategy/Data |
| 7 | Елена | Monitor | Monitoring |
| 8 | Алексей | Security Engineer | Security |
| 9 | Павел | Trading Strategy Developer | Trading |
| 10 | Мария | Risk Manager | Risk Management |
| 11 | Роман | Database Engineer | Database |
| 12 | Ольга | Performance Engineer | Performance |
| 13 | Татьяна | Technical Writer | Documentation |
| 14 | Даниил | Principal Backend Architect | Backend |
| 15 | Никита | Full-stack Developer | Backend |
| 16 | Андрей | Frontend Developer | Frontend |
| 17 | София | UI/UX Designer | Frontend |
| 18 | Артем | Code Reviewer | QA |
| 19 | Дарья | SEO & AI Visibility Specialist | Marketing |
| 20 | Марина | Content Manager | Marketing |
| 21 | Екатерина | Financial Analyst | Trading |
| 22 | Анастасия | Product Manager | Product |
| 23 | Юлия | Legal Counsel | Legal |
| 24 | Владимир | Data Engineer | Database |
| 25 | Глеб | SRE Engineer | DevOps/Infra |
| 26 | Яна | UX Researcher | Frontend |
| 27 | Кирилл | Backend Developer | Backend |
| 28 | Михаил | ML Researcher | ML/AI |
| 29 | Александр | System Architect | Architecture |
| 30 | Наталья | QA Lead | QA |
| 31 | Светлана | Technical Writer | Documentation |
| 32 | Олег | DevOps Engineer | DevOps/Infra |
| 33 | Вадим | Security Analyst | Security |
| 34 | Полина | Frontend Developer | Frontend |
| 35 | Ксения | Data Analyst | Strategy/Data |
| 36 | Виталий | Performance Engineer | Performance |
| 37 | Станислав | Database Engineer | Database |
| 38 | Денис | Backend Developer | Backend |
| 39 | Евгений | ML Engineer | ML/AI |
| 40 | Илья | Full-stack Developer | Backend |
| 41 | Леонид | Risk Analyst | Risk Management |
| 42 | Тимофей | Trading Analyst | Trading |
| 43 | Валерия | Product Analyst | Product |
| 44 | Ульяна | Content Writer | Marketing |
| 45 | Алла | HR Specialist | HR |
| 46 | Борис | Infrastructure Engineer | DevOps/Infra |
| 47 | Галина | Compliance Officer | Legal |
| 48 | Зоя | Support Engineer | Support |
| 49 | Лариса | QA Engineer | QA |
| 50 | Инна | Data Scientist | Strategy/Data |
| 51 | Марк | Backend Developer | Backend |
| 52 | Филипп | Frontend Developer | Frontend |
| 53 | Георгий | Monitor | Monitoring |
| 54 | Василий | Security Engineer | Security |
| 55 | Константин | Technical Lead | Architecture |
| 56 | Ирина | Documentation Writer | Documentation |
| 57 | Людмила | Analyst | Strategy/Data |
| 58 | Вероника | Local Developer (Agent) | Development |
| 59 | Alex | Principal AI Coordination Architect | AI Coordination |
| 60 | Адриан | Principal System Design Architect | System Design |
| 61 | Алекс | Principal Multi-Agent Systems Architect | Multi-Agent Systems |
| 62 | Алекс Ковальски | Principal Software Architect & Engineering Lead | Coding |
| 63 | Алекс Нейман | Principal Machine Learning Architect | Machine Learning |
| 64 | Александр Нейман | Principal AI Systems Architect & Technical Fellow | AI Systems |
| 65 | Александра | Principal Error Handling & User Interface Architect | Error Handling / User Interface |
| 66 | Альберт | Директор по продажам (Sales Director) | Management |
| 67 | Артемий | UI/UX Designer | Web & Product |
| 68 | Артур | Principal Agent Architecture & Workflow Systems Architect | Agent Architecture / Workflow Management |
| 69 | Артём | Senior UX/UI Designer & Web Strategy Lead | Web & Product |
| 70 | Виктор | Chief Trading Strategist | Trading |
| 71 | Виктор_M&A | M&A Analyst / Инвестиционный стратег | Finance & Accounting |
| 72 | Владимир_CEO | CEO / Executive Director | Management |
| 73 | Григорий | Главный Экономист / Макроаналитик | Finance & Accounting |
| 74 | Диана | Performance Coach / Психолог | Management |
| 75 | Дмитрий_Ad | Classifieds Specialist (Avito, Профи) | Marketing & Growth |
| 76 | Евгения | PR-директор / Бренд-менеджер | Consulting |
| 77 | Кристина | Senior Copywriter | Marketing |
| 78 | Лиза | SMM & Content Lead | Marketing |
| 79 | Макс | Lead DevOps Architect & Senior System Administrator | System Administration / DevOps |
| 80 | Маркус | Chief People & Team Excellence Officer | Team Management |
| 81 | Натан | Director of Competitive Intelligence | Competitive Intelligence |
| 82 | Николай | GR-директор (Government Relations) | Security & Legal |
| 83 | Оксана | Digital Strategist / Media Planner | Marketing & Growth |
| 84 | Оливер | Chief Knowledge Officer & Knowledge Architecture Strategist | Knowledge Management |
| 85 | Степан | Senior Data Scientist | Tech & AI |

**Итого: 85 сотрудников.**

## Правило для будущего

**При добавлении нового сотрудника:**

1. Добавьте запись в **`configs/experts/employees.json`** в массив `employees`: `{"name": "Имя", "role": "Роль", "department": "Отдел"}`.
2. Сделайте **git add** и **git commit**. Если один раз выполнили **`./scripts/install_git_hooks.sh`**, при коммите автоматически запустится sync и в коммит попадут:
   - `configs/experts/_known_names_generated.py` (KNOWN_EXPERT_NAMES),
   - `knowledge_os/db/seed_experts.json` (role, department; новый эксперт добавится с шаблонным system_prompt),
   - эта таблица в `configs/experts/employees.md`.
3. При необходимости добавьте роль в `.cursor/rules/` и связь в `configs/experts/team.md`.
4. Для БД: примените seed/миграцию или добавьте запись в таблицу `experts`.

## Системная роль: Оркестратор

**Оркестратор** — не отдельный сотрудник, а системная роль координации задач. Подробно: **`.cursor/rules/22_orchestrator.md`**. В Cursor: `@orchestrator`.

## Связь с другими файлами

- **Основные роли и Cursor:** `configs/experts/team.md`
- **Seed для БД:** `knowledge_os/db/seed_experts.json`
- **Department Heads:** `knowledge_os/app/department_heads_system.py`
- **Автономные кандидаты (MDM):** `configs/experts/autonomous_candidates.json` — автономно нанятые для ревью и добавления в employees.json
