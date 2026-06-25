#!/usr/bin/env python3
"""
Singularity 15.0: автоматическая настройка Open WebUI (Golden Persona + инструмент ask_victoria).
Запуск: OPENWEBUI_ADMIN_EMAIL=admin@atra.local OPENWEBUI_ADMIN_PASSWORD=atra-admin-2026 python scripts/openwebui_bootstrap_singularity_15.py
Или после экспорта из .env: python scripts/openwebui_bootstrap_singularity_15.py
"""
import os
import sys
import json

try:
    import httpx
except ImportError:
    print("Установите: pip install httpx", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://localhost:3005")
EMAIL = os.getenv("OPENWEBUI_ADMIN_EMAIL", "admin@atra.local")
PASSWORD = os.getenv("OPENWEBUI_ADMIN_PASSWORD", "atra-admin-2026")
TIMEOUT = 30


def load_env():
    env_path = os.path.join(REPO_ROOT, ".env")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k in ("OPENWEBUI_ADMIN_EMAIL", "OPENWEBUI_ADMIN_PASSWORD", "OPENWEBUI_URL"):
                        os.environ.setdefault(k, v)


def main():
    load_env()
    base = OPENWEBUI_URL.rstrip("/")
    email = os.getenv("OPENWEBUI_ADMIN_EMAIL", EMAIL)
    password = os.getenv("OPENWEBUI_ADMIN_PASSWORD", PASSWORD)

    print("Open WebUI bootstrap (Singularity 15.0)")
    print(f"  URL: {base}")
    print(f"  Login: {email}")
    print()

    # 1. Login
    try:
        r = httpx.post(
            f"{base}/api/v1/auths/signin",
            json={"email": email, "password": password},
            timeout=TIMEOUT,
        )
    except httpx.ConnectError as e:
        print(f"Ошибка подключения к Open WebUI: {e}")
        print("  Запустите: ./scripts/start_singularity_15_openwebui.sh")
        sys.exit(1)

    if r.status_code != 200:
        print(f"Вход не удался (HTTP {r.status_code}). Проверьте OPENWEBUI_ADMIN_EMAIL и OPENWEBUI_ADMIN_PASSWORD.")
        print("  Для первого запуска без пользователей задайте их в .env или export; админ создастся при старте контейнера.")
        token = None
    else:
        data = r.json()
        token = data.get("token") or data.get("access_token")
        if token:
            print("  Вход выполнен.")
        else:
            print("  Ответ без токена:", list(data.keys()))
            token = None

    # 2. Try to get OpenAPI to find model/tool creation endpoints
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        spec = httpx.get(f"{base}/openapi.json", headers=headers, timeout=10).json()
    except Exception:
        spec = {}
    paths = spec.get("paths") or {}

    # 3. Load Golden Persona system prompt
    golden_path = os.path.join(REPO_ROOT, "docs", "SINGULARITY_15_GOLDEN_PERSONA.md")
    system_prompt = ""
    if os.path.isfile(golden_path):
        with open(golden_path, encoding="utf-8") as f:
            content = f.read()
        if "```" in content:
            parts = content.split("```")
            for i, p in enumerate(parts):
                if i % 2 == 1 and p.strip().startswith("Ты"):
                    system_prompt = p.strip()
                    break
            if not system_prompt and len(parts) >= 2:
                system_prompt = parts[1].strip()
        else:
            system_prompt = content[:2500].strip()
    if not system_prompt:
        system_prompt = "Ты — Виктория (Team Lead ATRA). Для любого исполнения вызывай только инструмент ask_victoria(goal, project_context, user_key). Не симулируй экспертов."

    model_created = False
    for path, methods in paths.items():
        if "model" in path.lower() and "post" in methods:
            if token and path.startswith("/api/"):
                try:
                    resp = httpx.post(
                        f"{base}{path}",
                        headers={**headers, "Content-Type": "application/json"},
                        json={
                            "id": "victoria-singularity-15",
                            "name": "Victoria (Singularity 15.0)",
                            "model": "Victoria",
                            "system_prompt": system_prompt[:4000],
                        },
                        timeout=TIMEOUT,
                    )
                    if resp.status_code in (200, 201):
                        model_created = True
                        print("  Создан пресет Victoria (Singularity 15.0).")
                        break
                except Exception as e:
                    pass
    if not model_created and token:
        pass  # API may differ

    # 4. Tool: try to register from file
    tool_path = os.path.join(REPO_ROOT, "configs", "openwebui_ask_victoria_tool.py")
    tool_created = False
    if os.path.isfile(tool_path):
        with open(tool_path) as f:
            tool_content = f.read()
        for path, methods in paths.items():
            if "tool" in path.lower() and "post" in methods:
                if token:
                    try:
                        resp = httpx.post(
                            f"{base}{path}",
                            headers={**headers, "Content-Type": "application/json"},
                            json={"content": tool_content, "name": "ask_victoria"},
                            timeout=TIMEOUT,
                        )
                        if resp.status_code in (200, 201):
                            tool_created = True
                            print("  Инструмент ask_victoria добавлен через API.")
                            break
                    except Exception:
                        pass
    if not tool_created:
        pass

    # 5. One-shot file for manual paste if API didn't do it
    out_dir = os.path.join(REPO_ROOT, "configs", "openwebui_singularity_15_oneload")
    os.makedirs(out_dir, exist_ok=True)
    oneload = os.path.join(out_dir, "SYSTEM_PROMPT_AND_TOOL.txt")
    with open(oneload, "w", encoding="utf-8") as f:
        f.write("=== СИСТЕМНЫЙ ПРОМПТ (скопируйте в Open WebUI → Model → System Prompt) ===\n\n")
        f.write(system_prompt)
        f.write("\n\n=== ИНСТРУМЕНТ ===\n")
        f.write("Workspace → Tools → Import Tools → выберите файл: configs/openwebui_ask_victoria_tool.py\n")
        f.write("(в контейнере: /workspace/configs/openwebui_ask_victoria_tool.py)\n")
        f.write(
            "\nValves: VICTORIA_URL=http://victoria-agent:8000, USE_BACKEND_PROXY=true, "
            "BACKEND_FALLBACK_URL=http://atra-web-ide-backend:8000\n"
        )
    print(f"  Файл для копирования: {oneload}")

    print()
    print("Дальше: откройте http://localhost:3005 → выберите модель Victoria → вставьте системный промпт из файла выше; добавьте инструмент из configs/openwebui_ask_victoria_tool.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
