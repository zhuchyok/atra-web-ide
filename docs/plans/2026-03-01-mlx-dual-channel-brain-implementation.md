# MLX Dual-Channel Intelligence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a dual-channel processing system in MLX to keep Victoria (30B) always in memory while allowing parallel execution of background tasks.

**Architecture:**

- Increase model cache to 5 to avoid disk I/O.
- Enable 2 concurrent slots in MLX (one reserved for Victoria).
- Use priority-based queuing to ensure Victoria never waits.

**Tech Stack:** Python, FastAPI, MLX, asyncio.

---

### Task 1: Environment Configuration

**Files:**

- Modify: `.env`

**Step 1: Update MLX parameters**
Modify `.env` to set:

```bash
MLX_MAX_CACHED_MODELS=5
MLX_MAX_CONCURRENT=2
MLX_PRELOAD_MODELS=fast,coding,victoria-wisdom-30b
```

**Step 2: Commit**

```bash
git add .env
git commit -m "config: update MLX cache and concurrency limits for dual-channel brain"
```

---

### Task 2: MLX Server Optimization

**Files:**

- Modify: `knowledge_os/app/mlx_api_server.py`

**Step 1: Implement Priority-Aware Semaphore**
Modify `mlx_api_server.py` to handle VIP requests.

```python
# Around line 134
_concurrent_semaphore = asyncio.Semaphore(_max_concurrent_requests)
_vip_semaphore = asyncio.Semaphore(1) # Dedicated slot for Victoria
```

**Step 2: Update `rate_limit_middleware` for VIP routing**
Modify the middleware to check for `X-Request-Priority: high` and use the `_vip_semaphore` if the model is Victoria.

**Step 3: Update `preload_models` logic**
Ensure it doesn't stop after the first model if memory allows.

**Step 4: Commit**

```bash
git add knowledge_os/app/mlx_api_server.py
git commit -m "feat: implement dual-channel priority queuing in MLX server"
```

---

### Task 3: Local Router Refinement

**Files:**

- Modify: `knowledge_os/app/local_router.py`

**Step 1: Hard-code VIP routing for reasoning**
Ensure `category="reasoning"` always adds `X-Request-Priority: high` header.

**Step 2: Commit**

```bash
git add knowledge_os/app/local_router.py
git commit -m "feat: enforce VIP routing for reasoning tasks in local_router"
```

---

### Task 4: Verification & Stress Test

**Files:**

- Create: `scripts/test_dual_channel_mlx.py`

**Step 1: Write stress test script**
Create a script that sends a heavy request to Victoria and a light request to Phi-3.5 simultaneously and measures if they run in parallel.

**Step 2: Run verification**

```bash
python3 scripts/test_dual_channel_mlx.py
```

Expected: Both requests return successfully without waiting for each other.

**Step 3: Commit**

```bash
git add scripts/test_dual_channel_mlx.py
git commit -m "test: add dual-channel MLX verification script"
```
