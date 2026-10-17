"""
Modul integrasi Google Drive API via Service Account.
Mengunduh berkas CV (PDF/DOCX/Google Docs) dengan mitigasi SSRF dan exponential backoff.
"""

import os
import re
import json
import base64
import time
from typing import Tuple, Optional, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io
from .config import MAX_FILE_SIZE_BYTES

# Regex validasi ID Drive yang ketat (panjang minimal 10 karakter alfanumerik / hyphen / underscore)
DRIVE_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{10,}$")

# Pola-pola URL Google Drive yang sah
URL_PATTERNS = [
    re.compile(r"[?&]id=([A-Za-z0-9_-]{10,})"),
    re.compile(r"/file/d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"/document/d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"/d/([A-Za-z0-9_-]{10,})"),
]


def extract_drive_file_id(input_str: Optional[str]) -> Optional[str]:
    """
    Mengekstrak Google Drive File ID dari URL atau string ID mentah.
    Mencegah SSRF dengan memvalidasi format ID secara ketat.
    """
    if not input_str or not isinstance(input_str, str):
        return None

    cleaned = input_str.strip()

    # Cek apakah langsung berupa ID yang cocok regex
    if DRIVE_ID_REGEX.match(cleaned):
        return cleaned

    # Cek terhadap pola URL Drive
    for pattern in URL_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            candidate_id = match.group(1)
            if DRIVE_ID_REGEX.match(candidate_id):
                return candidate_id

    return None


def extract_all_drive_file_ids(cell_value: Optional[str]) -> list[str]:
    """
    Mengekstrak seluruh File ID jika satu sel CSV berisi beberapa link dipisah koma/spasi/baris baru.
    """
    if not cell_value or not isinstance(cell_value, str):
        return []

    tokens = re.split(r"[\s,;]+", cell_value.strip())
    results = []
    seen = set()

    for token in tokens:
        file_id = extract_drive_file_id(token)
        if file_id and file_id not in seen:
            seen.add(file_id)
            results.append(file_id)

    return results


def get_drive_service(creds_b64: Optional[str] = None):
    """
    Menginisialisasi klien Google Drive API dengan Service Account (scope: drive.readonly).
    """
    b64_str = creds_b64 or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    if not b64_str:
        raise ValueError("Kredensial GOOGLE_SERVICE_ACCOUNT_JSON_B64 belum disetel.")

    try:
        json_bytes = base64.b64decode(b64_str)
        service_info = json.loads(json_bytes.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Gagal mengurai kredensial Service Account: {str(e)}")

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    credentials = service_account.Credentials.from_service_account_info(
        service_info, scopes=scopes
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def download_drive_file(
    file_id: str,
    drive_service: Optional[Any] = None,
    max_retries: int = 3
) -> Tuple[bytes, str, str]:
    """
    Mengunduh berkas dari Google Drive dengan penanganan retry 429/5xx (exponential backoff).
    Mengembalikan (file_bytes, mime_type, filename).
    """
    if not DRIVE_ID_REGEX.match(file_id):
        raise ValueError(f"File ID tidak valid: {file_id}")

    service = drive_service or get_drive_service()

    # Dapatkan metadata berkas (nama, ukuran, mimeType)
    meta = None
    for attempt in range(max_retries):
        try:
            meta = service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size",
                supportsAllDrives=True
            ).execute()
            break
        except HttpError as err:
            status = err.resp.status
            if status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            if status == 404:
                raise FileNotFoundError(f"File ID {file_id} tidak ditemukan di Google Drive atau izin akses belum diberikan ke Service Account.")
            if status == 403:
                raise PermissionError(f"Akses ditolak ke File ID {file_id}. Pastikan folder CV telah dibagikan ke email Service Account.")
            raise

    if not meta:
        raise RuntimeError("Gagal mengambil metadata berkas dari Google Drive.")

    mime_type = meta.get("mimeType", "")
    filename = meta.get("name", f"{file_id}.bin")
    reported_size = int(meta.get("size", 0))

    if reported_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Ukuran berkas melebihi batas 10 MB ({reported_size / (1024*1024):.1f} MB).")

    # Tangani Google Docs native (ekspor ke PDF)
    is_google_doc = mime_type == "application/vnd.google-apps.document"
    fh = io.BytesIO()

    for attempt in range(max_retries):
        try:
            if is_google_doc:
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType="application/pdf"
                )
                mime_type = "application/pdf"
            else:
                request = service.files().get_media(
                    fileId=file_id,
                    supportsAllDrives=True
                )

            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if fh.tell() > MAX_FILE_SIZE_BYTES:
                    raise ValueError("Ukuran unduhan berkas melebihi batas 10 MB.")
            break
        except HttpError as err:
            status_code = err.resp.status
            if status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                fh.seek(0)
                fh.truncate(0)
                continue
            raise

    file_bytes = fh.getvalue()
    return file_bytes, mime_type, filename
