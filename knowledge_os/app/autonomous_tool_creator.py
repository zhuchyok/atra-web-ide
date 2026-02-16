"""
[SINGULARITY 12.0] Autonomous Tool Creator.
Enables Victoria to autonomously generate, test, and register new tools (skills) 
when existing capabilities are insufficient.
"""

import os
import logging
import asyncio
import json
import uuid
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

class AutonomousToolCreator:
    """
    Metacognitive Tool Creation: Victoria's ability to expand her own toolset.
    """
    
    def __init__(self):
        self.skills_dir = os.getenv("WORKSPACE_SKILLS_DIR", "/app/skills")
        self.sandbox_enabled = os.getenv("USE_SANDBOX", "true").lower() == "true"
        
    async def identify_skill_need(self, error_message: str, goal: str) -> Optional[str]:
        """
        Analyzes an execution failure to determine if a new tool is needed.
        """
        analysis_prompt = f"""
        Analyze the following execution failure and goal. 
        Determine if the failure is due to a missing specialized tool or capability.
        If yes, describe the exact functionality needed for a new tool.
        
        GOAL: {goal}
        ERROR: {error_message}
        
        Return JSON:
        {{
            "needs_new_tool": true|false,
            "tool_name": "name_of_the_needed_tool",
            "tool_description": "detailed description of what the tool should do",
            "required_parameters": ["param1", "param2"]
        }}
        """
        try:
            from ai_core import run_smart_agent_async
            response = await run_smart_agent_async(analysis_prompt, expert_name="Architect", category="reasoning")
            
            # Extract JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Failed to identify skill need: {e}")
        return None

    async def generate_tool_code(self, tool_spec: Dict[str, Any]) -> Optional[str]:
        """
        Generates Python code for the new tool.
        """
        code_prompt = f"""
        Generate a Python function for a new tool based on this specification:
        NAME: {tool_spec['tool_name']}
        DESCRIPTION: {tool_spec['tool_description']}
        PARAMETERS: {tool_spec['required_parameters']}
        
        Requirements:
        1. Function must be asynchronous if it performs I/O.
        2. Use standard libraries or already installed packages.
        3. Include docstrings and error handling.
        4. The function should be self-contained.
        
        Return ONLY the Python code for the function.
        """
        try:
            from ai_core import run_smart_agent_async
            code = await run_smart_agent_async(code_prompt, expert_name="Developer", category="coding")
            # Clean up code (remove markdown fences)
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()
            return code
        except Exception as e:
            logger.error(f"Failed to generate tool code: {e}")
        return None

    async def test_and_register_tool(self, tool_name: str, description: str, code: str, category: str = "dynamic") -> bool:
        """
        Tests the generated code in a sandbox and registers it as a permanent skill.
        """
        logger.info(f"🛠️ [TOOL CREATOR] Testing and registering tool: {tool_name}")
        
        # 1. Create SKILL.md for the registry
        skill_path = Path(self.skills_dir) / tool_name
        skill_path.mkdir(parents=True, exist_ok=True)
        
        skill_md_content = f"""---
name: {tool_name}
description: {description}
category: {category}
version: 1.0.0
author: Victoria Autonomous Creator
---

### Instructions
This tool was autonomously generated to solve a specific need.

### Code
```python
{code}
```
"""
        (skill_path / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
        
        # 2. Save the actual implementation file
        impl_file = skill_path / f"{tool_name}.py"
        impl_file.write_text(code, encoding="utf-8")
        
        # 3. Test in Sandbox (simplified for now: syntax check)
        try:
            import py_compile
            py_compile.compile(str(impl_file), doraise=True)
            logger.info(f"✅ [TOOL CREATOR] Syntax check passed for {tool_name}")
        except Exception as e:
            logger.error(f"❌ [TOOL CREATOR] Syntax check failed for {tool_name}: {e}")
            return False
            
        # 4. Register in Skill Registry
        try:
            from skill_registry import get_skill_registry
            registry = get_skill_registry()
            registry.load_skills() # Reload to include new skill
            logger.info(f"🚀 [TOOL CREATOR] Tool {tool_name} successfully registered.")
            return True
        except Exception as e:
            logger.error(f"Failed to register tool: {e}")
            return False

    async def create_tool_on_the_fly(self, error_message: str, goal: str) -> bool:
        """
        Full cycle of autonomous tool creation.
        """
        spec = await self.identify_skill_need(error_message, goal)
        if spec and spec.get("needs_new_tool"):
            logger.info(f"💡 [TOOL CREATOR] Victoria decided to create a new tool: {spec['tool_name']}")
            code = await self.generate_tool_code(spec)
            if code:
                return await self.test_and_register_tool(spec['tool_name'], spec['tool_description'], code)
        return False

_instance = None
def get_autonomous_tool_creator():
    global _instance
    if _instance is None:
        _instance = AutonomousToolCreator()
    return _instance
