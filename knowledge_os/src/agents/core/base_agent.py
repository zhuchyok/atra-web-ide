import asyncio
import logging
import json
from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

# Настройка логирования для терминала
logger = logging.getLogger(__name__)

class AgentAction(BaseModel):
    """Структура действия агента"""
    tool: str
    tool_input: Dict[str, Any]
    thought: str

class AgentFinish(BaseModel):
    """Структура завершения работы агента"""
    output: Any  # Изменено на Any для гибкости
    thought: str

class AtraBaseAgent(ABC):
    """
    Базовый класс для всех автономных агентов ATRA.
    """
    
    def __init__(self, name: str, model_name: str = None):
        self.name = name
        # Автовыбор модели: None = сканирование Ollama при первом запросе
        self.model_name = model_name or "auto"
        self.memory: List[Dict[str, str]] = []
        self.tools: Dict[str, Any] = {}
        # История выполненных команд для предотвращения циклов
        self.executed_commands_hash: List[str] = []
        # Долгосрочные знания о проекте, которые не стираются между run()
        self.project_knowledge: Dict[str, Any] = {
            "files_found": [],
            "server_status": {},
            "last_errors": [],
            "database_schema": {}
        }
        
    def add_tool(self, name: str, func: Any):
        self.tools[name] = func

    @abstractmethod
    async def plan(self, goal: str) -> List[str]:
        pass

    @abstractmethod
    async def step(self, prompt: str) -> Union[AgentAction, AgentFinish, Dict[str, Any]]:
        pass

    def _get_context_summary(self) -> str:
        """Формирует краткую сводку накопленных знаний для промпта"""
        summary = "\n--- НАКОПЛЕННЫЕ ЗНАНИЯ (Project Knowledge) ---\n"
        if self.project_knowledge["files_found"]:
            summary += f"Файлы: {', '.join(self.project_knowledge['files_found'][:10])}\n"
        if self.project_knowledge["database_schema"]:
            summary += f"Схема БД: {json.dumps(self.project_knowledge['database_schema'])}\n"
        if self.project_knowledge["server_status"]:
            summary += f"Серверы: {json.dumps(self.project_knowledge['server_status'])}\n"
        return summary

    async def run(self, goal: str, max_steps: int = 500) -> str:
        logger.info(f"\n🚀 ЗАДАЧА: {goal}")
        
        # Мы не стираем память полностью, а добавляем контекст знаний
        knowledge_context = self._get_context_summary()
        self.memory = [{"role": "system", "content": f"Ты уже знаешь следующее о проекте: {knowledge_context}"}]
        
        current_input = goal
        steps_taken = 0
        
        while steps_taken < max_steps:
            steps_taken += 1
            logger.info(f"\n--- ШАГ {steps_taken} ---")
            
            result = await self.step(current_input)
            
            # Если возникла ошибка в step (не JSON и т.д.)
            if isinstance(result, dict) and "error" in result:
                logger.error(f"❌ Ошибка шага: {result['error']}")
                return f"Сбой агента: {result['error']}"

            # Сохраняем ответ в память
            if isinstance(result, (AgentAction, AgentFinish)):
                content_to_save = {
                    "thought": result.thought,
                    "tool": getattr(result, 'tool', 'finish'),
                    "tool_input": getattr(result, 'tool_input', {})
                }
                self.memory.append({"role": "assistant", "content": json.dumps(content_to_save, ensure_ascii=False)})
                
                print(f"🤔 Мысль: {result.thought}")

            # Финал
            if isinstance(result, AgentFinish):
                logger.info(f"✅ Готово!")
                return str(result.output)
            
            # Действие
            if isinstance(result, AgentAction):
                # Генерируем хэш команды для проверки на циклы
                cmd_hash = f"{result.tool}:{json.dumps(result.tool_input, sort_keys=True)}"
                if self.executed_commands_hash.count(cmd_hash) >= 2:
                    error_msg = f"ОСТАНОВКА: Ты повторяешь команду {result.tool} уже 3-й раз с теми же аргументами. СМЕНИ СТРАТЕГИЮ! Проверь правильность имен таблиц и файлов."
                    logger.warning(f"⚠️ {error_msg}")
                    self.memory.append({"role": "user", "content": error_msg})
                    current_input = error_msg
                    self.executed_commands_hash.append(cmd_hash) # Фиксируем для истории
                    continue
                
                self.executed_commands_hash.append(cmd_hash)
                print(f"🛠  Инструмент: {result.tool}")
                print(f"📝 Аргументы: {json.dumps(result.tool_input, indent=2, ensure_ascii=False)}")
                
                if result.tool in self.tools:
                    try:
                        observation = await self.tools[result.tool](**result.tool_input)
                        obs_str = str(observation)
                        print(f"👀 Результат: {obs_str[:300]}..." if len(obs_str) > 300 else f"👀 Результат: {obs_str}")
                        
                        self.memory.append({"role": "user", "content": f"Observation from {result.tool}: {observation}"})
                        current_input = "Результат получен. Продолжай выполнение задачи."
                    except Exception as e:
                        error_msg = f"Ошибка при вызове {result.tool}: {str(e)}"
                        logger.error(f"❌ {error_msg}")
                        self.memory.append({"role": "user", "content": error_msg})
                        current_input = f"Произошла ошибка: {error_msg}. Попробуй другой способ."
                else:
                    error_msg = f"Инструмент {result.tool} не найден."
                    logger.error(f"❌ {error_msg}")
                    self.memory.append({"role": "user", "content": error_msg})
                    current_input = f"Ошибка: инструмента {result.tool} не существует. Используй только доступные инструменты."
            
        return f"Превышен лимит шагов ({max_steps})."
