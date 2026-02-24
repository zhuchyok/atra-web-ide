# Implementation Roadmap: Фазы 2-7

**Статус:** 🚀 EXECUTION IN PROGRESS  
**Фаза 1:** ✅ COMPLETE  
**Оставшиеся фазы:** 2-7 (26 дней → оптимизируем до 10-15 дней)

---

## Стратегия быстрого внедрения

Вместо последовательного выполнения (26 дней), делаем параллельно:

1. **Создать базовые компоненты** для всех фаз
2. **Реализовать MVP** каждой практики
3. **Задокументировать** и протестировать

---

## 🎯 Фаза 2: Victoria Core (УПРОЩЁННАЯ — 2 дня вместо 7)

### 2.1. Fallback для Victoria/Veronica (P0) — ПРИОРИТЕТ

**Файл:** `backend/app/routes/chat.py`

```python
# Добавить fallback при недоступности Victoria
async def call_victoria_with_fallback(query: str, context: dict):
    """Victoria → Veronica → Hardcoded response"""
    try:
        return await httpx.post(VICTORIA_URL, json={"query": query}, timeout=60)
    except (httpx.TimeoutException, httpx.ConnectError):
        logger.warning("Victoria unavailable, trying Veronica fallback")
        try:
            return await httpx.post(VERONICA_URL, json={"query": query}, timeout=30)
        except Exception:
            return {"response": "Агенты временно недоступны. Попробуйте позже."}
```

**Эффект:** Victoria timeout rate 2-3% → <0.5%

### 2.2. Retry с exponential backoff (P1)

**Файл:** `backend/app/config.py`

```python
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    reraise=True
)
async def call_victoria_with_retry(url: str, payload: dict):
    return await httpx.post(url, json=payload, timeout=60)
```

**LCEL-цепочки и Middleware:** Отложены (требуют рефакторинга Victoria Enhanced, ~5 дней)

---

## 🎯 Фаза 3: atra-cli UX (2 дня)

### 3.1. clap_complete + --generate

**Файл:** `rust_core/atra-cli/Cargo.toml`

```toml
[dependencies]
clap_complete = "4.4"
```

**Файл:** `rust_core/atra-cli/src/main.rs`

```rust
use clap_complete::{generate, Shell};

#[arg(long = "generate", value_enum)]
generator: Option<Shell>,

if let Some(shell) = cli.generator {
    generate(shell, &mut Cli::command(), "atra", &mut std::io::stdout());
    return Ok(());
}
```

### 3.2. ValueHint для путей

```rust
#[arg(value_hint = ValueHint::FilePath)]
image_path: PathBuf,
```

### 3.3. Config file support

```rust
#[arg(short, long, value_hint = ValueHint::FilePath)]
config: Option<PathBuf>,

// В main(): загрузка ~/.config/atra/config.toml
```

---

## 🎯 Фаза 4: MLX Optimization (1 день)

### 4.1. Профиль квантования

**Файл:** `knowledge_os/app/mlx_api_server.py`

```python
QUANT_PROFILE = {
    "reasoning": "mlx-community/Qwen3-Coder-30B-Q4_K_M",
    "fast": "mlx-community/Qwen3-Coder-8B-Q4_0",
    "default": "mlx-community/Qwen3-Coder-30B-Q8_0",
}

@app.post("/generate")
async def generate(req: GenerateRequest, profile: str = "default"):
    model = QUANT_PROFILE.get(profile, QUANT_PROFILE["default"])
    ...
```

### 4.2. Memory thresholds

```python
def get_gpu_memory():
    device = mx.metal.device()
    allocated = device.currentAllocatedSize if hasattr(device, 'currentAllocatedSize') else None
    max_mem = device.recommendedMaxWorkingSetSize if hasattr(device, 'recommendedMaxWorkingSetSize') else None
    return {"allocated": allocated, "max": max_mem, "percent": (allocated/max_mem*100) if allocated and max_mem else None}

@app.get("/health")
async def health():
    gpu = get_gpu_memory()
    if gpu and gpu["percent"] and gpu["percent"] > 95:
        mx.metal.clear_cache()
        gc.collect()
        return {"status": "critical", "gpu_memory": gpu}
    return {"status": "ok", "gpu_memory": gpu}
```

---

## 🎯 Фаза 5: Victoria Advanced (УПРОЩЁННАЯ — 1 день)

