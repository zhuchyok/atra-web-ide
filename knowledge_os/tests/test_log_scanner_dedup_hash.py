from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOG_SCANNER = ROOT / "knowledge_os" / "app" / "medic" / "log_scanner.py"


def test_log_scanner_hash_normalizes_dynamic_noise_before_dedup():
    text = LOG_SCANNER.read_text(encoding="utf-8")
    assert "def make_error_hash(self, container: str, error: Dict) -> str:" in text
    assert "hashlib.sha1" in text
    assert r"\b\d{4}-\d{2}-\d{2}[ t]\d{2}:\d{2}:\d{2}" in text
    assert r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b" in text
    assert r"\[\d+\]" in text
    assert "msg = re.sub(r\"\\s+\", \" \", msg).strip()" in text


def test_log_scanner_ignores_victoria_warmup_busy_noise():
    text = LOG_SCANNER.read_text(encoding="utf-8")
    assert r"\[VICTORIA\]\s+Прогрев .*вернул 503" in text
    assert r"\[VICTORIA\]\s+Прогрев .*busy \(503\)" in text


def test_log_scanner_ignores_watchdog_postgres_type_noise():
    text = LOG_SCANNER.read_text(encoding="utf-8")
    assert r"operator does not exist: (double precision \* text|text \* double precision)" in text
    assert r"canceling statement due to user request" in text
    assert r"FATAL:\s+connection to client lost" in text
    assert r'column "last_exec_time" does not exist' in text
    assert r"password authentication failed" in text
    assert r"\[MISMATCH-RECOVERY\]" in text
    assert r"Too many conn" in text
    assert r'unrecognized configuration parameter "default_pool_size"' in text
    assert r"task_identity_map.*violates foreign key constraint" in text
    assert r"Sandbox bind path .* is container-local" in text
    assert r"SandboxManager: Docker not available" in text
    assert r"Ошибка парсинга промпта" in text
    assert r"IndentationError.*corporation_knowledge_system" in text
    assert r"Traceback \(most recent call last\):" in text
    assert r"_receive_event\(timeout=timeout\)" in text
    assert r"Ollama timeout, retry \d+/\d+" in text
    assert r"Exception calling Node .*ReadTimeout" in text
    assert r"\[SANDBOX GROUNDING\]" in text
    assert r"No module named 'pytest'" in text
    assert r"Все модели недоступны" in text
    assert r"Error de respuesta" in text
    assert r"FATAL:" in text
    assert r'terminating background worker "parallel worker"' in text
    assert r"Ollama embed failed after" in text
    assert r"(?:^|[\s\"'])ERROR[:\s]|- ERROR -|\bCRITICAL\b|FATAL:" in text
    assert r"Exception:|Error:|RuntimeError:" not in text
    assert r"\[INFERENCE\] Ошибка прогрева модели" in text
    assert r"ai_core audit failed/timeout" in text
    assert r"TimeoutError\(\)" in text
    assert r"\b(TimeoutError|ReadTimeout|ConnectTimeout)\b" not in text
    assert "re.compile(r\"timeout|TimeoutError|ReadTimeout\")" not in text
