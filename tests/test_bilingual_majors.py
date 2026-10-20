"""
Test suite untuk validasi ekstraksi dan pencocokan jurusan dwibahasa (Bahasa Indonesia & Bahasa Inggris).
Memastikan CV berbahasa Inggris terdeteksi jurusannya secara akurat dan cocok dengan syarat lowongan.
"""

import pytest
from api._lib.extract import (
    normalize_major,
    extract_education_details,
    extract_gpa,
    classify_experience_type,
    estimate_duration_months
)
from api._lib.sections import segment_cv_sections
from api._lib.scoring import (
    is_bilingual_major_match,
    evaluate_hard_requirements,
    safe_skill_match,
    calculate_category_scores
)
from sklearn.feature_extraction.text import TfidfVectorizer


# ==============================================================================
# 1. TEST NORMALISASI JURUSAN DWIBAHASA
# ==============================================================================

def test_normalize_major_bilingual():
    # Format Indonesia
    assert normalize_major("S1 Teknik Informatika") == "teknik informatika"
    assert normalize_major("Program Studi Ilmu Komunikasi") == "ilmu komunikasi"
    assert normalize_major("Jurusan Manajemen Bisnis, S1") == "manajemen bisnis"
    assert normalize_major("Sarjana Ekonomi") == "ekonomi"
    assert normalize_major("D4 Manajemen Perhotelan") == "manajemen perhotelan"

    # Format Inggris
    assert normalize_major("Bachelor of Science in Computer Science") == "computer science"
    assert normalize_major("B.A. in Communication Studies") == "communication studies"
    assert normalize_major("Bachelor of Business Administration (BBA)") == "business administration"
    assert normalize_major("B.S. in Information Systems") == "information systems"
    assert normalize_major("Bachelor of Economics") == "economics"
    assert normalize_major("Major: Marketing, GPA: 3.85/4.00") == "marketing"
    assert normalize_major("Field of Study: Digital Marketing") == "digital marketing"
    assert normalize_major("Undergraduate in Software Engineering") == "software engineering"
    assert normalize_major("Bachelor of Engineering (B.Eng) in Industrial Engineering") == "industrial engineering"


# ==============================================================================
# 2. TEST EKSTRAKSI PENDIDIKAN & JURUSAN DARI TEKS CV INGGRIS
# ==============================================================================

def test_extract_education_details_english_cv():
    # Kasus 1: Gelar Bachelor of Science dengan "in"
    edu_text_1 = """
    EDUCATION
    Universitas Indonesia | Depok, Indonesia
    Bachelor of Science in Marketing, GPA: 3.85 / 4.00
    August 2020 - July 2024
    """
    res1 = extract_education_details(edu_text_1, edu_text_1)
    assert res1["university_status"] == "ok"
    assert res1["major"] == "marketing"
    assert res1["major_status"] == "ok"

    # Kasus 2: Singkatan B.A. / B.Sc
    edu_text_2 = """
    Academic Background:
    Binus University
    B.A. in Communication Studies (2019 - 2023)
    Cumulative GPA: 3.72
    """
    res2 = extract_education_details(edu_text_2, edu_text_2)
    assert res2["university_status"] == "ok"
    assert "communication" in res2["major"]
    assert res2["major_status"] == "ok"

    # Kasus 3: Label eksplisit Major: atau Field of Study:
    edu_text_3 = """
    EDUCATION
    Institut Teknologi Bandung
    Degree: Bachelor of Science
    Major: Computer Science
    GPA: 3.90/4.00
    """
    res3 = extract_education_details(edu_text_3, edu_text_3)
    assert res3["university_status"] == "ok"
    assert res3["major"] == "computer science"
    assert res3["major_status"] == "ok"

    # Kasus 4: Gelar BBA
    edu_text_4 = """
    Education:
    Prasetiya Mulya University
    Bachelor of Business Administration (BBA)
    Graduated with Honors
    """
    res4 = extract_education_details(edu_text_4, edu_text_4)
    assert res4["university_status"] == "ok"
    assert "business administration" in res4["major"]
    assert res4["major_status"] == "ok"


# ==============================================================================
# 3. TEST PENCOCOKAN JURUSAN DWIBAHASA (ID <-> EN)
# ==============================================================================

