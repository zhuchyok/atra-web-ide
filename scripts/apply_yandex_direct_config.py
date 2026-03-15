#!/usr/bin/env python3
"""
Применяет конфиг заголовков и текстов объявлений Setki21 к Яндекс.Директу.

Режимы:
  Без флагов — через API (нужна одобренная заявка в Директе).
  --runbook  — без API: генерирует пошаговую инструкцию для ручного ввода в кабинете.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.direct")
CONFIG_PATH = os.path.join(REPO_ROOT, "configs", "setki21_direct_ads.yaml")
RUNBOOK_PATH = os.path.join(REPO_ROOT, "docs", "runbooks", "SETKI21_DIRECT_APPLY_MANUAL.md")
API_BASE = "https://api.direct.yandex.com/json/v5"


def load_env() -> dict:
    out = {}
    if not os.path.exists(ENV_FILE):
        raise SystemExit(
            f"Файл {ENV_FILE} не найден. Сначала: python3 scripts/setup_yandex_direct_env.py"
        )
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


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise SystemExit(f"Конфиг не найден: {CONFIG_PATH}")
    try:
        import yaml
    except ImportError:
        raise SystemExit(
            "Для YAML нужен PyYAML: pip install pyyaml (или в venv проекта)"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


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
            return json.loads(resp.read().decode())
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
            hint = " Проверь токен и доступ «Яндекс.Директ — API» в OAuth. Новый токен: python3 scripts/setup_yandex_direct_env.py"
        elif code == "58" or "незавершенная регистрация" in msg.lower():
            hint = " Подай заявку: direct.yandex.ru → Настройки → Настройки API → Мои заявки. См. docs/YANDEX_DIRECT_OAUTH_SETUP.md"
        raise RuntimeError(f"{msg} (code={code}){hint}") from e


def write_runbook(config: dict, out_path: str) -> None:
    """Пишет runbook для ручного применения без API."""
    headlines = config.get("headlines") or []
    texts = config.get("texts") or []
    desc = config.get("description") or "Setki21"
    lines = [
        "# Setki21: ручное применение заголовков и текстов в Яндекс.Директе",
        "",
        "Инструкция сгенерирована из `configs/setki21_direct_ads.yaml`. API не используется — одобрение заявки не нужно.",
        "",
        "## Шаги",
        "",
        "1. Открой [direct.yandex.ru](https://direct.yandex.ru), войди в кабинет.",
        "2. Перейди: **Кампании** → нужная кампания → **Группы объявлений** → открой группу.",
        "3. В списке объявлений отредактируй нужные объявления (или создай новые).",
        "4. Для каждого объявления подставь **Заголовок** и **Текст** из таблицы ниже (скопируй без кавычек).",
        "",
        "## Что вставить (по вариантам)",
        "",
        "Рекомендуется: первые 5 объявлений — по одному варианту заголовка и текста из таблицы.",
        "",
        "| № | Заголовок | Текст объявления |",
        "|---|-----------|------------------|",
    ]
    for i in range(max(len(headlines), 1)):
        h = headlines[i] if i < len(headlines) else ""
        t = texts[i % len(texts)] if texts else ""
        # Экранируем | в ячейках
        h_esc = h.replace("|", "\\|")
        t_esc = t.replace("|", "\\|")
        lines.append(f"| {i + 1} | {h_esc} | {t_esc} |")
    lines.extend([
        "",
        "## Все заголовки (для копирования)",
        "",
    ])
    for i, h in enumerate(headlines, 1):
        lines.append(f"{i}. `{h}`")
    lines.extend([
        "",
        "## Все тексты (для копирования)",
        "",
    ])
    for i, t in enumerate(texts, 1):
        lines.append(f"{i}. `{t}`")
    lines.append("")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Применить конфиг Setki21 к объявлениям Директа (API или runbook).")
    parser.add_argument("--runbook", action="store_true", help="Сгенерировать инструкцию для ручного ввода, без API")
    args = parser.parse_args()

    os.chdir(REPO_ROOT)
    config = load_config()

    if args.runbook:
        write_runbook(config, RUNBOOK_PATH)
        print(f"Runbook записан: {RUNBOOK_PATH}")
        print("Открой файл и по шагам введи заголовки и тексты в кабинете Директа. API не нужен.")
        return

    env = load_env()
    token = env.get("YANDEX_DIRECT_TOKEN")
    if not token:
        raise SystemExit("В .env.direct нет YANDEX_DIRECT_TOKEN")

    headlines = config.get("headlines") or []
    texts = config.get("texts") or []
    if not headlines or not texts:
        raise SystemExit(
            "В конфиге configs/setki21_direct_ads.yaml должны быть списки headlines и texts"
        )

    # Кампании
    campaigns_resp = api_post(
        token,
        "campaigns",
        {
            "method": "get",
            "params": {
                "SelectionCriteria": {},
                "FieldNames": ["Id", "Name", "State", "Status", "Type"],
            },
        },
    )
    if "error" in campaigns_resp:
        err = campaigns_resp["error"]
        raise RuntimeError(
            err.get("error_string", str(campaigns_resp))
            + " (code="
            + str(err.get("error_code", ""))
            + ")"
        )
    campaigns = campaigns_resp.get("result", {}).get("Campaigns") or []
    if not campaigns:
        raise SystemExit("В аккаунте Директа нет кампаний")

    campaign_id = config.get("campaign_id")
    if campaign_id is not None:
        if not any(c["Id"] == campaign_id for c in campaigns):
            raise SystemExit(f"Кампания с Id {campaign_id} не найдена")
    else:
        campaign_id = campaigns[0]["Id"]
    print(f"Кампания: Id={campaign_id}")

    # Группы объявлений
    adgroups_resp = api_post(
        token,
        "adgroups",
        {
            "method": "get",
            "params": {
                "SelectionCriteria": {"CampaignIds": [campaign_id]},
                "FieldNames": ["Id", "Name", "CampaignId", "Status"],
            },
        },
    )
    if "error" in adgroups_resp:
        err = adgroups_resp["error"]
        raise RuntimeError(err.get("error_string", str(adgroups_resp)))
    adgroups = adgroups_resp.get("result", {}).get("AdGroups") or []
    adgroup_ids = [g["Id"] for g in adgroups]
    if not adgroup_ids:
        raise SystemExit("В кампании нет групп объявлений")

    # Объявления с полями текста
    ads_resp = api_post(
        token,
        "ads",
        {
            "method": "get",
            "params": {
                "SelectionCriteria": {"AdGroupIds": adgroup_ids},
                "FieldNames": ["Id", "AdGroupId", "State", "Status", "Type"],
                "TextAdFieldNames": ["Title", "Title2", "Text", "Href"],
            },
        },
    )
    if "error" in ads_resp:
        err = ads_resp["error"]
        raise RuntimeError(err.get("error_string", str(ads_resp)))
    ads = ads_resp.get("result", {}).get("Ads") or []
    # Только текстовые и не архивные
    text_ads = [
        a
        for a in ads
        if a.get("Type") == "TEXT_AD" and (a.get("State") or "").upper() != "ARCHIVED"
    ]
    if not text_ads:
        raise SystemExit("Нет подходящих текстовых объявлений для обновления")

    # Обновляем до первых N объявлений (N = min(5, кол-во объявлений))
    n = min(5, len(text_ads), len(headlines))
    to_update = text_ads[:n]
    updates = []
    for i, ad in enumerate(to_update):
        new_title = headlines[i]
        new_text = texts[i % len(texts)]
        updates.append(
            {
                "Id": ad["Id"],
                "TextAd": {"Title": new_title, "Text": new_text},
            }
        )
        print(f"  Ad Id={ad['Id']}: Title={new_title!r}, Text={new_text!r}")

    update_resp = api_post(
        token,
        "ads",
        {
            "method": "update",
            "params": {"Ads": updates},
        },
    )
    if "error" in update_resp:
        err = update_resp["error"]
        raise RuntimeError(err.get("error_string", str(update_resp)))

    result = update_resp.get("result", {}).get("UpdateResults") or []
    ok = sum(1 for r in result if (r.get("Errors") or []) == [])
    print(f"\nОбновлено объявлений: {ok} из {len(updates)}")
    for r in result:
        if r.get("Errors"):
            print(f"  Id {r.get('Id')}: {r['Errors']}")
    if ok < len(updates):
        sys.exit(1)


if __name__ == "__main__":
    main()
