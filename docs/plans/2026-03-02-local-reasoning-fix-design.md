# Design: Local-First Reasoning & Council Mode (Singularity 21.1)

## 1. Context & Problem

Expert dialogues (`ExpertCouncil`) and reasoning tasks are currently falling back to cloud models (`cursor-agent`) too early, consuming tokens.

- **Cause 1**: `_run_cloud_agent_async` hardcodes `category="general"`, losing VIP/Reasoning priority.
- **Cause 2**: Hybrid Strategist/Executor is limited to coding tasks.
- **Cause 3**: Fragile failover logic doesn't fully leverage the dual-brain (MLX + Ollama) availability of `victoria-wisdom-30b`.

## 2. Proposed Design: "The Local Reasoning Fortress"

### 2.1. Intelligent Routing Hierarchy

For `category="reasoning"` or `is_vip=True`:

1. **L1: MLX (Mac Studio)** - Highest priority, lowest latency.
2. **L2: Ollama (Mac Studio)** - Failover for the same `victoria-wisdom-30b` model.
3. **L3: Cloud (Last Resort)** - Only if L1 and L2 are confirmed offline via health-checks.

### 2.2. Key Changes

#### `ai_core.py`

- Modify `_run_cloud_agent_async` to accept `category` and `is_vip` parameters.
- Remove hardcoded `"general"` category.
- Implement a "Strict Local" attempt for reasoning tasks before even considering cloud.

#### `local_router.py`

- Refine `_is_echo_response`: Allow partial overlaps for expert dialogues (using `TEAM_PERSONALITIES` context).
- Ensure `X-Request-Priority: high` is injected for all reasoning/VIP tasks.
- Improve failover: If MLX fails, explicitly retry with Ollama using the same category.

#### `expert_council_discussion.py`

- Explicitly set `is_vip=True` for all expert opinions and final synthesis.

### 2.3. Error Handling & Failover

- If both local engines are offline, the system will log a `CRITICAL` warning and then fallback to cloud automatically to ensure service continuity.

## 3. Success Criteria

- [ ] 0 cloud tokens spent on expert dialogues when Mac Studio is online.
- [ ] `victoria-wisdom-30b` is used for >95% of reasoning tasks.
- [ ] No "Echo Response" false positives for expert реплик.

## 4. Implementation Plan (Next Step)

1. Update `ai_core.py` routing logic.
2. Update `local_router.py` failover and echo detection.
3. Update `expert_council_discussion.py` to use VIP flags.
4. Verify with `verify_dual_channel.py`.
