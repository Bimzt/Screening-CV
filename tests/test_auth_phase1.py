import os
import sys
import time
import io
import json
import pytest

# Ensure api/ and root directory are in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../api")))

from api._lib.auth import (
    sign_session,
    verify_session,
    parse_cookie_header,
    check_request_auth,
    check_csrf_header,
)
from api._lib.config import SESSION_COOKIE_NAME
from api.hello import handler


class DummyWFile:
    def __init__(self):
        self.buffer = io.BytesIO()

    def write(self, data):
        self.buffer.write(data)

    def get_value(self):
        return self.buffer.getvalue().decode("utf-8")


class DummyRequest:
    def __init__(self, headers, method="GET"):
        self.headers = headers
        self.command = method
        self.path = "/api/hello"
        self.request_version = "HTTP/1.1"
        self.close_connection = False
        self.rfile = io.BytesIO()
        self.wfile = DummyWFile()
        self.status_code = None
        self.response_headers = {}

    def send_response(self, code, message=None):
        self.status_code = code

    def send_header(self, keyword, value):
        self.response_headers[keyword] = value

    def end_headers(self):
        pass


def test_sign_and_verify_session():
    secret = "test-secret-key-at-least-32-chars-long!"
    token = sign_session(secret)
    assert token is not None
    assert "." in token

    # Harus valid dengan secret yang sama
    assert verify_session(token, secret) is True

    # Harus ditolak jika secret berbeda
    assert verify_session(token, "wrong-secret") is False

    # Harus ditolak jika token rusak/malformed
    assert verify_session("invalid.token.here", secret) is False
    assert verify_session("invalid_token", secret) is False
    assert verify_session("", secret) is False
    assert verify_session(None, secret) is False


def test_session_expiration():
    secret = "test-secret-key-at-least-32-chars-long!"
    # Simulasikan token yang dibuat 9 jam lalu (melebihi 8 jam)
    old_timestamp = str(int(time.time()) - (9 * 3600))
    import hmac
    import hashlib
    sig = hmac.new(secret.encode(), old_timestamp.encode(), hashlib.sha256).hexdigest()
    expired_token = f"{old_timestamp}.{sig}"

    assert verify_session(expired_token, secret) is False


def test_parse_cookie_header():
    header = f"{SESSION_COOKIE_NAME}=test_token_123; other_cookie=abc"
    parsed = parse_cookie_header(header)
    assert parsed.get(SESSION_COOKIE_NAME) == "test_token_123"
    assert parsed.get("other_cookie") == "abc"


def test_check_csrf_header():
    assert check_csrf_header({"X-Requested-With": "XMLHttpRequest"}) is True
    assert check_csrf_header({"x-requested-with": "XMLHttpRequest"}) is True
    assert check_csrf_header({"X-CV-Screener": "1"}) is True
    assert check_csrf_header({"Content-Type": "application/json"}) is False


def test_hello_endpoint_unauthenticated(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "super-secret-key-32-characters-test")

    # Request tanpa cookie
    req = DummyRequest(headers={})
    h = handler.__new__(handler)
    h.headers = req.headers
    h.wfile = req.wfile
    h.send_response = req.send_response
    h.send_header = req.send_header
    h.end_headers = req.end_headers

    h.do_GET()
    assert req.status_code == 401
    body = json.loads(req.wfile.get_value())
    assert body["status"] == "error"


def test_hello_endpoint_authenticated(monkeypatch):
    secret = "super-secret-key-32-characters-test"
    monkeypatch.setenv("SESSION_SECRET", secret)
    token = sign_session(secret)

    # Request dengan cookie valid
    req = DummyRequest(headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"})
    h = handler.__new__(handler)
    h.headers = req.headers
    h.wfile = req.wfile
    h.send_response = req.send_response
    h.send_header = req.send_header
    h.end_headers = req.end_headers

    h.do_GET()
    assert req.status_code == 200
    body = json.loads(req.wfile.get_value())
    assert body["status"] == "ok"
    assert body["authenticated"] is True


def test_hello_endpoint_post_csrf(monkeypatch):
    secret = "super-secret-key-32-characters-test"
    monkeypatch.setenv("SESSION_SECRET", secret)
    token = sign_session(secret)

    # POST tanpa header CSRF
    req = DummyRequest(
        headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"},
        method="POST"
    )
    h = handler.__new__(handler)
    h.headers = req.headers
    h.wfile = req.wfile
    h.send_response = req.send_response
    h.send_header = req.send_header
    h.end_headers = req.end_headers

    h.do_POST()
    assert req.status_code == 403

    # POST dengan header CSRF
    req2 = DummyRequest(
        headers={
            "Cookie": f"{SESSION_COOKIE_NAME}={token}",
            "X-Requested-With": "XMLHttpRequest"
        },
        method="POST"
    )
    h2 = handler.__new__(handler)
    h2.headers = req2.headers
    h2.wfile = req2.wfile
    h2.send_response = req2.send_response
    h2.send_header = req2.send_header
    h2.end_headers = req2.end_headers

    h2.do_POST()
    assert req2.status_code == 200
    body = json.loads(req2.wfile.get_value())
    assert body["status"] == "ok"
