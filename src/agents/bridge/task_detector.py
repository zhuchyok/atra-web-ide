"""
Детектор типа задачи для маршрутизации запросов Victoria.
Определяет: simple_chat (приветствия, простые вопросы) → быстрый путь без Enhanced;
veronica / department_heads / enhanced — для выбора обработчика.

Мировая практика (docs/VERONICA_REAL_ROLE.md): Veronica — «руки», не «решатель».
При PREFER_EXPERTS_FIRST=true (по умолчанию) в Veronica идут только простые
одношаговые запросы (покажи файлы, выведи список); остальные execution → enhanced,
чтобы Victoria сначала задействовала экспертов (85 в БД).
"""

import os
import re
from typing import Optional

# Curator/chat fixed-token probes ("Reply YES only", "Fact: … Reply YES").
# Must match mid-string too: pair goals put YES after tip text that often
# contains incidental FACT_SEEKING_MARKERS (inflight/stale/ttc/11437).
_FIXED_TOKEN_REPLY_PROBE_RE = re.compile(
    r"(?:^|[\s.!?\"'(\[\-/:])(reply|answer|ответь|ответьте)\s+(yes|no|да|нет)\b",
    re.IGNORECASE,
)


def is_fixed_token_reply_probe(goal: str) -> bool:
    """True when the ask is a fixed YES/NO token, not a live metrics probe."""
    g = (goal or "").strip()
    return bool(g and _FIXED_TOKEN_REPLY_PROBE_RE.search(g))


# Brain canary harness (scripts/brain_canary_battle.py) embeds BCANARY-<id>-<hex>.
_BCANARY_TOKEN_RE = re.compile(r"BCANARY-[A-Za-z0-9_-]+", re.IGNORECASE)


def extract_brain_canary_token(goal: str) -> Optional[str]:
    """Return first BCANARY-* token from goal, if any."""
    m = _BCANARY_TOKEN_RE.search(goal or "")
    return m.group(0) if m else None


def is_brain_canary_probe(goal: str) -> bool:
    """Harness probe: measure brain answer, not orchestrator async handoff."""
    return extract_brain_canary_token(goal) is not None


def prefix_brain_canary_token(goal: str, text: str) -> str:
    """Ensure canary answers echo the harness nonce (first line)."""
    tok = extract_brain_canary_token(goal)
    body = (text or "").strip()
    if not tok or not body:
        return body
    if tok.lower() in body.lower():
        return body
    return f"{tok}\n{body}"


def is_destructive_infra_wipe(goal: str) -> bool:
    """True for wipe-all docker volumes / nuke-without-backup style asks."""
    g = (goal or "").lower()
    if not g:
        return False
    wipe_verbs = (
        "удал",
        "снес",
        "wipe",
        "уничтож",
        "purge",
        "rm -rf",
        "volume rm",
        "down -v",
    )
    volume_marks = (
        "docker volume",
        "volumes",
        "том",
        "volume ",
    )
    nuke_context = (
        "без бэкап",
        "без backup",
        "с нуля",
        "все volume",
        "все docker",
        "всех volume",
        "project atra",
        "проекта atra",
    )
    has_wipe = any(v in g for v in wipe_verbs)
    has_vol = any(v in g for v in volume_marks)
    has_nuke = any(v in g for v in nuke_context)
    return bool(has_wipe and has_vol and (has_nuke or "все" in g))


def is_secret_exfil_ask(goal: str) -> bool:
    """True when user asks to paste secrets from .env / passwords into chat."""
    g = (goal or "").lower()
    if not g:
        return False
    secret_marks = (
        ".env",
        "postgres_password",
        "парол",
        "password",
        "secret",
        "токен бота",
        "api key",
        "apikey",
    )
    ask_marks = ("покажи", "дай ", "вывед", "в чат", "целиком", "paste", "show me")
    return any(s in g for s in secret_marks) and any(a in g for a in ask_marks)


def is_cloud_bypass_ask(goal: str) -> bool:
    """True when user asks to bypass STRICT_LOCAL / send goals to cloud APIs."""
    g = (goal or "").lower()
    if not g:
        return False
    bypass = (
        "обойд",
        "bypass",
        "вместо 11434",
        "вместо локальн",
        "cloud api",
        "облачн",
        "openai.com",
        "strict_local",
    )
    send = ("отправ", "ходи в", "перейди на cloud", "use cloud")
    return any(b in g for b in bypass) and (
        any(s in g for s in send) or "облач" in g or "cloud" in g
    )


def safety_refuse_answer(goal: str) -> Optional[str]:
    """Deterministic safety refusals (before LLM / canary direct)."""
    if is_destructive_infra_wipe(goal):
        return (
            "Отказ: не удаляю docker volumes и не сношу проект без явного "
            "подтверждения куратора и бэкапа. Это разрушительная операция — "
            "не буду выполнять."
        )
    if is_secret_exfil_ask(goal):
        return (
            "Отказ: не показываю пароли и секреты из `.env` в чате. "
            "Используйте переменные окружения / secret manager."
        )
    if is_cloud_bypass_ask(goal):
        return (
            "Отказ: не обхожу локальный контур и не отправляю goal в облачный API. "
            "Работаем STRICT_LOCAL (11434/8010)."
        )
    return None


def fixed_token_reply_answer(goal: str) -> Optional[str]:
    """Deterministic YES/NO for fixed-token probes (never a metrics dump)."""
    g = (goal or "").strip()
    # Multi-choice ("yes/no", "yes or no", "unset") is a real question — not echo YES.
    if re.search(r"\byes\s*/\s*no\b|\bда\s*/\s*нет\b|\byes\s+or\s+no\b|\bunset\b", g, re.I):
        return None
    m = _FIXED_TOKEN_REPLY_PROBE_RE.search(g)
    if not m:
        return None
    token = (m.group(2) or "").lower()
    if token in ("yes", "да"):
        return "YES"
    if token in ("no", "нет"):
        return "NO"
    return None


# Ключевые слова по типам (порядок проверки важен)
SIMPLE_CHAT_KEYWORDS = [
    "привет",
    "здравствуй",
    "приветствую",
    "добрый день",
    "добрый вечер",
    "доброе утро",
    "как дела",
    "что нового",
    "расскажи о себе",
    "кто ты",
    "чем занимаешься",
    "спасибо",
    "пожалуйста",
    "пока",
    "до свидания",
    "удачи",
    "хорошего дня",
    "приветствую",
    "здорово",
    "ок",
    "понятно",
    "ясно",
]

# Простые одношаговые запросы — реальная роль Veronica (руки): только показать/вывести/прочитать
VERONICA_SIMPLE_KEYWORDS = [
    "покажи файлы",
    "выведи список файлов",
    "список файлов",
    "покажи список",
    "прочитай файл",
    "покажи файл",
    "содержимое файла",
    "выведи содержимое",
    "сделай скриншот",
    "проверь как выглядит",
    "нажми на",
    "открой страницу",
    "визуальная проверка",
    "проверь ui",
    "проверь ux",
]

VERONICA_KEYWORDS = [
    "выполни",
    "сделай",
    "напиши код",
    "исправь код",
    "исправь",
    "напиши функцию",
    "запусти",
    "протестируй",
    "проверь код",
    "проверь",
    "собери",
    "установи",
    "настрой",
    "подготовь",
    "создай файл",
    "удали файл",
    "переименуй",
    "перемести файл",
    "покажи файлы",
    "выведи список файлов",
]

DEPARTMENT_HEADS_KEYWORDS = [
    "проанализируй",
    "разработай стратегию",
    "оптимизируй",
    "спроектируй",
    "планируй",
    "исследуй",
    "изучи",
    "оцени",
    "предложи решение",
    "найди проблему",
    "сравни",
    "обобщи",
    "систематизируй",
]

# Запросы куратора, которые должны идти в Enhanced (RAG/эталоны), не в Veronica
CURATOR_STANDARD_KEYWORDS = [
    "статус проекта",
    "какой статус",
    "дашборд",
    "что умеешь",
    "что ты умеешь",
    "status project",
    "project status",
    "dashboard",
    "what can you do",
]


# Исполнительные задачи куратора/Victoria: аудит, дашборд, правки — Enhanced/tools, не in-process Swarm LLM
OPERATIONAL_EXECUTION_MARKERS = (
    "аудит",
    "ре-аудит",
    "deep-analysis",
    "deep analysis",
    "дашборд",
    "dashboard",
    "исправ",
    "проверь",
    "sql",
    "миграц",
    "контейнер",
    "quality gate",
    "оркестрац",
    "эксперт",
)

OPERATIONAL_NO_CLARIFY_MARKERS = (
    "без уточнений",
    "не задавай уточняющие",
    "не задавай встречные вопросы",
    "начинай выполнение сразу",
    "сразу выполняй",
)


def is_operational_execution_goal(goal: str) -> bool:
    """
    Задачи с явным исполнением (аудит дашборда, правки, сверка с БД).
    Маршрут: Victoria Enhanced + инструменты; запрет in-process Swarm (3× ai_core).
    """
    if not (goal or "").strip():
        return False
    g = (goal or "").lower().strip()
    if any(m in g for m in OPERATIONAL_NO_CLARIFY_MARKERS) and any(
        m in g for m in OPERATIONAL_EXECUTION_MARKERS
    ):
        return True
    if "критическая задача" in g and any(m in g for m in ("дашборд", "dashboard", "аудит")):
        return True
    if ("deep-analysis" in g or "deep analysis" in g) and "дашборд" in g:
        return True
    return False


FACT_SEEKING_MARKERS = (
    "порт",
    "ports",
    " health",
    "health ",
    "/health",
    "статус проекта",
    "статус по проекту",
    "статус системы",
    "очеред",
    "pending",
    "in_progress",
    "knowledge_nodes",
    "сколько узл",
    "сколько знан",
    "дашборд",
    "dashboard",
    "localhost",
    "8010",
    "8011",
    "3005",
    "8501",
    "11434",
    "11436",
    "11437",
    "/api/ps",
    "слот",
    "сканер",
    "log-scanner",
    "log_scanner",
    "по фактам",
    "живьём",
    "живьем",
    "open webui",
    "openwebui",
    "veronica",
    "victoria agent",
    "throughput",
    "пропуск",
    "stale",
    "застряв",
    "error rate",
    "contract",
    "контракт",
    "1h",
    "1ч",
    "24h",
    "24ч",
    "сутк",
    "churn",
    "/metrics",
    "metrics",
    "p95",
    "p50",
    "ttc",
    "time_to_completed",
    "time-to-completed",
    "duration_seconds",
    "inflight",
    "victoria_async",
    "atra_allow_git",
    "printenv",
)

FACT_PLANNING_EXCLUDE_MARKERS = (
    "сделай план",
    "дай план",
    "план фикса",
    "план исправ",
    "в 5 шагах",
    "в 3 шагах",
    "пошагово",
    "как исправ",
    "как проверить",
    "как починить",
    "mitigation plan",
    "fix plan",
    "step-by-step",
)


