"""Avito session: headed chromium с персистентным профилем и CDP-портом.
Запуск: .venv/bin/python scripts/avito_session.py
Иван логинится в окне; дальше подключаемся через CDP 9222.
"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir="/Users/bikos/.atra-avito-profile",
        headless=False,
        args=["--remote-debugging-port=9222", "--no-first-run", "--no-default-browser-check"],
        viewport={"width": 1400, "height": 900},
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.avito.ru/", wait_until="domcontentloaded")
    print("Окно открыто, профиль: ~/.atra-avito-profile, CDP: 9222", flush=True)
    try:
        while True:
            page.wait_for_timeout(60000)
    except KeyboardInterrupt:
        pass
