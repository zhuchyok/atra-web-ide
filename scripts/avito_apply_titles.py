"""Применение карты уникальных заголовков к объявлениям Авито.

За один запуск обрабатывает до 20 карточек (дневной лимит правок).
Прогресс хранит в logs/avito_titles_progress.json — можно перезапускать.
Использование: .venv/bin/python scripts/avito_apply_titles.py [лимит]
"""
import json
import os
import sys
import time
from pathlib import Path

import psycopg2

REPO = Path(__file__).resolve().parent.parent
MAP_PATH = REPO / "logs" / "avito_unique_titles.json"
PROGRESS_PATH = REPO / "logs" / "avito_titles_progress.json"
DB_DSN = os.environ.get(
    "ATRA_DB_DSN", "postgresql://admin:secret@127.0.0.1:6432/knowledge_os"
)  # pragma: allowlist secret
DAILY_LIMIT = int(os.getenv("AVITO_DAILY_LIMIT", "20"))

SEO_TEXTS = {
    "двери": """ПВХ дверь от производителя — самовывоз с завода в Чебоксарах.

Новая дверь ПВХ из профиля VEKA. Подходит для дачи, гаража, хозпостроек, офиса.

• Цена: {price} ₽. Другие размеры и конфигурации — под заказ (изготовление 3–5 дней)
• Самовывоз: завод, г. Чебоксары. Доставка по Чувашии — договоримся
• Гарантия 5 лет по договору, работаем с физлицами и ИП/ООО

Напишите размеры — посчитаем точную цену за 10 минут.

«Столичные Окна» (магазин «Окна напрямую от завода») — на рынке с 2009 года, официальные партнёры Veka, Rehau, Kaleva.""",
    "окна": """Пластиковое окно ПВХ от производителя — самовывоз с завода в Чебоксарах.

Новое окно из профиля VEKA, стеклопакет энергосбережение. Подойдёт для дачи, гаража, балкона, коттеджа.

• Цена: {price} ₽. Размеры и конфигурации — под заказ (изготовление 3–5 дней)
• Доставка по Чувашии или самовывоз с завода
• Гарантия 5 лет. Установка — отдельная услуга, посчитаем по адресу

Напишите размеры окна — рассчитаем за 10 минут.

«Столичные Окна» (магазин «Окна напрямую от завода») — на рынке с 2009 года, официальные партнёры Veka, Rehau, Kaleva.""",
    "беседки": """Остекление беседки или террасы ПВХ — работаем по всей Чувашии.

Тёплый контур защитит от дождя и ветра, продлит сезон на террасе до поздней осени.

• Замер и расчёт — бесплатно, выезд по Чувашии
• Цена: {price} ₽ по проекту; самовывоз комплектующих с завода в Чебоксарах или монтаж под ключ
• Профиль VEKA/Rehau, гарантия 5 лет по договору

Пришлите размеры беседки — посчитаем стоимость за день.

«Столичные Окна» (магазин «Окна напрямую от завода») — на рынке с 2009 года, официальные партнёры Veka, Rehau, Kaleva.""",
    "дома": """Остекление дома или коттеджа ПВХ — от замера до монтажа, Чувашия.

Профиль VEKA/Rehau, ламинирование под цвет фасада, энергосберегающие стеклопакеты.

• Цена: {price} ₽ по проекту; бесплатный замер, смета за 1 день, договор с фиксированной ценой
• Гарантия 5 лет на монтаж, бригады с опытом 10+ лет
• Оплата: наличные, карта, расчётный счёт (ИП/ООО), рассрочка 0% на 6 мес

Напишите площадь остекления — подготовим расчёт.

«Столичные Окна» (магазин «Окна напрямую от завода») — на рынке с 2009 года, официальные партнёры Veka, Rehau, Kaleva.""",
    "панорамные": """Панорамные ПВХ двери и окна от завода — максимум света в доме. Чебоксары и Чувашия.

Двери-порталы, поворотно-сдвижные системы, большие стеклопакеты: современные решения для дома, террасы, веранды, летней кухни.

• Панорамные двери ПВХ — любые размеры под ваш проём
• Тёплые энергосберегающие стеклопакеты
• Изготовление на заводе за 5–10 дней, монтаж бригадами с опытом 10+ лет
• Гарантия 5 лет по договору

**Цены:** панорамные двери — от 15 300 ₽, точный расчёт — по вашим размерам бесплатно.

**Как заказать:** напишите размеры проёма в сообщении — подготовим варианты и расчёт за день. Замер по Чувашии — бесплатно.

«Столичные Окна» (магазин «Окна напрямую от завода») — партнёры Veka, Rehau, Kaleva.""",
}