CANONICAL_ATRA_PORTS = (
    ("victoria", "8010"),
    ("veronica", "8011"),
    ("open webui", "3005"),
    ("webui", "3005"),
    ("dashboard", "8501"),
    ("дашборд", "8501"),
)


def goal_wants_scanner(goal: str) -> bool:
    g = (goal or "").lower()
    return any(x in g for x in ("сканер", "log-scanner", "log_scanner", "class=human"))


def goal_wants_ollama_slots(goal: str) -> bool:
    """Live /api/ps, not the 8010/8011/3005 registry."""
    g = (goal or "").lower()
    return any(x in g for x in ("11434", "11436", "11437", "/api/ps", "слот", "ollama"))


_PROCESS_ENV_FACT_KEYS = (
    "ATRA_ALLOW_GIT_MUTATE",
    "ATRA_ALLOW_GIT_PUSH",
    "VICTORIA_MODEL",
    "VICTORIA_PLANNER_MODEL",
    "VICTORIA_BRAIN_MODEL",
    "VICTORIA_MLX_BRAIN",
    "PROJECT_ROOT",
)


def goal_wants_process_env(goal: str) -> bool:
    """Ask about process env Victoria can read via os.environ (no docker needed)."""
    g = (goal or "").lower()
    if not g:
        return False
    if "atra_allow_git_mutate" in g or "atra_allow_git_push" in g:
        return True
    # Bare atra_allow_git only — not atra_allow_git_pull (false-proof sibling keys).
    if re.search(r"\batra_allow_git\b", g) and not re.search(
        r"atra_allow_git_(?!mutate\b|push\b)\w+", g
    ):
        return True
    if "project_root" in g and any(x in g for x in ("printenv", "env ", "getenv", "os.environ")):
        return True
    if "printenv" in g and any(k.lower() in g for k in _PROCESS_ENV_FACT_KEYS):
        return True
    if "victoria_model" in g and any(
        x in g for x in ("printenv", "env", "пин", "pin", "день", "day")
    ):
        return True
    return False


def _env_keys_mentioned_in_goal(goal: str) -> list[str]:
    """Allowlisted KEY=… mentions in goal order (no silent drop of asked keys)."""
    g = goal or ""
    gl = g.lower()
    keys: list[str] = []
    seen: set[str] = set()
    # Prefer explicit allowlisted names as written / lowercased in the goal.
    for k in _PROCESS_ENV_FACT_KEYS:
        if k.lower() in gl and k not in seen:
            seen.add(k)
            keys.append(k)
    if keys:
        return keys
    # Unknown atra_allow_git_* (e.g. _PULL) — never invent MUTATE/PUSH.
    if re.search(r"atra_allow_git_(?!mutate\b|push\b)\w+", gl):
        return []
    # Heuristic fallbacks when names are paraphrased.
    if "atra_allow_git_mutate" in gl or ("mutate" in gl and "atra_allow" in gl):
        keys.append("ATRA_ALLOW_GIT_MUTATE")
    if "atra_allow_git_push" in gl or ("push" in gl and "atra_allow" in gl):
        keys.append("ATRA_ALLOW_GIT_PUSH")
    if re.search(r"\batra_allow_git\b", gl) and not keys:
        keys.extend(["ATRA_ALLOW_GIT_MUTATE", "ATRA_ALLOW_GIT_PUSH"])
    if "victoria_planner_model" in gl:
        keys.append("VICTORIA_PLANNER_MODEL")
    elif "victoria_model" in gl or "victoria_brain_model" in gl:
        keys.append("VICTORIA_MODEL")
    if "printenv" in gl and not keys:
        keys.extend(["ATRA_ALLOW_GIT_MUTATE", "ATRA_ALLOW_GIT_PUSH", "VICTORIA_MODEL"])
    ordered: list[str] = []
    seen2: set[str] = set()
    for k in keys:
        if k not in seen2:
            seen2.add(k)
            ordered.append(k)
    return ordered


def process_env_fact_answer(goal: str) -> Optional[str]:
    """Deterministic UNSET/value for every allowlisted key mentioned (no false single-key)."""
    if not goal_wants_process_env(goal):
        return None
    ordered = _env_keys_mentioned_in_goal(goal)
    if not ordered:
        return None
    bits: list[str] = []
    for key in ordered:
        raw = os.environ.get(key)
        if raw is None or raw == "":
            bits.append(f"{key}=UNSET")
        else:
            bits.append(f"{key}={raw}")
    return " ".join(bits) if bits else None


_FIRST_LINE_GOAL_RE = re.compile(
    r"(?:read\s+file|прочитай(?:те)?\s+файл|первая\s+строка|first\s+line)"
    r".{0,80}?"
    r"(?P<path>(?:docs|src|knowledge_os|configs|scripts|tests|/Users|/app|/workspace)[^\s\"']+\.[A-Za-z0-9]+)",
    re.IGNORECASE | re.DOTALL,
)


def _workspace_roots() -> list[str]:
    roots: list[str] = []
    for cand in (
        os.getcwd(),
        os.getenv("PROJECT_ROOT") or "",
        "/workspace/atra-web-ide",
        "/app",
    ):
        if cand and cand not in roots:
            roots.append(cand)
    return roots


def resolve_repo_file_path(path: str) -> Optional[str]:
    """Absolute path if file exists under known workspace roots."""
    raw = (path or "").rstrip(".,;:)?!\"'")
    if not raw:
        return None
    if os.path.isfile(raw):
        return os.path.abspath(raw)
    if os.path.isabs(raw):
        return None
    for cand in _workspace_roots():
        joined = os.path.join(cand, raw)
        if os.path.isfile(joined):
            return joined
        # Curator shorthand: tests/foo.py → knowledge_os/tests/foo.py
        if raw.startswith("tests/"):
            under_kos = os.path.join(cand, "knowledge_os", raw)
            if os.path.isfile(under_kos):
                return under_kos
    return None


def resolve_repo_dir_path(path: str) -> Optional[str]:
    """Absolute path if directory exists under known workspace roots."""
    raw = (path or "").rstrip(".,;:)?!\"'/")
    if not raw:
        return None
    if os.path.isdir(raw):
        return os.path.abspath(raw)
    if os.path.isabs(raw):
        return None
    for cand in _workspace_roots():
        joined = os.path.join(cand, raw)
        if os.path.isdir(joined):
            return joined
        if raw.startswith("tests/"):
            under_kos = os.path.join(cand, "knowledge_os", raw)
            if os.path.isdir(under_kos):
                return under_kos
    return None


def first_line_file_answer(goal: str) -> Optional[str]:
    """Deterministic first-line read (curator pairs; blocks LLM/PgBouncer drift)."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    # ≥2 paths → multi_first_line_answer (avoid false single-file quote).
    if len(_repo_paths_in_goal(g)) >= 2:
        return None
    if not any(
        x in gl
        for x in (
            "first line",
            "первая строка",
            "read file",
            "прочитай файл",
            "прочитайте файл",
            "top of",
            "beginning of",
            "opening of",
            "начало ",
        )
    ):
        return None
    if not any(
        x in gl
        for x in (
            "first line",
            "первая строка",
            "only the first",
            "top of",
            "beginning of",
            "opening of",
            "начало ",
        )
    ):
        if not re.search(r"report\s+only\s+the\s+first\s+line|только\s+перв", gl):
            return None
    # «top/opening … five lines» / last+first mixes → line_range (no single-line false-proof).
    if any(x in gl for x in ("last ", "tail ", "bottom ", "final ", "последн", "хвост")):
        return None
    if re.search(
        rf"(?:top|opening|начало).{{0,40}}(?:{_WORD_N_ALT}|few)\s+(?:lines?|строк)",
        gl,
        re.IGNORECASE,
    ) or re.search(
        rf"(?:first|top|opening|первые|первых)\s+(?:{_WORD_N_ALT}|few)\s+(?:lines?|строк)",
        gl,
        re.IGNORECASE,
    ):
        if not re.search(r"\bfirst\s+line\b|первая\s+строка|only\s+the\s+first\s+line", gl):
            return None
    m = _FIRST_LINE_GOAL_RE.search(g)
    if not m and any(x in gl for x in ("top of", "beginning of", "opening of", "начало ")):
        paths = _repo_paths_in_goal(g)
        if len(paths) != 1:
            return None
        resolved = resolve_repo_file_path(paths[0])
        if not resolved:
            return None
        try:
            with open(resolved, encoding="utf-8", errors="replace") as fh:
                return fh.readline().rstrip("\n\r")
        except OSError:
            return None
    if not m:
        return None
    # fall through with m set from _FIRST_LINE_GOAL_RE
    resolved = resolve_repo_file_path(m.group("path"))
    if not resolved:
        return None
    try:
        with open(resolved, encoding="utf-8", errors="replace") as fh:
            return fh.readline().rstrip("\n\r")
    except OSError:
        return None


def multi_first_line_answer(goal: str) -> Optional[str]:
    """First line from 2–3 repo paths — blocks LLM invent / single-file false proof."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    paths = _repo_paths_in_goal(g)
    if len(paths) < 2:
        return None
    if not any(
        x in gl
        for x in (
            "first line",
            "первая строка",
            "первые строк",
            "only the first",
            "только перв",
            "top of",
            "beginning of",
            "opening of",
            "начало ",
        )
    ):
        return None
    # Mixed first+last across paths → leave to line_range / multi_nth (no B:1 false-proof).
    if any(
        x in gl
        for x in ("last ", "tail ", "bottom ", "final ", "последн", "хвост", "trailing", "ending")
    ):
        return None
    # Mixed "first line of A and line 5 of B" → leave to multi_nth (no B:1 false-proof).
    if re.search(
        r"(?:line\s*(?:number\s*)?|строк[аиуе]?\s*(?:номер\s*)?)([2-9]\d*|[1-9]\d+)",
        gl,
    ):
        return None
    hits: list[str] = []
    for rel in paths[:3]:
        resolved = resolve_repo_file_path(rel)
        if not resolved:
            hits.append(f"{rel}:1: missing")
            continue
        try:
            with open(resolved, encoding="utf-8", errors="replace") as fh:
                hits.append(f"{rel}:1:{fh.readline().rstrip(chr(10) + chr(13))}")
        except OSError:
            hits.append(f"{rel}:1: read_error")
    if not hits:
        return None
    return "Multi-first-line (no LLM):\n" + "\n".join(hits)


_NTH_LINE_GOAL_RE = re.compile(
    r"(?:line\s*(?:number\s*)?(?P<n1>\d+)|строк[аиуе]?\s*(?:номер\s*)?(?P<n2>\d+)|(?P<n3>\d+)\s*-\s*based)"
    r".{0,120}?"
    r"(?P<path>(?:docs|src|knowledge_os|configs|scripts|tests|/Users|/app|/workspace)[^\s\"']+\.[A-Za-z0-9]+)"
    r"|"
    r"(?P<path2>(?:docs|src|knowledge_os|configs|scripts|tests|/Users|/app|/workspace)[^\s\"']+\.[A-Za-z0-9]+)"
    r".{0,120}?"
    r"(?:line\s*(?:number\s*)?(?P<n4>\d+)|строк[аиуе]?\s*(?:номер\s*)?(?P<n5>\d+))",
    re.IGNORECASE | re.DOTALL,
)


