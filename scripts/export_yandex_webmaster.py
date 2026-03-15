#!/usr/bin/env python3
"""
Выгрузка данных из API Яндекс.Вебмастера в JSON.
Читает учётные данные из .env.webmaster (создаётся через setup_yandex_webmaster_env.py).
Результаты: docs/webmaster_export/
"""
import json
import os
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.webmaster")
OUT_DIR = os.path.join(REPO_ROOT, "docs", "webmaster_export")
API_BASE = "https://api.webmaster.yandex.net/v4"


def load_env() -> dict:
    out = {}
    if not os.path.exists(ENV_FILE):
        raise SystemExit(f"Файл {ENV_FILE} не найден. Сначала запусти: python3 scripts/setup_yandex_webmaster_env.py")
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                v = v.strip().strip('"').strip("'")
                if v.startswith('"') and v.endswith('"'):
                    v = v[1:-1].replace('\\"', '"')
                out[k.strip()] = v
    return out


def api_get(token: str, path: str) -> dict:
    url = API_BASE + path
    req = urllib.request.Request(url, headers={"Authorization": f"OAuth {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    os.chdir(REPO_ROOT)
    env = load_env()
    token = env.get("YANDEX_WEBMASTER_TOKEN")
    if not token:
        raise SystemExit("В .env.webmaster нет YANDEX_WEBMASTER_TOKEN. Запусти setup_yandex_webmaster_env.py")

    os.makedirs(OUT_DIR, exist_ok=True)

    user = api_get(token, "/user/")
    user_id = user.get("user_id")
    if not user_id:
        raise SystemExit("Не удалось получить user_id: " + json.dumps(user, ensure_ascii=False, indent=2))

    hosts = api_get(token, f"/user/{user_id}/hosts/")
    host_list = hosts.get("hosts") or []
    with open(os.path.join(OUT_DIR, "user_and_hosts.json"), "w", encoding="utf-8") as f:
        json.dump({"user": user, "hosts": host_list}, f, ensure_ascii=False, indent=2)
    print(f"Сохранено: user_and_hosts.json ({len(host_list)} сайтов)")

    for h in host_list:
        host_id = h.get("host_id")
        name = (h.get("host_url") or host_id or "unknown").replace("https://", "").replace("http://", "").replace("/", "_")
        if not host_id:
            continue
        prefix = f"/user/{user_id}/hosts/{host_id}"
        for label, path in [
            ("summary", f"{prefix}/summary/"),
            ("indexing_history", f"{prefix}/indexing/history/"),
            ("search_queries_all_history", f"{prefix}/search-queries/all/history/"),
            ("diagnostics", f"{prefix}/diagnostics/"),
        ]:
            try:
                data = api_get(token, path)
                safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in name)[:50]
                fn = os.path.join(OUT_DIR, f"{safe_name}_{label}.json")
                with open(fn, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"  {safe_name}: {label}")
            except Exception as e:
                print(f"  {name}: {label} — ошибка: {e}")

    print(f"\nВсё сохранено в {OUT_DIR}")


if __name__ == "__main__":
    main()
