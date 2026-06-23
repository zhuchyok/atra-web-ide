#!/usr/bin/env python3
"""
Runtime DI guard.

Detects constructor-style calls inside functions/methods in runtime code and
highlights places where dependencies are instantiated ad-hoc instead of via providers.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


DEFAULT_TARGETS = [
    "backend/app",
    "knowledge_os/app",
    "src/agents",
]

EXCLUDED_PARTS = {
    "__pycache__",
    "tests",
    "test",
    "knowledge_base",
    "venv",
    "node_modules",
}

# Allowed constructors that are typically value objects, response wrappers,
# or framework-level objects that are acceptable inline.
ALLOWED_CALLS = {
    "Depends",
    "Field",
    "HTTPException",
    "JSONResponse",
    "PlainTextResponse",
    "StreamingResponse",
    "HTMLResponse",
    "Response",
    "Path",
    "Query",
    "Body",
    "File",
    "UploadFile",
    "ValueError",
    "TypeError",
    "RuntimeError",
    "Exception",
    "TimeoutError",
    "ValidationError",
    "ImportError",
}

ALLOWED_SUFFIXES = (
    "Request",
    "Response",
    "Result",
    "Status",
    "Config",
    "Model",
    "Schema",
    "Error",
    "Exception",
    "Info",
    "Payload",
    "Params",
)

PROVIDER_FN_PREFIXES = ("get_", "_get_", "build_", "create_", "make_")

HEAVY_CALLS = {
    "LocalAIRouter",
    "RedisManager",
    "KnowledgeDistiller",
    "SyntheticDataGenerator",
    "TrainingPipeline",
    "SwarmOrchestrator",
    "MetaArchitect",
    "EvolutionMonitor",
    "CuriosityEngine",
    "MemoryConsolidator",
    "MultiClusterBridge",
    "ServerKnowledgeSync",
    "KnowledgeArchiver",
    "KnowledgeOSClient",
    "RAGLightService",
    "AutoOptimizer",
    "VictoriaEnhanced",
    "IntegrationBridge",
    "ThreadPoolExecutor",
    "ProcessPoolExecutor",
}


@dataclass
class Finding:
    file: str
    function: str
    line: int
    call: str


def _load_allowlist(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _is_ignored(finding: Finding, allowlist: list[dict]) -> bool:
    for entry in allowlist:
        file_match = entry.get("file")
        fn_match = entry.get("function")
        call_match = entry.get("call")
        if file_match and file_match != finding.file:
            continue
        if fn_match and fn_match != finding.function:
            continue
        if call_match and call_match != finding.call:
            continue
        return True
    return False


def _iter_py_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        yield path


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _scan_file(
    path: Path,
    repo_root: Path,
    mode: str,
    focus_calls: set[str],
    allow_calls: set[str],
    allowlist: list[dict],
) -> List[Finding]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    findings: List[Finding] = []
    rel = str(path.relative_to(repo_root))
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            call = _call_name(node.func)
            if not call:
                continue
            # Heuristic: class-like constructor call
            if not call[:1].isupper():
                continue
            if fn.name.startswith(PROVIDER_FN_PREFIXES):
                continue
            if call in ALLOWED_CALLS:
                continue
            if call in allow_calls:
                continue
            if call.endswith(ALLOWED_SUFFIXES):
                continue
            if mode == "heavy" and call not in HEAVY_CALLS:
                continue
            if focus_calls and call not in focus_calls:
                continue
            finding = Finding(
                file=rel,
                function=fn.name,
                line=node.lineno,
                call=call,
            )
            if _is_ignored(finding, allowlist):
                continue
            findings.append(finding)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="DI runtime guard")
    parser.add_argument(
        "--targets",
        nargs="*",
        default=DEFAULT_TARGETS,
        help="Relative directories to scan",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON report",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit non-zero when findings exist",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max findings to print",
    )
    parser.add_argument(
        "--mode",
        choices=("heavy", "all"),
        default="heavy",
        help="Guard mode: heavy (high-signal constructors) or all.",
    )
    parser.add_argument(
        "--focus-calls",
        nargs="*",
        default=[],
        help="Optional constructor names to focus on (overrides broad scan).",
    )
    parser.add_argument(
        "--allow-calls",
        nargs="*",
        default=[],
        help="Constructor names to ignore additionally.",
    )
    parser.add_argument(
        "--allowlist-file",
        default="scripts/di_runtime_guard_allowlist.json",
        help="JSON allowlist with optional keys: file, function, call.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    findings: List[Finding] = []
    scanned_files = 0
    focus_calls = {x for x in args.focus_calls if x}
    allow_calls = {x for x in args.allow_calls if x}
    allowlist_path = (repo_root / args.allowlist_file).resolve()
    allowlist = _load_allowlist(allowlist_path)

    for target in args.targets:
        target_path = repo_root / target
        if not target_path.exists():
            continue
        for py_file in _iter_py_files(target_path):
            scanned_files += 1
            findings.extend(
                _scan_file(
                    py_file,
                    repo_root,
                    mode=args.mode,
                    focus_calls=focus_calls,
                    allow_calls=allow_calls,
                    allowlist=allowlist,
                )
            )

    if args.json:
        payload = {
            "scanned_files": scanned_files,
            "findings_count": len(findings),
            "findings": [f.__dict__ for f in findings[: args.limit]],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"scanned_files={scanned_files}")
        print(f"findings_count={len(findings)}")
        for f in findings[: args.limit]:
            print(f"{f.file}:{f.line} {f.function} -> {f.call}()")
        if len(findings) > args.limit:
            print(f"... truncated {len(findings) - args.limit} findings")

    if args.enforce and findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
