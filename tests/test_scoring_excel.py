import os
import sys
import io
import pytest
from openpyxl import load_workbook

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../api")))

from api._lib.scoring import (
    safe_skill_match,
    evaluate_hard_requirements,
    calculate_category_scores,
    rank_candidates_for_batch,
)
from api._lib.excel import sanitize_excel_cell, generate_screening_excel


def test_safe_skill_match():
    text = "Saya menguasai C++, Python, SQL, dan Power BI untuk analisis data."
    assert safe_skill_match("c++", text) is True
    assert safe_skill_match("python", text) is True
    assert safe_skill_match("sql", text) is True
    assert safe_skill_match("power bi", text) is True
    assert safe_skill_match("java", text) is False
    assert safe_skill_match("c#", text) is False


def test_formula_injection_sanitization():
    assert sanitize_excel_cell("=1+1") == "'=1+1"
    assert sanitize_excel_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_excel_cell("-123") == "'-123"
    assert sanitize_excel_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_excel_cell("John Doe") == "John Doe"
    assert sanitize_excel_cell(3.75) == 3.75


def test_hard_requirements_evaluation():
    profile = {
        "division": "Data Analyst",
        "hardRequirements": {
            "minGpa": 3.0,
            "allowedMajors": ["Informatika", "Sistem Informasi"],
            "mandatorySkills": {
                "items": ["SQL", "Python"],
                "rule": "all"
            }
        }
    }

    # Kasus 1: Memenuhi semua syarat
    cand_pass = {
        "fields": {"gpa": 3.5, "major": "Teknik Informatika"},
        "fieldStatus": {"gpa": "ok", "major": "ok"}
    }
    status, reasons = evaluate_hard_requirements(cand_pass, profile, "Memiliki kemampuan SQL dan Python mendalam.")
    assert status == "Memenuhi"

    # Kasus 2: IPK di bawah minimum
    cand_low_gpa = {
        "fields": {"gpa": 2.8, "major": "Sistem Informasi"},
        "fieldStatus": {"gpa": "ok", "major": "ok"}
    }
    status, reasons = evaluate_hard_requirements(cand_low_gpa, profile, "Menguasai SQL dan Python.")
    assert status == "Tidak memenuhi"
    assert any("di bawah syarat minimum" in r for r in reasons)

    # Kasus 3: IPK ambigu / tidak terbaca -> Perlu Dicek
    cand_ambiguous_gpa = {
        "fields": {"gpa": None, "major": "Informatika"},
        "fieldStatus": {"gpa": "ambigu", "major": "ok"}
    }
    status, reasons = evaluate_hard_requirements(cand_ambiguous_gpa, profile, "Menguasai SQL dan Python.")
    assert status == "Perlu dicek"


def test_batch_ranking_and_excel_export():
    profile_da = {
        "division": "Data Analyst",
        "title": "Data Analyst Intern",
        "jd": "Menganalisis data, membuat query SQL, dan visualisasi Tableau.",
        "categories": {
            "experience": {"label": "Pengalaman", "weight": 35, "active": True},
            "projects": {"label": "Project", "weight": 30, "active": True},
            "cert_edu": {"label": "Pendidikan", "weight": 20, "active": True},
            "competencies": {"label": "Kompetensi", "weight": 15, "active": True},
        },
        "thresholds": {"durationMonths": 12, "projectsCount": 3},
        "additionalSkills": ["SQL", "Tableau", "Python"],
    }

    candidates = [
        {
            "fileId": "file_1",
            "candidateName": "Kandidat A",
            "divisionChoices": ["Data Analyst"],
            "fields": {
                "name": "Kandidat A",
                "email": "a@test.com",
                "phone": "+62811111111",
                "university": "Universitas Indonesia",
                "major": "Sistem Informasi",
                "gpa": 3.8,
                "portfolioLinks": ["https://github.com/a"],
                "experiences": [{"title": "Data Intern", "durationMonths": 12, "type": "kerja/magang"}],
                "projects": [{"title": "Sales Dashboard"}],
                "certifications": ["Google Data Analytics"],
            },
            "sections": {
                "experience": "Data Analyst Intern menggunakan SQL dan Tableau.",
                "projects": "Dashboard penjualan.",
                "skills": "SQL, Python, Tableau",
            },
            "fieldStatus": {"gpa": "ok", "major": "ok"},
            "flags": [],
            "isScanPdf": False,
        },
        {
            "fileId": "file_2",
            "candidateName": "Kandidat Scan",
            "divisionChoices": ["Data Analyst"],
            "fields": {"name": "Kandidat Scan"},
            "sections": {},
            "fieldStatus": {},
            "flags": ["pdf_scan"],
            "isScanPdf": True,
        }
    ]

    ranking_res = rank_candidates_for_batch(candidates, {"Data Analyst": profile_da})
    assert "Data Analyst" in ranking_res["divisionResults"]
    assert len(ranking_res["divisionResults"]["Data Analyst"]) == 1
    assert len(ranking_res["reviewList"]) == 1  # Kandidat scan masuk review list

    top_cand = ranking_res["divisionResults"]["Data Analyst"][0]
    assert top_cand["rank"] == 1
    assert top_cand["finalScore"] > 0

    # Test Excel generation
    excel_bytes = generate_screening_excel(ranking_res, {"Data Analyst": profile_da})
    assert len(excel_bytes) > 1000

    wb = load_workbook(io.BytesIO(excel_bytes))
    sheet_names = wb.sheetnames
    assert "Ranking" in sheet_names
    assert "Perlu Dicek" in sheet_names
    assert "Ringkasan Lowongan" in sheet_names

    ws_rank = wb["Ranking"]
    assert ws_rank.cell(row=2, column=1).value == "Data Analyst"
    assert ws_rank.cell(row=2, column=3).value == "Pilihan 1"
    assert ws_rank.cell(row=2, column=4).value == "Kandidat A"
    assert "Perbandingan Pilihan 1 & 2" in sheet_names


