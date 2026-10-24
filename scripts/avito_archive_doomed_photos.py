"""Архив фото обречённых объявлений Авито (дубли, автоудаление 13.11.2026).

Для каждой карточки из вкладки «С ошибками»: собрать ссылки на все фото
с публичной страницы → скачать → сохранить в ~/Downloads/Авито фото архив/
с дедупликацией по перцептивному хэшу (одинаковые баннеры не плодим).
Манифест: logs/avito_photo_archive_manifest.json

Запуск: .venv/bin/python scripts/avito_archive_doomed_photos.py [лимит]
"""
import io
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image
import imagehash
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = Path.home() / "Downloads" / "Авито фото архив"
MANIFEST = REPO / "logs" / "avito_photo_archive_manifest.json"
REJECTED_URL = 'https://www.avito.ru/profile/pro/items?filters=%7B%22tabs%22%3A%22rejected%22%7D'


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"archived": {}, "hashes": {}, "done_items": []}


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    m = load_manifest()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = b.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 1) собрать ссылки на публичные страницы обречённых
        page.goto(REJECTED_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        cards = {}
        stale = 0
        for rnd in range(80):
            snap = page.evaluate("""() => Array.from(document.querySelectorAll('[data-marker^="item-snippet/"]'))
                .map(e => ({id: e.dataset.marker.replace('item-snippet/',''),
                            href: (e.querySelector('a[href*="/"]')||{}).getAttribute ? (Array.from(e.querySelectorAll('a')).find(a => /\\d{7,}/.test(a.href))||{}).href : null}))""")
            for it in snap:
                if it['href'] and it['id'] not in m['done_items']:
                    cards[it['id']] = it['href']
            if len(cards) == stale:
                # пагинация: «Показать ещё» / следующая страница
                clicked = page.evaluate("""() => {
                    const el = Array.from(document.querySelectorAll('button'))
                        .find(b => (b.innerText||'').trim() === 'Показать ещё'
                             || (b.getAttribute('aria-label')||'') === 'Следующая страница');
                    if (el) { el.click(); return true; }
                    return false;
                }""")
                if not clicked:
                    break
                page.wait_for_timeout(3500)
            stale = len(cards)
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(900)
        todo = [i for i in cards if i not in m['done_items']][:limit]
        print(f"обречённых с фото-страницами: {len(cards)}, к архиву: {len(todo)}")

        # 2) для каждой: публичная страница → все img авито-CDN → скачать
        for n, tid in enumerate(todo):
            try:
                page.goto(cards[tid], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(4000)
                srcs = page.evaluate("""() => {
                    const out = new Set();
                    document.querySelectorAll('img').forEach(im => {
                        const s = im.src || '';
                        if (/img\\.avito\\.st|avito\\.st/.test(s)) out.add(s.split('?')[0]);
                    });
                    // галерея лежит в initial-data JSON
                    const html = document.documentElement.innerHTML;
                    const re = /https:\\/\\/[0-9]+\\.img\\.avito\\.st\\/image\\/[^"\\\\\\s]+/g;
                    (html.match(re) || []).forEach(u => out.add(u));
                    return Array.from(out).slice(0, 15);
                }""")
                saved = 0
                for u in srcs:
                    try:
                        data = page.evaluate("""async (u) => {
                            const r = await fetch(u);
                            const b = await r.blob();
                            return await new Promise(res => { const f = new FileReader();
                                f.onload = () => res(f.result); f.readAsDataURL(b); });
                        }""", u)
                        buf = io.BytesIO(base64_decode(data))
                        h = str(imagehash.phash(Image.open(buf).convert("RGB")))
                        if h in m['hashes']:
                            continue
                        m['hashes'][h] = tid
                        fpath = OUT_DIR / f"{tid}_{saved:02d}.jpg"
                        fpath.write_bytes(buf.getvalue())
                        saved += 1
                    except Exception:
                        continue
                m['done_items'].append(tid)
                m['archived'][tid] = {"url": cards[tid], "photos": saved,
                                      "ts": datetime.now().isoformat()}
                print(f"✅ {tid}: {saved} уникальных фото")
            except Exception as e:
                print(f"ERR {tid}: {str(e)[:70]}")
            MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1))
            time.sleep(1)

    total = sum(v["photos"] for v in m["archived"].values())
    print(f"итого в архиве: {len(m['done_items'])} карточек, {total} фото")
    return 0


def base64_decode(dataurl: str) -> bytes:
    import base64
    return base64.b64decode(dataurl.split(",", 1)[1])


if __name__ == "__main__":
    sys.exit(main())
