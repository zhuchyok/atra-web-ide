# Agent Protocol

## Communication

### Message Bus

Agents communicate via **Redis Pub/Sub** (`agent_messaging.py`).

| Layer               | Transport                      | Format        | Persistence |
| ------------------- | ------------------------------ | ------------- | ----------- |
| Presence            | Redis Pub/Sub `agent:alive:*`  | JSON          | TTL 60s     |
| Direct message      | Redis Pub/Sub `agent:msg:*`    | JSON envelope | None        |
| Guaranteed delivery | Redis Streams `agent:stream:*` | JSON          | Persistent  |

### Message Envelope

```json
{
  "msg_id": "uuid",
  "from_agent": "Виктория",
  "to_agent": "Роман",
  "verb": "TELL | ASK | COUNTER | HANDOFF",
  "payload": { ... },
  "correlation_id": "optional-uuid",
  "requires_response": false,
  "timestamp": "2026-06-30T12:00:00Z"
}
```

Registered verbs (see `agent_message_registry.py`):

| Verb          | Purpose                        | Version |
| ------------- | ------------------------------ | ------- |
| `TELL`        | Fire-and-forget info           | 1.0     |
| `ASK`         | Request + response             | 1.0     |
| `PING`        | Liveness check                 | 1.0     |
| `OBSERVE`     | State observation              | 1.0     |
| `HANDOFF`     | Task delegation                | 1.0     |
| `BROADCAST`   | Publish to all                 | 1.0     |
| `COUNTER`     | Decline task (overload/policy) | 1.0     |
| `SUBCONTRACT` | Propose decomposition          | 1.0     |
| `CONFLICT`    | Verification conflict          | 1.0     |

### A2A Protocol (Google-compatible)

`a2a_protocol.py` provides an **Agent-to-Agent** compliance layer:

- **AgentCard**: capability advertisement (name, skills, url, auth)
- **A2ATask**: lifecycle states (SUBMITTED → WORKING → COMPLETED / FAILED)
- **Discovery**: `GET /a2a/agents/{name}/card` returns AgentCard JSON
- Auto-registers all DB experts as AgentCards on startup

### gRPC

`protos/agent_protocol.proto` defines a gRPC `AgentService`:

```protobuf
rpc ProcessTask(TaskRequest) returns (TaskResponse);
rpc GetHealth(HealthRequest) returns (HealthResponse);
rpc InitiateHandoff(HandoffRequest) returns (HandoffResponse);
```

Not used at runtime — exists for external agent compatibility.

---

## Task Distribution

### Blackboard Auction

```
Post Goal → Bidding → Resolve Auction → Claim → Execute
```

1. **Orchestrator** posts goal: `blackboard_service.post_goal(task_id, description, metadata)`
2. **Experts** bid: `blackboard_service.post_bid(task_id, expert_name, score)`
3. **Auction resolves**: highest bidder passes gates (routing policy, concurrency limit, counter-offer check)
4. **Winner claims**: `claim_task()` — atomic via Redis `SET NX` + heartbeat guard
5. **Winner executes**: task appears on expert's Redis Stream, `process_task()` runs

### Routing Gates (in order)

| Gate            | Config                             | Effect                               |
| --------------- | ---------------------------------- | ------------------------------------ |
| Bid threshold   | `BLACKBOARD_MIN_BID_SCORE` (0.4)   | Bids below threshold ignored         |
| Routing policy  | `BLACKBOARD_ENFORCE_TARGET_EXPERT` | Only target_expert may claim         |
| Verification    | `BLACKBOARD_VERIFICATION_EXPERTS`  | Only specified experts may verify    |
| R&D exclusion   | `BLACKBOARD_RD_EXCLUDED_EXPERTS`   | Excluded experts skip R&D tasks      |
| Capabilities    | `BLACKBOARD_EXPERT_CAPABILITIES`   | Required skills must match           |
| **Negotiation** | `COUNTER` message                  | Expert can decline (overload/policy) |
| Concurrency     | `MAX_EXPERT_HEAVY_TASKS` (2)       | Active task limit per expert         |

