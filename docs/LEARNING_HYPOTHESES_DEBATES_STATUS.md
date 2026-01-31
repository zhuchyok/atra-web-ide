# Статус: обучение, гипотезы, база знаний, дебаты

**Дата:** 2026-01-29  
**Цель:** Ответ на вопрос: *обучения проходят? гипотезы создаются? база знаний пополняется? дебаты происходят? сотрудники все обучаются*

---

## Краткий ответ

| Процесс | Реализовано в коде | Запускается автоматически | Где смотреть |
|--------|---------------------|---------------------------|--------------|
| **Обучения** (экспертов) | ✅ Nightly Learner | ❌ Нет (нужен запуск вручную/cron) | Дашборд → «Академия ИИ» |
| **Гипотезы** | ✅ Cross-Domain Linker, Streaming/Enhanced Orchestrator | ❌ Нет (оркестраторы не в docker-compose) | `knowledge_nodes` с `metadata->>'source' = 'cross_domain_linker'` |
| **База знаний пополняется** | ✅ capture_knowledge, оркестраторы | Частично: при чатах/API; оркестраторы — вручную | Дашборд → «База знаний», «Узлы» |
| **Дебаты** | ✅ Nightly Learner → run_expert_council, Debate Processor | ❌ Нет (внутри Nightly Learner, который не запущен по умолчанию) | Дашборд → «Академия ИИ и Дебаты» |
| **Сотрудники обучаются** | ✅ expert_learning_logs в Nightly Learner | ❌ Нет (то же: Nightly Learner не в автозапуске) | Дашборд → «Академия ИИ» (логи обучения) |

**Итог:** Всё реализовано в коде, но **ни один из этих процессов не стартует автоматически** при `docker-compose up`. Чтобы они шли, нужно запускать **Nightly Learner** и **оркестраторы** (Enhanced/Streaming) вручную или по cron.

---

## 1. Обучения (обучение экспертов)

- **Где:** `knowledge_os/app/nightly_learner.py`
- **Что делает:** для каждого эксперта получает инсайты (LLM), сохраняет в `knowledge_nodes`, пишет в `expert_learning_logs`, при высокой уверенности вызывает `run_expert_council` (дебаты). Также запускает Contextual Learning, Debate Processor и др.
- **Автозапуск:** не в docker-compose. Нужен запуск скрипта (или cron), например:
  ```bash
  cd knowledge_os/app && python nightly_learner.py
  ```
- **На дашборде:** вкладка «Академия ИИ и Дебаты» → блок «Академия ИИ» читает `expert_learning_logs`. Если записей нет — обучение не запускалось или не писало в эту БД.

---

## 2. Гипотезы

- **Где:**
  - Cross-Domain Linker (в Enhanced/Streaming Orchestrator) — пишет в `knowledge_nodes` с `metadata->>'source' = 'cross_domain_linker'`
  - Streaming Orchestrator — обработка событий INSIGHT_HYPOTHESIS, создание задач на валидацию
  - Research Lab — гипотезы по макро-данным (DXY), логи в `research/hypotheses_log.json`
  - Expert Council Discussion — `generate_hypotheses()`, `save_hypotheses()` в `knowledge_nodes` с `metadata->>'type' = 'hypothesis'`
- **Автозапуск:** оркестраторы не в docker-compose. Запуск вручную/скриптами:
  - `scripts/start_enhanced_orchestrator.sh` или цикл из `scripts/start_all_autonomous_systems.sh`
  - Streaming Orchestrator — отдельно (см. `knowledge_os/app/streaming_orchestrator.py`)
- **На дашборде:** гипотезы — это узлы в «База знаний» с соответствующими метаданными; вкладка «Гипотезы» (если есть) показывает выборки из `knowledge_nodes`.

---

## 3. База знаний пополняется

- **Где:**
  - MCP/API: `capture_knowledge()` в `knowledge_os/app/main.py` и `main_enhanced.py` — при вызовах из чатов/агентов
  - Оркестраторы: новые узлы за последние 6 часов, кросс-доменные связи (Streaming/Enhanced)
  - Nightly Learner: новые узлы из инсайтов экспертов
- **Автозапуск:** пополнение через `capture_knowledge` идёт при использовании чата/API; оркестраторы и Nightly Learner — только при их явном запуске.
- **На дашборде:** «База знаний», «Узлы», счётчики по `knowledge_nodes`.

---

## 4. Дебаты

- **Где:**
  - Создание: `nightly_learner.py` → `run_expert_council()` → INSERT в `expert_discussions`
  - Обработка: `knowledge_os/app/debate_processor.py` — анализ консенсуса, создание задач, приоритизация знаний
- **Автозапуск:** Debate Processor вызывается **внутри** Nightly Learner (фаза 10). Отдельного сервиса/cron для него в проекте нет. Если Nightly Learner не крутится — дебаты не создаются и не обрабатываются.
- **На дашборде:** «Академия ИИ и Дебаты» → блок «Дебаты» читает `expert_discussions`. Пусто = дебаты не создавались или БД не та.

---

## 5. Сотрудники (эксперты) обучаются

- **Где:** те же циклы Nightly Learner: для каждого эксперта — инсайты, запись в `expert_learning_logs`, обновление `experts.last_learned_at`.
- **Автозапуск:** только при запущенном Nightly Learner.
- **На дашборде:** «Академия ИИ» — список из `expert_learning_logs` (кто, тема, summary, learned_at).

---

## Что сделать, чтобы всё это работало

1. **Запускать Nightly Learner** (раз в сутки или по расписанию):
   - **Всё в одном (venv + один цикл):** `bash scripts/run_everything.sh`
   - Или только обучение + оркестратор (один цикл): `bash scripts/run_learning_and_orchestration.sh` (при отсутствии venv скрипт сам запустит `setup_knowledge_os_venv.sh`).
   - Настройка venv вручную: `bash scripts/setup_knowledge_os_venv.sh`
   - Или вручную: `cd knowledge_os/app && ../.venv/bin/python nightly_learner.py`
   - Или добавить в cron; пути `/root/` в nightly_learner заменены на `sys.executable` (Mac Studio).

2. **Запускать оркестраторы** (гипотезы, пополнение базы из новых узлов):
   - `bash scripts/run_learning_and_orchestration.sh` (один цикл Nightly Learner + Enhanced Orchestrator), или
   - `scripts/start_all_autonomous_systems.sh` (фон), или
   - `scripts/start_enhanced_orchestrator.sh` (один цикл).

3. **Убедиться в одной БД:** дашборд, Nightly Learner, оркестраторы и воркеры должны использовать один и тот же `DATABASE_URL` (как в `docs/DATABASE_LOCAL_ONLY.md`), иначе логи обучения, дебаты и узлы будут в разных местах и на дашборде не появятся.

После этого на дашборде появятся записи об обучении и дебатах, а гипотезы и узлы знаний начнут расти при работе оркестраторов и Nightly Learner.
