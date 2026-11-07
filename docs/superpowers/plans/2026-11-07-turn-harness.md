# Turn Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать ходу Виктории журнал JSONL, fail-closed одобрение, сдачу файлом и diff, потолок прав ребёнка и секрет-как-ссылку, не заменяя очередь `tasks` и не поднимая DeepSeek Harness.

**Architecture:** Новый пакет `knowledge_os/app/turn_harness/` — чистые функции и JSONL. Очередь Postgres и `session_context` остаются. В промпт попадает хвост журнала по бюджету, полный журнал лежит на диске. Каждый срез включается своим флагом и выключается тем же флагом.

**Tech Stack:** Python 3, stdlib (`json`, `os`, `fcntl`, `subprocess`), pytest, существующие хуки `victoria_server.py`, `expert_worker.py`, `victoria_telegram_bot.py`.

## Global Constraints

- Флаги по умолчанию выключены: `TURN_LOG=0`, `APPROVAL_FAIL_CLOSED=0`, `TURN_DELIVERABLE=0`, `CHILD_CEILING=off`, `CREDENTIAL_REF=0`.
- Каталог журнала: `TURN_LOG_DIR`, по умолчанию `logs/turns`. Перед включением `TURN_LOG=1` на живом процессе проверить, что каталог смонтирован с хоста.
- Причины закрытия хода, ровно этот набор: `completed`, `cancelled`, `timeout`, `max_steps`, `tool_error`, `approval_denied`, `crashed`.
- Исходы одобрения, ровно этот набор: `allowed-once`, `rejected`, `cancelled`, `unavailable`. Дальше пускает только `allowed-once`.
- Бюджет промпта журнала: `TURN_PROMPT_MAX_CHARS=12000`. Один результат тула: `TURN_TOOL_RESULT_MAX_CHARS=4000`. Блок `session_context` на 2000 символов не менять.
- В хвост промпта всегда входят: цель из `turn_opened`, последнее `approval_decided`, последний `tool_result` со статусом ошибки, последнее `files_presented`.
- Глубина ребёнка: больше 3 — нарушение. Режимы: `plan`, `accept_edits`, `dont_ask`.
- `output_schema` ребёнка — список обязательных ключей, не полный JSON Schema.
- Секрет в журнал, лог и `describe()` не попадает. Пустая строка значит «секрета нет».
- Очередь `tasks`, порты мозга/рук/кодера, Cordis и плагины DeepSeek в этот план не входят.

---

## File map

| Файл                                           | Ответственность                                                                                      |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `knowledge_os/app/turn_harness/events.py`      | append, replay, причина закрытия, хвост для промпта, sweep сирот                                     |
| `knowledge_os/app/turn_harness/approval.py`    | `decide()`, политика `ask`/`never`                                                                   |
| `knowledge_os/app/turn_harness/deliverable.py` | `presented` + `git diff --stat` по путям хода                                                        |
| `knowledge_os/app/turn_harness/child.py`       | глубина, режим, схема ответа                                                                         |
| `knowledge_os/app/turn_harness/credentials.py` | `resolve` / `describe`                                                                               |
| `knowledge_os/tests/test_turn_harness_*.py`    | по одному файлу на модуль                                                                            |
| `src/agents/bridge/victoria_server.py`         | открытие хода, закрытие в `finally`, sweep рядом с lifespan, approval, deliverable, metadata ребёнка |
| `knowledge_os/app/expert_worker.py`            | проверка потолка до `in_progress`                                                                    |
| `src/agents/bridge/victoria_telegram_bot.py`   | токен через `resolve` в момент отправки                                                              |

Порядок: события → врезка журнала → одобрение → сдача → ребёнок → секреты. Каждый таск зелёный без следующих флагов.

---

### Task 1: Журнал хода и причина закрытия

**Files:**

- Create: `knowledge_os/app/turn_harness/__init__.py`
- Create: `knowledge_os/app/turn_harness/events.py`
- Test: `knowledge_os/tests/test_turn_harness_events.py`

**Interfaces:**

- Consumes: ничего
- Produces:
  - `REASONS: frozenset[str]`
  - `append_event(log_dir: str, task_id: str, event_type: str, **fields) -> dict`
  - `read_events(log_dir: str, task_id: str) -> list[dict]`
  - `reason_for_store(store: dict) -> str`
  - `derive_prompt(events: list[dict], *, max_chars: int = 12000, tool_max: int = 4000) -> str`
  - `sweep_open_turns(log_dir: str) -> int`

