"""
Task orchestration package: world-class orchestration (parent/child tasks, expert specializations, model registry).

Use from knowledge_os/app (PYTHONPATH includes app dir):
  from task_orchestration import ModelRegistry, TaskComplexityAnalyzer
  from task_orchestration.model_registry import ModelRegistry
  from task_orchestration.task_complexity_analyzer import TaskComplexityAnalyzer
  from task_orchestration.model_availability_checker import ModelAvailabilityChecker

Or from project root with app on path:
  from app.task_orchestration import ModelRegistry, TaskComplexityAnalyzer
"""

from .expert_matching_engine import ExpertMatchingEngine
from .integration_bridge import IntegrationBridge
from .jira_style_orchestrator import JiraStyleOrchestrator
from .model_availability_checker import ModelAvailabilityChecker
from .model_registry import ModelRegistry
from .optimizer import OrchestrationOptimizer
from .orchestration_monitor import OrchestrationMonitor
from .smart_worker_integration import SmartWorkerIntegration
from .task_complexity_analyzer import TaskComplexityAnalyzer
from .task_decomposer import SubTask, TaskDecomposer, TaskDependencyGraph

__all__ = [
    "ModelRegistry",
    "TaskComplexityAnalyzer",
    "ModelAvailabilityChecker",
    "ExpertMatchingEngine",
    "TaskDecomposer",
    "TaskDependencyGraph",
    "SubTask",
    "IntegrationBridge",
    "OrchestrationMonitor",
    "SmartWorkerIntegration",
    "JiraStyleOrchestrator",
    "OrchestrationOptimizer",
]