### Heartbeat / Release

- Claimed tasks publish heartbeat to `blackboard:heartbeat:{task_id}` (TTL 300s)
- If heartbeat expires → `run_gc_cycle()` reopens task for bidding
- On completion: `release_task()` removes from active set

---

## Adding a New Agent

1. **Create container** — add service in `docker-compose.agents.yml`:

   ```yaml
   my-agent:
     image: python:3.11-slim
     environment:
       - EXPERT_NAME=МойАгент
       - REDIS_URL=redis://redis:6379
     command: python -m app.expert_worker
   ```

2. **Register in DB** (via migration or API):

   ```sql
   INSERT INTO experts (name, role, system_prompt, department)
   VALUES ('МойАгент', 'My Role', 'You are an expert in ...', 'My Department');
   ```

3. **(Optional) A2A card**: auto-registered from `experts` table on startup

4. **Verify health**:
   ```bash
   curl localhost:8002/api/agents/health
   # Should see: {"name": "МойАгент", "alive": true, "active_tasks": 0}
   ```

---

## SLA & Monitoring

### Per-agent Prometheus metrics (exposed at `/metrics`)

| Metric                        | Type      | Labels                   |
| ----------------------------- | --------- | ------------------------ |
| `agent_task_duration_seconds` | Histogram | agent, task_type, status |
| `agent_errors_total`          | Counter   | agent, error_type        |
| `agent_tasks_processed_total` | Counter   | agent, status            |
| `agent_availability`          | Gauge     | agent                    |
| `agent_latency_p95_seconds`   | Gauge     | agent                    |

### Thresholds

| Metric       | Default Threshold                     | Status                              |
| ------------ | ------------------------------------- | ----------------------------------- |
| P95 latency  | `SLA_LATENCY_P95_THRESHOLD_SEC` = 30s | `healthy` / `degraded` / `critical` |
| Error rate   | `SLA_ERROR_RATE_THRESHOLD` = 0.05     |                                     |
| Availability | `SLA_AVAILABILITY_THRESHOLD` = 0.95   |                                     |

### Status endpoint

```bash
curl localhost:8002/api/agents/health
# Returns: {"agents": [{"name": "...", "alive": true, "active_tasks": 2, "sla": {...}}], "count": 6}
```

---

## Architecture Diagram

```
Task → Orchestrator → TaskDecomposer → ExpertMatchingEngine
  → Blackboard (post_goal → bids → resolve → claim)
  → Redis Stream: expert_tasks:{name}
  → Expert Worker (AgentBase subclass)
    → ai_core.run_smart_agent_async() → LLM
  → Result → tasks table + knowledge_nodes + SLA metrics
  → DependencyGraph.record_call()
  → StateCheckpoint.save()
```

### Cross-cutting

| Service                       | Role                                   |
| ----------------------------- | -------------------------------------- |
| `agent_messaging.py`          | Inter-agent Pub/Sub + Streams          |
| `agent_dependency_graph.py`   | Call graph tracking + D3 viz           |
| `agent_sla_metrics.py`        | Prometheus metrics + SLA reports       |
| `agent_message_registry.py`   | Schema validation + protobuf mapping   |
| `state_checkpoint.py`         | Full state save/restore/rollback       |
| `group_chat_state_machine.py` | Multi-agent conversation state machine |
| `code_sandbox.py`             | Docker-isolated code execution         |
| `a2a_protocol.py`             | Google A2A compliance                  |

---

## Testing

```bash
# Unit tests
pytest knowledge_os/tests/test_agent_messaging.py -v

# E2E (mocked LLM)
pytest knowledge_os/tests/test_e2e_full_cycle.py -v

# SLA
pytest knowledge_os/tests/test_agent_sla_metrics.py -v

# All agent tests
pytest knowledge_os/tests/test_agent_*.py -v
```

### CI/CD

- **Agent Tests**: GitHub Actions on push to `agent_*.py` / `expert_*.py` — spins up Postgres + Redis, runs unit tests
- **Agent Audit**: Weekly (Monday 6am) — all tests + dead code check + message schema validation
