"""
Central config for Knowledge OS (env-based).
Orchestration V2 feature flags for Canary / A/B deployment.
"""
import os

# ---------------------------------------------------------------------------
# Orchestration V2 (Canary deployment)
# ---------------------------------------------------------------------------
ORCHESTRATION_V2_ENABLED = os.getenv("ORCHESTRATION_V2_ENABLED", "false").lower() in ("1", "true", "yes")
ORCHESTRATION_V2_PERCENTAGE = float(os.getenv("ORCHESTRATION_V2_PERCENTAGE", "10"))  # 0..100, % of traffic to V2

# Legacy alias (IntegrationBridge may use this)
USE_ORCHESTRATION_V2 = os.getenv("USE_ORCHESTRATION_V2", "").lower() in ("1", "true", "yes")