def test_dual_choice_ranking_and_recommendation():
    """
    Menguji bahwa kandidat dengan 2 pilihan dinilai di kedua divisi dan menghasilkan
    rekomendasi komparatif yang tepat.
    """
    profile_p1 = {
        "division": "Data Analyst",
        "title": "Data Analyst",
        "jd": "SQL, Python, data analytics, tableau.",
        "categories": {
            "experience": {"label": "Pengalaman", "weight": 50, "active": True},
            "projects": {"label": "Project", "weight": 50, "active": True},
        },
        "thresholds": {"durationMonths": 12, "projectsCount": 2},
    }
    profile_p2 = {
        "division": "Graphic Designer",
        "title": "Graphic Designer",
        "jd": "Figma, Adobe Illustrator, Photoshop, visual design, branding.",
        "categories": {
            "experience": {"label": "Pengalaman", "weight": 50, "active": True},
            "projects": {"label": "Project", "weight": 50, "active": True},
        },
        "thresholds": {"durationMonths": 12, "projectsCount": 2},
    }

    # Kandidat melamar Pilihan 1: Data Analyst, Pilihan 2: Graphic Designer
    # CV memuat banyak portofolio desain visual & Figma
    cand = {
        "fileId": "cand_dual_1",
        "candidateName": "Bima Arya",
        "divisionChoices": ["Data Analyst", "Graphic Designer"],
        "fields": {
            "name": "Bima Arya",
            "email": "bima@example.com",
            "phone": "08123456789",
            "university": "Universitas Indonesia",
            "major": "Desain Komunikasi Visual",
            "gpa": 3.75,
            "portfolioLinks": ["https://behance.net/bima"],
            "experiences": [{"title": "Graphic Design Intern", "durationMonths": 14, "type": "kerja/magang"}],
            "projects": [{"title": "Branding Campaign"}, {"title": "UI Kit Redesign"}],
            "certifications": ["Adobe Certified Professional"],
        },
        "sections": {
            "experience": "Graphic Designer di agency, mahir Figma, Adobe Illustrator, Photoshop.",
            "projects": "Redesign UI dan branding campaign visual.",
            "skills": "Figma, Illustrator, Photoshop, Branding, Visual Design",
        },
        "fieldStatus": {},
        "flags": [],
        "isScanPdf": False,
    }

    profiles_map = {
        "Data Analyst": profile_p1,
        "Graphic Designer": profile_p2,
    }

    res = rank_candidates_for_batch([cand], profiles_map)
    assert "Data Analyst" in res["divisionResults"]
    assert "Graphic Designer" in res["divisionResults"]

    c_da = res["divisionResults"]["Data Analyst"][0]
    c_gd = res["divisionResults"]["Graphic Designer"][0]

    # Pastikan metadata pilihan terpasang
    assert c_da["choiceRank"] == 1
    assert c_da["isFirstChoice"] is True
    assert c_gd["choiceRank"] == 2
    assert c_gd["isFirstChoice"] is False

    # Pastikan kedua hasil saling terhubung
    assert c_da["choice1Result"]["division"] == "Data Analyst"
    assert c_da["choice2Result"]["division"] == "Graphic Designer"
    assert c_gd["choice1Result"]["division"] == "Data Analyst"
    assert c_gd["choice2Result"]["division"] == "Graphic Designer"

    # Kandidat memiliki portofolio DKV / Figma kuat, sehingga skor di Graphic Designer > Data Analyst
    assert c_gd["finalScore"] > c_da["finalScore"]
    assert c_da["bestFitChoice"] == 2
    assert "Pilihan 2" in c_da["recommendationNote"]

    # Verifikasi pembuatan berkas Excel
    excel_bytes = generate_screening_excel(res, profiles_map)
    wb = load_workbook(io.BytesIO(excel_bytes))
    ws_comp = wb["Perbandingan Pilihan 1 & 2"]
    assert ws_comp.cell(row=2, column=2).value == "Bima Arya"
    assert ws_comp.cell(row=2, column=8).value == "Data Analyst"
    assert ws_comp.cell(row=2, column=11).value == "Graphic Designer"
    assert ws_comp.cell(row=2, column=14).value == "Pilihan 2"


