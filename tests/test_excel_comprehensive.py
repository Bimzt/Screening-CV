import os
import sys
import io
import pytest
from openpyxl import load_workbook

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../api")))

from api._lib.extract import extract_education_details, clean_campus_name
from api._lib.excel import (
    generate_screening_excel,
    format_campus_display,
    format_major_display,
    format_gpa_display,
    format_phone_display,
    format_ai_eval_display,
    sanitize_excel_cell
)


def test_campus_multi_line_and_delimiter_cleaning():
    """Memastikan ekstraksi kampus mengatasi split-line PDF dan delimiter yang berantakan."""
    # 1. Kasus multi-line terpotong di PDF
    cv_split_1 = """
    EDUCATION
    Universitas
    Gadjah Mada
    Yogyakarta
    S1 Akuntansi (2020 - 2024)
    IPK: 3.82
    """
    res1 = extract_education_details(cv_split_1, cv_split_1)
    assert res1["university"] == "Universitas Gadjah Mada"
    assert res1["university_status"] == "ok"
    assert res1["grad_year_or_semester"] == "Lulus 2024"

    # 2. Kasus multi-line institut teknologi
    cv_split_2 = """
    EDUCATION
    Institut Teknologi
    Bandung
    Teknik Informatika, 2019-2023
    """
    res2 = extract_education_details(cv_split_2, cv_split_2)
    assert res2["university"] == "Institut Teknologi Bandung"
    assert res2["university_status"] == "ok"
    assert res2["grad_year_or_semester"] == "Lulus 2023"

    # 3. Kasus baris panjang dengan pipe, kota, gelar, dan GPA
    raw_pipe = "• Universitas Indonesia | Depok, Indonesia | Bachelor of Computer Science | GPA: 3.85 | 2020 - 2024"
    cleaned_c = clean_campus_name(raw_pipe)
    assert cleaned_c == "Universitas Indonesia"

    # 4. Kasus trailing lokasi
    raw_loc = "Universitas Brawijaya, Malang, Jawa Timur, Indonesia"
    assert clean_campus_name(raw_loc) == "Universitas Brawijaya"

    # 5. Kasus singkatan kampus ternama
    assert clean_campus_name("ITB") == "Institut Teknologi Bandung (ITB)"
    assert clean_campus_name("UI") == "Universitas Indonesia"
    assert clean_campus_name("UGM") == "Universitas Gadjah Mada (UGM)"
    assert clean_campus_name("BINUS") == "Binus University"


def test_campus_false_positives_avoided():
    """Memastikan kata-kata umum seperti 'club', 'fruit', 'UI design' tidak salah terdeteksi sebagai kampus."""
    text_cv = """
    EXPERIENCE
    Frontend Developer
    - Built intuitive UI components with React and Tailwind CSS.
    - Active in English Club and Debate Club.
    """
    res = extract_education_details("", text_cv)
    # Tidak boleh menganggap 'UI components' atau 'English Club' sebagai kampus
    assert res["university"] != "Built intuitive UI components with React and Tailwind CSS."
    assert res["university"] != "Active in English Club and Debate Club."


def test_excel_formatting_helpers():
    """Menguji helper pembersihan data khusus ekspor Excel."""
    # 1. Kampus display
    assert format_campus_display(None) == "-"
    assert format_campus_display("") == "-"
    assert format_campus_display("• Universitas Indonesia | Depok") == "Universitas Indonesia"
    assert format_campus_display("ITB") == "Institut Teknologi Bandung (ITB)"

    # 2. Jurusan display (Title Case dan akronim kapital)
    assert format_major_display("teknik informatika") == "Teknik Informatika"
    assert format_major_display("desain komunikasi visual (dkv)") == "Desain Komunikasi Visual (DKV)"
    assert format_major_display("manajemen sdm") == "Manajemen SDM"
    assert format_major_display(None) == "-"

    # 3. IPK display
    assert format_gpa_display(3.85) == 3.85
    assert format_gpa_display("3.75") == 3.75
    assert format_gpa_display(None) == "-"
    assert format_gpa_display("invalid") == "-"

    # 4. Nomor HP teks
    assert format_phone_display("+6281234567890") == "'+6281234567890"
    assert format_phone_display("081234567890") == "081234567890"
    assert format_phone_display(None) == "-"

    # 5. AI Evaluation terstruktur
    ai_data = {
        "modelUsed": "Gemini 3.8 Flash",
        "practicalLevel": "Tinggi",
        "contextualScore": 95,
        "executiveSummary": "Kandidat memiliki keunggulan eksekusi terbukti.",
        "keyStrength": "Arsitektur frontend performa tinggi.",
        "strengths": ["React", "TypeScript", "Next.js"],
        "areasToProbe": ["Manajemen state terdistribusi"],
        "interviewQuestion": "Bagaimana Anda memitigasi re-render berlebihan di Next.js?"
    }
    ai_text = format_ai_eval_display(ai_data)
    assert "[Gemini 3.8 Flash | Tinggi | Skor 95]" in ai_text
    assert "• Ringkasan Eksekutif:" in ai_text
    assert "• Keunggulan Utama:" in ai_text
    assert "• Pertanyaan Validasi:" in ai_text


