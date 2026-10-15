"""Avito session: headed chromium с персистентным профилем и CDP-портом.
Запуск: .venv/bin/python scripts/avito_session.py
Иван логинится в окне; дальше подключаемся через CDP 9222.

Живучесть: если вкладку закрыли — открывает новую, а не умирает
(закрытие последней вкладки убивает браузер вместе с логином).
"""
import time

from playwright.sync_api import sync_playwright

CDP_PORT = 9222
START_URL = "https://www.avito.ru/"


def open_page(ctx):
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if page.url in ("about:blank", ""):
            page.goto(START_URL, wait_until="domcontentloaded")
        return page
    except Exception:
        return None


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir="/Users/bikos/.atra-avito-profile",
        headless=False,
        args=[f"--remote-debugging-port={CDP_PORT}", "--no-first-run", "--no-default-browser-check"],
        viewport={"width": 1400, "height": 900},
    )
    page = open_page(ctx)
    print("Окно открыто, профиль: ~/.atra-avito-profile, CDP: 9222", flush=True)
    while True:
        time.sleep(30)
        try:
            if ctx.pages:
                page = ctx.pages[0]
                page.wait_for_timeout(100)  # пинг: жива ли цель
            else:
                print("вкладку закрыли — переоткрываю", flush=True)
                open_page(ctx)
        except Exception:
            try:
                print("цель потеряна — переоткрываю вкладку", flush=True)
                open_page(ctx)
            except Exception:
                pass