def test_bilingual_major_matching():
    # Pemasaran <-> Marketing
    assert is_bilingual_major_match("Pemasaran", "Marketing")
    assert is_bilingual_major_match("Marketing", "Pemasaran")
    assert is_bilingual_major_match("Pemasaran", "Digital Marketing")
    assert is_bilingual_major_match("Pemasaran", "marketing management")

    # Manajemen <-> Management
    assert is_bilingual_major_match("Manajemen", "Management")
    assert is_bilingual_major_match("Management", "Manajemen")
    assert is_bilingual_major_match("Manajemen", "Business Management")
    assert is_bilingual_major_match("Manajemen Bisnis", "Management")

    # Bisnis <-> Business
    assert is_bilingual_major_match("Bisnis", "Business")
    assert is_bilingual_major_match("Bisnis", "Business Administration")
    assert is_bilingual_major_match("Administrasi Bisnis", "Business Administration")

    # Komunikasi <-> Communication
    assert is_bilingual_major_match("Komunikasi", "Communication")
    assert is_bilingual_major_match("Komunikasi", "Communication Studies")
    assert is_bilingual_major_match("Ilmu Komunikasi", "Mass Communication")
    assert is_bilingual_major_match("Humas", "Public Relations")

    # Ekonomi <-> Economics
    assert is_bilingual_major_match("Ekonomi", "Economics")
    assert is_bilingual_major_match("Ilmu Ekonomi", "Economics")
    assert is_bilingual_major_match("Ekonomi Pembangunan", "Development Economics")

    # Akuntansi <-> Accounting
    assert is_bilingual_major_match("Akuntansi", "Accounting")
    assert is_bilingual_major_match("Keuangan", "Finance")

    # Teknologi & Komputer
    assert is_bilingual_major_match("Ilmu Komputer", "Computer Science")
    assert is_bilingual_major_match("Teknik Informatika", "Software Engineering")
    assert is_bilingual_major_match("Teknik Informatika", "Informatics")
    assert is_bilingual_major_match("Sistem Informasi", "Information Systems")
    assert is_bilingual_major_match("Sains Data", "Data Science")
    assert is_bilingual_major_match("Statistika", "Statistics")

    # Desain & Seni
    assert is_bilingual_major_match("Desain Grafis", "Graphic Design")
    assert is_bilingual_major_match("Desain Komunikasi Visual", "Visual Communication Design")
    assert is_bilingual_major_match("DKV", "Visual Communication Design")

    # Teknik
    assert is_bilingual_major_match("Teknik Industri", "Industrial Engineering")
    assert is_bilingual_major_match("Teknik Mesin", "Mechanical Engineering")
    assert is_bilingual_major_match("Teknik Elektro", "Electrical Engineering")

    # Sosial & Hukum
    assert is_bilingual_major_match("Psikologi", "Psychology")
    assert is_bilingual_major_match("Hukum", "Law")
    assert is_bilingual_major_match("Hubungan Internasional", "International Relations")
    assert is_bilingual_major_match("Sastra Inggris", "English Literature")


# ==============================================================================
# 4. TEST INTEGRASI EVALUASI HARD REQUIREMENTS DENGAN CV INGGRIS
# ==============================================================================

def test_evaluate_hard_requirements_with_english_major():
    # Profil lowongan BUSDEV berbahasa Indonesia
    profile_busdev = {
        "hardRequirements": {
            "minGpa": 3.20,
            "allowedMajors": [
                "semua jurusan",
                "diutamakan Manajemen",
                "Bisnis",
                "Pemasaran",
                "Ekonomi",
                "Komunikasi"
            ],
            "mandatorySkills": {
                "items": ["riset pasar", "pitching"],
                "rule": "all"
            }
        }
    }

    # Kandidat A: Menulis "Marketing" di CV bahasa Inggris
    cand_a = {
        "fields": {
            "name": "David Wilson",
            "gpa": 3.75,
            "major": "marketing",
        },
        "fieldStatus": {"gpa": "ok", "major": "ok"},
        "sections": {
            "education": "Bachelor of Science in Marketing, Universitas Indonesia"
        }
    }

    status, reasons = evaluate_hard_requirements(
        candidate=cand_a,
        profile=profile_busdev,
        all_cv_text="Bachelor of Science in Marketing. Experienced in riset pasar and pitching."
    )

    assert status == "Memenuhi"
    # Pastikan diidentifikasi sebagai jurusan kriteria prioritas
    assert any("sesuai kriteria prioritas" in r for r in reasons)

    # Kandidat B: Menulis "Business Administration"
    cand_b = {
        "fields": {
            "name": "Sarah Connor",
            "gpa": 3.80,
            "major": "business administration",
        },
        "fieldStatus": {"gpa": "ok", "major": "ok"},
        "sections": {
            "education": "Prasetiya Mulya University, Bachelor of Business Administration"
        }
    }

    status_b, reasons_b = evaluate_hard_requirements(
        candidate=cand_b,
        profile=profile_busdev,
        all_cv_text="Bachelor of Business Administration. Good in riset pasar and pitching."
    )
    assert status_b == "Memenuhi"
    assert any("sesuai kriteria prioritas" in r for r in reasons_b)

    # Profil lowongan Tech: Khusus Ilmu Komputer & Sistem Informasi
    profile_tech = {
        "hardRequirements": {
            "minGpa": 3.00,
            "allowedMajors": [
                "Ilmu Komputer",
                "Teknik Informatika",
                "Sistem Informasi"
            ],
            "mandatorySkills": {
                "items": ["python"],
                "rule": "all"
            }
        }
    }

    # Kandidat Tech dengan "Computer Science"
    cand_tech = {
        "fields": {
            "name": "Alex Tan",
            "gpa": 3.65,
            "major": "computer science",
        },
        "fieldStatus": {"gpa": "ok", "major": "ok"},
        "sections": {
            "education": "ITB, B.Sc in Computer Science"
        }
    }

    status_tech, reasons_tech = evaluate_hard_requirements(
        candidate=cand_tech,
        profile=profile_tech,
        all_cv_text="B.Sc in Computer Science. Proficient in Python."
    )
    assert status_tech == "Memenuhi"
    assert any("sesuai kriteria" in r for r in reasons_tech)


