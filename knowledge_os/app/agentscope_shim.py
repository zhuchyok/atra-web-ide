"""
Minimal AgentScope shim for ATRA system.
Provides AgentBase and Msg interfaces without requiring the full agentscope package.
Used as fallback when agentscope is not installed or has dependency conflicts.
"""

import logging

logger = logging.getLogger(__name__)


class Msg(dict):
    """Minimal message type compatible with AgentScope Msg."""
    def __init__(self, name: str = "", role: str = "assistant", content: str = "", **kwargs):
        super().__init__(name=name, role=role, content=content, **kwargs)
        self.name = name
        self.role = role
        self.content = content


class AgentBase:
    """
    Minimal AgentBase shim compatible with AgentScope AgentBase interface.
    Provides state_dict/load_state_dict for Event Sourcing.
    """
    def __init__(self, name: str = "", sys_prompt: str = "", **kwargs):
        self.name = name
        self.sys_prompt = sys_prompt
        self._memory: list = []

    def state_dict(self) -> dict:
        return {
            "name": self.name,
            "sys_prompt": self.sys_prompt,
            "memory_len": len(self._memory),
        }

    def load_state_dict(self, state: dict):
        self.name = state.get("name", self.name)
        self.sys_prompt = state.get("sys_prompt", self.sys_prompt)

    def reply(self, x=None):
        raise NotImplementedError("Subclasses must implement reply()")
