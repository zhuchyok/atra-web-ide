# План внедрения: Best Practices из 5 топовых проектов

**Дата:** 2026-02-24  
**Исходные аудиты:**

- `/Users/bikos/Downloads/tokio/AUDIT_REPORT.md` (9/10)
- `/Users/bikos/Downloads/langchain/AUDIT_REPORT.md` (8.5/10)
- `/Users/bikos/Downloads/llama.cpp/AUDIT_REPORT.md` (9/10)
- `/Users/bikos/Downloads/clap/AUDIT_REPORT.md` (9/10)
- `/Users/bikos/Downloads/turbo/AUDIT_REPORT.md` (8.5/10)

---

## 🎯 Сводная таблица: Топ-20 практик

| №   | Практика                 | Источник  | Компонент ATRA | Приоритет | Оценка ROI | Сложность |
| --- | ------------------------ | --------- | -------------- | --------- | ---------- | --------- |
| 1   | Graceful shutdown        | tokio     | Gateway        | 🔴 P0     | 10/10      | 1 день    |
| 2   | Runtime Builder          | tokio     | Gateway        | 🔴 P0     | 9/10       | 1 день    |
| 3   | Semaphore для chat       | tokio     | Gateway        | 🔴 P0     | 10/10      | 0.5 дня   |
| 4   | LCEL-цепочки             | langchain | Victoria       | 🔴 P0     | 9/10       | 3 дня     |
| 5   | Middleware для экспертов | langchain | Victoria       | 🔴 P0     | 10/10      | 2 дня     |
| 6   | Fallback LLM/experts     | langchain | Victoria       | 🔴 P0     | 9/10       | 2 дня     |
| 7   | clap_complete            | clap      | atra-cli       | 🔴 P0     | 8/10       | 1 день    |
| 8   | ValueHint paths          | clap      | atra-cli       | 🔴 P0     | 7/10       | 0.5 дня   |
| 9   | Retry exponential        | langchain | Backend        | 🟡 P1     | 8/10       | 1 день    |
| 10  | RouterRunnable           | langchain | Victoria       | 🟡 P1     | 7/10       | 2 дня     |
| 11  | JoinSet shutdown         | tokio     | Gateway        | 🟡 P1     | 6/10       | 1 день    |
| 12  | Streaming debug          | langchain | Victoria       | 🟡 P1     | 8/10       | 2 дня     |
| 13  | Квантование профили      | llama.cpp | MLX            | 🟡 P1     | 7/10       | 1 день    |
| 14  | Memory thresholds        | llama.cpp | MLX            | 🟡 P1     | 8/10       | 1 день    |
| 15  | Task hashing             | turbo     | CI/CD          | 🟡 P1     | 9/10       | 3 дня     |
| 16  | Local cache              | turbo     | CI/CD          | 🟡 P1     | 8/10       | 2 дня     |
| 17  | Colored help             | clap      | atra-cli       | 🟢 P2     | 5/10       | 0.5 дня   |
| 18  | Config file              | clap      | atra-cli       | 🟢 P2     | 6/10       | 1 день    |
| 19  | RunnableParallel         | langchain | Victoria       | 🟢 P2     | 6/10       | 1 день    |
| 20  | Remote cache             | turbo     | CI/CD          | 🟢 P2     | 7/10       | 5 дней    |

**Итого:** 35+ дней работы → разделим на фазы

---

## 📦 Фазы внедрения

### **Фаза 1: Gateway Critical (P0)** — 3 дня

**Цель:** Graceful shutdown, rate limiting, tuned runtime для rust_core/gateway.

#### Задачи:

1. **Graceful shutdown с signal::ctrl_c()**

   ```rust
   // rust_core/gateway/src/main.rs
   use tokio::signal;

   let shutdown_signal = async {
       signal::ctrl_c().await.expect("failed to listen for Ctrl-C");
       info!("SIGINT received, shutting down gracefully");
   };

   axum::serve(listener, app)
       .with_graceful_shutdown(shutdown_signal)
       .await?;
   ```

   **Файлы:** `rust_core/gateway/src/main.rs`  
   **Зависимости:** `tokio = { version = "1.49", features = ["signal"] }`  
   **Тесты:** `curl localhost:8081/health` + Ctrl-C → graceful shutdown без abort

