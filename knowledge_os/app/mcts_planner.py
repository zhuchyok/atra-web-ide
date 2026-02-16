"""
[SINGULARITY 12.0] MCTS Planner.
Implements Monte Carlo Tree Search for long-horizon plan optimization.
Supports imaginary rollouts, backpropagation, and rollback.
"""

import os
import asyncio
import logging
import math
import random
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class MCTSNode:
    """Node in the MCTS tree."""
    node_id: str
    action: str
    parent: Optional['MCTSNode'] = None
    children: List['MCTSNode'] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0
    depth: int = 0
    is_terminal: bool = False
    state_description: str = ""

class MCTSPlanner:
    """
    Monte Carlo Tree Search Planner for complex, multi-step tasks.
    """
    
    def __init__(
        self, 
        model_name: str = "qwen2.5-coder:32b",
        exploration_weight: float = 1.41,
        max_iterations: int = 10,
        max_depth: int = 5
    ):
        self.model_name = model_name
        self.exploration_weight = exploration_weight
        self.max_iterations = max_iterations
        self.max_depth = max_depth
        self.root: Optional[MCTSNode] = None

    async def plan(self, goal: str, context: str = "") -> List[str]:
        """
        Generates an optimized plan using MCTS.
        """
        logger.info(f"🌳 [MCTS] Starting tree search for goal: {goal[:100]}...")
        
        self.root = MCTSNode(
            node_id="root",
            action="Start",
            state_description=f"Initial state for: {goal}"
        )
        
        for i in range(self.max_iterations):
            logger.info(f"🔄 [MCTS] Iteration {i+1}/{self.max_iterations}")
            
            # 1. Selection
            node = self._select(self.root)
            
            # 2. Expansion
            if not node.is_terminal and node.depth < self.max_depth:
                node = await self._expand(node, goal, context)
            
            # 3. Simulation (Imaginary Rollout)
            reward = await self._simulate(node, goal, context)
            
            # 4. Backpropagation
            self._backpropagate(node, reward)
            
        # Extract the best path
        best_path = self._get_best_path()
        logger.info(f"✅ [MCTS] Optimized plan found with {len(best_path)} steps.")
        return [n.action for n in best_path if n.node_id != "root"]

    def _select(self, node: MCTSNode) -> MCTSNode:
        """Selects the most promising node using UCB1."""
        while node.children:
            if any(c.visits == 0 for c in node.children):
                return random.choice([c for c in node.children if c.visits == 0])
            
            # UCB1 Selection
            log_total_visits = math.log(node.visits)
            node = max(node.children, key=lambda c: (c.value / c.visits) + 
                       self.exploration_weight * math.sqrt(log_total_visits / c.visits))
        return node

    async def _expand(self, node: MCTSNode, goal: str, context: str) -> MCTSNode:
        """Expands the tree by generating possible next actions."""
        expansion_prompt = f"""
        Given the current goal and steps taken, suggest 3 possible next actions.
        GOAL: {goal}
        CONTEXT: {context}
        STEPS TAKEN: {self._get_path_string(node)}
        
        Return JSON list of actions: ["action1", "action2", "action3"]
        """
        try:
            from ai_core import run_smart_agent_async
            response = await run_smart_agent_async(expansion_prompt, expert_name="Architect", category="reasoning")
            
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                actions = json.loads(json_match.group())
                for action in actions:
                    child = MCTSNode(
                        node_id=f"{node.node_id}_{len(node.children)}",
                        action=action,
                        parent=node,
                        depth=node.depth + 1
                    )
                    node.children.append(child)
                return random.choice(node.children) if node.children else node
        except Exception as e:
            logger.error(f"MCTS Expansion failed: {e}")
        return node

    async def _simulate(self, node: MCTSNode, goal: str, context: str) -> float:
        """Performs an imaginary rollout to estimate the value of a node."""
        simulation_prompt = f"""
        Imagine you take this action: {node.action}
        As part of this plan: {self._get_path_string(node)}
        For the goal: {goal}
        
        Evaluate the probability of success (0.0 to 1.0) and potential risks.
        Return ONLY the numeric probability.
        """
        try:
            from ai_core import run_smart_agent_async
            response = await run_smart_agent_async(simulation_prompt, expert_name="Architect", category="reasoning")
            
            import re
            score_match = re.search(r'0\.\d+|1\.0', response)
            if score_match:
                return float(score_match.group())
        except Exception:
            pass
        return 0.5 # Default neutral reward

    def _backpropagate(self, node: MCTSNode, reward: float):
        """Updates visits and values up the tree."""
        while node:
            node.visits += 1
            node.value += reward
            node.reward = reward # Store last reward for rollback logic
            node = node.parent

    def _get_best_path(self) -> List[MCTSNode]:
        """Extracts the path with the highest visit count."""
        path = []
        node = self.root
        while node:
            path.append(node)
            if not node.children:
                break
            node = max(node.children, key=lambda c: c.visits)
        return path

    def _get_path_string(self, node: MCTSNode) -> str:
        path = []
        curr = node
        while curr:
            path.append(curr.action)
            curr = curr.parent
        return " -> ".join(reversed(path))

_instance = None
def get_mcts_planner():
    global _instance
    if _instance is None:
        _instance = MCTSPlanner()
    return _instance
