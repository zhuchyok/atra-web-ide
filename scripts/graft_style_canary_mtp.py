#!/usr/bin/env python3
"""Graft Unsloth day MTP blk.64.* tensors into style LoRA GGUF for ollama 0.33.

Does NOT touch victoria-qwen38:latest. Writes a sibling *-mtp.gguf by default.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from gguf import GGUFReader, GGUFValueType, GGUFWriter

MTP_PREFIX = "blk.64."
DAY_BLOB_DEFAULT = (
    Path.home()
    / ".ollama/models/blobs/sha256-a680f44a06920e5d689774823782006aa3acc8db95750323373b24139b67e348"
)

SKIP_KEYS = {
    "GGUF.version",
    "GGUF.tensor_count",
    "GGUF.kv_count",
    "general.architecture",  # GGUFWriter ctor
    "qwen35.block_count",
    "qwen35.nextn_predict_layers",
}


def _add_scalar(writer: GGUFWriter, key: str, t: GGUFValueType, val) -> None:
    dispatch = {
        GGUFValueType.STRING: writer.add_string,
        GGUFValueType.UINT8: writer.add_uint8,
        GGUFValueType.INT8: writer.add_int8,
        GGUFValueType.UINT16: writer.add_uint16,
        GGUFValueType.INT16: writer.add_int16,
        GGUFValueType.UINT32: writer.add_uint32,
        GGUFValueType.INT32: writer.add_int32,
        GGUFValueType.UINT64: writer.add_uint64,
        GGUFValueType.INT64: writer.add_int64,
        GGUFValueType.FLOAT32: writer.add_float32,
        GGUFValueType.FLOAT64: writer.add_float64,
        GGUFValueType.BOOL: writer.add_bool,
    }
    fn = dispatch.get(t)
    if fn is None:
        raise ValueError(f"unsupported scalar {key} type={t}")
    fn(key, val)


def _copy_field(writer: GGUFWriter, field) -> None:
    if field.name in SKIP_KEYS:
        return
    types = list(field.types or [])
    if not types:
        return
    if types[0] == GGUFValueType.ARRAY:
        writer.add_array(field.name, field.contents())
        return
    val = field.contents()
    _add_scalar(writer, field.name, types[0], val)


def graft(canary: Path, day: Path, out: Path) -> None:
    src = GGUFReader(str(canary))
    donor = GGUFReader(str(day))
    mtp = [t for t in donor.tensors if t.name.startswith(MTP_PREFIX)]
    if len(mtp) != 15:
        raise SystemExit(f"expected 15 MTP tensors from day, got {len(mtp)}")

    arch = None
    for f in src.fields.values():
        if f.name == "general.architecture":
            arch = f.contents()
            break
    if arch != "qwen35":
        raise SystemExit(f"unexpected arch {arch!r}")

    if out.exists():
        out.unlink()

    writer = GGUFWriter(str(out), arch)
    for f in src.fields.values():
        try:
            _copy_field(writer, f)
        except Exception as e:
            print(f"FATAL field {f.name}: {e}", file=sys.stderr)
            raise

    writer.add_uint32("qwen35.block_count", 65)
    writer.add_uint32("qwen35.nextn_predict_layers", 1)

    for t in src.tensors:
        if t.name.startswith(MTP_PREFIX):
            continue
        writer.add_tensor(t.name, t.data, raw_dtype=t.tensor_type)

    for t in mtp:
        writer.add_tensor(t.name, t.data, raw_dtype=t.tensor_type)
        print(f"graft {t.name} shape={tuple(t.shape)} type={t.tensor_type}", file=sys.stderr)

    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file(progress=True)
    writer.close()

    # verify
    chk = GGUFReader(str(out))
    bc = chk.fields["qwen35.block_count"].contents()
    nxt = chk.fields["qwen35.nextn_predict_layers"].contents()
    n_mtp = sum(1 for t in chk.tensors if t.name.startswith(MTP_PREFIX))
    print(
        f"OK wrote {out} ({out.stat().st_size / 1e9:.2f}G) "
        f"block_count={bc} nextn={nxt} mtp_tensors={n_mtp} total={len(chk.tensors)}"
    )
    if bc != 65 or nxt != 1 or n_mtp != 15:
        raise SystemExit("verify failed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--canary",
        type=Path,
        default=Path("training_data/style_v1_fused_fp16/victoria-style-qwen38-q8_0.gguf"),
    )
    ap.add_argument("--day-blob", type=Path, default=DAY_BLOB_DEFAULT)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("training_data/style_v1_fused_fp16/victoria-style-qwen38-q8_0-mtp.gguf"),
    )
    ap.add_argument("--inplace", action="store_true", help="Replace canary path after backup")
    args = ap.parse_args()
    if not args.canary.is_file():
        raise SystemExit(f"missing canary gguf {args.canary}")
    if not args.day_blob.is_file():
        raise SystemExit(f"missing day blob {args.day_blob}")
    graft(args.canary, args.day_blob, args.out)
    if args.inplace:
        bak = args.canary.with_suffix(".gguf.PRE_MTP")
        if not bak.exists():
            shutil.copy2(args.canary, bak)
            print(f"backup {bak}")
        shutil.move(str(args.out), str(args.canary))
        print(f"replaced {args.canary}")


if __name__ == "__main__":
    main()