- [ ] **Step 1: Write the failing test**

```python
import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "app" / "turn_harness" / "events.py"
_spec = importlib.util.spec_from_file_location("turn_harness_events", _PATH)
events = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(events)


def test_append_and_single_close(tmp_path):
    events.append_event(str(tmp_path), "t1", "turn_opened", goal="почини лог")
    events.append_event(str(tmp_path), "t1", "tool_result", status="error", text="x" * 5000)
    events.append_event(str(tmp_path), "t1", "turn_closed", reason="completed")
    rows = events.read_events(str(tmp_path), "t1")
    assert [r["type"] for r in rows] == ["turn_opened", "tool_result", "turn_closed"]
    assert rows[0]["seq"] == 1 and rows[-1]["seq"] == 3
    assert rows[-1]["reason"] == "completed"


def test_reason_for_store_prefers_explicit():
    assert events.reason_for_store({"status": "failed", "turn_end_reason": "max_steps"}) == "max_steps"
    assert events.reason_for_store({"status": "failed", "error": "Background timeout after 180s"}) == "timeout"
    assert events.reason_for_store({"status": "completed"}) == "completed"
    assert events.reason_for_store({"status": "cancelled"}) == "cancelled"
    assert events.reason_for_store({"status": "failed", "error": "boom"}) == "tool_error"


def test_derive_prompt_keeps_anchors_inside_budget():
    ev = [
        {"seq": 1, "type": "turn_opened", "goal": "цель-якорь"},
        {"seq": 2, "type": "tool_result", "status": "error", "text": "ОШИБКА-ЯКОРЬ " + ("z" * 8000)},
        {"seq": 3, "type": "approval_decided", "outcome": "allowed-once"},
        {"seq": 4, "type": "files_presented", "paths": ["src/a.py"]},
        {"seq": 5, "type": "model_message", "text": "m" * 20000},
    ]
    text = events.derive_prompt(ev, max_chars=12000, tool_max=4000)
    assert "цель-якорь" in text
    assert "allowed-once" in text
    assert "src/a.py" in text
    assert "ОШИБКА-ЯКОРЬ" in text
    assert len(text) <= 12000


def test_sweep_closes_orphan_as_crashed(tmp_path):
    events.append_event(str(tmp_path), "open1", "turn_opened", goal="g")
    events.append_event(str(tmp_path), "done1", "turn_opened", goal="g")
    events.append_event(str(tmp_path), "done1", "turn_closed", reason="completed")
    n = events.sweep_open_turns(str(tmp_path))
    assert n == 1
    last = events.read_events(str(tmp_path), "open1")[-1]
    assert last["type"] == "turn_closed" and last["reason"] == "crashed"
    assert events.sweep_open_turns(str(tmp_path)) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest knowledge_os/tests/test_turn_harness_events.py -v`

Expected: FAIL, `events.py` отсутствует.

- [ ] **Step 3: Write minimal implementation**

`knowledge_os/app/turn_harness/__init__.py` — пустой файл.

`knowledge_os/app/turn_harness/events.py`:

