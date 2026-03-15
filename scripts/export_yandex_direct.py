#!/usr/bin/env python3
"""
Выгрузка данных из API Яндекс.Директа в JSON.
Читает учётные данные из .env.direct (создаётся через setup_yandex_direct_env.py).
Результаты: docs/direct_export/
"""
import json
import os
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.direct")
OUT_DIR = os.path.join(REPO_ROOT, "docs", "direct_export")
API_BASE = "https://api.direct.yandex.com/json/v5"


def load_env() -> dict:
    out = {}
    if not os.path.exists(ENV_FILE):
        raise SystemExit(f"Файл {ENV_FILE} не найден. Сначала запусти: python3 scripts/setup_yandex_direct_env.py")
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


def api_post(token: str, service: str, payload: dict) -> dict:
    url = f"{API_BASE}/{service}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Language": "ru",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            out = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            err = json.loads(body)
            msg = err.get("error", {}).get("error_string", body or str(e))
            code = err.get("error", {}).get("error_code", "")
        except Exception:
            msg = body or str(e)
            code = ""
        hint = ""
        if "авторизац" in msg.lower() or e.code == 401:
            hint = " Проверь: 1) токен под логином Директа? 2) доступ «Яндекс.Директ — API» в OAuth? 3) новый токен: python3 scripts/setup_yandex_direct_env.py"
        elif code == "58" or "незавершенная регистрация" in msg.lower():
            hint = " Подай заявку: direct.yandex.ru → Настройки → Настройки API → Мои заявки → Новая заявка, укажи Client ID. См. docs/YANDEX_DIRECT_OAUTH_SETUP.md"
        raise RuntimeError(f"{msg} (code={code}){hint}") from e
    if "error" in out:
        err = out.get("error", {})
        msg = err.get("error_string", str(out))
        code = err.get("error_code", "")
        hint = ""
        if "авторизац" in msg.lower() or code in ("53", "54", "56"):
            hint = " Проверь: 1) токен получен под логином Директа? 2) у приложения в OAuth есть доступ «Яндекс.Директ — API»? 3) получи новый токен: python3 scripts/setup_yandex_direct_env.py"
        elif code == "58" or "незавершенная регистрация" in msg.lower():
            hint = " Нужна заявка на доступ к API: зайди в direct.yandex.ru → Настройки → Настройки API → Мои заявки → Новая заявка, укажи Client ID приложения из OAuth, выбери тип доступа и дождись одобрения (до 7 дней). См. docs/YANDEX_DIRECT_OAUTH_SETUP.md"
        raise RuntimeError(f"{msg} (code={code}){hint}")
    return out


def main() -> None:
    os.chdir(REPO_ROOT)
    env = load_env()
    token = env.get("YANDEX_DIRECT_TOKEN")
    if not token:
        raise SystemExit("В .env.direct нет YANDEX_DIRECT_TOKEN. Запусти setup_yandex_direct_env.py")

    os.makedirs(OUT_DIR, exist_ok=True)

    # Список кампаний
    campaigns_payload = {
        "method": "get",
        "params": {
            "SelectionCriteria": {},
            "FieldNames": ["Id", "Name", "State", "Status", "Type", "StatusPayment"],
        },
    }
    campaigns_resp = api_post(token, "campaigns", campaigns_payload)
    campaigns = campaigns_resp.get("result", {}).get("Campaigns") or []
    with open(os.path.join(OUT_DIR, "campaigns.json"), "w", encoding="utf-8") as f:
        json.dump(campaigns_resp, f, ensure_ascii=False, indent=2)
    print(f"Сохранено: campaigns.json ({len(campaigns)} кампаний)")

    if not campaigns:
        print("Кампаний нет. Всё сохранено в", OUT_DIR)
        return

    campaign_ids = [c["Id"] for c in campaigns]

    # Группы объявлений по кампаниям
    adgroups_payload = {
        "method": "get",
        "params": {
            "SelectionCriteria": {"CampaignIds": campaign_ids},
            "FieldNames": ["Id", "Name", "CampaignId", "Status", "Type", "State"],
        },
    }
    try:
        adgroups_resp = api_post(token, "adgroups", adgroups_payload)
        adgroups = adgroups_resp.get("result", {}).get("AdGroups") or []
        with open(os.path.join(OUT_DIR, "adgroups.json"), "w", encoding="utf-8") as f:
            json.dump(adgroups_resp, f, ensure_ascii=False, indent=2)
        print(f"Сохранено: adgroups.json ({len(adgroups)} групп)")
    except Exception as e:
        print("adgroups — ошибка:", e)
        adgroups = []

    # Ключевые слова (по всем группам или по первым 20)
    adgroup_ids = [g["Id"] for g in adgroups[:500]]
    if adgroup_ids:
        keywords_payload = {
            "method": "get",
            "params": {
                "SelectionCriteria": {"AdGroupIds": adgroup_ids},
                "FieldNames": ["Id", "Keyword", "AdGroupId", "State", "Status", "Bid", "CampaignId"],
            },
        }
        try:
            keywords_resp = api_post(token, "keywords", keywords_payload)
            keywords = keywords_resp.get("result", {}).get("Keywords") or []
            with open(os.path.join(OUT_DIR, "keywords.json"), "w", encoding="utf-8") as f:
                json.dump(keywords_resp, f, ensure_ascii=False, indent=2)
            print(f"Сохранено: keywords.json ({len(keywords)} фраз)")
        except Exception as e:
            print("keywords — ошибка:", e)

    # Объявления (по тем же группам)
    if adgroup_ids:
        ads_payload = {
            "method": "get",
            "params": {
                "SelectionCriteria": {"AdGroupIds": adgroup_ids},
                "FieldNames": ["Id", "State", "Status", "Type", "AdGroupId"],
            },
        }
        try:
            ads_resp = api_post(token, "ads", ads_payload)
            ads = ads_resp.get("result", {}).get("Ads") or []
            with open(os.path.join(OUT_DIR, "ads.json"), "w", encoding="utf-8") as f:
                json.dump(ads_resp, f, ensure_ascii=False, indent=2)
            print(f"Сохранено: ads.json ({len(ads)} объявлений)")
        except Exception as e:
            print("ads — ошибка:", e)

    print(f"\nВсё сохранено в {OUT_DIR}")


if __name__ == "__main__":
    main()
