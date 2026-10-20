import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../api")))

from api._lib.drive import extract_drive_file_id, extract_all_drive_file_ids
from api._lib.extract import extract_gpa, extract_email, extract_phone, normalize_major, estimate_duration_months, classify_experience_type
from api._lib.sections import segment_cv_sections
from api._lib.parsing import parse_cv_document


def test_drive_id_extraction_and_ssrf_protection():
    # Pola link sah (berkas tunggal)
    assert extract_drive_file_id("1aB2c3D4e5F6g7H8i9J0_-") == "1aB2c3D4e5F6g7H8i9J0_-"
    assert extract_drive_file_id("https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/view") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    assert extract_drive_file_id("https://drive.google.com/open?id=1AbCdEfGhIjKlMnOpQrStUvWxYz") == "1AbCdEfGhIjKlMnOpQrStUvWxYz"
    assert extract_drive_file_id("https://drive.google.com/d/1AbCdEfGhIjKlMnOpQrStUvWxYz") == "1AbCdEfGhIjKlMnOpQrStUvWxYz"

    # Pola link Google Drive Folder (dukungan pelamar yang mengunggah folder CV)
    assert extract_drive_file_id("https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs?usp=sharing") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
    assert extract_drive_file_id("https://drive.google.com/drive/u/0/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz") == "1AbCdEfGhIjKlMnOpQrStUvWxYz"
    assert extract_drive_file_id("https://drive.google.com/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz") == "1AbCdEfGhIjKlMnOpQrStUvWxYz"

    # Format terenkode (URL encoded) dan formula Excel/Spreadsheet
    assert extract_drive_file_id("https%3A%2F%2Fdrive.google.com%2Ffile%2Fd%2F1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs%2Fview") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
    assert extract_drive_file_id('=HYPERLINK("https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view", "Budi CV")') == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
    assert extract_drive_file_id('"https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view"') == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
    assert extract_drive_file_id("Link CV: https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view (sudah open access)") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"

    # Input berbahaya / URL eksternal (cegah SSRF)
    assert extract_drive_file_id("http://169.254.169.254/latest/meta-data") is None
    assert extract_drive_file_id("https://malicious-site.com/steal-data") is None
    assert extract_drive_file_id("javascript:alert(1)") is None
    assert extract_drive_file_id("") is None
    assert extract_drive_file_id(None) is None

    # Multi link di satu sel
    multi = "https://drive.google.com/file/d/11111111111111111111/view, https://drive.google.com/file/d/22222222222222222222/view"
    ids = extract_all_drive_file_ids(multi)
    assert len(ids) == 2
    assert "11111111111111111111" in ids
    assert "22222222222222222222" in ids


def test_gpa_extraction():
    # Variasi format angka
    assert extract_gpa("IPK: 3.75")[0] == 3.75
    assert extract_gpa("IPK: 3,85")[0] == 3.85
    assert extract_gpa("GPA 3.8 / 4.00")[0] == 3.8
    assert extract_gpa("Indeks Prestasi Kumulatif 3,90 / 4.0")[0] == 3.90

    # Di luar rentang 0-4
    assert extract_gpa("IPK 5.2")[1] == "tidak_ditemukan"
    assert extract_gpa("GPA 85/100")[1] in ("ambigu", "tidak_ditemukan")

    # Ambigu (dua nilai IPK berbeda)
    gpa, status = extract_gpa("IPK Semester 1: 3.20. IPK Terakhir: 3.80")
    assert status == "ambigu"


def test_email_and_phone():
    text = "Hubungi saya di pelamar.baru@soko.id atau +6281234567890."
    email, em_status = extract_email(text)
    assert email == "pelamar.baru@soko.id"
    assert em_status == "ok"

    phone, ph_status = extract_phone(text)
    assert phone == "+6281234567890"
    assert ph_status == "ok"


def test_major_normalization():
    assert normalize_major("S1 Teknik Informatika") == "teknik informatika"
    assert normalize_major("Program Studi Ilmu Komunikasi") == "ilmu komunikasi"
    assert normalize_major("Jurusan Manajemen Bisnis, S1") == "manajemen bisnis"


def test_section_segmentation():
    sample_cv = """
    John Doe
    email@test.com
    
    Pendidikan
    Universitas Indonesia
    S1 Sistem Informasi (2020 - 2024)
    IPK: 3.85 / 4.00
    
    Pengalaman Kerja
    Software Engineering Intern di PT Maju Mundur (Jan 2023 - Des 2023)
    Mengembangkan fitur pencarian CV dengan Python.
    
    Proyek
    Aplikasi Web Screening CV
    Dibangun dengan Next.js dan Tailwind.
    
    Keahlian
    Python, SQL, React, TypeScript, Git
    """
    sections, flags = segment_cv_sections(sample_cv)
    assert "Sistem Informasi" in sections["education"]
    assert "Software Engineering Intern" in sections["experience"]
    assert "Aplikasi Web Screening CV" in sections["projects"]
    assert "Python, SQL" in sections["skills"]
    assert "seksi_tidak_terdeteksi" not in flags


def test_duration_and_experience_tagging():
    assert estimate_duration_months("Magang selama 6 bulan") == 6
    assert estimate_duration_months("Jan 2022 - Des 2022") == 12

    assert classify_experience_type("Ketua Panitia Orientasi Kampus") == "kepanitiaan/volunteer"
    assert classify_experience_type("Staff Departemen PSDM BEM") == "organisasi"
    assert classify_experience_type("Content Writer Intern di Startup") == "kerja/magang"


def test_image_cv_and_ocr_handling(monkeypatch):
    # 1. Berkas gambar CV tanpa OCR / API key: aman, tidak crash, is_scan=True
    dummy_img = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    monkeypatch.setenv("GEMINI_API_KEY", "")
    res = parse_cv_document(dummy_img, "image/png", "cv_pelamar.png")
    assert res["is_scan"] is True
    assert "cv_gambar" in res["flags"]

    # 2. Berkas gambar CV dengan Gemini OCR aktif: berhasil ekstrak teks dan is_scan=False
    def mock_gemini_vision(file_bytes, mime_type, api_key=None, timeout=25):
        return """
        Budi Santoso
        Email: budi.santoso@example.com | 08123456789
        
        Pendidikan:
        S1 Manajemen Bisnis, Universitas Gadjah Mada (2020-2024), IPK 3.80
        
        Pengalaman Kerja:
        Business Development Intern di PT Maju Mundur (Jan 2023 - Des 2023)
        Melakukan riset pasar, pitching klien, dan negosiasi kerja sama.
        
        Keahlian:
        Sales, Marketing, Negosiasi, Pitching, Riset Pasar
        """

    monkeypatch.setattr("api._lib.gemini.extract_text_via_gemini_vision", mock_gemini_vision)
    res_ocr = parse_cv_document(dummy_img, "image/png", "cv_pelamar.png")
    assert res_ocr["is_scan"] is False
    assert "ocr_gemini" in res_ocr["flags"]
    assert "Budi Santoso" in res_ocr["text"]
    assert "Manajemen Bisnis" in res_ocr["text"]