2. **Runtime Builder вместо #[tokio::main]**

   ```rust
   fn main() -> Result<()> {
       let runtime = tokio::runtime::Builder::new_multi_thread()
           .worker_threads(4)  // Gateway — I/O-bound
           .max_blocking_threads(64)
           .thread_name("atra-gateway")
           .enable_all()
           .build()?;

       runtime.block_on(async { run_server().await })
   }
   ```

   **Файлы:** `rust_core/gateway/src/main.rs`  
   **Эффект:** Явный контроль над runtime, thread pool, метрики

3. **Semaphore для chat (MAX_CONCURRENT_CHAT=50)**

   ```rust
   // В AppState
   chat_semaphore: Arc<tokio::sync::Semaphore>,

   // В proxy_chat
   let _permit = state.chat_semaphore.acquire().await?;
   ```

   **Файлы:** `rust_core/gateway/src/main.rs`, `handlers/chat.rs`  
   **Эффект:** Backpressure, 503 при перегрузке (как в Python backend)

**Метрики:** Gateway latency -20%, 0 crashes при Ctrl-C, 503 при > 50 concurrent chat

---

### **Фаза 2: Victoria Core (P0)** — 7 дней

**Цель:** LCEL-подобная оркестрация, middleware, fallback для Victoria Enhanced.

#### Задачи:

1. **LCEL-цепочки для solve()**
   - Заменить `if complexity == "simple": ... elif == "swarm": ...` на `RunnableBranch` или граф.
   - Создать `OrchestratorChain` с шагами: `assess → route → execute → synthesize`.
   - **Файлы:** `knowledge_os/src/agents/implementations/victoria_enhanced.py`
   - **Зависимости:** рассмотреть `langchain-core` или собственную реализацию `Runnable` (без внешней зависимости)

2. **Middleware для экспертов**
   - Добавить хуки `before_expert`, `wrap_expert_call`, `after_expert` в Enhanced Orchestrator.
   - Реализовать retry, fallback, rate limit через middleware.
   - **Файлы:** `knowledge_os/src/agents/implementations/victoria_enhanced.py`, новый `expert_middleware.py`

3. **Fallback при недоступности Victoria/Veronica**
   - `with_fallbacks([primary_agent, backup_agent, hardcoded_response])`.
   - При 503/timeout → fallback.
   - **Файлы:** `backend/app/routes/chat.py`, `victoria_enhanced.py`

**Метрики:** Victoria timeout -50%, fallback hit rate, код читаемее (ветвление → граф)

---

### **Фаза 3: atra-cli UX (P0)** — 2 дня

**Цель:** Улучшить UX atra-cli: нативные completions, ValueHint, config file.

#### Задачи:

1. **clap_complete + --generate**

   ```toml
   [dependencies]
   clap_complete = "4.4"
   ```

   ```rust
   #[arg(long = "generate", value_enum)]
   generator: Option<Shell>,

   if let Some(shell) = cli.generator {
       clap_complete::generate(shell, &mut Cli::command(), "atra", &mut std::io::stdout());
       return Ok(());
   }
   ```

   **Файлы:** `rust_core/atra-cli/Cargo.toml`, `src/main.rs`  
   **Обновить:** `scripts/generate_completions.sh` → вызов `atra --generate bash/zsh/fish`

2. **ValueHint для путей**

   ```rust
   #[arg(value_hint = ValueHint::FilePath)]
   image_path: PathBuf,
   ```

   **Файлы:** `rust_core/atra-cli/src/main.rs` (Describe, Apply commands)

3. **Config file support**
   - Добавить `-c/--config <FILE>` с `ValueHint::FilePath`.
   - Загрузка TOML: `serde + toml`.
   - Merge с env (GATEWAY_URL, VICTORIA_URL).
   - **Файлы:** `rust_core/atra-cli/src/config.rs` (new), `main.rs`
   - **Формат:** `~/.config/atra/config.toml`:
     ```toml
     gateway_url = "http://localhost:8081"
     victoria_url = "http://localhost:8010"
     project_context = "atra-web-ide"
     ```

