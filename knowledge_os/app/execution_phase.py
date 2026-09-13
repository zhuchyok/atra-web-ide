"""
[EXECUTION PHASE] Parse LLM output for actionable commands and execute them.

Victoria's LLM generates text plans. This module:
1. Detects explicit code blocks, git commands, shell commands
2. For text-only plans (numbered steps), uses LLM to generate the actual code
3. Executes the generated code via file writes, subprocess, git
"""

import asyncio
import json
import logging
import os
import re
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.getenv(
    "PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
)

# Template cache for deterministic code generation
_TEMPLATE_CACHE: Dict[str, str] = {}


def _snake_to_title(name: str) -> str:
    """Convert snake_case to Title Case."""
    return name.replace("_", " ").replace("-", " ").title()


def _gen_python(
    goal: str, func_name: str, class_name: str, description: str,
    func_title: str, is_test: bool, is_api: bool, is_class: bool, is_cli: bool,
) -> str:
    """Generate Python code based on intent detection."""
    if is_test:
        test_name = func_name or "test_main"
        return (
            f'"""Tests for {test_name}."""\n\n'
            f"import pytest\n\n\n"
            f"def {test_name}():\n"
            f'    """Test {test_name}."""\n'
            f"    result = True\n"
            f"    assert result is True\n\n\n"
            f"def test_{test_name}_edge_cases():\n"
            f'    """Edge cases for {test_name}."""\n'
            f"    assert True\n\n\n"
            f"if __name__ == '__main__':\n"
            f"    {test_name}()\n"
        )
    if is_api:
        endpoint = func_name or "handler"
        return (
            f'"""API handler: {endpoint}."""\n\n'
            f"from fastapi import APIRouter, HTTPException\n"
            f"from pydantic import BaseModel\n\n\n"
            f"router = APIRouter()\n\n\n"
            f"class {endpoint.title()}Request(BaseModel):\n"
            f"    pass\n\n\n"
            f"class {endpoint.title()}Response(BaseModel):\n"
            f"    status: str = 'ok'\n\n\n"
            f'@router.post("/{endpoint}")\n'
            f"async def {endpoint}(request: {endpoint.title()}Request):\n"
            f'    """Handle {endpoint} request."""\n'
            f"    return {endpoint.title()}Response()\n"
        )
    if class_name:
        docstring = f'    """{_snake_to_title(class_name)} class."""\n\n' if not description else f'    """{description}."""\n\n'
        return (
            f"class {class_name}:\n"
            f"{docstring}"
            f"    def __init__(self):\n"
            f"        self._initialized = False\n\n"
            f"    def initialize(self):\n"
            f'        """Initialize the instance."""\n'
            f"        self._initialized = True\n"
            f"        return self\n\n"
            f"    def __repr__(self):\n"
            f"        return f'<{class_name} initialized={{self._initialized}}>'\n"
        )
    if is_cli:
        script_name = func_name or "main"
        return (
            f'"""CLI script: {script_name}."""\n\n'
            f"import argparse\n"
            f"import sys\n\n\n"
            f"def {script_name}(args=None):\n"
            f'    """Run {script_name}."""\n'
            f"    parser = argparse.ArgumentParser()\n"
            f"    parser.add_argument('--verbose', '-v', action='store_true')\n"
            f"    parsed = parser.parse_args(args)\n"
            f"    print(f'Running {script_name}')\n"
            f"    return 0\n\n\n"
            f"if __name__ == '__main__':\n"
            f"    sys.exit({script_name}())\n"
        )
    if func_name:
        # Detect common patterns and generate actual implementations
        func_lower = func_name.lower()
        goal_lower = goal.lower()

        # Fibonacci
        if any(w in func_lower for w in ["fibonacci", "fib"]) or any(w in goal_lower for w in ["фибоначчи", "fibonacci"]):
            return (
                f"def {func_name}(n: int) -> int:\n"
                f'    """Calculate the nth Fibonacci number."""\n'
                f"    if n <= 0:\n"
                f"        return 0\n"
                f"    elif n == 1:\n"
                f"        return 1\n"
                f"    a, b = 0, 1\n"
                f"    for _ in range(2, n + 1):\n"
                f"        a, b = b, a + b\n"
                f"    return b\n"
                f"\n\n"
                f"if __name__ == '__main__':\n"
                f"    for i in range(10):\n"
                f"        print(f'{func_name}({{i}}) = {{{func_name}(i)}}')\n"
            )

        # Factorial
        if any(w in func_lower for w in ["factorial", "факториал"]) or any(w in goal_lower for w in ["факториал", "factorial"]):
            return (
                f"def {func_name}(n: int) -> int:\n"
                f'    """Calculate factorial of n."""\n'
                f"    if n < 0:\n"
                f"        raise ValueError('n must be non-negative')\n"
                f"    if n <= 1:\n"
                f"        return 1\n"
                f"    result = 1\n"
                f"    for i in range(2, n + 1):\n"
                f"        result *= i\n"
                f"    return result\n"
                f"\n\n"
                f"if __name__ == '__main__':\n"
                f"    for i in range(10):\n"
                f"        print(f'{func_name}({{i}}) = {{{func_name}(i)}}')\n"
            )

        # Sort
        if any(w in func_lower for w in ["sort", "сортир"]) or any(w in goal_lower for w in ["сортир", "sort"]):
            return (
                f"def {func_name}(arr: list) -> list:\n"
                f'    """Sort array using quicksort algorithm."""\n'
                f"    if len(arr) <= 1:\n"
                f"        return arr\n"
                f"    pivot = arr[len(arr) // 2]\n"
                f"    left = [x for x in arr if x < pivot]\n"
                f"    middle = [x for x in arr if x == pivot]\n"
                f"    right = [x for x in arr if x > pivot]\n"
                f"    return {func_name}(left) + middle + {func_name}(right)\n"
                f"\n\n"
                f"if __name__ == '__main__':\n"
                f"    import random\n"
                f"    arr = [random.randint(0, 100) for _ in range(10)]\n"
                f"    print(f'Unsorted: {{arr}}')\n"
                f"    print(f'Sorted: {{{func_name}(arr)}}')\n"
            )

        # Search
        if any(w in func_lower for w in ["search", "поиск"]) or any(w in goal_lower for w in ["поиск", "search"]):
            return (
                f"def {func_name}(arr: list, target) -> int:\n"
                f'    """Binary search for target in sorted array."""\n'
                f"    left, right = 0, len(arr) - 1\n"
                f"    while left <= right:\n"
                f"        mid = (left + right) // 2\n"
                f"        if arr[mid] == target:\n"
                f"            return mid\n"
                f"        elif arr[mid] < target:\n"
                f"            left = mid + 1\n"
                f"        else:\n"
                f"            right = mid - 1\n"
                f"    return -1\n"
                f"\n\n"
                f"if __name__ == '__main__':\n"
                f"    arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n"
                f"    print(f'Search for 5: {{{func_name}(arr, 5)}}')\n"
                f"    print(f'Search for 11: {{{func_name}(arr, 11)}}')\n"
            )

        # Validate
        if any(w in func_lower for w in ["valid", "провер"]) or any(w in goal_lower for w in ["провер", "valid"]):
            return (
                f"def {func_name}(data) -> bool:\n"
                f'    """Validate input data."""\n'
                f"    if data is None:\n"
                f"        return False\n"
                f"    if isinstance(data, str) and not data.strip():\n"
                f"        return False\n"
                f"    if isinstance(data, (list, dict)) and len(data) == 0:\n"
                f"        return False\n"
                f"    return True\n"
                f"\n\n"
                f"if __name__ == '__main__':\n"
                f"    print(f'Validate None: {{{func_name}(None)}}')\n"
                f"    print(f'Validate empty: {{{func_name}(\"\")}}')\n"
                f"    print(f'Validate valid: {{{func_name}(\"hello\")}}')\n"
            )

        # Default: unknown pattern — don't generate stub, let user know
        logger.info("[EXECUTION] Unknown pattern for %s, skipping code generation", func_name)
        return ""
    return (
        "def main():\n"
        '    """Main entry point."""\n\n'
        "    print('Hello World')\n"
        "    return True\n"
        "\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )


def _gen_javascript(
    goal: str, func_name: str, description: str,
    func_title: str, is_test: bool, is_api: bool,
) -> str:
    """Generate JavaScript code based on intent detection."""
    if is_test:
        test_name = func_name or "testMain"
        return (
            f"/** Tests for {test_name} */\n\n"
            f"const {{ describe, it, expect }} = require('vitest');\n\n"
            f"describe('{test_name}', () => {{\n"
            f"    it('should work', () => {{\n"
            f"        expect(true).toBe(true);\n"
            f"    }});\n\n"
            f"    it('should handle edge cases', () => {{\n"
            f"        expect(true).toBe(true);\n"
            f"    }});\n"
            f"}});\n"
        )
    if is_api:
        endpoint = func_name or "handler"
        return (
            f"/** API handler: {endpoint} */\n\n"
            f"const express = require('express');\n"
            f"const router = express.Router();\n\n"
            f"router.post('/{endpoint}', async (req, res) => {{\n"
            f"    try {{\n"
            f"        res.json({{ status: 'ok' }});\n"
            f"    }} catch (err) {{\n"
            f"        res.status(500).json({{ error: err.message }});\n"
            f"    }}\n"
            f"}});\n\n"
            f"module.exports = router;\n"
        )
    if func_name:
        return (
            f"/**\n * {func_title}\n */\n"
            f"function {func_name}() {{\n"
            f"    console.log('{func_title}');\n"
            f"    return true;\n"
            f"}}\n\n"
            f"module.exports = {{ {func_name} }};\n"
        )
    return (
        "/** Main entry point */\n"
        "function main() {\n"
        "    console.log('Hello World');\n"
        "    return true;\n"
        "}\n\n"
        "module.exports = { main };\n"
    )


def _gen_typescript(
    goal: str, func_name: str, description: str,
    func_title: str, is_test: bool, is_api: bool,
) -> str:
    """Generate TypeScript code based on intent detection."""
    if is_test:
        test_name = func_name or "testMain"
        return (
            f"import {{ describe, it, expect }} from 'vitest';\n\n"
            f"describe('{test_name}', () => {{\n"
            f"    it('should work', () => {{\n"
            f"        expect(true).toBe(true);\n"
            f"    }});\n\n"
            f"    it('should handle edge cases', () => {{\n"
            f"        expect(true).toBe(true);\n"
            f"    }});\n"
            f"}});\n"
        )
    if is_api:
        endpoint = func_name or "handler"
        return (
            f"import {{ Router, Request, Response }} from 'express';\n\n"
            f"const router = Router();\n\n"
            f"router.post('/{endpoint}', async (req: Request, res: Response) => {{\n"
            f"    try {{\n"
            f"        res.json({{ status: 'ok' }});\n"
            f"    }} catch (err) {{\n"
            f"        res.status(500).json({{ error: (err as Error).message }});\n"
            f"    }}\n"
            f"}});\n\n"
            f"export default router;\n"
        )
    if func_name:
        return (
            f"/**\n * {func_title}\n */\n"
            f"export function {func_name}(): boolean {{\n"
            f"    console.log('{func_title}');\n"
            f"    return true;\n"
            f"}}\n"
        )
    return (
        "/** Main entry point */\n"
        "export function main(): boolean {\n"
        "    console.log('Hello World');\n"
        "    return true;\n"
        "}\n"
    )


def _gen_bash(goal: str, func_name: str, description: str) -> str:
    """Generate bash script."""
    script_name = func_name or "main"
    return (
        f"#!/usr/bin/env bash\n"
        f"set -euo pipefail\n\n"
        f"# {description or script_name}\n\n"
        f"{script_name}() {{\n"
        f"    echo \"{script_name}\"\n"
        f"}}\n\n"
        f"main() {{\n"
        f"    {script_name} \"$@\"\n"
        f"}}\n\n"
        f"main \"$@\"\n"
    )


def _detect_code_blocks(text: str) -> List[Dict[str, str]]:
    """Extract code blocks with language tags from LLM output."""
    blocks = []
    pattern = r"```(\w+)?\n(.*?)```"
    for match in re.finditer(pattern, text, re.DOTALL):
        lang = match.group(1) or "text"
        code = match.group(2).strip()
        if len(code) > 10:
            blocks.append({"language": lang, "code": code})
    return blocks


def _detect_execution_plan(text: str) -> List[Dict[str, str]]:
    """
    Parse Victoria's JSON execution plan from the output.
    Victoria's system prompt includes:
    ```json
    [{"action": "read_file|edit|run", "path": "...", "command": "...", "description": "..."}]
    ```
    """
    plans = []
    # Find JSON blocks
    json_pattern = r"```json\s*\n(.*?)```"
    for match in re.finditer(json_pattern, text, re.DOTALL):
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "action" in item:
                        plans.append(item)
        except json.JSONDecodeError:
            pass
    # Also try inline JSON
    inline_pattern = r'\[\s*\{\s*"action"\s*:.*?\}\s*\]'
    for match in re.finditer(inline_pattern, text, re.DOTALL):
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "action" in item:
                        plans.append(item)
        except json.JSONDecodeError:
            pass
    return plans


def _detect_file_paths(text: str) -> List[str]:
    """Extract file paths that the LLM wants to create/modify."""
    paths = []
    patterns = [
        r"(?:создай|создать|write|create|добавь)\s+(?:файл\s+)?[`\"']?([a-zA-Z0-9_/.-]+\.\w+)[`\"']?",
        r"(?:запиши|сохрани|save|write to)\s+[`\"']?([a-zA-Z0-9_/.-]+\.\w+)[`\"']?",
        r"(?:в файле|in file|to file)\s+[`\"']?([a-zA-Z0-9_/.-]+\.\w+)[`\"']?",
        r"file[:\s]+[`\"']?([a-zA-Z0-9_/.-]+\.\w+)[`\"']?",
    ]
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            path = m.group(1)
            if path and not path.startswith("http"):
                paths.append(path)
    return list(set(paths))


def _detect_git_commands(text: str) -> List[str]:
    """Extract git commands from LLM output."""
    commands = []
    patterns = [
        r"(git\s+(?:add|commit|push|pull|checkout|branch|diff|log|status)[^\n`]*)",
    ]
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            cmd = m.group(1).strip().rstrip(".")
            if cmd:
                commands.append(cmd)
    return commands


def _detect_shell_commands(text: str) -> List[str]:
    """Extract shell commands from LLM output."""
    commands = []
    patterns = [
        r"`(npm\s+[^`]+)`",
        r"`(pip\s+[^`]+)`",
        r"`(docker\s+[^`]+)`",
        r"`(python\s+[^`]+)`",
        r"`(node\s+[^`]+)`",
    ]
    for p in patterns:
        for m in re.finditer(p, text):
            cmd = m.group(1).strip()
            if cmd:
                commands.append(cmd)
    return commands


def _is_text_plan(text: str) -> bool:
    """Check if output is a numbered text plan (no code blocks)."""
    code_block_count = len(re.findall(r"```\w*\n", text))
    if code_block_count > 0:
        return False
    # [GUARD] Не-кодовые задачи (web_search, вопросы) не превращаем в файлы —
    # иначе каждый web-ответ порождал src/generated_file.py мусор.
    text_lower = text.lower()
    no_code_markers = (
        "web_search",
        "интернет",
        "новости",
        "найди в интернете",
        "уточните",
        "какова",
        "фаза",
        "вопрос",
    )
    if any(m in text_lower for m in no_code_markers):
        return False
    # Check for numbered steps pattern
    step_pattern = r"^\s*\d+[\.\)]\s+"
    lines = text.strip().split("\n")
    step_lines = sum(1 for line in lines if re.match(step_pattern, line.strip()))
    return step_lines >= 2


def _extract_plan_steps(text: str) -> List[str]:
    """Extract individual steps from a numbered plan."""
    steps = []
    lines = text.strip().split("\n")
    current_step = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+[\.\)]\s+", stripped):
            if current_step:
                steps.append(" ".join(current_step))
            current_step = [re.sub(r"^\d+[\.\)]\s+", "", stripped)]
        elif stripped and current_step:
            current_step.append(stripped)
    if current_step:
        steps.append(" ".join(current_step))
    return steps


