"""
Terminal Router - PTY для терминала в Web IDE.
Команда v "задача" — запрос к Victoria Agent.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
from typing import Optional
import logging
import os
import subprocess
import uuid
import os
import sys
import asyncio

logger = logging.getLogger(__name__)

# PTY доступен только на Unix системах
try:
    import pty
    import select
    import termios
    import struct
    import fcntl
    PTY_AVAILABLE = True
except ImportError:
    PTY_AVAILABLE = False
    logger.warning("PTY not available on this system (Windows?)")
router = APIRouter()


def _start_pty_sync(session: "TerminalSession") -> bool:
    """Синхронный запуск PTY (вызывается из run_in_executor, чтобы не блокировать event loop)."""
    if not PTY_AVAILABLE:
        return False
    try:
        pid, fd = pty.fork()
        if pid == 0:
            shell = os.environ.get('SHELL') or '/bin/sh'
            if not os.path.exists(shell):
                shell = '/bin/sh'
            os.execv(shell, [shell])
        # Родительский процесс
        session.pid = pid
        session.fd = fd
        old_settings = termios.tcgetattr(fd)
        new_settings = termios.tcgetattr(fd)
        new_settings[0] = 0
        new_settings[1] = 0
        new_settings[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        new_settings[3] = termios.ICANON | termios.ECHO | termios.ECHOE | termios.ISIG
        new_settings[6][termios.VMIN] = 0
        new_settings[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, new_settings)
        size = struct.pack('HHHH', 24, 80, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
        return True
    except Exception as e:
        logger.error(f"Failed to start PTY: {e}", exc_info=True)
        return False


class TerminalSession:
    """Сессия терминала с PTY"""
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.pid = None
        self.fd = None
    
    async def start(self):
        """Запустить PTY (не блокирует event loop)."""
        if not PTY_AVAILABLE:
            logger.error("PTY not available on this system")
            return False
        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(None, lambda: _start_pty_sync(self))
        if ok:
            logger.info(f"PTY started: pid={self.pid}, fd={self.fd}")
        return ok
    
    def resize(self, cols: int, rows: int):
        """Изменить размер терминала"""
        if self.fd and PTY_AVAILABLE:
            try:
                size = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, size)
            except Exception as e:
                logger.warning(f"Failed to resize terminal: {e}")
    
    async def read_output(self):
        """Читать вывод из PTY"""
        if not self.fd or not PTY_AVAILABLE:
            return
        
        try:
            # Неблокирующее чтение
            if select.select([self.fd], [], [], 0.1)[0]:
                data = os.read(self.fd, 1024)
                if data:
                    await self.websocket.send_text(data.decode('utf-8', errors='replace'))
        except Exception as e:
            logger.error(f"Read error: {e}")
    
    async def write_input(self, data: str):
        """Записать ввод в PTY"""
        if self.fd and PTY_AVAILABLE:
            try:
                os.write(self.fd, data.encode('utf-8'))
            except Exception as e:
                logger.error(f"Write error: {e}")
    
    def close(self):
        """Закрыть PTY"""
        if self.pid:
            try:
                os.kill(self.pid, 15)  # SIGTERM
                os.waitpid(self.pid, 0)
            except:
                pass
        if self.fd:
            try:
                os.close(self.fd)
            except:
                pass


@router.websocket("/pty")
async def terminal_pty(websocket: WebSocket):
    """
    WebSocket для PTY терминала
    
    Клиент отправляет:
    - Текст: ввод команды
    - JSON: {"type": "resize", "cols": 80, "rows": 24}
    
    Сервер отправляет:
    - Текст: вывод команды
    """
    await websocket.accept()
    
    if not PTY_AVAILABLE:
        await websocket.send_text("⚠️ PTY не доступен на этой системе\r\n")
        await websocket.close(code=1008, reason="PTY not available")
        return
    
    session = TerminalSession(websocket)
    
    if not await session.start():
        await websocket.close(code=1008, reason="Failed to start PTY")
        return
    
    try:
        # Запускаем цикл чтения вывода
        import asyncio
        
        async def read_loop():
            while True:
                await session.read_output()
                await asyncio.sleep(0.05)  # 20 FPS
        
        read_task = asyncio.create_task(read_loop())
        
        # Обрабатываем ввод от клиента
        while True:
            try:
                data = await websocket.receive()
                
                if "text" in data:
                    # Текстовый ввод
                    text = data["text"]
                    await session.write_input(text)
                
                elif "bytes" in data:
                    # Бинарные данные (для resize)
                    pass
                
                elif "json" in data:
                    # JSON команды (resize)
                    json_data = data["json"]
                    if json_data.get("type") == "resize":
                        cols = json_data.get("cols", 80)
                        rows = json_data.get("rows", 24)
                        session.resize(cols, rows)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
                break
        
        read_task.cancel()
        session.close()
        
    except Exception as e:
        logger.error(f"Terminal session error: {e}", exc_info=True)
        session.close()
        await websocket.close(code=1011, reason="Internal error")


# --- Victoria Ask (команда v "задача" из терминала) ---
class TerminalAskRequest(BaseModel):
    """Запрос к Victoria из терминала"""
    command: str = ""  # "v задача" или просто "задача"


@router.post("/ask")
async def terminal_ask(req: TerminalAskRequest):
    """
    Выполнить задачу через Victoria Agent.
    Вызывается при вводе в терминале: v "создай файл test.py" или v список файлов
    """
    goal = (req.command or "").strip()
    if goal.lower().startswith("v "):
        goal = goal[2:].strip().strip("'\"").strip()
    if not goal:
        return {"response": "Укажите задачу: v \"ваша задача\"", "error": "empty_goal"}

    try:
        from app.services.victoria import get_victoria_client
        victoria = await get_victoria_client()
        project_context = os.getenv("PROJECT_NAME", "atra-web-ide")
        correlation_id = str(uuid.uuid4())
        result = await victoria.run(
            prompt=goal,
            project_context=project_context,
            correlation_id=correlation_id,
        )
        output = result.get("response") or result.get("result") or result.get("error") or "Нет ответа"
        if isinstance(output, dict):
            output = str(output)
        return {"response": output, "status": result.get("status", "success")}
    except Exception as e:
        logger.exception("Terminal ask Victoria: %s", e)
        return {"response": f"Ошибка: {e}", "error": str(e), "status": "error"}
