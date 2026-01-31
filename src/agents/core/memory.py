import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class AgentMemoryState:
    """Объект состояния памяти агента (Stateless подход)"""
    agent_id: str
    steps: List[Dict[str, Any]]  # Список шагов: Thought, Action, Observation
    goals: List[str]             # Текущие цели
    context: Dict[str, Any]      # Общий контекст (переменные, флаги)
    last_update: str

class AgentMemoryManager:
    """
    Менеджер памяти агентов.
    Следует принципу Stateless: не хранит состояние внутри, а помогает его сериализовать/десериализовать.
    """
    
    def __init__(self, storage_dir: str = "cache/agents"):
        self.storage_dir = storage_dir
        import os
        os.makedirs(storage_dir, exist_ok=True)

    def create_empty_state(self, agent_id: str) -> AgentMemoryState:
        return AgentMemoryState(
            agent_id=agent_id,
            steps=[],
            goals=[],
            context={},
            last_update=datetime.now(timezone.utc).isoformat()
        )

    def save_state(self, state: AgentMemoryState):
        """Сохранение состояния в файл (для персистентности между запусками)"""
        file_path = f"{self.storage_dir}/{state.agent_id}.json"
        try:
            with open(file_path, 'w') as f:
                json.dump(asdict(state), f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error saving agent state {state.agent_id}: {e}")

    def load_state(self, agent_id: str) -> AgentMemoryState:
        """Загрузка состояния из файла"""
        file_path = f"{self.storage_dir}/{agent_id}.json"
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    return AgentMemoryState(**data)
        except Exception as e:
            logger.error(f"❌ Error loading agent state {agent_id}: {e}")
        
        return self.create_empty_state(agent_id)

    def add_step(self, state: AgentMemoryState, thought: str, action: Optional[Dict] = None, observation: Optional[str] = None):
        """Добавление шага в память и возврат обновленного состояния"""
        state.steps.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "thought": thought,
            "action": action,
            "observation": observation
        })
        state.last_update = datetime.now(timezone.utc).isoformat()
        return state

