"""
Endpoint Python Serverless: POST /api/evaluate
Menerima kandidat dan profil divisi, lalu mengevaluasi kesiapan kerja riil menggunakan Google Gemini.
Mengembalikan hasil evaluasi kontekstual (skor AI, tingkat praktikal, ringkasan eksekutif, dan keunggulan utama).
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from _lib.auth import check_request_auth, check_csrf_header
from _lib.gemini import evaluate_candidates_tier2


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
            if content_length > 10 * 1024 * 1024:
                self._send_json(413, {"status": "error", "message": "Ukuran payload melebihi batas 10MB."})
                return
            body_bytes = self.rfile.read(content_length)
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            self._send_json(400, {"status": "error", "message": "Format JSON tidak valid."})
            return

        candidates = payload.get("candidates", [])
        profile = payload.get("profile", {})
        max_candidates = int(payload.get("maxCandidates", 10))

        if not isinstance(candidates, list) or not isinstance(profile, dict):
            self._send_json(400, {"status": "error", "message": "Payload harus memiliki array 'candidates' dan objek 'profile'."})
            return

        api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if not api_key:
            self._send_json(400, {
                "status": "error",
                "message": "GEMINI_API_KEY belum dikonfigurasi di server/Vercel Environment Variables."
            })
            return

        try:
            eval_results = evaluate_candidates_tier2(
                candidates=candidates,
                profile=profile,
                max_candidates=max_candidates,
                api_key=api_key
            )
            self._send_json(200, {
                "status": "ok",
                "data": eval_results,
                "modelUsed": os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
            })
        except Exception as e:
            self._send_json(500, {
                "status": "error",
                "message": f"Gagal mengevaluasi via Gemini: {str(e)}"
            })
