# 📋 Автосинхронизация .cursor/rules/

> Автоматическое обновление экспертных правил Cursor при изменениях в команде

## 🎯 Кратко

При изменении `configs/experts/employees.json` автоматически обновляются файлы в `.cursor/rules/` с описаниями всех экспертов.

**Запуск вручную:** `python3 scripts/sync_cursor_rules.py`  
**Автоматически:** при коммите изменений в `employees.json` (pre-commit hook).

## 📊 Сейчас

- **85 экспертов** — по одному файлу на сотрудника
- **Шаблоны** для 15+ ролей (Team Lead, Backend, Frontend, DevOps, ML и др.)
- **Копирование в другой проект:** `cp -r .cursor/rules/ ~/другой-проект/.cursor/`

## 📚 Документация

- `docs/CURSOR_RULES_QUICK_START.md` — быстрый старт
- `docs/CURSOR_RULES_AUTOSYNC.md` — полное описание

---

*Файлы экспертов (01_…md — 85_…md) генерируются скриптом. README.md и atra.mdc не удаляются при синхронизации.*

## Мета-правило: /expert и /brainstorm

**expert_and_brainstorm.mdc** (alwaysApply) — при запросе /expert или «подключи экспертов» агент подключает: экспертов (team.md, .cursor/rules, TEAM_PERSONALITIES), узлы знаний (MASTER_REFERENCE, CHANGES), знания гигантов (COGNITIVE_CODE, OPENWEBUI_RAG_SETUP). При /brainstorm или креативной задаче — обязательно скилл brainstorming (дизайн → одобрение → docs/plans/ → writing-plans). См. docs/plans/2026-02-23-expert-and-brainstorm-design.md.

---
🚀 Singularity 31.2+:
- Ты — часть децентрализованного Роя (Swarm).
- Используй Blackboard Service для аукционов задач.
- Твоя память: Knowledge Fabric (LanceDB + GraphRAG + VisualRAG).
- Твой кодекс: Digital Constitution & Constitutional Court.
- Твой транспорт: Redis UDS.
