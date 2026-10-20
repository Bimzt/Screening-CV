"""
Modul integrasi Google Drive API via Service Account.
Mengunduh berkas CV (PDF/DOCX/Google Docs) dengan mitigasi SSRF, dukungan folder,
pemulihan shortlink, dan exponential backoff.
"""

import os
import re
import json
import base64
import time
from typing import Tuple, Optional, Dict, Any, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import io
import urllib.request
import urllib.parse
from http.cookiejar import CookieJar
from .config import MAX_FILE_SIZE_BYTES

# Regex validasi ID Drive yang ketat (panjang minimal 10 karakter alfanumerik / hyphen / underscore)
DRIVE_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{10,}$")

# Pola-pola URL Google Drive yang sah
URL_PATTERNS = [
    re.compile(r"/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]{10,})"),
    re.compile(r"/folders/([A-Za-z0-9_-]{10,})"),
    re.compile(r"/file/(?:u/\d+/)?d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"/document/(?:u/\d+/)?d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"/spreadsheets/(?:u/\d+/)?d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"/presentation/(?:u/\d+/)?d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"[?&]id=([A-Za-z0-9_-]{10,})"),
    re.compile(r"/d/([A-Za-z0-9_-]{10,})"),
]

SHORT_DOMAINS = ("s.id/", "bit.ly/", "tinyurl.com/", "cutt.ly/", "linktr.ee/", "rb.gy/", "t.co/", "shorturl.at/")


