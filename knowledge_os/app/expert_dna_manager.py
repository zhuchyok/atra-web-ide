import logging
import os
from typing import Dict, Optional

import asyncpg

logger = logging.getLogger(__name__)


class ExpertDNAManager:
    """
    [SINGULARITY 21.17] Expert DNA Manager.
    Handles dynamic loading of expert-specific rules (.mdc) and specialization context.
    """

    def __init__(self, db_url: str, rules_dir: str = ".cursor/rules"):
        self.db_url = db_url
        self.rules_dir = rules_dir
        self._rules_cache: Dict[str, str] = {}

    async def get_expert_dna(self, expert_name: str) -> str:
        """
        Retrieves the full DNA (rules + specialization) for a given expert.
        Prioritizes DB overrides [SINGULARITY 21.18].
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Fetch expert specialization info and dynamic overrides
                row = await conn.fetchrow(
                    """
                    SELECT e.id, e.specialization_level, e.rule_file, e.department, e.role,
                           o.custom_instructions as dynamic_override
                    FROM experts e
                    LEFT JOIN expert_dna_overrides o ON e.id = o.expert_id AND o.is_active = TRUE
                    WHERE e.name = $1
                    ORDER BY o.updated_at DESC
                    LIMIT 1
                """,
                    expert_name,
                )

                if not row:
                    return ""

                dna_parts = []
                level = row["specialization_level"] or "PRO"
                rule_file = row["rule_file"]
                dynamic_override = row["dynamic_override"]

                dna_parts.append(f"🧬 EXPERT SPECIALIZATION: {level} (AUTOMATED)")
                dna_parts.append(f"👤 ROLE: {row['role']} | 📁 DEPT: {row['department']}")

                # 1. [SINGULARITY 21.18] Priority: Dynamic DB Overrides
                if dynamic_override:
                    dna_parts.append(f"\n### ⚡️ DYNAMIC DNA OVERRIDE (DB):\n{dynamic_override}")
                    logger.info(f"🚀 [EXPERT DNA] Applied dynamic override for {expert_name}")

                # 2. Fallback: Load rule file content if exists
                if rule_file:
                    rule_content = await self._load_rule_file(rule_file)
                    if rule_content:
                        dna_parts.append(f"\n### 📜 BASE EXPERT RULES (.mdc):\n{rule_content}")

                return "\n".join(dna_parts) + "\n"

            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error loading expert DNA for {expert_name}: {e}")
            return ""

    async def _load_rule_file(self, filename: str) -> Optional[str]:
        """Loads and caches rule file content."""
        if filename in self._rules_cache:
            return self._rules_cache[filename]

        # Try multiple possible locations for rules
        possible_paths = [
            os.path.join(os.getcwd(), self.rules_dir, filename),
            os.path.join("/app/project", self.rules_dir, filename),
            os.path.join(os.environ.get("PROJECT_ROOT", "/app"), self.rules_dir, filename),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        content = f.read()
                        # Basic stripping of frontmatter if exists
                        if content.startswith("---"):
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                content = parts[2].strip()

                        self._rules_cache[filename] = content
                        return content
                except Exception as e:
                    logger.warning(f"Failed to read rule file {path}: {e}")

        return None


# Singleton instance for easy access
_dna_manager = None


def get_expert_dna_manager():
    global _dna_manager
    if _dna_manager is None:
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
        _dna_manager = ExpertDNAManager(db_url)
    return _dna_manager
