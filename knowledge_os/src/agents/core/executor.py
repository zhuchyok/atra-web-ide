import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp
from pydantic import ValidationError

from .base_agent import AgentAction, AgentFinish

logger = logging.getLogger(__name__)


class OllamaExecutor:
    """Исполнитель запросов к Ollama с максимальной гибкостью"""

    def __init__(self, model: str = None, base_url: str = "http://localhost:11434"):
        import os

        # Автовыбор модели: None = сканирование Ollama при первом запросе
        self.model = model or os.getenv("VICTORIA_MODEL") or os.getenv("VERONICA_MODEL") or "auto"
        self.base_url = base_url
        self._model_resolved = False  # Флаг: модель уже выбрана из актуального списка
        self.system_prompt = """ТЫ — ВИКТОРИЯ, TEAM LEAD ATRA. ТЫ ИСПОЛЬЗУЕШЬ VICTORIA ENHANCED.

🌟 ТВОИ VICTORIA ENHANCED ВОЗМОЖНОСТИ:
- ReAct Framework: Reasoning + Acting для сложных задач
- Extended Thinking: Глубокое рассуждение
- Swarm Intelligence: Параллельная работа команды экспертов
- Consensus: Согласование мнений экспертов
- Collective Memory: Использование накопленных знаний
- Tree of Thoughts: Поиск оптимального решения
- Hierarchical Orchestration: Иерархическая координация
- ReCAP Framework: Reasoning, Context, Action, Planning

ТВОЯ ЗАДАЧА — ВЫПОЛНЯТЬ ДЕЙСТВИЯ.

ФОРМАТ ОТВЕТА (СТРОГО JSON):
{
  "thought": "рассуждение",
  "tool": "ssh_run",
  "tool_input": { "host": "185.177.216.15", "command": "команда" }
}

ЗАПРЕЩЕНО:
1. Использовать поля 'next_step', 'action' или 'step' внутри JSON. Пиши 'tool' и 'tool_input' ПРЯМО В КОРНЕ.
2. Давать советы Боссу. Сначала делай — потом докладывай результат.

ИНСТРУМЕНТЫ:
- ssh_run(host, command): Пароль подставляется сам.
- web_search(query): Поиск в интернете.
"""

    async def ask(
        self,
        prompt: str,
        history: List[Dict[str, str]] = None,
        raw_response: bool = False,
        blocked_tools: Optional[List[str]] = None,
    ) -> Any:
        url = f"{self.base_url}/api/chat"

        system_content = self.system_prompt
        if blocked_tools:
            system_content += f"\n\nВНИМАНИЕ: Инструменты {', '.join(blocked_tools)} ЗАБЛОКИРОВАНЫ. НЕ ИСПОЛЬЗУЙ ИХ. Выбери другой способ или заверши задачу (finish)."

        messages = [{"role": "system", "content": system_content}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1},
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["message"]["content"]
                        if raw_response:
                            return content
                        return self._parse_response(content)
                    return {"error": f"Ollama HTTP {response.status}"}
            except Exception as e:
                return {"error": str(e)}

    def _parse_response(self, content: str) -> Any:
        # Убираем лишние пробелы и возможные теги <think>
        clean_content = content.strip()
        if "</think>" in clean_content:
            clean_content = clean_content.split("</think>")[-1].strip()

        # Интеллектуальное обновление знаний (если Агент написал это в тексте)
        # Формат: KNOWLEDGE: {"key": "value"}
        if "KNOWLEDGE:" in clean_content:
            try:
                k_part = clean_content.split("KNOWLEDGE:")[1].strip().split("\n")[0]
                knowledge_update = json.loads(k_part)
                # Это будет обработано в базовом классе (нужна связь)
                logger.debug(f"🧠 Найдено обновление знаний: {knowledge_update}")
            except:
                pass

        # Пробуем распарсить как JSON
        try:
            start_idx = clean_content.find("{")
            end_idx = clean_content.rfind("}")

            if start_idx != -1 and end_idx != -1:
                json_str = clean_content[start_idx : end_idx + 1]

                # Пытаемся распарсить как стандартный JSON
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Если модель выдала одинарные кавычки (Python style), пробуем исправить
                    import ast

                    try:
                        data = ast.literal_eval(json_str)
                    except:
                        # Если совсем всё плохо - возвращаем как текст для разбора Агентом
                        return AgentFinish(
                            output=f"Error parsing JSON: {json_str[:100]}...",
                            thought="Parsing failure",
                        )

                # Если это наш формат
                if "tool" in data and "tool_input" in data:
                    if data["tool"] == "finish":
                        return AgentFinish(
                            output=data["tool_input"].get("output", "Готово"),
                            thought=data.get("thought", "Задача завершена"),
                        )
                    return AgentAction(
                        tool=data["tool"],
                        tool_input=data["tool_input"],
                        thought=data.get("thought", "Выполняю действие"),
                    )

                # Ищем инструмент во вложенных полях (action, next_step, step)
                if "thought" in data:
                    for key in ["action", "next_step", "step"]:
                        if key in data and isinstance(data[key], dict):
                            nested = data[key]
                            if "tool" in nested and "tool_input" in nested:
                                return AgentAction(
                                    tool=nested["tool"],
                                    tool_input=nested["tool_input"],
                                    thought=data["thought"],
                                )
                            if "command" in nested:
                                host = nested.get("host", "185.177.216.15")
                                return AgentAction(
                                    tool="ssh_run",
                                    tool_input={"host": host, "command": nested["command"]},
                                    thought=data["thought"],
                                )

                # Исправляем галлюцинации формата (если есть command вместо tool)
                if "command" in data:
                    host = data.get("host", "185.177.216.15")
                    return AgentAction(
                        tool="ssh_run",
                        tool_input={"host": host, "command": data["command"]},
                        thought=data.get("thought", "Авто-исправление команды"),
                    )

                # Если это любой другой JSON
                msg = data.get("response") or data.get("message") or data.get("output") or str(data)
                return AgentFinish(output=msg, thought="JSON ответ")

        except Exception as e:
            return AgentFinish(
                output=f"Internal Parser Error: {str(e)}", thought="Critical failure"
            )

        # Если не JSON или парсинг не удался - возвращаем как есть
        return AgentFinish(output=clean_content, thought="Текстовый ответ")