def nth_line_file_answer(goal: str) -> Optional[str]:
    """Deterministic Nth line (1-based) for curator pairs outside first-line probe."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    # Do not steal first-line probes.
    if first_line_file_answer(g) is not None:
        return None
    # Blame / windowed range asks → git_blame / line_range (no single-line false-proof).
    if any(
        x in gl
        for x in (
            "blame",
            "annotate",
            "who wrote",
            "who last touched",
            "next ",
            "after line",
            "around",
            "±",
            "before and after",
            "surrounding",
            "of context",
        )
    ):
        return None
    # ≥2 paths → multi_nth_line_answer
    if len(_repo_paths_in_goal(g)) >= 2:
        return None
    if not any(
        x in gl for x in ("line ", "line number", "строк", "read_file", "read file", "прочитай")
    ):
        return None
    m = _NTH_LINE_GOAL_RE.search(g)
    if not m:
        return None
    n_raw = m.group("n1") or m.group("n2") or m.group("n3") or m.group("n4") or m.group("n5")
    path = m.group("path") or m.group("path2")
    if not n_raw or not path:
        return None
    n = int(n_raw)
    if n < 1 or n > 500:
        return None
    # first line already handled elsewhere
    if n == 1:
        return None
    resolved = resolve_repo_file_path(path)
    if not resolved:
        return None
    try:
        with open(resolved, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                if i == n:
                    return line.rstrip("\n\r")
    except OSError:
        return None
    return None


_LINE_N_PATH_PAIR_RE = re.compile(
    r"(?:line\s*(?:number\s*)?|quote\s*line\s*|строк[аиуе]?\s*(?:номер\s*)?)(?P<n>\d+)\s+"
    r"(?:of\s+|в\s+|из\s+)?"
    r"(?P<path>(?:docs|src|knowledge_os|configs|scripts|tests|/Users|/app|/workspace)[^\s\"']+\.[A-Za-z0-9]+)",
    re.IGNORECASE,
)


def _read_repo_line(rel: str, n: int) -> str:
    resolved = resolve_repo_file_path(rel)
    if not resolved:
        return f"{rel}:{n}: missing"
    try:
        with open(resolved, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                if i == n:
                    return f"{rel}:{n}:{line.rstrip(chr(10) + chr(13))}"
    except OSError:
        return f"{rel}:{n}: read_error"
    return f"{rel}:{n}: short_file"


def multi_nth_line_answer(goal: str) -> Optional[str]:
    """Quote line N from 2–3 paths (same N or per-path N) — blocks false-proof invent."""
    g = (goal or "").strip()
    if not g:
        return None
    if multi_first_line_answer(g) is not None or first_line_file_answer(g) is not None:
        return None
    gl = g.lower()
    paths = _repo_paths_in_goal(g)
    if len(paths) < 2:
        return None
    if not any(
        x in gl
        for x in (
            "line ",
            "line number",
            "quote line",
            "строк",
            "read_file",
            "read file",
            "прочитай",
        )
    ):
        return None
    # Per-path N: "line 3 of A and line 5 of B" (avoids quoting B:3 when asked B:5).
    pairs: list[tuple[str, int]] = []
    seen: set[str] = set()
    for m in _LINE_N_PATH_PAIR_RE.finditer(g):
        rel, n = m.group("path"), int(m.group("n"))
        if rel in seen or n < 1 or n > 500:
            continue
        seen.add(rel)
        pairs.append((rel, n))
    # path-before-N: "…task_detector.py line 5 and …cursor_method.md line 3"
    for m in re.finditer(
        r"(?P<path>(?:docs|src|knowledge_os|configs|scripts|tests|/Users|/app|/workspace)[^\s\"']+\.[A-Za-z0-9]+)"
        r"\s+(?:line\s*(?:number\s*)?|quote\s*line\s*|строк[аиуе]?\s*(?:номер\s*)?)(?P<n>\d+)",
        g,
        re.IGNORECASE,
    ):
        rel, n = m.group("path"), int(m.group("n"))
        if rel in seen or n < 1 or n > 500:
            continue
        seen.add(rel)
        pairs.append((rel, n))
    if len(pairs) >= 2:
        hits = [_read_repo_line(rel, n) for rel, n in pairs[:3]]
        return "Multi-line quote (no LLM):\n" + "\n".join(hits)
    ns_found = [
        int(x)
        for x in re.findall(
            r"(?:line\s*(?:number\s*)?|quote\s*line\s*|строк[аиуе]?\s*(?:номер\s*)?)(\d+)",
            g,
            re.IGNORECASE,
        )
    ]
    # ≥2 distinct Ns without per-path pairs → miss (no same-N false-proof).
    if len(set(ns_found)) >= 2:
        return None
    nm = re.search(
        r"(?:line\s*(?:number\s*)?|quote\s*line\s*|строк[аиуе]?\s*(?:номер\s*)?)(\d+)"
        r"|(\d+)\s*-\s*based",
        g,
        re.IGNORECASE,
    )
    if not nm:
        return None
    n = int(nm.group(1) or nm.group(2))
    if n < 1 or n > 500 or n == 1:
        return None
    hits = [_read_repo_line(rel, n) for rel in paths[:3]]
    return "Multi-line quote (no LLM):\n" + "\n".join(hits)


_EVIDENCE_TOOL_MARKERS = (
    "read_file",
    "read file",
    "прочитай файл",
    "прочитайте файл",
    "первая строка",
    "first line",
    "line number",
    "quote line",
    "git_diff",
    "git diff",
    "git_status",
    "git status",
    "git_commit",
    "git commit",
    "git_add",
    "git add",
    "printenv",
    "atra_allow_git",
    "grep_search",
    "rg -n",
    "cursor_method.md",
    "найди",
    "find ",
    "where ",
    "где ",
    "в файлах",
    "объясни",
    "explain ",
    "exist",
    "exists",
    "существует",
    "есть ли файл",
    "does file",
    "file exists",
    "compare",
    "сравни",
    "what does",
    "quote the",
    "line with",
    "на какой стро",
    "в какой стро",
    "what line",
    "which line",
    "line containing",
    "defined in",
    "show where",
    "где лежит",
    "где находится",
    "где объявлен",
    "locate definition",
    "definition of",
    "where can",
    "point me",
    "opening lines",
    "first few",
    "top of",
    "top five",
    "beginning of",
    "last ",
    "tail ",
    "wc -l",
    "how many lines",
    "сколько строк",
    "sed ",
    "blame",
    "annotate",
    "who wrote",
    "context around",
    "before and after",
    "surrounding",
    "list_directory",
    "list files",
    "list dir",
    "what files",
    "ls ",
    "tree ",
)


def is_evidence_tool_goal(goal: str) -> bool:
    """File/git/env evidence asks — no experience/RAG/crystal bleed."""
    g = (goal or "").strip().lower()
    if not g:
        return False
    return any(m in g for m in _EVIDENCE_TOOL_MARKERS)


_REPO_PATH_RE = re.compile(
    r"(?P<path>(?:docs|src|knowledge_os|configs|scripts|tests|/Users|/app|/workspace)[^\s\"']+\.[A-Za-z0-9]+)",
    re.IGNORECASE,
)

# Dir paths without required extension (list_directory / ls).
_REPO_DIR_RE = re.compile(
    r"(?P<path>(?:docs|src|knowledge_os|configs|scripts|tests)(?:/[A-Za-z0-9_.-]+)+/?)",
    re.IGNORECASE,
)

_SUMMARIZE_MARKERS = (
    "summarize",
    "суммар",
    "three short bullets",
    "три коротк",
    "кратко",
    "in three",
    "3 bullets",
    "перескаж",
    "what does",
    "teach about",
    "stick to that file",
    "stick only to",
    "о чём файл",
    "чему учит",
)


def _summarize_repo_file(rel: str) -> Optional[str]:
    """Up to 3 bullets from disk for one repo-relative path."""
    resolved = resolve_repo_file_path(rel)
    if not resolved:
        return None
    try:
        with open(resolved, encoding="utf-8", errors="replace") as fh:
            raw_lines = [ln.rstrip("\n\r") for ln in fh]
    except OSError:
        return None
    bullets: list[str] = []
    for ln in raw_lines:
        s = ln.strip()
        if not s or s.startswith("```"):
            continue
        if s.startswith("#"):
            bullets.append(s.lstrip("#").strip())
        elif s.startswith("- ") or s.startswith("* "):
            bullets.append(s[2:].strip().strip("*").strip())
        elif s.startswith("**"):
            bullets.append(s.replace("**", "").strip().rstrip(":").strip())
        if len(bullets) >= 3:
            break
    if len(bullets) < 3:
        for ln in raw_lines:
            s = ln.strip()
            if len(s) < 12 or s.startswith("#") or s.startswith("-") or s.startswith("*"):
                continue
            if s not in bullets:
                bullets.append(s[:180])
            if len(bullets) >= 3:
                break
    if not bullets:
        return None
    out = [f"From `{rel}` (file read, no LLM):"]
    for b in bullets[:3]:
        out.append(f"- {b}")
    return "\n".join(out)


def _is_symbol_do_in_file_ask(goal: str) -> bool:
    """True for «What does SYMBOL do in PATH» — not a file summarize."""
    return bool(
        re.search(
            r"what does\s+[A-Za-z_][\w.]{2,80}\s+do\b",
            goal or "",
            re.IGNORECASE,
        )
    )


def file_summarize_answer(goal: str) -> Optional[str]:
    """Deterministic file→bullets for summarize/read_file (blocks PgBouncer LLM drift)."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    if first_line_file_answer(g) is not None or nth_line_file_answer(g) is not None:
        return None
    if multi_first_line_answer(g) is not None or multi_nth_line_answer(g) is not None:
        return None
    # Symbol-do-in-file → multi_grep; compare → file_compare (no header-bullet false-proof).
    if _is_symbol_do_in_file_ask(g) or any(x in gl for x in ("compare", "сравни")):
        return None
    # ≥2 paths → multi_file_summarize_answer (avoid false single-file complete answer).
    if len(_repo_paths_in_goal(g)) >= 2:
        return None
    if not any(m in gl for m in _SUMMARIZE_MARKERS):
        return None
    if not any(x in gl for x in ("read_file", "read file", "прочитай", ".md", ".txt", ".py")):
        return None
    m = _REPO_PATH_RE.search(g)
    if not m:
        return None
    return _summarize_repo_file(m.group("path"))