**Метрики:** atra-cli UX 9/10 (vs текущие 7/10)

---

### **Фаза 4: MLX Optimization (P1)** — 2 дня

**Цель:** Квантование профили, memory thresholds, метрики для mlx_api_server.

#### Задачи:

1. **Профиль квантования**

   ```python
   QUANT_PROFILE = {
       "reasoning": "Q4_K_M",  # qwen3-coder:30b
       "coding": "Q5_K_M",
       "fast": "Q4_0",
       "default": "Q8_0",
   }
   ```

   **Файлы:** `knowledge_os/app/mlx_api_server.py`, README

2. **Memory thresholds в /health**
   - `mx.metal.device()` (если доступно) → allocated_size, recommended_max.
   - При > 95% → агрессивная очистка.
   - **Файлы:** `mlx_api_server.py`

3. **Метрики: TTFT, tokens/s, load_time**
   - Логировать в `/health` или отдельный `/metrics`.
   - **Файлы:** `mlx_api_server.py`, ContinuousBatcher

**Метрики:** MLX memory usage -15%, TTFT на fast models -20%

---

### **Фаза 5: Victoria Advanced (P1)** — 4 дня

**Цель:** Retry с jitter, RouterRunnable, streaming debug для Victoria Enhanced.

#### Задачи:

1. **Retry с exponential jitter**
   - `tenacity` уже в зависимостях.
   - Обёртка для HTTP-вызовов Victoria/Veronica: `@retry(wait_exponential_jitter, stop_after_attempt=3)`.
   - **Файлы:** `backend/app/routes/chat.py`, `victoria_enhanced.py`

2. **RouterRunnable для экспертов**
   - Маршрутизация по `expert_id` или роли: `{"backend": igor_runnable, "qa": anna_runnable}`.
   - **Файлы:** `victoria_enhanced.py`, новый `expert_router.py`

3. **Streaming debug (astream_log-подобное)**
   - SSE: не только финальный ответ, но и шаги (`expert_called`, `expert_result`, `tool_used`).
   - **Файлы:** Backend `routes/chat.py`, frontend `src/components/Chat.svelte`

**Метрики:** Victoria retry success rate 95%, debug transparency 10/10

---

### **Фаза 6: CI/CD Task Caching (P1)** — 5 дней

**Цель:** Task hashing, local cache, change detection для CI.

#### Задачи:

1. **Создать atra.json**

   ```json
   {
     "tasks": {
       "rust_core:build": {
         "inputs": [
           "rust_core/**/*.rs",
           "rust_core/**/Cargo.toml",
           "Cargo.lock"
         ],
         "outputs": ["rust_core/target/"],
         "dependsOn": []
       },
       "knowledge_os:test": {
         "inputs": ["knowledge_os/**/*.py", "knowledge_os/requirements.txt"],
         "outputs": [],
         "dependsOn": ["knowledge_os:lint"]
       }
     }
   }
   ```

2. **Реализовать task hasher**
   - Python script: `scripts/task_hash.py` — вычисление хешей для каждой задачи.
   - Использовать xxHash64 или SHA256.

3. **Local cache в CI**
   - GitHub Actions: кэширование `.atra/cache` как artifact.
   - Hit → restore, skip execution.

4. **Change detection**
   - `git diff main...HEAD --name-only` → affected tasks.
   - Пропуск unaffected в CI.

**Метрики:** CI time -50%, cache hit rate 70%+

---

### **Фаза 7: Polishing (P2)** — 3 дня

**Цель:** Доработки atra-cli, RunnableParallel для Swarm, config optimizations.

#### Задачи:

1. **Colored help для atra-cli**
   - `#[command(styles = ATRA_STYLES)]` с cyan/magenta.
   - **Файлы:** `rust_core/atra-cli/src/main.rs`

2. **debug_assert тест для CLI**
   - `#[test] fn verify_cli() { Cli::command().debug_assert(); }`

3. **RunnableParallel для Swarm**
   - Заменить `asyncio.gather` на декларативный `RunnableParallel`.
   - **Файлы:** `victoria_enhanced.py` (Swarm logic)

