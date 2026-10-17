"""
Endpoint Python Serverless: POST /api/rank
Menerima seluruh hasil ekstraksi CV dan daftar profil per divisi.
Mengelompokkan pelamar per divisi, menghitung TF-IDF dan skor kategori,
mengevaluasi hard requirements, dan mengembalikan ranking JSON.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from _lib.auth import check_request_auth, check_csrf_header
from _lib.scoring import rank_candidates_for_batch


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

        candidates = payload.get("candidates", [])
        profiles = payload.get("profiles", [])

        if not isinstance(candidates, list) or not isinstance(profiles, list):
            self._send_json(400, {"status": "error", "message": "Candidates dan profiles harus berupa array."})
            return

        # Peta profil berdasarkan nama divisi (dan alias jika ada)
        profiles_by_division = {}
        for p in profiles:
            div_name = p.get("division")
            if div_name:
                profiles_by_division[div_name] = p
                for alias in p.get("divisionAliases", []):
                    if alias:
                        profiles_by_division[alias] = p

        # Eksekusi Pemeringkatan
        try:
            ranking_result = rank_candidates_for_batch(candidates, profiles_by_division)
            self._send_json(200, {
                "status": "ok",
                "data": ranking_result
            })
        except Exception as e:
            self._send_json(500, {
                "status": "error",
                "message": f"Terjadi kesalahan saat memproses ranking: {str(e)}"
            })
