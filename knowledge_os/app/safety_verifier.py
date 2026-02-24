import ast
import json
import logging
import os
from typing import Any, Dict, List, Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None

try:
    from ai_core import run_smart_agent_async
except ImportError:

    async def run_smart_agent_async(prompt, **kwargs):
        return None


try:
    from graphrag.graphrag_service import get_graphrag_service
except ImportError:

    def get_graphrag_service():
        return None


logger = logging.getLogger(__name__)


class SafetyVerifier:
    """
    [SINGULARITY 10.0+] Safety Verification via GraphRAG (Impact Analysis).
    Verifies if a proposed mutation is safe by analyzing downstream dependencies.
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"
        )

    async def verify_mutation(
        self, module_name: str, function_name: str, mutated_code: str
    ) -> Dict[str, Any]:
        """
        Takes a proposed mutation and returns a safety score and risk factors.
        """
        logger.info(f"🛡️ [SAFETY] Starting impact analysis for {module_name}.{function_name}...")

        try:
            # 1. Analyze mutated code for signature
            mutated_args = self._extract_function_args(mutated_code, function_name)

            # 2. Use GraphRAG to identify downstream dependencies
            dependencies = await self._get_downstream_dependencies(module_name, function_name)

            # 3. Generate Impact Analysis prompt for local judge model
            audit_prompt = self._generate_audit_prompt(
                module_name, function_name, mutated_args, mutated_code, dependencies
            )

            # 4. Call local judge model (qwq:32b or qwen2.5-coder:32b as per project rules)
            audit_json = await run_smart_agent_async(
                audit_prompt,
                expert_name="Виктория",
                category="safety_audit",
                model="qwen2.5-coder:32b",  # Using qwen2.5-coder:32b as preferred in rules
            )

            # 5. Parse and return result
            return self._parse_audit_result(audit_json)

        except Exception as e:
            logger.error(f"Safety verification failed: {e}")
            return {
                "safety_score": 0,
                "risks": [f"Verification error: {str(e)}"],
                "recommendation": "abort",
            }

    def _extract_function_args(self, code: str, function_name: str) -> List[str]:
        """Extracts argument names from the mutated function code."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Handle both top-level functions and methods
                    current_name = node.name
                    if current_name == function_name or (
                        "." in function_name and function_name.split(".")[-1] == current_name
                    ):
                        return [arg.arg for arg in node.args.args]
            return []
        except Exception as e:
            logger.warning(f"Failed to parse AST for args extraction: {e}")
            return []

    async def _get_downstream_dependencies(
        self, module_name: str, function_name: str
    ) -> List[Dict[str, Any]]:
        """Uses GraphRAG and DB queries to find who calls this function."""
        callers = []
        if not asyncpg:
            return callers

        try:
            conn = await asyncpg.connect(self.db_url)
            # Find the node for this function in knowledge_nodes
            # We look for nodes that represent this function/module
            func_node_id = await conn.fetchval(
                """
                SELECT id FROM knowledge_nodes
                WHERE (metadata->>'file_path' LIKE $1 OR metadata->>'file_path' LIKE $2)
                AND content LIKE $3
                LIMIT 1
            """,
                f"%{module_name}.py",
                f"%{module_name}%",
                f"%def {function_name}%",
            )

            if func_node_id:
                # Find nodes that have a 'calls' link to this function
                caller_nodes = await conn.fetch(
                    """
                    SELECT kn.content, kn.metadata->>'file_path' as file_path, kn.metadata->>'name' as name
                    FROM knowledge_links kl
                    JOIN knowledge_nodes kn ON kl.source_node_id = kn.id
                    WHERE kl.target_node_id = $1 AND kl.link_type = 'calls'
                """,
                    func_node_id,
                )
                callers = [dict(c) for c in caller_nodes]

            await conn.close()
        except Exception as e:
            logger.error(f"Error fetching dependencies from DB: {e}")

        return callers

    def _generate_audit_prompt(
        self, module: str, function: str, args: List[str], code: str, deps: List[Dict[str, Any]]
    ) -> str:
        deps_str = (
            json.dumps(deps, indent=2) if deps else "No downstream dependencies found in graph."
        )

        return f"""
ВЫ - ЭКСПЕРТ ПО БЕЗОПАСНОСТИ И КАЧЕСТВУ КОДА (QA/SRE).
ЗАДАЧА: Провести анализ влияния (Impact Analysis) для архитектурной мутации.

МОДУЛЬ: {module}
ФУНКЦИЯ: {function}
НОВАЯ СИГНАТУРА (АРГУМЕНТЫ): {args}

СПИСОК ЗАВИСИМЫХ КОМПОНЕНТОВ (DOWNSTREAM DEPENDENCIES) ИЗ GRAPHRAG:
{deps_str}

НОВЫЙ КОД МУТАЦИИ:
```python
{code}
```

ВОПРОСЫ ДЛЯ АНАЛИЗА:
1. Основываясь на этих зависимостях, сломает ли изменение {function} компоненты {", ".join([d.get("name", "Unknown") for d in deps]) if deps else "системы"}?
2. Есть ли изменения в сигнатуре (удаление аргументов, изменение типов), которые не учтены в вызовах?
3. Есть ли побочные эффекты (side effects), которые могут повлиять на стабильность?

ПРАВИЛА ОЦЕНКИ:
- Score 0-100.
- Если сигнатура изменилась несовместимым образом -> Score < 30.
- Если есть риск side effects или race conditions -> Score < 60.
- Если мутация безопасна и сохраняет обратную совместимость -> Score > 80.

ВЕРНИТЕ ОТВЕТ В JSON:
{{
    "safety_score": int (0-100),
    "risks": ["риск 1", "риск 2"],
    "recommendation": "abort" или "proceed"
}}
"""

    def _parse_audit_result(self, audit_json: str) -> Dict[str, Any]:
        try:
            if not audit_json:
                return {
                    "safety_score": 0,
                    "risks": ["No response from judge model"],
                    "recommendation": "abort",
                }

            if "```json" in audit_json:
                audit_json = audit_json.split("```json")[1].split("```")[0].strip()
            elif "```" in audit_json:
                audit_json = audit_json.split("```")[1].split("```")[0].strip()

            result = json.loads(audit_json)
            # Ensure safety_score is 0-100
            score = result.get("safety_score", 0)
            if isinstance(score, float) and score <= 1.0:
                score = int(score * 100)

            return {
                "safety_score": score,
                "risks": result.get("risks", ["Unknown risk"]),
                "recommendation": result.get("recommendation", "abort"),
            }
        except Exception as e:
            logger.error(f"Failed to parse safety audit JSON: {e}")
            return {
                "safety_score": 0,
                "risks": [f"Audit parsing error: {str(e)}"],
                "recommendation": "abort",
            }
