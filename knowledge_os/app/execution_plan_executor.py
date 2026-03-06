"""
Executor для выполнения execution_plan от Victoria.
Преобразует шаги плана в вызовы MCP tools (filesystem server).
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ExecutionPlanExecutor:
    """
    Выполняет execution_plan от Victoria через MCP tools.
    
    Использует user-filesystem MCP server для:
    - read_file: чтение файлов
    - write_file: запись/правка файлов  
    - execute_command: выполнение команд в терминале
    """
    
    def __init__(self, mcp_client):
        """
        Args:
            mcp_client: клиент для вызова MCP tools (например, из CallMcpTool)
        """
        self.mcp_client = mcp_client
        
    async def execute_plan(self, plan: List[Dict[str, Any]], workspace_path: str) -> List[Dict[str, Any]]:
        """
        Выполняет execution_plan последовательно.
        
        Args:
            plan: список шагов [{"action": "read_file", "path": "...", ...}, ...]
            workspace_path: путь к workspace (для относительных путей)
            
        Returns:
            Список результатов [{"step": 1, "action": "read_file", "status": "success", "result": "..."}, ...]
        """
        results = []
        
        for i, step in enumerate(plan, 1):
            action = step.get("action")
            description = step.get("description", "")
            
            logger.info(f"[EXECUTION_PLAN] Шаг {i}/{len(plan)}: {action} - {description}")
            
            try:
                if action == "read_file":
                    result = await self._execute_read_file(step, workspace_path)
                elif action == "edit":
                    result = await self._execute_edit(step, workspace_path)
                elif action == "run":
                    result = await self._execute_run(step, workspace_path)
                else:
                    result = {"status": "error", "message": f"Неизвестное действие: {action}"}
                    
                results.append({
                    "step": i,
                    "action": action,
                    "description": description,
                    **result
                })
                
                # Если шаг failed и критичный — остановить выполнение
                if result.get("status") == "error" and step.get("critical", False):
                    logger.error(f"[EXECUTION_PLAN] Критический шаг {i} провалился, останавливаем выполнение")
                    break
                    
            except Exception as e:
                logger.exception(f"[EXECUTION_PLAN] Ошибка на шаге {i}")
                results.append({
                    "step": i,
                    "action": action,
                    "description": description,
                    "status": "error",
                    "message": str(e)
                })
                
                if step.get("critical", False):
                    break
                    
        return results
        
    async def _execute_read_file(self, step: Dict[str, Any], workspace_path: str) -> Dict[str, Any]:
        """Читает файл через MCP filesystem server"""
        path = step.get("path")
        if not path:
            return {"status": "error", "message": "Не указан path"}
            
        # Если путь относительный, добавляем workspace_path
        if not path.startswith("/"):
            path = f"{workspace_path}/{path}"
            
        try:
            # Вызов MCP tool: user-filesystem/read_file
            result = await self.mcp_client.call_tool(
                server="user-filesystem",
                tool_name="read_file",
                arguments={"path": path}
            )
            
            return {
                "status": "success",
                "result": result.get("content", ""),
                "path": path
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Не удалось прочитать файл: {str(e)}",
                "path": path
            }
            
    async def _execute_edit(self, step: Dict[str, Any], workspace_path: str) -> Dict[str, Any]:
        """
        Редактирует файл через MCP filesystem server.
        Пока упрощённая версия — просто записывает новое содержимое.
        TODO: добавить поддержку diff/patch для точечных правок.
        """
        path = step.get("path")
        content = step.get("content")  # Новое содержимое файла
        
        if not path:
            return {"status": "error", "message": "Не указан path"}
            
        if not path.startswith("/"):
            path = f"{workspace_path}/{path}"
            
        try:
            # Вызов MCP tool: user-filesystem/write_file
            # ВАЖНО: это перезапишет файл полностью!
            result = await self.mcp_client.call_tool(
                server="user-filesystem",
                tool_name="write_file",
                arguments={"path": path, "content": content}
            )
            
            return {
                "status": "success",
                "message": "Файл изменён",
                "path": path
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Не удалось изменить файл: {str(e)}",
                "path": path
            }
            
    async def _execute_run(self, step: Dict[str, Any], workspace_path: str) -> Dict[str, Any]:
        """Выполняет команду через MCP filesystem server"""
        command = step.get("command")
        
        if not command:
            return {"status": "error", "message": "Не указана command"}
            
        try:
            # Вызов MCP tool: user-filesystem/execute_command
            result = await self.mcp_client.call_tool(
                server="user-filesystem",
                tool_name="execute_command",
                arguments={
                    "command": command,
                    "working_dir": workspace_path
                }
            )
            
            return {
                "status": "success",
                "result": result.get("output", ""),
                "exit_code": result.get("exit_code", 0),
                "command": command
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Не удалось выполнить команду: {str(e)}",
                "command": command
            }
