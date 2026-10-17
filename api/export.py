"""
Endpoint Python Serverless: POST /api/export
Menerima hasil pemeringkatan dan daftar profil,
menghasilkan berkas spreadsheet Excel (.xlsx) dengan 3 sheet berstandar HR.
Stateless dan mengembalikan binary spreadsheet langsung.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from _lib.auth import check_request_auth, check_csrf_header
from _lib.excel import generate_screening_excel


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: dict):
        response_body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def do_POST(self):
        # 1. Pengecekan Header CSRF
        if not check_csrf_header(self.headers):
            self._send_json(403, {
                "status": "error",
                "message": "Permintaan ditolak: Header CSRF tidak ditemukan."
            })
            return

        # 2. Verifikasi Autentikasi Sesi
        is_auth, error_msg = check_request_auth(self.headers)
        if not is_auth:
            self._send_json(401, {
                "status": "error",
                "message": error_msg or "Sesi tidak valid atau telah kedaluwarsa."
            })
            return

        # 3. Baca Payload JSON
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 15 * 1024 * 1024:
                self._send_json(413, {"status": "error", "message": "Ukuran payload melebihi batas 15MB."})
                return
            body_bytes = self.rfile.read(content_length)
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            self._send_json(400, {"status": "error", "message": "Format JSON tidak valid."})
            return

        ranking_data = payload.get("rankingData")
        profiles = payload.get("profiles", [])

        if not ranking_data or not isinstance(ranking_data, dict):
            self._send_json(400, {"status": "error", "message": "Field 'rankingData' wajib diisi."})
            return

        profiles_by_division = {}
        for p in profiles:
            div_name = p.get("division")
            if div_name:
                profiles_by_division[div_name] = p

        # 4. Generate Berkas Excel
        try:
            excel_bytes = generate_screening_excel(ranking_data, profiles_by_division)
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            self.send_header(
                "Content-Disposition",
                'attachment; filename="CV_Screening_Results.xlsx"'
            )
            self.send_header("Content-Length", str(len(excel_bytes)))
            self.end_headers()
            self.wfile.write(excel_bytes)
        except Exception as e:
            self._send_json(500, {
                "status": "error",
                "message": f"Gagal membuat file Excel: {str(e)}"
            })