def test_excel_illegal_characters_sanitization():
    """
    Menguji bahwa teks CV dengan karakter kontrol ilegal XML (ASCII 0-31)
    dibersihkan secara otomatis dan tidak menyebabkan openpyxl IllegalCharacterError.
    """
    profile = {
        "division": "Staff",
        "title": "Staff Umum",
        "jd": "Deskripsi pekerjaan staff umum.",
        "categories": {
            "experience": {"label": "Pengalaman", "weight": 100, "active": True},
        },
    }

    # Teks pengalaman mengandung karakter kontrol seperti vertical tab (\x0b), form feed (\x0c), null (\x00)
    cand = {
        "fileId": "cand_control_chars",
        "candidateName": "Pelamar Karakter Kontrol",
        "divisionChoices": ["Staff"],
        "fields": {
            "name": "Pelamar \x0b Karakter \x0c Kontrol",
            "email": "test\x01@gmail.com",
            "phone": "08123\x02456",
            "university": "Universitas \x03 Indonesia",
            "major": "Manajemen \x04",
            "experiences": [
                {
                    "title": "Sta of Funding \x0b KSPM FEB UBB \x0c (3 bln)",
                    "durationMonths": 3,
                    "type": "kerja/magang"
                }
            ],
            "projects": [{"title": "Project \x05 Rahasia"}],
            "certifications": ["Cert \x06 Internasional"],
            "portfolioLinks": ["https://drive.google.com/\x07link"],
        },
        "sections": {
            "experience": "Pengalaman kerja dengan \x0b kontrol chars.",
        },
        "fieldStatus": {},
        "flags": [],
        "isScanPdf": False,
    }

    res = rank_candidates_for_batch([cand], {"Staff": profile})
    # Harus berhasil membuat file Excel tanpa IllegalCharacterError
    excel_bytes = generate_screening_excel(res, {"Staff": profile})
    assert len(excel_bytes) > 1000

    wb = load_workbook(io.BytesIO(excel_bytes))
    ws_rank = wb["Ranking"]
    # Karakter kontrol \x0b dan \x0c harus sudah dibersihkan
    exp_cell = ws_rank.cell(row=2, column=12).value
    assert "\x0b" not in exp_cell
    assert "\x0c" not in exp_cell
    assert "Sta of Funding" in exp_cell


def test_tier2_gemini_graceful_fallback_without_key():
    from api._lib.gemini import evaluate_candidates_tier2
    candidates = [{"fileId": "c1", "name": "Budi"}]
    profile = {"division": "IT", "jd": "Software Engineer"}
    # Tanpa api_key dan tanpa environment variable -> dict kosong
    res = evaluate_candidates_tier2(candidates, profile, api_key=None)
    assert res == {}


