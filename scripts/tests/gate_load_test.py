#!/usr/bin/env python3
"""Нагрузочный тест universal gate (v149.26): /api/tags латентность под генеративной нагрузкой.
Гейт.local_router:1818 берёт /api/tags с timeout=3.0s. Если tags > 3s → фолбэк на хардкоды.
Нагрузка: 10x phi3.5 на 11434 + 6x fast на 11435 (короткие генерации)."""
import json, time, threading, urllib.request, urllib.error, statistics

STOP = time.time() + 50
tags_lat = {11434: [], 11435: []}
tags_fail = {11434: 0, 11435: 0}
gen_stats = {11434: {"ok": 0, "err": 0, "lat": []}, 11435: {"ok": 0, "err": 0, "lat": []}}
lock = threading.Lock()

def gen_worker(port, model):
    body = json.dumps({"model": model, "prompt": "Say ok", "stream": False,
                       "options": {"num_predict": 5, "num_ctx": 2048, "temperature": 0}}).encode()
    while time.time() < STOP:
        t0 = time.time()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/generate", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                r.read()
            dt = time.time() - t0
            with lock:
                gen_stats[port]["ok"] += 1; gen_stats[port]["lat"].append(dt)
        except Exception as e:
            with lock:
                gen_stats[port]["err"] += 1; gen_stats[port]["lat"].append(time.time() - t0)
        time.sleep(0.3)

def tags_monitor():
    while time.time() < STOP:
        for port in (11434, 11435):
            t0 = time.time()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/tags", timeout=10) as r:
                    r.read()
                with lock:
                    tags_lat[port].append(time.time() - t0)
            except Exception:
                with lock:
                    tags_fail[port] += 1
        time.sleep(2)

def ps_models(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ps", timeout=5) as r:
            return [m.get("name") for m in json.load(r).get("models", [])]
    except Exception as e:
        return [f"ERR {e}"]

def pct(xs, p):
    if not xs: return float("nan")
    xs = sorted(xs); k = min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))
    return xs[k]

print("BEFORE 11434 ps:", ps_models(11434))
print("BEFORE 11435 ps:", ps_models(11435))
threads = [threading.Thread(target=gen_worker, args=(11434, "phi3.5:3.8b"), daemon=True) for _ in range(10)]
threads += [threading.Thread(target=gen_worker, args=(11435, "fast"), daemon=True) for _ in range(6)]
threads.append(threading.Thread(target=tags_monitor, daemon=True))
t_start = time.time()
for t in threads: t.start()
while time.time() < STOP: time.sleep(2)
print("\n=== РЕЗУЛЬТАТЫ (нагрузка ~50с) ===")
for port in (11434, 11435):
    lats = tags_lat[port]
    print(f"tags :{port} n={len(lats)} fail={tags_fail[port]} p50={pct(lats,50)*1000:.0f}ms "
          f"p95={pct(lats,95)*1000:.0f}ms max={max(lats)*1000:.0f}ms" if lats else f"tags :{port} НЕТ ДАННЫХ")
    g = gen_stats[port]
    gl = g["lat"]
    print(f"gen  :{port} ok={g['ok']} err={g['err']} p50={pct(gl,50):.1f}s p95={pct(gl,95):.1f}s max={max(gl):.1f}s" if gl else f"gen :{port} нет")
print("AFTER 11434 ps:", ps_models(11434))
print("AFTER 11435 ps:", ps_models(11435))
