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
    assert (
        scanner.extract_error(
            "WARNING:quality_assurance:🧪 [SANDBOX GROUNDING] Code failed verification: Runtime/Assertion Error"
        )
        is None
    )
    assert scanner.extract_error("ModuleNotFoundError: No module named 'pytest'") is None


def test_ignore_visual_search_retry_and_router_readtimeout():
    scanner = LogScanner()
    assert scanner.extract_error("WARNING:__main__:Ollama timeout, retry 2/5 in 3s") is None
    assert (
        scanner.extract_error(
            "ERROR:local_router:[ROUTER] Exception calling Node Mac Studio (Ollama): ReadTimeout:"
        )
        is None
    )


def test_ignore_pg_parallel_fatal_and_busy_retries():
    scanner = LogScanner()
    assert (
        scanner.extract_error(
            '2026-09-21 FATAL:  terminating background worker "parallel worker" due to a'
        )
        is None
    )
    assert (
        scanner.extract_error("Признание опасности FATAL сообщения, но отсутствие инструментов")
        is None
    )
    assert (
        scanner.extract_error("ERROR:__main__:Search error: Ollama embed failed after 5 retries")
        is None
    )
    assert (
        scanner.extract_error(
            'ERROR:src.agents.core.executor:[LLM_ERROR] HTTP 503: {"error":"server busy, please try again.'
        )
        is None
    )


def test_ignore_llm_prose_error_and_rag_timeout():
    scanner = LogScanner()
    assert (
        scanner.extract_error("2. Error de respuesta: Para identificar problemas de fiabilidad.")
        is None
    )
    assert (
        scanner.extract_error(
            "2026-09-20 23:44:47,223 - ERROR - ⏰ RAG retrieval превысил таймаут 30.0с — продолжаем без контекста"
        )
        is None
    )


def test_ignore_nightly_ai_core_audit_timeout():
    scanner = LogScanner()
    assert (
        scanner.extract_error(
            "2026-09-21 10:03:43,797 WARNING ai_core audit failed/timeout: TimeoutError()"
        )
        is None
    )


def test_ignore_worker_ops_logged_as_error():
    scanner = LogScanner()
    assert (
        scanner.extract_error(
            "ERROR:ExpertWorker:🔄 [RESURRECTION] Found my task 4730fb20-7e73-459d-a970-20615b4b24f5. Resuming..."
        )
        is None
    )
    assert (
        scanner.extract_error(
            "ERROR:ExpertWorker:✅ [RESURRECTION] Successfully resumed 1 tasks for Инна"
        )
        is None
    )
    assert (
        scanner.extract_error(
            "ERROR:ExpertWorker:🏆 [AUCTION] Юлия WON task 09cbc470-24f3-4072-90dd-153e53727261"
        )
        is None
    )
    assert (
        scanner.extract_error(
            "ERROR:ExpertWorker:❌ [HEARTBEAT] Loop failed for 4730fb20-7e73-459d-a970-20615b4b24f5: Lost task own"
        )
        is None
    )
    assert (
        scanner.extract_error(
            "ERROR:app.ai_core:⛔ [LOOP-BREAKER] Виктория: промпт(Проанализируй текст"
        )
        is None
    )
    assert scanner.extract_error('FATAL: role "postgres" does not exist') is None
    assert (
        scanner.extract_error(
            "ERROR ❌ [DISTILLATION] Failed to parse wisdom for node 8ab34478-9dd8-4623-86"
        )
        is None
    )


def test_ignore_source_guard_refuse_and_embed_404():
    scanner = LogScanner()
    assert (
        scanner.extract_error(
            "2026-11-03 22:44:33,043 - ERROR - 🛡️ [SOURCE_GUARD] ОТКАЗ "
            "(protected source path (src/agents/)): /workspace/atra-web-ide/src/agents/bridge/victoria_server.py"
        )
        is None
    )
    assert (
        scanner.extract_error(
            "ERROR:__main__:Search error: Ollama embed failed: 404 "
            '{"error":"model \\"nomic-embed-text\\" not found"}'
        )
        is None
    )
    assert (
        scanner.extract_error(
            "WARNING [LOG_SCANNER] [RATE_LIMIT] Throttled: 5/5 tasks in last hour"
        )
        is None
    )
    assert (
        scanner.extract_error("ERROR [LOG_SCANNER] ❌ [LOG_SCANNER] Ошибка отправки в Victoria: ")
        is None
    )


def test_ignore_redis_flap_and_tokens_used_sql():
    scanner = LogScanner()
    assert scanner.extract_error(
        "ERROR:event_bus_redis_bridge:⚠️ Bridge loop error: Connection closed by server."
    ) is None
    assert scanner.extract_error(
        "ERROR:ExpertWorker:⚠️ [WORKER] Ошибка в цикле: Connection closed by server."
    ) is None
    assert scanner.extract_error(
        "ERROR:PerformanceWatchdog:Error in system resource monitoring: Error 111 connecting to /data/redis/redis.sock"
    ) is None
    assert scanner.extract_error(
        'ERROR:  column "tokens_used" does not exist at character 47'
    ) is None
    assert scanner.extract_error(
        "ERROR - [FALLBACK] Max fallback attempts reached (3)"
    ) is None


def test_ignore_write_file_missing_and_norm_in_echo():
    scanner = LogScanner()
    assert scanner.extract_error("ERROR - ❌ Инструмент write_file не найден.") is None
    assert scanner.extract_error("WARNING - NORM_IN len=12 head='TypeError: x'") is None


def test_ignore_git_push_rejected():
    scanner = LogScanner()
    assert (
        scanner.extract_error(
            "Error: git_push rejected (ATRA_ALLOW_GIT_PUSH not set). Human push only."
        )
        is None
    )


def test_still_catches_resurrection_recovery_failed():
    scanner = LogScanner()
    hit = scanner.extract_error("ERROR:ExpertWorker:❌ [RESURRECTION] Recovery failed: boom")
    assert hit is not None


def test_still_catches_real_type_and_sql_errors():
    scanner = LogScanner()
    typo = scanner.extract_error(
        "TypeError: run_smart_agent_async() got an unexpected keyword argument 'model'"
    )
    assert typo is not None
    assert typo["type"] == "TypeError"

    sql = scanner.extract_error('ERROR:  invalid input syntax for type interval: "%s days"')
    assert sql is not None
    assert sql["type"] in ("LOG_ERROR", "EXCEPTION")
