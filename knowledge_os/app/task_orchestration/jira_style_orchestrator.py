"""
Jira-style адаптер оркестрации: Epic / Story / Subtask.

Оборачивает базовый оркестратор (EnhancedOrchestratorV2 или V2Swarm) и даёт
термины в стиле Jira: create_epic, create_story, create_subtask.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class JiraStyleOrchestrator:
    """
    Адаптер в стиле Jira: Epic = родительская задача, Story = подзадача, Subtask = под-подзадача.
    Оборачивает base_orchestrator (EnhancedOrchestratorV2 или EnhancedOrchestratorV2Swarm).
    """

    def __init__(self, base_orchestrator: Any):
        self.orchestrator = base_orchestrator

    async def create_epic(self, summary: str, description: str, metadata: Optional[Dict] = None) -> str:
        """Создать Epic (родительскую задачу) через phase_1 и вернуть task_id."""
        task_id = None
        if hasattr(self.orchestrator, "run_phases_1_to_5"):
            result = await self.orchestrator.run_phases_1_to_5(
                description=f"EPIC: {summary}\n\n{description}",
                metadata=dict(metadata or {}, jira_type="epic", summary=summary),
            )
            task_id = result.get("task_id")
        if not task_id and hasattr(self.orchestrator, "active_tasks"):
            import uuid
            task_id = str(uuid.uuid4())
            self.orchestrator.active_tasks[task_id] = {
                "description": f"EPIC: {summary}\n\n{description}",
                "metadata": dict(metadata or {}, jira_type="epic", summary=summary),
                "epic": True,
            }
        return task_id or ""

    async def create_story(self, epic_id: str, summary: str, description: str = "") -> str:
        """Добавить Story (подзадачу) к Epic в памяти оркестратора."""
        epic = getattr(self.orchestrator, "active_tasks", {}).get(epic_id)
        if not epic:
            raise ValueError(f"Epic {epic_id} not found")
        if "stories" not in epic:
            epic["stories"] = []
        story_id = f"{epic_id}_story_{len(epic['stories']) + 1}"
        epic["stories"].append({
            "id": story_id,
            "summary": summary,
            "description": description or summary,
            "status": "todo",
        })
        return story_id

    async def create_subtask(self, story_id: str, summary: str, description: str = "") -> str:
        """Добавить Subtask к Story в памяти оркестратора."""
        for _epid, epic in getattr(self.orchestrator, "active_tasks", {}).items():
            if not isinstance(epic, dict) or "stories" not in epic:
                continue
            for story in epic["stories"]:
                if story.get("id") == story_id:
                    if "subtasks" not in story:
                        story["subtasks"] = []
                    subtask_id = f"{story_id}_subtask_{len(story['subtasks']) + 1}"
                    story["subtasks"].append({
                        "id": subtask_id,
                        "summary": summary,
                        "description": description or summary,
                        "status": "todo",
                    })
                    return subtask_id
        raise ValueError(f"Story {story_id} not found")
