#!/usr/bin/env python3
"""
Evaluate LoRA readiness gate from generated dataset manifest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default="knowledge_os/training_data/lora_dataset_manifest.json",
    )
    parser.add_argument("--min-train-samples", type=int, default=2000)
    parser.add_argument("--min-eval-samples", type=int, default=200)
    parser.add_argument("--report", default="docs/audits/lora-readiness-gate.md")
    parser.add_argument(
        "--fuse-target",
        default="",
        help="Base model path/tag for Wave-4 promote (qwen38 family).",
    )
    parser.add_argument(
        "--require-fuse",
        action="store_true",
        help="Fail unless fuse_target matches victoria-qwen38 / Qwen3.8 family.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    distilled_pct = float(data.get("distilled_pct") or 0.0)
    # Style corpus may set required_distilled_pct=0.0 — do not treat 0 as "missing".
    if "required_distilled_pct" in data and data.get("required_distilled_pct") is not None:
        required_pct = float(data.get("required_distilled_pct"))
    else:
        required_pct = 50.0
    train_samples = int(data.get("train_samples") or 0)
    eval_samples = int(data.get("eval_samples") or 0)
    gate_distilled = distilled_pct >= required_pct
    gate_train = train_samples >= args.min_train_samples
    gate_eval = eval_samples >= args.min_eval_samples
    # Wave 4: volume PASS ≠ fuse-ready. Refuse known wrong bases for promote.
    fuse_target = str(
        data.get("fuse_target") or data.get("base_model") or args.fuse_target or ""
    ).strip()
    allowed = tuple(
        data.get("fuse_target_required") or ["qwen3.8", "victoria-qwen38", "Qwen3.8", "Qwen3-8"]
    )
    blocked = ("llama-3.2-3b", "qwen2.5-3b", "llama3.2")
    fuse_lower = fuse_target.lower()
    fuse_ok = bool(fuse_target) and any(a.lower() in fuse_lower for a in allowed)
    fuse_blocked = any(b in fuse_lower for b in blocked)
    gate_fuse = fuse_ok and not fuse_blocked
    # Volume gate (legacy) vs Wave-4 promote gate (volume + fuse).
    gate_volume = gate_distilled and gate_train and gate_eval
    gate_pass = (gate_volume and gate_fuse) if args.require_fuse else gate_volume

    report = [
        "# LoRA Readiness Gate",
        "",
        f"- distilled_pct: `{distilled_pct:.2f}`",
        f"- required_distilled_pct: `{required_pct:.2f}`",
        f"- train_samples: `{train_samples}` (min `{args.min_train_samples}`)",
        f"- eval_samples: `{eval_samples}` (min `{args.min_eval_samples}`)",
        f"- fuse_target: `{fuse_target or '(unset)'}`",
        "",
        "## Gate checks",
        f"- distillation_gate: `{gate_distilled}`",
        f"- train_size_gate: `{gate_train}`",
        f"- eval_size_gate: `{gate_eval}`",
        f"- fuse_target_ok: `{gate_fuse}` (blocked_wrong_base=`{fuse_blocked}`)",
        f"- volume_gate: `{gate_volume}`",
        "",
        f"## Final verdict: `{'PASS' if gate_pass else 'FAIL'}`",
        "",
        "Note: volume PASS alone must not promote into live victoria-qwen38.",
    ]

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
