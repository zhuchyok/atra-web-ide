#!/usr/bin/env python3
"""
Слушатель на хосте для «живого организма»: оркестратор в Docker при недоступности
Ollama/MLX шлёт POST сюда — хост запускает восстановление (Ollama, MLX, контейнеры).

Запуск на хосте (Mac Studio):
  python3 scripts/host_recovery_listener.py
  # или в фоне: nohup python3 scripts/host_recovery_listener.py >> /tmp/host_recovery_listener.log 2>&1 &

Оркестратору в docker-compose задать:
  RECOVERY_WEBHOOK_URL: http://host.docker.internal:9099/recover

Порт по умолчанию 9099 (можно RECOVERY_LISTENER_PORT=9100).
"""
import json
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PORT = int(os.getenv("RECOVERY_LISTENER_PORT", "9099"))


class RecoveryHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/recover" and not self.path.rstrip("/").endswith("recover"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length).decode("utf-8", errors="ignore") if length else "{}"
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}
        ollama_ok = data.get("ollama", True)
        mlx_ok = data.get("mlx", True)
        # Запускаем полное самовосстановление (Ollama, MLX, контейнеры)
        script = os.path.join(ROOT, "scripts", "system_auto_recovery.sh")
        ran = False
        if os.path.isfile(script) and os.access(script, os.X_OK):
            try:
                subprocess.Popen(
                    ["/bin/bash", script],
                    cwd=ROOT,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                ran = True
            except Exception:
                pass
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {"ok": True, "recovery_triggered": ran, "ollama": ollama_ok, "mlx": mlx_ok}
            ).encode("utf-8")
        )

    def log_message(self, format, *args):
        print("[host_recovery_listener]", format % args, file=sys.stderr)


def main():
    server = HTTPServer(("0.0.0.0", PORT), RecoveryHandler)
    print(f"Host recovery listener on 0.0.0.0:{PORT} (POST /recover)", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()
