import logging
import os

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

# Имена экспертов → role hint (когда DB role недоступен / не совпал с map)
EXPERT_NAME_TO_ROLE_HINTS = {
    "анна": "qa",
    "игорь": "backend",
    "роман": "backend",
    "сергей": "devops",
    "дмитрий": "ml",
    "татьяна": "documentation",
    "ольга": "backend",
    "алексей": "backend",
    "елена": "devops",
    "виктория": "general",
    "максим": "general",
    "мария": "general",
    "павел": "python",
    "арина": "general",
}


def _folders_for_role_dept(role: str = "", department: str = "") -> list[str]:
    """Match ROLE_DEPARTMENT_TO_SKILLS keys as substrings of role/department (smart-worker style)."""
    role_lower = (role or "").lower()
    dept_lower = (department or "").lower()
    skill_folders: list[str] = []
    for key, folders in ROLE_DEPARTMENT_TO_SKILLS.items():
        if key in role_lower or key in dept_lower:
            for f in folders:
                if f not in skill_folders:
                    skill_folders.append(f)
    return skill_folders


def _read_skill_snippets_sync(skill_folders: list[str], max_chars_per_skill: int = 2000) -> str:
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


def _select_skills_by_relevance_sync(
    task_title: str, task_description: str, max_skills: int = 3
) -> list[str]:
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


async def load_skills_for_expert(
    expert_name: str,
    task_description: str,
    role: str | None = None,
    department: str | None = None,
) -> str:
    """
    Load up to 3 skill snippets for an expert.
    Order: explicit role/dept → name hint → keyword relevance → general.
    """
    skill_folders = _folders_for_role_dept(role or "", department or "")

    if not skill_folders:
        # Direct key match (tests pass role key as expert_name)
        role_key = (expert_name or "").lower().strip()
        skill_folders = list(ROLE_DEPARTMENT_TO_SKILLS.get(role_key, []))

    if not skill_folders:
        hint = EXPERT_NAME_TO_ROLE_HINTS.get((expert_name or "").lower().strip())
        if hint:
            skill_folders = list(ROLE_DEPARTMENT_TO_SKILLS.get(hint, []))

    if not skill_folders:
        skill_folders = _select_skills_by_relevance_sync(expert_name, task_description)

    # Merge task-relevant skills (cap 3 total), same idea as smart_worker
    relevant = _select_skills_by_relevance_sync(expert_name, task_description, 3)
    for f in relevant:
        if f not in skill_folders:
            skill_folders.append(f)

    if not skill_folders:
        skill_folders = list(ROLE_DEPARTMENT_TO_SKILLS.get("general", []))

    skill_folders = skill_folders[:3]
    if not skill_folders:
        return ""
    return _read_skill_snippets_sync(skill_folders)