def resolve_shortener_url(url: str, timeout: int = 5) -> Optional[str]:
    """
    Mengikuti redirect HTTP dari tautan pendek (s.id, bit.ly, dll) untuk mendapatkan URL tujuan.
    """
    if not any(d in url.lower() for d in SHORT_DOMAINS):
        return None
    try:
        target_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
        req = urllib.request.Request(
            target_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            if final_url and final_url != target_url:
                return final_url
    except Exception:
        pass
    return None


def extract_drive_file_id(input_str: Optional[str]) -> Optional[str]:
    """
    Mengekstrak Google Drive File/Folder ID dari URL atau string ID mentah.
    Mencegah SSRF dengan memvalidasi format ID secara ketat.
    """
    if not input_str or not isinstance(input_str, str):
        return None

    cleaned = input_str.strip()

    # Cek apakah langsung berupa ID yang cocok regex
    if DRIVE_ID_REGEX.match(cleaned):
        return cleaned

    # Decode URL-encoded characters (misal %2F -> /)
    try:
        cleaned = urllib.parse.unquote(cleaned)
    except Exception:
        pass

    # Bersihkan kutipan awal dan akhir, kurung
    cleaned = cleaned.strip("\"'() \t\r\n")

    # Tangani formula =HYPERLINK("...", "...")
    hyperlink_match = re.search(r'HYPERLINK\s*\(\s*["\']([^"\']+)["\']', cleaned, re.IGNORECASE)
    if hyperlink_match:
        cleaned = hyperlink_match.group(1).strip()

    # Coba resolusi jika berupa link pemendek URL
    if any(d in cleaned.lower() for d in SHORT_DOMAINS):
        resolved = resolve_shortener_url(cleaned)
        if resolved:
            cleaned = resolved

    # Cek terhadap pola-pola URL Google Drive
    for pattern in URL_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            candidate_id = match.group(1)
            # Pastikan candidate ID valid dan bukan IP address / path lokal (SSRF prevention)
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


def download_public_drive_file(file_id: str) -> Tuple[bytes, str, str]:
    """
    Mengunduh berkas dari tautan publik Google Drive (Anyone with the link can view)
    tanpa memerlukan Service Account. Mendukung file tunggal dan folder publik.
    Mengembalikan (file_bytes, mime_type, filename).
    """
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 1. Coba unduh langsung sebagai file
    direct_urls = [
        f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0",
        f"https://drive.google.com/uc?export=download&id={file_id}",
        f"https://docs.google.com/document/d/{file_id}/export?format=pdf",
    ]

    for url in direct_urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=25) as resp:
                content_disposition = resp.headers.get("Content-Disposition", "")
                data = resp.read(MAX_FILE_SIZE_BYTES + 1024)

                # Tangani konfirmasi scan virus jika ukuran berkas besar
                if b"confirm=" in data:
                    match = re.search(r"confirm=([0-9A-Za-z_-]+)", data.decode("utf-8", errors="ignore"))
                    if match:
                        confirm_token = match.group(1)
                        c_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm={confirm_token}"
                        c_req = urllib.request.Request(c_url, headers=headers)
                        with opener.open(c_req, timeout=25) as c_resp:
                            data = c_resp.read(MAX_FILE_SIZE_BYTES + 1024)
                            content_disposition = c_resp.headers.get("Content-Disposition", "")

                # Validasi format berkas
                if data.startswith(b"%PDF-"):
                    mime = "application/pdf"
                    fn = f"{file_id}.pdf"
                    if "filename=" in content_disposition:
                        fn_match = re.search(r'filename="?([^";\n]+)"?', content_disposition)
                        if fn_match:
                            fn = fn_match.group(1)
                    return data, mime, fn
                elif data.startswith(b"PK\x03\x04"):
                    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    fn = f"{file_id}.docx"
                    if "filename=" in content_disposition:
                        fn_match = re.search(r'filename="?([^";\n]+)"?', content_disposition)
                        if fn_match:
                            fn = fn_match.group(1)
                    return data, mime, fn
                elif data.startswith(b"\xd0\xcf\x11\xe0"):
                    # Format biner legacy Word (.doc)
                    mime = "application/msword"
                    fn = f"{file_id}.doc"
                    if "filename=" in content_disposition:
                        fn_match = re.search(r'filename="?([^";\n]+)"?', content_disposition)
                        if fn_match:
                            fn = fn_match.group(1)
                    return data, mime, fn
                elif data.startswith(b"\x89PNG\r\n\x1a\n"):
                    mime = "image/png"
                    fn = f"{file_id}.png"
                    if "filename=" in content_disposition:
                        fn_match = re.search(r'filename="?([^";\n]+)"?', content_disposition)
                        if fn_match:
                            fn = fn_match.group(1)
                    return data, mime, fn
                elif data.startswith(b"\xff\xd8\xff"):
                    mime = "image/jpeg"
                    fn = f"{file_id}.jpg"
                    if "filename=" in content_disposition:
                        fn_match = re.search(r'filename="?([^";\n]+)"?', content_disposition)
                        if fn_match:
                            fn = fn_match.group(1)
                    return data, mime, fn
                elif data.startswith(b"RIFF") and b"WEBP" in data[:16]:
                    mime = "image/webp"
                    fn = f"{file_id}.webp"
                    if "filename=" in content_disposition:
                        fn_match = re.search(r'filename="?([^";\n]+)"?', content_disposition)
                        if fn_match:
                            fn = fn_match.group(1)
                    return data, mime, fn
        except Exception:
            continue

    # 2. Jika bukan berkas langsung, coba periksa apakah tautan berupa folder publik Google Drive
    folder_urls = [
        f"https://drive.google.com/embeddedfolderview?id={file_id}#list",
        f"https://drive.google.com/drive/folders/{file_id}",
    ]
    for f_url in folder_urls:
        try:
            req = urllib.request.Request(f_url, headers=headers)
            with opener.open(req, timeout=15) as resp:
                html_text = resp.read(300 * 1024).decode("utf-8", errors="ignore")
                found_child_ids: List[str] = []
                for p in [r"/file/d/([A-Za-z0-9_-]{15,})", r'data-id="([A-Za-z0-9_-]{15,})"', r'"id":"([A-Za-z0-9_-]{15,})"']:
                    for match in re.finditer(p, html_text):
                        cid = match.group(1)
                        if cid != file_id and cid not in found_child_ids and DRIVE_ID_REGEX.match(cid):
                            found_child_ids.append(cid)
                for cid in found_child_ids:
                    try:
                        return download_public_drive_file(cid)
                    except Exception:
                        continue
        except Exception:
            continue

    raise PermissionError(
        f"Berkas Google Drive ({file_id}) tidak dapat diunduh secara publik. "
        "Pastikan izin tautan diatur 'Siapa saja yang memiliki link' (Anyone with the link)."
    )


