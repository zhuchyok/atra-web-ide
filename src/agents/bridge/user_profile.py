"""USER.md profile loader for Victoria prompt inject (Hermes USER pattern).

Only USER.md is injected — never SOUL.md.

Truncation / noise policy:
- If stripped USER.md fits in max_chars → inject it whole (after light fluff strip).
- If oversized/noisy → prefer markdown sections whose headings match
  priorities / preferences (EN + RU: priority|priorities|preference|preferences|
  приоритет|предпочтен); if those are empty/still long → first N chars at a
  line boundary.
Missing file / IO errors: fail-open → empty string.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_PRIORITY_HEADING_RE = re.compile(
    r"(?im)^#{1,6}\s*.*(?:priorit(?:y|ies)|preferences?|приоритет\w*|предпочтен\w*).*$"
)


def user_profile_inject_enabled() -> bool:
    """USER_PROFILE_INJECT defaults to true."""
    return os.getenv("USER_PROFILE_INJECT", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def resolve_user_profile_path() -> Path:
    override = (os.getenv("VICTORIA_USER_PROFILE_PATH") or "").strip()
    if override:
        return Path(override)
    # Prefer CWD (container / repo root), then walk up from this file.
    candidates = [
        Path.cwd() / "knowledge_os" / "USER.md",
        Path(__file__).resolve().parents[3] / "knowledge_os" / "USER.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def _truncate_at_line(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    cut = text.rfind("\n", 0, max_chars)
    if cut < max_chars // 2:
        cut = max_chars
    return text[:cut].rstrip()


def _extract_priority_sections(text: str) -> str:
    """Keep only priorities/preferences sections when present."""
    matches = list(_PRIORITY_HEADING_RE.finditer(text))
    if not matches:
        return ""
    chunks: list[str] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # Extend end to next heading of any level after this section body.
        rest = text[start:end]
        # If we matched only priority headings, body may include following
        # non-priority content until the next priority heading — trim at any
        # subsequent markdown heading that is not itself a priority match.
        lines = rest.splitlines(keepends=True)
        kept: list[str] = []
        for idx, line in enumerate(lines):
            if idx == 0:
                kept.append(line)
                continue
            if re.match(r"^#{1,6}\s+", line) and not _PRIORITY_HEADING_RE.match(line):
                break
            kept.append(line)
        chunk = "".join(kept).strip()
        if chunk:
            chunks.append(chunk)
    return "\n\n".join(chunks).strip()


def _strip_fluff(text: str) -> str:
    """Light cleanup: drop empty lines runs and leading title-only noise."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    # Drop a leading "# USER.md ..." banner if present; keep content sections.
    while lines and (not lines[0].strip() or re.match(r"(?i)^#\s*user\.md\b", lines[0])):
        lines.pop(0)
    cleaned: list[str] = []
    blank_run = 0
    for ln in lines:
        if not ln.strip():
            blank_run += 1
            if blank_run > 1:
                continue
            cleaned.append("")
        else:
            blank_run = 0
            cleaned.append(ln)
    return "\n".join(cleaned).strip()


def load_user_profile(max_chars: int = 1500) -> str:
    """Read USER.md (or VICTORIA_USER_PROFILE_PATH). Fail-open on missing/errors."""
    path = resolve_user_profile_path()
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if not raw or not raw.strip():
        return ""

    body = _strip_fluff(raw)
    if not body:
        return ""
    if len(body) <= max_chars:
        return body
    preferred = _strip_fluff(_extract_priority_sections(raw))
    if preferred:
        return _truncate_at_line(preferred, max_chars)
    return _truncate_at_line(body, max_chars)


def format_user_profile_block(profile: str) -> str:
    """Prefix block for project_prompt inject."""
    text = (profile or "").strip()
    if not text:
        return ""
    return f"\nUSER PROFILE (owner):\n{text}\n"
