#!/usr/bin/env python3
"""
Тест API ATRA Web IDE: /, /health, /api/domains, /api/knowledge, /api/experts

Режимы:
  1) Через живой сервер (рекомендуется):
     python scripts/test_all.py --live http://127.0.0.1:8080
     Сначала запустите backend: cd backend && uvicorn app.main:app --port 8080

  2) Через TestClient (только / и /health; domains/knowledge/experts с БД — через --live):
     PYTHONPATH=backend backend/.venv/bin/python scripts/test_all.py
"""
import argparse
import json
import os
import sys

try:
    import httpx
except ImportError:
    httpx = None


def run_live(base: str):
    """Тесты через HTTP к живому серверу."""
    base = base.rstrip("/")
    client = httpx.Client(base_url=base, timeout=30.0)

    def get(path):
        return client.get(path)

    r = get("/")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "endpoints" in d and "domains" in d["endpoints"] and "knowledge" in d["endpoints"]
    print("  GET /             OK")

    r = get("/health")
    assert r.status_code == 200, r.text
    assert "status" in r.json()
    print("  GET /health       OK")

    r = get("/api/domains/")
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d, list)
    print(f"  GET /api/domains/ OK ({len(d)} domains)")

    r = get("/api/knowledge?q=test&limit=5")
    assert r.status_code == 200, f"status={r.status_code} body={r.text[:300]}"
    d = r.json()
    assert isinstance(d, list)
    print(f"  GET /api/knowledge?q=test OK ({len(d)} items)")

    r = get("/api/knowledge")
    assert r.status_code == 422
    print("  GET /api/knowledge (no q) 422 OK")

    r = get("/api/experts/")
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d, list)
    print(f"  GET /api/experts/ OK ({len(d)} experts)")

    client.close()


def run_testclient():
    """Тесты через TestClient (/, /health без БД)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backend = os.path.join(root, "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    os.chdir(backend)

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    r = client.get("/")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "endpoints" in d and "domains" in d["endpoints"] and "knowledge" in d["endpoints"]
    print("  GET /             OK")

    r = client.get("/health")
    assert r.status_code == 200, r.text
    assert "status" in r.json()
    print("  GET /health       OK")

    print("  (domains/knowledge/experts — используйте --live http://HOST:PORT)")


def main():
    ap = argparse.ArgumentParser(description="ATRA Web IDE API tests")
    ap.add_argument("--live", metavar="URL", help="Базовый URL живого backend (например http://127.0.0.1:8080)")
    args = ap.parse_args()

    print("ATRA Web IDE API tests")
    print("-" * 40)

    if args.live:
        if not httpx:
            print("  pip install httpx для --live")
            sys.exit(1)
        run_live(args.live)
    else:
        run_testclient()

    print("-" * 40)
    print("All tests passed.")


if __name__ == "__main__":
    main()
