"""Shared Cursor-method snippet for Victoria, workers, and swarm."""

CURSOR_METHOD_PROMPT = (
    "МЕТОД CURSOR (обязателен): факты до вывода; "
    "не говори «готово» без доказательства (команда, тест, health); "
    "корень, не симптом; KISS.\n"
)

BARE_DONE_MARKERS = (
    "готово",
    "задача выполнена",
    "done",
    "всё работает",
    "все работает",
)
UNVERIFIED_SUCCESS_MARKERS = (
    "тесты пройдены",
    "тесты зелёные",
    "тесты зеленые",
    "задача закрыта",
    "фиксирую статус",
    "задача выполнена",
)
EVIDENCE_MARKERS = (
    "pytest",
    "curl",
    "pending=",
    "in_progress=",
    "passed",
    "exit_code",
    "/health",
    "assert",
    "8010",
    "docker",
)


def is_bare_done(result: str) -> bool:
    """True if the answer claims done/ok without a check artifact."""
    text = (result or "").strip().lower()
    if not text:
        return False
    if any(e in text for e in EVIDENCE_MARKERS):
        return False
    if any(m in text for m in UNVERIFIED_SUCCESS_MARKERS):
        return True
    if len(text) > 80:
        return False
    return any(m in text for m in BARE_DONE_MARKERS)


BARE_DONE_REFUSAL = (
    "Не заявляю «готово» без доказательства "
    "(нужен вывод команды, теста или /health)."
)


def reject_bare_done_answer(text: str) -> str:
    """Egress guard: replace bare-done claims with an honest refusal."""
    if is_bare_done(text):
        return BARE_DONE_REFUSAL
    return text or ""


def should_journal_task(summary: str, execution_mode: str | None = None) -> bool:
    """Skip fast-path noise; keep real work and failures."""
    if execution_mode == "fast_path":
        return False
    return not (summary or "").lower().startswith("fast-path")
