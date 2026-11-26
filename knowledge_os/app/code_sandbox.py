import asyncio
import json
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    image: str = "python:3.11-slim"
    timeout_seconds: int = 30
    memory_limit_mb: int = 256
    network_enabled: bool = False
    allowed_modules: List[str] = field(
        default_factory=lambda: ["json", "math", "re", "collections", "itertools", "typing"]
    )


@dataclass
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    error: Optional[str] = None


class CodeSandbox:
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()

    @staticmethod
    def check_docker_available() -> bool:
        import subprocess

        try:
            result = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    async def run(self, code: str, input_data: Optional[dict] = None) -> SandboxResult:
        tmpdir = None
        start_time = time.perf_counter()
        try:
            tmpdir = tempfile.mkdtemp(prefix="code_sandbox_")
            tmp_path = Path(tmpdir)

            script_path = tmp_path / "sandbox_script.py"
            script_path.write_text(code, encoding="utf-8")

            if input_data:
                input_path = tmp_path / "sandbox_input.json"
                input_path.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")

            volume_bind = f"{tmpdir}:/sandbox"
            network_arg = (
                "--network=none" if not self.config.network_enabled else "--network=bridge"
            )
            memory_arg = f"-m{self.config.memory_limit_mb}m"
            timeout_arg = f"--timeout={self.config.timeout_seconds}"

            cmd = [
                "docker",
                "run",
                "--rm",
                network_arg,
                memory_arg,
                timeout_arg,
                "--read-only",
                "-v",
                volume_bind,
                "-w",
                "/sandbox",
                self.config.image,
                "python",
                "/sandbox/sandbox_script.py",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.config.timeout_seconds + 10
                )
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
                elapsed = (time.perf_counter() - start_time) * 1000
                return SandboxResult(
                    success=False,
                    stdout="",
                    stderr="",
                    exit_code=-1,
                    execution_time_ms=elapsed,
                    error=f"Execution timed out after {self.config.timeout_seconds}s",
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            exit_code = process.returncode or 0
            elapsed = (time.perf_counter() - start_time) * 1000

            return SandboxResult(
                success=exit_code == 0,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time_ms=elapsed,
                error=None if exit_code == 0 else stderr or f"Exit code: {exit_code}",
            )

        except FileNotFoundError:
            elapsed = (time.perf_counter() - start_time) * 1000
            return SandboxResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                execution_time_ms=elapsed,
                error="Docker is not available. Install Docker to run code in sandbox.",
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000
            return SandboxResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                execution_time_ms=elapsed,
                error=str(exc),
            )
        finally:
            if tmpdir:
                try:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Failed to clean up sandbox temp dir {tmpdir}: {e}")

    async def run_with_file_check(
        self, code: str, expected_files: List[str], input_data: Optional[dict] = None
    ) -> Tuple[SandboxResult, Dict[str, str]]:
        tmpdir = None
        start_time = time.perf_counter()
        try:
            tmpdir = tempfile.mkdtemp(prefix="code_sandbox_")
            tmp_path = Path(tmpdir)

            script_path = tmp_path / "sandbox_script.py"
            script_path.write_text(code, encoding="utf-8")

            if input_data:
                input_path = tmp_path / "sandbox_input.json"
                input_path.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")

            volume_bind = f"{tmpdir}:/sandbox"
            network_arg = (
                "--network=none" if not self.config.network_enabled else "--network=bridge"
            )
            memory_arg = f"-m{self.config.memory_limit_mb}m"
            timeout_arg = f"--timeout={self.config.timeout_seconds}"

            cmd = [
                "docker",
                "run",
                "--rm",
                network_arg,
                memory_arg,
                timeout_arg,
                "--read-only",
                "-v",
                volume_bind,
                "-w",
                "/sandbox",
                self.config.image,
                "python",
                "/sandbox/sandbox_script.py",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.config.timeout_seconds + 10
                )
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
                elapsed = (time.perf_counter() - start_time) * 1000
                return (
                    SandboxResult(
                        success=False,
                        stdout="",
                        stderr="",
                        exit_code=-1,
                        execution_time_ms=elapsed,
                        error=f"Execution timed out after {self.config.timeout_seconds}s",
                    ),
                    {},
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            exit_code = process.returncode or 0
            elapsed = (time.perf_counter() - start_time) * 1000

            result = SandboxResult(
                success=exit_code == 0,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time_ms=elapsed,
                error=None if exit_code == 0 else stderr or f"Exit code: {exit_code}",
            )

            file_contents: Dict[str, str] = {}
            for fname in expected_files:
                fpath = tmp_path / fname
                if fpath.exists():
                    file_contents[fname] = fpath.read_text(encoding="utf-8")

            return (result, file_contents)

        except FileNotFoundError:
            elapsed = (time.perf_counter() - start_time) * 1000
            return (
                SandboxResult(
                    success=False,
                    stdout="",
                    stderr="",
                    exit_code=-1,
                    execution_time_ms=elapsed,
                    error="Docker is not available. Install Docker to run code in sandbox.",
                ),
                {},
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000
            return (
                SandboxResult(
                    success=False,
                    stdout="",
                    stderr="",
                    exit_code=-1,
                    execution_time_ms=elapsed,
                    error=str(exc),
                ),
                {},
            )
        finally:
            if tmpdir:
                try:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Failed to clean up sandbox temp dir {tmpdir}: {e}")


_sandbox_instance: Optional[CodeSandbox] = None


def get_code_sandbox() -> CodeSandbox:
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = CodeSandbox()
    return _sandbox_instance


CODE_BLOCK_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def extract_python_code_blocks(text: str) -> List[str]:
    return CODE_BLOCK_RE.findall(text)


async def run_code_in_sandbox_and_append_results(report_text: str) -> str:
    sandbox = get_code_sandbox()
    code_blocks = extract_python_code_blocks(report_text)
    if not code_blocks:
        return report_text

    def _build_comment(block_idx: int, result: SandboxResult) -> str:
        lines = [
            f"\n<!-- sandbox-result block={block_idx} success={'true' if result.success else 'false'} -->\n",
            f"# Sandbox execution result (block {block_idx}):\n",
        ]
        if result.error:
            lines.append(f"# Error: {result.error}\n")
        if result.stdout:
            lines.append("# stdout:\n")
            for line in result.stdout.splitlines():
                lines.append(f"# | {line}\n")
        if result.stderr:
            lines.append("# stderr:\n")
            for line in result.stderr.splitlines():
                lines.append(f"# | {line}\n")
        lines.append(f"# exit code: {result.exit_code} | time: {result.execution_time_ms:.1f}ms\n")
        return "".join(lines)

    parts = []
    last_end = 0
    for block_idx, match in enumerate(CODE_BLOCK_RE.finditer(report_text)):
        code = match.group(1).strip()
        if not code:
            continue

        parts.append(report_text[last_end : match.end()])
        last_end = match.end()

        result = await sandbox.run(code)
        parts.append(_build_comment(block_idx, result))

    parts.append(report_text[last_end:])
    return "".join(parts)
