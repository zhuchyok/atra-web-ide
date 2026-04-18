"""
Function Caller - LLM-powered function calling (OpenAI tool_calls pattern)

Usage:
    from function_caller import FunctionCaller, Tool

    # Define tools
    tools = [
        Tool(name="search", description="Search the web", args={"type": "object", "properties": {"query": {"type": "string"}}}),
    ]

    caller = FunctionCaller(tools)
    result = await caller.call("Найди информацию про Python")
"""

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MLX_URL = os.getenv("MLX_API_URL", "http://localhost:11435")


class Tool(BaseModel):
    name: str
    description: str
    args: Dict[str, Any] = Field(default_factory=dict)


class FunctionCall(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class FunctionCaller:
    """
    Function Calling - LLM вызывает функции автоматически.
    Pattern: OpenAI tool_calls + Anthropic.
    """

    def __init__(self, tools: List[Tool], model: str = "victoria-wisdom-v3.5"):
        self.tools = tools
        self.model = model
        self._tool_map: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable):
        self._tool_map[name] = func

    async def call(self, prompt: str) -> Dict[str, Any]:
        parsed = await self._parse_function_call(prompt)
        if not parsed:
            return {"type": "text", "content": prompt}

        func_name = parsed.name
        args = parsed.arguments

        if func_name in self._tool_map:
            try:
                result = await self._tool_map[func_name](**args)
                return {"type": "function", "name": func_name, "result": result}
            except Exception as e:
                logger.error(f"[FunctionCaller] {func_name} failed: {e}")
                return {"type": "error", "message": str(e)}

        return {"type": "text", "content": f"Function {func_name} not found"}

    async def _parse_function_call(self, prompt: str) -> Optional[FunctionCall]:
        import httpx

        tools_desc = "\n".join(f"- {t.name}: {t.description}" for t in self.tools)

        system_prompt = f"""You are a function calling assistant.
Available functions:
{tools_desc}

If the user wants to use a function, respond with:
FUNCTION: function_name
ARGS: {{"arg1": "value1"}}

If no function needed, respond with:
FUNCTION: none

User request: {prompt}
Response:"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{MLX_URL.rstrip('/')}/api/generate",
                    json={
                        "prompt": system_prompt,
                        "stream": False,
                        "options": {"temperature": 0.1},
                    },
                )
                if resp.status_code != 200:
                    return None

                text = resp.json().get("response", "").strip()

                if "FUNCTION: none" in text:
                    return None

                for tool in self.tools:
                    if f"FUNCTION: {tool.name}" in text:
                        try:
                            args_start = text.find("ARGS:")
                            if args_start > 0:
                                args_str = text[args_start + 5 :].strip()
                                args = json.loads(args_str) if args_str.startswith("{") else {}
                            else:
                                args = {}
                            return FunctionCall(name=tool.name, arguments=args)
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            logger.debug(f"[FunctionCaller] Parse failed: {e}")
        return None


async def call_function(prompt: str, tools: List[Tool]) -> Dict[str, Any]:
    caller = FunctionCaller(tools)
    return await caller.call(prompt)


_instance: Optional[FunctionCaller] = None


def get_function_caller(tools: List[Tool]) -> FunctionCaller:
    return FunctionCaller(tools)
