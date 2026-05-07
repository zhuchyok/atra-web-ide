#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
import time


def emit(payload: dict) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()
    return 0


STATE_PATH = os.path.join(os.path.dirname(__file__), ".autoflow_state.json")


def load_state() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
            if isinstance(state, dict):
                return state
    except Exception:
        pass
    return {}


def save_state(state: dict) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception:
        # Hook should never fail closed because of state writes.
        pass


def extract_text(obj) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for key in ("prompt", "userPrompt", "message", "text", "input"):
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                return val
        for val in obj.values():
            out = extract_text(val)
            if out:
                return out
    if isinstance(obj, list):
        for item in obj:
            out = extract_text(item)
            if out:
                return out
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return emit({"permission": "allow"})

    prompt = extract_text(payload).lower()
    if not prompt:
        return emit({"permission": "allow"})

    creative = re.search(
        r"(нов(ую|ый|ая)|добав(ь|ить)|сделай|придум|дизайн|концепц|архитектур|feature|компонент)",
        prompt,
    )
    bugfix = re.search(
        r"(баг|ошибк|сломал|не работает|подвис|завис|регресс|fix|debug|traceback|exception)",
        prompt,
    )
    finalize = re.search(
        r"(готово|заверши|финал|release|ship|прод|закрыть|дожми|acceptance|report)",
        prompt,
    )

    category = None
    if creative:
        category = "creative"
    elif bugfix:
        category = "bugfix"
    elif finalize:
        category = "finalize"

    state = load_state()
    now = int(time.time())
    prompt_hash = hashlib.sha1(prompt.encode("utf-8")).hexdigest()
    prev_category = state.get("last_category")
    prev_hash = state.get("last_prompt_hash")
    consecutive = int(state.get("consecutive_asks", 0))

    if category:
        if prev_category == category and prev_hash != prompt_hash:
            consecutive += 1
        elif prev_category == category and prev_hash == prompt_hash:
            # Same prompt repeated: keep current level.
            consecutive = max(consecutive, 1)
        else:
            consecutive = 1
        state.update(
            {
                "last_category": category,
                "last_prompt_hash": prompt_hash,
                "consecutive_asks": consecutive,
                "updated_at": now,
            }
        )
        save_state(state)

    escalated = category is not None and consecutive >= 2

    if creative:
        user_msg = "AutoFlow: сначала дизайн. Запускаю brainstorm -> одобрение -> план внедрения."
        if escalated:
            user_msg = (
                "AutoFlow: повторный creative-запрос. Следующий шаг прямо сейчас: "
                "напишите `/brainstorm` и утвердите дизайн, затем `writing-plans`."
            )
        return emit(
            {
                "permission": "ask",
                "user_message": user_msg,
                "agent_message": "Use brainstorming skill first, then writing-plans. Do not implement before design approval.",
            }
        )
    if bugfix:
        user_msg = "AutoFlow: сначала системная диагностика причины, потом фикс."
        if escalated:
            user_msg = (
                "AutoFlow: повторный bugfix-запрос. Следующий шаг: запустите режим диагностики "
                "(systematic-debugging), затем фикс только по подтвержденной причине."
            )
        return emit(
            {
                "permission": "ask",
                "user_message": user_msg,
                "agent_message": "Use systematic-debugging skill before proposing or applying code fixes.",
            }
        )
    if finalize:
        user_msg = "AutoFlow: перед финалом нужна верификация с фактами (тесты/проверки)."
        if escalated:
            user_msg = (
                "AutoFlow: повторный финал-запрос. Следующий шаг: verification-before-completion "
                "с фактами (тесты/health/метрики), затем финальный отчет."
            )
        return emit(
            {
                "permission": "ask",
                "user_message": user_msg,
                "agent_message": "Use verification-before-completion before claiming completion.",
            }
        )

    return emit({"permission": "allow"})


if __name__ == "__main__":
    raise SystemExit(main())