def test_batch_ranking_with_tier2_ai_evaluation():
    from unittest.mock import patch

    mock_gemini_response = {
        "c_1": {
            "contextualScore": 92.0,
            "practicalLevel": "Tinggi",
            "executiveSummary": "Memiliki bukti eksekusi proyek nyata dengan skala terukur.",
            "keyStrength": "Kepemimpinan Proyek"
        }
    }

    cand = {
        "fileId": "c_1",
        "candidateName": "Andi Pratama",
        "divisionChoices": ["IT Support"],
        "fields": {
            "name": "Andi Pratama",
            "email": "andi@example.com",
            "university": "ITB",
            "major": "Teknik Informatika",
            "gpa": 3.8
        },
        "sections": {
            "experience": "Memimpin pengembangan sistem antrian tiket IT.",
            "projects": "Sistem monitoring server.",
            "skills": "Python, Linux, Networking"
        },
        "fieldStatus": {"gpa": "ok", "major": "ok"},
        "flags": [],
        "isScanPdf": False
    }

    profile = {
        "division": "IT Support",
        "title": "IT Support Specialist",
        "jd": "Menangani troubleshooting hardware, software, dan jaringan.",
        "categories": {
            "experience": {"label": "Pengalaman", "weight": 35, "active": True},
            "projects": {"label": "Project", "weight": 30, "active": True},
            "cert_edu": {"label": "Pendidikan", "weight": 20, "active": True},
            "competencies": {"label": "Kompetensi", "weight": 15, "active": True},
        },
        "thresholds": {"durationMonths": 6, "projectsCount": 2},
    }

    with patch("api._lib.scoring.evaluate_candidates_tier2", return_value=mock_gemini_response):
        ranking_result = rank_candidates_for_batch([cand], {"IT Support": profile})
        ranked_cand = ranking_result["divisionResults"]["IT Support"][0]
        assert "aiEvaluation" in ranked_cand
        assert ranked_cand["aiEvaluation"]["contextualScore"] == 92.0
        assert "✨ AI:" in ranked_cand["reasons"]

        # Generate excel dan verifikasi kolom Evaluasi AI (kolom 22)
        excel_bytes = generate_screening_excel(ranking_result, {"IT Support": profile})
        wb = load_workbook(io.BytesIO(excel_bytes))
        ws_rank = wb["Ranking"]
        ai_col_header = ws_rank.cell(row=1, column=22).value
        assert ai_col_header == "Evaluasi AI (Gemini)"
        ai_val = ws_rank.cell(row=2, column=22).value
        assert "[Tinggi | Skor 92.0]" in ai_val
        assert "Kepemimpinan Proyek" in ai_val


def test_tier2_gemini_edge_cases_and_markdown_stripping():
    from unittest.mock import patch, MagicMock
    from api._lib.gemini import evaluate_candidates_tier2, _safe_float

    # Test _safe_float
    assert _safe_float(95) == 95.0
    assert _safe_float("85/100") == 85.0
    assert _safe_float("90%") == 90.0
    assert _safe_float("invalid", default=50.0) == 50.0

    # Mock response Gemini dengan pembungkus markdown ```json ... ```
    mock_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "```json\n{\n  \"evaluations\": [\n    {\n      \"candidateId\": \"c_test\",\n      \"contextualScore\": \"88/100\",\n      \"practicalLevel\": \"Tinggi\",\n      \"executiveSummary\": \"Eksekusi nyata terbukti kuat.\",\n      \"keyStrength\": \"Problem Solver\"\n    }\n  ]\n}\n```"
                        }
                    ]
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json_bytes = io.BytesIO(import_json_dumps := __import__("json").dumps(mock_payload).encode("utf-8")).getvalue()
    mock_resp.__enter__.return_value = mock_resp

    candidates = [
        {
            "fileId": "c_test",
            "name": "Budi Santoso",
            "experiences": [None, {"title": "HR Lead", "durationMonths": 12, "type": "kerja"}, "Freelance"],
            "projects": [None, {"title": "Modul TNA"}],
            "certifications": [None, {"title": "CHRP"}],
            "skillsFound": ["TNA", None, "Training"]
        }
    ]
    profile = {"division": "HR", "jd": "Menganalisis TNA"}

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = evaluate_candidates_tier2(candidates, profile, api_key="  dummy_key_with_spaces  ")
        assert "c_test" in res
        assert res["c_test"]["contextualScore"] == 88.0
        assert res["c_test"]["practicalLevel"] == "Tinggi"
        assert res["c_test"]["keyStrength"] == "Problem Solver"



