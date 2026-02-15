# Отчёты куратора — индекс

**Назначение:** быстрый обзор содержимого каталога. Полный runbook: [CURATOR_RUNBOOK.md](../CURATOR_RUNBOOK.md).

---

## Постоянные документы

| Файл | Описание |
|------|----------|
| [CURATOR_CHECKLIST.md](CURATOR_CHECKLIST.md) | Чеклист при разборе отчётов (цепочка, качество, эталоны). |
| [standards/](standards/) | Эталоны ответов (what_can_you_do, greeting, status_project, list_files, one_line_code). |
| [standards/README.md](standards/README.md) | Как добавлять эталоны и как переносить в RAG. |
| [CURATOR_LIST_FILES_FAILURES.md](CURATOR_LIST_FILES_FAILURES.md) | Причина сбоев «список файлов» (connection reset) и что делать при следующих. |

---

## Отчёты и выводы (2026-02-08)

| Файл | Описание |
|------|----------|
| [CORPORATION_FULL_AUDIT_2026-02-08.md](CORPORATION_FULL_AUDIT_2026-02-08.md) | Полный аудит связки корпорации, баги, быстродействие. |
| [VERIFICATION_2026-02-08.md](VERIFICATION_2026-02-08.md) | Тесты, исправленные недочёты, ссылка на аудит. |
| [FINDINGS_2026-02-08.md](FINDINGS_2026-02-08.md) | Выводы куратора (первый прогон). |
| [FINDINGS_2026-02-08_full_run.md](FINDINGS_2026-02-08_full_run.md) | Выводы по полному прогону (5 задач). |
| curator_2026-02-08_22-51-44.* | Полный прогон (привет, статус, список файлов, что умеешь, код). |
| curator_2026-02-08_23-08-43.* | Повторный полный прогон: 4/5 success; «список файлов» — error после retry (connection reset). |
| curator_2026-02-08_23-16-02.* | Полный прогон после правок: **5/5 success**; «список файлов» — success (92.7 с); retry GET /run/status + DELEGATE_VERONICA_TIMEOUT=90. |
| curator_*_findings.md | Выводы по отдельным прогонам. |

---

## Как запустить прогон

```bash
./scripts/run_curator.sh
# или полный:
./scripts/run_curator.sh --file scripts/curator_tasks.txt --async --max-wait 600
```

Добавить эталоны в RAG: `DATABASE_URL=... python3 scripts/curator_add_standard_to_knowledge.py`
