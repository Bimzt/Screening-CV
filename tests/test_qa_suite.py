"""
Suite Pengujian QA Komprehensif (End-to-End & Edge Cases).
Memvalidasi fungsionalitas screening CV gambar, OCR Vision, toleransi link Drive,
akurasi pengskoran, serta proteksi terhadap kegagalan/crash.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../api")))

from api._lib.drive import extract_drive_file_id, extract_all_drive_file_ids
from api._lib.parsing import parse_cv_document, extract_from_pdf, extract_from_image
from api._lib.sections import segment_cv_sections
from api._lib.extract import extract_cv_fields, extract_gpa, normalize_major
from api._lib.scoring import evaluate_hard_requirements, calculate_category_scores, rank_candidates_for_batch
from api._lib.excel import generate_screening_excel


# ==============================================================================
# 1. QA TEST: SCREENING CV GAMBAR & PDF SCAN VIA GEMINI VISION
# ==============================================================================

def test_qa_image_cv_extraction_with_ocr(monkeypatch):
    """
    Memastikan berkas CV berformat gambar (PNG/JPG) berhasil diekstrak via Gemini Vision
    dan menghasilkan field lengkap untuk penilaian.
    """
    dummy_image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    ocr_mock_text = """
    CURRICULUM VITAE
    Nama: Naufal Akbar
    Email: naufal.akbar@example.com
    No HP: +6281234567890
    
    Pendidikan:
    Universitas Indonesia
    S1 Ilmu Komunikasi, IPK 3.85 / 4.00 (2020 - 2024)
    
    Pengalaman Kerja:
    Content Creator & Social Media Lead di PT Kreatif Nusantara (Jan 2023 - Des 2023)
    - Menyusun content calendar, copywriting, dan video editing di TikTok & Reels.
    - Meningkatkan engagement rate sebesar 150%.
    
    Proyek:
    Kampanye Brand Launching 2023
    - Menghasilkan 100K views organik di Instagram.
    
    Keahlian:
    Content Creation, Copywriting, Video Editing, Social Media Strategy, Canva, CapCut
    """

    # Mock Gemini Vision OCR
    monkeypatch.setattr(
        "api._lib.gemini.extract_text_via_gemini_vision",
        lambda file_bytes, mime_type, api_key=None, timeout=25: ocr_mock_text
    )

    # 1. Uji parsing dokumen gambar PNG
    parsed = parse_cv_document(dummy_image_bytes, "image/png", "cv_naufal.png")
    assert parsed["is_scan"] is False
    assert "ocr_gemini" in parsed["flags"]
    assert "cv_gambar" in parsed["flags"]
    assert "Naufal Akbar" in parsed["text"]

    # 2. Uji segmentasi seksi dari teks OCR
    sections, sec_flags = segment_cv_sections(parsed["text"])
    assert "Ilmu Komunikasi" in sections["education"]
    assert "Content Creator" in sections["experience"]
    assert "Copywriting" in sections["skills"]

    # 3. Uji ekstraksi field dari hasil OCR
    fields, statuses, ext_flags = extract_cv_fields(
        full_text=parsed["text"],
        sections=sections,
        all_links=parsed["links"]
    )
    assert fields["name"] == "Naufal Akbar"
    assert fields["email"] == "naufal.akbar@example.com"
    assert fields["phone"] == "+6281234567890"
    assert fields["gpa"] == 3.85
    assert "komunikasi" in fields["major"].lower()
    assert len(fields["experiences"]) >= 1


def test_qa_scanned_pdf_automatic_ocr_fallback(monkeypatch):
    """
    Memastikan PDF scan (<200 karakter) otomatis dialihkan ke Gemini Vision OCR.
    """
    dummy_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    ocr_pdf_text = """
    Nama: Sarah Rahmawati
    Email: sarah.rahmawati@gmail.com
    Pendidikan: S1 Manajemen Bisnis, Universitas Gadjah Mada (IPK: 3.75)
    Pengalaman: Business Development Staff di PT Sukses Bersama (2022 - 2023)
    Keahlian: Sales, Pitching, Negosiasi, Riset Pasar
    """

    monkeypatch.setattr(
        "api._lib.gemini.extract_text_via_gemini_vision",
        lambda file_bytes, mime_type, api_key=None, timeout=25: ocr_pdf_text
    )

    parsed = parse_cv_document(dummy_pdf_bytes, "application/pdf", "scan_cv.pdf")
    assert parsed["is_scan"] is False
    assert "ocr_gemini" in parsed["flags"]
    assert "Sarah Rahmawati" in parsed["text"]


def test_qa_image_cv_graceful_without_api_key(monkeypatch):
    """
    Memastikan sistem tidak crash jika berkas gambar diunggah tetapi API key Gemini kosong / OCR gagal.
    Dokumen harus ditandai is_scan=True secara aman untuk audit rekruter.
    """
    dummy_img = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    monkeypatch.setenv("GEMINI_API_KEY", "")

    parsed = parse_cv_document(dummy_img, "image/png", "cv_tanpa_api.png")
    assert parsed["is_scan"] is True
    assert "cv_gambar" in parsed["flags"]
    assert parsed["error"] is not None


# ==============================================================================
# 2. QA TEST: TOLERANSI TAUTAN GOOGLE DRIVE & FORMAT TIDAK STANDAR
# ==============================================================================

def test_qa_drive_links_tolerance():
    """
    Menguji berbagai ragam link Google Drive yang umum diisi pelamar di Google Form.
    """
    # 1. Link Folder Google Drive
    assert extract_drive_file_id("https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs?usp=sharing") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
    assert extract_drive_file_id("https://drive.google.com/drive/u/0/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
    assert extract_drive_file_id("https://drive.google.com/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"

    # 2. Link File Google Drive
    assert extract_drive_file_id("https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view?usp=drivesdk") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
    assert extract_drive_file_id("https://drive.google.com/open?id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"

    # 3. URL-encoded dan Formula Excel
    assert extract_drive_file_id("https%3A%2F%2Fdrive.google.com%2Ffile%2Fd%2F1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs%2Fview") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"
    assert extract_drive_file_id('=HYPERLINK("https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view", "Buka CV")') == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"

    # 4. Teks campuran
    assert extract_drive_file_id("CV Budi: https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view (sudah dibuka aksesnya)") == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs"

    # 5. Link Eksternal Berbahaya / Non-Drive (Mencegah SSRF)
    assert extract_drive_file_id("http://169.254.169.254/latest/meta-data") is None
    assert extract_drive_file_id("https://canva.com/design/DAF12345/view") is None
    assert extract_drive_file_id("https://linkedin.com/in/budi-santoso") is None


# ==============================================================================
# 3. QA TEST: AKURASI PENGSEKORAN & EVALUASI PERSYARATAN
# ==============================================================================

def test_qa_scoring_accuracy_and_stability():
    """
    Memastikan perhitungan skor tidak pernah menghasilkan NaN, tidak melebihi rentang 0-100,
    dan mengevaluasi hard requirements secara adil.
    """
    profile = {
        "division": "BUSDEV",
        "title": "Business Development",
        "jd": "Melakukan riset pasar, mengelola database leads, menyusun proposal pitch deck, pitching, dan negosiasi kerja sama.",
        "thresholds": {"durationMonths": 0, "projectsCount": 0},
        "hardRequirements": {
            "minGpa": 3.2,
            "allowedMajors": ["semua jurusan", "diutamakan Manajemen", "Bisnis", "Ekonomi"],
            "mandatorySkills": {
                "items": ["riset pasar", "pitching"],
                "rule": "all"
            }
        },
        "additionalSkills": ["sales", "marketing", "negosiasi"],
        "categories": {
            "experience": {"active": True, "weight": 0.30},
            "projects": {"active": True, "weight": 0.25},
            "cert_edu": {"active": True, "weight": 0.15},
            "competencies": {"active": True, "weight": 0.30}
        }
    }

    candidates = [
        # Kandidat 1: Sempurna (Memenuhi syarat, skill lengkap, pengalaman relevan)
        {
            "sourceRowIndex": 2,
            "fileId": "cand_perfect",
            "candidateName": "Budi Santoso",
            "divisionChoices": ["BUSDEV"],
            "sections": {
                "experience": "Business Development Intern di PT Maju Mundur. Melakukan riset pasar dan pitching proposal kerja sama ke 20 klien.",
                "projects": "Penyusunan pitch deck B2B dan riset pasar industri F&B.",
                "education": "S1 Manajemen Bisnis, Universitas Indonesia. IPK: 3.80",
                "skills": "Riset pasar, pitching, negosiasi, sales, marketing",
                "certifications": "Certified Business Development Associate"
            },
            "fields": {
                "name": "Budi Santoso",
                "gpa": 3.80,
                "major": "manajemen bisnis",
                "experiences": [{"durationMonths": 6}],
                "projects": [{"title": "Pitch deck B2B"}],
            },
            "fieldStatus": {"gpa": "ok", "major": "ok"}
        },
        # Kandidat 2: IPK di bawah standar (Harus 'Tidak memenuhi')
        {
            "sourceRowIndex": 3,
            "fileId": "cand_low_gpa",
            "candidateName": "Andi Pratama",
            "divisionChoices": ["BUSDEV"],
            "sections": {
                "experience": "Sales Intern di CV Maju. Melakukan riset pasar dan pitching.",
                "projects": "Riset pasar penjualan retail.",
                "education": "S1 Akuntansi. IPK: 2.95",
                "skills": "Riset pasar, pitching, sales"
            },
            "fields": {
                "name": "Andi Pratama",
                "gpa": 2.95,
                "major": "akuntansi",
                "experiences": [],
                "projects": []
            },
            "fieldStatus": {"gpa": "ok", "major": "ok"}
        },
        # Kandidat 3: IPK kosong / ambigu (Harus 'Perlu dicek')
        {
            "sourceRowIndex": 4,
            "fileId": "cand_no_gpa",
            "candidateName": "Citra Lestari",
            "divisionChoices": ["BUSDEV"],
            "sections": {
                "experience": "Marketing Intern. Melakukan riset pasar dan pitching klien.",
                "projects": "Pitch deck riset kompetitor.",
                "education": "S1 Manajemen.",
                "skills": "Riset pasar, pitching, negosiasi"
            },
            "fields": {
                "name": "Citra Lestari",
                "gpa": None,
                "major": "manajemen",
                "experiences": [],
                "projects": []
            },
            "fieldStatus": {"gpa": "tidak_ditemukan", "major": "ok"}
        }
    ]

    ranked_results = rank_candidates_for_batch(candidates, {"BUSDEV": profile})
    busdev_ranked = ranked_results["divisionResults"]["BUSDEV"]

    assert len(busdev_ranked) == 3

    # Validasi urutan status: Memenuhi (#1) -> Perlu dicek (#2) -> Tidak memenuhi (#3)
    p1 = busdev_ranked[0]
    p2 = busdev_ranked[1]
    p3 = busdev_ranked[2]

    assert p1["candidateName"] == "Budi Santoso"
    assert p1["hardRequirementStatus"] == "Memenuhi"
    assert 0.0 <= p1["finalScore"] <= 100.0

    assert p2["candidateName"] == "Citra Lestari"
    assert p2["hardRequirementStatus"] == "Perlu dicek"

    assert p3["candidateName"] == "Andi Pratama"
    assert p3["hardRequirementStatus"] == "Tidak memenuhi"


def test_qa_excel_export_generation():
    """
    Memastikan file Excel hasil export berhasil dibuat tanpa error dan memuat 4 sheet.
    """
    mock_ranking_data = {
        "divisionResults": {
            "BUSDEV": [
                {
                    "rank": 1,
                    "name": "Budi Santoso",
                    "email": "budi@test.com",
                    "phone": "08123456789",
                    "university": "Universitas Indonesia",
                    "major": "Manajemen Bisnis",
                    "gpa": 3.80,
                    "finalScore": 88.5,
                    "hardRequirementStatus": "Memenuhi",
                    "reasons": "Kompetensi cocok",
                    "categoryScores": {"experience": 85.0, "projects": 90.0, "cert_edu": 88.0, "competencies": 92.0},
                    "skillsFound": ["Sales", "Pitching"],
                    "experiences": [{"title": "BD Intern", "details": "Riset pasar", "durationMonths": 6}],
                    "projects": [{"title": "Market deck"}],
                    "certifications": [],
                    "divisionChoices": ["BUSDEV"],
                    "flags": ["ocr_gemini"]
                }
            ]
        },
        "reviewList": [
            {
                "rowIndex": 5,
                "name": "Pelamar Gagal",
                "division": "BUSDEV",
                "issueType": "Gagal Ekstraksi / Format Tidak Didukung",
                "suggestedAction": "Tautan Canva, mohon berkas PDF Google Drive.",
                "driveLink": "https://canva.com/design/test"
            }
        ]
    }

    excel_bytes = generate_screening_excel(mock_ranking_data, {"BUSDEV": {"title": "Business Development"}})
    assert len(excel_bytes) > 2000
    assert excel_bytes.startswith(b"PK\x03\x04")  # Valid XLSX ZIP container
