import asyncio
import os
import json
import logging
import yaml
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("skill_refinement")

SKILLS_DIR = Path("knowledge_os/app/skills")

async def refine_skills():
    """
    [SINGULARITY 24.0] Autonomous Skill Refinement.
    Виктория анализирует старые навыки и обновляет их на основе недавних успехов.
    """
    logger.info("🧠 [REFINEMENT] Starting Autonomous Skill Refinement cycle...")

    try:
        from knowledge_os.app.ai_core import run_smart_agent_async

        # 1. Получаем список всех навыков
        skill_files = list(SKILLS_DIR.glob("**/SKILL.md"))
        if not skill_files:
            logger.info("😴 [REFINEMENT] No skills found to refine.")
            return

        # Для теста возьмем 2 случайных или старых навыка (чтобы не перегружать Mac Studio)
        # В реальности можно фильтровать по дате изменения
        target_skills = [s for s in skill_files if "procedural" in str(s)]
        if not target_skills:
            target_skills = skill_files[:2]

        for skill_path in target_skills:
            logger.info(f"🔍 [REFINEMENT] Auditing skill: {skill_path}")

            with open(skill_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 2. Просим Викторию проанализировать навык
            audit_prompt = f"""### ЗАДАЧА: АУДИТ НАВЫКА (Autonomous Refinement)
Ты — Виктория, Team Lead. Проанализируй текущий навык (SOP) и предложи улучшения на основе эры Singularity 24.0 (скорость, точность, гибридный RAG, локальные модели).

ТЕКУЩИЙ НАВЫК:
{content}

ЗАДАНИЕ:
1. Найди устаревшие инструкции.
2. Добавь советы по оптимизации токенов.
3. Уточни процедуру для локальных моделей (lfm2.5-thinking, victoria-wisdom-v3.5).
4. Верни ОБНОВЛЕННЫЙ текст файла SKILL.md полностью.
"""

            refined_content = await run_smart_agent_async(audit_prompt, category="reasoning")

            if refined_content and "---" in refined_content:
                # 3. Сохраняем обновленный навык
                # Извлекаем только блок Markdown (если модель добавила лишний текст)
                if "```markdown" in refined_content:
                    refined_content = refined_content.split("```markdown")[1].split("```")[0].strip()
                elif "```" in refined_content:
                    refined_content = refined_content.split("```")[1].split("```")[0].strip()

                with open(skill_path, "w", encoding="utf-8") as f:
                    f.write(refined_content.strip())

                logger.info(f"✅ [REFINEMENT] Skill refined and updated: {skill_path}")
            else:
                logger.warning(f"⚠️ [REFINEMENT] Failed to get valid refinement for {skill_path}")

    except Exception as e:
        logger.error(f"❌ [REFINEMENT] Refinement cycle failed: {e}")

if __name__ == "__main__":
    asyncio.run(refine_skills())
