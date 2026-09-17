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
    assert r"Ошибка парсинга промпта" in text
    assert r"IndentationError.*corporation_knowledge_system" in text
