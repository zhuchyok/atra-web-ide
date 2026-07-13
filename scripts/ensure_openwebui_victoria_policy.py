#!/usr/bin/env python3
"""Ensure Open WebUI model routing to ask_victoria is always enforced.

This script also force-binds known Victoria runtime model ids, so choosing
`victoria-wisdom-v3.5:latest` directly in Open WebUI still uses:
- ask_victoria tool routing
- Golden Persona style prompt
- policy override block
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


TOOL_ID = "ask_victoria_singularity_15"
TARGET_MODEL_IDS = [
    "Victoria",
    "victoria-wisdom-v3.5:latest",
    "victoria-wisdom-v3.5:latest-pre-qwen36",
    "victoria-wisdom-v3.5-pre-qwen36:latest",
]
TOOL_ROUTER_MODEL = "qwen3.6:35b-a3b-nvfp4"
TOOL_ROUTER_OVERRIDES = {
    "Victoria": TOOL_ROUTER_MODEL,
    "victoria-wisdom-v3.5:latest": TOOL_ROUTER_MODEL,
    "victoria-wisdom-v3.5:latest-pre-qwen36": TOOL_ROUTER_MODEL,
    "victoria-wisdom-v3.5-pre-qwen36:latest": TOOL_ROUTER_MODEL,
}
DEFAULT_SYSTEM = (
    "Ты — Виктория, Team Lead корпорации ATRA. "
    "Для любых запросов на действие/анализ проекта вызывай ask_victoria. "
    "Для приветствий и короткого small-talk отвечай кратко сама."
)
POLICY_BLOCK = (
    "\n\n[ATRA POLICY OVERRIDE]\n"
    "- Для ЛЮБОГО пользовательского запроса сначала вызывай ask_victoria, затем отвечай по факту результата.\n"
    "- Не отвечай из внутренних знаний модели без tool-call ask_victoria, даже для общих вопросов про систему.\n"
    "- Вызов инструмента делай ТОЛЬКО как нативный tool/function call Open WebUI.\n"
    "- НИКОГДА не печатай в сообщении пользователю строку вида ask_victoria(...), это считается ошибкой формата.\n"
    "- Если tool-call недоступен технически, ответь кратко как Виктория и попроси повторить запрос, но не выводи синтаксис вызова.\n"
    "- Не используй формат ссылок вида [1], [2] и не цитируй служебные source-id в тексте ответа.\n"
    "- Не упоминай технические имена инструментов/источников вроде ask_victoria_singularity_15 в пользовательском ответе.\n"
    "- Вопросы вида «а доступ появился?», «видишь ли ты папку/файл», проверки путей "
    "(/Users/..., /workspace/..., /app/...) относятся к зоне действия ask_victoria.\n"
    "- В таких запросах НЕ отвечай общими рассуждениями про sandbox и НЕ пиши гипотезы.\n"
    "- Всегда сначала вызывай инструмент ask_victoria и отвечай только фактом из его результата.\n"
    "- Не выводи внутренние рассуждения/chain-of-thought и блоки <details type=\"reasoning\">.\n"
    "- На прямые вопросы идентичности (\"ты Виктория?\", \"кто ты?\") отвечай кратко: "
    "\"Да, я Виктория, Team Lead корпорации ATRA.\".\n"
)


def run(cmd: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, check=False)


def _discover_ollama_model_ids() -> set[str]:
    """Best-effort discovery of local runtime model IDs from ollama."""
    out = run(["ollama", "list"])
    if out.returncode != 0:
        return set()
    ids: set[str] = set()
    lines = (out.stdout or "").splitlines()
    # Typical format:
    # NAME            ID        SIZE   MODIFIED
    # qwen2.5:14b     ...
    for idx, line in enumerate(lines):
        s = (line or "").strip()
        if not s:
            continue
        if idx == 0 and "NAME" in s and "ID" in s:
            continue
        name = s.split()[0].strip()
        if name and ":" in name:
            ids.add(name)
    return ids


def _load_golden_persona() -> str:
    docs_path = Path(__file__).resolve().parents[1] / "docs" / "SINGULARITY_15_GOLDEN_PERSONA.md"
    try:
        text = docs_path.read_text(encoding="utf-8")
    except Exception:
        return DEFAULT_SYSTEM
    blocks = re.findall(r"```(.*?)```", text, flags=re.DOTALL)
    for block in blocks:
        candidate = (block or "").strip()
        if "Ты отвечаешь только от имени Виктории" in candidate:
            return candidate
    return DEFAULT_SYSTEM


def _upsert_policy_block(system_prompt: str) -> str:
    """Remove older policy blocks and append current one once."""
    text = system_prompt or ""
    text = re.sub(
        r"\n*\[ATRA POLICY OVERRIDE\]\n(?:- .*(?:\n|$))+",
        "\n",
        text,
        flags=re.MULTILINE,
    ).strip()
    return (text + POLICY_BLOCK).strip()


def main() -> int:
    ps = run(["docker", "ps", "--format", "{{.Names}}"])
    if ps.returncode != 0:
        print("openwebui-policy: docker unavailable", file=sys.stderr)
        return 1
    if "open-webui" not in set(ps.stdout.split()):
        print("openwebui-policy: open-webui not running; skip")
        return 0

    golden_persona = _load_golden_persona()

    read_code = f"""
