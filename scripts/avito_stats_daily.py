"""Ежедневный снимок метрик кабинета Авито Pro → logs/avito_stats_daily.json.

Фиксирует: просмотры сегодня/30д, счётчики карточек, группы качества.
Нужен для оценки динамики после правок (заголовки/фото/SEO).
Запуск: launchd daily 09:50 → com.atra.avito-stats
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "logs" / "avito_stats_daily.json"


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = b.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.avito.ru/profile/pro/items", wait_until="domcontentloaded")
        page.wait_for_timeout(8000)
        body = page.inner_text("body")

        def grab(pattern):
            m = re.search(pattern, body)
            return int(m.group(1).replace("\xa0", "").replace(" ", "")) if m else None

        snap = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "views_today": grab(r"\+?\s*(\d+)\s*\n+\s*просмотр[аов] сегодня"),
            "views_30d": grab(r"([\d\s\xa0]+)\n+\s*за\s*30\s*дней"),
            "active": grab(r"Активные\s*\n?\s*(\d+)"),
            "errors": grab(r"С ошибками\s*\n?\s*(\d+)"),
            "inactive": grab(r"Неопубликованные\s*\n?\s*(\d+)"),
            "fast_sale": grab(r"Можно продать быстрее\s*\n?\s*(\d+)"),
            "growing": grab(r"Растут просмотры(?:\s*в\s*категории)?\s*\n+\s*(\d+)"),
            "weak_attention": grab(r"Плохо привлекают внимание\s*\n?\s*(\d+)"),
            "low_search": grab(r"Низко в поиске\s*\n?\s*(\d+)"),
            "few_contacts": grab(r"Мало контактов\s*\n?\s*(\d+)"),
            "deal_terms": grab(r"Условия сделки\s*\n\s*Есть в\s*(\d+)"),
        }

    data = []
    if OUT.exists():
        try:
            data = json.loads(OUT.read_text())
        except Exception:
            data = []
    # один снимок на день — перезаписываем сегодняшний
    today = snap["date"][:10]
    data = [d for d in data if d["date"][:10] != today]
    data.append(snap)
    OUT.write_text(json.dumps(data[-120:], ensure_ascii=False, indent=1))
    print(json.dumps(snap, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
