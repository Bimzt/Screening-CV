"""
Endpoint Python Serverless: POST /api/process
Mengunduh berkas CV dari Google Drive (atau menerima base64 testing),
mengekstrak teks PDF/DOCX, mendeteksi scan, membagi seksi, dan mengekstrak field.
Stateless dan tidak menyimpan berkas ke disk.
"""

from http.server import BaseHTTPRequestHandler
import json
import base64
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from _lib.auth import check_request_auth, check_csrf_header
from _lib.drive import extract_drive_file_id, download_drive_file
from _lib.parsing import parse_cv_document
from _lib.sections import segment_cv_sections
from _lib.extract import extract_cv_fields


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: dict):
        response_body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def do_POST(self):
        # 1. Pengecekan CSRF
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

        # 3. Baca Body JSON
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 15 * 1024 * 1024:
                self._send_json(413, {"status": "error", "message": "Ukuran payload melebihi batas."})
                return
            body_bytes = self.rfile.read(content_length)
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            self._send_json(400, {"status": "error", "message": "Format JSON tidak valid."})
            return

        file_id_input = payload.get("fileId") or payload.get("driveLink")
        candidate_name = payload.get("candidateName")
        source_row_index = payload.get("sourceRowIndex")
        drive_link = payload.get("driveLink", "")
        division_choices = payload.get("divisionChoices", [])
        custom_headings = payload.get("customHeadings")
        raw_base64 = payload.get("rawBase64")  # Opsional untuk testing offline/mock

        file_id = extract_drive_file_id(file_id_input)
        if not file_id and not raw_base64:
            # Gagal validasi File ID Drive: berikan penjelasan yang spesifik
            raw_str = str(file_id_input or "").strip()
            raw_lower = raw_str.lower()
            if not raw_str:
                err_msg = "Kolom link CV kosong di CSV pelamar ini. Pastikan kolom yang dipetakan pada langkah sebelumnya sudah benar."
            elif "canva.com" in raw_lower:
                err_msg = "Link mengarah ke Canva. Pelamar perlu mengunggah berkas PDF CV ke Google Drive."
            elif "linkedin.com" in raw_lower:
                err_msg = "Link mengarah ke profil LinkedIn, bukan berkas CV di Google Drive."
            elif "instagram.com" in raw_lower or "tiktok.com" in raw_lower:
                err_msg = "Link mengarah ke akun media sosial, bukan berkas Google Drive."
            elif "drive.google.com" in raw_lower:
                err_msg = "Tautan Google Drive tidak memuat File ID yang sah atau format URL terpotong."
            else:
                display_link = raw_str[:45] + ("..." if len(raw_str) > 45 else "")
                err_msg = f"Tautan tidak didukung ({display_link}). Pastikan tautan Google Drive dengan akses publik."

            self._send_json(200, {
                "status": "ok",
                "result": {
                    "fileId": file_id_input or "",
                    "sourceRowIndex": source_row_index,
                    "driveLink": drive_link,
                    "candidateName": candidate_name or "Tidak Diketahui",
                    "fields": {
                        "name": candidate_name,
                        "email": None,
                        "phone": None,
                        "university": None,
                        "major": None,
                        "gpa": None,
                        "graduationYearOrSemester": None,
                        "portfolioLinks": [],
                        "skillsFound": [],
                        "experiences": [],
                        "projects": [],
                        "certifications": [],
                    },
                    "sections": {},
                    "fieldStatus": {"fileId": "tidak_ditemukan"},
                    "flags": ["link_drive_tidak_valid"],
                    "isScanPdf": False,
                    "divisionChoices": division_choices,
                    "error": err_msg
                }
            })
            return

        # 4. Unduh atau Dapatkan Berkas
        file_bytes = None
        mime_type = "application/pdf"
        filename = f"{file_id}.pdf"
        download_error = None

        if raw_base64:
            try:
                file_bytes = base64.b64decode(raw_base64)
                mime_type = payload.get("mimeType", "application/pdf")
                filename = payload.get("filename", "uploaded_cv.pdf")
            except Exception as e:
                download_error = f"Gagal membaca berkas: {str(e)}"
        else:
            try:
                file_bytes, mime_type, filename = download_drive_file(file_id)
            except Exception as e:
                download_error = str(e)

        if download_error or not file_bytes:
            err_text = str(download_error)
            if "Akses ditolak" in err_text or "403" in err_text or "tidak dapat diunduh" in err_text:
                err_msg = "Akses Google Drive terkunci. Pastikan izin tautan diatur ke 'Siapa saja yang memiliki link' (Anyone with the link)."
            elif "404" in err_text or "tidak ditemukan" in err_text:
                err_msg = f"Berkas tidak ditemukan di Google Drive atau telah dihapus oleh pelamar."
            elif "kosong" in err_text:
                err_msg = err_text
            else:
                err_msg = f"Gagal mengunduh dari Google Drive: {err_text}"

            self._send_json(200, {
                "status": "ok",
                "result": {
                    "fileId": file_id or "",
                    "sourceRowIndex": source_row_index,
                    "driveLink": drive_link,
                    "candidateName": candidate_name or "Tidak Diketahui",
                    "fields": {
                        "name": candidate_name,
                        "email": None,
                        "phone": None,
                        "university": None,
                        "major": None,
                        "gpa": None,
                        "graduationYearOrSemester": None,
                        "portfolioLinks": [],
                        "skillsFound": [],
                        "experiences": [],
                        "projects": [],
                        "certifications": [],
                    },
                    "sections": {},
                    "fieldStatus": {"file": "tidak_ditemukan"},
                    "flags": ["gagal_unduh_drive"],
                    "isScanPdf": False,
                    "divisionChoices": division_choices,
                    "error": err_msg
                }
            })
            return

        # 5. Parsing Dokumen
        parsed = parse_cv_document(file_bytes, mime_type, filename)
        if parsed.get("error") and not parsed.get("is_scan"):
            self._send_json(200, {
                "status": "ok",
                "result": {
                    "fileId": file_id or "",
                    "sourceRowIndex": source_row_index,
                    "driveLink": drive_link,
                    "candidateName": candidate_name or "Tidak Diketahui",
                    "fields": {
                        "name": candidate_name,
                        "email": None,
                        "phone": None,
                        "university": None,
                        "major": None,
                        "gpa": None,
                        "graduationYearOrSemester": None,
                        "portfolioLinks": [],
                        "skillsFound": [],
                        "experiences": [],
                        "projects": [],
                        "certifications": [],
                    },
                    "sections": {},
                    "fieldStatus": {"document": "ambigu"},
                    "flags": ["dokumen_rusak_atau_tidak_didukung"],
                    "isScanPdf": False,
                    "divisionChoices": division_choices,
                    "error": parsed["error"]
                }
            })
            return

        full_text = parsed["text"]
        is_scan = parsed["is_scan"]
        all_links = parsed["links"]

        # 6. Segmentasi Seksi
        sections, section_flags = segment_cv_sections(full_text, custom_headings)

        # 7. Ekstraksi Field
        fields, field_status, extract_flags = extract_cv_fields(
            full_text=full_text,
            sections=sections,
            all_links=all_links,
            candidate_name_from_csv=candidate_name
        )

        flags = list(set(section_flags + extract_flags + parsed.get("flags", [])))
        if is_scan:
            flags.append("pdf_scan_ocr_belum_didukung")

        self._send_json(200, {
            "status": "ok",
            "result": {
                "fileId": file_id or "",
                "sourceRowIndex": source_row_index,
                "driveLink": drive_link,
                "candidateName": fields["name"],
                "fields": fields,
                "sections": sections,
                "fieldStatus": field_status,
                "flags": flags,
                "isScanPdf": is_scan,
                "divisionChoices": division_choices,
                "error": parsed.get("error") if is_scan else None
            }
        })
