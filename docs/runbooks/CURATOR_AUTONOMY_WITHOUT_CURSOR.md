# Runbook: Автономность куратора без Cursor/Claude

**Версия:** 1.0 · 2026-03-21  
**Проблема:** Если Cursor/Claude заблокируют — кто проверяет патчи Виктории?

---

## Текущее состояние (2026-03-21 — ОБНОВЛЕНО)

```
РАБОТАЕТ БЕЗ CURSOR:
  ✅ com.atra.curator-scheduled → run_curator_autonomous.sh (каждый день 9:00)
  ✅ victoria_self_curator.py — Victoria анализирует свои отчёты
  ✅ autonomous_remediation_executor.sh — исполняет задачи из БД
  ✅ SearXNG self-hosted — веб-поиск без внешних API
  ✅ STRICT_LOCAL guard — блокирует внешние модели
  ✅ FAST_PATCH_PATH — Victoria применяет патчи сама (< 200 мс, без LLM)
```

---

## Решение: два класса патчей

### TRUSTED (Victoria применяет сама)
Условия: один файл, < 10 строк, нет изменений интерфейса/API, confidence > 0.9

| Тип | Пример |
|---|---|
| `pip install` → `sys.exit(1)` | worker.py EMERGENCY REPAIR BLOCK |
| hardcoded строка → `os.getenv()` | DB_URL, conn_str |
| добавить пакет в requirements.txt | Pillow, pypdf |
| log сообщение с pip hint → правильный hint | _PIP_CMD → _INSTALL_MSG |

### CRITICAL (ждут человека в очереди БД)
- Меняют публичный API или интерфейс
- Security: JWT, пароли, токены
- Затрагивают 3+ файлов одновременно
- Архитектурные решения

---

## Как Victoria применяет TRUSTED патч сама

### Шаблон задачи (используй этот формат):

```json
{
  "goal": "Проверь knowledge_os/app/evaluator.py на антипаттерн asyncpg pip install в рантайме.\n\n1. Прочитай файл, найди EMERGENCY REPAIR BLOCK или subprocess pip install\n2. Если нашёл — это TRUSTED патч (заменить на sys.exit(1) + hint)\n3. Примени патч самостоятельно через write_file: перезапиши нужные строки\n4. Подтверди: 'ПРИМЕНЕНО: файл:строки' или 'ОК: антипаттерн не найден'",
  "project_context": "atra-web-ide",
  "max_steps": 20
}
```

### Ключевое: `"примени самостоятельно"` в goal
Victoria умеет писать файлы через tools (`write_file`, `apply_patch`).  
Без этой фразы — она только предлагает. С ней — применяет.

---

## Автономный цикл без Cursor (схема)

```
launchd 9:00 ежедневно
    ↓
run_curator_autonomous.sh
    ↓
Victoria прогоняет curator_tasks.txt
    ↓
victoria_self_curator.py анализирует отчёт
    ↓
Расхождение с эталоном?
  ДА → записать задачу в БД (tasks table)
       ↓
  autonomous_remediation_executor.sh
       ↓
  Victoria выполняет задачу:
    TRUSTED → apply сама → лог в curator_reports/
    CRITICAL → статус "awaiting_curator" в БД
       ↓
  Telegram-бот уведомляет: "Применено N патчей. Ожидают ревью: M"
```

---

## Проверить что автономный цикл работает сейчас

```bash
# 1. Проверить что launchd-задание активно
launchctl list | grep curator

# 2. Ручной прогон автономного куратора
bash scripts/run_curator_autonomous.sh

# 3. Посмотреть последний отчёт
ls -lt docs/curator_reports/ | head -5
cat docs/curator_reports/$(ls -t docs/curator_reports/*.md | head -1 | xargs basename)
```

---

## Что ещё нужно сделать (backlog)

| Задача | Приоритет | Через кого |
|---|---|---|
| Стабилизировать ReAct-цикл для tool execution (apply_patch без таймаута) | ВЫСОКИЙ | Victoria + Куратор |
| Telegram-уведомление при CRITICAL патче в очереди | СРЕДНИЙ | Victoria |
| Тест: Victoria применяет TRUSTED патч без Cursor | В РАБОТЕ — инфраструктура готова, ReAct нестабилен |

## Текущее ограничение (2026-03-21)

Victoria говорит `"ПРИМЕНЕНО"` через fast_path (без tool execution) — галлюцинация.
При отключении fast_path для патч-задач — ReAct-цикл виснет на 120 сек.

**Что сделано:**
- `apply_patch` зарегистрирован в tools Victoria
- `concrete_task_indicators` содержат "trusted патч", "apply_patch" и др.
- `is_vip = True` отключён для патч-задач (не bypass fast_path)

**Что не готово:**
- ReAct-цикл с tool execution: таймаут при реальном выполнении apply_patch

**Workaround:** TRUSTED патчи куратор применяет напрямую через Cursor StrReplace.
Цель: довести до 70% самостоятельного применения Victoria к концу апреля 2026.

---

## Связанные документы

- `docs/AUTONOMY_OFFLINE_READINESS.md` — полная карта офлайн-готовности
- `docs/CURATOR_RUNBOOK.md` — полный цикл куратора
- `docs/runbooks/VICTORIA_PATCH_WORKFLOW.md` — Victoria пишет патч → проверка → apply
- `scripts/victoria_self_curator.py` — скрипт самоанализа
- `scripts/run_curator_autonomous.sh` — автономный прогон без Cursor
