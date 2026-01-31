# Отчёт: проверка заполненности экспертов и ролей

**Дата:** 2026-01-27

## Что проверено

1. **configs/experts/employees.md** — 58 сотрудников, у каждого роль и отдел. ✅ Заполнено.
2. **knowledge_os/db/seed_experts.json** — 13 базовых экспертов; раньше не было поля `department`. ✅ Исправлено: для всех 13 добавлен `department` в соответствии с employees.md.
3. **knowledge_os/app/task_orchestration/expert_matching_engine.py** — маппинг CATEGORY_TO_ROLES. ✅ Дополнен: добавлены роли из employees.md (QA Lead, Security Analyst, Data Engineer, SRE Engineer, Documentation Writer, Analyst, Risk Analyst, Trading Analyst, Product Analyst, ML Researcher и др.), чтобы подбор экспертов учитывал все роли из списка.
4. **knowledge_os/app/department_heads_system.py** — DEPARTMENT_HEADS и DEPARTMENT_KEYWORDS. ✅ Приведено к employees.md: добавлены отделы Leadership, Trading, Marketing, Product, Legal, HR, Support, Development; для Architecture head указан Александр; добавлены ключевые слова для всех отделов (Leadership, Documentation, Monitoring, Trading, Product, Legal, HR, Support, Development).
5. **knowledge_os/scripts/check_experts_count.py** — KNOWN_EXPERT_NAMES (для сканирования хардкодов). ✅ Расширено до 58 имён из employees.md.

## Внесённые изменения

| Файл | Изменение |
|------|-----------|
| `knowledge_os/db/seed_experts.json` | Для всех 13 экспертов добавлено поле `department` (Leadership, ML/AI, Backend, DevOps/Infra, QA, Strategy/Data, Monitoring, Security, Trading, Risk Management, Database, Performance, Documentation). |
| `knowledge_os/app/department_heads_system.py` | DEPARTMENT_HEADS: добавлены Leadership (Виктория), Trading (Павел), Marketing (Дарья), Product (Анастасия), Legal (Юлия), HR (Алла), Support (Зоя), Development (Вероника); Architecture head → Александр. DEPARTMENT_KEYWORDS: добавлены ключевые слова для Leadership, Documentation, Monitoring, Trading, Product, Legal, HR, Support, Development. |
| `knowledge_os/scripts/check_experts_count.py` | KNOWN_EXPERT_NAMES расширен до 58 имён (все из employees.md). |
| `knowledge_os/app/task_orchestration/expert_matching_engine.py` | CATEGORY_TO_ROLES: в coding добавлены Data Engineer, QA Lead; в reasoning — Security Analyst, Risk Analyst, Trading Analyst, Product Analyst, ML Researcher, Analyst; в general — SRE Engineer, Data Engineer, Documentation Writer, QA Lead, Security Analyst, Content Manager, Legal Counsel, Compliance Officer, Support Engineer, HR Specialist, Infrastructure Engineer, ML Researcher, UX Researcher, Product Analyst, Trading Analyst, Risk Analyst, Analyst; в fast — SRE Engineer. |

## Рекомендации

- **БД:** При загрузке экспертов из seed (JSON или SQL) убедитесь, что используется колонка `department`, если она есть в источнике. В `server_knowledge_sync` и `enhanced_orchestrator` при INSERT уже передаётся department.
- **Новые сотрудники:** Добавлять в `configs/experts/employees.md` с ролью и отделом; при появлении новых ролей — при необходимости дополнять CATEGORY_TO_ROLES и DEPARTMENT_HEADS/DEPARTMENT_KEYWORDS.
- **expert_specializations:** Для ещё более точного подбора можно заполнять таблицу `expert_specializations` (category = coding/reasoning/general и т.д.) по экспертам — тогда ExpertMatchingEngine будет использовать её в первую очередь.
