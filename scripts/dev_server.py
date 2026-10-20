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

import threading

# Map rute endpoint ke modul Python di folder api/
ROUTES = {
    "/api/hello": "hello",
    "/api/process": "process",
    "/api/rank": "rank",
    "/api/export": "export",
    "/api/evaluate": "evaluate",
}

_MODULE_LOCK = threading.Lock()
_FILE_MTIMES = {}


def _get_endpoint_handler(module_name: str):
    """
    Mengambil class handler dari modul endpoint secara thread-safe.
    Hanya me-reload jika berkas .py benar-benar dimodifikasi pada disk,
    mencegah race condition ketika banyak CV diekstrak secara bersamaan.
    """
    with _MODULE_LOCK:
        py_file = os.path.join(API_DIR, f"{module_name}.py")
        current_mtime = os.path.getmtime(py_file) if os.path.exists(py_file) else None

        # Cek apakah ada berkas di _lib yang dimodifikasi
        lib_dir = os.path.join(API_DIR, "_lib")
        lib_changed = False
        if os.path.isdir(lib_dir):
            for fname in os.listdir(lib_dir):
                if fname.endswith(".py"):
                    fpath = os.path.join(lib_dir, fname)
                    fmtime = os.path.getmtime(fpath)
                    if _FILE_MTIMES.get(fpath) != fmtime:
                        lib_changed = True
                        _FILE_MTIMES[fpath] = fmtime
                        sub_name = f"_lib.{fname[:-3]}"
                        if sub_name in sys.modules:
                            try:
                                importlib.reload(sys.modules[sub_name])
                            except Exception:
                                pass

        last_mtime = _FILE_MTIMES.get(py_file)
        need_reload = (current_mtime is not None and last_mtime != current_mtime) or lib_changed

        if module_name in sys.modules:
            mod = sys.modules[module_name]
            # Pastikan atribut handler benar-benar ada dan tidak rusak
            if need_reload or not hasattr(mod, "handler"):
                try:
                    mod = importlib.reload(mod)
                except Exception:
                    sys.modules.pop(module_name, None)
                    mod = importlib.import_module(module_name)
        else:
            mod = importlib.import_module(module_name)

        if current_mtime is not None:
            _FILE_MTIMES[py_file] = current_mtime

        handler_class = getattr(mod, "handler", None)
        if handler_class is None:
            # Fallback jika modul sempat rusak di cache
            sys.modules.pop(module_name, None)
            mod = importlib.import_module(module_name)
            handler_class = getattr(mod, "handler")

        return handler_class


class DevDispatcherHandler(BaseHTTPRequestHandler):
    def _dispatch(self, method: str):
        path = self.path.split("?")[0].rstrip("/")
        module_name = ROUTES.get(path)

        if not module_name and path.startswith("/api/"):
            candidate = path[len("/api/"):].strip("/")
            if candidate and not candidate.startswith("_"):
                py_file = os.path.join(API_DIR, f"{candidate}.py")
                if os.path.exists(py_file):
                    module_name = candidate

        if not module_name:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Endpoint dev tidak ditemukan"}')
            return

        try:
            handler_class = _get_endpoint_handler(module_name)
            
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
