# Оптимизация архитектуры «Мозг и Руки» (MLX & Ollama) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Реализовать упреждающий прогрев (Predictive Warm-up), зеркалирование контекста через Redis и умное управление памятью для бесшовной работы MLX и Ollama.

**Architecture:**

- `local_router.py` становится центром управления Failover и прогревом.
- `ollama_keep_alive_policy.py` управляет жизненным циклом моделей с учетом Cooldown.
- `Redis` используется как хранилище "горячего" контекста для мгновенного переключения.

**Tech Stack:** Python, Redis, httpx, asyncio.

---

### Task 1: Умная политика памяти и Cooldown

**Files:**

- Modify: `knowledge_os/app/ollama_keep_alive_policy.py`

**Step 1: Обновить списки моделей и добавить константы**

```python
IMMORTAL_MODELS = {
    "nomic-embed-text",
    "moondream",
    "tinyllama",
    "phi3.5:3.8b"
}
RECOVERY_COOLDOWN_SECONDS = 300 # 5 минут
```

**Step 2: Реализовать логику Cooldown в get_keep_alive**
Нужно добавить отслеживание времени последнего сбоя MLX.

**Step 3: Commit**

```bash
git add knowledge_os/app/ollama_keep_alive_policy.py
git commit -m "feat: add immortal models and cooldown constants to ollama policy"
```

---

### Task 2: Зеркалирование контекста (Context Mirroring)

**Files:**

- Create: `knowledge_os/app/context_mirror.py`

**Step 1: Реализовать класс ContextMirror**

```python
import redis
import json

class ContextMirror:
    def __init__(self, redis_url):
        self.redis = redis.from_url(redis_url)

    async def save_context(self, session_id, history):
        self.redis.set(f"context:{session_id}", json.dumps(history), ex=3600)

    async def get_context(self, session_id):
        data = self.redis.get(f"context:{session_id}")
        return json.loads(data) if data else []
```

**Step 2: Commit**

```bash
git add knowledge_os/app/context_mirror.py
git commit -m "feat: implement ContextMirror for Redis integration"
```

---

### Task 3: Упреждающий прогрев и Failover в Router

**Files:**

- Modify: `knowledge_os/app/local_router.py`

**Step 1: Добавить метод \_trigger_predictive_warmup**

```python
async def _trigger_predictive_warmup(self, model_name):
    if await self._should_warmup():
        asyncio.create_task(self._warmup_ollama(model_name))
```

**Step 2: Интегрировать ContextMirror в run_local_llm**
Перед каждым запросом к MLX сохранять контекст, при ошибке — забирать для Ollama.

**Step 3: Реализовать логику переключения (Failover)**
Если MLX вернул ошибку, немедленно пробовать Ollama с подгруженным контекстом.

**Step 4: Commit**

```bash
git add knowledge_os/app/local_router.py
git commit -m "feat: integrate predictive warm-up and failover logic in local_router"
```

---

### Task 4: Мониторинг латентности (MLX Monitor)

**Files:**

- Create: `knowledge_os/app/mlx_monitor.py`

**Step 1: Реализовать отслеживание TBT (Time Between Tokens)**
Добавить запись времени между чанками в стриминге и расчет среднего.

**Step 2: Commit**

```bash
git add knowledge_os/app/mlx_monitor.py
git commit -m "feat: add MLX latency monitoring"
```
