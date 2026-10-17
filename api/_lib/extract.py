"""
Modul ekstraksi field terstruktur dari teks CV.
Mengekstrak kontak (email, HP), pendidikan (kampus, jurusan, IPK, tahun lulus/semester),
tautan portofolio, entri pengalaman bertag (kerja/magang, organisasi, volunteer), project, dan sertifikasi.
"""

import re
from typing import Dict, Any, List, Optional, Tuple

# Regex Email
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Regex Nomor HP Indonesia (08..., +628..., 628...)
PHONE_REGEX = re.compile(
    r"(?:\+?62|08)[0-9\s\-\.]{8,15}"
)

# Domain tautan portofolio
PORTFOLIO_DOMAINS = [
    "linkedin.com", "github.com", "gitlab.com", "behance.net", "dribbble.com",
    "instagram.com", "tiktok.com", "canva.com", "drive.google.com", "medium.com",
    "notion.site", "notion.so"
]

# Kata kunci kampus
CAMPUS_KEYWORDS = [
    "universitas", "university", "institut", "institute", "politeknik", "polytechnic",
    "sekolah tinggi", "akademi", "stmik", "ui", "itb", "ugm", "its", "undip", "unpad",
    "unair", "binus", "telkom", "ub", "unbraw"
]

# Kata kunci derajat / prefix jurusan untuk normalisasi
MAJOR_PREFIXES = [
    r"\bs1\b", r"\bd4\b", r"\bd3\b", r"\bstrata 1\b", r"\bdiploma 4\b", r"\bdiploma 3\b",
    r"\bjurusan\b", r"\bprogram studi\b", r"\bprodi\b", r"\bdepartemen\b", r"\bfakultas\b",
    r"\bmajor\b", r"\bbachelor of\b", r"\bbachelor in\b"
]


def extract_email(text: str) -> Tuple[Optional[str], str]:
    """Mengembalikan (email, status: ok | ambigu | tidak_ditemukan)."""
    matches = EMAIL_REGEX.findall(text)
    if not matches:
        return None, "tidak_ditemukan"
    unique = list(dict.fromkeys(matches))
    if len(unique) == 1:
        return unique[0].lower(), "ok"
    # Jika ada lebih dari satu email
    return unique[0].lower(), "ambigu"


