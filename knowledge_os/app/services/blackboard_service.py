import json
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

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
    """
    def __init__(self):
        self.redis = get_redis_manager()
        self.key_prefix = "blackboard:"

    async def post_goal(self, task_id: str, goal: str, metadata: Dict[str, Any]):
        """Выставить высокоуровневую цель на Blackboard для самоорганизации экспертов."""
        key = f"{self.key_prefix}goals"
        entry = {
            "task_id": task_id,
            "goal": goal,
            "metadata": metadata,
            "status": "bidding_open",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        client = await self.redis.get_client()
        await client.hset(key, task_id, json.dumps(entry))
        logger.info(f"🎯 [BLACKBOARD] New goal posted for BIDDING: {task_id}")

    async def post_bid(self, task_id: str, expert_name: str, score: float):
        """Записать ставку эксперта на задачу."""
        key = f"{self.key_prefix}bids:{task_id}"
        client = await self.redis.get_client()
        await client.hset(key, expert_name, str(score))
        await client.expire(key, 60) # Ставки живут 60 секунд
        logger.info(f"💰 [AUCTION] {expert_name} bid {score} for {task_id}")

    async def resolve_auction(self, task_id: str) -> Optional[str]:
        """Определить победителя аукциона и закрепить задачу."""
        key = f"{self.key_prefix}bids:{task_id}"
        client = await self.redis.get_client()
        all_bids = await client.hgetall(key)
        
        if not all_bids:
            # [SINGULARITY 28.9] Self-Diagnostic: No bids for a goal?
            logger.warning(f"⚠️ [SELF-DIAGNOSTIC] No bids for task {task_id}. Triggering efficiency audit...")
            asyncio.create_task(self._trigger_efficiency_audit(task_id, "no_bids"))
            return None
            
        # [SINGULARITY 29.7] Swarm Load Balancing: Sort bids and check concurrency for each candidate
        # Sort experts by bid score descending
        sorted_bids = sorted(all_bids.items(), key=lambda x: float(x[1]), reverse=True)
        
        max_tasks = int(os.getenv("MAX_EXPERT_HEAVY_TASKS", "2"))
        winner = None
        
        for expert_name_bytes, score in sorted_bids:
            expert_name = expert_name_bytes.decode() if isinstance(expert_name_bytes, bytes) else expert_name_bytes
            
            # Count current active tasks for this expert
            goals_key = f"{self.key_prefix}goals"
            all_goals = await client.hgetall(goals_key)
            active_count = 0
            for g_id, g_raw in all_goals.items():
                g_data = json.loads(g_raw)
                if g_data.get("status") == "claimed" and g_data.get("assignee") == expert_name:
                    active_count += 1
            
            if active_count < max_tasks:
                winner = expert_name
                break
            else:
                logger.info(f"⚖️ [SWARM] Expert {expert_name} skipped for task {task_id} (concurrency limit: {active_count}/{max_tasks})")

        if winner and await self.claim_task(task_id, winner):
            await client.delete(key) # Очищаем ставки
            return winner
        
        if not winner:
            logger.warning(f"⚠️ [SWARM] No available experts for task {task_id} due to concurrency limits.")
            
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
                    "line": 45 # Approximate area of auction logic
                }
            }
            # Attempt to mutate the core logic if it's inefficient
            await mutation.analyze_and_mutate(error_event, propose_only=True) # Start with propose for safety
        except Exception as e:
            logger.error(f"❌ [SELF-DIAGNOSTIC] Audit failed: {e}")

    async def claim_task(self, task_id: str, expert_name: str) -> bool:
        """Попытка атомарного захвата задачи экспертом (Auction/Bidding)."""
        lock_key = f"{self.key_prefix}lock:{task_id}"
        heartbeat_key = f"{self.key_prefix}heartbeat:{task_id}"
        client = await self.redis.get_client()
        
        # [SINGULARITY 29.7] Concurrency Guard for direct claims
        max_tasks = int(os.getenv("MAX_EXPERT_HEAVY_TASKS", "2"))
        goals_key = f"{self.key_prefix}goals"
        all_goals = await client.hgetall(goals_key)
        active_count = 0
        for g_id, g_raw in all_goals.items():
            g_data = json.loads(g_raw)
            if g_data.get("status") == "claimed" and g_data.get("assignee") == expert_name:
                active_count += 1
        
        if active_count >= max_tasks:
            logger.warning(f"⚖️ [SWARM] Expert {expert_name} claim rejected for {task_id} (limit {active_count}/{max_tasks})")
            return False

        # Атомарная блокировка на 30 секунд для предотвращения race condition
        if await client.set(lock_key, expert_name, nx=True, ex=30):
            key = f"{self.key_prefix}goals"
            raw_goal = await client.hget(key, task_id)
            if raw_goal:
                goal_data = json.loads(raw_goal)
                if goal_data["status"] in ("unclaimed", "bidding_open"):
                    goal_data["status"] = "claimed"
                    goal_data["assignee"] = expert_name
                    goal_data["claimed_at"] = datetime.now(timezone.utc).isoformat()
                    
                    # [SINGULARITY 29.2] Heartbeat initialization
                    await client.set(heartbeat_key, expert_name, ex=60) # Initial 60s life
                    
                    await client.hset(key, task_id, json.dumps(goal_data))
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
            await client.expire(heartbeat_key, 60)
            # logger.debug(f"💓 [HEARTBEAT] Task {task_id} updated by {expert_name}")
        else:
            logger.warning(f"⚠️ [HEARTBEAT] Task {task_id} heartbeat failed. Owner is {owner}, not {expert_name}")
            raise RuntimeError(f"Lost task ownership for {task_id}")

    async def run_gc_cycle(self) -> int:
        """[SINGULARITY 29.2] Blackboard Garbage Collector.
        Reclaims tasks that were claimed but the worker died (no heartbeat).
        Returns number of reclaimed tasks.
        """
        import asyncio # Added this import
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
                    reclaimed_count += 1
        
        if reclaimed_count > 0:
            logger.info(f"🧹 [GC] Cycle complete. Reclaimed {reclaimed_count} abandoned tasks.")
        
        return reclaimed_count

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

    async def post_evidence(self, task_id: str, agent_name: str, evidence: Dict[str, Any], schema: Optional[Dict] = None):
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
            "timestamp": datetime.now(timezone.utc).isoformat()
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