4. **Remote cache (опционально)**
   - S3-backend для task cache.

**Метрики:** atra-cli UX 10/10, Swarm clarity

---

## 📊 Ожидаемые результаты

### Производительность:

| Компонент | Метрика       | Текущее           | Цель         | Источник  |
| --------- | ------------- | ----------------- | ------------ | --------- |
| Gateway   | Latency (p95) | ~300ms            | ~210ms       | tokio     |
| Gateway   | Shutdown time | Immediate (abort) | <2s graceful | tokio     |
| Victoria  | Timeout rate  | 2-3%              | <0.5%        | langchain |
| Victoria  | Code clarity  | 6/10              | 9/10         | langchain |
| atra-cli  | Completions   | Ручные            | Native       | clap      |
| atra-cli  | UX score      | 7/10              | 9/10         | clap      |
| MLX       | Memory spikes | 95%+              | <85%         | llama.cpp |
| CI        | Build time    | ~15 min           | ~7 min       | turbo     |
| CI        | Cache hit     | 0%                | 70%          | turbo     |

### Качество кода:

- Gateway: 9/10 (vs 7/10) — graceful shutdown, backpressure
- Victoria: 9/10 (vs 7/10) — LCEL-граф, middleware, fallback
- atra-cli: 9/10 (vs 7/10) — completions, config, colored help
- CI/CD: 9/10 (vs 6/10) — task cache, change detection

---

## 🚀 Roadmap

### Неделя 1 (P0, дни 1-5):

- День 1: Gateway graceful shutdown + Runtime Builder
- День 2: Gateway semaphore + тесты
- День 3-5: Victoria LCEL-цепочки (assess → route → execute → synthesize)

### Неделя 2 (P0, дни 6-10):

- День 6-7: Victoria middleware (retry, fallback, rate limit)
- День 8: Victoria fallback для LLM/experts
- День 9: atra-cli clap_complete + ValueHint
- День 10: atra-cli config file

### Неделя 3 (P1, дни 11-15):

- День 11: Backend retry exponential
- День 12: Victoria RouterRunnable
- День 13: Victoria streaming debug
- День 14: MLX квантование профили + memory thresholds
- День 15: Gateway JoinSet shutdown

### Неделя 4-5 (P1, дни 16-25):

- День 16-18: Task hashing для Cargo + Python
- День 19-20: Local cache в CI
- День 21-22: Change detection
- День 23-25: Тесты и документация

### Неделя 6 (P2, дни 26-28):

- День 26: atra-cli colored help + debug_assert
- День 27: Victoria RunnableParallel для Swarm
- День 28: Final polish

---

## 📝 Детальная разбивка по фазам

### **ФАЗА 1: Gateway Critical (P0)**

#### 1.1. Graceful Shutdown

**Файлы:** `rust_core/gateway/src/main.rs`

**Изменения:**

1. В `Cargo.toml`: `tokio = { version = "1.49", features = ["signal", "rt-multi-thread", "macros"] }`
2. Заменить:

   ```rust
   axum::serve(listener, app).await?;
   ```

   на:

   ```rust
   let shutdown = async {
       tokio::signal::ctrl_c().await.expect("failed to listen for Ctrl-C");
       tracing::info!("Received shutdown signal, gracefully stopping server");
   };

   axum::serve(listener, app)
       .with_graceful_shutdown(shutdown)
       .await?;
   ```

**Тест:**

```bash
cargo run --bin gateway &
sleep 2
curl http://localhost:8081/health
kill -SIGINT $!
# Должно завершиться gracefully за < 2s
```

#### 1.2. Runtime Builder

**Файлы:** `rust_core/gateway/src/main.rs`

**Изменения:**

1. Убрать `#[tokio::main]`
2. Создать runtime вручную:
   ```rust
   fn main() -> Result<()> {
       tracing_subscriber::fmt::init();

       let runtime = tokio::runtime::Builder::new_multi_thread()
           .worker_threads(num_cpus::get().min(4))
           .max_blocking_threads(64)
           .thread_name("atra-gateway-worker")
           .enable_all()
           .build()?;

       runtime.block_on(async {
           let app = create_app().await?;
           let listener = tokio::net::TcpListener::bind("0.0.0.0:8081").await?;

           let shutdown = async {
               tokio::signal::ctrl_c().await.expect("Ctrl-C listener failed");
               tracing::info!("Shutdown signal received");
           };

           axum::serve(listener, app)
               .with_graceful_shutdown(shutdown)
               .await?;

           Ok(())
       })
   }
   ```

