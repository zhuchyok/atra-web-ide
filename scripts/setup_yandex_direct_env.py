#!/usr/bin/env python3
"""
Интерактивная настройка учётных данных для API Яндекс.Директа.
Записывает данные в .env.direct (файл в .gitignore).
Приложение в OAuth должно иметь доступ «Яндекс.Директ — Использование API».
Запуск: python3 scripts/setup_yandex_direct_env.py
"""
import os
import sys
import urllib.parse
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.direct")


def prompt(msg: str, secret: bool = False) -> str:
    if secret and sys.stdin.isatty():
        try:
            import getpass
            return (getpass.getpass(msg) or "").strip()
        except Exception:
            pass
    return input(msg).strip()


def load_existing() -> dict:
    out = {}
    if not os.path.exists(ENV_FILE):
        return out
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def save_env(vars: dict) -> None:
    existing = load_existing()
    existing.update(vars)
    lines = [
        "# Учётные данные API Яндекс.Директа (не коммитить)",
        "# Создано скриптом scripts/setup_yandex_direct_env.py",
        "",
    ]
    for k, v in existing.items():
        if not v:
            continue
        if "\n" in v or " " in v or "#" in v or '"' in v:
            v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        lines.append(f"{k}={v}")
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nЗаписано в {ENV_FILE}")


def exchange_code_for_token(client_id: str, client_secret: str, code: str) -> str:
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth.yandex.ru/token",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        import json
        body = json.loads(resp.read().decode())
    token = body.get("access_token")
    if not token:
        raise SystemExit("В ответе нет access_token: " + str(body))
    return token


def main() -> None:
    os.chdir(REPO_ROOT)
    print("Учётные данные для API Яндекс.Директа")
    print("(файл .env.direct в корне проекта, не коммитится)")
    print("Важно: при получении токена войди под тем логином, с которым заходишь в Директ.\n")

    existing = load_existing()
    client_id = prompt("Client ID (ID приложения): ").strip() or existing.get("YANDEX_DIRECT_CLIENT_ID", "")
    if not client_id:
        print("Нужен Client ID. Выход.")
        sys.exit(1)

    client_secret = prompt("Client secret (Пароль приложения): ", secret=True).strip() or existing.get("YANDEX_DIRECT_CLIENT_SECRET", "")
    if not client_secret:
        print("Нужен Client secret. Выход.")
        sys.exit(1)

    have_token = prompt("У тебя уже есть access_token? (y/n) [n]: ").strip().lower() or "n"
    if have_token == "y":
        token = prompt("Вставь access_token: ", secret=True).strip()
        if not token:
            print("Токен не введён. Выход.")
            sys.exit(1)
    else:
        print("\nПолучить код: открой в браузере под логином Директа:")
        print(f"  https://oauth.yandex.ru/authorize?response_type=code&client_id={client_id}")
        print("После «Разрешить» скопируй код со страницы oauth.yandex.ru/verification_code\n")
        code = prompt("Вставь код: ").strip()
        if not code:
            print("Код не введён. Выход.")
            sys.exit(1)
        token = exchange_code_for_token(client_id, client_secret, code)
        print("Токен успешно получен.")

    save_env({
        "YANDEX_DIRECT_CLIENT_ID": client_id,
        "YANDEX_DIRECT_CLIENT_SECRET": client_secret,
        "YANDEX_DIRECT_TOKEN": token,
    })
    print("Готово. Для выгрузки данных запусти: python3 scripts/export_yandex_direct.py")


if __name__ == "__main__":
    main()
