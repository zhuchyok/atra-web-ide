"""
Enhanced Orchestrator V2 + Swarm Intelligence и Consensus Agent.

Расширение EnhancedOrchestratorV2: при высокой сложности опционально использует
Swarm Intelligence для подбора экспертов и Collective Memory для записи назначений.
Агрегация результатов подзадач — через Consensus Agent (фаза 11).
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from .enhanced_orchestrator_v2 import EnhancedOrchestratorV2
except ImportError:
    from app.enhanced_orchestrator_v2 import EnhancedOrchestratorV2

SwarmIntelligence = None
ConsensusAgent = None
CollectiveMemorySystem = None

try:
    from app.swarm_intelligence import SwarmIntelligence as _SI
    SwarmIntelligence = _SI
except ImportError:
    try:
        from swarm_intelligence import SwarmIntelligence as _SI
        SwarmIntelligence = _SI
    except ImportError:
        pass

try:
    from app.consensus_agent import ConsensusAgent as _CA
    ConsensusAgent = _CA
except ImportError:
    try:
        from consensus_agent import ConsensusAgent as _CA
        ConsensusAgent = _CA
    except ImportError:
        pass

try:
    from app.collective_memory import CollectiveMemorySystem as _CMS
    CollectiveMemorySystem = _CMS
except ImportError:
    try:
        from collective_memory import CollectiveMemorySystem as _CMS
        CollectiveMemorySystem = _CMS
    except ImportError:
        pass


class EnhancedOrchestratorV2Swarm(EnhancedOrchestratorV2):
    """
    Расширение EnhancedOrchestratorV2 с опциональным Swarm Intelligence и Consensus Agent.
    phase_5_select_experts: при сложности > 0.7 и наличии графа можно вызвать Swarm;
    по умолчанию используется базовый подбор экспертов, результат записывается в Collective Memory.
    """

    def __init__(self, db_url: Optional[str] = None):
        super().__init__(db_url=db_url)
        self.swarm_intelligence = None
        self.consensus_agent = None
        self.collective_memory = None
        self._load_swarm_components()

    def _load_swarm_components(self) -> None:
        """Загрузка Swarm, Consensus и Collective Memory при наличии модулей."""
        if SwarmIntelligence:
            try:
                self.swarm_intelligence = SwarmIntelligence(swarm_size=8)
                logger.info("EnhancedOrchestratorV2Swarm: SwarmIntelligence loaded")
            except Exception as e:
                logger.debug("SwarmIntelligence init failed: %s", e)
        if ConsensusAgent:
            try:
                self.consensus_agent = ConsensusAgent()
                logger.info("EnhancedOrchestratorV2Swarm: ConsensusAgent loaded")
            except Exception as e:
                logger.debug("ConsensusAgent init failed: %s", e)
        if CollectiveMemorySystem:
            try:
                self.collective_memory = CollectiveMemorySystem(db_url=self._db_url)
                logger.info("EnhancedOrchestratorV2Swarm: CollectiveMemorySystem loaded")
            except Exception as e:
                logger.debug("CollectiveMemorySystem init failed: %s", e)

    async def phase_5_select_experts(
        self,
        task_id: str,
        graph: Optional[Any] = None,
        description: str = "",
    ) -> Dict[str, Dict[str, Any]]:
        """
        Подбор экспертов: при сложности > 0.7 и наличии Swarm можно использовать его;
        иначе — базовый ExpertMatchingEngine. Результат пишется в Collective Memory.
        """
        task = self.active_tasks.get(task_id)
        complexity = (task or {}).get("complexity", 0)
        use_swarm = (
            complexity > 0.7
            and self.swarm_intelligence is not None
            and graph is not None
            and getattr(graph, "subtasks", None)
        )
        if use_swarm:
            try:
                swarm_prompt = (
                    f"Задача: {description[:500]}\n\nПодзадачи: "
                    + ", ".join(
                        f"{st.title} ({st.category})"
                        for st in (graph.subtasks or {}).values()
                    )
                    + ". Подбери оптимальную команду экспертов по категориям (coding, reasoning, vision, general)."
                )
                try:
                    from app.expert_services import get_all_expert_names
                    swarm_agents = get_all_expert_names(max_count=getattr(self.swarm_intelligence, "swarm_size", 8))
                except ImportError:
                    swarm_agents = None
                await self.swarm_intelligence.solve(problem=swarm_prompt, agent_names=swarm_agents)
                # Фактические назначения делаем через базовый ExpertMatchingEngine
            except Exception as e:
                logger.debug("Swarm phase_5 failed, falling back: %s", e)
        assignments = await super().phase_5_select_experts(task_id, graph=graph, description=description)
        if assignments and self.collective_memory:
            try:
                await self.collective_memory.record_action(
                    agent_name="Orchestrator",
                    action="expert_assignment",
                    result=json.dumps(assignments),
                    location=task_id,
                )
            except Exception as e:
                logger.debug("CollectiveMemory record_action: %s", e)
        return assignments

    async def phase_11_aggregate_results_with_consensus(
        self,
        task_id: str,
        subtask_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Агрегация результатов подзадач через Consensus Agent (если доступен).
        """
        if not subtask_results:
            return {"aggregated_result": "", "method": "none", "subtasks_count": 0}
        if self.consensus_agent is None:
            return self._simple_aggregate_results(subtask_results)
        try:
            texts = [str(r.get("result", r.get("output", ""))) for r in subtask_results if r]
            question = f"Итоговый результат для задачи {task_id} по подзадачам."
            try:
                from app.expert_services import get_all_expert_names
                consensus_agents = get_all_expert_names(max_count=8)
            except ImportError:
                consensus_agents = ["Виктория", "Вероника", "Игорь", "Сергей", "Дмитрий"]
            result = await self.consensus_agent.reach_consensus(
                agents=consensus_agents,
                question=question,
                initial_context={"subtask_results": texts},
            )
            out = {
                "consensus_result": getattr(result, "final_answer", str(result)),
                "method": "consensus_agent",
                "subtasks_count": len(subtask_results),
                "successful_subtasks": sum(1 for r in subtask_results if r.get("success", False)),
            }
            if self.collective_memory:
                try:
                    await self.collective_memory.record_action(
                        agent_name="Orchestrator",
                        action="consensus_achieved",
                        result=out.get("consensus_result", ""),
                        location=task_id,
                    )
                except Exception as e:
                    logger.debug("CollectiveMemory record_action: %s", e)
            return out
        except Exception as e:
            logger.debug("Consensus aggregate failed: %s", e)
            return self._simple_aggregate_results(subtask_results)

    def _simple_aggregate_results(self, subtask_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Простая конкатенация результатов подзадач."""
        texts = [str(r.get("result", r.get("output", ""))) for r in subtask_results if r]
        return {
            "aggregated_result": "\n\n".join(texts),
            "method": "simple_concatenation",
            "subtasks_count": len(subtask_results),
            "successful_subtasks": sum(1 for r in subtask_results if r.get("success", False)),
        }
