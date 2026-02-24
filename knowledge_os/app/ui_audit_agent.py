"""
[SINGULARITY 10.0+] UI/UX Audit Agent.
Uses multimodal models to audit frontend screenshots against design standards.
"""

import asyncio
import base64
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UIUXAuditAgent:
    """
    Agent for visual auditing of frontend interfaces.
    Integrates with Vision models to analyze screenshots.
    """

    def __init__(self):
        self.standards_path = os.getenv("UX_STANDARDS_PATH", "docs/UX_STANDARDS.md")

    async def audit_screenshot(
        self, image_base64: str, project_context: str = "general"
    ) -> Dict[str, Any]:
        """
        Perform a visual audit of a screenshot against Apple HIG and Google Material standards.
        """
        logger.info(f"🎨 [UI/UX AUDIT] Starting cognitive audit for project: {project_context}")

        # 1. Load design standards
        standards = ""
        if os.path.exists(self.standards_path):
            with open(self.standards_path, encoding="utf-8") as f:
                standards = f.read()

        # 2. Prepare prompt for Vision model with "Giant Knowledge" (Apple HIG / Material)
        prompt = f"""
        Ты - Элитный UI/UX Аудитор (Елена). Твоя база знаний включает Apple HIG и Google Material Design.
        Проведи глубокий визуальный аудит данного скриншота.

        ПРОЕКТ: {project_context}

        СТАНДАРТЫ ПРОЕКТА:
        {standards}

        ЗАДАЧА:
        1. ВИЗУАЛЬНЫЙ АНАЛИЗ: Оцени композицию, баланс белого пространства и иерархию.
        2. СООТВЕТСТВИЕ СТАНДАРТАМ: Найди отклонения от Apple HIG (для Mac/iOS стиля) или Material Design.
        3. ТЕХНИЧЕСКИЕ ОШИБКИ: Наложение текста, плохая контрастность, неровные отступы.
        4. ПАТЧ-ПЛАН: Сформулируй конкретные CSS/HTML правки для исправления.

        ВЕРНИ ОТВЕТ В ФОРМАТЕ:
        ### 🚨 КРИТИЧЕСКИЕ ОШИБКИ (UI BUGS):
        - [ ] ...
        ### 📐 НАРУШЕНИЕ ГАЙДЛАЙНОВ (HIG/Material):
        - ...
        ### 💡 UX РЕКОМЕНДАЦИИ (Улучшение конверсии/удобства):
        - ...
        ### 🛠️ ТЕХНИЧЕСКОЕ ЗАДАНИЕ ДЛЯ VERONICA (CSS/HTML Fixes):
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
                "project": project_context,
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
