from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "knowledge_os" / "app" / "telegram_notifications_worker.py"


def test_telegram_chat_id_alias_is_supported():
    text = WORKER.read_text(encoding="utf-8")
    assert 'os.getenv("TELEGRAM_CHAT_ID")' in text
    assert 'os.getenv("TELEGRAM_USER_ID")' in text
    assert 'os.getenv("CHAT_ID", "")' in text
