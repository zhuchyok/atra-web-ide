"""Log scanner must not turn asyncio cancel / retry noise into Victoria tasks."""

import importlib.util
from pathlib import Path

_SCANNER = Path(__file__).resolve().parents[2] / "knowledge_os" / "app" / "medic" / "log_scanner.py"
_spec = importlib.util.spec_from_file_location("log_scanner_under_test", _SCANNER)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
LogScanner = _mod.LogScanner


def test_ignore_cancelled_traceback_header():
    scanner = LogScanner()
    assert scanner.extract_error("Traceback (most recent call last):") is None
    assert scanner.extract_error("asyncio.exceptions.CancelledError") is None
    assert scanner.extract_error("event = await self._receive_event(timeout=timeout)") is None


def test_ignore_sandbox_qa_noise():
    scanner = LogScanner()
    assert scanner.extract_error(
        "WARNING:quality_assurance:🧪 [SANDBOX GROUNDING] Code failed verification: Runtime/Assertion Error"
    ) is None
    assert scanner.extract_error("ModuleNotFoundError: No module named 'pytest'") is None


def test_ignore_visual_search_retry_and_router_readtimeout():
    scanner = LogScanner()
    assert scanner.extract_error("WARNING:__main__:Ollama timeout, retry 2/5 in 3s") is None
    assert scanner.extract_error(
        "ERROR:local_router:[ROUTER] Exception calling Node Mac Studio (Ollama): ReadTimeout:"
    ) is None


def test_ignore_pg_parallel_fatal_and_busy_retries():
    scanner = LogScanner()
    assert scanner.extract_error(
        '2026-09-21 FATAL:  terminating background worker "parallel worker" due to a'
    ) is None
    assert scanner.extract_error(
        "Признание опасности FATAL сообщения, но отсутствие инструментов"
    ) is None
    assert scanner.extract_error(
        "ERROR:__main__:Search error: Ollama embed failed after 5 retries"
    ) is None
    assert scanner.extract_error(
        'ERROR:src.agents.core.executor:[LLM_ERROR] HTTP 503: {"error":"server busy, please try again.'
    ) is None


def test_ignore_llm_prose_error_and_rag_timeout():
    scanner = LogScanner()
    assert scanner.extract_error(
        "2. Error de respuesta: Para identificar problemas de fiabilidad."
    ) is None
    assert scanner.extract_error(
        "2026-09-20 23:44:47,223 - ERROR - ⏰ RAG retrieval превысил таймаут 30.0с — продолжаем без контекста"
    ) is None


def test_ignore_nightly_ai_core_audit_timeout():
    scanner = LogScanner()
    assert scanner.extract_error(
        "2026-09-21 10:03:43,797 WARNING ai_core audit failed/timeout: TimeoutError()"
    ) is None


def test_still_catches_real_type_and_sql_errors():
    scanner = LogScanner()
    typo = scanner.extract_error(
        "TypeError: run_smart_agent_async() got an unexpected keyword argument 'model'"
    )
    assert typo is not None
    assert typo["type"] == "TypeError"

    sql = scanner.extract_error(
        'ERROR:  invalid input syntax for type interval: "%s days"'
    )
    assert sql is not None
    assert sql["type"] in ("LOG_ERROR", "EXCEPTION")
