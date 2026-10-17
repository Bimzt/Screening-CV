"""
Endpoint Python Serverless: /api/hello
Digunakan pada Fase 1 untuk memvalidasi integrasi Next.js + Python runtime di Vercel
serta verifikasi sesi mandiri dari cookie.
"""

from http.server import BaseHTTPRequestHandler
import json
import time
import os
import sys

# Pastikan api/ berada di sys.path agar impor modul _lib berfungsi
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from _lib.auth import check_request_auth, check_csrf_header


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: dict):
        response_body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def do_GET(self):
        # 1. Verifikasi Autentikasi Sesi
        is_auth, error_msg = check_request_auth(self.headers)
        if not is_auth:
            self._send_json(401, {
                "status": "error",
                "message": error_msg or "Akses ditolak. Sesi tidak valid."
            })
            return

        # 2. Respon Berhasil
        self._send_json(200, {
            "status": "ok",
            "message": "Halo dari Python Serverless CV Screener!",
            "authenticated": True,
            "runtime": f"Python {sys.version.split()[0]}",
            "timestamp": int(time.time())
        })

    def do_POST(self):
        # 1. Pengecekan Header CSRF
        if not check_csrf_header(self.headers):
            self._send_json(403, {
                "status": "error",
                "message": "Permintaan ditolak: Header CSRF (X-Requested-With) tidak ditemukan."
            })
            return

        # 2. Verifikasi Autentikasi Sesi
        is_auth, error_msg = check_request_auth(self.headers)
        if not is_auth:
            self._send_json(401, {
                "status": "error",
                "message": error_msg or "Akses ditolak. Sesi tidak valid."
            })
            return

        # 3. Respon Berhasil
        self._send_json(200, {
            "status": "ok",
            "message": "POST berhasil! Python Serverless & sesi terverifikasi.",
            "authenticated": True,
            "runtime": f"Python {sys.version.split()[0]}",
            "timestamp": int(time.time())
        })
