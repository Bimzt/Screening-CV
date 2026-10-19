"""
Local Python Dev Server untuk CV Screener.
Menjalankan endpoint serverless Python di http://127.0.0.1:8000
sehingga Next.js dapat meneruskan permintaan /api/* selama pengembangan lokal.
Menggunakan modul bawaan Python (ThreadingHTTPServer) tanpa dependensi eksternal.
"""

import sys
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import importlib

# Pastikan root project dan folder api/ masuk ke sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(BASE_DIR, "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

# Baca .env.local jika ada
ENV_LOCAL = os.path.join(BASE_DIR, ".env.local")
if os.path.exists(ENV_LOCAL):
    with open(ENV_LOCAL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

# Map rute endpoint ke modul Python di folder api/
ROUTES = {
    "/api/hello": "hello",
    "/api/process": "process",
    "/api/rank": "rank",
    "/api/export": "export",
    "/api/evaluate": "evaluate",
}


class DevDispatcherHandler(BaseHTTPRequestHandler):
    def _dispatch(self, method: str):
        path = self.path.split("?")[0].rstrip("/")
        module_name = ROUTES.get(path)

        if not module_name:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Endpoint dev tidak ditemukan"}')
            return

        try:
            # Auto-reload submodul _lib dan endpoint handler secara dinamis saat pengembangan
            for sub in ["_lib.excel", "_lib.scoring", "_lib.auth", "_lib.drive", "_lib.extraction"]:
                if sub in sys.modules:
                    try:
                        importlib.reload(sys.modules[sub])
                    except Exception:
                        pass

            if module_name in sys.modules:
                mod = importlib.reload(sys.modules[module_name])
            else:
                mod = importlib.import_module(module_name)

            handler_class = getattr(mod, "handler")
            
            # Buat instance handler dan jalankan method yang sesuai
            # Karena BaseHTTPRequestHandler.__init__ memanggil handle(),
            # kita delegasikan self secara langsung
            handler_instance = handler_class.__new__(handler_class)
            handler_instance.request = self.request
            handler_instance.client_address = self.client_address
            handler_instance.server = self.server
            handler_instance.rfile = self.rfile
            handler_instance.wfile = self.wfile
            handler_instance.headers = self.headers
            handler_instance.command = self.command
            handler_instance.path = self.path
            handler_instance.request_version = self.request_version
            handler_instance.requestline = getattr(self, "requestline", f"{method} {self.path} HTTP/1.1")
            handler_instance.close_connection = self.close_connection
            handler_instance.server_version = self.server_version
            handler_instance.sys_version = self.sys_version
            handler_instance.protocol_version = self.protocol_version
            
            # Eksekusi method do_GET, do_POST, dll.
            handler_func = getattr(handler_instance, f"do_{method}", None)
            if handler_func:
                handler_func()
            else:
                self.send_response(405)
                self.end_headers()
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            msg = f'{{"status": "error", "message": "Internal Server Error di {module_name}: {str(e)}"}}'
            self.wfile.write(msg.encode("utf-8"))

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_OPTIONS(self):
        # Handle CORS preflight jika dipanggil langsung
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Requested-With, X-CV-Screener")
        self.end_headers()


def run(port: int = 8000):
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, DevDispatcherHandler)
    print(f"[*] Python Dev Server aktif di http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server dihentikan.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run(port)
