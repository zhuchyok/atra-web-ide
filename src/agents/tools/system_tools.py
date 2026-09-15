import logging
import os
import re
import shlex
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Попытка загрузить переменные окружения для серверов
SERVER_CREDENTIALS = {
    "185.177.216.15": {
        "user": os.getenv("SERVER_TRADING_USER", "root"),
        "pass": os.getenv("SERVER_TRADING_PASS", "u44Ww9NmtQj,XG"),
    },
    "46.149.66.170": {
        "user": os.getenv("SERVER_AGENTS_USER", "root"),
        "pass": os.getenv("SERVER_AGENTS_PASS", "tT@B43Td21w?NB"),
    },
}


class SystemTools:
    """Инструменты для взаимодействия с операционной системой и серверами"""

    @staticmethod
    def _resolve_workspace_path(path: Optional[str]) -> str:
        """
        Normalize user-provided paths between host and container workspaces.
        This prevents false "not found" when users provide host paths in Open WebUI.
        """
        requested = (path or ".").strip() or "."
        if requested.startswith("~/"):
            requested = os.path.expanduser(requested)

        if os.path.exists(requested):
            return requested

        host_workspace = os.getenv(
            "ATRA_HOST_WORKSPACE", "/Users/bikos/Documents/atra-web-ide"
        ).rstrip("/")
        container_workspace = os.getenv(
            "ATRA_CONTAINER_WORKSPACE", "/workspace/atra-web-ide"
        ).rstrip("/")

        # Bare relative paths (def write_file("foo.py")): resolve against
        # the mounted src/ dir so files land on the host, not in container root
        if not requested.startswith("/"):
            src_root = os.path.join(container_workspace, "src")
            if not os.path.isdir(src_root) and os.path.isdir("/app/src"):
                src_root = "/app/src"
            if os.path.isdir(src_root):
                return os.path.join(src_root, requested)

        if host_workspace and requested.startswith(host_workspace):
            suffix = requested[len(host_workspace) :].lstrip("/")
            mapped = os.path.join(container_workspace, suffix) if suffix else container_workspace
            if os.path.exists(mapped):
                return mapped

        return requested

    @staticmethod
    def _validate_command_safety(command: str) -> bool:
        """
        Проверка команды на безопасность перед выполнением.
        Запрещает деструктивные действия без явного подтверждения.
        """
        # --- ПРИОРИТЕТ СПЕЦИАЛИЗИРОВАННЫХ ИНСТРУМЕНТОВ (Claude Code Pattern) ---
        file_ops = [r"\bcat\b", r"\bsed\b", r"\bawk\b", r"\bfind\b", r"\bgrep\b", r"\becho\s+.*>"]
        for op in file_ops:
            if re.search(op, command, re.IGNORECASE):
                logger.info(
                    f"💡 Рекомендация: Используйте специализированные инструменты (read_file, apply_patch, grep_search) вместо Bash для: {command}"
                )
                # Мы не блокируем жестко, но логируем рекомендацию для обучения агентов

        dangerous_patterns = [
            r"rm\s+-rf\s+/",  # Удаление корня
            r"rm\s+-rf\s+\*",  # Удаление всего в папке
            r"rm\s+-rf\s+\.",  # Удаление текущей папки
            r"mkfs",  # Форматирование диска
            r"dd\s+if=/dev/zero",  # Затирание диска
            r"shutdown",  # Выключение
            r"reboot",  # Перезагрузка
            r"DROP\s+DATABASE",  # Удаление БД
            r"DROP\s+TABLE\s+(?!rejected_signals)",  # Удаление таблиц (кроме разрешенной)
            r"mv\s+/\s+",  # Перемещение корня
            r"> /dev/sda",  # Запись на диск напрямую
            r"\bchmod\s+777\b",  # Открытие прав на всё
            r"\bsudo\s+rm\b",  # sudo rm
            r"\bsudo\s+dd\b",  # sudo dd
            r"\bmkfs\.",  # Форматирование (mkfs.*)
            r">\s*/dev/",  # Запись в блочное устройство
            r"\|\s*rm\s+",  # pipe в rm
        ]
        # Дополнительно: блокировка команд в системных путях (если команда меняет /etc, /bin и т.д.)
        if re.search(
            r"(rm|mv|chmod|chown)\s+.*(/etc/|/bin/|/sbin/|/usr/bin/|/root/)", command, re.IGNORECASE
        ):
            logger.warning(f"🚨 ОБНАРУЖЕНА ОПАСНАЯ КОМАНДА (системный путь): {command}")
            return False

        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                logger.warning(f"🚨 ОБНАРУЖЕНА ОПАСНАЯ КОМАНДА: {command}")
                return False
        return True

    @staticmethod
    async def run_local_command(command: Optional[str] = None, cmd: Optional[str] = None) -> str:
        """Выполнение команды в локальном терминале. Принимает command или cmd (LLM может вернуть любое)."""
        c = (command if command is not None else cmd) or ""
        c = c.strip()
        if not SystemTools._validate_command_safety(c):
            return "Error: Command rejected by ATRA Safety Layer (Risk Manager: Maria). Reason: High destructive risk."

        try:
            if not c:
                return "Error: Empty command"

            # Безопасный запуск команды
            result = subprocess.run(
                c, shell=True, capture_output=True, text=True, timeout=30, check=False
            )
            return f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out (30s)"
        except Exception as e:
            return f"Exception: {str(e)}"

    @staticmethod
    async def write_file(file_path: str, content: str) -> str:
        """Создать/перезаписать файл. Путь реальный относительно корня проекта."""
        if not file_path or not content:
            return "Error: file_path and content are required"

        resolved_path = SystemTools._resolve_workspace_path(file_path)

        # Создаём директории если нужно
        dir_name = os.path.dirname(resolved_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        try:
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("📝 [WRITE_FILE] %s (%d chars)", resolved_path, len(content))
            return f"OK: File written: {resolved_path} ({len(content)} chars)"
        except Exception as e:
            return f"Error writing {resolved_path}: {str(e)}"

    @staticmethod
    async def run_ssh_command(
        host: str, command: str, user: Optional[str] = None, password: Optional[str] = None
    ) -> str:
        """
        Выполнение команды на удаленном сервере через SSH с защитой от инъекций.
        """
        if not SystemTools._validate_command_safety(command):
            return "Error: Command rejected by ATRA Safety Layer (Risk Manager: Maria). Reason: High destructive risk."

        # Автоматическая подстановка если хост наш
        if host in SERVER_CREDENTIALS:
            user = SERVER_CREDENTIALS[host]["user"]
            password = SERVER_CREDENTIALS[host]["pass"]

        if not user or not password:
            return "Error: Authentication credentials missing."

        logger.info(
            "🌐 SSH: %s@%s -> %s",
            user,
            host,
            command[:50] + "..." if len(command) > 50 else command,
        )

        # Экранирование для shell внутри SSH
        # shlex.quote хорошо работает для аргументов, но нам нужно экранировать всё для expect
        safe_command = command.replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")

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
                ["expect", "-c", expect_script],
                capture_output=True,
                text=True,
                timeout=70,
                check=False,
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
                result_lines = [line for line in lines if "password:" not in line.lower()]

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
            resolved_path = SystemTools._resolve_workspace_path(file_path)
            if not os.path.exists(resolved_path):
                return f"Error: File '{file_path}' not found (resolved='{resolved_path}')."
            with open(resolved_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"File Error: {str(e)}"

    @staticmethod
    async def list_directory(path: str = ".") -> str:
        """Список файлов в директории"""
        try:
            resolved_path = SystemTools._resolve_workspace_path(path)
            files = os.listdir(resolved_path)
            return "\n".join(files)
        except Exception as e:
            return f"List Directory Error: {str(e)}"

    @staticmethod
    async def grep_search(pattern: str, path: str = ".") -> str:
        """Поиск строки по всему проекту (аналог ripgrep)"""
        try:
            resolved_path = SystemTools._resolve_workspace_path(path)
            # Используем системный grep для скорости
            cmd = f"grep -rnE {shlex.quote(pattern)} {shlex.quote(resolved_path)} --exclude-dir=venv --exclude-dir=.git | head -n 20"
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30, check=False
            )
            return result.stdout if result.stdout else "No matches found."
        except Exception as e:
            return f"Grep Error: {str(e)}"

    @staticmethod
    async def apply_patch(file_path: str, old_text: str, new_text: str) -> str:
        """Точечная замена текста в файле (безопасное редактирование)"""
        try:
            resolved_path = SystemTools._resolve_workspace_path(file_path)
            if not os.path.exists(resolved_path):
                return f"Error: File '{file_path}' not found (resolved='{resolved_path}')."

            with open(resolved_path, encoding="utf-8") as f:
                content = f.read()

            if old_text not in content:
                return "Error: Old text not found in file. Patch failed."

            new_content = content.replace(old_text, new_text)
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Successfully patched {resolved_path}."
        except Exception as e:
            return f"Patch Error: {str(e)}"


class WebTools:
    """Инструменты для работы с интернетом"""

    @staticmethod
    async def _check_internet(timeout: float = 1.5) -> bool:
        """Быстрая проверка интернета: TCP до 1.1.1.1:53 (Cloudflare DNS)."""
        import asyncio as _asyncio

        try:
            _, writer = await _asyncio.wait_for(
                _asyncio.open_connection("1.1.1.1", 53),
                timeout=timeout,
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True
        except Exception:
            return False

    @staticmethod
    async def _searxng_search(query: str) -> str:
        """Поиск через локальный SearXNG (SEARXNG_URL из env)."""
        import httpx

        url = os.getenv("SEARXNG_URL", "http://searxng:8080")
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{url}/search",
                params={"q": query, "format": "json", "language": "ru"},
            )
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results", [])[:5]
        if not results:
            return ""
        parts = [
            f"Title: {r.get('title', '')}\nLink: {r.get('url', '')}\nSnippet: {r.get('content', '')}"
            for r in results
        ]
        return "\n---\n".join(parts)

    @staticmethod
    async def _duckduckgo_search(query: str) -> str:
        """Поиск через DuckDuckGo (публичный fallback)."""
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
        if not results:
            return ""
        parts = [f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}" for r in results]
        return "\n---\n".join(parts)

    @staticmethod
    async def web_search(query: str) -> str:
        """Поиск: SearXNG (локальный) → DuckDuckGo. При STRICT_LOCAL или нет интернета — локальная база."""
        strict_local = os.getenv("STRICT_LOCAL", "false").lower() in ("true", "1", "yes")
        if strict_local:
            logger.info("🔒 [STRICT_LOCAL] web_search заблокирован")
            return (
                "⚠️ Веб-поиск отключён (STRICT_LOCAL=true). "
                "Использую локальную базу знаний Victoria."
            )

        if not await WebTools._check_internet():
            logger.warning("🌐 [web_search] Интернет недоступен")
            return (
                "⚠️ Интернет недоступен. Использую локальную базу знаний Victoria. "
                "Проверьте подключение если нужен веб-поиск."
            )

        providers = [
            p.strip() for p in os.getenv("WEB_SEARCH_PROVIDERS", "searxng,duckduckgo").split(",")
        ]
        logger.info("🔍 Web search: %r | providers: %s", query, providers)

        for provider in providers:
            try:
                if provider == "searxng":
                    result = await WebTools._searxng_search(query)
                    if result:
                        return result
                elif provider == "duckduckgo":
                    result = await WebTools._duckduckgo_search(query)
                    if result:
                        return result
            except Exception as exc:
                logger.warning("⚠️ [web_search] provider=%s failed: %s", provider, exc)

        return "Поиск недоступен: все провайдеры не ответили. Использую локальную базу знаний."

    @staticmethod
    async def browser_action(goal: str) -> str:
        """
        Автономное управление браузером для проверки UI/UX и выполнения действий.
        """
        try:
            # Пытаемся импортировать из knowledge_os/app
            try:
                from app.browser_operator import get_browser_operator
            except ImportError:
                try:
                    from knowledge_os.app.browser_operator import get_browser_operator
                except ImportError:
                    # Если мы в контейнере, путь может быть другим
                    import sys as _sys

                    _sys.path.append("/app/knowledge_os/app")
                    from browser_operator import get_browser_operator

            operator = get_browser_operator()
            logger.info(f"🤖 [BROWSER ACTION] Starting: {goal}")
            result = await operator.execute_task(goal)

            if result["status"] == "success":
                output = f"✅ Browser Task Success!\nOutput: {result['output']}"
                if result.get("screenshot"):
                    output += f"\n[Screenshot Captured: {len(result['screenshot'])} bytes]"
                return output
            else:
                return f"❌ Browser Task Failed: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Browser Error: {str(e)}"


class DataTools:
    """Read-only инструменты данных: SQL и Git. Безопасность по умолчанию."""

    _SQL_WRITE_PATTERNS = re.compile(
        r"\b(insert|update|delete|drop|alter|truncate|vacuum|reindex|copy|create)\b",
        re.IGNORECASE,
    )

    @staticmethod
    def _validate_readonly_sql(sql: str) -> Optional[str]:
        q = (sql or "").strip()
        first = q.split()[0].lower() if q.split() else ""
        if first not in ("select", "with", "explain", "show", "table"):
            return f"❌ db_query: только SELECT/WITH/EXPLAIN. Запрещено: {sql[:80]}"
        if DataTools._SQL_WRITE_PATTERNS.search(q.replace("--", "").replace("/*", "")):
            return f"❌ db_query: DDL/DML запрещены в чтении. Запрос: {sql[:80]}"
        for kw in ("pg_sleep", "pg_read_file", "lo_import", "dblink"):
            if kw in q.lower():
                return f"❌ db_query: функция {kw} запрещена"
        return None

    @staticmethod
    async def db_query(sql: str = "", query: str = "") -> str:
        """Read-only SQL к knowledge_os (DATABASE_URL). Только SELECT/WITH/EXPLAIN."""
        import asyncpg

        q = (sql or query or "").strip()
        if not q:
            return "Ошибка: пустой SQL"
        err = DataTools._validate_readonly_sql(q)
        if err:
            return err
        dsn = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DIRECT_URL")
        if not dsn:
            return "Ошибка: DATABASE_URL не задан"
        try:
            conn = await asyncpg.connect(dsn, timeout=8)
            try:
                rows = await asyncio_wait_or(conn.fetch(q), timeout=10)
            finally:
                await conn.close()
            if not rows:
                return "OK: 0 строк"
            if not isinstance(rows, list):
                return str(rows)[:MAX_DB_CHARS]
            cols = list(rows[0].keys()) if rows else []
            head = " | ".join(cols)
            lines = [head, "-" * min(len(head), 120)]
            for r in rows[
                : int(os.getenv("DB_QUERY_MAX_ROWS", "25"))
            ]:
                lines.append(
                    " | ".join(
                        (str(r[c])[:60]).replace("\n", " ")[:MAX_CELL_CHARS] for c in cols
                    )
                )
            text = "\n".join(lines)
            suffix = "" if len(rows) <= int(os.getenv("DB_QUERY_MAX_ROWS", "25")) else "\n… (обрезано)"
            return text[:MAX_DB_CHARS] + suffix
        except Exception as e:
            return f"db_query error: {str(e)[:200]}"


class GitTools:
    """Базовые read-only git-инструменты (только чтение истории/статуса)."""

    @staticmethod
    def _resolve_repo() -> str:
        return os.getenv("WORKSPACE_ROOT") or os.getenv("PROJECT_ROOT") or os.getcwd()

    @staticmethod
    async def git_status() -> str:
        result = subprocess.run(
            ["git", "-C", GitTools._resolve_repo(), "status", "--short"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = (result.stdout or result.stderr or "").strip()
        return out[:MAX_DB_CHARS] or "(чисто)"

    @staticmethod
    async def git_diff(file_path: str = "") -> str:
        cmd = ["git", "-C", GitTools._resolve_repo(), "diff", "--stat"]
        if file_path:
            cmd.append(file_path)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        out = (result.stdout or result.stderr or "").strip()
        return out[:MAX_DB_CHARS] or "(нет изменений)"

    @staticmethod
    async def git_log(count: int = 10) -> str:
        n = max(1, min(int(count or 10), 50))
        result = subprocess.run(
            ["git", "-C", GitTools._resolve_repo(), "log", "--oneline", f"-{n}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = (result.stdout or result.stderr or "").strip()
        return out[:MAX_DB_CHARS]

    # ── [v3 Гит-агент, write] безопасные мутации через subprocess ──
    GIT_MAX_CHARS = int(os.getenv("GIT_TOOL_MAX_CHARS", "4000"))

    _GIT_BLOCK_TOKENS = ("rm -rf", "--force", "reset --hard", "clean -fd", "> /dev/sda?", "push --force")

    @staticmethod
    def _git_run(args: list, timeout: int = 20):
        repo = GitTools._resolve_repo()
        proc = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode, out

    @staticmethod
    def _gh_run(args: list, timeout: int = 30):
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=timeout, env=env,
            cwd=GitTools._resolve_repo() or os.getcwd(),
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode, out

    @staticmethod
    def _safe_token(text: str) -> bool:
        return not any(tok in text for tok in GitTools._GIT_BLOCK_TOKENS)

    @staticmethod
    async def git_branch_create(name: str = "") -> str:
        if not GitTools._safe_token(name):
            return "Error: опасное имя ветки"
        code, out = GitTools._git_run(["checkout", "-b", name])
        return ("ok: " + out if code == 0 else f"Error: {out}")[:MAX_DB_CHARS]

    @staticmethod
    async def git_add(paths: str = "") -> str:
        # однострочный список через пробел; safeguard на ".." и /etc
        if any(part.startswith("/") or ".." in part for part in paths.split()):
            return "Error: только относительные пути репозитория"
        code, out = GitTools._git_run(["add", "-A" if not paths else paths])
        return ("ok: " + out if code == 0 else f"Error: {out}")[:MAX_DB_CHARS]

    @staticmethod
    async def git_commit(message: str = "") -> str:
        if not GitTools._safe_token(message):
            return "Error: сообщение содержит запрещённые токены"
        code, out = GitTools._git_run(["commit", "--no-verify", "-m", message[:300]])
        return ("ok: " + out if code == 0 else f"Error: {out}")[:MAX_DB_CHARS]

    @staticmethod
    async def git_push(remote: str = "origin", branch: str = "") -> str:
        for t in (remote, branch):
            if not GitTools._safe_token(t or "x"):
                return "Error: опасные токены"
        args = ["push", "--no-verify", remote]
        if branch:
            args.append(branch)
        code, out = GitTools._git_run(args, timeout=60)
        return ("ok: " + out if code == 0 else f"Error: {out}")[:MAX_DB_CHARS]

    @staticmethod
    async def git_pr_create(title: str = "", body: str = "") -> str:
        import shutil
        if shutil.which("gh") is None:
            return (
                "Note: gh CLI доступен только на хосте. Команда прерывания.\n"
                "Рекомендации агенту: вызвать run_terminal_cmd с host-bridge или push ветку через git_push и создать PR вручную."
            )
        if not GitTools._safe_token(title + body):
            return "Error: запрещённые токены"
        code, out = GitTools._gh_run(["pr", "create", "--fill", "--title", title[:200], "--body", body[:3000]], timeout=60)
        return ("ok: " + out if code == 0 else f"Error: {out}")[:MAX_DB_CHARS]

    @staticmethod
    async def git_pr_list() -> str:
        code, out = GitTools._gh_run(["pr", "list", "--limit", "10"])
        return (out if code == 0 else f"Error: {out}")[:MAX_DB_CHARS]

    @staticmethod
    async def git_test_run(path: str = "") -> str:
        cmd = ["python3", "-m", "pytest", "-q"] if not path else ["python3", path]
        proc = subprocess.run(cmd, cwd=GitTools._resolve_repo(), capture_output=True, text=True, timeout=120)
        return ((proc.stdout or "") + (proc.stderr or ""))[:MAX_DB_CHARS]


MAX_DB_CHARS = int(os.getenv("DATA_TOOL_MAX_CHARS", "4000"))
MAX_CELL_CHARS = int(os.getenv("DATA_TOOL_MAX_CELL_CHARS", "60"))


async def asyncio_wait_or(coro, timeout: float = 10.0):
    import asyncio

    return await asyncio.wait_for(coro, timeout=timeout)