def test_excel_export_layout_and_hyperlinks():
    """Menguji bahwa berkas Excel hasil ekspor memuat 4 sheet, format angka, dan hyperlink yang sah."""
    mock_ranking = {
        "meta": {"totalProcessed": 2},
        "divisionResults": {
            "Frontend Engineer": [
                {
                    "fileId": "cand_1",
                    "name": "Budi Santoso.pdf",
                    "email": "budi@example.com",
                    "phone": "+6281234567890",
                    "university": "Universitas Indonesia | Depok | 2020-2024",
                    "major": "teknik informatika",
                    "gpa": 3.85,
                    "graduationYearOrSemester": "Lulus 2024",
                    "skillsFound": ["React", "TypeScript", "Next.js"],
                    "experiences": [{"type": "kerja/magang", "title": "Frontend Lead", "durationMonths": 18}],
                    "projects": [{"title": "Portal E-Commerce Enterprise"}],
                    "certifications": ["AWS Certified Cloud Practitioner"],
                    "portfolioLinks": ["https://github.com/budisantoso"],
                    "categoryScores": {
                        "experience": 90.0,
                        "projects": 85.0,
                        "cert_edu": 80.0,
                        "competencies": 95.0
                    },
                    "finalScore": 89.5,
                    "hardRequirementStatus": "Memenuhi",
                    "aiEvaluation": {
                        "modelUsed": "Gemini",
                        "practicalLevel": "Tinggi",
                        "contextualScore": 92.0,
                        "executiveSummary": "Kesiapan kerja sangat kuat.",
                        "keyStrength": "Kepemimpinan teknis frontend."
                    },
                    "reasons": "Memenuhi IPK dan skill wajib.",
                    "driveLink": "https://drive.google.com/file/d/test123456789/view"
                }
            ]
        },
        "reviewList": [
            {
                "rowIndex": 3,
                "name": "Siti Scan",
                "division": "Frontend Engineer",
                "issueType": "Scan PDF",
                "suggestedAction": "Periksa berkas secara manual.",
                "driveLink": "https://drive.google.com/file/d/scan123/view"
            }
        ]
    }

    profiles = {
        "Frontend Engineer": {
            "title": "Lead Frontend Developer",
            "jd": "Membangun antarmuka web modern dengan Next.js.",
            "categories": {
                "experience": {"label": "Pengalaman", "weight": 35, "active": True},
                "competencies": {"label": "Kompetensi", "weight": 65, "active": True}
            },
            "hardRequirements": {"minGpa": 3.5}
        }
    }

    excel_bytes = generate_screening_excel(mock_ranking, profiles)
    assert len(excel_bytes) > 2000
    assert excel_bytes.startswith(b"PK\x03\x04")

    wb = load_workbook(io.BytesIO(excel_bytes))
    assert "Ranking" in wb.sheetnames
    assert "Perbandingan Pilihan 1 & 2" in wb.sheetnames
    assert "Perlu Dicek" in wb.sheetnames
    assert "Ringkasan Lowongan" in wb.sheetnames

    # Verifikasi Sheet 1: Ranking
    ws_rank = wb["Ranking"]
    assert ws_rank.views.sheetView[0].showGridLines is True

    # Nama pelamar (bersih dari .pdf)
    assert ws_rank.cell(row=2, column=4).value == "Budi Santoso"

    # Kampus (bersih dari pipe dan lokasi)
    assert ws_rank.cell(row=2, column=7).value == "Universitas Indonesia"

    # Jurusan (Title Case)
    assert ws_rank.cell(row=2, column=8).value == "Teknik Informatika"

    # IPK (angka float)
    assert ws_rank.cell(row=2, column=9).value == 3.85
    assert ws_rank.cell(row=2, column=9).number_format == '0.00'

    # Skor Akhir (bold)
    assert ws_rank.cell(row=2, column=20).value == 89.5
    assert ws_rank.cell(row=2, column=20).font.bold is True

    # Status Syarat Wajib (fill hijau)
    status_cell = ws_rank.cell(row=2, column=21)
    assert status_cell.value == "Memenuhi"
    assert status_cell.fill.start_color.rgb == "00DCFCE7"

    # Hyperlink Drive
    link_cell = ws_rank.cell(row=2, column=28)
    assert link_cell.value == "https://drive.google.com/file/d/test123456789/view"
    assert link_cell.hyperlink is not None
    assert link_cell.font.underline == "single"