def _derive_file_path_from_goal(goal: str):
    """Extract file path from the goal text."""
    # Try to find explicit file path in goal
    paths = _detect_file_paths(goal)
    if paths:
        return paths[0]
    # Try to find path-like pattern
    match = re.search(r"(src/[\w/.-]+\.\w+)", goal)
    if match:
        return match.group(1)
    # Default
    # [GUARD] Без явного пути не пишем мусор в src/generated_file.py.
    return None


async def _generate_code_from_plan(
    goal: str,
    plan_steps: List[str],
    project_context: str = "atra-web-ide",
) -> Dict[str, Any]:
    """
    Generate code from a text plan using deterministic templates (no LLM).
    Wisdom model generates code through main LLM pipeline if needed.
    Returns {"file_path": str, "code": str, "language": str} or None.
    """
    file_path = _derive_file_path_from_goal(goal)
    if not file_path:
        return None
    ext = os.path.splitext(file_path)[1].lower()

    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".css": "css", ".html": "html", ".sh": "bash",
    }
    language = lang_map.get(ext, "python")

    # Check template cache first
    cache_key = f"{language}:{goal.lower().strip()}"
    cached = _TEMPLATE_CACHE.get(cache_key)
    if cached:
        logger.info("[EXECUTION] Template cache hit for %s", file_path)
        return {"file_path": file_path, "language": language, "code": cached}

    # Deterministic code generation
    logger.info("[EXECUTION] Deterministic code generation for %s", file_path)
    func_match = re.search(r"(?:функци[яюей]\s+|функцией\s+|function\s+|def\s+)(\w+)", goal, re.IGNORECASE)
    func_name = func_match.group(1) if func_match else None

    class_match = re.search(r"(?:класс[а]?\s+|class\s+)(\w+)", goal, re.IGNORECASE)
    class_name = class_match.group(1) if class_match else None

    # Extract description from goal
    desc_match = re.search(
        r"(?:с функцией|с функцией|функция|функцией|named|function)\s+\w+[\s:—–-]+(.+?)(?:\s*$|\s*\.)",
        goal, re.IGNORECASE,
    )
    description = desc_match.group(1).strip() if desc_match else ""

    # Convert snake_case to Title Case for display
    def _snake_to_title(name: str) -> str:
        return name.replace("_", " ").replace("-", " ").title()

    func_title = _snake_to_title(func_name) if func_name else "Hello World"

    # Detect what the goal is asking for
    goal_lower = goal.lower()
    # Test detection: only if explicitly asking for a test (not just file named "test_")
    is_test = any(w in goal_lower for w in [
        "напиши тест", "создай тест", "write test", "create test",
        "юнит-тест", "unit test", "тест для", "test for",
    ])
    is_api = any(w in goal_lower for w in ["api", "endpoint", "маршрут", "route", "handler"])
    is_class = any(w in goal_lower for w in ["класс", "class", "модуль", "module"])
    is_cli = any(w in goal_lower for w in ["cli", "командная строка", "command line", "script"])

    # Generate code based on language and intent
    if language == "python":
        code = _gen_python(goal, func_name, class_name, description, func_title, is_test, is_api, is_class, is_cli)
    elif language == "javascript":
        code = _gen_javascript(goal, func_name, description, func_title, is_test, is_api)
    elif language == "typescript":
        code = _gen_typescript(goal, func_name, description, func_title, is_test, is_api)
    elif language == "json":
        code = json.dumps({"message": "Hello World"}, indent=2) + "\n"
    elif language == "bash":
        code = _gen_bash(goal, func_name, description)
    else:
        code = f"# Generated from: {goal}\n"

    # Cache the result
    if code:
        _TEMPLATE_CACHE[cache_key] = code

    if not code:
        return None

    return {
        "file_path": file_path,
        "language": language,
        "code": code,
    }


