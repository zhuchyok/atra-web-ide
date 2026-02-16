"""
[SINGULARITY 10.0+] UI/UX Audit Agent.
Uses multimodal models to audit frontend screenshots against design standards.
"""

import asyncio
import logging
import os
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class UIUXAuditAgent:
    """
    Agent for visual auditing of frontend interfaces.
    Integrates with Vision models to analyze screenshots.
    """
    
    def __init__(self):
        self.standards_path = os.getenv("UX_STANDARDS_PATH", "docs/UX_STANDARDS.md")
        
    async def audit_screenshot(self, image_base64: str, project_context: str = "general") -> Dict[str, Any]:
        """
        Perform a visual audit of a screenshot.
        """
        logger.info(f"🎨 [UI/UX AUDIT] Starting audit for project: {project_context}")
        
        # 1. Load design standards (if exists)
        standards = "Используй стандартные принципы UX/UI: контрастность, выравнивание, читаемость шрифтов, консистентность отступов."
        if os.path.exists(self.standards_path):
            with open(self.standards_path, 'r', encoding='utf-8') as f:
                standards = f.read()
        
        # 2. Prepare prompt for Vision model
        prompt = f"""
Ты - эксперт по UI/UX дизайну (Елена). Проведи аудит данного скриншота фронтенда.
ПРОЕКТ: {project_context}

КРИТЕРИИ ПРОВЕРКИ:
{standards}

ЗАДАЧА:
1. Найди визуальные баги (кривая верстка, наложение элементов).
2. Оцени удобство интерфейса (UX).
3. Проверь соответствие цветовой схеме и шрифтам.

ВЕРНИ ОТВЕТ В ФОРМАТЕ:
### 🚨 Визуальные ошибки:
- [ ] Ошибка 1...
### 💡 Рекомендации по UX:
- ...
### 🛠️ Техническое задание для Veronica (CSS/HTML):
- ...
"""

        # 3. Call Vision model (via VisionProcessor or direct to local node)
        try:
            from vision_processor import get_vision_processor
            vision = get_vision_processor()
            analysis = await vision.describe_image(image_base64=image_base64, custom_prompt=prompt)
            
            if not analysis:
                return {"status": "error", "message": "Vision model returned empty analysis"}
                
            logger.info("✅ [UI/UX AUDIT] Visual analysis completed")
            return {
                "status": "success",
                "analysis": analysis,
                "timestamp": datetime.now().isoformat(),
                "project": project_context
            }
            
        except Exception as e:
            logger.error(f"❌ [UI/UX AUDIT] Audit failed: {e}")
            return {"status": "error", "message": str(e)}

    async def generate_fix_tasks(self, audit_result: Dict[str, Any]) -> List[str]:
        """
        Convert audit findings into actionable tasks for the orchestrator.
        """
        if audit_result.get("status") != "success":
            return []
            
        analysis = audit_result["analysis"]
        # Simple extraction logic (can be improved with LLM)
        tasks = []
        if "### 🛠️ Техническое задание" in analysis:
            tz_part = analysis.split("### 🛠️ Техническое задание")[1]
            for line in tz_part.split("\n"):
                line = line.strip().strip("-").strip()
                if line and len(line) > 10:
                    tasks.append(f"UI FIX: {line}")
                    
        return tasks

_instance = None
def get_ui_audit_agent():
    global _instance
    if _instance is None:
        _instance = UIUXAuditAgent()
    return _instance