### 5.1. Streaming debug (добавить промежуточные шаги в SSE)

**Файл:** `backend/app/routes/chat.py`

```python
async def stream_with_debug(generator):
    """Добавить debug events в SSE stream"""
    async for chunk in generator:
        yield f"data: {json.dumps(chunk)}\n\n"

        # Debug events
        if "expert_called" in chunk:
            yield f"data: {json.dumps({'debug': 'expert_called', 'expert': chunk['expert']})}\n\n"
```

**RouterRunnable:** Отложен (зависит от LCEL-цепочек)

---

## 🎯 Фаза 6: CI/CD Task Caching (УПРОЩЁННАЯ — 2 дня)

### 6.1. Task hashing (MVP)

**Файл:** `scripts/task_hash.py`

```python
import hashlib, json, glob

def hash_task(task_id: str, inputs: list[str]) -> str:
    """Content-addressed hash для task"""
    files = []
    for pattern in inputs:
        files.extend(glob.glob(pattern, recursive=True))

    content_hash = hashlib.sha256()
    for f in sorted(files):
        with open(f, 'rb') as fp:
            content_hash.update(fp.read())

    return content_hash.hexdigest()[:16]
```

### 6.2. Change detection

```python
def detect_changed_packages(base_ref="main"):
    """Git diff → affected packages"""
    result = subprocess.run(
        ["git", "diff", f"{base_ref}...HEAD", "--name-only"],
        capture_output=True, text=True
    )
    files = result.stdout.strip().split("\n")
    packages = set()
    for f in files:
        if f.startswith("rust_core/"): packages.add("rust_core")
        elif f.startswith("knowledge_os/"): packages.add("knowledge_os")
        elif f.startswith("frontend/"): packages.add("frontend")
    return list(packages)
```

**Full Turbo implementation:** Отложен (5 дней работы)

---

## 🎯 Фаза 7: Polishing (1 день)

### 7.1. Colored help

```rust
const ATRA_STYLES: clap::builder::Styles = clap::builder::Styles::styled()
    .header(AnsiColor::Cyan.on_default().bold())
    .usage(AnsiColor::Magenta.on_default().bold())
    .error(AnsiColor::Red.on_default().bold());

#[derive(Parser)]
#[command(styles = ATRA_STYLES)]
struct Cli { ... }
```

### 7.2. debug_assert test

```rust
#[test]
fn verify_cli() {
    use clap::CommandFactory;
    Cli::command().debug_assert();
}
```

---

## ⚡ Итоговая оценка времени

| Фаза                 | Оригинальная оценка | MVP оценка    | Статус        |
| -------------------- | ------------------- | ------------- | ------------- |
| 1. Gateway           | 3 дня               | 2 часа        | ✅ DONE       |
| 2. Victoria Core     | 7 дней              | 2 дня         | 🚀 SIMPLIFIED |
| 3. atra-cli          | 2 дня               | 2 дня         | ✅ FULL       |
| 4. MLX               | 2 дня               | 1 день        | ✅ FULL       |
| 5. Victoria Advanced | 4 дня               | 1 день        | 🚀 SIMPLIFIED |
| 6. CI/CD             | 5 дней              | 2 дня         | 🚀 SIMPLIFIED |
| 7. Polishing         | 3 дня               | 1 день        | ✅ FULL       |
| **ИТОГО**            | **26 дней**         | **9-10 дней** | **-60%**      |

**MVP подход:** Берём 80% пользы за 40% времени.

---

## 📋 Порядок выполнения (оптимизированный)

1. ✅ **Фаза 1: Gateway** (2 часа) — DONE
2. 🚀 **Фаза 3: atra-cli** (2 дня) — Быстрый win, видимый результат
3. 🚀 **Фаза 4: MLX** (1 день) — Небольшая, высокий impact
4. 🚀 **Фаза 2: Victoria Fallback** (1 день) — Только fallback, без LCEL
5. 🚀 **Фаза 7: Polishing** (1 день) — Финальные штрихи
6. 🚀 **Фаза 6: CI/CD MVP** (2 дня) — Change detection + basic hashing
7. 🚀 **Фаза 5: Streaming debug** (1 день) — Последнее

**Общее время MVP:** 8-9 дней вместо 26

---

**НАЧИНАЕМ С ФАЗЫ 3 (atra-cli) — самая простая и видимая!**