**Зависимости:** `num_cpus = "1.16"` (опционально)

#### 1.3. Semaphore для chat

**Файлы:** `rust_core/gateway/src/main.rs`, `handlers/chat.rs` (или где proxy_chat)

**Изменения:**

1. В `AppState`:
   ```rust
   pub struct AppState {
       chat_semaphore: Arc<tokio::sync::Semaphore>,
       // ...
   }
   ```
2. Инициализация:
   ```rust
   let state = AppState {
       chat_semaphore: Arc::new(tokio::sync::Semaphore::new(50)),
   };
   ```
3. В handler:
   ```rust
   async fn proxy_chat(State(state): State<AppState>, ...) -> Result<...> {
       let permit = state.chat_semaphore
           .acquire()
           .await
           .map_err(|_| StatusCode::SERVICE_UNAVAILABLE)?;

       // Forward to Victoria
       let response = ...;

       drop(permit);
       Ok(response)
   }
   ```

**Тест:**

```bash
# Запустить 60 параллельных chat-запросов
for i in {1..60}; do
    curl -X POST http://localhost:8081/api/chat/stream -d '{"query":"test"}' &
done
# Ожидаем: первые 50 — в работе, последние 10 — ждут или 503
```

**Документация:** Обновить `docs/VICTORIA.md` (Gateway semaphore)

---

### **ФАЗА 2: Victoria Core (P0)**

#### 2.1. LCEL-подобные цепочки

**Файлы:** `knowledge_os/src/agents/implementations/victoria_enhanced.py`

**Текущее состояние:** `solve()` — условные ветвления по `complexity`, `use_consensus`, `use_extended_thinking`.

**Новая архитектура:**

1. Создать `OrchestratorRunnable` — базовый класс с методами `invoke`, `ainvoke`, `stream`, `astream`.
2. Реализовать `RunnableBranch` для маршрутизации:

   ```python
   from abc import ABC, abstractmethod

   class Runnable(ABC):
       @abstractmethod
       async def ainvoke(self, input: dict) -> dict:
           pass

   class RunnableBranch(Runnable):
       def __init__(self, branches: list[tuple[Callable, Runnable]], default: Runnable):
           self.branches = branches
           self.default = default

       async def ainvoke(self, input: dict) -> dict:
           for condition, runnable in self.branches:
               if condition(input):
                   return await runnable.ainvoke(input)
           return await self.default.ainvoke(input)
   ```

3. Заменить `solve()` на:
   ```python
   orchestrator_chain = (
       AssessComplexityRunnable()
       | RunnableBranch(
           [(lambda x: x["complexity"] == "simple", SimpleRunnable()),
            (lambda x: x["complexity"] == "swarm", SwarmRunnable()),
            (lambda x: x["use_consensus"], ConsensusRunnable())],
           default=ReactRunnable()
       )
   )
   return await orchestrator_chain.ainvoke({"goal": goal, "context": context})
   ```

**Преимущества:**

- Декларативность
- Лёгкое добавление новых стратегий
- Отладка (trace chain)

**Файлы:** `knowledge_os/src/agents/implementations/runnable.py` (new), `victoria_enhanced.py`

#### 2.2. Middleware для экспертов

**Файлы:** `knowledge_os/src/agents/implementations/expert_middleware.py` (new)

**Схема:**

```python
class ExpertMiddleware(ABC):
    @abstractmethod
    async def before_expert(self, expert_id: int, task: str, context: dict) -> dict:
        pass

    @abstractmethod
    async def wrap_expert_call(self, expert_id: int, task: str, next_handler):
        pass

    @abstractmethod
    async def after_expert(self, expert_id: int, result: dict) -> dict:
        pass

class RetryMiddleware(ExpertMiddleware):
    async def wrap_expert_call(self, expert_id, task, next_handler):
        @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter())
        async def call():
            return await next_handler(expert_id, task)
        return await call()

class FallbackMiddleware(ExpertMiddleware):
    async def wrap_expert_call(self, expert_id, task, next_handler):
        try:
            return await next_handler(expert_id, task)
        except ExpertUnavailable:
            return await fallback_expert(expert_id, task)

# Композиция
middleware_stack = [RetryMiddleware(), FallbackMiddleware(), RateLimitMiddleware()]
```

