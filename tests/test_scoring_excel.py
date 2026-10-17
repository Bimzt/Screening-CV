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
    assert ws_rank.cell(row=2, column=3).value == "Kandidat A"
    assert ws_rank.cell(row=2, column=1).value == "Data Analyst"
