#!/usr/bin/env python3
"""
Замер до/после для cache_normalizer (Фаза 3.4 плана).
Вызывает normalize_and_hash в цикле (по умолчанию 1000 текстов), замеряет время.
Запуск: с установленным Rust-модулем и без — сравнить время.

  cd knowledge_os/scripts
  # С Rust (из venv knowledge_os):
  ../.venv/bin/python benchmark_cache_normalizer.py
  # Без Rust (pip uninstall cache_normalizer в venv):
  ../.venv/bin/python benchmark_cache_normalizer.py
"""
import hashlib
import os
import sys
import time

# Опционально Rust-модуль (без зависимости от embedding_optimizer/asyncpg)
try:
    from cache_normalizer import normalize_and_hash as do_hash
    _USE_RUST = True
except ImportError:
    _USE_RUST = False

    def do_hash(text: str) -> str:
        normalized = ' '.join(text.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()


N_TEXTS = int(os.getenv('BENCHMARK_N_TEXTS', '1000'))
SAMPLE_TEXTS = [
    "Как настроить Victoria для проекта atra?",
    "Explain the architecture of Knowledge OS collective memory system and how traces are stored.",
    "Кратко: что такое stigmergy в контексте агентов?",
    "A" * 200,
    "Normalize and hash this string for cache key generation. " * 10,
]


def main():
    texts = [SAMPLE_TEXTS[i % len(SAMPLE_TEXTS)] for i in range(N_TEXTS)]
    start = time.perf_counter()
    for t in texts:
        do_hash(t)
    elapsed = time.perf_counter() - start

    rust_status = "Rust (cache_normalizer)" if _USE_RUST else "Python (fallback)"
    print(f"[benchmark_cache_normalizer] {N_TEXTS} calls, {rust_status}")
    print(f"  Total: {elapsed:.3f}s, per call: {elapsed/N_TEXTS*1000:.3f} ms")
    return 0


if __name__ == '__main__':
    sys.exit(main())
