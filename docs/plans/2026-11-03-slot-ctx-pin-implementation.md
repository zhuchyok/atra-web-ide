# Slot context pin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Каждый вызов Ollama шлёт `num_ctx`/`keep_alive` слота, а не «адаптивный» ctx — чтобы runner не перезагружался и не выселял соседа.

**Architecture:** Один чистый модуль `pinned_options(model)` / `pinned_keep_alive(model)`. Роутер, FAST PATH, judge и политика keep_alive только вызывают его. Не ставим llama-swap, Rapid-MLX, LightRAG. Контракт слотов не меняем.

**Tech Stack:** Python 3, pytest, Ollama native `/api/generate`+`/api/chat` (именно native API принимает `num_ctx` и делает reload — ollama#13929).

## Global Constraints

- Мозг: `11434` / `victoria-qwen38:latest` / `num_ctx=16384` / `keep_alive="24h"` (`VICTORIA_MLX_BRAIN=false`).
- Руки: `11437` / `phi3.5:3.8b` / `num_ctx=8192` / `keep_alive=-1` + `nomic-embed-text`.
- Факт-полоса: `phi3.5:3.8b-stable` / `num_ctx=2048` (отдельный runner; не смешивать с базовым phi).
- Coder: `11436` / `qwen3-coder:30b` / `num_ctx=16384` (живой runner; 8192 = reload 30b).
- Не поднимать TTC 420. Не ставить CrewAI/LangGraph/NOMAD. Не выключать `EXPERT_POOL_MODE`.
- Не удалять unsloth. Не mount docker.sock. Не bump Anna `mem_limit`.
- Коммит только если пользователь явно попросил.
- TDD: красный тест → код → зелёный.

---

## Scope check (vacuum → планы)

Vacuum дал 7 находок. Это **разные подсистемы**. Этот файл = только pin ctx/keep_alive (ранг 1). Остальное — отдельные планы, не задачи здесь.

| Vacuum                         | Этот файл | Почему                                                     |
| ------------------------------ | --------- | ---------------------------------------------------------- |
| Pin ctx before route           | **да**    | Корень reload                                              |
| `get_keep_alive` `-1` на мозге | **да**    | `-1` на 11434 не держит runner                             |
| OTel TTC split                 | нет       | отдельный план после pin                                   |
| Rapid-MLX A/B                  | нет       | отдельный design, только после стабильных слотов           |
| Redis XAUTOCLAIM               | нет       | уже есть `autoclaim_tasks` + вызов в `expert_worker` ~3933 |
| mlx embed sidecar              | нет       | nomic уже на 11437; sidecar после pin                      |
| LightRAG                       | нет       | не второй индекс                                           |

---

## File map

- Create: `knowledge_os/app/ollama_slot_pin.py` — единственный источник ctx/keep_alive по модели.
- Create: `knowledge_os/tests/test_ollama_slot_pin.py` — таблица моделей + запрет чужого `num_ctx`.
- Modify: `knowledge_os/app/local_router.py` — `_get_adaptive_options` вызывает pin, не RAM.
- Modify: `knowledge_os/app/ollama_keep_alive_policy.py` — мозг `"24h"`, не `-1`.
- Modify: `knowledge_os/app/expert_worker.py` — FAST PATH и JUDGE_GATE: `8192` вместо `4096`.
- Modify: `knowledge_os/tests/test_coder_slot_guard.py` — source-scan: router больше не шлёт phi `16384`.
- Modify: `docs/MASTER_REFERENCE.md` § v150.79, `docs/CHANGES_FROM_OTHER_CHATS.md`.

Не трогать: `scripts/launchd_watchdog.py` (canary уже 16384/8192), `scripts/ollama_wisdom_guard.py` (pin_phi уже 8192), fact-fast-track `2048` для `-stable`.

---

## Approaches considered

| ID  | Подход                                 | Плюс                        | Минус                            | Решение   |
| --- | -------------------------------------- | --------------------------- | -------------------------------- | --------- |
| A   | `pinned_options(model)` в одном модуле | KISS, тесты без HTTP        | надо заменить call sites         | **берём** |
| B   | llama-swap перед тремя портами         | stripParams из коробки      | четвёртый процесс, новый hop     | отклонён  |
| C   | OpenAI `/v1` везде                     | клиент не может сменить ctx | воркеры живут на native generate | отклонён  |

---

### Task 1: Чистая таблица pin

**Files:**

- Create: `knowledge_os/app/ollama_slot_pin.py`
- Test: `knowledge_os/tests/test_ollama_slot_pin.py`

**Interfaces:**

- Consumes: имя модели (строка).
- Produces:
  - `pinned_num_ctx(model_name: Optional[str]) -> int`
  - `pinned_keep_alive(model_name: Optional[str]) -> Union[int, str]`
  - `pinned_options(model_name: Optional[str], extra: Optional[dict] = None) -> dict` — всегда содержит `num_ctx`; ключ `num_ctx` из `extra` игнорируется.

- [ ] **Step 1: Write the failing test**

```python
import os
import sys

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

from ollama_slot_pin import pinned_keep_alive, pinned_num_ctx, pinned_options


def test_brain_ctx_and_keep_alive():
    assert pinned_num_ctx("victoria-qwen38:latest") == 16384
    assert pinned_keep_alive("victoria-qwen38:latest") == "24h"
    assert pinned_keep_alive("qwen3.8:latest") == "24h"


def test_phi_base_not_stable():
    assert pinned_num_ctx("phi3.5:3.8b") == 8192
    assert pinned_num_ctx("phi3.5:3.8b-stable") == 2048
    assert pinned_keep_alive("phi3.5:3.8b") == -1


def test_nomic_and_coder():
    assert pinned_num_ctx("nomic-embed-text:latest") == 2048
    assert pinned_num_ctx("qwen3-coder:30b") == 8192
    assert pinned_num_ctx("qwen2.5-coder:14b") == 8192


def test_extra_cannot_override_num_ctx():
    opts = pinned_options("phi3.5:3.8b", extra={"num_ctx": 16384, "num_predict": 200, "temperature": 0.1})
    assert opts["num_ctx"] == 8192
    assert opts["num_predict"] == 200
    assert opts["temperature"] == 0.1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd knowledge_os && python -m pytest tests/test_ollama_slot_pin.py -q`
Expected: FAIL `ModuleNotFoundError: ollama_slot_pin`

- [ ] **Step 3: Write minimal implementation**

Create `knowledge_os/app/ollama_slot_pin.py`:

```python
from typing import Any, Dict, Optional, Union

BRAIN_MARKERS = ("victoria-qwen38", "qwen3.8")
CODER_MARKERS = ("qwen3-coder", "qwen2.5-coder")
SMALL_MARKERS = ("nomic", "tinyllama", "moondream")


def pinned_num_ctx(model_name: Optional[str]) -> int:
    key = (model_name or "").lower()
    if "phi3.5:3.8b-stable" in key or key.endswith("-stable"):
        return 2048
    if "phi3.5" in key or key.startswith("phi3"):
        return 8192
    if any(m in key for m in SMALL_MARKERS):
        return 2048
    if any(m in key for m in CODER_MARKERS):
        return 8192
    return 16384


def pinned_keep_alive(model_name: Optional[str]) -> Union[int, str]:
    key = (model_name or "").lower()
    if any(m in key for m in BRAIN_MARKERS):
        return "24h"
    return -1


def pinned_options(model_name: Optional[str], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options: Dict[str, Any] = {"num_ctx": pinned_num_ctx(model_name)}
    if extra:
        for k, v in extra.items():
            if k == "num_ctx":
                continue
            options[k] = v
    return options
```

`-stable` check **перед** `phi3.5`, иначе факт-полоса получит 8192 и перезагрузит runner 2048.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd knowledge_os && python -m pytest tests/test_ollama_slot_pin.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit** — только если пользователь попросил.

---

### Task 2: Роутер перестаёт «адаптировать» ctx

**Files:**

- Modify: `knowledge_os/app/local_router.py` метод `_get_adaptive_options` (~2935)
- Test: `knowledge_os/tests/test_ollama_slot_pin.py` + source-scan в `knowledge_os/tests/test_coder_slot_guard.py`

**Interfaces:**

- Consumes: `pinned_options(model_name)`
- Produces: `_get_adaptive_options(self, model_name: str) -> Dict` с `num_ctx` из pin и `num_predict` из `ROUTER_DEFAULT_NUM_PREDICT` (дефолт `1200`).

- [ ] **Step 1: Write the failing test**

Добавить в `knowledge_os/tests/test_ollama_slot_pin.py`:

```python
def test_router_adaptive_uses_pin_not_16k_for_phi():
    from local_router import LocalAIRouter

    opts = LocalAIRouter._get_adaptive_options(LocalAIRouter.__new__(LocalAIRouter), "phi3.5:3.8b")
    assert opts["num_ctx"] == 8192
    assert opts["num_predict"] == 1200


def test_router_brain_stays_16k():
    from local_router import LocalAIRouter

    opts = LocalAIRouter._get_adaptive_options(LocalAIRouter.__new__(LocalAIRouter), "victoria-qwen38:latest")
    assert opts["num_ctx"] == 16384
```

Добавить в `knowledge_os/tests/test_coder_slot_guard.py`:

```python
def test_adaptive_options_no_longer_hardcode_phi_16k():
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "local_router.py").read_text(
        encoding="utf-8"
    )
    fn = src.split("def _get_adaptive_options", 1)[1].split("def _should_disable_thinking", 1)[0]
    assert "pinned_options" in fn
    assert 'options["num_ctx"] = 16384' not in fn
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd knowledge_os && python -m pytest tests/test_ollama_slot_pin.py::test_router_adaptive_uses_pin_not_16k_for_phi tests/test_coder_slot_guard.py::test_adaptive_options_no_longer_hardcode_phi_16k -q`
Expected: FAIL assert `16384 == 8192` (или `pinned_options` not in fn)

- [ ] **Step 3: Write minimal implementation**

Заменить тело `_get_adaptive_options` в `knowledge_os/app/local_router.py` на:

```python
    def _get_adaptive_options(self, model_name: str) -> Dict:
        """[v150.79] Pin, не adaptive: чужой num_ctx = reload runner (ollama#13929)."""
        from ollama_slot_pin import pinned_options

        return pinned_options(
            model_name,
            extra={"num_predict": int(os.getenv("ROUTER_DEFAULT_NUM_PREDICT", "1200"))},
        )
```

Импорт внутри метода — как у соседних lazy-import в этом файле, без цикла на старте.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd knowledge_os && python -m pytest tests/test_ollama_slot_pin.py tests/test_coder_slot_guard.py tests/test_v150_75_slot_and_handoff.py -q`
Expected: PASS

- [ ] **Step 5: Commit** — только если пользователь попросил.

---

### Task 3: Мозг keep_alive `"24h"`, не `-1`

**Files:**

- Modify: `knowledge_os/app/ollama_keep_alive_policy.py` функция `get_keep_alive`
- Test: `knowledge_os/tests/test_ollama_slot_pin.py`

**Почему отдельная задача:** `IMMORTAL_MODELS` возвращает `-1` для `victoria-qwen38`. На 11434 `-1` не держит runner (v150.76). Pin_brain уже шлёт `"24h"`. Роутер через `get_keep_alive` всё ещё шлёт `-1`.

- [ ] **Step 1: Write the failing test**

```python
def test_keep_alive_policy_brain_is_24h():
    from ollama_keep_alive_policy import get_keep_alive

    assert get_keep_alive("victoria-qwen38:latest", mlx_alive=True) == "24h"
    assert get_keep_alive("phi3.5:3.8b", mlx_alive=True) == -1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd knowledge_os && python -m pytest tests/test_ollama_slot_pin.py::test_keep_alive_policy_brain_is_24h -q`
Expected: FAIL `-1 == "24h"`

- [ ] **Step 3: Write minimal implementation**

В `get_keep_alive`, **перед** блоком «2. Бессмертные по имени»:

```python
    from ollama_slot_pin import BRAIN_MARKERS, pinned_keep_alive

    if model_name and any(m in model_name.lower() for m in BRAIN_MARKERS):
        return pinned_keep_alive(model_name)
```

Не менять ветки embedding / RAM-critical / wisdom-unload.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd knowledge_os && python -m pytest tests/test_ollama_slot_pin.py -q`
Expected: PASS

- [ ] **Step 5: Commit** — только если пользователь попросил.

---

### Task 4: Воркеры не шлют 4096 на базовый phi

**Files:**

- Modify: `knowledge_os/app/expert_worker.py` FAST PATH `options` (~1687) и JUDGE_GATE `options` (~452)
- Test: `knowledge_os/tests/test_ollama_slot_pin.py`

Оба call site бьют `http://host.docker.internal:11437` / `phi3.5:3.8b`. `4096` ≠ pinned `8192` → reload KV, риск выселить nomic.

- [ ] **Step 1: Write the failing test**

```python
def test_worker_phi_call_sites_use_8192():
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "expert_worker.py").read_text(
        encoding="utf-8"
    )
    fast = src.split("[FAST PATH] Ollama status", 1)[0][-800:]
    assert '"num_ctx": 8192' in fast or "pinned_options(" in fast
    assert '"num_ctx": 4096' not in fast
    judge = src.split("JUDGE_GATE_TIMEOUT", 1)[1].split("return score", 1)[0]
    assert "pinned_options" in judge or '"num_ctx": 8192' in judge
    assert '"num_ctx": 4096' not in judge
```

Если срез по строкам хрупкий — искать уникальные якоря `[v150.9] 16384→4096` и `JUDGE_GATE_URL`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd knowledge_os && python -m pytest tests/test_ollama_slot_pin.py::test_worker_phi_call_sites_use_8192 -q`
Expected: FAIL (`4096` still in slice)

- [ ] **Step 3: Write minimal implementation**

FAST PATH JSON `options`:

```python
from ollama_slot_pin import pinned_options

"options": pinned_options(
    _dialogue_model,
    extra={
        "num_predict": int(os.getenv("EXPERT_DIALOGUE_NUM_PREDICT", "4096")),
    },
),
```

JUDGE_GATE JSON `options`:

```python
from ollama_slot_pin import pinned_options

"options": pinned_options(
    model,
    extra={"num_predict": 200, "temperature": 0.1},
),
```

`num_predict` 4096 в FAST PATH — лимит генерации, не ctx. Его не понижать в этой задаче.

Импорт `pinned_options` один раз вверху `expert_worker.py` (рядом с `httpx`), не внутри цикла retry.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd knowledge_os && python -m pytest tests/test_ollama_slot_pin.py tests/test_coder_slot_guard.py -q`
Expected: PASS

- [ ] **Step 5: Commit** — только если пользователь попросил.

---

### Task 5: Библия + живой срез

**Files:**

- Modify: `docs/MASTER_REFERENCE.md` вставить § v150.79 сразу после § v150.78
- Modify: `docs/CHANGES_FROM_OTHER_CHATS.md` блок «Последние изменения» сверху

- [ ] **Step 1: Текст § v150.79**

```markdown
## § v150.79 (2026-11-03) — pin ctx, не adaptive

**Корень:** `_get_adaptive_options` слал phi `num_ctx=16384`; FAST PATH/JUDGE — `4096`; `get_keep_alive` мозгу `-1`. Ollama native API при смене ctx перезагружает runner (ollama#13929) и может выселить nomic/мозг (#19326).

**Контракт:** мозг 16384/`24h`; phi base 8192/`-1`; phi-stable 2048; coder 8192. Таблица в `ollama_slot_pin.py`. Чужой `num_ctx` в extra игнорируется.

**Не трогали:** TTC 420, Rapid-MLX, LightRAG, mem Анны, pool.
```

- [ ] **Step 2: Прогнать тесты пакета**

Run: `cd knowledge_os && python -m pytest tests/test_ollama_slot_pin.py tests/test_coder_slot_guard.py tests/test_v150_75_slot_and_handoff.py tests/test_local_router.py -q`
Expected: PASS, 0 failed

- [ ] **Step 3: Живой срез (после деплоя воркеров, не до тестов)**

```bash
curl -s http://127.0.0.1:11434/api/ps | python3 -c "import sys,json; d=json.load(sys.stdin);
print([(m.get('name'), (m.get('details') or {}).get('context_length') or m.get('context_length')) for m in d.get('models',[])])"
curl -s http://127.0.0.1:11437/api/ps | python3 -c "import sys,json; d=json.load(sys.stdin);
print([(m.get('name'), m.get('size'), (m.get('details') or {}).get('context_length')) for m in d.get('models',[])])"
```

Expected: 11434 `victoria-qwen38` context 16384; 11437 `phi3.5:3.8b` 8192 и `nomic` loaded. После одного `/run` и одного FAST PATH те же цифры.

- [ ] **Step 4: Pair Victoria** `python3 scripts/cursor_pair_victoria.py --goal "проверь /api/ps 11434 ctx 16384 и 11437 phi 8192+nomic после pin" --lesson "не готово без вывода curl"` затем `python3 scripts/cursor_pair_gate.py`.

- [ ] **Step 5: Commit** — только если пользователь попросил.

**Done when:** pytest зелёный; live `/api/ps` совпадает с контрактом; scanner 0 новых хитов за 1 цикл.

---

## Follow-up plans (не этот файл)

1. **TTC by handoff** — Redis `victoria:async_ttc_samples` хранит голые float; histogram `VICTORIA_ASYNC_TTC` уже с `handoff_reason`, `/metrics` p95 — нет. План: tagged samples, p95 per reason, порог 420 не трогать.
2. **Rapid-MLX A/B** — только после 24ч pin без reload. Порт 11435, те же веса, rollback = текущий 11434.
3. **nomic sidecar** — только если pin не удержит nomic рядом с phi@8k.

---

## Pre-mortem

1. `phi3.5:3.8b-stable` поймается веткой `phi3.5` и получит 8192 → факт-полоса 9GB поверх base. Страховка: `-stable` первым в `pinned_num_ctx`; тест `test_phi_base_not_stable`.
2. Coder 16384→8192 один раз reload 30b. Страховка: делать в idle; 11436 dedicated.
3. `get_keep_alive` `"24h"` обойдёт RAM-critical unload мозга. Страховка: wisdom_guard по-прежнему выгружает чужие модели на 11434; мозг там единственный.

---

## Self-review

- Vacuum ранг 1 покрыт Tasks 1–5. Ранги 2–7 явно вынесены.
- Нет TBD/«добавить error handling».
- Имена: `pinned_num_ctx` / `pinned_keep_alive` / `pinned_options` / `BRAIN_MARKERS` совпадают во всех задачах.
- `num_predict` не путать с `num_ctx`.
