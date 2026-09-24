#!/usr/bin/env python3
"""
Проверка дашборда в браузере (Playwright).
Запуск: дашборд должен быть уже запущен на http://127.0.0.1:8501
  cd knowledge_os/dashboard && ../.venv/bin/python verify_dashboard_ui.py
Или: ./scripts/run_dashboard_ui_verify.sh
"""

import os
import subprocess
import sys
import time

DASH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(DASH))
VENV = os.path.join(ROOT, ".venv")
PY = (
    os.path.join(VENV, "bin", "python")
    if os.path.isfile(os.path.join(VENV, "bin", "python"))
    else sys.executable
)
BASE_URL = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8501")


def ensure_dashboard_running():
    """Проверить, что на 8501 что-то отвечает; при необходимости запустить в фоне."""
    try:
        import urllib.request

        req = urllib.request.Request(BASE_URL, method="GET")
        urllib.request.urlopen(req, timeout=3)
        return True
    except Exception:
        pass
    # Запуск в фоне
    print("Запуск дашборда в фоне...")
    proc = subprocess.Popen(
        [
            PY,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.port=8501",
            "--server.address=127.0.0.1",
            "--server.headless=true",
        ],
        cwd=DASH,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        time.sleep(1)
        try:
            import urllib.request

            urllib.request.urlopen(BASE_URL, timeout=2)
            print("Дашборд поднят.")
            return True
        except Exception:
            continue
    print("Таймаут ожидания дашборда.")
    return False


def run_playwright_checks():
    """Открыть браузер, пройти по разделам, проверить отсутствие ошибок."""
    from playwright.sync_api import sync_playwright

    # Текст для клика: подстрока, по которой в сайдбаре однозначно находится пункт
    sections = [
        ("Обзор (Pulse)", "Обзор"),
        ("Wisdom & Mentorship", "Wisdom"),
        ("Задачи и SLA", "Задачи"),
        ("Стратегия и ROI", "Стратегия"),
        ("Интеллект (RAG)", "Интеллект"),
        ("Инструменты экспертов", "Инструменты"),
        ("Система и Безопасность", "Система"),
    ]
    errors = []
    ok = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_timeout(20000)
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=15000)
            # Дождаться сайдбара
            sidebar = page.locator("[data-testid='stSidebar']").first
            sidebar.wait_for(state="visible", timeout=10000)
            ok.append("Страница загружена, сайдбар есть")

            body = page.locator("body").inner_text()
            if "Критическая ошибка дашборда" in body or "Traceback" in body:
                errors.append("На главной отображается ошибка")
            else:
                ok.append("Главная без критической ошибки")

            for i, (label, short) in enumerate(sections):
                try:
                    # Нижние пункты сайдбара: прокрутить вниз перед поиском
                    if i >= 5:
                        page.evaluate(
                            "const s = document.querySelector('[data-testid=stSidebar]'); if(s) s.scrollTop = s.scrollHeight"
                        )
                        page.wait_for_timeout(500)
                    search = (
                        label.split()[0]
                        if label.startswith("Инстр")
                        else (label.split()[0] if label.startswith("Систем") else label)
                    )
                    safe = search.replace("'", "\\'").replace('"', '\\"')
                    # Сначала пробуем JS-клик по сайдбару (надёжнее для нижних пунктов)
                    clicked = page.evaluate(f"""() => {{
                        const side = document.querySelector('[data-testid=stSidebar]');
                        if (!side) return false;
                        const all = side.querySelectorAll('*');
                        for (const e of all) {{
                            if (e.textContent && e.textContent.includes('{safe}') && e.offsetParent !== null && e.clientHeight > 0) {{
                                e.click();
                                return true;
                            }}
                        }}
                        return false;
                    }}""")
                    if not clicked:
                        opt = sidebar.get_by_text(search, exact=False).first
                        opt.scroll_into_view_if_needed(timeout=5000)
                        opt.click(timeout=8000)
                    page.wait_for_timeout(2500)
                    content = (
                        page.locator("main").inner_text()
                        if page.locator("main").count()
                        else page.locator("body").inner_text()
                    )
                    if "Критическая ошибка" in content or "Traceback" in content:
                        errors.append(f"Раздел «{short}»: ошибка на странице")
                    else:
                        ok.append(f"Раздел «{short}» загружен")
                except Exception as e:
                    errors.append(f"Раздел «{short}»: {e}")
        finally:
            browser.close()

    return ok, errors


def main():
    if not ensure_dashboard_running():
        print("Не удалось запустить/достучаться до дашборда.")
        sys.exit(1)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Установите Playwright: pip install playwright && playwright install chromium")
        sys.exit(1)

    print("Проверка UI дашборда (Playwright)...")
    ok, errors = run_playwright_checks()

    print("--- Результат ---")
    for x in ok:
        print("  OK:", x)
    for x in errors:
        print("  ERR:", x)
    print("---")
    if errors:
        print("Итог: есть ошибки UI")
        sys.exit(1)
    print("Итог: все проверки UI пройдены.")
    sys.exit(0)


if __name__ == "__main__":
    main()