**Интеграция:** Enhanced Orchestrator вызывает `run_smart_agent_async` через middleware stack.

#### 2.3. Fallback для Victoria/Veronica

**Файлы:** `backend/app/routes/chat.py`, `victoria_enhanced.py`

**Реализация:**

```python
async def call_victoria_with_fallback(query: str) -> str:
    try:
        return await httpx.post(VICTORIA_URL, json={"query": query}, timeout=60)
    except (httpx.TimeoutException, httpx.ConnectError):
        tracing.warning("Victoria unavailable, trying Veronica fallback")
        return await httpx.post(VERONICA_URL, json={"query": query}, timeout=30)
    except Exception as e:
        tracing.error(f"All agents unavailable: {e}")
        return "Агенты временно недоступны. Попробуйте позже."
```

**Метрики:** Fallback hit rate, user-facing errors -80%

---

### **ФАЗА 3: atra-cli UX (P0)**

_(Уже описано выше)_

---

### **ФАЗА 4: MLX Optimization (P1)**

#### 4.1. Профиль квантования

**Файлы:** `knowledge_os/app/mlx_api_server.py`

**Изменения:**

```python
QUANT_PROFILE = {
    "reasoning": "mlx-community/Qwen3-Coder-30B-Q4_K_M",
    "coding": "mlx-community/Qwen3-Coder-30B-Q5_K_M",
    "fast": "mlx-community/Qwen3-Coder-8B-Q4_0",
    "default": "mlx-community/Qwen3-Coder-30B-Q8_0",
}

def get_model_by_profile(profile: str = "default") -> str:
    return QUANT_PROFILE.get(profile, QUANT_PROFILE["default"])
```

**API:** `POST /generate` с `?profile=reasoning` → выбор модели.

#### 4.2. Memory thresholds

**Файлы:** `mlx_api_server.py`

**Изменения:**

```python
import mlx.core as mx

def get_gpu_memory():
    try:
        device = mx.metal.device()
        allocated = device.currentAllocatedSize if hasattr(device, 'currentAllocatedSize') else None
        recommended_max = device.recommendedMaxWorkingSetSize if hasattr(device, 'recommendedMaxWorkingSetSize') else None
        return {"allocated": allocated, "max": recommended_max, "percent": (allocated / recommended_max * 100) if allocated and recommended_max else None}
    except:
        return None

@app.get("/health")
async def health():
    gpu = get_gpu_memory()
    if gpu and gpu["percent"] and gpu["percent"] > 95:
        mx.metal.clear_cache()
        gc.collect()
        return {"status": "critical", "gpu_memory": gpu}
    return {"status": "ok", "gpu_memory": gpu}
```

#### 4.3. Метрики inference

**Файлы:** `mlx_api_server.py`, ContinuousBatcher

**Добавить логи:**

- `load_time` — время загрузки модели
- `ttft` — time to first token
- `tokens_per_second` — throughput
- `memory_used` — GPU memory

---

### **ФАЗА 5: Victoria Advanced (P1)**

_(Уже описано выше)_

---

### **ФАЗА 6: CI/CD Task Caching (P1)**

#### 6.1. atra.json

**Файл:** `atra.json` (корень)

**Структура:**

