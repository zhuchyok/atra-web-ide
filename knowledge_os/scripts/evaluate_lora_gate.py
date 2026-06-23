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
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    distilled_pct = float(data.get("distilled_pct") or 0.0)
    required_pct = float(data.get("required_distilled_pct") or 50.0)
    train_samples = int(data.get("train_samples") or 0)
    eval_samples = int(data.get("eval_samples") or 0)
    gate_distilled = distilled_pct >= required_pct
    gate_train = train_samples >= args.min_train_samples
    gate_eval = eval_samples >= args.min_eval_samples
    gate_pass = gate_distilled and gate_train and gate_eval

    report = [
        "# LoRA Readiness Gate",
        "",
        f"- distilled_pct: `{distilled_pct:.2f}`",
        f"- required_distilled_pct: `{required_pct:.2f}`",
        f"- train_samples: `{train_samples}` (min `{args.min_train_samples}`)",
        f"- eval_samples: `{eval_samples}` (min `{args.min_eval_samples}`)",
        "",
        "## Gate checks",
        f"- distillation_gate: `{gate_distilled}`",
        f"- train_size_gate: `{gate_train}`",
        f"- eval_size_gate: `{gate_eval}`",
        "",
        f"## Final verdict: `{'PASS' if gate_pass else 'FAIL'}`",
    ]

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
