"""
Explainable Router для объяснения решений ML-роутера.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class ExplainableRouter:
    """Объяснение решений роутера"""
    
    def explain_decision(self, features: Dict, decision: str) -> Dict:
        """Объяснить решение роутера"""
        return {
            "decision": decision,
            "features": features,
            "explanation": f"Выбран маршрут {decision} на основе features: {features}"
        }

# Глобальный экземпляр
_explainable_router: Optional[ExplainableRouter] = None

def get_explainable_router() -> ExplainableRouter:
    """Получить глобальный экземпляр ExplainableRouter"""
    global _explainable_router
    if _explainable_router is None:
        _explainable_router = ExplainableRouter()
    return _explainable_router