```json
{
  "version": "1.0",
  "tasks": {
    "rust_core:build": {
      "inputs": ["rust_core/**/*.rs", "rust_core/**/Cargo.toml", "Cargo.lock"],
      "outputs": ["rust_core/target/release/"],
      "cache": true,
      "dependsOn": []
    },
    "rust_core:test": {
      "inputs": ["rust_core/**/*.rs", "rust_core/**/Cargo.toml"],
      "outputs": [],
      "cache": true,
      "dependsOn": ["rust_core:build"]
    },
    "knowledge_os:lint": {
      "inputs": ["knowledge_os/**/*.py", "knowledge_os/pyproject.toml"],
      "outputs": [],
      "cache": true,
      "dependsOn": []
    },
    "knowledge_os:test": {
      "inputs": ["knowledge_os/**/*.py", "knowledge_os/requirements.txt"],
      "outputs": [],
      "cache": true,
      "dependsOn": ["knowledge_os:lint"]
    },
    "frontend:build": {
      "inputs": [
        "frontend/src/**",
        "frontend/package.json",
        "frontend/package-lock.json"
      ],
      "outputs": ["frontend/dist/"],
      "cache": true,
      "dependsOn": []
    }
  },
  "cache": {
    "local": ".atra/cache",
    "remote": null
  }
}
```

#### 6.2. Task hasher

**Файл:** `scripts/task_hash.py`

**Логика:**

1. Парсить `atra.json`
2. Для каждой задачи:
   - Собрать файлы по `inputs` (globwalk или git ls-files)
   - Хеш файлов: `xxhash.xxh64(content).hexdigest()`
   - Dependency hashes: рекурсивно для `dependsOn`
   - Global hash: lockfile + env
   - Final hash: `xxhash.xxh64(json.dumps(sorted([global, files, deps, env])))`.
3. Сохранить в `.atra/hashes/{task_id}.json`

**Использование:**

```bash
python scripts/task_hash.py rust_core:build
# Output: hash: a3f8b2c...
```

#### 6.3. Local cache в CI

**Файл:** `.github/workflows/ci-with-cache.yml`

**Изменения:**

```yaml
- name: Restore task cache
  uses: actions/cache@v4
  with:
    path: .atra/cache
    key: atra-cache-${{ runner.os }}-${{ github.sha }}
    restore-keys: |
      atra-cache-${{ runner.os }}-

- name: Run tasks with cache
  run: |
    python scripts/task_runner.py rust_core:build rust_core:test
    # Если hash match — restore from cache, skip execution
```

#### 6.4. Change detection

**Файл:** `scripts/detect_changes.py`

**Логика:**

```python
import subprocess

def detect_changed_files(base_ref="main"):
    result = subprocess.run(
        ["git", "diff", f"{base_ref}...HEAD", "--name-only"],
        capture_output=True, text=True
    )
    return result.stdout.strip().split("\n")

def map_files_to_packages(files):
    packages = set()
    for f in files:
        if f.startswith("rust_core/"): packages.add("rust_core")
        elif f.startswith("knowledge_os/"): packages.add("knowledge_os")
        elif f.startswith("frontend/"): packages.add("frontend")
        elif f.startswith("backend/"): packages.add("backend")
        elif f in ["Cargo.lock", "Cargo.toml"]: packages.update(["rust_core"])
    return list(packages)

def affected_tasks(packages, atra_config):
    tasks = []
    for task_id, task in atra_config["tasks"].items():
        task_pkg = task_id.split(":")[0]
        if task_pkg in packages:
            tasks.append(task_id)
        # Check dependsOn cascade
    return tasks
```

**Использование в CI:**

```bash
CHANGED=$(python scripts/detect_changes.py)
python scripts/task_runner.py $CHANGED
```

---

### **ФАЗА 7: Polishing (P2)**

#### 7.1. Colored help

**Файлы:** `rust_core/atra-cli/src/main.rs`

```rust
use clap::builder::styling::{AnsiColor, Style};

const ATRA_STYLES: clap::builder::Styles = clap::builder::Styles::styled()
    .header(AnsiColor::Cyan.on_default().bold())
    .usage(AnsiColor::Magenta.on_default().bold())
    .literal(AnsiColor::Green.on_default())
    .placeholder(AnsiColor::Yellow.on_default())
    .error(AnsiColor::Red.on_default().bold());

#[derive(Parser)]
#[command(name = "atra", about = "...", styles = ATRA_STYLES)]
struct Cli { ... }
```

#### 7.2. debug_assert test

**Файлы:** `rust_core/atra-cli/tests/cli_tests.rs` (new)

