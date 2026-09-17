"""Restored corp module must import and expose the orchestrator contract."""

from app.corporation_knowledge_system import CorporationKnowledgeSystem, update_all_agents_knowledge


def test_corporation_knowledge_system_contract():
    assert callable(update_all_agents_knowledge)
    system = CorporationKnowledgeSystem()
    assert hasattr(system, "update_corporation_knowledge")
    assert hasattr(system, "discover_ollama_models")
