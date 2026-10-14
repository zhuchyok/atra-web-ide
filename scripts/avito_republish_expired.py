"""Репаблиш истёкших объявлений Авито по мере освобождения бесплатных слотов.

Контекст (13.10.2026): бесплатные размещения в категории кончились,
возврат слотов — 06.11.2026. Форма редактирования истёкших молча не
сохраняет (restriction check), «Опубликовать» ведёт на /account/fee.
Этот скрипт ежедневно пробует опубликовать до N карточек из вкладки
«Неопубликованные»; как только слоты снова платные — останавливается.

После успешной публикации дёргает avito_apply_titles.py (лимит 5),
чтобы довесить уникальный заголовок + SEO + НДС уже активной карточке.

Запуск: launchd daily 10:20 → infrastructure/launchd/com.atra.avito-republish.plist
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = REPO / "logs" / "avito_republish_state.json"
INACTIVE_URL = 'https://www.avito.ru/profile/pro/items?filters=%7B%22tabs%22%3A%22inactive%22%7D'
MAX_PER_RUN = 5


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%m-%d %H:%M')}] {msg}", flush=True)


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"published": [], "blocked": []}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))


def main() -> int:
    state = load_state()
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        except Exception as e:
            log(f"CDP недоступен ({e}) — браузер не запущен, выход")
            return 0
        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        page.goto(INACTIVE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)

        ids = page.evaluate(
            """() => Array.from(document.querySelectorAll('[data-marker^="item-snippet/"]'))
                .map(e => e.dataset.marker.replace('item-snippet/',''))"""
        )
        todo = [i for i in ids if i not in state["published"] and i not in state["blocked"]]
        log(f"неопубликованных на вкладке: {len(ids)}, к обработке: {min(len(todo), MAX_PER_RUN)}")

        published_now = 0
        for tid in todo[:MAX_PER_RUN]:
            card = page.locator(f'[data-marker="item-snippet/{tid}"]').first
            try:
                card.scroll_into_view_if_needed()
                card.hover()
                page.wait_for_timeout(500)
                btn = card.locator('[data-marker="publish-action"]')
                if not btn.count():
                    log(f"{tid}: нет кнопки публикации — пропуск")
                    continue
                btn.first.click(timeout=8000)
                page.wait_for_timeout(4000)
                if "/account/fee" in page.url:
                    log(f"{tid}: слоты ещё платные (fee-страница) — стоп на сегодня")
                    page.goto(INACTIVE_URL, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)
                    break
                # дубли-баннер после публикации?
                body = page.inner_text("body")
                if "Товар уже продаётся" in body:
                    log(f"{tid}: Авито считает дублем → в блок-лист")
                    state["blocked"].append(tid)
                    save_state(state)
                    page.goto(INACTIVE_URL, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)
                    continue
                state["published"].append(tid)
                save_state(state)
                published_now += 1
                log(f"✅ {tid} опубликован")
                page.goto(INACTIVE_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
            except Exception as e:
                log(f"{tid}: ERR {type(e).__name__}: {str(e)[:80]}")
                try:
                    page.goto(INACTIVE_URL, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)
                except Exception:
                    pass

        if published_now:
            log(f"опубликовано за прогон: {published_now} — запускаю довеску заголовков")
            subprocess.run(
                [str(REPO / ".venv" / "bin" / "python"),
                 str(REPO / "scripts" / "avito_apply_titles.py"), "5"],
                cwd=str(REPO), timeout=1800,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
