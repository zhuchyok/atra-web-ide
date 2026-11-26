#!/usr/bin/env python3
"""Subtract 1.0 from style GGUF F32 RMSNorms that are systematically day+1.0.

Does NOT touch victoria-qwen38:latest. Default: copy → *-mtp-normfix.gguf, patch in-place.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
from gguf import GGMLQuantizationType, GGUFReader

DAY_BLOB_DEFAULT = (
    Path.home()
    / ".ollama/models/blobs/sha256-a680f44a06920e5d689774823782006aa3acc8db95750323373b24139b67e348"
)
NORM_SUFFIXES = (
    "attn_norm.weight",
    "post_attention_norm.weight",
    "attn_q_norm.weight",
    "attn_k_norm.weight",
    "output_norm.weight",
)


def _is_norm(name: str) -> bool:
    return name == "output_norm.weight" or any(name.endswith(s) for s in NORM_SUFFIXES)


def patch(src: Path, day: Path, out: Path, *, delta_tol: float = 0.05) -> None:
    if out.resolve() == src.resolve():
        raise SystemExit("refusing in-place on source; pass a distinct --out")
    print(f"copy {src} → {out}", file=sys.stderr)
    shutil.copy2(src, out)

    donor = GGUFReader(str(day))
    day_map = {t.name: t for t in donor.tensors}
    reader = GGUFReader(str(out))

    patched = 0
    skipped = 0
    with open(out, "r+b") as fh:
        for t in reader.tensors:
            if not _is_norm(t.name):
                continue
            if t.tensor_type != GGMLQuantizationType.F32:
                skipped += 1
                continue
            d = day_map.get(t.name)
            if d is None or d.tensor_type != GGMLQuantizationType.F32:
                skipped += 1
                continue
            a = np.asarray(d.data, dtype=np.float32).ravel()
            b = np.asarray(t.data, dtype=np.float32).ravel()
            mean_delta = float((b - a).mean())
            if abs(mean_delta - 1.0) > delta_tol:
                print(f"skip {t.name} mean_delta={mean_delta:.4f}", file=sys.stderr)
                skipped += 1
                continue
            fixed = (b - 1.0).astype("<f4", copy=False)
            fh.seek(int(t.data_offset))
            fh.write(fixed.tobytes())
            patched += 1
        fh.flush()

    # verify
    chk = GGUFReader(str(out))
    bad = 0
    for t in chk.tensors:
        if not _is_norm(t.name) or t.tensor_type != GGMLQuantizationType.F32:
            continue
        d = day_map.get(t.name)
        if d is None:
            continue
        a = np.asarray(d.data, dtype=np.float32).ravel()
        b = np.asarray(t.data, dtype=np.float32).ravel()
        md = float((b - a).mean())
        if abs(md - 1.0) < delta_tol:
            bad += 1
            print(f"STILL+1 {t.name} md={md}", file=sys.stderr)
    print(f"OK patched={patched} skipped={skipped} still_plus1={bad} → {out}")
    if patched < 150 or bad:
        raise SystemExit("verify failed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--src",
        type=Path,
        default=Path("training_data/style_v1_fused_fp16/victoria-style-qwen38-q8_0-mtp.gguf"),
    )
    ap.add_argument("--day-blob", type=Path, default=DAY_BLOB_DEFAULT)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("training_data/style_v1_fused_fp16/victoria-style-qwen38-q8_0-mtp-normfix.gguf"),
    )
    args = ap.parse_args()
    if not args.src.is_file():
        raise SystemExit(f"missing {args.src}")
    if not args.day_blob.is_file():
        raise SystemExit(f"missing {args.day_blob}")
    patch(args.src, args.day_blob, args.out)


if __name__ == "__main__":
    main()