def multi_file_summarize_answer(goal: str) -> Optional[str]:
    """Summarize 2–3 repo files from disk — blocks single-file false-proof under evidence."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    if (
        multi_first_line_answer(g) is not None
        or first_line_file_answer(g) is not None
        or multi_nth_line_answer(g) is not None
        or nth_line_file_answer(g) is not None
    ):
        return None
    # Compare goals must not stamp summarize-as-diff false-proof.
    if any(x in gl for x in ("compare", "сравни", "identical", "одинаков")):
        return None
    if _is_symbol_do_in_file_ask(g):
        return None
    paths = _repo_paths_in_goal(g)
    if len(paths) < 2:
        return None
    if not any(m in gl for m in _SUMMARIZE_MARKERS):
        return None
    if not any(
        x in gl for x in ("read_file", "read file", "прочитай", ".md", ".txt", ".py", "each")
    ):
        return None
    blocks: list[str] = []
    for rel in paths[:3]:
        block = _summarize_repo_file(rel)
        blocks.append(block or f"From `{rel}`: missing or empty")
    if not blocks:
        return None
    return "Multi-file summarize (no LLM):\n\n" + "\n\n".join(blocks)


def file_compare_answer(goal: str) -> Optional[str]:
    """Byte-compare exactly 2 repo files — IDENTICAL / DIFFER (no LLM invent)."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    if not any(x in gl for x in ("compare", "сравни", "identical", "одинаков", "same as")):
        return None
    paths = _repo_paths_in_goal(g)
    if len(paths) != 2:
        return None
    import hashlib

    digests: list[tuple[str, Optional[str]]] = []
    for rel in paths:
        resolved = resolve_repo_file_path(rel)
        if not resolved:
            digests.append((rel, None))
            continue
        h = hashlib.sha256()
        try:
            with open(resolved, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            digests.append((rel, h.hexdigest()[:16]))
        except OSError:
            digests.append((rel, None))
    a_rel, a_d = digests[0]
    b_rel, b_d = digests[1]
    lines = [
        "File compare (no LLM):",
        f"{a_rel}: {a_d or 'MISSING'}",
        f"{b_rel}: {b_d or 'MISSING'}",
    ]
    if a_d and b_d and a_d == b_d:
        lines.append("RESULT: IDENTICAL")
    else:
        lines.append("RESULT: DIFFER")
    return "\n".join(lines)


def _resolve_git_repo() -> Optional[str]:
    for cand in (
        os.getcwd(),
        os.getenv("PROJECT_ROOT") or "",
        "/workspace/atra-web-ide",
        "/app",
    ):
        if cand and os.path.isdir(os.path.join(cand, ".git")):
            return cand
    return None


def _git_diff_one(repo: str, rel: str) -> str:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", repo, "diff", "--", rel],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (result.stdout or result.stderr or "").strip() or "(нет изменений)"
    except (OSError, subprocess.TimeoutExpired):
        return "git_diff_error"


def git_diff_answer(goal: str) -> Optional[str]:
    """Single-path git_diff from disk (blocks LLM invent of hunks)."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    if not any(x in gl for x in ("git_diff", "git diff")):
        return None
    paths = _repo_paths_in_goal(g)
    if len(paths) != 1:
        return None
    repo = _resolve_git_repo()
    if not repo:
        return None
    rel = paths[0]
    return f"git_diff (no LLM):\n### {rel}\n{_git_diff_one(repo, rel)[:4000]}"


def multi_git_diff_answer(goal: str) -> Optional[str]:
    """git diff for 2–3 paths (sync) — blocks LLM invent when multi-path git_diff asked."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    if not any(x in gl for x in ("git_diff", "git diff")):
        return None
    paths = _repo_paths_in_goal(g)
    if len(paths) < 2:
        return None
    repo = _resolve_git_repo()
    if not repo:
        return None
    blocks = [f"### {rel}\n{_git_diff_one(repo, rel)[:2500]}" for rel in paths[:3]]
    return "Multi git_diff (no LLM):\n" + "\n\n".join(blocks)


def git_status_answer(goal: str) -> Optional[str]:
    """Deterministic git status --short (blocks LLM invent of porcelain)."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    if not any(x in gl for x in ("git_status", "git status")):
        return None
    if any(
        x in gl for x in ("git_diff", "git diff", "git_commit", "git commit", "git_add", "git add")
    ):
        return None
    repo = _resolve_git_repo()
    if not repo:
        return None
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", repo, "status", "--short"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = (result.stdout or result.stderr or "").strip() or "(чисто)"
    except (OSError, subprocess.TimeoutExpired):
        return None
    return f"git_status (no LLM):\n{out[:4000]}"


def git_blame_answer(goal: str) -> Optional[str]:
    """Thin git blame for 1 path (optional -L or symbol line) — blocks nth/multi_grep hijack."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    if not any(
        x in gl
        for x in (
            "git blame",
            "git_blame",
            "blame",
            "annotate",
            "who wrote",
            "who last touched",
        )
    ):
        return None
    paths = _repo_paths_in_goal(g)
    if len(paths) != 1:
        return None
    rel = paths[0]
    resolved = resolve_repo_file_path(rel)
    if not resolved:
        return None
    repo = _resolve_git_repo()
    if not repo:
        return None
    line_a = line_b = None
    lm = re.search(r"-L\s*(?P<a>\d+)\s*,\s*(?P<b>\d+)", g)
    if lm:
        line_a, line_b = int(lm.group("a")), int(lm.group("b"))
    if line_a is None:
        lm2 = re.search(r"\bline\s+(?P<a>\d+)\b", g, re.IGNORECASE)
        if lm2:
            line_a = line_b = int(lm2.group("a"))
    if line_a is None:
        # Symbol → first matching line (prefer snake_case / long idents after wrote/blame)
        sm = re.search(
            r"(?:who\s+(?:wrote|last\s+touched)|blame(?:\s+who\s+wrote)?|annotate)\s+"
            r"([A-Za-z_][\w.]{2,80})\b",
            g,
            re.IGNORECASE,
        )
        tok = sm.group(1) if sm else None
        _blame_stop = {
            "line",
            "who",
            "last",
            "git",
            "file",
            "path",
            "wrote",
            "touched",
            "annotate",
            "blame",
            "the",
            "with",
            "src",
            "docs",
            "configs",
            "scripts",
            "tests",
            "knowledge_os",
            "agents",
            "bridge",
            "app",
            "users",
            "workspace",
        }
        path_bits = {p for p in re.split(r"[/\\.]", rel) if p}
        # Prefer longest snake_case symbol; never path segments / stopwords.
        cands = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]{6,80})\b", g)
        cands = [
            c for c in cands if c.lower() not in _blame_stop and c not in path_bits and "_" in c
        ]
        if tok and (tok.lower() in _blame_stop or tok in path_bits or "_" not in tok):
            tok = max(cands, key=len) if cands else None
        elif cands and tok and tok not in cands:
            # Upgrade short/generic match to snake_case candidate when present
            longer = max(cands, key=len)
            if len(longer) > len(tok):
                tok = longer
        if tok and tok.lower() not in _blame_stop and tok not in path_bits:
            try:
                with open(resolved, encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if tok in line:
                            line_a = line_b = i
                            break
            except OSError:
                return None
    import subprocess

    # Whole-file blame without -L is too large / not evidence — require a line window.
    if line_a is None or line_b is None:
        return (
            "git_blame (no LLM):\nError: line window required (-L a,b / line N / symbol in path)."
        )
    cmd = ["git", "-C", repo, "blame", f"-L{line_a},{line_b}", "--", rel]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        out = (result.stdout or result.stderr or "").strip() or "(empty blame)"
    except (OSError, subprocess.TimeoutExpired):
        return None
    return f"git_blame (no LLM):\n{out[:4000]}"


def file_exists_answer(goal: str) -> Optional[str]:
    """path: EXISTS|MISSING for 1–3 repo paths — blocks LLM invent of existence."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    if not any(
        x in gl
        for x in (
            "exist",
            "exists",
            "существует",
            "есть ли файл",
            "does file",
            "file exists",
            "файл на месте",
            "наличие файл",
            "проверь наличие",
        )
    ):
        return None
    # Content audits stay on file_check / summarize / find paths.
    if any(
        x in gl
        for x in (
            "найди проблемы",
            "есть ли там",
            "summarize",
            "first line",
            "quote line",
            "lines ",
        )
    ):
        return None
    # «Does SYMBOL exist in PATH» — symbol membership, not path existence (→ multi_grep).
    if re.search(
        r"(?:does|is|есть ли)\s+[A-Za-z_][\w.]{2,80}\s+(?:exist|exists|существует)?\s*(?:in|в)\b",
        g,
        re.IGNORECASE,
    ) and not re.search(r"does\s+file\b|file\s+exists|есть ли файл", gl):
        return None
    if re.search(
        r"[A-Za-z_][\w.]{2,80}\s+(?:exist|exists)\s+in\b",
        g,
        re.IGNORECASE,
    ) and not re.search(r"does\s+file\b|file\s+exists|есть ли файл", gl):
        return None
    paths = _repo_paths_in_goal(g)
    if not paths:
        return None
    hits = [f"{rel}: {'EXISTS' if resolve_repo_file_path(rel) else 'MISSING'}" for rel in paths[:3]]
    return "File existence (no LLM):\n" + "\n".join(hits)


def list_directory_answer(goal: str) -> Optional[str]:
    """Sorted names from 1 allowlisted repo dir — blocks LLM invent of trees."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    has_list_marker = any(
        x in gl
        for x in (
            "list_directory",
            "list files",
            "list dir",
            "listdir",
            "ls ",
            "содержимое папк",
            "список файл",
            "покажи файлы",
            "tree ",
            "перечисли файл",
            "what files",
            "files are in",
            "directory listing",
            "directory contents",
            "enumerate files",
        )
    ) or bool(re.search(r"(?:^|\s)ls(?:\s|$)", gl))
    if not has_list_marker:
        return None
    dirs: list[str] = []
    seen: set[str] = set()
    for m in _REPO_DIR_RE.finditer(g):
        rel = m.group("path").rstrip("/")
        # Prefer real dirs; skip if it resolves only as a file with extension.
        if resolve_repo_dir_path(rel) and rel not in seen:
            seen.add(rel)
            dirs.append(rel)
    if not dirs:
        # Fail-closed: bare `ls` / `list files` without allowlisted dir — refuse, no LLM invent.
        return (
            "list_directory (no LLM):\n"
            "Error: allowlisted dir required "
            "(docs|src|knowledge_os|configs|scripts|tests/...)."
        )
    rel = dirs[0]
    resolved = resolve_repo_dir_path(rel)
    if not resolved:
        return None
    try:
        names = sorted(os.listdir(resolved))
    except OSError:
        return None
    cap = 80
    lines = [f"- {n}" for n in names[:cap]]
    if len(names) > cap:
        lines.append(f"- … (+{len(names) - cap} more)")
    return f"list_directory (no LLM):\n{rel}/\n" + "\n".join(lines)


# Word-numbers for «first five lines» / «первые пять строк» (digit form still preferred).
_WORD_TO_INT = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "один": 1,
    "одна": 1,
    "одну": 1,
    "два": 2,
    "две": 2,
    "двух": 2,
    "три": 3,
    "трех": 3,
    "трёх": 3,
    "четыре": 4,
    "четырех": 4,
    "четырёх": 4,
    "пять": 5,
    "пяти": 5,
    "шесть": 6,
    "шести": 6,
    "семь": 7,
    "семи": 7,
    "восемь": 8,
    "восьми": 8,
    "девять": 9,
    "девяти": 9,
    "десять": 10,
    "десяти": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
    "двадцать": 20,
    "twenty-one": 21,
    "twenty one": 21,
    "twenty-five": 25,
    "twenty five": 25,
    "thirty": 30,
    "тридцать": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
}
_WORD_N_ALT = r"\d+|" + "|".join(re.escape(k) for k in sorted(_WORD_TO_INT, key=len, reverse=True))


