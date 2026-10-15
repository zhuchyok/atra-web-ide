"""Замена «баннерных» первых фото (мужик + логотип + текст) на уникальные
складские снимки. Диагноз 15.10.2026: у большинства карточек группы
«Плохо привлекают внимание» первое фото — один и тот же рекламный баннер;
в выдаче сетка выглядит одинаково → CTR ~0%.

Как работает:
1. Детект: скриншоты превью карточек вкладки «Плохо привлекают внимание»
   → phash-сравнение с эталоном баннера (порог ≤10).
2. Замена: первое фото удаляется, загружается складское фото
   (~/Downloads/Окна завод) с уникальным кропом под карточку
   (сдвиг рамки по счётчику → другой хэш → дубли не провоцируем).
3. Прогресс возобновляемый: logs/avito_banner_progress.json.

Запуск: .venv/bin/python scripts/avito_fix_banner_photos.py [лимит]
"""
import io
import json
import sys
import time
from pathlib import Path

from PIL import Image
import imagehash
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
PHOTOS_DIR = Path.home() / "Downloads" / "Окна завод"
PROGRESS = REPO / "logs" / "avito_banner_progress.json"
WEAK_URL = "https://www.avito.ru/profile/pro/items"
GROUP_TEXT = "Плохо привлекают внимание"


def load_state() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text())
    return {"done": [], "queued": [], "crop_counter": 0}


def unique_crop(src_path: Path, n: int) -> Path:
    """Складское фото с детерминированным кропом по номеру карточки."""
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    dx = int(w * 0.05) * (n % 3)
    dy = int(h * 0.05) * ((n // 3) % 2)
    box = (dx, dy, w - int(w * 0.05) * ((n + 1) % 2), h - dy)
    crop = im.crop(box)
    out = Path(f"/tmp/avito_banner_photo_{n}.jpg")
    crop.save(out, quality=92)
    return out


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    state = load_state()
    photos = sorted(PHOTOS_DIR.glob("*.jpg")) + sorted(PHOTOS_DIR.glob("*.jpeg"))
    if not photos:
        print("Нет складских фото в", PHOTOS_DIR)
        return 1

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = b.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # ── детект баннерных карточек ──
        if not state["queued"]:
            page.goto(WEAK_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(7000)
            try:
                page.get_by_text(GROUP_TEXT).first.click()
                page.wait_for_timeout(5000)
            except Exception:
                print("Не открылась группа качества — Авито отдаёт пустую страницу?")
                return 1
            ids = page.evaluate(
                """() => Array.from(document.querySelectorAll('[data-marker^="item-snippet/"]'))
                    .map(e => e.dataset.marker.replace('item-snippet/',''))"""
            )
            # эталон баннера
            ref = None
            cand = {}
            for tid in ids:
                try:
                    el = page.locator(f'[data-marker="item-snippet/{tid}"] img').first
                    el.scroll_into_view_if_needed()
                    page.wait_for_timeout(700)
                    buf = el.screenshot()
                    im = Image.open(io.BytesIO(buf)).convert("RGB")
                    if ref is None:
                        ref = imagehash.phash(im)
                        cand[tid] = 0
                    else:
                        cand[tid] = ref - imagehash.phash(im)
                except Exception:
                    pass
            state["queued"] = [t for t, d in cand.items() if d <= 10 and t not in state["done"]]
            print(f"детект: {len(cand)} превью, баннерных: {len(state['queued'])}")
        else:
            print(f"в очереди из прошлого запуска: {len(state['queued'])}")

        # ── замена первых фото ──
        for tid in state["queued"][:limit]:
            try:
                page.goto(f"https://www.avito.ru/items/edit/{tid}",
                          wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(6000)
                before = page.evaluate(
                    "document.querySelectorAll('[data-marker*=\"preview(\"]').length")
                if before == 0:
                    print(f"— {tid}: фото не отображаются, пропуск")
                    state["queued"].remove(tid)
                    continue
                page.evaluate(
                    """(() => { var b = document.querySelector('[data-marker*="delete-button"]');
                         if (b) b.click(); })()"""
                )
                time.sleep(2.5)
                src = photos[state["crop_counter"] % len(photos)]
                crop = unique_crop(src, state["crop_counter"])
                state["crop_counter"] += 1
                page.set_input_files('input[data-marker="add/input"]', str(crop))
                time.sleep(6)
                page.locator("button").filter(has_text="Сохранить изменения").first.click()
                time.sleep(6)
                state["queued"].remove(tid)
                state["done"].append(tid)
                print(f"✅ {tid}: баннер → {src.name} (кроп #{state['crop_counter'] - 1})")
            except Exception as e:
                print(f"ERR {tid}: {str(e)[:80]}")
            PROGRESS.write_text(json.dumps(state, ensure_ascii=False, indent=1))
            time.sleep(2)

    print(f"итог: готово {len(state['done'])}, в очереди {len(state['queued'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
