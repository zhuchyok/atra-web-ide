import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from app.redis_manager import get_redis_manager
except ImportError:
    from redis_manager import get_redis_manager

logger = logging.getLogger("BlackboardService")


class BlackboardService:
    """
    [SINGULARITY 28.0] Shared Blackboard Service.
    A schema-validated space for agents to collaboratively build complex solutions.
    Implements Semantic Locking to prevent contradictory insights.
    [SINGULARITY 30.1] Redis-based Token Bucket Rate Limiter.
    Prevents 'Thundering Herd' effects by limiting heavy task claims and LLM inference.
    Refill rate is proportional to system resources (ice_mode).
    """

    def __init__(self):
        self.redis = get_redis_manager()
        self.key_prefix = "blackboard:"
        self.limiter_key = "limiter:global_tokens"
        self.metrics_key = f"{self.key_prefix}metrics"
        # [SINGULARITY 30.1] Limiter config
        self.max_tokens = 50.0  # [SINGULARITY 31.2] Increased for high load
        self.refill_rate_normal = 25.0  # [SINGULARITY 31.2] Increased for high load
        self.refill_rate_ice = 2.0  # tokens per second (resource saving)
        # [ROUTING POLICY] Keep distillation owner (Roman) out of RD/VERIFY contention by default.
        self.enforce_target_expert = os.getenv(
            "BLACKBOARD_ENFORCE_TARGET_EXPERT", "true"
        ).lower() in (
            "true",
            "1",
            "yes",
        )
        self.verification_experts = self._csv_set(
            os.getenv("BLACKBOARD_VERIFICATION_EXPERTS", "Анна,Алексей")
        )
        self.rd_excluded_experts = self._csv_set(os.getenv("BLACKBOARD_RD_EXCLUDED_EXPERTS", ""))
        self.expert_capabilities = self._parse_expert_capabilities(
            os.getenv("BLACKBOARD_EXPERT_CAPABILITIES", "")
        )

    async def _incr_metric(self, metric_name: str, value: int = 1):
        """Best-effort metric counter in Redis for routing/SLA observability."""
        try:
            client = await self.redis.get_client()
            await client.hincrby(self.metrics_key, metric_name, int(value))
            await client.hset(
                self.metrics_key, "updated_at", datetime.now(timezone.utc).isoformat()
            )
        except Exception as metric_err:
            logger.debug(f"Failed to increment metric {metric_name}: {metric_err}")

    @staticmethod
    def _csv_set(raw: Optional[str]) -> set:
        if not raw:
            return set()
        return {item.strip() for item in raw.split(",") if item and item.strip()}

    @staticmethod
    def _parse_expert_capabilities(raw: Optional[str]) -> Dict[str, set]:
        """
        Parse capability map from env:
        BLACKBOARD_EXPERT_CAPABILITIES="Роман:research,rd,backend;Анна:verification,qa"
        """
        mapping: Dict[str, set] = {}
        if not raw:
            return mapping
        for chunk in raw.split(";"):
            chunk = chunk.strip()
            if not chunk or ":" not in chunk:
                continue
            expert, caps_raw = chunk.split(":", 1)
            expert = expert.strip()
            caps = {c.strip() for c in caps_raw.split(",") if c.strip()}
            if expert and caps:
                mapping[expert] = caps
        return mapping

    @staticmethod
    def _extract_required_capabilities(metadata: Dict[str, Any]) -> set:
        required = set()
        if not isinstance(metadata, dict):
            return required
        direct_caps = metadata.get("required_capabilities")
        if isinstance(direct_caps, list):
            required.update(str(item).strip() for item in direct_caps if str(item).strip())
        contract = metadata.get("contract")
        if isinstance(contract, dict):
            contract_caps = contract.get("required_capabilities")
            if isinstance(contract_caps, list):
                required.update(str(item).strip() for item in contract_caps if str(item).strip())
        return required

    def _is_expert_eligible_for_goal(
        self, expert_name: str, task_id: str, goal_data: Dict[str, Any]
    ) -> tuple[bool, str]:
        metadata = (goal_data or {}).get("metadata", {}) or {}
        target_expert = metadata.get("target_expert")

        if self.enforce_target_expert and target_expert and target_expert != expert_name:
            return False, f"target_expert={target_expert}"

        task_id_str = str(task_id)
        category = str(metadata.get("category", "")).lower()
        is_verification = bool(metadata.get("is_verification")) or task_id_str.startswith("VERIFY_")
        is_rd = (
            bool(metadata.get("is_rd"))
            or category.startswith("r&d")
            or task_id_str.startswith("RD_")
        )

        if (
            is_verification
            and self.verification_experts
            and expert_name not in self.verification_experts
        ):
            return False, "verification_policy"

        if is_rd and self.rd_excluded_experts and expert_name in self.rd_excluded_experts:
            return False, "rd_exclusion_policy"

        required_caps = self._extract_required_capabilities(metadata)
        if required_caps:
            expert_caps = self.expert_capabilities.get(expert_name, set())
            if not required_caps.issubset(expert_caps):
                return False, "contract_capability_mismatch"

        return True, "ok"

    async def _count_expert_claims(
        self, client, goals_key: str, expert_name: str
    ) -> tuple[int, int]:
        """
        [SINGULARITY 31.2] O(1) count using Redis Sets.
        Count active claimed tasks for expert, pruning claims without heartbeat.
        """
        active_tasks_key = f"{self.key_prefix}active_tasks:{expert_name}"
        task_ids = await client.smembers(active_tasks_key)

        active_count = 0
        extreme_active = 0

        for task_id_bytes in task_ids:
            task_id = (
                task_id_bytes.decode() if isinstance(task_id_bytes, bytes) else str(task_id_bytes)
            )

            # Verify if task is still claimed by this expert and has heartbeat
            heartbeat_key = f"{self.key_prefix}heartbeat:{task_id}"
            raw_goal = await client.hget(goals_key, task_id)

            if not raw_goal:
                await client.srem(active_tasks_key, task_id)
                continue

            goal_data = json.loads(raw_goal)
            if goal_data.get("status") != "claimed" or goal_data.get("assignee") != expert_name:
                await client.srem(active_tasks_key, task_id)
                continue

            if not await client.exists(heartbeat_key):
                # Self-heal stale ownership
                goal_data["status"] = "bidding_open"
                goal_data["assignee"] = None
                goal_data["reclaimed_at"] = datetime.now(timezone.utc).isoformat()
                goal_data["reconcile_reason"] = "missing_heartbeat_during_count_o1"
                await client.hset(goals_key, task_id, json.dumps(goal_data))
                await client.srem(active_tasks_key, task_id)
                continue

            active_count += 1
            if goal_data.get("metadata", {}).get("resource_intensity") == "extreme":
                extreme_active += 1

        return active_count, extreme_active

    async def _get_current_refill_rate(self) -> float:
        """Check system:ice_mode to determine refill rate."""
        try:
            client = await self.redis.get_client()
            val = await client.get("system:ice_mode")
            is_ice = str(val).lower() in ("true", "1", "yes")
            return self.refill_rate_ice if is_ice else self.refill_rate_normal
        except Exception as e:
            logger.debug(f"Failed to check ice_mode for rate limiter: {e}")
            return self.refill_rate_normal

    async def acquire_token(self, timeout: float = 5.0) -> bool:
        """
        [SINGULARITY 30.1] Acquire a token from the global bucket.
        Uses Redis-based Token Bucket algorithm.
        """
        client = await self.redis.get_client()
        start_time = time.time()

        while time.time() - start_time < timeout:
            now = time.time()
            refill_rate = await self._get_current_refill_rate()

            # Use a Lua script for atomic get-and-set to avoid race conditions
            lua_script = """
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local max_tokens = tonumber(ARGV[2])
            local refill_rate = tonumber(ARGV[3])

            local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
            local tokens = tonumber(bucket[1]) or max_tokens
            local last_refill = tonumber(bucket[2]) or now

            -- Refill tokens
            local delta = math.max(0, now - last_refill) * refill_rate
            tokens = math.min(max_tokens, tokens + delta)

            if tokens >= 1 then
                tokens = tokens - 1
                redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
                return 1
            else
                redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
                return 0
            end
            """

            result = await client.eval(
                lua_script, 1, self.limiter_key, now, self.max_tokens, refill_rate
            )

            if result == 1:
                return True

            # Wait a bit before retrying
            await asyncio.sleep(0.1)

        logger.warning("⏳ [LIMITER] Token acquisition timed out")
        return False

    # [SINGULARITY 30.6] Heavyweight Semaphore for large models
    async def acquire_heavy_model_lock(self, model_name: str, timeout: float = 600.0) -> bool:
        """
        Захватывает глобальный замок на использование тяжелой модели (>30B).
        Предотвращает одновременную загрузку нескольких гигантов в Ollama.
        """
        client = await self.redis.get_client()
        lock_key = "system:heavy_model_lock"
        start_time = time.time()

        while time.time() - start_time < timeout:
            # SET NX EX: Установить если не существует, с TTL 10 минут
            if await client.set(lock_key, model_name, nx=True, ex=600):
                logger.info(f"🔒 [HEAVY-LOCK] Acquired for {model_name}")
                return True

            # Если замок уже наш (та же модель)
            current_owner = await client.get(lock_key)
            if current_owner == model_name:
                # Продлеваем TTL
                await client.expire(lock_key, 600)
                return True

            await asyncio.sleep(2.0)

        logger.warning(f"⏳ [HEAVY-LOCK] Timeout waiting for heavy model lock for {model_name}")
        return False

    async def release_heavy_model_lock(self, model_name: str):
        """Освобождает замок тяжелой модели."""
        client = await self.redis.get_client()
        lock_key = "system:heavy_model_lock"
        current_owner = await client.get(lock_key)
        if current_owner == model_name:
            await client.delete(lock_key)
            logger.info(f"🔓 [HEAVY-LOCK] Released by {model_name}")

    async def post_goal(self, task_id: str, goal: str, metadata: Dict[str, Any]):
        """Выставить высокоуровневую цель на Blackboard для самоорганизации экспертов."""
        key = f"{self.key_prefix}goals"
        metadata = dict(metadata or {})
        metadata.setdefault("external_task_id", str(task_id))
        entry = {
            "task_id": task_id,
            "goal": goal,
            "metadata": metadata,
            "status": "bidding_open",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        client = await self.redis.get_client()
        await client.hset(key, task_id, json.dumps(entry))
        logger.info(f"🎯 [BLACKBOARD] New goal posted for BIDDING: {task_id}")

    async def post_bid(self, task_id: str, expert_name: str, score: float):
        """Записать ставку эксперта на задачу."""
        key = f"{self.key_prefix}bids:{task_id}"
        client = await self.redis.get_client()
        await client.hset(key, expert_name, str(score))
        await client.expire(key, 60)  # Ставки живут 60 секунд
        logger.info(f"💰 [AUCTION] {expert_name} bid {score} for {task_id}")

    async def resolve_auction(self, task_id: str) -> Optional[str]:
        """Определить победителя аукциона и закрепить задачу."""
        key = f"{self.key_prefix}bids:{task_id}"
        client = await self.redis.get_client()
        all_bids = await client.hgetall(key)

        if not all_bids:
            # [SINGULARITY 28.9] Self-Diagnostic: No bids for a goal?
            logger.warning(
                f"⚠️ [SELF-DIAGNOSTIC] No bids for task {task_id}. Triggering efficiency audit..."
            )
            await self._incr_metric("lane_starvation_no_bids_total")
            asyncio.create_task(self._trigger_efficiency_audit(task_id, "no_bids"))
            return None

        # [SINGULARITY 29.7] Swarm Load Balancing: Sort bids and check concurrency for each candidate
        # Sort experts by bid score descending
        sorted_bids = sorted(all_bids.items(), key=lambda x: float(x[1]), reverse=True)

        # [SINGULARITY 31.2] Bid Threshold: Ignore candidates with low scores
        min_bid_score = float(os.getenv("BLACKBOARD_MIN_BID_SCORE", "0.4"))

        max_tasks = int(os.getenv("MAX_EXPERT_HEAVY_TASKS", "2"))
        winner = None

        # [SINGULARITY 30.4] Get task metadata to check for intensity
        goals_key = f"{self.key_prefix}goals"
        raw_goal = await client.hget(goals_key, task_id)
        is_extreme = False
        if raw_goal:
            goal_data = json.loads(raw_goal)
            is_extreme = goal_data.get("metadata", {}).get("resource_intensity") == "extreme"

        for expert_name_bytes, score_raw in sorted_bids:
            score = float(score_raw)
            if score < min_bid_score:
                logger.info(
                    f"📉 [AUCTION] {expert_name_bytes.decode()} bid {score} below threshold {min_bid_score}"
                )
                continue

            expert_name = (
                expert_name_bytes.decode()
                if isinstance(expert_name_bytes, bytes)
                else expert_name_bytes
            )
            if raw_goal:
                allowed, reason = self._is_expert_eligible_for_goal(expert_name, task_id, goal_data)
                if not allowed:
                    logger.info(
                        f"🧭 [ROUTING] Expert {expert_name} skipped for task {task_id} ({reason})"
                    )
                    await self._incr_metric(f"routing_reject_total:{reason}")
                    continue

            # Count current active tasks for this expert
            active_count, extreme_active = await self._count_expert_claims(
                client, goals_key, expert_name
            )

            # Check limits
            if active_count >= max_tasks:
                logger.info(
                    f"⚖️ [SWARM] Expert {expert_name} skipped for task {task_id} (concurrency limit: {active_count}/{max_tasks})"
                )
                await self._incr_metric("routing_reject_total:concurrency_limit")
                continue

            if is_extreme and extreme_active >= 1:
                logger.info(
                    f"⚖️ [SWARM] Expert {expert_name} skipped for EXTREME task {task_id} (already has {extreme_active})"
                )
                await self._incr_metric("routing_reject_total:extreme_limit")
                continue

            winner = expert_name
            break

        if winner and await self.claim_task(task_id, winner):
            await client.delete(key)  # Очищаем ставки
            return winner

        if not winner:
            logger.warning(
                f"⚠️ [SWARM] No available experts for task {task_id} due to concurrency limits."
            )
            await self._incr_metric("lane_starvation_no_winner_total")

        return None

    async def _trigger_efficiency_audit(self, task_id: str, reason: str):
        """[SINGULARITY 28.9] Autonomous Efficiency Audit & Mutation."""
        try:
            from codebase_mutation_engine import get_mutation_engine

            mutation = get_mutation_engine()

            error_event = {
                "error_info": {
                    "type": "EfficiencyAnomaly",
                    "message": f"Blackboard auction failed: {reason}",
                    "file": "knowledge_os/app/services/blackboard_service.py",
                    "line": 45,  # Approximate area of auction logic
                }
            }
            # Attempt to mutate the core logic if it's inefficient
            await mutation.analyze_and_mutate(
                error_event, propose_only=True
            )  # Start with propose for safety
        except Exception as e:
            logger.error(f"❌ [SELF-DIAGNOSTIC] Audit failed: {e}")

    async def claim_task(self, task_id: str, expert_name: str) -> bool:
        """Попытка атомарного захвата задачи экспертом (Auction/Bidding)."""
        lock_key = f"{self.key_prefix}lock:{task_id}"
        heartbeat_key = f"{self.key_prefix}heartbeat:{task_id}"
        client = await self.redis.get_client()

        # [SINGULARITY 30.4] Concurrency Guard with Task Weighting
        max_tasks = int(os.getenv("MAX_EXPERT_HEAVY_TASKS", "2"))
        goals_key = f"{self.key_prefix}goals"
        active_count, extreme_active = await self._count_expert_claims(
            client, goals_key, expert_name
        )

        # Rule 1: Never exceed absolute max tasks
        if active_count >= max_tasks:
            logger.warning(
                f"⚖️ [SWARM] Expert {expert_name} claim rejected for {task_id} (limit {active_count}/{max_tasks})"
            )
            await self._incr_metric("claim_reject_total:concurrency_limit")
            return False

        # Rule 2: Only one extreme task at a time
        raw_goal = await client.hget(goals_key, task_id)
        if raw_goal:
            goal_data = json.loads(raw_goal)
            allowed, reason = self._is_expert_eligible_for_goal(expert_name, task_id, goal_data)
            if not allowed:
                logger.warning(
                    f"🧭 [ROUTING] Expert {expert_name} claim rejected for {task_id} ({reason})"
                )
                await self._incr_metric(f"claim_reject_total:{reason}")
                return False
            if (
                goal_data.get("metadata", {}).get("resource_intensity") == "extreme"
                and extreme_active >= 1
            ):
                logger.warning(
                    f"⚖️ [SWARM] Expert {expert_name} rejected for EXTREME task {task_id} (already has {extreme_active})"
                )
                await self._incr_metric("claim_reject_total:extreme_limit")
                return False

        # [SINGULARITY 30.1] Rate Limiter: Heavy task claim requires a token
        if not await self.acquire_token():
            logger.warning(f"🛑 [LIMITER] Task claim rejected for {task_id} (no tokens available)")
            await self._incr_metric("claim_reject_total:token_limiter")
            return False

        # Атомарная блокировка на 30 секунд для предотвращения race condition
        if await client.set(lock_key, expert_name, nx=True, ex=30):
            key = f"{self.key_prefix}goals"
            raw_goal = await client.hget(key, task_id)
            if raw_goal:
                goal_data = json.loads(raw_goal)
                if goal_data["status"] in ("unclaimed", "bidding_open"):
                    # [OWNERSHIP SAFETY] Never overwrite existing heartbeat owner.
                    # If heartbeat already exists, another worker is actively processing
                    # or has just bootstrapped ownership in DB/stream path.
                    heartbeat_claimed = await client.set(
                        heartbeat_key, expert_name, ex=300, nx=True
                    )
                    if not heartbeat_claimed:
                        current_owner = await client.get(heartbeat_key)
                        logger.info(
                            "⏭️ [BLACKBOARD] Claim rejected for %s by %s: heartbeat owner is %s",
                            task_id,
                            expert_name,
                            current_owner,
                        )
                        await self._incr_metric("claim_reject_total:heartbeat_owned")
                        await client.delete(lock_key)
                        return False

                    goal_data["status"] = "claimed"
                    goal_data["assignee"] = expert_name
                    goal_data["claimed_at"] = datetime.now(timezone.utc).isoformat()
                    await client.hset(key, task_id, json.dumps(goal_data))
                    # [SINGULARITY 31.2] Track active tasks in O(1) set
                    await client.sadd(f"{self.key_prefix}active_tasks:{expert_name}", task_id)
                    logger.info(f"🤝 [BLACKBOARD] Task {task_id} claimed by {expert_name}")
                    return True
            await client.delete(lock_key)
        return False

    async def heartbeat_task(self, task_id: str, expert_name: str):
        """[SINGULARITY 29.2] Update task heartbeat to prevent GC from reclaiming it."""
        heartbeat_key = f"{self.key_prefix}heartbeat:{task_id}"
        client = await self.redis.get_client()
        # Проверяем, что мы все еще владельцы (защита от перехвата)
        owner = await client.get(heartbeat_key)
        if owner == expert_name:
            await client.expire(heartbeat_key, 300)  # [SINGULARITY 30.2] Increased to 5m
            # logger.debug(f"💓 [HEARTBEAT] Task {task_id} updated by {expert_name}")
        elif owner is None:
            # Runtime recovery path: allow bootstrap when task comes from DB/stream
            # and was not claimed through blackboard auction path.
            await client.set(heartbeat_key, expert_name, ex=300)
            logger.info(
                f"💓 [HEARTBEAT] Bootstrapped heartbeat ownership for task {task_id} by {expert_name}"
            )
        else:
            logger.warning(
                f"⚠️ [HEARTBEAT] Task {task_id} heartbeat failed. Owner is {owner}, not {expert_name}"
            )
            raise RuntimeError(f"Lost task ownership for {task_id}")

    async def release_task(self, task_id: str, expert_name: str):
        """[SINGULARITY 31.2] Release task from expert's active set."""
        client = await self.redis.get_client()
        await client.srem(f"{self.key_prefix}active_tasks:{expert_name}", task_id)
        logger.info(f"🔓 [BLACKBOARD] Task {task_id} released by {expert_name}")

    async def run_gc_cycle(self) -> int:
        """[SINGULARITY 29.2] Blackboard Garbage Collector.
        Reclaims tasks that were claimed but the worker died (no heartbeat).
        Returns number of reclaimed tasks.
        """
        import asyncio  # Added this import

        client = await self.redis.get_client()
        key = f"{self.key_prefix}goals"
        all_goals = await client.hgetall(key)

        reclaimed_count = 0
        for task_id, raw_data in all_goals.items():
            data = json.loads(raw_data)
            if data.get("status") == "claimed":
                heartbeat_key = f"{self.key_prefix}heartbeat:{task_id}"
                # Если ключа heartbeat нет — воркер умер
                if not await client.exists(heartbeat_key):
                    logger.warning(f"♻️ [GC] Task {task_id} lost heartbeat. Reclaiming...")
                    data["status"] = "bidding_open"
                    data["assignee"] = None
                    data["reclaimed_at"] = datetime.now(timezone.utc).isoformat()
                    await client.hset(key, task_id, json.dumps(data))
                    # [SINGULARITY 31.2] Remove from expert's active set
                    if assignee:
                        await client.srem(f"{self.key_prefix}active_tasks:{assignee}", task_id)
                    reclaimed_count += 1

        if reclaimed_count > 0:
            logger.info(f"🧹 [GC] Cycle complete. Reclaimed {reclaimed_count} abandoned tasks.")

        return reclaimed_count

    async def run_ghost_recovery(self):
        """
        [SINGULARITY 31.2] Ghost Task Recovery.
        Finds tasks that are 'claimed' but have no heartbeat or active set entry.
        """
        client = await self.redis.get_client()
        goals_key = f"{self.key_prefix}goals"
        all_goals = await client.hgetall(goals_key)

        recovered = 0
        for task_id_bytes, raw_data in all_goals.items():
            task_id = (
                task_id_bytes.decode() if isinstance(task_id_bytes, bytes) else str(task_id_bytes)
            )
            data = json.loads(raw_data)

            if data.get("status") == "claimed":
                assignee = data.get("assignee")
                heartbeat_key = f"{self.key_prefix}heartbeat:{task_id}"

                # If no heartbeat exists
                if not await client.exists(heartbeat_key):
                    logger.warning(
                        f"👻 [GHOST-RECOVERY] Task {task_id} has no heartbeat. Reopening..."
                    )
                    data["status"] = "bidding_open"
                    data["assignee"] = None
                    data["reclaimed_at"] = datetime.now(timezone.utc).isoformat()
                    data["reconcile_reason"] = "ghost_no_heartbeat"
                    await client.hset(goals_key, task_id, json.dumps(data))
                    if assignee:
                        await client.srem(f"{self.key_prefix}active_tasks:{assignee}", task_id)
                    recovered += 1

        if recovered > 0:
            logger.info(f"👻 [GHOST-RECOVERY] Recovered {recovered} ghost tasks.")
        return recovered

    async def get_unclaimed_tasks(self) -> List[Dict[str, Any]]:
        """Получить список всех свободных задач на бирже."""
        key = f"{self.key_prefix}goals"
        client = await self.redis.get_client()
        all_goals = await client.hgetall(key)
        unclaimed = []
        for task_id, raw_data in all_goals.items():
            data = json.loads(raw_data)
            if data["status"] in ("unclaimed", "bidding_open"):
                unclaimed.append(data)
        return unclaimed

    async def reconcile_goals_with_tasks(self, stale_minutes: int = 15) -> Dict[str, int]:
        """
        Reconcile stale blackboard claims to prevent dead ownership loops.
        Reopens claimed goals when heartbeat is absent or assignment policy no longer matches.
        """
        client = await self.redis.get_client()
        key = f"{self.key_prefix}goals"
        all_goals = await client.hgetall(key)
        now = datetime.now(timezone.utc)

        reopened_no_heartbeat = 0
        reopened_policy_mismatch = 0

        for task_id, raw_data in all_goals.items():
            task_id_str = task_id.decode() if isinstance(task_id, bytes) else str(task_id)
            data = json.loads(raw_data)
            if data.get("status") != "claimed":
                continue

            assignee = data.get("assignee")
            if not assignee:
                continue

            heartbeat_key = f"{self.key_prefix}heartbeat:{task_id_str}"
            has_heartbeat = await client.exists(heartbeat_key)
            if not has_heartbeat:
                data["status"] = "bidding_open"
                data["assignee"] = None
                data["reclaimed_at"] = now.isoformat()
                await client.hset(key, task_id_str, json.dumps(data))
                # [SINGULARITY 31.2] Remove from expert's active set
                await client.srem(f"{self.key_prefix}active_tasks:{assignee}", task_id_str)
                reopened_no_heartbeat += 1
                continue

            allowed, reason = self._is_expert_eligible_for_goal(assignee, task_id_str, data)
            claimed_at = data.get("claimed_at")
            stale_policy = False
            if claimed_at:
                try:
                    claimed_dt = datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
                    stale_policy = (now - claimed_dt).total_seconds() > stale_minutes * 60
                except Exception:
                    stale_policy = True

            if not allowed and stale_policy:
                data["status"] = "bidding_open"
                data["assignee"] = None
                data["reclaimed_at"] = now.isoformat()
                data["reconcile_reason"] = reason
                await client.hset(key, task_id_str, json.dumps(data))
                await client.delete(heartbeat_key)
                # [SINGULARITY 31.2] Remove from expert's active set
                await client.srem(f"{self.key_prefix}active_tasks:{assignee}", task_id_str)
                reopened_policy_mismatch += 1

        if reopened_no_heartbeat:
            await self._incr_metric("reconcile_reopened_no_heartbeat_total", reopened_no_heartbeat)
        if reopened_policy_mismatch:
            await self._incr_metric("reconcile_reopened_policy_total", reopened_policy_mismatch)

        return {
            "reopened_no_heartbeat": reopened_no_heartbeat,
            "reopened_policy_mismatch": reopened_policy_mismatch,
        }

    async def post_evidence(
        self, task_id: str, agent_name: str, evidence: Dict[str, Any], schema: Optional[Dict] = None
    ):
        """Post a piece of evidence or a partial solution to the blackboard."""
        if schema:
            try:
                import jsonschema

                jsonschema.validate(instance=evidence, schema=schema)
            except Exception as e:
                logger.error(f"❌ [BLACKBOARD] Schema validation failed for {agent_name}: {e}")
                raise ValueError(f"Evidence does not match schema: {e}")

        key = f"{self.key_prefix}{task_id}"
        entry = {
            "agent": agent_name,
            "data": evidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        client = await self.redis.get_client()
        # Semantic Locking: Check for contradictions (simplified version)
        # In a real system, this would use an LLM to check against previous entries
        await client.rpush(key, json.dumps(entry))
        logger.info(f"📝 [BLACKBOARD] {agent_name} posted evidence for task {task_id}")

    async def get_blackboard(self, task_id: str) -> List[Dict[str, Any]]:
        """Retrieve all evidence for a specific task."""
        key = f"{self.key_prefix}{task_id}"
        client = await self.redis.get_client()
        entries = await client.lrange(key, 0, -1)
        return [json.loads(e) for e in entries]

    async def clear_blackboard(self, task_id: str):
        """Clear the blackboard for a completed task."""
        key = f"{self.key_prefix}{task_id}"
        client = await self.redis.get_client()
        await client.delete(key)
        logger.info(f"🧹 [BLACKBOARD] Cleared for task {task_id}")


_blackboard = None


def get_blackboard_service() -> BlackboardService:
    global _blackboard
    if _blackboard is None:
        _blackboard = BlackboardService()
    return _blackboard
