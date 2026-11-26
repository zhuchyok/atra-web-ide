"""Style corpus valid split must keep refusals+facts (LoRA canary blind-spot fix)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "configs" / "training" / "style_v1" / "manifest.json"
BUILDER = ROOT / "scripts" / "build_lora_style_corpus.py"


def test_builder_has_stratified_split():
    text = BUILDER.read_text(encoding="utf-8")
    assert "def _stratified_split" in text
    assert "valid must keep refusals" in text
    assert "_refusal_prompts" in text


def test_live_manifest_keeps_refusal_and_fact_in_valid():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    split = data.get("bucket_split") or {}
    assert split.get("refusal", {}).get("valid", 0) >= 1
    assert split.get("fact", {}).get("valid", 0) >= 1
    assert int(data.get("train_samples") or 0) >= 200
    assert int(data.get("eval_samples") or 0) >= 40
