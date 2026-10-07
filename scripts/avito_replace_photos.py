"""Замена главного фото у дубли-карточек Авито на уникальные снимки со склада.

Для каждой карточки из групп дублей: удалить первое фото -> загрузить следующее
из пула фото Ивана (ротация) -> сохранить. Прогресс возобновляемый.
Использование: .venv/bin/python scripts/avito_replace_photos.py [лимит]
"""
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
PHOTOS_DIR = Path.home() / "Downloads" / "Окна завод"
PROGRESS = REPO / "logs" / "avito_photo_progress.json"
DUPS = REPO / "logs" / "avito_exact_dups.json"


def load_state() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text())
    return {"done": [], "photo_counter": 0}


def photos_list() -> list:
    files = sorted(PHOTOS_DIR.glob("*.jpg")) + sorted(PHOTOS_DIR.glob("*.jpeg")) + sorted(PHOTOS_DIR.glob("*.png"))
    return [str(f) for f in files]


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    state = load_state()
    photos = photos_list()
    if not photos:
        print("Нет фото в", PHOTOS_DIR)
        return 1
    dups = json.loads(DUPS.read_text())
    work = []
    for key, cards in dups.items():
        for c in cards:
            if c["id"] not in state["done"]:
                work.append(c)
    if not work:
        print("Все карточки из групп дублей уже обработаны.")
        return 0
    print(f"К обработке: {len(work)} карточек, лимит {limit}")

    from playwright.sync_api import sync_playwright

    done = 0
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        page = browser.contexts[0].pages[0]
        for card in work[:limit]:
            tid = card["id"]
            try:
                page.goto(
                    f"https://www.avito.ru/items/edit/{tid}",
                    wait_until="domcontentloaded",
                )
                time.sleep(6)
                before = page.evaluate(
                    "document.querySelectorAll('[data-marker*=\"preview(\"]').length"
                )
                if before == 0:
                    print(f"— {tid}: фото не отображаются (пропуск)")
                    state["done"].append(tid)
                    continue
                # удалить первое фото
                page.evaluate(
                    """(() => {
                        var b = document.querySelector('[data-marker*="delete-button"]');
                        if (b) b.click();
                    })()"""
                )
                time.sleep(2.5)
                # загрузить уникальное фото (ротация по счётчику)
                photo = photos[state["photo_counter"] % len(photos)]
                state["photo_counter"] += 1
                page.set_input_files(
                    'input[data-marker="add/input"]', photo
                )
                time.sleep(6)
                after = page.evaluate(
                    "document.querySelectorAll('[data-marker*=\"preview(\"]').length"
                )
                # сохранить
                save = page.locator("button").filter(has_text="Сохранить изменения").first
                save.scroll_into_view_if_needed()
                time.sleep(0.5)
                save.click()
                time.sleep(6)
                state["done"].append(tid)
                done += 1
                print(f"✅ {tid}: фото заменено ({photo.split('/')[-1][:25]}), до {before} → превью {after}")
            except Exception as e:
                errors.append(tid)
                print(f"ERR {tid}: {str(e)[:70]}")
            # сохранять прогресс после каждой карточки
            PROGRESS.write_text(json.dumps(state, ensure_ascii=False, indent=1))

    print(f"Итог: {done} обновлено, ошибок {len(errors)}")
    if errors:
        print("Ошибки:", errors[:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