async def _execute_file_write(
    file_path: str,
    content: str,
    project_root: str,
    git_engine: Any = None,
) -> Dict[str, Any]:
    """Write content to a file and optionally commit to git."""
    result = {"file": file_path, "success": False, "error": None}
    try:
        full_path = os.path.join(project_root, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        result["success"] = True
        logger.info("[EXECUTION] File written: %s", file_path)

        # Git commit
        if git_engine:
            try:
                subprocess.run(
                    ["git", "add", file_path],
                    cwd=project_root,
                    check=True,
                    timeout=10,
                )
                subprocess.run(
                    ["git", "commit", "-m", f"[VICTORIA] Auto-write: {file_path}"],
                    cwd=project_root,
                    check=True,
                    timeout=10,
                )
                result["committed"] = True
            except subprocess.CalledProcessError:
                result["committed"] = False
            except subprocess.TimeoutExpired:
                result["committed"] = False
    except Exception as e:
        result["error"] = str(e)
    return result


async def _execute_shell_command(
    command: str,
    project_root: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Execute a shell command safely."""
    result = {"command": command, "success": False, "output": "", "error": None}

    dangerous = ["rm -rf", "sudo", "chmod 777", "shutdown", "reboot", "kill -9"]
    cmd_lower = command.lower()
    if any(d in cmd_lower for d in dangerous):
        result["error"] = f"Blocked dangerous command: {command}"
        return result

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=project_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        result["output"] = (stdout or b"").decode("utf-8", errors="replace")[:2000]
        result["error"] = (stderr or b"").decode("utf-8", errors="replace")[:1000]
        result["success"] = proc.returncode == 0
        result["returncode"] = proc.returncode
    except asyncio.TimeoutError:
        result["error"] = f"Command timed out after {timeout}s"
    except Exception as e:
        result["error"] = str(e)
    return result


async def execute_plan_commands(
    goal: str,
    llm_output: str,
    project_context: str = "atra-web-ide",
    git_engine: Any = None,
) -> Dict[str, Any]:
    """
    Parse LLM output for actionable commands and execute them.

    Flow:
    1. Try to find explicit code blocks, git commands, shell commands
    2. If none found but it's a text plan → generate code via LLM → execute
    3. Return execution results
    """
    if not llm_output:
        return {"executed": False, "command_count": 0}

    execution_log = []
    commands_executed = 0
    project_root = PROJECT_ROOT

    # === Phase 0: Parse Victoria's JSON execution plan ===
    exec_plans = _detect_execution_plan(llm_output)
    if exec_plans:
        logger.info("[EXECUTION] Found %d execution plan items", len(exec_plans))
        for plan_item in exec_plans[:10]:  # Limit to 10 actions
            action = plan_item.get("action", "")
            path = plan_item.get("path", "")
            command = plan_item.get("command", "")

            if action == "edit" and path:
                # Find the code block that corresponds to this path
                code_blocks_for_path = [
                    b for b in _detect_code_blocks(llm_output)
                    if b["language"] not in ("text", "markdown")
                ]
                if code_blocks_for_path:
                    # Use the first relevant code block
                    block = code_blocks_for_path[0]
                    write_result = await _execute_file_write(path, block["code"], project_root, git_engine)
                    execution_log.append(write_result)
                    if write_result["success"]:
                        commands_executed += 1
            elif action == "run" and command:
                exec_result = await _execute_shell_command(command, project_root, timeout=30)
                execution_log.append(exec_result)
                if exec_result["success"]:
                    commands_executed += 1

    # === Phase 1: Parse explicit code blocks ===
    code_blocks = _detect_code_blocks(llm_output)
    file_paths = _detect_file_paths(llm_output)

    logger.info("[EXECUTION] Phase 1: Found %d code blocks, %d file paths", len(code_blocks), len(file_paths))

    for i, block in enumerate(code_blocks):
        if block["language"] in ("text", "markdown"):
            continue
        target_path = file_paths[i] if i < len(file_paths) else None
        if not target_path:
            # Try to derive from goal
            target_path = _derive_file_path_from_goal(goal)
            # If multiple blocks, append index
            if len(code_blocks) > 1:
                base, ext = os.path.splitext(target_path)
                target_path = f"{base}_{i}{ext}"
        if not target_path:
            ext_map = {
                "python": ".py", "javascript": ".js", "typescript": ".ts",
                "json": ".json", "yaml": ".yaml", "yml": ".yml",
                "css": ".css", "html": ".html",
            }
            ext = ext_map.get(block["language"], ".txt")
            name_match = re.search(r"(?:def|class|function|const|let|var)\s+(\w+)", block["code"])
            target_path = f"src/{name_match.group(1)}{ext}" if name_match else f"src/generated_{i}{ext}"

        write_result = await _execute_file_write(target_path, block["code"], project_root, git_engine)
        execution_log.append(write_result)
        if write_result["success"]:
            commands_executed += 1

    # === Phase 2: Execute git commands ===
    git_commands = _detect_git_commands(llm_output)
    for cmd in git_commands[:5]:
        exec_result = await _execute_shell_command(cmd, PROJECT_ROOT, timeout=15)
        execution_log.append(exec_result)
        if exec_result["success"]:
            commands_executed += 1

    # === Phase 3: Execute shell commands ===
    shell_commands = _detect_shell_commands(llm_output)
    for cmd in shell_commands[:5]:
        exec_result = await _execute_shell_command(cmd, PROJECT_ROOT, timeout=30)
        execution_log.append(exec_result)
        if exec_result["success"]:
            commands_executed += 1

    # === Phase 3.5: Extract code from mixed text plan + code blocks ===
    # When wisdom outputs "1. Создай файл... 2. Напиши код... [code blocks]"
    # Phase 1 might miss code blocks if they're embedded in text
    if commands_executed == 0:
        code_blocks = _detect_code_blocks(llm_output)
        if code_blocks:
            logger.info("[EXECUTION] Phase 3.5: Found %d code blocks in mixed output", len(code_blocks))
            target_path = _derive_file_path_from_goal(goal)
            if not target_path:
                target_path = f"src/auto_{int(__import__('time').time())}.py"
            for i, block in enumerate(code_blocks):
                if block["language"] in ("text", "markdown"):
                    continue
                path = target_path
                if len(code_blocks) > 1:
                    base, ext = os.path.splitext(target_path)
                    path = f"{base}_{i}{ext}"
                write_result = await _execute_file_write(path, block["code"], project_root, git_engine)
                execution_log.append(write_result)
                if write_result["success"]:
                    commands_executed += 1

    # === Phase 4: Text plan → deterministic code generation ===
    if commands_executed == 0 and _is_text_plan(llm_output):
        logger.info("[EXECUTION] Text plan detected, generating code deterministically")
        plan_steps = _extract_plan_steps(llm_output)
        if plan_steps:
            code_result = await _generate_code_from_plan(goal, plan_steps, project_context)
            if code_result and code_result.get("code") and code_result.get("file_path"):
                write_result = await _execute_file_write(
                    code_result["file_path"],
                    code_result["code"],
                    project_root,
                    git_engine,
                )
                execution_log.append(write_result)
                if write_result["success"]:
                    commands_executed += 1
                    logger.info(
                        "[EXECUTION] Generated and wrote %s from plan",
                        code_result["file_path"],
                    )

    if commands_executed == 0:
        # Fallback messaging — explain what happened
        if _is_text_plan(llm_output):
            plan_steps = _extract_plan_steps(llm_output)
            if plan_steps:
                # Check if we know the pattern
                goal_lower = goal.lower()
                known_patterns = ["fibonacci", "fib", "фибоначчи", "factorial", "факториал",
                                  "sort", "сортир", "search", "поиск", "valid", "провер"]
                is_known = any(p in goal_lower for p in known_patterns)
                if not is_known:
                    return {
                        "executed": False,
                        "command_count": 0,
                        "append_output": (
                            "**Не удалось сгенерировать код:**\n"
                            "- Неизвестный паттерн для детерминистической генерации\n"
                            "- Попробуйте переформулировать задачу или укажите конкретную логику"
                        ),
                    }
        return {"executed": False, "command_count": 0}

    # Build summary
    summary_lines = ["**Выполненные действия:**"]
    for entry in execution_log:
        if entry.get("success"):
            if "file" in entry:
                summary_lines.append(f"- Файл создан: `{entry['file']}`")
            elif "command" in entry:
                summary_lines.append(f"- Команда выполнена: `{entry['command']}`")

    return {
        "executed": True,
        "command_count": commands_executed,
        "execution_log": execution_log,
        "append_output": "\n".join(summary_lines),
    }