def clean_phone_number(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+62"):
        return digits
    elif digits.startswith("62"):
        return "+" + digits
    elif digits.startswith("08"):
        return "+62" + digits[1:]
    return digits


def extract_phone(text: str) -> Tuple[Optional[str], str]:
    """Mengembalikan (phone, status: ok | ambigu | tidak_ditemukan)."""
    matches = PHONE_REGEX.findall(text)
    valid_phones = []
    for m in matches:
        cleaned = clean_phone_number(m)
        if len(re.sub(r"\D", "", cleaned)) >= 10:
            if cleaned not in valid_phones:
                valid_phones.append(cleaned)

    if not valid_phones:
        return None, "tidak_ditemukan"
    if len(valid_phones) == 1:
        return valid_phones[0], "ok"
    return valid_phones[0], "ambigu"


def extract_gpa(text: str) -> Tuple[Optional[float], str]:
    """
    Mengekstrak nilai IPK / GPA dengan toleransi koma/titik dan skala /4.00.
    Mengembalikan (gpa_value, status: ok | ambigu | tidak_ditemukan).
    """
    # Pola IPK: IPK 3.75, GPA 3,8, IPK: 3.75/4.00, Indeks Prestasi Kumulatif 3.90, IPK Semester 1: 3.20
    explicit_pattern = re.compile(
        r"\b(?:ipk|gpa|grade point(?: average)?|indeks prestasi(?: kumulatif)?|ip)\b(?:.{0,25}?)([0-4][\.,][0-9]{1,2})(?:\s*\/\s*([0-9][\.,]?[0-9]*))?",
        re.IGNORECASE
    )

    matches = explicit_pattern.findall(text)
    plausible_gpas = []

    for match in matches:
        val_str = match[0].replace(",", ".")
        scale_str = match[1].replace(",", ".") if match[1] else ""
        try:
            val = float(val_str)
            # Cek jika skala bukan 4.00
            if scale_str and float(scale_str) not in (4.0, 4):
                return None, "ambigu"

            if 0.0 <= val <= 4.0:
                plausible_gpas.append(val)
        except ValueError:
            continue

    if not plausible_gpas:
        # Pola rasio skala 4: misal "3.86/4.00", "3.86 / 4.0", "3.86/4" tanpa label IPK eksplisit
        scale_pattern = re.compile(
            r"\b([0-4][\.,][0-9]{1,2})\s*\/\s*4(?:\.00?)?\b"
        )
        for sm in scale_pattern.finditer(text):
            try:
                val = float(sm.group(1).replace(",", "."))
                if 0.0 <= val <= 4.0:
                    plausible_gpas.append(val)
            except ValueError:
                continue

    if not plausible_gpas:
        return None, "tidak_ditemukan"

    unique_gpas = list(set(plausible_gpas))
    if len(unique_gpas) == 1:
        return unique_gpas[0], "ok"

    return unique_gpas[0], "ambigu"


def normalize_major(major_raw: str) -> str:
    """
    Normalisasi nama jurusan: huruf kecil, buang prefiks S1/Prodi/Jurusan, buang tanda baca.
    """
    if not major_raw:
        return ""
    text = major_raw.lower()
    for prefix in MAJOR_PREFIXES:
        text = re.sub(prefix, " ", text, flags=re.IGNORECASE)
    # Hapus tanda baca dan spasi berlebih
    text = re.sub(r"[\(\)\[\],.:;/\-]", " ", text)
    tokens = text.split()
    return " ".join(tokens).strip()


def extract_education_details(edu_text: str, full_text: str) -> Dict[str, Any]:
    """
    Mengekstrak kampus, jurusan, tahun lulus / semester dari seksi pendidikan.
    """
    search_text = edu_text if edu_text.strip() else full_text
    lines = [line.strip() for line in search_text.splitlines() if line.strip()]

    campus = None
    campus_status = "tidak_ditemukan"
    major = None
    major_status = "tidak_ditemukan"
    grad_year_or_semester = None

    # Deteksi tahun lulus / semester
    year_match = re.search(r"\b(20[12][0-9])\b", search_text)
    sem_match = re.search(r"\b(?:semester|sem\.?)\s*([1-8])\b", search_text, re.IGNORECASE)

    if sem_match:
        grad_year_or_semester = f"Semester {sem_match.group(1)}"
    elif year_match:
        grad_year_or_semester = f"Lulus {year_match.group(1)}"

    for line in lines:
        line_lower = line.lower()

        # Lewati baris yang merupakan daftar skill / keahlian jika ada yang lolos ke seksi pendidikan
        if re.match(r"^(?:soft\s+skills?|hard\s+skills?|skills?|kemampuan|keahlian)\b", line_lower):
            continue

        # Deteksi kampus
        if not campus:
            for kw in CAMPUS_KEYWORDS:
                if kw in line_lower:
                    campus = line
                    campus_status = "ok"
                    break

        # Deteksi jurusan
        if not major:
            # 1. Coba pola gelar / awalan jurusan eksplisit (e.g. "Bachelor of Data Science, 3.86/4.00" -> "Data Science")
            degree_match = re.search(
                r"\b(?:bachelor\s+(?:of|in)|sarjana|s1|d4|d3|jurusan|prodi|program\s+studi|major\s+in)\s+([a-zA-Z\s]{3,35})",
                line,
                re.IGNORECASE
            )
            if degree_match:
                extracted_raw = degree_match.group(1).split(",")[0].strip()
                norm = normalize_major(extracted_raw)
                if norm and len(norm) >= 3:
                    major = norm
                    major_status = "ok"

            # 2. Fallback jika ada kata kunci rumpun ilmu/jurusan
            if not major:
                major_keywords = [
                    "sains data", "data science", "statistika", "matematika", "ilmu komputer",
                    "teknik", "sistem", "manajemen", "komunikasi", "akuntansi", "psikologi",
                    "desain", "hukum", "sastra", "informatika", "bisnis", "administrasi"
                ]
                if any(p in line_lower for p in major_keywords):
                    first_part = line.split(",")[0].strip()
                    norm = normalize_major(first_part)
                    if norm:
                        major = norm
                        major_status = "ok"

    return {
        "university": campus,
        "university_status": campus_status,
        "major": major,
        "major_status": major_status,
        "grad_year_or_semester": grad_year_or_semester,
    }


def filter_portfolio_links(links: List[str]) -> List[str]:
    """
    Menyaring tautan yang relevan sebagai portofolio/profil profesional.
    """
    portfolio_links = []
    for link in links:
        link_lower = link.lower()
        if any(domain in link_lower for domain in PORTFOLIO_DOMAINS):
            if link not in portfolio_links:
                portfolio_links.append(link)
    return portfolio_links


def classify_experience_type(title_and_desc: str) -> str:
    """
    Mengklasifikasikan pengalaman: 'kerja/magang', 'organisasi', atau 'kepanitiaan/volunteer'.
    """
    lower = title_and_desc.lower()
    if any(k in lower for k in ["kepanitiaan", "panitia", "volunteer", "relawan", "event", "acara"]):
        return "kepanitiaan/volunteer"
    elif any(k in lower for k in ["organisasi", "himpunan", "bem", "senat", "club", "komunitas", "divisi", "departemen"]):
        return "organisasi"
    else:
        return "kerja/magang"


MONTH_NAMES = {
    "jan": 1, "januari": 1, "january": 1,
    "feb": 2, "februari": 2, "february": 2,
    "mar": 3, "maret": 3, "march": 3,
    "apr": 4, "april": 4,
    "mei": 5, "may": 5,
    "jun": 6, "juni": 6, "june": 6,
    "jul": 7, "juli": 7, "july": 7,
    "agu": 8, "agustus": 8, "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "okt": 10, "oktober": 10, "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "des": 12, "desember": 12, "dec": 12, "december": 12,
}


def estimate_duration_months(text: str) -> int:
    """
    Memperkirakan durasi pengalaman dalam satuan bulan dari teks tanggal.
    Contoh: '3 bulan', '6 months', 'Jan 2022 - Des 2022' (12 bulan).
    """
    # 1. Pola eksplisit 'X bulan'
    bulan_match = re.search(r"(\d+)\s*(?:bulan|months?|bln)", text, re.IGNORECASE)
    if bulan_match:
        try:
            return min(int(bulan_match.group(1)), 48)
        except ValueError:
            pass

    # 2. Pola bulan + tahun: 'Jan 2022 - Des 2022' atau 'Januari 2023 - Present'
    month_range_pattern = re.compile(
        r"\b([A-Za-z]+)\s+(20[12][0-9])\s*[-–]\s*([A-Za-z]+)?\s*(20[12][0-9]|sekarang|present)?\b",
        re.IGNORECASE
    )
    m_match = month_range_pattern.search(text)
    if m_match:
        m1_str = (m_match.group(1) or "").lower()
        y1_str = m_match.group(2)
        m2_str = (m_match.group(3) or "").lower()
        y2_str = (m_match.group(4) or "").lower()

        m1 = MONTH_NAMES.get(m1_str, 1)
        y1 = int(y1_str) if y1_str else 2023

        if y2_str in ("sekarang", "present") or not y2_str:
            y2 = 2024
            m2 = MONTH_NAMES.get(m2_str, 12)
        else:
            try:
                y2 = int(y2_str)
            except ValueError:
                y2 = y1
            m2 = MONTH_NAMES.get(m2_str, 12)

        total_months = (y2 - y1) * 12 + (m2 - m1 + 1)
        if 1 <= total_months <= 60:
            return total_months

    # 3. Pola tahun '2022 - 2023' (12 bulan)
    year_range_match = re.search(r"\b(20[12][0-9])\s*[-–]\s*(20[12][0-9]|sekarang|present)\b", text, re.IGNORECASE)
    if year_range_match:
        try:
            y1 = int(year_range_match.group(1))
            y2_str = year_range_match.group(2).lower()
            y2 = 2024 if y2_str in ("sekarang", "present") else int(y2_str)
            diff_years = max(1, y2 - y1)
            return min(diff_years * 12, 48)
        except ValueError:
            pass

    # Default konservatif pengalaman level mahasiswa/intern
    return 3



def extract_experiences(exp_text: str) -> List[Dict[str, Any]]:
    """
    Mengekstrak daftar entri pengalaman beserta tipe dan durasi.
    """
    if not exp_text or not exp_text.strip():
        return []

    entries = []
    lines = [l.strip() for l in exp_text.splitlines() if l.strip()]

    # Pisahkan blok berdasarkan bullet points atau baris tanggal
    current_block = []
    for line in lines:
        if line.startswith(("-", "•", "*", "–")) or re.search(r"\b20[12][0-9]\b", line):
            if current_block:
                block_str = " | ".join(current_block)
                exp_type = classify_experience_type(block_str)
                dur = estimate_duration_months(block_str)
                entries.append({
                    "title": current_block[0][:100],
                    "details": block_str[:250],
                    "durationMonths": dur,
                    "type": exp_type
                })
                current_block = []
        current_block.append(line)

    if current_block:
        block_str = " | ".join(current_block)
        entries.append({
            "title": current_block[0][:100],
            "details": block_str[:250],
            "durationMonths": estimate_duration_months(block_str),
            "type": classify_experience_type(block_str)
        })

    return entries


def extract_cv_fields(
    full_text: str,
    sections: Dict[str, str],
    all_links: List[str],
    candidate_name_from_csv: Optional[str] = None
) -> Tuple[Dict[str, Any], Dict[str, str], List[str]]:
    """
    Mengekstrak seluruh field kandidat dari teks CV dan seksi-seksi.
    Mengembalikan (fields_dict, field_status_dict, flags).
    """
    flags = []
    field_status = {}

    # 1. Nama Kandidat
    name = candidate_name_from_csv
    if not name:
        # Fallback ke baris teratas CV
        lines = [l.strip() for l in full_text.splitlines() if l.strip()]
        name = lines[0][:80] if lines else "Tanpa Nama"
    field_status["name"] = "ok" if name else "tidak_ditemukan"

    # 2. Email & Kontak HP
    email, email_status = extract_email(full_text)
    field_status["email"] = email_status

    phone, phone_status = extract_phone(full_text)
    field_status["phone"] = phone_status

    # 3. IPK
    gpa, gpa_status = extract_gpa(full_text)
    field_status["gpa"] = gpa_status
    if gpa_status == "ambigu":
        flags.append("ipk_ambigu")

    # 4. Pendidikan (Kampus, Jurusan, Tahun Lulus/Semester)
    edu_info = extract_education_details(sections.get("education", ""), full_text)
    field_status["university"] = edu_info["university_status"]
    field_status["major"] = edu_info["major_status"]

    # 5. Tautan Portofolio
    portfolio_links = filter_portfolio_links(all_links)

    # 6. Pengalaman
    experiences = extract_experiences(sections.get("experience", ""))

    # 7. Project
    project_text = sections.get("projects", "")
    # 7. Project
    project_text = sections.get("projects", "")
    projects = []
    if project_text.strip():
        p_lines = [l.strip() for l in project_text.splitlines() if l.strip()]
        for pl in p_lines[:15]:
            clean_pl = re.sub(r"^[•\-\*\d\.\)\s\uE000-\uF8FF]+", "", pl).strip()
            if pl.startswith(("-", "•", "*", "1", "2", "3", "4", "5")) or re.match(r"^(?:project|proyek)\b", clean_pl, re.IGNORECASE):
                projects.append({"title": (clean_pl if clean_pl else pl)[:100]})
        if not projects and p_lines:
            clean_first = re.sub(r"^[•\-\*\d\.\)\s\uE000-\uF8FF]+", "", p_lines[0]).strip()
            projects.append({"title": (clean_first if clean_first else p_lines[0])[:100]})

    # 8. Sertifikasi
    cert_text = sections.get("certifications", "")
    certs = []
    if cert_text.strip():
        for cl in cert_text.splitlines()[:15]:
            cl = cl.strip()
            clean_cl = re.sub(r"^[•\-\*\d\.\)\s\uE000-\uF8FF]+", "", cl).strip()
            if clean_cl and len(clean_cl) > 3:
                certs.append(clean_cl[:100])

    fields = {
        "name": name,
        "email": email,
        "phone": phone,
        "university": edu_info["university"],
        "major": edu_info["major"],
        "gpa": gpa,
        "graduationYearOrSemester": edu_info["grad_year_or_semester"],
        "portfolioLinks": portfolio_links,
        "skillsFound": [],
        "experiences": experiences,
        "projects": projects,
        "certifications": certs,
    }

    return fields, field_status, flags