# ==============================================================================
# 5. TEST PENCOCOKAN KOMPETENSI / SKILL DWIBAHASA (ID <-> EN)
# ==============================================================================

def test_bilingual_skills_matching():
    # Syarat Lowongan (ID) vs Teks CV (EN)
    assert safe_skill_match("riset pasar", "Conducted market research and industry analysis.")
    assert safe_skill_match("negosiasi", "Led client negotiation and contract closure.")
    assert safe_skill_match("kemitraan", "Secured 15+ strategic partnerships with national brands.")
    assert safe_skill_match("penjualan", "Responsible for b2b sales and outbound lead generation.")
    assert safe_skill_match("pembuatan konten", "Skilled in content creation and short-form video production.")
    assert safe_skill_match("manajemen media sosial", "Led social media management across Instagram and TikTok.")
    assert safe_skill_match("penyuntingan video", "Proficient in video editing with CapCut and Premiere Pro.")
    assert safe_skill_match("penulisan naskah", "Experienced copywriter with strong storytelling abilities.")
    assert safe_skill_match("analisis data", "Conducted comprehensive data analysis using SQL and Python.")
    assert safe_skill_match("kerja sama tim", "Proven track record of teamwork and cross-divisional leadership.")
    assert safe_skill_match("manajemen waktu", "Strong time management and problem solving competencies.")

    # Sebaliknya: Syarat Lowongan (EN) vs Teks CV (ID)
    assert safe_skill_match("market research", "Melakukan riset pasar dan pemetaan kompetitor.")
    assert safe_skill_match("negotiation", "Melakukan negosiasi kerjasama dengan mitra eksternal.")
    assert safe_skill_match("partnership", "Membangun kemitraan strategis dengan 10 sponsor.")
    assert safe_skill_match("content creation", "Fokus pada pembuatan konten edukasi di media sosial.")


# ==============================================================================
# 6. TEST SEGMENTASI SEKSI PADA CV BERBAHASA INGGRIS
# ==============================================================================

def test_bilingual_sections_segmentation():
    english_cv = """
    ALEXANDER WRIGHT
    alex.wright@example.com | +6281122334455 | Jakarta, Indonesia

    ACADEMICS
    Universitas Indonesia
    Bachelor of Business Administration, Major: Marketing
    Cumulative GPA: 3.82 out of 4.00 (Class of 2024)

    PROFESSIONAL EXPERIENCE
    Business Development Specialist | PT Tech Nusantara (Jan 2023 to Dec 2023)
    - Conducted comprehensive market research and identified 50+ B2B leads.
    - Led pitch deck presentations and contract negotiations, securing 12 new clients.
    
    Committee Member | National Youth Conference 2022
    - Event organizer and liaison officer coordinating 500+ participants.

    SELECTED PROJECTS
    Market Expansion Capstone Project (2023)
    - Formulated market analysis and pitch deck resulting in top 3 finish.

    LICENSES & CERTIFICATIONS
    Google Digital Marketing & E-Commerce Professional Certificate (2023)

    CORE COMPETENCIES
    Market Research, B2B Sales, Pitch Deck Preparation, Negotiation, Teamwork, Canva
    """

    sections, flags = segment_cv_sections(english_cv)
    assert "Marketing" in sections["education"] or "Universitas Indonesia" in sections["education"]
    assert "Business Development Specialist" in sections["experience"]
    assert "Market Expansion Capstone" in sections["projects"]
    assert "Google Digital Marketing" in sections["certifications"]
    assert "Market Research" in sections["skills"]


