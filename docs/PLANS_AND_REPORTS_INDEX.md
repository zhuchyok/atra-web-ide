# Индекс планов и отчётов

**Назначение:** единая точка входа «где что искать» для планов, отчётов, программ обучения и AI-инсайтов. Рекомендация из [PROJECT_GAPS_ANALYSIS_2026_02_05.md](PROJECT_GAPS_ANALYSIS_2026_02_05.md) §5 (Документация, Татьяна).

**Обновлено:** 2026-02-05

---

## 1. Планы (.cursor/plans/)

| Что | Где | Описание |
|-----|-----|----------|
| План верификации и полная хронология | [.cursor/plans/VERIFICATION_AND_FULL_PICTURE_PLAN.md](../.cursor/plans/VERIFICATION_AND_FULL_PICTURE_PLAN.md) | Верификация архитектуры, чеклист, связь с MASTER_REFERENCE. |
| План деплоя Knowledge OS | .cursor/plans/knowledge_os_deployment_*.plan.md | Деплой и конфигурация. |
| Планы по бэктесту, оптимизации, индикаторам | .cursor/plans/ | BACKTEST_*, OPTIMIZATION_*, INSTITUTIONAL_INDICATORS_*, RF_INSTITUTIONAL_HUNTER_* и др. — исторические планы по торговой логике. |

**Актуальность:** для текущей разработки корпорации (Victoria, воркер, оркестратор) опираться на **MASTER_REFERENCE**, **VERIFICATION_CHECKLIST_OPTIMIZATIONS** и **CHANGES_FROM_OTHER_CHATS**. Планы в .cursor/plans/ — справочно и для верификации. **Планы по корпорации (умнее быстрее, как я, PRINCIPLE_EXPERTS_FIRST, бэклог) закрыты** (2026-02-08): всё внедрено; см. CHANGES §0.4eg, MASTER_REFERENCE «Последние изменения».

---

## 2. Архив отчётов (docs/archive/)

| Что | Где | Описание |
|-----|-----|----------|
| Архив: общее описание | [archive/README.md](archive/README.md) | Структура архива, что куда перенесено. |
| Исторические отчёты из корня | [archive/root_reports/](archive/root_reports/) | COMPLETE_*, FINAL_*, VICTORIA_*, TELEGRAM_*, отчёты о миграции и статусах. Для текущей работы — docs/ (MASTER_REFERENCE, таблица §8). |
| Бэкапы исходников (.backup) | [archive/obsolete_backups/](archive/obsolete_backups/) | Файлы .backup из src/ и др.; текущий код — в рабочих каталогах. |

---

## 3. Программы обучения (learning_programs/)

Программы по экспертам (по имени): `learning_programs/<имя>_program.md` (например viktoriya_program.md, igor_program.md, anna_program.md). Список файлов — в каталоге [learning_programs/](../learning_programs/).

---

## 4. AI Insights (ai_insights/)

Файлы инсайтов по дате: `ai_insights/ai_insights_YYYYMMDD_HHMMSS.md`. Исторические записи; для актуальных выводов — **CHANGES_FROM_OTHER_CHATS** и **MASTER_REFERENCE** (последние изменения).

---

## 5. Отчёты куратора (curator_reports/)

| Что | Где | Описание |
|-----|-----|----------|
| Runbook куратора | [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md) | Прогон → чеклист → добавление эталонов в RAG. |
| Чеклист при разборе | [curator_reports/CURATOR_CHECKLIST.md](curator_reports/CURATOR_CHECKLIST.md) | Цепочка, качество, эталоны «как я». |
| Эталоны ответов | [curator_reports/standards/](curator_reports/standards/) | what_can_you_do, greeting, status_project, list_files, one_line_code. |
| Прогоны (JSON + превью) | curator_reports/curator_YYYY-MM-DD_HH-MM-SS.* | Результаты скрипта curator_send_tasks_to_victoria.py. |
| Выводы и аудит | curator_reports/FINDINGS_*.md, CORPORATION_FULL_AUDIT_*.md, VERIFICATION_*.md | Выводы куратора и полный аудит корпорации. |

---

## 6. Скрипты (E2E, coverage baseline)

| Что | Как запустить | Описание |
|-----|---------------|----------|
| E2E Playwright | `docker compose up -d` → `cd frontend && npm run e2e` | Тесты чата и health (§0.4g). |
| Coverage baseline | `bash knowledge_os/scripts/setup_knowledge_os.sh` → `./scripts/measure_coverage_baseline.sh` | Замер покрытия без БД; затем обновить COVERAGE_FAIL_UNDER в CI. |

---

## 7. Связь с библией

- **Главная точка входа по документации:** [MASTER_REFERENCE.md](MASTER_REFERENCE.md) §8 (таблица документов).
- **Изменения и контекст из чатов:** [CHANGES_FROM_OTHER_CHATS.md](CHANGES_FROM_OTHER_CHATS.md).
- **Недостатки и приоритеты:** [PROJECT_GAPS_ANALYSIS_2026_02_05.md](PROJECT_GAPS_ANALYSIS_2026_02_05.md).
- **TODO/FIXME backlog:** [TODO_FIXME_BACKLOG.md](TODO_FIXME_BACKLOG.md) — приоритизация по критичности; при правках — закрывать или обновлять.

При добавлении новых планов или отчётов — при необходимости обновить этот индекс и ссылку в MASTER_REFERENCE §8.