def download_drive_file(
    file_id: str,
    drive_service: Optional[Any] = None,
    max_retries: int = 3
) -> Tuple[bytes, str, str]:
    """
    Mengunduh berkas dari Google Drive dengan penanganan retry 429/5xx (exponential backoff).
    Mendukung unduhan via Service Account, folder Google Drive, dan otomatis fallback ke link publik jika tanpa kredensial.
    Mengembalikan (file_bytes, mime_type, filename).
    """
    if not DRIVE_ID_REGEX.match(file_id):
        raise ValueError(f"File ID tidak valid: {file_id}")

    has_sa = bool(drive_service or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64"))
    if not has_sa:
        return download_public_drive_file(file_id)

    try:
        service = drive_service or get_drive_service()
    except Exception:
        return download_public_drive_file(file_id)

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
            if status in (403, 404):
                try:
                    return download_public_drive_file(file_id)
                except Exception:
                    pass
            if status == 404:
                raise FileNotFoundError(f"File ID {file_id} tidak ditemukan di Google Drive atau izin akses belum diberikan ke Service Account.")
            if status == 403:
                raise PermissionError(f"Akses ditolak ke File ID {file_id}. Pastikan folder/file telah dibagikan ke email Service Account atau diatur publik.")
            raise

    if not meta:
        raise RuntimeError("Gagal mengambil metadata berkas dari Google Drive.")

    mime_type = meta.get("mimeType", "")
    filename = meta.get("name", f"{file_id}.bin")

    # Tangani Folder Google Drive
    if mime_type == "application/vnd.google-apps.folder":
        try:
            children_res = service.files().list(
                q=f"'{file_id}' in parents and trashed = false",
                fields="files(id, name, mimeType, size)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=30
            ).execute()
            files = children_res.get("files", [])
            if not files:
                raise FileNotFoundError(f"Folder Google Drive '{filename}' kosong, tidak memuat berkas apapun.")

            # Cari berkas CV terbaik di dalam folder
            best_file = None
            # Prioritas 1: file PDF dengan nama 'cv' atau 'resume'
            for f in files:
                m = f.get("mimeType", "")
                n = f.get("name", "").lower()
                if (m == "application/pdf" or n.endswith(".pdf")) and ("cv" in n or "resume" in n):
                    best_file = f
                    break
            # Prioritas 2: file PDF apapun
            if not best_file:
                for f in files:
                    m = f.get("mimeType", "")
                    n = f.get("name", "").lower()
                    if m == "application/pdf" or n.endswith(".pdf"):
                        best_file = f
                        break
            # Prioritas 3: file Word (.docx, .doc)
            if not best_file:
                for f in files:
                    m = f.get("mimeType", "")
                    n = f.get("name", "").lower()
                    if "word" in m or n.endswith(".docx") or n.endswith(".doc"):
                        best_file = f
                        break
            # Prioritas 4: Berkas Gambar (PNG/JPG/WEBP) dengan nama 'cv' atau 'resume'
            if not best_file:
                for f in files:
                    m = f.get("mimeType", "").lower()
                    n = f.get("name", "").lower()
                    if ("image" in m or n.endswith((".png", ".jpg", ".jpeg", ".webp"))) and ("cv" in n or "resume" in n):
                        best_file = f
                        break
            # Prioritas 5: Google Docs
            if not best_file:
                for f in files:
                    if f.get("mimeType") == "application/vnd.google-apps.document":
                        best_file = f
                        break
            # Prioritas 6: Berkas Gambar apapun
            if not best_file:
                for f in files:
                    m = f.get("mimeType", "").lower()
                    n = f.get("name", "").lower()
                    if "image" in m or n.endswith((".png", ".jpg", ".jpeg", ".webp")):
                        best_file = f
                        break
            # Prioritas 7: berkas non-folder pertama
            if not best_file:
                for f in files:
                    if f.get("mimeType") != "application/vnd.google-apps.folder":
                        best_file = f
                        break

            if not best_file:
                raise FileNotFoundError(f"Tidak ditemukan dokumen CV (PDF/DOCX/Gambar) di dalam folder '{filename}'.")

            return download_drive_file(best_file["id"], drive_service=service, max_retries=max_retries)
        except HttpError:
            return download_public_drive_file(file_id)

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