def _parse_line_count_token(raw: str) -> Optional[int]:
    s = (raw or "").strip().lower().replace("-", " ")
    if not s:
        return None
    if s.isdigit():
        return int(s)
    return (
        _WORD_TO_INT.get(s)
        or _WORD_TO_INT.get(s.replace(" ", "-"))
        or _WORD_TO_INT.get(s.replace(" ", ""))
    )


def line_range_file_answer(goal: str) -> Optional[str]:
    """Quote lines A–B (1-based inclusive) from one repo file — blocks LLM invent."""
    g = (goal or "").strip()
    if not g:
        return None
    if (
        first_line_file_answer(g) is not None
        or multi_first_line_answer(g) is not None
        or multi_nth_line_answer(g) is not None
        or nth_line_file_answer(g) is not None
    ):
        return None
    gl = g.lower()
    paths = _repo_paths_in_goal(g)
    if len(paths) != 1:
        return None
    # Forced absolute windows (sed / next-after / ±around line) — skip first/last dual parse.
    forced_ranges: Optional[list[tuple[int, int]]] = None
    sed_m = re.search(
        r"sed\s+-n\s+['\"]?(?P<a>\d+)\s*,\s*(?P<b>\d+)p['\"]?",
        g,
        re.IGNORECASE,
    )
    if sed_m:
        forced_ranges = [(int(sed_m.group("a")), int(sed_m.group("b")))]
    if forced_ranges is None:
        next_after = re.search(
            rf"(?:next|следующие)\s+(?P<n>{_WORD_N_ALT})\s+(?:lines?|строк)\s+"
            rf"(?:after|после)\s+line\s+(?P<m>\d+)",
            g,
            re.IGNORECASE,
        )
        if next_after:
            n = _parse_line_count_token(next_after.group("n"))
            m0 = int(next_after.group("m"))
            if n is not None:
                forced_ranges = [(m0 + 1, m0 + n)]
    if forced_ranges is None:
        around_line = re.search(
            rf"(?:±\s*(?P<k1>{_WORD_N_ALT})|around\s+(?P<k2>{_WORD_N_ALT}))\s+"
            rf"(?:lines?\s+)?(?:around\s+)?line\s+(?P<m>\d+)"
            rf"|line\s+(?P<m2>\d+).{{0,40}}?(?:±\s*(?P<k3>{_WORD_N_ALT})|around\s+(?P<k4>{_WORD_N_ALT}))",
            g,
            re.IGNORECASE,
        )
        if around_line:
            raw_k = (
                around_line.group("k1")
                or around_line.group("k2")
                or around_line.group("k3")
                or around_line.group("k4")
            )
            m0 = int(around_line.group("m") or around_line.group("m2") or "0")
            k = _parse_line_count_token(raw_k or "")
            if k is not None and m0 >= 1:
                forced_ranges = [(max(1, m0 - k), m0 + k)]
    rm = re.search(
        r"(?:lines?|строк[аиуеи]?)\s*(?P<a>\d+)\s*(?:[-–—]+|\s+to\s+|\s+through\s+)\s*(?P<b>\d+)",
        g,
        re.IGNORECASE,
    )
    first_n = re.search(
        rf"(?:first|top|opening|первые|первых|начало)\s+(?P<n>{_WORD_N_ALT})\s+(?:lines?|строк)",
        g,
        re.IGNORECASE,
    )
    # «opening lines» / «first few lines» without explicit N → first 5 (convention).
    opening_few = re.search(
        r"(?:opening|first|top)\s+few\s+lines?|(?:opening|первые)\s+lines?\b|начало\s+(?:файла|file)",
        g,
        re.IGNORECASE,
    )
    head_n = re.search(
        rf"(?:head\s+-n?\s*|head\s+)(?P<n>{_WORD_N_ALT})\b",
        g,
        re.IGNORECASE,
    )
    # «first line» / «top of» as N=1 when paired with a last-window ask.
    first_one = bool(re.search(r"\bfirst\s+line\b|первая\s+строка|top\s+of\b|opening\s+of\b", gl))
    last_n = re.search(
        rf"(?:last|final|bottom|trailing|ending|последн(?:ие|их)?|хвост|концев\w*)\s+"
        rf"(?P<n>{_WORD_N_ALT})\s+(?:lines?|строк)",
        g,
        re.IGNORECASE,
    )
    tail_n = re.search(
        rf"(?:tail\s+-n?\s*|tail\s+)(?P<n>{_WORD_N_ALT})\b",
        g,
        re.IGNORECASE,
    )
    last_few = re.search(
        r"(?:last|final|bottom|trailing|ending|последн)\s+few\s+lines?|последние\s+строк",
        g,
        re.IGNORECASE,
    )
    from_end = bool(re.search(r"from\s+the\s+end|с\s+конца", gl))
    # «first and last N lines» → both windows size N
    both_n = re.search(
        rf"first\s+and\s+last\s+(?P<n>{_WORD_N_ALT})\s+(?:lines?|строк)",
        g,
        re.IGNORECASE,
    )
    # «first A and last B lines» (lines only after second N)
    first_and_last = re.search(
        rf"(?:first|top|opening|первые|первых)\s+(?P<a>{_WORD_N_ALT})\s+and\s+"
        rf"(?:last|final|bottom|trailing|ending|последн\w*|хвост)\s+(?P<b>{_WORD_N_ALT})"
        rf"(?:\s+(?:lines?|строк))?",
        g,
        re.IGNORECASE,
    )
    # «last A and first B» / «last A and first line»
    last_and_first = re.search(
        rf"(?:last|final|bottom|trailing|ending|последн\w*|хвост|tail\s+-n?\s*)\s*"
        rf"(?P<a>{_WORD_N_ALT})?\s*(?:lines?|строк)?\s+and\s+"
        rf"(?:first\s+line|top\s+of|opening\s+of|"
        rf"(?:first|top|opening|первые)\s+(?P<b>{_WORD_N_ALT})(?:\s+(?:lines?|строк))?)",
        g,
        re.IGNORECASE,
    )

    n_first: Optional[int] = None
    n_last: Optional[int] = None
    if both_n:
        n = _parse_line_count_token(both_n.group("n"))
        if n is not None:
            n_first = n_last = n
    if first_and_last and n_first is None and n_last is None:
        n_first = _parse_line_count_token(first_and_last.group("a"))
        n_last = _parse_line_count_token(first_and_last.group("b"))
    if last_and_first and (n_first is None or n_last is None):
        # group a may be empty when «tail -n 5 and top of» was parsed differently
        raw_a = last_and_first.group("a")
        raw_b = last_and_first.group("b")
        if raw_a and n_last is None:
            n_last = _parse_line_count_token(raw_a)
        if raw_b and n_first is None:
            n_first = _parse_line_count_token(raw_b)
        elif re.search(r"first\s+line|top\s+of|opening\s+of", last_and_first.group(0), re.I):
            if n_first is None:
                n_first = 1
    if first_n and n_first is None:
        n_first = _parse_line_count_token(first_n.group("n"))
    elif opening_few and n_first is None:
        n_first = 5
    elif head_n and ("|" in g or "head" in gl) and n_first is None:
        n_first = _parse_line_count_token(head_n.group("n"))
    if last_n and n_last is None:
        n_last = _parse_line_count_token(last_n.group("n"))
    elif tail_n and ("|" in g or "tail" in gl) and n_last is None:
        n_last = _parse_line_count_token(tail_n.group("n"))
    elif (last_few or from_end) and n_last is None:
        n_last = 5
    if first_one and n_last is not None and n_first is None:
        n_first = 1

    if forced_ranges is None and rm and n_first is None and n_last is None:
        a, b = int(rm.group("a")), int(rm.group("b"))
        if a < 1 or b < 1 or a > 500 or b > 500 or a > b:
            return None
        if a == b:
            return None
    elif forced_ranges is None and (n_first is not None or n_last is not None):
        if n_first is not None and (n_first < 1 or n_first > 500):
            return None
        if n_last is not None and (n_last < 1 or n_last > 500):
            return None
    elif forced_ranges is None:
        return None

    rel = paths[0]
    resolved = resolve_repo_file_path(rel)
    if not resolved:
        return None
    hits: list[str] = []
    seen_idx: set[int] = set()
    try:
        with open(resolved, encoding="utf-8", errors="replace") as fh:
            all_lines = fh.readlines()
        total = len(all_lines)
        ranges: list[tuple[int, int]] = []
        if forced_ranges is not None:
            for a, b in forced_ranges:
                if a > 500 or b > 500:
                    return None
                ranges.append((max(1, a), min(b, total)))
        elif rm and n_first is None and n_last is None:
            ranges.append((int(rm.group("a")), int(rm.group("b"))))
        else:
            if n_first is not None:
                ranges.append((1, min(n_first, total)))
            if n_last is not None:
                a = max(1, total - n_last + 1)
                ranges.append((a, total))
        for a, b in ranges:
            if a > b:
                continue
            for i in range(a, b + 1):
                if i in seen_idx or i > total:
                    continue
                seen_idx.add(i)
                hits.append(f"{rel}:{i}:{all_lines[i - 1].rstrip(chr(10) + chr(13))}")
    except OSError:
        return None
    if not hits:
        return None
    return "Line range (no LLM):\n" + "\n".join(hits)


