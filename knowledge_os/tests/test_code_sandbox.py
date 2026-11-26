import asyncio
import json
import re
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_os.app.code_sandbox import (
    CODE_BLOCK_RE,
    CodeSandbox,
    SandboxConfig,
    SandboxResult,
    extract_python_code_blocks,
    get_code_sandbox,
    run_code_in_sandbox_and_append_results,
)


class TestSandboxConfig:
    def test_default_config(self):
        config = SandboxConfig()
        assert config.image == "python:3.11-slim"
        assert config.timeout_seconds == 30
        assert config.memory_limit_mb == 256
        assert config.network_enabled is False
        assert "json" in config.allowed_modules
        assert "math" in config.allowed_modules

    def test_custom_config(self):
        config = SandboxConfig(image="python:3.12", timeout_seconds=60, memory_limit_mb=512, network_enabled=True)
        assert config.image == "python:3.12"
        assert config.timeout_seconds == 60
        assert config.memory_limit_mb == 512
        assert config.network_enabled is True


class TestSandboxResult:
    def test_success_result(self):
        result = SandboxResult(success=True, stdout="hello", stderr="", exit_code=0, execution_time_ms=10.5)
        assert result.success is True
        assert result.stdout == "hello"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.execution_time_ms == 10.5
        assert result.error is None

    def test_failure_result(self):
        result = SandboxResult(
            success=False, stdout="", stderr="Error!", exit_code=1, execution_time_ms=5.2, error="Error!"
        )
        assert result.success is False
        assert result.stderr == "Error!"
        assert result.exit_code == 1
        assert result.error == "Error!"


class TestExtractPythonCodeBlocks:
    def test_extracts_single_block(self):
        text = "Some text\n```python\nprint('hello')\n```\nmore text"
        blocks = extract_python_code_blocks(text)
        assert len(blocks) == 1
        assert "print('hello')" in blocks[0]

    def test_extracts_multiple_blocks(self):
        text = "```python\nprint(1)\n```\n...\n```python\nprint(2)\n```"
        blocks = extract_python_code_blocks(text)
        assert len(blocks) == 2

    def test_returns_empty_for_no_blocks(self):
        assert extract_python_code_blocks("just text") == []

    def test_handles_language_specific_markers(self):
        text = "```python\ndef foo():\n    return 42\n```"
        blocks = extract_python_code_blocks(text)
        assert len(blocks) == 1
        assert "def foo()" in blocks[0]

    def test_regex_matches_code_blocks(self):
        text = "```python\nx = 1\n```"
        matches = CODE_BLOCK_RE.findall(text)
        assert len(matches) == 1
        assert matches[0].strip() == "x = 1"


