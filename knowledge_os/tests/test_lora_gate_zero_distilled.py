"""Style corpus may set required_distilled_pct=0.0 — must not coerce to 50."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "knowledge_os" / "scripts" / "evaluate_lora_gate.py"


def test_zero_required_distilled_passes_distillation_gate():
    with tempfile.TemporaryDirectory() as td:
        man = Path(td) / "manifest.json"
        man.write_text(
            json.dumps(
                {
                    "distilled_pct": 0.0,
                    "required_distilled_pct": 0.0,
                    "train_samples": 250,
                    "eval_samples": 50,
                }
            ),
            encoding="utf-8",
        )
        report = Path(td) / "gate.md"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--manifest",
                str(man),
                "--min-train-samples",
                "200",
                "--min-eval-samples",
                "40",
                "--report",
                str(report),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        out = proc.stdout + proc.stderr
        assert "distillation_gate: `True`" in out
        assert "Final verdict: `PASS`" in out
        assert "required_distilled_pct: `0.00`" in out
