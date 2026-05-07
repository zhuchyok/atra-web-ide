#!/usr/bin/env python3
import json
import re
import sys


def _emit(obj: dict) -> int:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return _emit({"permission": "allow"})

    command = str(payload.get("command", "")).strip()
    if not command:
        return _emit({"permission": "allow"})

    lowered = command.lower()

    hard_deny_patterns = [
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+checkout\s+--\b",
        r"\brm\s+-rf\s+/\b",
        r"\bdocker\s+system\s+prune\b.*\b-a\b",
        r"\bmkfs\.",
        r"\bdd\s+if=",
    ]
    for pattern in hard_deny_patterns:
        if re.search(pattern, lowered):
            return _emit(
                {
                    "permission": "deny",
                    "user_message": "Команда заблокирована safety-hook: потенциально разрушительная операция.",
                    "agent_message": "Blocked by shell safety gate due to destructive command pattern.",
                }
            )

    if re.search(r"\bgit\s+push\b.*--force\b", lowered):
        return _emit(
            {
                "permission": "ask",
                "user_message": "Обнаружен force-push. Подтвердите выполнение только при явной необходимости.",
                "agent_message": "Force push requires explicit confirmation.",
            }
        )

    return _emit({"permission": "allow"})


if __name__ == "__main__":
    raise SystemExit(main())