class TestCodeSandbox:
    @pytest.mark.asyncio
    async def test_run_creates_temp_dir_and_writes_code(self):
        sandbox = CodeSandbox()
        with patch.object(sandbox, "run", new=AsyncMock()) as mock_run:
            mock_run.return_value = SandboxResult(
                success=True, stdout="42\n", stderr="", exit_code=0, execution_time_ms=15.0
            )
            result = await sandbox.run("print(42)")
            assert result.success is True
            assert result.stdout == "42\n"
            assert result.execution_time_ms == 15.0

    @pytest.mark.asyncio
    async def test_run_with_input_data(self):
        sandbox = CodeSandbox()
        with patch.object(sandbox, "run", new=AsyncMock()) as mock_run:
            mock_run.return_value = SandboxResult(
                success=True, stdout='{"key": "value"}\n', stderr="", exit_code=0, execution_time_ms=12.0
            )
            result = await sandbox.run("import json; print(json.load(open('/sandbox/sandbox_input.json')))", {"key": "value"})
            assert result.success is True

    @pytest.mark.asyncio
    async def test_run_timeout(self):
        sandbox = CodeSandbox()
        with patch.object(sandbox, "run", new=AsyncMock()) as mock_run:
            mock_run.return_value = SandboxResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                execution_time_ms=30000.0,
                error="Execution timed out after 30s",
            )
            result = await sandbox.run("import time; time.sleep(999)")
            assert result.success is False
            assert result.error is not None
            assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_run_docker_not_available(self):
        sandbox = CodeSandbox()
        with patch.object(sandbox, "run", new=AsyncMock()) as mock_run:
            mock_run.return_value = SandboxResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                execution_time_ms=5.0,
                error="Docker is not available. Install Docker to run code in sandbox.",
            )
            result = await sandbox.run("print('hi')")
            assert result.success is False
            assert "Docker" in result.error

    @pytest.mark.asyncio
    async def test_run_with_file_check_returns_expected_files(self):
        sandbox = CodeSandbox()
        with patch.object(sandbox, "run_with_file_check", new=AsyncMock()) as mock_run:
            mock_run.return_value = (
                SandboxResult(success=True, stdout="file created", stderr="", exit_code=0, execution_time_ms=20.0),
                {"output.txt": "hello world"},
            )
            result, files = await sandbox.run_with_file_check(
                "open('/sandbox/output.txt', 'w').write('hello world')",
                expected_files=["output.txt"],
            )
            assert result.success is True
            assert "output.txt" in files
            assert files["output.txt"] == "hello world"

    @pytest.mark.asyncio
    async def test_run_with_file_check_missing_files(self):
        sandbox = CodeSandbox()
        with patch.object(sandbox, "run_with_file_check", new=AsyncMock()) as mock_run:
            mock_run.return_value = (
                SandboxResult(success=True, stdout="", stderr="", exit_code=0, execution_time_ms=10.0),
                {},
            )
            result, files = await sandbox.run_with_file_check(
                "print('no files created')",
                expected_files=["nonexistent.txt"],
            )
            assert files == {}

    @pytest.mark.asyncio
    async def test_run_with_file_check_docker_unavailable(self):
        sandbox = CodeSandbox()
        with patch.object(sandbox, "run_with_file_check", new=AsyncMock()) as mock_run:
            mock_run.return_value = (
                SandboxResult(
                    success=False,
                    stdout="",
                    stderr="",
                    exit_code=-1,
                    execution_time_ms=5.0,
                    error="Docker is not available.",
                ),
                {},
            )
            result, files = await sandbox.run_with_file_check("print('x')", expected_files=[])
            assert result.success is False
            assert result.error is not None

    def test_check_docker_available_static(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = CodeSandbox.check_docker_available()
            assert result is True

    def test_check_docker_not_available(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = CodeSandbox.check_docker_available()
            assert result is False

    def test_singleton(self):
        instance1 = get_code_sandbox()
        instance2 = get_code_sandbox()
        assert instance1 is instance2


class TestSandboxCodeExecutionAppend:
    @pytest.mark.asyncio
    async def test_no_code_blocks_returns_unchanged(self):
        text = "Just a plain response without any code."
        result = await run_code_in_sandbox_and_append_results(text)
        assert result == text

    @pytest.mark.asyncio
    async def test_code_block_gets_sandbox_result_appended(self):
        text = "Here is the code:\n```python\nprint(42)\n```"
        mock_sandbox = MagicMock()
        mock_sandbox.run = AsyncMock(return_value=SandboxResult(
            success=True, stdout="42\n", stderr="", exit_code=0, execution_time_ms=15.0
        ))

        with patch("knowledge_os.app.code_sandbox.get_code_sandbox", return_value=mock_sandbox):
            result = await run_code_in_sandbox_and_append_results(text)
            assert "sandbox-result" in result
            assert "success=true" in result
            assert "42" in result

    @pytest.mark.asyncio
    async def test_multiple_code_blocks_get_results(self):
        text = "Block 1:\n```python\nprint(1)\n```\nBlock 2:\n```python\nprint(2)\n```"
        mock_sandbox = MagicMock()
        mock_sandbox.run = AsyncMock(return_value=SandboxResult(
            success=True, stdout="1\n", stderr="", exit_code=0, execution_time_ms=10.0
        ))

        with patch("knowledge_os.app.code_sandbox.get_code_sandbox", return_value=mock_sandbox):
            result = await run_code_in_sandbox_and_append_results(text)
            assert result.count("sandbox-result") == 2

    @pytest.mark.asyncio
    async def test_handles_timeout_in_sandbox_run(self):
        text = "```python\nimport time; time.sleep(999)\n```"
        mock_sandbox = MagicMock()
        mock_sandbox.run = AsyncMock(return_value=SandboxResult(
            success=False, stdout="", stderr="", exit_code=-1, execution_time_ms=30000.0,
            error="Execution timed out after 30s"
        ))

        with patch("knowledge_os.app.code_sandbox.get_code_sandbox", return_value=mock_sandbox):
            result = await run_code_in_sandbox_and_append_results(text)
            assert "timed out" in result

    @pytest.mark.asyncio
    async def test_empty_code_block_skipped(self):
        text = "Empty block:\n```python\n```"
        result = await run_code_in_sandbox_and_append_results(text)
        assert "sandbox-result" not in result

    @pytest.mark.asyncio
    async def test_stderr_appears_in_comment(self):
        text = "```python\nprint(1/0)\n```"
        mock_sandbox = MagicMock()
        mock_sandbox.run = AsyncMock(return_value=SandboxResult(
            success=False, stdout="", stderr="ZeroDivisionError: division by zero", exit_code=1,
            execution_time_ms=5.0, error="ZeroDivisionError: division by zero"
        ))

        with patch("knowledge_os.app.code_sandbox.get_code_sandbox", return_value=mock_sandbox):
            result = await run_code_in_sandbox_and_append_results(text)
            assert "ZeroDivisionError" in result

    @pytest.mark.asyncio
    async def test_real_docker_integration(self):
        if not CodeSandbox.check_docker_available():
            pytest.skip("Docker is not available on this machine")
        text = "```python\nprint('hello from sandbox')\n```"
        result = await run_code_in_sandbox_and_append_results(text)
        assert "sandbox-result" in result
        assert "hello from sandbox" in result


class TestSandboxResultDataClass:
    def test_default_error_is_none(self):
        result = SandboxResult(success=True, stdout="", stderr="", exit_code=0, execution_time_ms=0.0)
        assert result.error is None

    def test_custom_error(self):
        result = SandboxResult(success=False, stdout="", stderr="fail", exit_code=1, execution_time_ms=1.0, error="fail")
        assert result.error == "fail"

    def test_equality_based_on_fields(self):
        r1 = SandboxResult(True, "a", "", 0, 1.0)
        r2 = SandboxResult(True, "a", "", 0, 1.0)
        assert r1 == r2
