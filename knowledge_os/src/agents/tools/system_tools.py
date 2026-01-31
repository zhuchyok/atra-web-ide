import subprocess
import logging
import os
import shlex
from typing import Optional

logger = logging.getLogger(__name__)

# Попытка загрузить переменные окружения для серверов
SERVER_CREDENTIALS = {
    "185.177.216.15": {
        "user": os.getenv("SERVER_TRADING_USER", "root"),
        "pass": os.getenv("SERVER_TRADING_PASS", "u44Ww9NmtQj,XG")
    },
    "46.149.66.170": {
        "user": os.getenv("SERVER_AGENTS_USER", "root"),
        "pass": os.getenv("SERVER_AGENTS_PASS", "tT@B43Td21w?NB")
    }
}

class SystemTools:
    """Инструменты для взаимодействия с операционной системой и серверами"""

    @staticmethod
    async def run_local_command(command: str) -> str:
        """Выполнение команды в локальном терминале"""
        try:
            if not command:
                return "Error: Empty command"
            
            # Безопасный запуск команды
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30,
                check=False
            )
            return f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out (30s)"
        except Exception as e:
            return f"Exception: {str(e)}"

    @staticmethod
    async def run_ssh_command(host: str, command: str, user: Optional[str] = None, password: Optional[str] = None) -> str:
        """
        Выполнение команды на удаленном сервере через SSH с защитой от инъекций.
        """
        # Автоматическая подстановка если хост наш
        if host in SERVER_CREDENTIALS:
            user = SERVER_CREDENTIALS[host]["user"]
            password = SERVER_CREDENTIALS[host]["pass"]
        
        if not user or not password:
            return "Error: Authentication credentials missing."

        logger.info("🌐 SSH: %s@%s -> %s", user, host, command[:50] + "..." if len(command) > 50 else command)
        
        # Экранирование для shell внутри SSH
        # shlex.quote хорошо работает для аргументов, но нам нужно экранировать всё для expect
        safe_command = command.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
        
        expect_script = f"""
        set timeout 60
        spawn ssh -q -o StrictHostKeyChecking=no -o ConnectTimeout=10 {user}@{host} "{safe_command}"
        expect {{
            "password:" {{ 
                send "{password}\\r"
                exp_continue
            }}
            eof
        }}
        """
        
        try:
            result = subprocess.run(
                ['expect', '-c', expect_script], 
                capture_output=True, 
                text=True, 
                timeout=70,
                check=False
            )
            
            output = result.stdout
            lines = output.splitlines()
            
            # Находим реальное начало вывода (после пароля)
            result_lines = []
            capture = False
            for line in lines:
                if capture:
                    result_lines.append(line)
                if "password:" in line.lower() or f"{user}@{host}" in line:
                    capture = True
            
            # Если захвата не произошло, берем всё без строк с паролем
            if not result_lines:
                result_lines = [l for l in lines if "password:" not in l.lower()]
                
            final_output = "\n".join(result_lines).strip()
            
            if result.returncode != 0 and not final_output:
                return f"SSH System Error: {result.stderr.strip()}"
                
            return final_output if final_output else "Command executed successfully (no output)."
            
        except subprocess.TimeoutExpired:
            return "Error: SSH Command timed out (70s)"
        except Exception as e:
            return f"SSH Exception: {str(e)}"

    @staticmethod
    async def read_project_file(file_path: str) -> str:
        """Чтение файла из проекта"""
        try:
            if not os.path.exists(file_path):
                return f"Error: File '{file_path}' not found."
            with open(file_path, 'r') as f:
                return f.read()
        except Exception as e:
            return f"File Error: {str(e)}"

    @staticmethod
    async def list_directory(path: str = ".") -> str:
        """Список файлов в директории"""
        try:
            files = os.listdir(path)
            return "\n".join(files)
        except Exception as e:
            return f"List Directory Error: {str(e)}"

    @staticmethod
    async def grep_search(pattern: str, path: str = ".") -> str:
        """Поиск строки по всему проекту (аналог ripgrep)"""
        try:
            # Используем системный grep для скорости
            cmd = f"grep -rnE {shlex.quote(pattern)} {shlex.quote(path)} --exclude-dir=venv --exclude-dir=.git | head -n 20"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout if result.stdout else "No matches found."
        except Exception as e:
            return f"Grep Error: {str(e)}"

    @staticmethod
    async def apply_patch(file_path: str, old_text: str, new_text: str) -> str:
        """Точечная замена текста в файле (безопасное редактирование)"""
        try:
            if not os.path.exists(file_path):
                return f"Error: File '{file_path}' not found."
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            if old_text not in content:
                return "Error: Old text not found in file. Patch failed."
            
            new_content = content.replace(old_text, new_text)
            with open(file_path, 'w') as f:
                f.write(new_content)
            
            return f"Successfully patched {file_path}."
        except Exception as e:
            return f"Patch Error: {str(e)}"

class WebTools:
    """Инструменты для работы с интернетом"""
    
    @staticmethod
    async def web_search(query: str) -> str:
        """Поиск актуальной информации в интернете"""
        try:
            from duckduckgo_search import DDGS
            logger.info(f"🔍 Searching the web for: {query}")
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(query, max_results=5)]
                if not results:
                    return "No results found."
                
                formatted_results = []
                for r in results:
                    formatted_results.append(f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}\n")
                
                return "\n---\n".join(formatted_results)
        except ImportError:
            return "Error: 'duckduckgo-search' library not found. Please run 'pip install duckduckgo-search'."
        except Exception as e:
            return f"Web Search Error: {str(e)}"
