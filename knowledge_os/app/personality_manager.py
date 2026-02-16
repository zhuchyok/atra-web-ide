"""
[SINGULARITY 10.0+] Personality Manager.
Dynamically adjusts agent personality and tone based on user interaction patterns (Anthropic pattern).
"""

import logging
import os
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)

class PersonaType(Enum):
    SGT_MAJOR = "sgt_major"  # Concise, direct, military precision
    ARCHITECT = "architect"  # Detailed, educational, strategic
    DEVELOPER = "developer"  # Technical, practical, focused on code
    CONSULTANT = "consultant" # Professional, balanced, business-oriented

class PersonalityManager:
    """
    Manages dynamic personality adaptation for agents.
    Analyzes query context and user history to select the best tone.
    """
    
    def __init__(self):
        self.default_persona = PersonaType.DEVELOPER
        
    def analyze_persona_needs(self, query: str, context: Optional[Dict[str, Any]] = None) -> PersonaType:
        """
        Analyze the query and context to determine the required persona.
        """
        query_lower = query.lower()
        
        # 1. Detect "Sgt. Major" needs (urgency, brevity, direct commands)
        if len(query) < 50 or any(kw in query_lower for kw in ["быстро", "кратко", "статус", "чек", "fix it", "run"]):
            return PersonaType.SGT_MAJOR
            
        # 2. Detect "Architect" needs (complexity, strategy, "why" questions)
        if any(kw in query_lower for kw in ["почему", "архитектура", "как лучше", "сравнение", "выбор", "стратегия"]):
            return PersonaType.ARCHITECT
            
        # 3. Detect "Consultant" needs (business, OKR, planning)
        if any(kw in query_lower for kw in ["бизнес", "план", "okr", "цели", "результат"]):
            return PersonaType.CONSULTANT
            
        return self.default_persona

    def get_persona_modifier(self, persona: PersonaType) -> str:
        """
        Get the system prompt modifier for a specific persona.
        """
        modifiers = {
            PersonaType.SGT_MAJOR: """
TONE: SGT. MAJOR (Concise & Direct)
- Be extremely brief and precise.
- No pleasantries or filler words.
- Focus on actions and results.
- Use bullet points for multiple items.
""",
            PersonaType.ARCHITECT: """
TONE: ARCHITECT (Strategic & Educational)
- Provide deep context and reasoning.
- Explain the 'why' behind decisions.
- Consider long-term implications and scalability.
- Use structured sections and diagrams if helpful.
""",
            PersonaType.DEVELOPER: """
TONE: DEVELOPER (Technical & Practical)
- Focus on code quality and implementation details.
- Be technical but clear.
- Suggest best practices and patterns.
- Keep explanations focused on the task at hand.
""",
            PersonaType.CONSULTANT: """
TONE: CONSULTANT (Professional & Balanced)
- Balance technical depth with business value.
- Focus on milestones and deliverables.
- Be professional and structured.
- Highlight risks and trade-offs.
"""
        }
        return modifiers.get(persona, "")

    def adapt_prompt(self, query: str, system_prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Adapt the system prompt based on the detected persona needs.
        """
        persona = self.analyze_persona_needs(query, context)
        modifier = self.get_persona_modifier(persona)
        
        logger.info(f"🎭 [PERSONALITY] Adapted to persona: {persona.value}")
        
        return f"{system_prompt}\n\n{modifier}"

_instance = None
def get_personality_manager():
    global _instance
    if _instance is None:
        _instance = PersonalityManager()
    return _instance
