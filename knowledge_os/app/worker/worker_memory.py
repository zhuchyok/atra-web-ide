import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Маппинг role/department → папки скиллов
ROLE_DEPARTMENT_TO_SKILLS = {
    "backend": ["backend-development", "code-review"],
    "qa": ["qa-regression", "webapp-testing"],
    "frontend": ["frontend-design", "webapp-testing"],
    "python": ["python-development", "code-documentation"],
    "devops": ["observability", "disaster-recovery"],
    "ml": ["llm-application-dev", "model-ensemble"],
    "documentation": ["code-documentation", "doc-coauthoring"],
    "general": ["ask-questions-if-underspecified", "code-review"],
}

def _read_skill_snippets_sync(skill_folders: List[str], max_chars_per_skill: int = 2000) -> str:
    """Читает первые max_chars_per_skill символов из SKILL.md для каждой папки."""
    skills_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
    parts = []
    for folder in skill_folders[:3]:
        path = os.path.join(skills_dir, folder, "SKILL.md")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            if "---" in raw:
                parts_fm = raw.split("---", 2)
                text = parts_fm[2].strip() if len(parts_fm) >= 3 else raw
            else:
                text = raw
            snippet = text[:max_chars_per_skill]
            if len(text) > max_chars_per_skill:
                snippet += "\n..."
            parts.append(f"[{folder}]\n{snippet}")
        except Exception as e:
            logger.debug("Skill read failed %s: %s", path, e)
    if not parts:
        return ""
    return "\n\n📋 ИНСТРУКЦИИ ИЗ СКИЛЛОВ (используй при решении):\n" + "\n\n---\n\n".join(parts)

def _get_skill_description_sync(skills_dir: str, folder: str) -> str:
    """Читает из SKILL.md description из frontmatter или имя папки."""
    path = os.path.join(skills_dir, folder, "SKILL.md")
    if not os.path.isfile(path):
        return folder.replace("-", " ")
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read(1500)
        if "---" in raw and "description:" in raw.lower():
            for line in raw.split("\n"):
                if line.strip().lower().startswith("description:"):
                    return line.split(":", 1)[1].strip().strip('"') + " " + folder.replace("-", " ")
        return folder.replace("-", " ")
    except Exception:
        return folder.replace("-", " ")

def _select_skills_by_relevance_sync(task_title: str, task_description: str, max_skills: int = 3) -> List[str]:
    """Выбирает до max_skills скиллов по ключевым словам задачи."""
    skills_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
    if not os.path.isdir(skills_dir):
        return []
    task_text = f"{task_title} {task_description}".lower()
    task_words = set(_ for _ in task_text.replace("-", " ").split() if len(_) > 1)
    scored = []
    for folder in os.listdir(skills_dir):
        if not os.path.isdir(os.path.join(skills_dir, folder)) or folder.startswith("."):
            continue
        desc = _get_skill_description_sync(skills_dir, folder).lower()
        desc_words = set(_ for _ in desc.replace("-", " ").split() if len(_) > 1)
        overlap = len(task_words & desc_words)
        if overlap > 0 or folder.replace("-", " ") in task_text:
            scored.append((overlap + (2 if folder.replace("-", " ") in task_text else 0), folder))
    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored[:max_skills]]