# ==============================================================================
# 7. TEST EKSTRAKSI GPA, DURATION & EXP TYPE DARI CV INGGRIS
# ==============================================================================

def test_bilingual_gpa_dates_and_experience():
    # IPK dalam berbagai format bahasa Inggris
    assert extract_gpa("Cumulative GPA: 3.82 out of 4.00")[0] == 3.82
    assert extract_gpa("Overall GPA: 3.75/4.00")[0] == 3.75
    assert extract_gpa("CGPA 3.90 out of 4.0")[0] == 3.90
    assert extract_gpa("Grade Point Average: 3.65")[0] == 3.65

    # Durasi dengan format kata 'to' / 'until' / 'Present'
    assert estimate_duration_months("Jan 2022 to Dec 2022") == 12
    assert estimate_duration_months("August 2023 to Present") >= 1
    assert estimate_duration_months("01/2023 - 06/2023") == 6
    assert estimate_duration_months("Duration: 6 months") == 6

    # Klasifikasi tipe pengalaman
    assert classify_experience_type("Liaison Officer at International Youth Summit") == "kepanitiaan/volunteer"
    assert classify_experience_type("Vice President of Student Council") == "organisasi"
    assert classify_experience_type("Marketing Intern at StartUp Inc.") == "kerja/magang"


# ==============================================================================
# 8. TEST PENGSEKORAN KATEGORI RESILIEN UNTUK CV INGGRIS
# ==============================================================================

def test_bilingual_category_scoring_resilience():
    # JD BUSDEV dalam Bahasa Indonesia
    profile = {
        "division": "BUSDEV",
        "title": "Business Development",
        "jd": "Melakukan riset pasar dan mengelola database leads, menyusun proposal pitch deck, pitching dan negosiasi kerja sama.",
        "thresholds": {"durationMonths": 0, "projectsCount": 0},
        "hardRequirements": {
            "minGpa": 3.20,
            "allowedMajors": ["semua jurusan", "diutamakan Manajemen", "Bisnis", "Pemasaran", "Ekonomi"],
            "mandatorySkills": {
                "items": ["riset pasar", "pitching"],
                "rule": "all"
            }
        },
        "additionalSkills": ["sales", "marketing", "negosiasi"],
        "categories": {
            "experience": {"active": True, "weight": 0.35},
            "projects": {"active": True, "weight": 0.25},
            "cert_edu": {"active": True, "weight": 0.15},
            "competencies": {"active": True, "weight": 0.25}
        }
    }

    # Kandidat dengan CV 100% Bahasa Inggris
    english_candidate = {
        "fields": {
            "name": "Alexander Wright",
            "gpa": 3.82,
            "major": "marketing",
            "experiences": [{"durationMonths": 12}],
            "projects": [{"title": "Market deck B2B"}],
        },
        "fieldStatus": {"gpa": "ok", "major": "ok"},
        "sections": {
            "experience": "Business Development Intern. Conducted market research, pitched deck presentations, and closed sales deals with 15 corporate partners.",
            "projects": "B2B pitch deck project and market analysis for retail clients.",
            "education": "Universitas Indonesia, Bachelor of Science in Marketing, GPA 3.82",
            "skills": "Market research, pitching, negotiation, sales, marketing, partnership",
            "certifications": "Certified Business Development Professional"
        }
    }

    vec = TfidfVectorizer(stop_words="english")
    vec.fit([profile["jd"], english_candidate["sections"]["experience"], english_candidate["sections"]["projects"]])

    cat_scores, final_score, reasons = calculate_category_scores(
        candidate=english_candidate,
        profile=profile,
        vec=vec,
        jd_text=profile["jd"],
        all_cv_text="Bachelor of Science in Marketing. Conducted market research, pitching, negotiation, sales, marketing."
    )

    # Validasi bahwa kompetensi bahasa Inggris cocok dengan JD bahasa Indonesia
    assert cat_scores["competencies"] == 100.0
    assert cat_scores["cert_edu"] >= 80.0
    assert final_score >= 70.0