import sqlite3, json
c=sqlite3.connect('/app/backend/data/webui.db')
c.row_factory=sqlite3.Row
rows=c.execute("SELECT id,name,meta,params FROM model").fetchall()
for r in rows:
    print(json.dumps({{"id": r["id"], "name": r["name"], "meta": r["meta"] or "{{}}", "params": r["params"] or "{{}}"}}, ensure_ascii=False))
"""
    read = run(["docker", "exec", "-i", "open-webui", "python", "-"], stdin=read_code)
    if read.returncode != 0:
        print(f"openwebui-policy: read failed: {read.stderr.strip()}", file=sys.stderr)
        return 1

    user_code = """
import sqlite3
c=sqlite3.connect('/app/backend/data/webui.db')
c.row_factory=sqlite3.Row
u=c.execute("SELECT id FROM user ORDER BY created_at ASC LIMIT 1").fetchone()
print((u["id"] if u else "").strip())
"""
    user_read = run(["docker", "exec", "-i", "open-webui", "python", "-"], stdin=user_code)
    if user_read.returncode != 0:
        print(f"openwebui-policy: user lookup failed: {user_read.stderr.strip()}", file=sys.stderr)
        return 1
    owner_user_id = (user_read.stdout or "").strip()
    if not owner_user_id:
        print("openwebui-policy: no user found in Open WebUI db", file=sys.stderr)
        return 1

    model_payloads: list[dict] = []
    for line in (read.stdout or "").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            model_payloads.append(json.loads(s))
        except Exception:
            continue

    model_map: dict[str, dict] = {}
    existing_ids: set[str] = set()
    for item in model_payloads:
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        model_map[model_id] = item
        existing_ids.add(model_id)

    target_ids = set(existing_ids)
    target_ids.update(TARGET_MODEL_IDS)
    target_ids.update(_discover_ollama_model_ids())
    for item in model_payloads:
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        try:
            meta = json.loads((item.get("meta") or "{}").strip() or "{}")
        except Exception:
            meta = {}
        if TOOL_ID in (meta.get("toolIds") or []):
            target_ids.add(model_id)

    updates: list[tuple[str, str, str | None, str, str]] = []
    inserted = 0
    for model_id in sorted(target_ids):
        item = model_map.get(model_id, {"id": model_id, "name": model_id, "meta": "{}", "params": "{}"})
        try:
            meta = json.loads((item.get("meta") or "{}").strip() or "{}")
        except Exception:
            meta = {}
        try:
            params = json.loads((item.get("params") or "{}").strip() or "{}")
        except Exception:
            params = {}
        tool_ids = list(meta.get("toolIds") or [])
        if TOOL_ID not in tool_ids:
            tool_ids.append(TOOL_ID)
        meta["toolIds"] = tool_ids
        capabilities = dict(meta.get("capabilities") or {})
        # Disable citation-style prompting that leaks tool source IDs ([1], ask_victoria_...).
        capabilities["citations"] = False
        meta["capabilities"] = capabilities

        system_prompt = str(params.get("system") or "").strip()
        if not system_prompt:
            system_prompt = golden_persona or DEFAULT_SYSTEM
        system_prompt = _upsert_policy_block(system_prompt)
        params["system"] = system_prompt

        updates.append(
            (
                model_id,
                str(item.get("name") or model_id),
                TOOL_ROUTER_OVERRIDES.get(model_id),
                json.dumps(meta, ensure_ascii=False),
                json.dumps(params, ensure_ascii=False),
            )
        )
        if model_id not in existing_ids:
            inserted += 1

    update_code = """
import json, sqlite3, sys, time
payload = json.loads(sys.stdin.read() or "{}")
updates = payload.get("updates") or []
user_id = payload.get("user_id") or ""
if not user_id:
    raise SystemExit("missing user_id")
c = sqlite3.connect('/app/backend/data/webui.db')
now = int(time.time())
for m, n, base_model_id, meta, params in updates:
    row = c.execute("SELECT 1 FROM model WHERE id=?", (m,)).fetchone()
    if row:
        c.execute(
            "UPDATE model SET name=?, base_model_id=?, meta=?, params=?, updated_at=?, is_active=1 WHERE id=?",
            (n, base_model_id, meta, params, now, m),
        )
    else:
        c.execute(
            "INSERT INTO model (id, user_id, base_model_id, name, meta, params, created_at, updated_at, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (m, user_id, base_model_id, n, meta, params, now, now),
        )
c.commit()
print(f"updated_models={len(updates)}")
"""
    update_payload = json.dumps({"updates": updates, "user_id": owner_user_id}, ensure_ascii=False)
    up = run(
        ["docker", "exec", "-i", "open-webui", "python", "-c", update_code],
        stdin=update_payload,
    )
    if up.returncode != 0:
        print(f"openwebui-policy: update failed: {up.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"openwebui-policy: updated ({len(updates)} model(s), inserted={inserted})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