def line_count_file_answer(goal: str) -> Optional[str]:
    """Exact line count for one repo file — blocks LLM invent of wc -l."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    if not any(
        x in gl
        for x in (
            "wc -l",
            "how many lines",
            "count lines",
            "line count",
            "number of lines",
            "total lines",
            "linecount",
            "сколько строк",
            "число строк",
            "длина файла",
        )
    ):
        return None
    paths = _repo_paths_in_goal(g)
    if len(paths) != 1:
        return None
    rel = paths[0]
    resolved = resolve_repo_file_path(rel)
    if not resolved:
        return None
    try:
        with open(resolved, encoding="utf-8", errors="replace") as fh:
            n = sum(1 for _ in fh)
    except OSError:
        return None
    return f"Line count (no LLM):\n{rel}: {n} lines"


_PGBOUNCER_BLEED_RE = re.compile(
    r"pgbouncer|default_pool_size|\b6432\b|переходим к (?:выполнению|исполнению)\s+тз",
    re.IGNORECASE,
)


def looks_like_pgbouncer_recipe(text: str) -> bool:
    """True if answer drifted into sticky PgBouncer/6432 runbook."""
    return bool(_PGBOUNCER_BLEED_RE.search(text or ""))


_GREP_LINE_GOAL_RE = re.compile(
    r"(?:rg\s+-n|grep_search|grep\s+-rnE?|grep\s+-n)\s+"
    r"['\"](?P<pat>[^'\"]+)['\"]\s+"
    r"(?P<path>(?:docs|src|knowledge_os|configs|scripts|tests|/Users|/app|/workspace)[^\s\"']+\.[A-Za-z0-9]+)",
    re.IGNORECASE,
)


def _bare_done_refusal_text() -> str:
    try:
        from knowledge_os.app.cursor_method import BARE_DONE_REFUSAL

        return BARE_DONE_REFUSAL
    except Exception:
        try:
            from app.cursor_method import BARE_DONE_REFUSAL

            return BARE_DONE_REFUSAL
        except Exception:
            return (
                "Не заявляю «готово» без доказательства (нужен вывод команды, теста или /health)."
            )


def bare_done_instruction_answer(goal: str) -> Optional[str]:
    """Curator asks to say «готово» without evidence → refuse (no LLM/PgBouncer path).

    Also refuses short user claims of green tests / closed task with no artifact.
    """
    g = (goal or "").strip().lower()
    if not g:
        return None
    has_ready = (
        "готово" in g
        or " done" in f" {g}"
        or g.startswith("done")
        or "задача сделана" in g
        or "задача закрыта" in g
        or "тесты зелёные" in g
        or "тесты зеленые" in g
        or "тесты пройдены" in g
    )
    if not has_ready:
        return None
    instruct = any(
        x in g
        for x in (
            "одним словом",
            "без доказательств",
            "без пруфа",
            "without evidence",
            "just say",
            "скажи только",
            "ответь только",
            "ответь ровно",
            "ответь одним",
            "словом готово",
            "say only",
            "reply with only",
            "only the word",
        )
    )
    claim_only = (
        any(
            x in g
            for x in (
                "задача сделана",
                "всё готово",
                "все готово",
                "тесты зелёные",
                "тесты зеленые",
                "тесты пройдены",
                "задача закрыта",
            )
        )
        and not any(
            x in g
            for x in (
                "?",
                "проверь",
                "verify",
                "pytest",
                "curl",
                "покажи",
                "почему",
                "как ",
                "docker",
                "/health",
            )
        )
        and len(g) < 220
    )
    if not instruct and not claim_only:
        return None
    return _bare_done_refusal_text()


def git_mutate_reject_answer(goal: str) -> Optional[str]:
    """Deterministic fail-closed reply when mutate asked and ATRA_ALLOW_GIT_MUTATE unset."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    mutate_ask = any(
        x in gl
        for x in (
            "git_commit",
            "git commit",
            "git_add",
            "git add ",
            "git add\n",
            "git mutate",
            "git_branch_create",
            "git branch create",
        )
    )
    if not mutate_ask:
        return None
    # Read-only git asks are not mutate.
    if any(
        x in gl for x in ("git_status", "git status", "git_diff", "git diff", "git_log", "git log")
    ):
        if not any(x in gl for x in ("git_commit", "git commit", "git_add", "git add", "mutate")):
            return None
    if os.getenv("ATRA_ALLOW_GIT_MUTATE", "").lower() in ("true", "1", "yes"):
        return None
    return (
        "Error: git mutate rejected (ATRA_ALLOW_GIT_MUTATE not set). "
        "Human approve only — set env true and restart Victoria."
    )