```python
"""Журнал одного хода: append-only JSONL. Промпт — проекция, не второе хранилище."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

REASONS = frozenset(
    {
        "completed",
        "cancelled",
        "timeout",
        "max_steps",
        "tool_error",
        "approval_denied",
        "crashed",
    }
)


def _path(log_dir: str, task_id: str) -> str:
    safe = "".join(c for c in task_id if c.isalnum() or c in "-_")
    if not safe:
        raise ValueError("task_id empty")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, safe + ".jsonl")


def append_event(log_dir: str, task_id: str, event_type: str, **fields) -> dict:
    path = _path(log_dir, task_id)
    seq = 1
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    seq += 1
    event = {
        "seq": seq,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": event_type,
        **fields,
    }
    if event_type == "turn_closed" and event.get("reason") not in REASONS:
        raise ValueError(f"bad reason: {event.get('reason')}")
    line = json.dumps(event, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        if os.name != "nt":
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        fh.write(line)
        fh.flush()
    return event


def read_events(log_dir: str, task_id: str) -> list:
    path = _path(log_dir, task_id)
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def reason_for_store(store: dict) -> str:
    explicit = store.get("turn_end_reason")
    if explicit in REASONS:
        return explicit
    status = store.get("status")
    if status == "completed":
        return "completed"
    if status == "cancelled":
        return "cancelled"
    err = str(store.get("error") or "").lower()
    if "timeout" in err:
        return "timeout"
    if status == "failed":
        return "tool_error"
    return "crashed"


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n…[обрезано]"


def derive_prompt(events: list, *, max_chars: int = 12000, tool_max: int = 4000) -> str:
    anchors = []
    rest = []
    for ev in events:
        kind = ev.get("type")
        if kind == "turn_opened":
            anchors.append("goal: " + str(ev.get("goal") or ""))
        elif kind == "approval_decided":
            anchors.append("approval: " + str(ev.get("outcome") or ""))
        elif kind == "files_presented":
            anchors.append("presented: " + ",".join(ev.get("paths") or []))
        elif kind == "tool_result" and ev.get("status") == "error":
            anchors.append("tool_error: " + _clip(str(ev.get("text") or ""), tool_max))
        elif kind == "tool_result":
            rest.append("tool: " + _clip(str(ev.get("text") or ""), tool_max))
        elif kind == "model_message":
            rest.append("model: " + str(ev.get("text") or ""))
    head = "\n".join(anchors)
    if len(head) > max_chars:
        return head[:max_chars]
    budget = max_chars - len(head) - (1 if head else 0)
    tail = []
    used = 0
    for piece in reversed(rest):
        if used + len(piece) + 1 > budget:
            break
        tail.append(piece)
        used += len(piece) + 1
    body = "\n".join(reversed(tail))
    if head and body:
        return head + "\n" + body
    return head or body


def sweep_open_turns(log_dir: str) -> int:
    if not os.path.isdir(log_dir):
        return 0
    closed = 0
    for name in os.listdir(log_dir):
        if not name.endswith(".jsonl"):
            continue
        task_id = name[: -len(".jsonl")]
        rows = read_events(log_dir, task_id)
        if rows and rows[-1].get("type") != "turn_closed":
            append_event(log_dir, task_id, "turn_closed", reason="crashed")
            closed += 1
    return closed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest knowledge_os/tests/test_turn_harness_events.py -v`

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/turn_harness/__init__.py knowledge_os/app/turn_harness/events.py knowledge_os/tests/test_turn_harness_events.py
git commit -m "feat: add append-only turn journal with a bounded prompt projection"
```

---

### Task 2: Врезка журнала в async /run

**Files:**

- Modify: `src/agents/bridge/victoria_server.py` (старт `_bounded_background_run` около строки 10159, `_mark_timeout` около 10176, `finally` около 10231, lifespan около 2188)
- Test: `knowledge_os/tests/test_turn_harness_events.py` (флаг `TURN_LOG`)

**Interfaces:**

- Consumes: `append_event`, `reason_for_store`, `sweep_open_turns` из Task 1
- Produces: при `TURN_LOG=1` файл `logs/turns/{task_id}.jsonl` с `turn_opened` и одним `turn_closed`. При флаге `0` файлов нет. `store["turn_end_reason"]` если выставлен раньше `finally`, побеждает в `reason_for_store`.

- [ ] **Step 1: Write the failing test**

Добавить в `knowledge_os/tests/test_turn_harness_events.py`:

```python
def test_flag_off_means_caller_skips(tmp_path, monkeypatch):
    monkeypatch.delenv("TURN_LOG", raising=False)
    assert events.logging_enabled() is False
    monkeypatch.setenv("TURN_LOG", "1")
    assert events.logging_enabled() is True
    monkeypatch.setenv("TURN_LOG_DIR", str(tmp_path))
    assert events.log_dir() == str(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest knowledge_os/tests/test_turn_harness_events.py::test_flag_off_means_caller_skips -v`

Expected: FAIL, `logging_enabled` отсутствует.

- [ ] **Step 3: Add flag helpers and wire three hooks**

В конец `events.py`:

```python
def logging_enabled() -> bool:
    return os.getenv("TURN_LOG", "0").strip().lower() in {"1", "true", "yes", "on"}


def log_dir() -> str:
    return os.getenv("TURN_LOG_DIR", "logs/turns")
```

В `victoria_server.py` добавить локальный хелпер рядом с `_fail_orphaned_inflight_on_startup`:

```python
def _turn_log():
    try:
        from app.turn_harness.events import (
            append_event,
            log_dir,
            logging_enabled,
            reason_for_store,
            sweep_open_turns,
        )
    except ImportError:
        from turn_harness.events import (
            append_event,
            log_dir,
            logging_enabled,
            reason_for_store,
            sweep_open_turns,
        )
    return append_event, log_dir, logging_enabled, reason_for_store, sweep_open_turns
```

В `lifespan`, сразу после `_create_tracked_task(_fail_orphaned_inflight_on_startup())`:

```python
    try:
        _append, _dir, _on, _reason, _sweep = _turn_log()
        if _on():
            n = _sweep(_dir())
            if n:
                logger.warning("[TURN] sweep closed %s open journals as crashed", n)
    except Exception as e:
        logger.warning("[TURN] sweep failed: %s", e)
```

В начале `_bounded_background_run`, до `bg_task = asyncio.ensure_future(task_coro)`:

```python
            try:
                _append, _dir, _on, _reason, _sweep = _turn_log()
                if _on():
                    _append(_dir(), task_id, "turn_opened", goal=str(task_data.get("goal") or "")[:2000])
            except Exception as e:
                logger.warning("[TURN] open failed task_id=%s: %s", task_id[:8], e)
```

В `_mark_timeout`, рядом с `store["error"] = ...`:

```python
                    store["turn_end_reason"] = "timeout"
```

В `finally`, после того как `status_final` попал в (`completed`, `failed`, `cancelled`) и до `_clear_async_inflight`:

```python
                        try:
                            _append, _dir, _on, _reason, _sweep = _turn_log()
                            if _on():
                                rows_reason = _reason(store)
                                _append(_dir(), task_id, "turn_closed", reason=rows_reason)
                                store["turn_end_reason"] = rows_reason
                        except Exception as e:
                            logger.warning("[TURN] close failed task_id=%s: %s", task_id[:8], e)
```

Отдельные `store["status"] = "completed"` не переписывать: `finally` закрывает журнал по статусу. Причина `max_steps` появляется только если код, который сам упёрся в лимит шагов, до `return` записал `store["turn_end_reason"] = "max_steps"`. Пока такой записи нет, лимит шагов закрывается как `tool_error` через `reason_for_store`.

- [ ] **Step 4: Run tests**

Run: `pytest knowledge_os/tests/test_turn_harness_events.py -v`

Expected: PASS.

Ручная проверка флага (процесс Виктории не обязателен):

```bash
TURN_LOG=0 python3 -c "import os; os.chdir('knowledge_os'); import importlib.util; from pathlib import Path; p=Path('app/turn_harness/events.py'); s=importlib.util.spec_from_file_location('e', p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.logging_enabled())"
```

Expected: `False`.

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/turn_harness/events.py knowledge_os/tests/test_turn_harness_events.py src/agents/bridge/victoria_server.py
git commit -m "feat: record async /run open and close in the turn journal"
```

---

### Task 3: Fail-closed одобрение

**Files:**

- Create: `knowledge_os/app/turn_harness/approval.py`
- Modify: `src/agents/bridge/victoria_server.py` блок «Проверка Human-in-the-Loop для критических действий» (сейчас зовёт `request_approval(action_type=..., action_data=...)` и `check_approval`, которых у `HumanApprovalSystem` нет, и исключение глотается)
- Test: `knowledge_os/tests/test_turn_harness_approval.py`

**Interfaces:**

- Consumes: `append_event`, `logging_enabled`, `log_dir` из Task 1. Журнал пишется только если `TURN_LOG=1`. Решение `decide` работает и без журнала.
- Produces: `async decide(*, task_id, tool_name, call_id, reason, policy, answerer) -> str`

`policy="never"` возвращает `rejected` и не вызывает `answerer`. `policy="ask"` вызывает `answerer`. Ответчик вернул не `allowed-once` и не `rejected`, бросил, или его нет — исход `unavailable`. `allowed-once` — единственный пропуск.

- [ ] **Step 1: Write the failing test**

```python
import asyncio
import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "app" / "turn_harness" / "approval.py"
_spec = importlib.util.spec_from_file_location("turn_harness_approval", _PATH)
approval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(approval)


def test_never_rejects_without_answerer():
    called = {"n": 0}

    async def answerer(_req):
        called["n"] += 1
        return "allowed-once"

    out = asyncio.run(
        approval.decide(
            task_id="t",
            tool_name="git_push",
            call_id="c1",
            reason="push",
            policy="never",
            answerer=answerer,
        )
    )
    assert out == "rejected"
    assert called["n"] == 0


def test_missing_answerer_is_unavailable():
    out = asyncio.run(
        approval.decide(
            task_id="t",
            tool_name="git_push",
            call_id="c1",
            reason="push",
            policy="ask",
            answerer=None,
        )
    )
    assert out == "unavailable"


def test_only_allowed_once_passes():
    async def ok(_req):
        return "allowed-once"

    async def junk(_req):
        return "yes"

    assert asyncio.run(approval.decide(task_id="t", tool_name="sh", call_id="c", reason="r", policy="ask", answerer=ok)) == "allowed-once"
    assert asyncio.run(approval.decide(task_id="t", tool_name="sh", call_id="c", reason="r", policy="ask", answerer=junk)) == "unavailable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest knowledge_os/tests/test_turn_harness_approval.py -v`

Expected: FAIL, модуль отсутствует.

- [ ] **Step 3: Implement `decide` and replace the broken call**

`knowledge_os/app/turn_harness/approval.py`:

```python
"""Один вопрос на одно действие. Пропуск только allowed-once."""

from __future__ import annotations

OUTCOMES = frozenset({"allowed-once", "rejected", "cancelled", "unavailable"})


async def decide(*, task_id, tool_name, call_id, reason, policy, answerer) -> str:
    if policy == "never":
        return "rejected"
    if policy != "ask":
        return "unavailable"
    if answerer is None:
        return "unavailable"
    try:
        raw = await answerer(
            {
                "task_id": task_id,
                "tool_name": tool_name,
                "call_id": call_id,
                "reason": reason,
            }
        )
    except Exception:
        return "unavailable"
    if raw in ("allowed-once", "rejected"):
        return raw
    return "unavailable"
```

В блоке Human-in-the-Loop в `victoria_server.py` оставить прежний код под `if os.getenv("APPROVAL_FAIL_CLOSED", "0") not in ("1", "true", "yes", "on")`. В ветке флага:

```python
            from app.turn_harness.approval import decide
            from app.turn_harness.events import append_event, log_dir, logging_enabled

            is_critical = any(
                marker in goal.lower()
                for marker in (
                    "деплой",
                    "deploy",
                    "удал",
                    "delete",
                    "rm ",
                    "api ключ",
                    "secret",
                    "пароль",
                )
            )
            if is_critical:
                policy = os.getenv("APPROVAL_POLICY", "never")
                if logging_enabled():
                    append_event(log_dir(), task_id, "approval_asked", tool_name="task_execution", reason=goal[:200])
                outcome = await decide(
                    task_id=task_id,
                    tool_name="task_execution",
                    call_id=task_id,
                    reason=goal[:200],
                    policy=policy,
                    answerer=None,
                )
                if logging_enabled():
                    append_event(log_dir(), task_id, "approval_decided", outcome=outcome)
                if outcome != "allowed-once":
                    store["status"] = "failed"
                    store["turn_end_reason"] = "approval_denied"
                    store["error"] = "Действие не одобрено: " + outcome
                    await _sync_store()
                    return
```

`answerer=None` на этом срезе сознательно: живого ответчика в Telegram ещё нет, поэтому `ask` тоже даёт `unavailable` и ход останавливается. Подключать `_pending_approvals` отдельным шагом только когда бот умеет ответить `allowed-once` на конкретный `call_id`. До этого ночной и фоновый прогон живут на `APPROVAL_POLICY=never`.

Тот же `decide` вызвать перед исполнением тулов `git_push` и шелла, если команда содержит `curl`, `wget` или `git push`. Пропуск только при `allowed-once`. В результат тула модели писать строку `отказано: {outcome}`, без текста аудита.

- [ ] **Step 4: Run tests**

Run: `pytest knowledge_os/tests/test_turn_harness_approval.py knowledge_os/tests/test_turn_harness_events.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/turn_harness/approval.py knowledge_os/tests/test_turn_harness_approval.py src/agents/bridge/victoria_server.py
git commit -m "fix: fail closed when a critical goal has no approval answer"
```

---

### Task 4: Сдача хода файлом и diff

**Files:**

- Create: `knowledge_os/app/turn_harness/deliverable.py`
- Modify: `src/agents/bridge/victoria_server.py` возврат `autonomous_code` около строки 13230
- Test: `knowledge_os/tests/test_turn_harness_deliverable.py`

**Interfaces:**

- Consumes: список путей, которые ход записал
- Produces: `build_deliverable(workspace: str, paths: list[str]) -> dict` с ключами `presented: list[str]` и `workspace_diff: str`

- [ ] **Step 1: Write the failing test**

```python
import importlib.util
import subprocess
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "app" / "turn_harness" / "deliverable.py"
_spec = importlib.util.spec_from_file_location("turn_harness_deliverable", _PATH)
deliverable = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deliverable)


def test_diff_is_limited_to_written_path(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    target = tmp_path / "src" / "a.py"
    target.parent.mkdir()
    target.write_text("print(1)\n")
    other = tmp_path / "src" / "noise.py"
    other.write_text("print(2)\n")
    got = deliverable.build_deliverable(str(tmp_path), ["src/a.py"])
    assert got["presented"] == ["src/a.py"]
    assert "src/a.py" in got["workspace_diff"]
    assert "noise.py" not in got["workspace_diff"]


def test_missing_git_is_explicit(tmp_path):
    (tmp_path / "a.py").write_text("x\n")
    got = deliverable.build_deliverable(str(tmp_path), ["a.py"])
    assert got["presented"] == ["a.py"]
    assert got["workspace_diff"].startswith("git_diff_unavailable")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest knowledge_os/tests/test_turn_harness_deliverable.py -v`

Expected: FAIL, модуль отсутствует.

- [ ] **Step 3: Implement and attach to autonomous-code**

`knowledge_os/app/turn_harness/deliverable.py`:

```python
"""Сдача хода: какие файлы записаны и их git diff --stat."""

from __future__ import annotations

import os
import subprocess


def build_deliverable(workspace: str, paths: list) -> dict:
    clean = []
    for raw in paths:
        rel = str(raw).replace("\\", "/").lstrip("/")
        if rel and ".." not in rel.split("/"):
            clean.append(rel)
    if not clean:
        return {"presented": [], "workspace_diff": ""}
    try:
        proc = subprocess.run(
            ["git", "diff", "--stat", "--", *clean],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"presented": clean, "workspace_diff": f"git_diff_unavailable: {e}"}
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "git failed").strip()
        return {"presented": clean, "workspace_diff": "git_diff_unavailable: " + err[:300]}
    stat = proc.stdout.strip()
    if not stat:
        proc2 = subprocess.run(
            ["git", "status", "--short", "--", *clean],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        stat = proc2.stdout.strip() or "(нет diff: файл совпадает с индексом или не под git)"
    return {"presented": clean, "workspace_diff": stat}
```

В `autonomous_code`, перед `return { ... "file_path": file_written ...}`:

```python
    deliverable_fields = {"presented": [], "workspace_diff": ""}
    if os.getenv("TURN_DELIVERABLE", "0").lower() in {"1", "true", "yes", "on"}:
        from app.turn_harness.deliverable import build_deliverable

        paths = [file_written] if file_written else []
        deliverable_fields = build_deliverable(workspace, paths)
        if final_stage == "passed" and file_path and (
            not deliverable_fields["presented"]
            or str(deliverable_fields["workspace_diff"]).startswith("git_diff_unavailable")
        ):
            final_stage = "deliverable_missing"
```

В возвращаемый dict добавить `"presented"` и `"workspace_diff"` из `deliverable_fields`. При `TURN_LOG=1` дописать событие `files_presented` с `paths=deliverable_fields["presented"]`.

- [ ] **Step 4: Run tests**

Run: `pytest knowledge_os/tests/test_turn_harness_deliverable.py -v`

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/turn_harness/deliverable.py knowledge_os/tests/test_turn_harness_deliverable.py src/agents/bridge/victoria_server.py
git commit -m "feat: require a path-scoped git diff before a code turn counts as passed"
```

---

### Task 5: Потолок ребёнка

**Files:**

- Create: `knowledge_os/app/turn_harness/child.py`
- Modify: `src/agents/bridge/victoria_server.py` `_dispatch_plan_step_to_stream` metadata около строки 13313
- Modify: `knowledge_os/app/expert_worker.py` сразу после чтения `metadata` и до `UPDATE ... in_progress` (около строки 1419)
- Test: `knowledge_os/tests/test_turn_harness_child.py`

**Interfaces:**

- Consumes: `metadata` задачи: `depth`, `permission_mode`, `allowed_tools`, `output_schema` (список ключей), `parent_task_id`
- Produces:
  - `ceiling_mode() -> str` значения `off` | `log` | `enforce`
  - `inspect_child(metadata: dict, tool_name: str) -> tuple[bool, str]`
  - `check_output(metadata: dict, result) -> tuple[bool, str]`

- [ ] **Step 1: Write the failing test**

```python
import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "app" / "turn_harness" / "child.py"
_spec = importlib.util.spec_from_file_location("turn_harness_child", _PATH)
child = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(child)


def test_depth_over_3_is_a_violation():
    ok, why = child.inspect_child({"depth": 4, "permission_mode": "plan"}, "read_file")
    assert ok is False and "depth" in why


def test_plan_cannot_write():
    ok, why = child.inspect_child({"depth": 1, "permission_mode": "plan"}, "write_file")
    assert ok is False and "plan" in why


def test_dont_ask_only_listed_tools():
    meta = {"depth": 1, "permission_mode": "dont_ask", "allowed_tools": ["read_file"]}
    assert child.inspect_child(meta, "read_file")[0] is True
    assert child.inspect_child(meta, "git_push")[0] is False


def test_output_schema_is_required_keys():
    meta = {"output_schema": ["file_path", "status"]}
    assert child.check_output(meta, {"file_path": "a.py", "status": "ok"})[0] is True
    ok, why = child.check_output(meta, {"file_path": "a.py"})
    assert ok is False and "status" in why


def test_ordinary_task_without_child_fields_is_allowed():
    assert child.inspect_child({}, "write_file") == (True, "")
    assert child.inspect_child({"source": "nightly"}, "git_push")[0] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest knowledge_os/tests/test_turn_harness_child.py -v`

Expected: FAIL, модуль отсутствует.

- [ ] **Step 3: Implement and gate the worker**

`knowledge_os/app/turn_harness/child.py`:

```python
"""Ребёнок не шире родителя. Хост задаёт режим, модель его не меняет."""

from __future__ import annotations

import os

MAX_DEPTH = 3
_PLAN_FORBIDDEN = {"write_file", "run_terminal_cmd", "ssh_run", "git_push"}
_EDIT_FORBIDDEN = {"git_push", "ssh_run"}


def ceiling_mode() -> str:
    mode = os.getenv("CHILD_CEILING", "off").strip().lower()
    if mode in {"log", "enforce"}:
        return mode
    return "off"


def inspect_child(metadata: dict, tool_name: str) -> tuple:
    if "permission_mode" not in metadata and "parent_task_id" not in metadata:
        return True, ""
    depth = int(metadata.get("depth") or 0)
    if depth > MAX_DEPTH:
        return False, f"depth {depth} > {MAX_DEPTH}"
    mode = str(metadata.get("permission_mode") or "plan")
    if mode == "plan" and tool_name in _PLAN_FORBIDDEN:
        return False, f"plan forbids {tool_name}"
    if mode == "accept_edits" and tool_name in _EDIT_FORBIDDEN:
        return False, f"accept_edits forbids {tool_name}"
    if mode == "dont_ask":
        allowed = set(metadata.get("allowed_tools") or [])
        if tool_name not in allowed:
            return False, f"dont_ask forbids {tool_name}"
    return True, ""


def check_output(metadata: dict, result) -> tuple:
    required = list(metadata.get("output_schema") or [])
    if not required:
        return True, ""
    if not isinstance(result, dict):
        return False, "result is not an object"
    missing = [key for key in required if key not in result]
    if missing:
        return False, "missing " + ",".join(missing)
    return True, ""
```

В `_dispatch_plan_step_to_stream` в `payload["metadata"]` добавить:

```python
            "parent_task_id": session_id,
            "depth": 1,
            "permission_mode": "accept_edits",
            "allowed_tools": ["read_file", "write_file", "list_directory"],
            "output_schema": ["file_path", "status"],
```

В `expert_worker.py` после того, как `metadata` уже разобран и до `UPDATE tasks SET status = 'in_progress'`:

```python
                    try:
                        from app.turn_harness.child import ceiling_mode, inspect_child
                    except ImportError:
                        from turn_harness.child import ceiling_mode, inspect_child
                    _ceiling = ceiling_mode()
                    if _ceiling != "off":
                        _ok, _why = inspect_child(metadata or {}, str((metadata or {}).get("requested_tool") or "write_file"))
                        if not _ok:
                            logger.warning("[CHILD] %s task=%s (%s)", _ceiling, task_id, _why)
                            if _ceiling == "enforce":
                                await conn.execute(
                                    "UPDATE tasks SET status = 'failed', updated_at = NOW(), "
                                    "metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb WHERE id = $1",
                                    db_task_id,
                                    json.dumps({"turn_end_reason": "tool_error", "child_violation": _why}),
                                )
                                return
```

Первую неделю на живом рое держать `CHILD_CEILING=log`. `enforce` включать после суток лога без чужих задач в `failed` по `child_violation`.

- [ ] **Step 4: Run tests**

Run: `pytest knowledge_os/tests/test_turn_harness_child.py -v`

Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/turn_harness/child.py knowledge_os/tests/test_turn_harness_child.py src/agents/bridge/victoria_server.py knowledge_os/app/expert_worker.py
git commit -m "feat: cap child expert depth and tools before the task starts"
```

---

### Task 6: Секрет как ссылка

**Files:**

- Create: `knowledge_os/app/turn_harness/credentials.py`
- Modify: `src/agents/bridge/victoria_telegram_bot.py` функция `send_telegram_message` (строки 240–249)
- Test: `knowledge_os/tests/test_turn_harness_credentials.py`

**Interfaces:**

- Consumes: `os.environ`
- Produces:
  - `resolve(ref: str) -> str | None`
  - `describe(ref: str) -> dict` ключи `ref`, `configured`, `source`

- [ ] **Step 1: Write the failing test**

```python
import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "app" / "turn_harness" / "credentials.py"
_spec = importlib.util.spec_from_file_location("turn_harness_credentials", _PATH)
credentials = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(credentials)


def test_empty_is_absent(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "   ")
    assert credentials.resolve("TELEGRAM_BOT_TOKEN") is None
    info = credentials.describe("TELEGRAM_BOT_TOKEN")
    assert info["configured"] is False
    assert "value" not in info
    assert info["ref"] == "TELEGRAM_BOT_TOKEN"


def test_resolve_reads_current_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-a")
    assert credentials.resolve("TELEGRAM_BOT_TOKEN") == "secret-a"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-b")
    assert credentials.resolve("TELEGRAM_BOT_TOKEN") == "secret-b"
    info = credentials.describe("TELEGRAM_BOT_TOKEN")
    assert info == {"ref": "TELEGRAM_BOT_TOKEN", "configured": True, "source": "env"}
    assert "secret" not in str(info)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest knowledge_os/tests/test_turn_harness_credentials.py -v`

Expected: FAIL, модуль отсутствует.

- [ ] **Step 3: Implement and use it at send time**

`knowledge_os/app/turn_harness/credentials.py`:

```python
"""В конфиге и в логе — имя переменной. Значение читается на операцию."""

from __future__ import annotations

import os


def resolve(ref: str):
    value = os.environ.get(ref, "")
    if not str(value).strip():
        return None
    return str(value)


def describe(ref: str) -> dict:
    return {
        "ref": ref,
        "configured": resolve(ref) is not None,
        "source": "env",
    }
```

В `send_telegram_message` заменить использование модуля-глобала `TELEGRAM_BOT_TOKEN` на чтение в момент отправки, под флагом `CREDENTIAL_REF`:

```python
    token = TELEGRAM_BOT_TOKEN
    if os.getenv("CREDENTIAL_REF", "0").lower() in {"1", "true", "yes", "on"}:
        from app.turn_harness.credentials import resolve

        token = resolve("TELEGRAM_BOT_TOKEN") or resolve("TG_TOKEN")
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
```

В лог этой функции токен не писать. Стартовое предупреждение «токен не установлен» перевести на `describe("TELEGRAM_BOT_TOKEN")["configured"]`, когда флаг включён.

- [ ] **Step 4: Run tests**

Run: `pytest knowledge_os/tests/test_turn_harness_credentials.py knowledge_os/tests/test_turn_harness_events.py knowledge_os/tests/test_turn_harness_approval.py knowledge_os/tests/test_turn_harness_deliverable.py knowledge_os/tests/test_turn_harness_child.py -v`

Expected: PASS, все тесты пакета.

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/turn_harness/credentials.py knowledge_os/tests/test_turn_harness_credentials.py src/agents/bridge/victoria_telegram_bot.py
git commit -m "feat: resolve the telegram token per send without logging it"
```

---

## Контрольный срез после Task 2

Один async `/run` при `TURN_LOG=1` оставляет `logs/turns/{task_id}.jsonl` с `turn_opened` и ровно одним `turn_closed`. `derive_prompt` содержит цель. `pending` / `in_progress` / `queued` ведут себя как до флага. При `TURN_LOG=0` каталог не пополняется.

## Вне плана

Порты 11434 / 11436 / 11437, замена `session_context`, новая таблица событий, подпись плагинов, песочница с закрытой сетью, живой ответчик Telegram для `ask`.
