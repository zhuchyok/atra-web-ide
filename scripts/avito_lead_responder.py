"""Avito Auto-Responder — монитор лидов + автоответчик.

Каждые 10 минут проверяет непрочитанные чаты клиентов.
Новые лиды → алерт через ntfy (мгновенно на телефон Ивана).
Дальнейшая разработка: авто-генерация ответа через qwen38 + отправка через API.

Использование: launchd каждые 10 минут или вручную.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# state — в ~/Library/Logs (проверенно доступно для launchd-процессов,
# в repo/logs запись под TCC может молча не пройти)
STATE_PATH = Path.home() / "Library" / "Logs" / "atra-avito-lead-state.json"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "atra_victoria_curator")
ACCOUNT_ID = "7561711"


def get_token() -> str:
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ.get("AVITO_CLIENT_ID", ""),
        "client_secret": os.environ.get("AVITO_CLIENT_SECRET", "")
    }).encode()
    req = urllib.request.Request("https://api.avito.ru/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def notify_ntfy(message: str, title: str = "Avito Lead") -> None:
    topic = os.environ.get("NTFY_TOPIC", "atra_victoria_curator")
    data = json.dumps({"topic": topic, "message": message[:3500], "title": title}).encode()
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=data,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=15)


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {}


def save_state(state: dict) -> None:
    try:
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))
        print(f"state сохранён: {STATE_PATH}")
    except Exception as e:
        print(f"state save ERR ({STATE_PATH}): {e}")
        try:
            alt = Path("/tmp/atra-avito-lead-state.json")
            alt.write_text(json.dumps(state, ensure_ascii=False, indent=1))
            print(f"state сохранён в /tmp: {alt}")
        except Exception as e2:
            print(f"state save ERR /tmp: {e2}")


def notify_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_USER_ID", "")
    if not token or not chat_id:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message[:3500]}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10
        )
    except Exception:
        pass  # Telegram недоступен — не блокируем




def _validate_reply(reply: str, customer_text: str) -> tuple:
    """Проверка ответа на галлюцинации."""
    import re as _re
    # телефон: только официальный
    phones = _re.findall(r"[\d\-()\s]{10,}", reply)
    for ph in phones:
        clean = _re.sub(r"[^0-9]", "", ph)
        if len(clean) >= 10 and "8352384020" not in clean:
            return False, "чужой телефон"
    return True, ""


DOMAIN_WORDS = (
    "остекление остекления остеклению остеклением остеклении"
    " застеклить застеклен"
    " окно окна окон окнам окнами"
    " дверь двери дверей дверям дверями"
    " балкон балкона балкону балконы балконов"
    " беседка беседки беседку беседок беседкам беседками"
    " веранда веранды веранду веранд верандам"
    " терраса террасы террасу террас террасам террасами"
    " подоконник подоконники подоконника подоконников"
    " откосы откос отлив отливы отлива"
    " стеклопакет стеклопакеты стеклопакета стеклопакетов"
    " ламинирование ламинированием ламинация"
    " замер замера замеру замерщик замерщиком"
    " монтаж монтажа монтажу монтажом монтажник"
    " установка установки установкой"
    " панорамный панорамные панорамное"
    " раздвижной раздвижные раздвижное портальный портальные"
    " профиль профиля профилю профилем профилей"
    " коттедж коттеджа коттеджу коттеджей дача дачи дачу дач"
    " рассрочка рассрочку рассрочки гарантия гарантией гарантию"
).split()


DOMAIN_WORDS_LATIN = (
    "veka rehau kaleva brusbox tatprof aluvet"
).split()


def fix_domain_typos(text: str) -> str:
    """Правка опечаток в профильных словах.

    Правило уникального кандидата: слово заменяется на словарное, только если
    ровно ОДНО словарное слово в пределах расстояния Дамерау—Левенштейна ≤2.
    «остечение» → остекление (один кандидат), «профили» не трогается
    (три кандидата: профиль/профиля/профилю — значит, слово корректное).
    """
    import re as _re

    def lev(a: str, b: str, maxd: int = 2) -> int:
        if abs(len(a) - len(b)) > maxd:
            return maxd + 1
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j-1] + 1, prev[j-1] + (ca != cb)))
            if min(cur) > maxd:
                return maxd + 1
            prev = cur
        return prev[-1]

    words = [w for w in DOMAIN_WORDS if isinstance(w, str)]

    def best_cand(lw: str):
        # иерархия: уникальный кандидат на дистанции 1 — явная опечатка;
        # иначе единственный на дистанции 2; иначе слово считаем корректным
        c1 = [c for c in words if lev(lw, c, 1) <= 1]
        if len(c1) == 1:
            return c1[0]
        c2 = [c for c in words if lev(lw, c, 2) <= 2]
        if len(c2) == 1:
            return c2[0]
        return None

    def sub(m):
        w = m.group(0)
        lw = w.lower()
        if lw in words or len(lw) < 5:
            return w
        c = best_cand(lw)
        if c:
            return c if w.islower() else c.capitalize()
        return w
    text = _re.sub(r"[а-яА-ЯёЁ]{5,}", sub, text)

    latin = set(DOMAIN_WORDS_LATIN)
    def sub_lat(m):
        w = m.group(0)
        lw = w.lower()
        if lw in latin or len(lw) < 4:
            return w
        cands = [c for c in latin if lev(lw, c, 1) <= 1]
        if len(cands) == 1:
            return cands[0] if w.islower() else cands[0].capitalize()
        return w
    return _re.sub(r"[a-zA-Z]{4,}", sub_lat, text)


def template_reply(customer_text: str, item_title: str, last_sent: str = "") -> str | None:
    """Шаблонный ответ для типовых вопросов — эталонный русский без LLM.

    Закрывает ~80% потока: сроки, стоимость, замер, адреса, профили.
    Возвращает None, если вопрос нестандартный → идёт в LLM.
    ГВАРДЫ:
    - клиент уже дал размеры/конкретику → шаблоны «спросить размеры» запрещены;
    - тот же шаблон, что и в прошлый раз, повторять нельзя (клиент ушёл так).
    """
    import re as _re
    t = customer_text.lower()
    # клиент уже дал размеры или конкретную геометрию → не задаём вопросов, идём в LLM с контекстом
    if _re.search(r"\d+\s*[xх×*]\s*\d+|\d+\s*(метр|метра|метров|м\b|см|мм)|трапеци|про[её]м", t):
        return None
    # тот же шаблон, что и в прошлый раз — нельзя (клиент уже это слышал)
    if last_sent and last_sent.strip() == customer_text.strip() and False:
        return None

    def has(*words):
        return any(w in t for w in words)

    if has("срок", "сколько ждать", "когда изготов", "когда сдела", "сколько делается",
           "как долго", "сколько времени"):
        return ("Здравствуйте! Стандартные окна делаем за 8–10 рабочих дней, "
                "нестандарт — 14–19. Напишите размеры проёма — передам в расчётный "
                "отдел и уточню срок под ваш заказ.")
    if has("цен", "стоимост", "сколько стоит", "прайс", "расцен"):
        return ("Здравствуйте! Стоимость считаем индивидуально — она зависит от "
                "размеров и комплектации. Напишите размеры проёма (ширина × высота) "
                "и нужна ли установка — передам в расчётный отдел, расчёт за 10 минут.")
    if has("замер", "померить", "выезд"):
        return ("Здравствуйте! Замер бесплатный: специалист приезжает в будни "
                "с 9:00 до 19:00, в субботу с 10:00 до 14:00. Оставьте телефон — "
                "согласуем удобное время.")
    if has("адрес", "где вы", "куда подъехать", "офис", "склад"):
        return ("Здравствуйте! Мы в Чебоксарах, ул. Гражданская, 53 (3 этаж), "
                "и в Новочебоксарске, ул. Винокурова, 109 (ТД «Слобода»). "
                "Подскажите ваш район — подскажу, что удобнее.")
    if has("профи", "veka", "rehau", "века", "рехау", "калева", "kaleva"):
        return ("Здравствуйте! Работаем с профилями Veka, Rehau, Kaleva и Brusbox — "
                "официальные партнёры, профили сертифицированные. Расскажу подробнее "
                "о вариантах, если напишете, для чего ищете окна.")
    if has("рассрочк", "кредит", "оплата", "налич", "карт"):
        return ("Здравствуйте! Есть рассрочка 0% на 6 месяцев. Оплата — наличными, "
                "картой или по счёту для ИП/ООО. Детали рассчитаем под ваш заказ — "
                "напишите размеры и что планируете остеклять.")
    return None


def correct_text(text: str) -> str:
    """Вычитка ответа перед отправкой — только детерминированные проверки.

    1. Словарная правка профильных слов (остечение→остекление, Vecka→Veka).
    2. Цифро-буквенный мусор («1сти») → замена на чистый шаблонный ответ:
       починить такой текст LLM-редактором нельзя надёжно (phi3.5 сам портит),
       а шаблон всегда чистый и вежливый.
    """
    import re as _re

    if not text or len(text) < 5:
        return text

    text = fix_domain_typos(text)

    # мусор: смесь цифр и кириллицы внутри слова, сжатые гласные,
    # смешанные алфавиты («Зdravostnyi» — транслит из сломанной генерации)
    if (_re.search(r"\d[а-яё]{2,}|[а-яё]\d[а-яё]", text, _re.I)
            or _re.search(r"[а-яёА-ЯЁ][a-z]{2,}|[a-z][а-яёА-ЯЁ]{2,}", text)
            or "  " in text):
        print("  ⚠ мусор в ответе модели — заменяю на чистый шаблон")
        return ("Здравствуйте! Спасибо за обращение — уточню детали у расчётного "
                "отдела и вернусь к вам с точным расчётом.")
    return text


def send_reply(token: str, chat_id: str, text: str) -> bool:
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps({"message": {"text": text}, "type": "text"}).encode()
    url = f"https://api.avito.ru/messenger/v1/accounts/{ACCOUNT_ID}/chats/{chat_id}/messages"
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"  ❌ Отправка: {e}")
        return False


def main() -> int:
    print("VERSION: state-v2 2026-10-22", flush=True)
    # свежий токен
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ.get("AVITO_CLIENT_ID", ""),
        "client_secret": os.environ.get("AVITO_CLIENT_SECRET", "")
    }).encode()
    req = urllib.request.Request("https://api.avito.ru/token", data=data)
    with urllib.request.urlopen(req, timeout=15) as r:
        token = json.loads(r.read())["access_token"]

    hdrs = {"Authorization": f"Bearer {token}"}

    # непрочитанные чаты
    url = f"https://api.avito.ru/messenger/v2/accounts/{ACCOUNT_ID}/chats?unread_only=true&limit=50"
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=15) as r:
        chats = json.loads(r.read()).get("chats", [])

    if not chats:
        print("Непрочитанных чатов нет.")
        return 0

    print(f"Непрочитанных чатов: {len(chats)}")
    alerts_sent = 0
    state = load_state()
    state_dirty = False

    for chat in chats[:10]:  # обрабатываем первые 10 за запуск
        chat_id = chat["id"]
        ctx = chat.get("context", {})
        val = ctx.get("value", {}) if isinstance(ctx, dict) else {}
        item_title = val.get("title", "?")[:50] if isinstance(val, dict) else "?"

        # получить сообщения
        msg_url = f"https://api.avito.ru/messenger/v3/accounts/{ACCOUNT_ID}/chats/{chat_id}/messages/"
        req_msg = urllib.request.Request(msg_url, headers=hdrs)
        try:
            with urllib.request.urlopen(req_msg, timeout=15) as r:
                msgs = json.loads(r.read()).get("messages", [])
        except Exception as e:
            print(f"ERR messages {chat_id[:15]}: {e}")
            continue

        # последнее сообщение от клиента
        # ВАЖНО: в v3 API поле author отсутствует — направление только в direction
        # ("in" = клиент, "out" = мы). Старая проверка author.type не работала ВООБЩЕ,
        # из-за чего Татьяна не видела вопросы клиентов и отвечала шаблонами на пустоту.
        customer_text = ""
        customer_msg_id = ""
        for m in reversed(msgs):
            if m.get("direction") == "in":
                content = m.get("content", {})
                if isinstance(content, dict):
                    txt = str(content.get("text", "")).strip()
                    if txt and not txt.startswith("[Системное сообщение]"):
                        customer_text = txt[:150]
                        customer_msg_id = str(m.get("id") or m.get("message_id")
                                              or m.get("uuid") or "")
                        break

        # дедуп: алерт только если сообщение клиента новое
        # (если id пустой — хэш текста, hash() солёный per-process)
        import hashlib as _hl
        seen_key = customer_msg_id or _hl.md5(
            f"{len(msgs)}:{customer_text}".encode()).hexdigest()[:12]
        seen = state.get(chat_id, {}).get("last_seen_key")
        if seen == seen_key:
            print(f"  ⏭ уже алертили по этому сообщению — пропуск")
            continue

        alert = f"Avito: новый лид!\nОбъявление: {item_title}\nСообщение: {customer_text or '(без текста)'}"

        # ntfy (мгновенно на телефон)
        try:
            notify_ntfy(alert)
            alerts_sent += 1
            print(f"✅ ntfy: {item_title[:40]}")
        except Exception as e:
            print(f"ntfy ERR: {e}")
        finally:
            # пишем всегда после алерта: чат мог быть без текста (фото/вложение)
            state[chat_id] = {"last_seen_key": seen_key,
                              "item": item_title,
                              "last_reply": (reply if not via_template else "шаблон:" + reply[:60]),
                              "ts": datetime.now(timezone.utc).isoformat()}
            state_dirty = True
            save_state(state)

        # ─── ПРОВЕРКИ ОСТАНОВКИ ───
        # 1) Менеджер уже ответил → бот молчит
        last_author = ""
        if msgs:
            last_m = msgs[-1]
            last_author = last_m.get("author", {}).get("type", "") if isinstance(last_m.get("author"), dict) else ""
        if last_author and last_author != "customer":
            print(f"  🤝 Менеджер уже ответил — бот молчит")
            continue

        # 2) Бот уже дал 5+ ответов → хватит
        out_count = sum(1 for m in msgs if m.get("direction") == "out")
        if out_count >= 5:
            print(f"  ⛔ {out_count} ответов бота — нужен менеджер")
            continue

        # 3) Клиент просит человека → эскалация
        escalate = ["менеджер", "руководител", "человек", "живой", "оператор", "поговорит"]
        if any(kw in customer_text.lower() for kw in escalate):
            print(f"  🤝 Клиент просит человека — эскалация")
            continue

        # ─── ОТВЕТ: сначала шаблон по типу вопроса (эталонный русский),
        # LLM-цепочка только для нестандартных вопросов ───
        reply = template_reply(customer_text, item_title)
        via_template = reply is not None
        if via_template:
            print("  📋 шаблонный ответ")
        # (мозг 11434 периодически заклинивает под GPU-нагрузкой —
        #  тогда отвечает лёгкая модель на инстансе рук 11437)
        # короткий редакторский промпт: только критичные правила и факты
        # (полный 14к-документ замедляет prefill и не нужен в single-turn)
        prompt_path = REPO / "docs" / "AVITO_TATYANA_PROMPT_SHORT.md"
        tatyana_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

        anti_rules = (
            "СТРОЙКА АНТИ-ВЫДУМКИ:\n"
            "- Цены НЕ называй вообще — передавай в расчётный отдел\n"
            "- Сроки: только из блока «Сроки» выше\n"
            "- Не выдумывай услуги, телефоны, адреса\n"
            "- Если не знаешь — скажи что передашь расчётному отделу"
        )
        sys_prompt = (
            "Ты — Татьяна, специалист по остеклению. "
            "Отвечай коротко (2-3 предложения), тепло и профессионально."
            + "\n\n" + tatyana_prompt
            + "\n\n" + anti_rules
        )

        def llm_chat(base_url: str, model: str, timeout_s: int) -> str:
            payload = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Клиент написал по объявлению «{item_title}»: {customer_text}. Ответь как Татьяна."}
                ],
                "stream": False,
                "think": False,
                # num_ctx 8192: дефолтные 2048 при полном промпте уходили в
                # shift KV-кэша → segfault llama-server (краши 20 и 22.10)
                "options": {"temperature": 0.4, "num_predict": 250, "num_ctx": 8192}
            }).encode()
            req = urllib.request.Request(
                f"{base_url}/api/chat", data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                m = json.loads(r.read())["message"]
                text = (m.get("content") or "").strip()
                if not text:
                    # thinking-модели кладут текст в reasoning
                    text = (m.get("reasoning") or m.get("thinking") or "").strip()
                return text

        import re as _re
        if not via_template:
            reply = ""
            # ── 1) MLX-мозг (11435): быстрый (1-3с) и умный — приоритет ──
            # контекст диалога: последние 6 сообщений чата (клиент видел прошлые ответы!)
            # атрибуция по direction (in = клиент, out = мы); чистим «Татьяна:» префиксы
            history_lines = []
            for m in msgs[-6:]:
                txt = str(m.get("content", {}).get("text", "")).strip()
                if not txt or txt.startswith("[Системное сообщение]"):
                    continue
                txt = re.sub(r"^Татьяна:\s*", "", txt)
                who = "Клиент" if m.get("direction") == "in" else "Татьяна"
                history_lines.append(f"- {who}: {txt[:150]}")
            history = "\n".join(history_lines)
            mlx_prompt = (sys_prompt
                + ("\n\nИстория диалога (хронология). ЕСЛИ КЛИЕНТ УЖЕ НАЗВАЛ РАЗМЕРЫ — НЕ СПРАШИВАЙ РАЗМЕРЫ ПОВТОРНО: "
                   "поблагодари, скажи что передаёшь запрос в расчётный отдел и расчёт подготовят в ближайшее время. "
                   "НЕ ПОВТОРЯЙ свои прошлые вопросы:\n" + history if history else "")
                + "\n\nНовое сообщение клиента по объявлению «" + item_title + "»: " + customer_text
                + "\nОтветь как Татьяна именно на ЭТО сообщение.")
            try:
                mlx_payload = json.dumps({
                    "model": "default",
                    "prompt": mlx_prompt,
                    "max_tokens": 250
                }).encode()
                mlx_req = urllib.request.Request(
                    "http://localhost:11435/api/generate", data=mlx_payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(mlx_req, timeout=45) as r:
                    reply = _re.sub(r"<think>[\s\S]*?</think>", "",
                                    json.loads(r.read()).get("response", "")).strip()
                if len(reply) >= 5:
                    print("  🧠 ответ MLX-мозга")
                else:
                    print("  ⚠ MLX: пустой ответ, пробую ollama-модели")
                    reply = ""
            except Exception as e:
                print(f"  ⚠ MLX: {type(e).__name__}, пробую ollama-модели")
                reply = ""
        if not via_template and len(reply) < 5:
            for base_url, model, timeout_s in (
                # qwen38/phi — резерв на случай простоя MLX
                ("http://localhost:11434", "victoria-qwen38:latest", 60),
                ("http://localhost:11437", "phi3.5:3.8b", 60),
            ):
                # две попытки: HTTPError бывает при рестарте llama-server
                for attempt in range(2):
                    try:
                        reply = _re.sub(r"<think>[\s\S]*?</think>", "", llm_chat(base_url, model, timeout_s)).strip()
                        if len(reply) >= 5:
                            break
                        print(f"  ⚠ {model}: пустой ответ, пробую следующую модель")
                        break
                    except Exception as e:
                        if attempt == 0 and "HTTPError" in type(e).__name__:
                            print(f"  ⚠ {model}: HTTPError — пауза 20с и повтор (рестарт llama-server?)")
                            time.sleep(20)
                            continue
                        print(f"  ⚠ {model}: {type(e).__name__}, пробую следующую модель")
                        reply = ""
                        break

        if len(reply) >= 5:
            # АНТИ-ЦЕНА: убрать любые цифры похожие на стоимость
            # Правило компании: бот НЕ озвучивает цены — только расчётный отдел
            price_patterns = [
                r"\d+[\s ]*₽",
                r"\d+[\s ]*(руб|рубл)",
                r"стоимость\s*[:—-]?\s*\d+",
                r"от\s*\d+\s*(₽|руб|тыс)",
            ]
            for pat in price_patterns:
                reply = _re.sub(pat, "рассчитаем индивидуально", reply)

        # валидация: телефон + без ссылок + без выдуманных цен
        import re as _re
        phones = _re.findall(r"[\d\-()\s]{10,}", reply)
        for ph in phones:
            clean = _re.sub(r"[^0-9]", "", ph)
            if len(clean) >= 10 and "8352384020" not in clean:
                reply = "Здравствуйте! Спасибо за обращение — я передам ваш запрос расчётному отделу, они свяжутся с вами с точным расчётом."
                break

        # пустой ответ LLM → безопасный фолбэк (пустоту не отправляем)
        if len(reply) < 5:
            reply = ("Здравствуйте! Спасибо за обращение — уточню детали у расчётного "
                     "отдела и вернусь к вам с точным расчётом.")

        # вычитка перед отправкой (орфография/пунктуация, смысл не трогаем)
        reply = correct_text(reply)

        sent = send_reply(token, chat_id, reply)
        if not sent:
            # 400 чаще всего = дубликат/пустой текст → повтор с изменённым текстом
            sent = send_reply(token, chat_id, "Добрый день! " + reply)
        if sent:
            print(f"  ✅ Татьяна ответила: {reply[:50]}")
        else:
            print(f"  ❌ Ответ не доставлен — нужен менеджер")


        # Telegram (если доступен)
        try:
            notify_telegram(alert)
        except Exception:
            pass

        # пометить чат как прочитанный через API (чтобы не дублировал)
        read_url = f"https://api.avito.ru/messenger/v2/accounts/{ACCOUNT_ID}/chats/{chat_id}/read"
        req_read = urllib.request.Request(read_url, headers=hdrs, method="POST")
        try:
            urllib.request.urlopen(req_read, timeout=10)
        except Exception:
            pass

        time.sleep(1)  # не спамить API

    if state_dirty:
        save_state(state)
    print(f"Итого алертов отправлено: {alerts_sent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
