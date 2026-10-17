"""
Modul otentikasi dan keamanan untuk fungsi Python Serverless.
Memverifikasi session cookie secara independen menggunakan HMAC-SHA256.
"""

import os
import hmac
import hashlib
import time
from http import cookies
from typing import Tuple, Optional, Dict
from .config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS


def sign_session(secret: str) -> str:
    """
    Menghasilkan token sesi HMAC-SHA256.
    Format: <timestamp>.<hex_hmac_signature>
    """
    if not secret:
        raise ValueError("Secret cannot be empty")
    timestamp_str = str(int(time.time()))
    sig = hmac.new(
        secret.encode("utf-8"),
        timestamp_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{timestamp_str}.{sig}"



def verify_session(token: Optional[str], secret: Optional[str], max_age_sec: int = SESSION_MAX_AGE_SECONDS) -> bool:
    """
    Memverifikasi integritas dan masa berlaku token sesi HMAC.
    Format token: <timestamp>.<hex_hmac_signature>
    """
    if not token or not secret:
        return False

    parts = token.split(".")
    if len(parts) != 2:
        return False

    timestamp_str, signature = parts
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False

    now = int(time.time())
    # Cek kedaluwarsa atau clock skew > 60s
    if (now - timestamp > max_age_sec) or (timestamp - now > 60):
        return False

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        timestamp_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


def parse_cookie_header(raw_cookie_header: Optional[str]) -> Dict[str, str]:
    """
    Mengurai header Cookie menjadi dictionary.
    """
    if not raw_cookie_header:
        return {}
    c = cookies.SimpleCookie()
    try:
        c.load(raw_cookie_header)
        return {key: morsel.value for key, morsel in c.items()}
    except Exception:
        # Fallback manual jika parsing cookie standar gagal
        result = {}
        for item in raw_cookie_header.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                result[k.strip()] = v.strip()
        return result


DEFAULT_SESSION_SECRET = "super-secret-development-session-key-32chars"


def check_request_auth(headers) -> Tuple[bool, Optional[str]]:
    """
    Memverifikasi sesi dari request headers.
    Mengembalikan (is_authenticated, error_message).
    """
    secret = os.environ.get("SESSION_SECRET") or DEFAULT_SESSION_SECRET

    raw_cookie = headers.get("cookie") or headers.get("Cookie")
    cookie_dict = parse_cookie_header(raw_cookie)
    token = cookie_dict.get(SESSION_COOKIE_NAME)

    if not token:
        return False, "Sesi tidak ditemukan. Silakan login terlebih dahulu."

    if not verify_session(token, secret):
        return False, "Sesi tidak valid atau telah kedaluwarsa. Silakan login kembali."

    return True, None


def check_csrf_header(headers) -> bool:
    """
    Memverifikasi keberadaan header kustom (X-Requested-With atau X-CV-Screener)
    sebagai lapisan pertahanan tambahan terhadap CSRF.
    """
    requested_with = headers.get("x-requested-with") or headers.get("X-Requested-With")
    custom_header = headers.get("x-cv-screener") or headers.get("X-CV-Screener")
    return bool(requested_with or custom_header)
