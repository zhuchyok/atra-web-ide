#!/usr/bin/env python3
"""Check all agent modules are importable and have correct signatures."""

import importlib
import sys

AGENT_MODULES = [
    "app.agent_messaging",
    "app.agent_protocol",
    "app.agent_dependency_graph",
    "app.agent_sla_metrics",
    "app.agent_message_registry",
    "app.agent_lifecycle_manager",
    "app.agent_ab_testing",
    "app.agent_chaos_injector",
    "app.agent_kpi_tracker",
    "app.agent_evolver",
    "app.agent_self_assessment",
    "app.code_sandbox",
    "app.ai_pipeline",
    "app.ai_core",
    "app.expert_worker",
    "app.expert_aliases",
    "app.expert_contract",
    "app.expert_council_discussion",
    "app.expert_dna_manager",
    "app.expert_evolver",
    "app.expert_generator",
    "app.expert_validator",
    "app.expert_synthesizer",
    "app.expert_services",
    "app.group_chat_state_machine",
    "app.state_checkpoint",
    "app.a2a_protocol",
    "app.services.blackboard_service",
    "app.explicit_handoffs",
    "app.event_bus_redis_bridge",
    "app.smart_worker_autonomous",
    "app.hierarchical_orchestration",
    "app.shadow_execution_manager",
]


def check_agent_health():
    errors = []
    for mod_name in AGENT_MODULES:
        try:
            importlib.import_module(mod_name)
            print(f"  \u2705 {mod_name}")
        except Exception as e:
            errors.append(f"  \u274c {mod_name}: {e}")
            print(f"  \u274c {mod_name}: {e}")

    if errors:
        print(f"\n{len(errors)} errors out of {len(AGENT_MODULES)} modules")
        return False
    print(f"\nAll {len(AGENT_MODULES)} modules healthy")
    return True


if __name__ == "__main__":
    sys.exit(0 if check_agent_health() else 1)
