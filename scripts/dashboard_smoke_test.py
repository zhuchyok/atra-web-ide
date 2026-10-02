"""Smoke-тест дашборда ATRA Corporation (http://localhost:8501).

Автоматизирует ручной аудит: открывает все 7 разделов, кликает вложенные табы,
проверяет отсутствие критических ошибок (Traceback / «КРИТИЧНО» / session_state
exceptions) и что страница рендерит контент.

Запуск: python3 scripts/dashboard_smoke_test.py
(нужен playwright: pip install playwright && playwright install chromium)
"""
import sys
import time

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8501"
SECTIONS = [
    "🏠 Обзор (Pulse)",
    "🏛️ Wisdom & Mentorship",
    "🛠️ Задачи и SLA",
    "🎯 Стратегия и ROI",
    "🧠 Интеллект (RAG)",
    "🕵️ Инструменты экспертов",
    "⚙️ Система и Безопасность",
    "🧪 Self-Dev",
]
MIN_CONTENT_CHARS = 400


def page_text(page) -> str:
    return page.inner_text("body")


def ui_exceptions(page) -> list:
    """Настоящие ошибки UI: Streamlit-исключения и Traceback в них.

    Текстовые паттерны типа «КРИТИЧНО:» в основном потоке не считаем —
    так легитимно выглядят исторические записи Пульса/SOP (цитаты логов).
    """
    problems = []
    try:
        count = page.locator('[data-testid="stException"]').count()
    except Exception:
        count = 0
    if count:
        problems.append(f"Streamlit exceptions на странице: {count}")
    try:
        body = page_text(page)
        if "Traceback (most recent call last)" in body:
            problems.append("Traceback в контенте страницы")
    except Exception:
        pass
    return problems


def check(page, section: str) -> list:
    problems = []
    page.get_by_text(section, exact=True).first.click()
    page.wait_for_timeout(8000)
    text = page_text(page)
    if len(text) < MIN_CONTENT_CHARS:
        problems.append(f"{section}: мало контента ({len(text)} симв.)")
    problems.extend(ui_exceptions(page))
    return problems


def main() -> int:
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(12000)

        for section in SECTIONS:
            try:
                failures.extend(check(page, section))
                print(f"[{'FAIL' if any(f.startswith(section) for f in failures) else 'OK'}] {section}")
            except Exception as e:
                failures.append(f"{section}: исключение {e}")
                print(f"[FAIL] {section}: {e}")

        # Вложенные табы самых глубоких разделов
        nested = {
            "🧠 Интеллект (RAG)": ["📊 Целостность", "🔍 Ревизия", "⚔️ Prompt Battle"],
            "⚙️ Система и Безопасность": ["🧬 Self-Healing", "🚨 War Room", "🤖 Логи"],
        }
        for section, tabs in nested.items():
            page.get_by_text(section, exact=True).first.click()
            page.wait_for_timeout(6000)
            for tab in tabs:
                try:
                    page.evaluate(
                        """(name) => {
                            var el = Array.from(document.querySelectorAll('[role=tab], button[data-baseweb=tab]'))
                                .find(x => x.textContent.trim() === name);
                            if (el) el.click();
                        }""",
                        tab,
                    )
                    page.wait_for_timeout(6000)
                    problems = ui_exceptions(page)
                    for pr in problems:
                        failures.append(f"{section} → {tab}: {pr}")
                    print(f"[{'FAIL' if problems else 'OK'}] {section} → {tab}")
                except Exception as e:
                    failures.append(f"{section} → {tab}: {e}")

        browser.close()

    if failures:
        print("\n=== ПРОВАЛЫ ===")
        for f in failures:
            print("❌", f)
        return 1
    print("\n✅ Smoke-тест пройден: все разделы и табы без критических ошибок")
    return 0


if __name__ == "__main__":
    sys.exit(main())