def _repo_paths_in_goal(goal: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for m in _REPO_PATH_RE.finditer(goal or ""):
        p = m.group("path")
        if p not in seen:
            seen.add(p)
            paths.append(p)
    return paths


def grep_line_answer(goal: str) -> Optional[str]:
    """Deterministic rg/grep hit for curator pairs (blocks invented :123 recipes)."""
    g = (goal or "").strip()
    if not g:
        return None
    # ≥2 paths → multi_grep_line_answer (avoid single-file hijack of multi-file asks).
    if len(_repo_paths_in_goal(g)) >= 2:
        return None
    gl = g.lower()
    if not any(x in gl for x in ("rg -n", "grep_search", "grep -n", "grep -rn")):
        return None
    m = _GREP_LINE_GOAL_RE.search(g)
    if not m:
        return None
    pat = m.group("pat")
    resolved = resolve_repo_file_path(m.group("path"))
    if not resolved or not pat:
        return None
    try:
        with open(resolved, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                if pat in line:
                    rel = m.group("path")
                    return f"{rel}:{i}:{line.rstrip()}"
    except OSError:
        return None
    return f"No matches for {pat!r} in {m.group('path')}"


def multi_grep_line_answer(goal: str) -> Optional[str]:
    """Deterministic symbol locate in 1–3 repo paths — blocks LLM invent of path:line."""
    g = (goal or "").strip()
    if not g:
        return None
    gl = g.lower()
    paths = _repo_paths_in_goal(g)
    # Blame → git_blame_answer (no symbol-locate false-proof).
    if any(
        x in gl
        for x in ("git blame", "git_blame", "blame", "annotate", "who wrote", "who last touched")
    ):
        return None
    # Single-path rg -n stays on grep_line_answer (same shape, existing pairs)
    # unless context window (-C/-A/-B / before and after) is requested.
    _ctx_ask = any(
        x in gl
        for x in (
            "before and after",
            "surrounding",
            "context around",
            "of context",
            "-c ",
            "-a ",
            "-b ",
            "±",
        )
    ) or bool(re.search(r"-[CAB]\s*\d+", g))
    if (
        len(paths) == 1
        and any(x in gl for x in ("rg -n", "grep_search", "grep -n", "grep -rn"))
        and not _ctx_ask
    ):
        return None
    if not any(
        x in gl
        for x in (
            "найди",
            "find ",
            "where ",
            "where is",
            "locate ",
            "search for",
            "grep",
            "rg ",
            "где ",
            "в файлах",
            "объясни",
            "explain ",
            "what does",
            "quote the",
            "line with",
            "на какой стро",
            "в какой стро",
            "what line",
            "which line",
            "line containing",
            "defined in",
            "show where",
            "где лежит",
            "где находится",
            "где объявлен",
            "point me",
            "definition of",
            "declaration of",
            "highlight ",
            "contain",
            "mentioned",
            "context",
            "surrounding",
            "before and after",
            "is ",
            "exist",
            "line number",
            "quote line",
            "report path",
        )
    ):
        return None
    if not paths:
        return (
            "Symbol find (no LLM):\n"
            "Error: repo path required "
            "(docs|src|knowledge_os|configs|scripts|tests/...)."
        )
    pat_m = re.search(r"['\"]([^'\"]{2,120})['\"]", g)
    if not pat_m:
        pat_m = re.search(
            r"what does\s+([A-Za-z_][\w.]{2,80})\s+do\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # context around TOKEN / N lines before and after TOKEN
        pat_m = re.search(
            r"(?:context\s+around|surrounding\s+context\s+for|before\s+and\s+after|"
            r"±\s*\d+\s+lines?\s+around|with\s+\d+\s+lines?\s+of\s+context)\s+"
            r"[`']?([A-Za-z_][\w.]{2,80})\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # Does PATH contain TOKEN / Is TOKEN mentioned in PATH
        pat_m = re.search(
            r"contain(?:s)?\s+[`']?([A-Za-z_][\w.]{2,80})\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        pat_m = re.search(
            r"(?:is|есть ли)\s+[`']?([A-Za-z_][\w.]{2,80})\s+mentioned\s+in\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # «Locate/Find/Show definition of TOKEN» before generic locate
        pat_m = re.search(
            r"(?:locate|find|show|go\s+to|jump\s+to|open)\s+(?:the\s+)?(?:definition|declaration|decl)\s+of\s+[`']?([A-Za-z_][\w.]{2,80})\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # Bare «Definition/Declaration of TOKEN in PATH»
        pat_m = re.search(
            r"(?:definition|declaration)\s+of\s+[`']?([A-Za-z_][\w.]{2,80})\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # bare grep/rg/highlight TOKEN path
        pat_m = re.search(
            r"(?:grep|rg|highlight)\s+[`']?([A-Za-z_][\w.]{2,80})\b",
            g,
            re.IGNORECASE,
        )
        if pat_m and pat_m.group(1).lower() in {"-n", "-rn", "-rne", "search"}:
            pat_m = None
    if not pat_m:
        # «Where can/might I find TOKEN» before generic where (avoids TOKEN=can)
        pat_m = re.search(
            r"where\s+(?:can|could|might|would|should|do|does|did)\s+"
            r"(?:\w+\s+){0,4}(?:find|locate|look\s+for)\s+[`']?([A-Za-z_][\w.]{2,80})\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # «Find where TOKEN is declared/defined»
        pat_m = re.search(
            r"(?:find\s+)?where\s+[`']?([A-Za-z_][\w.]{2,80})\s+is\s+(?:declared|defined|located)\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # «where does TOKEN live/sit» before generic where (avoids TOKEN=does)
        pat_m = re.search(
            r"where\s+does\s+[`']?([A-Za-z_][\w.]{2,80})\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # «What line is TOKEN on» / «What line number is TOKEN»
        pat_m = re.search(
            r"what\s+line(?:\s+number)?\s+is\s+[`']?([A-Za-z_][\w.]{2,80})\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        pat_m = re.search(
            r"(?:report|tell\s+me|give\s+me|point\s+me\s+to)\s+(?:the\s+)?(?:line(?:\s+number)?\s+(?:of|for)\s+)?[`']?([A-Za-z_][\w.]{2,80})\b",
            g,
            re.IGNORECASE,
        )
        if pat_m and pat_m.group(1).lower() in {
            "the",
            "line",
            "number",
            "me",
            "to",
        }:
            pat_m = None
    if not pat_m:
        pat_m = re.search(
            r"(?:quote(?:\s+the)?\s+line(?:\s+(?:with|containing))?|line with|line containing|"
            r"(?:на|в)\s+какой\s+стро(?:ке|чке)(?:\s+определ[её]н[аоы]?)?|"
            r"(?:what|which)\s+line(?:\s+(?:has|contains))?|"
            r"show(?:\s+me)?\s+where|"
            r"где\s+(?:лежит|находится|объявлен[аоы]?))\s+[`']?([A-Za-z_][\w.]{2,80})",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # Is TOKEN defined in PATH / TOKEN defined in PATH
        pat_m = re.search(
            r"(?:is\s+)?[`']?([A-Za-z_][\w.]{2,80})\s+defined\s+in\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # Does SYMBOL exist in PATH (symbol membership)
        pat_m = re.search(
            r"(?:does|is)\s+[`']?([A-Za-z_][\w.]{2,80})\s+exist(?:s)?\s+in\b",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # Avoid «is declared in» → TOKEN=declared (handled above)
        pat_m = re.search(
            r"(?:is|есть ли)\s+[`']?([A-Za-z_][\w.]{2,80})\s+(?:in|в)\b",
            g,
            re.IGNORECASE,
        )
        if pat_m and pat_m.group(1).lower() in {
            "declared",
            "defined",
            "located",
            "definition",
            "declaration",
        }:
            pat_m = None
    if not pat_m:
        pat_m = re.search(
            r"(?:найди|find|where(?:\s+is)?|locate|search for|объясни|explain)\s+[`']?([A-Za-z_][\w.]{2,80})",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        # «На/В какой строке/строчке [определён] TOKEN» / «где лежит|объявлен TOKEN»
        pat_m = re.search(
            r"(?:(?:на|в)\s+какой\s+стро(?:ке|чке)(?:\s+определ[её]н[аоы]?)?|"
            r"где\s+(?:лежит|находится|объявлен[аоы]?))\s+([A-Za-z_][\w.]{2,80})",
            g,
            re.IGNORECASE,
        )
    if not pat_m:
        return None
    pat = pat_m.group(1)
    if pat.lower() in {
        "how",
        "the",
        "a",
        "an",
        "in",
        "with",
        "что",
        "как",
        "file",
        "path",
        "line",
        "me",
        "where",
        "does",
        "can",
        "could",
        "might",
        "would",
        "should",
        "did",
        "contains",
        "containing",
        "live",
        "defined",
        "definition",
        "declared",
        "declaration",
        "decl",
        "located",
        "number",
        "on",
        "i",
        "you",
        "find",
        "look",
        "определён",
        "определен",
        "лежит",
        "находится",
        "объявлен",
    }:
        return None
    # Context window: -C N / N lines before and after / ±N / with N lines of context.
    ctx_k = 0
    cm = re.search(
        r"(?:-C\s*|±\s*)(?P<k>\d+)|(?P<k2>\d+)\s+lines?\s+before\s+and\s+after|"
        r"with\s+(?P<k3>\d+)\s+lines?\s+of\s+context|"
        r"-(?:A|B)\s*(?P<k4>\d+)",
        g,
        re.IGNORECASE,
    )
    if cm:
        ctx_k = int(cm.group("k") or cm.group("k2") or cm.group("k3") or cm.group("k4") or "0")
    elif any(x in gl for x in ("surrounding context", "context around")):
        ctx_k = 3
    ctx_k = max(0, min(ctx_k, 20))

    hits: list[str] = []
    for rel in paths[:3]:
        resolved = resolve_repo_file_path(rel)
        if not resolved:
            hits.append(f"{rel}: missing")
            continue
        found = False
        try:
            with open(resolved, encoding="utf-8", errors="replace") as fh:
                all_lines = fh.readlines()
            for i, line in enumerate(all_lines, 1):
                if pat in line:
                    if ctx_k:
                        a = max(1, i - ctx_k)
                        b = min(len(all_lines), i + ctx_k)
                        for j in range(a, b + 1):
                            hits.append(f"{rel}:{j}:{all_lines[j - 1].rstrip(chr(10) + chr(13))}")
                    else:
                        hits.append(f"{rel}:{i}:{line.rstrip()}")
                    found = True
                    break
        except OSError:
            hits.append(f"{rel}: read_error")
            continue
        if not found:
            hits.append(f"{rel}: no match for {pat!r}")
    if not hits:
        return None
    header = "Multi-file find (no LLM):\n" if len(paths) >= 2 else "Symbol find (no LLM):\n"
    return header + "\n".join(hits)


def goal_wants_ttc(goal: str) -> bool:
    """TTC/p95 dump only when the user asks for latency metrics — not 'metrics dump' prose.

    Do not put ``ttc`` on both sides of the AND: that made bare "what is ttc" /
    "explain ttc" emit a live p50/p95 dump instead of an explanation.

    Definitional asks ("дай определение ttc", "что такое ttc") must not trip the
    (ttc ∧ дай/покажи) path unless explicit latency markers are present.
    """
    g = (goal or "").lower()
    _latency_markers = (
        "/metrics",
        "victoria_async",
        "p50",
        "p95",
        "samples",
        "inflight",
        "time_to_completed",
        "time-to-completed",
        "duration_seconds",
    )
    _definitional = (
        "определение",
        "что такое",
        "объясни",
        "what is",
        "what's",
        "explain",
        "значит",
    )
    if any(x in g for x in _definitional) and not any(x in g for x in _latency_markers):
        return False
    if any(
        x in g
        for x in (
            "/metrics",
            "victoria_async",
            "time_to_completed",
            "time-to-completed",
            "duration_seconds",
        )
    ):
        return True
    if any(x in g for x in ("p95", "p50", "ttc")) and any(
        x in g
        for x in (
            "async",
            "samples",
            "latency",
            "victoria",
            "inflight",
            "prometheus",
            "дай",
            "покажи",
            "какие",
            "curl",
            "grep",
            "show",
            "give",
        )
    ):
        return True
    # Bare "metrics" is too broad ("metrics dump" meta-questions). Require TTC context.
    if "metrics" in g and any(
        x in g for x in ("ttc", "p95", "p50", "async", "prometheus", "victoria_async", "/metrics")
    ):
        return True
    return False


def grounded_ports_answer(goal: str) -> Optional[str]:
    """Ответ по портам из реестра, не из головы модели."""
    g = (goal or "").lower()
    if "порт" not in g and "port" not in g:
        return None
    found: list[str] = []
    seen: set[str] = set()
    for name, port in CANONICAL_ATRA_PORTS:
        if name in g and port not in seen:
            found.append(port)
            seen.add(port)
    # Named service(s) win: "какой порт у Victoria?" → 8010, not the full dump.
    # Previously len(found)==1 fell through to "8010, 8011, 3005" via "порт ".
    if found:
        return ", ".join(found)
    if "порта" in g or "порты" in g or "порт " in g:
        return "8010, 8011, 3005"
    return None


def public_task_title(goal: str, limit: int = 255) -> str:
    """Заголовок задачи без префикса метода Cursor."""
    g = (goal or "").strip() or "Task"
    if "МЕТОД CURSOR" in g:
        for sep in ("ЗАДАЧА:", "ТЕКУЩИЙ ЗАПРОС:", "ЗАПРОС ПОЛЬЗОВАТЕЛЯ:"):
            if sep in g:
                g = g.split(sep, 1)[-1].strip()
                break
        else:
            lines = [
                ln
                for ln in g.splitlines()
                if ln.strip()
                and "МЕТОД CURSOR" not in ln
                and not ln.strip().startswith(("1.", "2.", "3.", "4.", "Источник портов"))
            ]
            g = " ".join(lines).strip() or "Task"
    return g[:limit]


def format_live_fact_answer(
    goal: str,
    *,
    health: Optional[str] = None,
    queue: Optional[dict] = None,
    nodes: Optional[int] = None,
    ops: Optional[dict] = None,
    ttc: Optional[dict] = None,
    slots: Optional[str] = None,
    scanner: Optional[str] = None,
) -> Optional[str]:
    """Короткий ответ из живых probe, без LLM."""
    if not is_fact_seeking_question(goal):
        return None
    g = (goal or "").lower()
    bits: list[str] = []
    ports = grounded_ports_answer(goal)
    if ports:
        bits.append(ports)
    if goal_wants_ollama_slots(goal):
        bits.append(slots if slots else "слоты не сняла")
    if goal_wants_scanner(goal):
        bits.append(scanner if scanner else "сканер не сняла")
    env_line = process_env_fact_answer(goal)
    if env_line:
        bits.append(env_line)
    if ("health" in g or "жив" in g) and health:
        bits.append(health)
    if queue is not None and any(x in g for x in ("очеред", "pending", "in_progress")):
        bits.append(
            "pending="
            + str(int(queue.get("pending") or 0))
            + " in_progress="
            + str(int(queue.get("in_progress") or 0))
        )
    if nodes is not None and any(
        x in g for x in ("knowledge_nodes", "сколько узл", "сколько знан")
    ):
        bits.append(str(int(nodes)))
    if ops is not None and any(
        x in g
        for x in (
            "throughput",
            "пропуск",
            "stale",
            "застряв",
            "error rate",
            "ошиб",
            "failed",
            "contract",
            "контракт",
            "24h",
            "24ч",
            "сутк",
            "cancel",
            "cancelled",
            "отмен",
            "churn",
        )
    ):
        parts: list[str] = []
        if "throughput_1h" in ops:
            parts.append("throughput_1h=" + str(int(ops.get("throughput_1h") or 0)))
        if "throughput_24h" in ops:
            parts.append("throughput_24h=" + str(int(ops.get("throughput_24h") or 0)))
        if "stale_in_progress" in ops:
            parts.append("stale_in_progress=" + str(int(ops.get("stale_in_progress") or 0)))
        if "failed_1h" in ops:
            parts.append("failed_1h=" + str(int(ops.get("failed_1h") or 0)))
        if "completed_1h" in ops:
            parts.append("completed_1h=" + str(int(ops.get("completed_1h") or 0)))
        if "error_rate_1h" in ops:
            parts.append("error_rate_1h=" + str(float(ops.get("error_rate_1h") or 0.0)))
        if "contract_enforced_24h" in ops:
            parts.append(
                "contract_enforced_24h="
                + str(int(ops.get("contract_enforced_24h") or 0))
                + "/"
                + str(int(ops.get("completed_24h") or 0))
            )
        if "cancelled_1h_total" in ops:
            parts.append("cancelled_1h_total=" + str(int(ops.get("cancelled_1h_total") or 0)))
        if "cancelled_1h_work" in ops:
            parts.append("cancelled_1h_work=" + str(int(ops.get("cancelled_1h_work") or 0)))
        if "cancelled_1h_policy" in ops:
            parts.append("cancelled_1h_policy=" + str(int(ops.get("cancelled_1h_policy") or 0)))
        if "cancelled_24h_total" in ops:
            parts.append("cancelled_24h_total=" + str(int(ops.get("cancelled_24h_total") or 0)))
        if "cancelled_24h_work" in ops:
            parts.append("cancelled_24h_work=" + str(int(ops.get("cancelled_24h_work") or 0)))
        if "cancelled_24h_policy" in ops:
            parts.append("cancelled_24h_policy=" + str(int(ops.get("cancelled_24h_policy") or 0)))
        if "cancelled_24h_uncategorized" in ops:
            parts.append(
                "cancelled_24h_uncategorized="
                + str(int(ops.get("cancelled_24h_uncategorized") or 0))
            )
        if parts:
            bits.append(" ".join(parts))
    if ttc is not None and goal_wants_ttc(goal):
        line = (
            "p50="
            + str(float(ttc.get("p50") or 0.0))
            + " p95="
            + str(float(ttc.get("p95") or 0.0))
            + " samples="
            + str(int(ttc.get("samples") or 0))
            + " inflight_max="
            + str(float(ttc.get("inflight_max") or 0.0))
            + " inflight="
            + str(int(ttc.get("inflight_n") or 0))
        )
        by_reason = ttc.get("by_reason") or {}
        if by_reason:
            try:
                from src.agents.bridge.async_ttc import format_reason_p95_line
            except ImportError:
                from async_ttc import format_reason_p95_line

            extra = format_reason_p95_line(by_reason)
            if extra:
                line += " by_reason=" + extra
        bits.append(line)
    is_status_overview = "статус" in g and any(x in g for x in ("проект", "систем", "роя", "swarm"))
    if is_status_overview and not bits:
        # Сводный статус: компактный срез живых метрик (эталон status_project).
        healthy = (
            (health or "ok") == "ok" and queue is not None and int(queue.get("pending") or 0) == 0
        )
        bits.append(
            "Статус проекта: активная разработка идёт стабильно, сбоев нет."
            if healthy
            else "Статус проекта: активная разработка, но есть проблемы, требующие внимания."
        )
        if health:
            bits.append(f"health={health}")
        if queue is not None:
            bits.append(
                "pending="
                + str(int(queue.get("pending") or 0))
                + " in_progress="
                + str(int(queue.get("in_progress") or 0))
            )
        if ops is not None:
            bits.append(
                "failed_1h="
                + str(int(ops.get("failed_1h") or 0))
                + " completed_24h="
                + str(int(ops.get("completed_24h") or 0))
                + " error_rate_1h="
                + str(float(ops.get("error_rate_1h") or 0.0))
            )
        if nodes is not None:
            bits.append("knowledge_nodes=" + str(int(nodes)))
    if not bits:
        return None
    return bits[0] if len(bits) == 1 else " ".join(bits)


def is_fact_seeking_question(goal: str) -> bool:
    """Вопрос, на который нельзя отвечать из головы: порты, очередь, health, живой статус."""
    g = (goal or "").lower().strip()
    if not g:
        return False
    if g in ("кто ты", "кто ты?", "что ты умеешь", "что ты умеешь?"):
        return False

    # Fixed short-reply chat probes are never live-fact, even with ignore+metrics words
    # or incidental marker substrings in a fact preamble (INFLIGHT_STALE, TTC, :11437).
    if is_fixed_token_reply_probe(g):
        return False

    # Объяснительные/творческие цели — не fact-probe, даже если внутри есть
    # слово-маркер («объясни backpressure в очередях задач» ≠ «сколько в очереди»).
    # English mirrors: "what is ttc" / "explain ttc" must not dump live p50/p95.
    if any(
        g.startswith(v)
        for v in (
            "объясни",
            "что такое",
            "напиши",
            "найди",
            "расскажи",
            "сравни",
            "проанализируй",
            "разбери",
            "explain",
            "what is",
            "what's",
            "whats",
            "tell me about",
            "tell me what",
        )
    ):
        return False

    # Исключаем автоматические задачи (лог сканер, медицинские задачи и т.д.)
    # Эти задачи требуют реальной обработки, а не детерминированного ответа
    automated_prefixes = ["[log_scanner]", "[medic]", "[proactive]", "[feedback]"]
    if any(g.startswith(prefix) for prefix in automated_prefixes):
        return False

    # План/инструкция — это не live-fact probe даже при наличии метрик/портов.
    if any(marker in g for marker in FACT_PLANNING_EXCLUDE_MARKERS):
        return False

    # Исключаем задачи которые начинаются с маркера ошибки - это задачи на исправление
    if g.startswith("ошибка") or g.startswith("error") or g.startswith("исправь"):
        return False

    # Исключаем задачи с "ошибка" в контексте лог сканера или исправления
    # Если goal содержит "ошибка" и "контейнер" или "исправь" - это задача на исправление
    if "ошибка" in g and ("контейнер" in g or "исправь" in g or "log_scanner" in g):
        return False

    return any(m in g for m in FACT_SEEKING_MARKERS)


def is_introspection_goal(goal: str) -> bool:
    """Задача интроспекции (самоаудит Виктории от куратора): всегда deep_analysis.

    LLM-стратегия локально просит «уточните» для таких задач — у них нет
    конкретных файлов/инструментов, но они однозначны по определению. Issue #64.
    """
    g = (goal or "").lower()
    return any(m in g for m in ("самоаудит", "интроспекц", "честность отказов"))


def is_curator_standard_goal(goal: str) -> bool:
    """
    Запрос из списка кураторских эталонов: статус проекта, что умеешь, дашборд.
    Такие запросы не должны делегироваться в Veronica — только Enhanced (simple + RAG).
    """
    if not (goal or "").strip():
        return False
    g = (goal or "").lower().strip()
    if any(kw in g for kw in CURATOR_STANDARD_KEYWORDS):
        return True
    # «какой статус проекта?», «статус по проекту»
    if "статус" in g and ("проект" in g or "дашборд" in g):
        return True
    if "что" in g and "умеешь" in g:
        return True
    return False


# Категории, где ночные A/B-битвы показали выигрыш консилиума над соло
# (battle_20260922_205549: research 4-1, testing 4-0). Список — env, чтобы
# пополнять по данным новых битв без правки кода.
_CONSILIUM_CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    "research": (
        "объясни",
        "что такое",
        "расскажи",
        "чем отличается",
        "найди в интернете",
        "исследуй",
    ),
    "testing": (
        "тест",
        "чеклист",
        "покрытие",
        "smoke",
        "план проверки",
        "план регресса",
    ),
    "analysis": (
        "проанализируй",
        "разбери",
        "анализ",
    ),
    "security": (
        "безопасность",
        "security",
        "уязвимост",
        "вторжение",
        " prompt injection",
        "hardcoded секрет",
    ),
    # [v149.59] По данным битв (battle_20261007/20261010) консилиум выигрывает
    # code-категории у соло — добавляем code-паттерны (владелец: качество-first).
    "code": (
        "напиши код",
        "реализуй",
        "рефактор",
        "баг",
        "не работает код",
        "исправь функци",
        "оптимизируй код",
        "напиши функци",
        "напиши скрипт",
        "напиши тест",
        "python-скрипт",
        "sql-запрос",
    ),
}


def consilium_categories() -> tuple[str, ...]:
    raw = os.getenv("CONSILIUM_CATEGORIES", "research,testing,analysis,security")
    return tuple(x.strip() for x in raw.split(",") if x.strip() in _CONSILIUM_CATEGORY_PATTERNS)


def is_consilium_winnable_goal(goal: str) -> Optional[str]:
    """Категория, где консилиум (дебат) статистически выигрывает у соло — или None.

    Узкие паттерны: research — объяснительные глаголы в начале цели;
    testing — явные маркеры тест-планирования. Классификация нужна ДО
    стратегической LLM, поэтому только regex/keywords.
    """
    g = (goal or "").lower().strip()
    if not g:
        return None
    enabled = consilium_categories()
    if "research" in enabled:
        research_starters = _CONSILIUM_CATEGORY_PATTERNS["research"]
        if any(g.startswith(v) for v in research_starters) or "найди в интернете" in g:
            return "research"
    if "testing" in enabled:
        testing_markers = _CONSILIUM_CATEGORY_PATTERNS["testing"]
        if any(m in g for m in testing_markers):
            return "testing"
    if "analysis" in enabled:
        analysis_starters = _CONSILIUM_CATEGORY_PATTERNS["analysis"]
        if any(g.startswith(v) for v in analysis_starters) or any(
            v in g for v in analysis_starters
        ):
            return "analysis"
    if "security" in enabled:
        security_markers = _CONSILIUM_CATEGORY_PATTERNS["security"]
        if any(m in g for m in security_markers):
            return "security"
    return None


def _is_simple_veronica_request(goal: str) -> bool:
    """
    Запрос — одношаговое действие (показать/вывести/прочитать).
    Только такие запросы по задумке идут сразу в Veronica (руки); остальные — в enhanced (эксперты).
    """
    if not goal or len(goal.strip()) > 120:
        return False
    goal_lower = goal.lower().strip()
    if any(kw in goal_lower for kw in VERONICA_SIMPLE_KEYWORDS):
        return True
    # Короткая фраза типа «покажи файлы в src»
    if len(goal_lower) <= 50 and (
        "покажи" in goal_lower or "выведи" in goal_lower or "список" in goal_lower
    ):
        return True
    return False


def detect_task_type(goal: str, context: str = "") -> str:
    """
    Определяет тип задачи для маршрутизации:
    - simple_chat: приветствия, простые вопросы → быстрый путь (agent.run без Enhanced)
    - veronica: только простые одношаговые запросы (покажи файлы, выведи список) при PREFER_EXPERTS_FIRST
    - department_heads: аналитические/стратегические
    - enhanced: сложные задачи, execution через экспертов (по умолчанию для «сделай/напиши код»)
    """
    if not (goal or "").strip():
        return "simple_chat"
    goal_lower = goal.lower().strip()
    prefer_experts_first = os.getenv("PREFER_EXPERTS_FIRST", "true").lower() in ("true", "1", "yes")

    # Кураторские эталоны и operational execution — Enhanced (RAG/tools), не Veronica/Swarm
    if is_curator_standard_goal(goal) or is_operational_execution_goal(goal):
        return "enhanced"

    # Простые одношаговые запросы → Veronica (реальная роль: руки)
    if _is_simple_veronica_request(goal):
        return "veronica"

    # Исполнительные ключевые слова: при PREFER_EXPERTS_FIRST — в enhanced (эксперты первыми)
    for word in VERONICA_KEYWORDS:
        if word in goal_lower:
            if prefer_experts_first:
                return "enhanced"
            return "veronica"
    # Эвристики: код — при PREFER_EXPERTS_FIRST в enhanced
    if _is_code_related(goal_lower):
        return "enhanced" if prefer_experts_first else "veronica"

    # Аналитические
    for word in DEPARTMENT_HEADS_KEYWORDS:
        if word in goal_lower:
            return "department_heads"
    # Очень короткие фразы — чаще всего приветствие
    if len(goal_lower) <= 25 and any(k in goal_lower for k in SIMPLE_CHAT_KEYWORDS):
        return "simple_chat"
    # Явные приветствия
    for word in SIMPLE_CHAT_KEYWORDS:
        if word in goal_lower:
            return "simple_chat"
    # Эвристики: анализ
    if _is_analysis_related(goal_lower):
        return "department_heads"
    return "enhanced"


def _is_code_related(goal: str) -> bool:
    code_indicators = [
        "python",
        "javascript",
        "java",
        "код",
        "функция",
        "класс",
        "метод",
        "библиотека",
        "импорт",
        "компиляция",
        "дебаг",
        "тест",
        "lint",
    ]
    return any(i in goal for i in code_indicators)


def _is_analysis_related(goal: str) -> bool:
    analysis_indicators = [
        "данные",
        "анализ",
        "отчет",
        "отчёт",
        "график",
        "диаграмма",
        "статистика",
        "тренд",
        "паттерн",
        "корреляция",
        "прогноз",
        "рекомендация",
        "метрика",
        "insight",
    ]
    return any(i in goal for i in analysis_indicators)


def should_use_enhanced(goal: str, project_context: Optional[str], use_enhanced_env: bool) -> bool:
    """
    Решает, использовать ли Enhanced для данного запроса.
    Если env USE_VICTORIA_ENHANCED=true, но запрос — simple_chat, возвращаем False
    (быстрый ответ через agent.run без тяжёлого Enhanced).
    Operational/curator execution goals всегда идут в Enhanced (даже если env выключен),
    чтобы не попадать в зависающий in-process Swarm.
    """
    task_type = detect_task_type(goal or "", project_context or "")
    if task_type == "simple_chat":
        return False
    force_operational = os.getenv("VICTORIA_FORCE_ENHANCED_OPERATIONAL", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    if force_operational and (
        is_operational_execution_goal(goal) or is_curator_standard_goal(goal)
    ):
        return True
    if not use_enhanced_env:
        return False
    return True
