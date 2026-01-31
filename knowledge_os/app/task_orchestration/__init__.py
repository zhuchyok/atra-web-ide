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

from .model_registry import ModelRegistry
from .task_complexity_analyzer import TaskComplexityAnalyzer
from .model_availability_checker import ModelAvailabilityChecker
from .expert_matching_engine import ExpertMatchingEngine
from .task_decomposer import TaskDecomposer, TaskDependencyGraph, SubTask
from .integration_bridge import IntegrationBridge
from .orchestration_monitor import OrchestrationMonitor
from .smart_worker_integration import SmartWorkerIntegration
from .jira_style_orchestrator import JiraStyleOrchestrator
from .optimizer import OrchestrationOptimizer

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
