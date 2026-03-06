import os
import time
import subprocess
import requests
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(os.path.expanduser("~/Library/Logs/atra-recovery-listener.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PORT = 9099
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class RecoveryHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, body: dict):
        import json
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_GET(self):
        if self.path == '/recover' or self.path == '/':
            self._send_json(200, {"status": "ok", "service": "recovery-listener", "port": PORT})
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == '/recover':
            content_length = int(self.headers.get('Content-Length', 0) or 0)
            post_data = self.rfile.read(content_length).decode('utf-8', errors='ignore') if content_length else ''
            logger.info(f"📥 Получен сигнал на восстановление: {post_data}")

            try:
                # Запуск скрипта самовосстановления
                script_path = os.path.join(ROOT_DIR, "scripts", "system_auto_recovery.sh")
                logger.info(f"🚀 Запуск дефибриллятора: {script_path}")

                # Запускаем в фоне, чтобы не блокировать HTTP ответ
                subprocess.Popen(["bash", script_path], start_new_session=True)

                self._send_json(200, {"status": "recovery_initiated"})
            except Exception as e:
                logger.error(f"❌ Ошибка при запуске восстановления: {e}")
                self._send_json(500, {"status": "error", "message": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Подавляем стандартные логи HTTP сервера в консоль
        return

def run_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, RecoveryHandler)
    logger.info(f"📡 Recovery Listener запущен на порту {PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Recovery Listener остановлен")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
