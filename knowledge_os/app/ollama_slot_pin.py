from typing import Any, Dict, Optional, Union

BRAIN_MARKERS = ("victoria-qwen38", "qwen3.8")
CODER_MARKERS = ("qwen3-coder", "qwen2.5-coder")
SMALL_MARKERS = ("nomic", "tinyllama", "moondream")


def pinned_num_ctx(model_name: Optional[str]) -> int:
    key = (model_name or "").lower()
    if "phi3.5:3.8b-stable" in key or key.endswith("-stable"):
        return 2048
    if "phi3.5" in key or key.startswith("phi3"):
        return 8192
    if any(m in key for m in SMALL_MARKERS):
        return 2048
    if any(m in key for m in CODER_MARKERS):
        return 16384
    return 16384


def pinned_keep_alive(model_name: Optional[str]) -> Union[int, str]:
    key = (model_name or "").lower()
    if any(m in key for m in BRAIN_MARKERS):
        return "24h"
    return -1


def pinned_options(
    model_name: Optional[str], extra: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    options: Dict[str, Any] = {"num_ctx": pinned_num_ctx(model_name)}
    if extra:
        for k, v in extra.items():
            if k == "num_ctx":
                continue
            options[k] = v
    return options