def load_progress() -> dict:
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text())
    return {"done": []}


def save_progress(state: dict) -> None:
    PROGRESS_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))


def load_map() -> list:
    data = json.loads(MAP_PATH.read_text())
    done = set(load_progress().get("done", []))
    return [r for r in data if r["id"] not in done]


def group_for(title: str) -> str:
    t = title.lower()
    if "панорам" in t:
        return "панорамные"
    if "двер" in t:
        return "двери"
    if "беседк" in t or "террас" in t or "веранд" in t:
        return "беседки"
    if "коттедж" in t or "дом" in t or "дач" in t or "остеклен" in t:
        return "дома"
    return "окна"


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else DAILY_LIMIT
    from playwright.sync_api import sync_playwright

    pending = load_map()
    if not pending:
        print("Карта пуста — все заголовки применены.")
        return 0

    state = load_progress()
    processed = 0
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        page = browser.contexts[0].pages[0]
        for row in pending[:limit]:
            tid, new_title = row["id"], row["new"]
            group = group_for(new_title)
            try:
                page.goto(
                    f"https://www.avito.ru/items/edit/{tid}",
                    wait_until="domcontentloaded",
                )
                time.sleep(6)
                # заголовок — точный селектор
                inp = page.locator('input[name="title"]')
                inp.fill(new_title)
                time.sleep(1)
                # цена из формы — числовое поле
                price = page.evaluate(
                    """(() => {
                        var el = Array.from(document.querySelectorAll('input')).find(
                            i => i.offsetParent !== null && /^\\d{4,7}$/.test(i.value || '')
                        );
                        return el ? el.value : null;
                    })()"""
                )
                # описание: очистить и вставить SEO-текст группы
                ed = page.locator("div.public-DraftEditor-content").first
                ed.click()
                time.sleep(0.4)
                page.keyboard.press("Meta+a")
                page.keyboard.press("Backspace")
                time.sleep(0.4)
                text = SEO_TEXTS[group].format(price=price or "по запросу")
                page.keyboard.insert_text(text)
                time.sleep(2)
                # НДС 5%, если селект на форме
                page.evaluate(
                    """(() => {
                        var sel = document.querySelector('select[name="params[120415]"]');
                        if (!sel) return;
                        var opt = Array.from(sel.options).find(o => o.textContent.trim() === '5');
                        if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change', {bubbles: true})); }
                    })()"""
                )
                time.sleep(1)
                save = page.locator("button").filter(has_text="Сохранить изменения").first
                save.scroll_into_view_if_needed()
                save.click()
                time.sleep(6)
                # верификация: заголовок в форме после сохранения
                check = page.evaluate(
                    """(t) => {
                        var el = Array.from(document.querySelectorAll('input')).find(
                            i => i.offsetParent !== null && (i.value||'') === t
                        );
                        return !!el;
                    }""",
                    new_title,
                )
                if check:
                    state["done"].append(tid)
                    save_progress(state)
                    processed += 1
                    print(f"✅ {new_title[:55]}")
                else:
                    print(f"⏳ не сохранилось: {tid}")
            except Exception as e:
                print(f"ERR {tid}: {str(e)[:70]}")
            time.sleep(2)
    print(f"Итог запуска: обработано {processed}, в карте осталось {len(pending) - processed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
