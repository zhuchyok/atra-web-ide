# ATRA Web IDE — Agent Instructions

## Quick Start
```bash
# Start services (MLX, Ollama, Postgres, workers)
docker compose up -d

# Start Victoria API
cd knowledge_os && uvicorn app.main:app --host 0.0.0.0 --port 8010
```

## Key Directories
- `knowledge_os/app/` — Core AI agents (Victoria, orchestrators, workers)
- `knowledge_os/db/` — PostgreSQL schema and migrations
- `backend/` — Rust core components
- `frontend/` — React/TypeScript UI

## Critical Commands

### Run Victoria (main API)
```bash
uvicorn knowledge_os.app.main:app --host 0.0.0.0 --port 8010
```

### Query tasks status (DB)
```bash
docker exec knowledge_postgres psql -U admin -d knowledge_os -c "SELECT status, count(*) FROM tasks GROUP BY status;"
```

### Check services
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## Common Issues

### "Solved:" or "ЗАДАЧА:" in responses
- Check `ai_core.py` — `_clean_response()` should filter metadata markers
- Check `VictoriaEnhanced.solve()` — should call `run_smart_agent_async`, not return stub

### Hallucinations
- Ensure anti-hallucination prompt is injected in `ai_core.py` for Victoria
- System relies on `victoria-wisdom-v3.5` model via MLX (port 11435)

### Database not accessible
- Use `docker exec knowledge_postgres psql -U admin -d knowledge_os` instead of local `psql`
- Default: `postgresql://admin:secret@localhost:6432/knowledge_os`

### Worker stuck tasks
- Check Redis queue: `knowledge_os/app/redis_manager.py`
- Task states: `pending`, `in_progress`, `completed`, `cancelled`
- Auto-requeue: see `smart_worker_autonomous.py`

## Testing
```bash
pytest knowledge_os/tests/
```

## Env Configuration
- Main config: `.env` in knowledge_os/
- Model settings: `VICTORIA_MODEL`, `VICTORIA_MLX_BRAIN=true`
- Timeouts: `MLX_GENERATION_TIMEOUT=600`, `SMART_WORKER_MAX_PENDING=1000`

## Advanced Components (Singularity 28.X)

### Symbol Tuning (symbol_tuner.py)
- 8 behavior symbols: concise, detailed, creative, diplomatic, technical, educational, fast, safe
- Usage: `from symbol_tuner import get_symbol_tuner; tuner = get_symbol_tuner()`

### Constitutional Rewards (constitutional_rewards.py)
- Penalties for: hallucination (-0.5), ignored_data (-0.3), security_risk (-0.4)
- Rewards for: constitutional_compliance (+0.3), self_correction (+0.2), helped_user (+0.5)
- Usage: `from constitutional_rewards import get_constitutional_rewards`

### Toil Detection (toil_detector.py)
- Auto-detects repetitive tasks
- Usage: `from toil_detector import get_toil_detector; detector = get_toil_detector()`

### Wisdom Pipeline (agent_ab_testing.py)
- Auto-generates wisdom rules from A/B results
- Usage: `ab_test = get_agent_ab_testing(); await ab_test.generate_wisdom_rules(7)`