```rust
#[test]
fn verify_cli() {
    use clap::CommandFactory;
    crate::Cli::command().debug_assert();
}
```

#### 7.3. RunnableParallel для Swarm

**Файлы:** `victoria_enhanced.py`

```python
class RunnableParallel(Runnable):
    def __init__(self, runnables: dict[str, Runnable]):
        self.runnables = runnables

    async def ainvoke(self, input: dict) -> dict:
        tasks = {key: runnable.ainvoke(input) for key, runnable in self.runnables.items()}
        results = await asyncio.gather(*tasks.values())
        return dict(zip(tasks.keys(), results))

# В Swarm:
parallel = RunnableParallel({"igor": igor_runnable, "anna": anna_runnable, ...})
results = await parallel.ainvoke({"goal": goal})
```

---

## 🔍 Зависимости

### Rust (Gateway, atra-cli):

```toml
tokio = { version = "1.49", features = ["signal", "rt-multi-thread", "macros"] }
clap_complete = "4.4"
num_cpus = "1.16"
```

### Python (Victoria, Backend):

```txt
# В requirements.txt уже есть tenacity
# Добавить при необходимости langchain-core (опционально, или реализовать Runnable сами)
```

---

## 📏 Критерии успеха

### Фаза 1 (Gateway):

- ✅ `curl http://localhost:8081/health` + Ctrl-C → graceful shutdown < 2s
- ✅ Load test: 60 concurrent chat → 50 ok, 10 queued (503)
- ✅ Latency p95 < 250ms

### Фаза 2 (Victoria):

- ✅ Timeout rate < 0.5%
- ✅ Fallback hit rate < 5% (при нормальной работе)
- ✅ Код читаемее: ветвление → граф (peer review 9/10)

### Фаза 3 (atra-cli):

- ✅ `atra --generate bash > completions/atra.bash`
- ✅ Tab в Zsh → file completion для `describe`
- ✅ `atra -c ~/.config/atra/config.toml chat "test"`

### Фаза 4 (MLX):

- ✅ `/health` с GPU memory
- ✅ При load > 95% → clear_cache
- ✅ TTFT для fast models < 2s

### Фаза 5 (Victoria Advanced):

- ✅ Retry успешность 95%+
- ✅ Streaming debug: `{"step": "expert_called", "expert": "Igor", "task": "..."}`

### Фаза 6 (CI/CD):

- ✅ Cache hit rate 70%+
- ✅ CI time для PR с 1 изменённым пакетом: < 5 мин
- ✅ Full CI: < 10 мин (vs 15 мин текущее)

### Фаза 7 (Polishing):

- ✅ atra-cli help с цветами
- ✅ debug_assert test проходит
- ✅ Swarm через RunnableParallel

---

## 📚 Документация

После каждой фазы обновлять:

- `docs/CHANGES_FROM_OTHER_CHATS.md` — раздел "0.6A–0.6G: Внедрение best practices из 5 топовых проектов"
- `docs/MASTER_REFERENCE.md` — соответствующие секции (Gateway, Victoria, atra-cli, MLX, CI/CD)
- `README.md` — новые возможности (graceful shutdown, native completions, task cache)
- Создать `docs/WORLD_CLASS_AUDIT_PHASE2_FINAL.md` — сводный отчёт (как `BEST_PRACTICES_FINAL.md`)

---

## ⚠️ Риски и зависимости

| Риск                       | Вероятность | Митигация                                                       |
| -------------------------- | ----------- | --------------------------------------------------------------- |
| LCEL-цепочки сложные       | Средняя     | Начать с простой версии (RunnableBranch без полного LCEL)       |
| Task hashing медленный     | Низкая      | Использовать git ls-files, xxHash (не SHA256), parallel hashing |
| Remote cache unavailable   | Низкая      | Graceful fallback на local                                      |
| Breaking changes в Gateway | Низкая      | Фича-флаги, постепенный rollout                                 |

---

## 🚀 Готовность к запуску

- [x] Все 5 проектов склонированы
- [x] Аудиты завершены
- [x] План создан
- [x] Приоритизация выполнена
- [ ] Начать Фазу 1

**Следующий шаг:** Внедрение Фазы 1 (Gateway Critical)
