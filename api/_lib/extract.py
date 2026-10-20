"""
Modul ekstraksi field terstruktur dari teks CV.
Mengekstrak kontak (email, HP), pendidikan (kampus, jurusan, IPK, tahun lulus/semester),
tautan portofolio, entri pengalaman bertag (kerja/magang, organisasi, volunteer), project, dan sertifikasi.
"""

import re
import datetime
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

# Kata kunci kampus (ID & EN)
CAMPUS_KEYWORDS = [
    "universitas", "university", "institut", "institute", "politeknik", "polytechnic",
    "sekolah tinggi", "akademi", "stmik", "college", "school of", "faculty of", "campus",
    "academy", "ui", "itb", "ugm", "its", "undip", "unpad",
    "unair", "binus", "telkom", "ub", "unbraw"
]

# Kata kunci derajat / prefix jurusan untuk normalisasi (ID & EN)
MAJOR_PREFIXES = [
    # Gelar & Kualifikasi Berbahasa Inggris (Urutan dari terpanjang untuk akurasi match)
    r"\bbachelor\s+of\s+science\s+(?:in|of)\b",
    r"\bbachelor\s+of\s+arts\s+(?:in|of)\b",
    r"\bbachelor\s+of\s+business\s+administration\s+(?:in|of)?\b",
    r"\bbachelor\s+of\s+engineering\s+(?:in|of)\b",
    r"\bbachelor\s+of\s+economics\s+(?:in|of)\b",
    r"\bbachelor\s+of\s+communication\s+(?:in|of)\b",
    r"\bbachelor\s+of\s+computer\s+science\s+(?:in|of)\b",
    r"\bbachelor\s+of\s+applied\s+science\s+(?:in|of)\b",
    r"\bbachelor\s+(?:degree\s+in|degree\s+of|of|in)\b",
    r"\bbachelor's\s+(?:degree\s+in|degree\s+of|in|of)\b",
    r"\bbachelor\b",
    r"\bb\.?s\.?c?\.?\s+(?:in|of)\b",
    r"\bb\.?a\.?\s+(?:in|of)\b",
    r"\bbba\s+(?:in|of)?\b",
    r"\bb\.?eng\.?\s+(?:in|of)\b",
    r"\bb\.?com\.?\s+(?:in|of)\b",
    r"\bb\.?ed\.?\s+(?:in|of)\b",
    r"\bmaster\s+of\s+science\s+(?:in|of)\b",
    r"\bmaster\s+of\s+business\s+administration\s+(?:in|of)?\b",
    r"\bmaster\s+(?:of|in|degree\s+in)\b",
    r"\bmba\b",
    r"\bm\.?s\.?c?\.?\s+(?:in|of)\b",
    r"\bm\.?a\.?\s+(?:in|of)\b",
    r"\bassociate\s+degree\s+(?:in|of)\b",
    r"\bdiploma\s+(?:in|of|4|3|four|three)?\b",
    r"\bundergraduate\s+(?:student\s+in|student\s+of|degree\s+in|in|of)?\b",
    r"\bcandidate\s+(?:in|for)\b",
    r"\bfield\s+of\s+study\s*:?\b",
    r"\barea\s+of\s+study\s*:?\b",
    r"\bconcentration\s*(?:in|:)?\b",
    r"\bspecialization\s*(?:in|:)?\b",
    r"\bdegree\s*(?:in|:)?\b",
    r"\bmajor\s*(?:in|:)?\b",
    r"\bscience\s+in\b",
    r"\barts\s+in\b",

    # Gelar & Istilah Berbahasa Indonesia
    r"\bsarjana\s+ilmu\b",
    r"\bsarjana\b",
    r"\bs1\b", r"\bd4\b", r"\bd3\b", r"\bd2\b", r"\bd1\b",
    r"\bstrata\s+1\b", r"\bdiploma\s+4\b", r"\bdiploma\s+3\b",
    r"\bjurusan\s*:?\b", r"\bprogram\s+studi\s*:?\b", r"\bprodi\s*:?\b",
    r"\bdepartemen\s*:?\b", r"\bfakultas\s*:?\b", r"\bbidang\s+studi\s*:?\b"
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
    Mengekstrak nilai IPK / GPA dengan toleransi koma/titik dan skala /4.00 (ID & EN).
    Mendukung format 'IPK 3.75', 'GPA 3.8', 'CGPA 3.85', '3.85 out of 4.00', 'Cumulative GPA 3.9'.
    Mengembalikan (gpa_value, status: ok | ambigu | tidak_ditemukan).
    """
    # Pola IPK: IPK 3.75, GPA 3,8, CGPA 3.85, Cumulative GPA 3.90, Grade Point Average: 3.8 / 4.0, 3.85 out of 4.0
    explicit_pattern = re.compile(
        r"\b(?:ipk|gpa|cgpa|cumulative\s+gpa|overall\s+gpa|grade\s+point(?:\s+average)?|indeks\s+prestasi(?:\s+kumulatif)?|ip)\b(?:.{0,25}?)([0-4][\.,][0-9]{1,2})(?:\s*(?:\/|out\s+of)\s*([0-9][\.,]?[0-9]*))?",
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
        # Pola rasio skala 4: misal "3.86/4.00", "3.86 / 4.0", "3.86 out of 4.00" tanpa label IPK eksplisit
        scale_pattern = re.compile(
            r"\b([0-4][\.,][0-9]{1,2})\s*(?:\/|out\s+of)\s*4(?:\.00?)?\b",
            re.IGNORECASE
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


# Kata kunci rumpun ilmu / jurusan dwibahasa (ID & EN)
BILINGUAL_MAJOR_KEYWORDS = [
    # Business & Management
    "business administration", "administrasi bisnis", "business management", "manajemen bisnis",
    "international business", "bisnis internasional", "business", "bisnis", "management", "manajemen",
    "marketing management", "digital marketing", "marketing", "pemasaran",
    "financial management", "finance", "keuangan", "banking", "perbankan",
    "accounting", "akuntansi", "audit", "taxation", "perpajakan",
    "development economics", "economics", "ekonomi pembangunan", "ekonomi",
    "entrepreneurship", "kewirausahaan", "administration", "administrasi",
    "public administration", "administrasi publik", "administrasi negara",
    # Communication & Media
    "communication studies", "communication science", "mass communication", "communications", "communication",
    "ilmu komunikasi", "komunikasi", "public relations", "hubungan masyarakat", "humas",
    "journalism", "jurnalistik", "media studies", "broadcasting", "penyiaran",
    # Tech & Computer
    "computer science", "ilmu komputer", "software engineering", "rekayasa perangkat lunak",
    "information systems", "sistem informasi", "information technology", "teknologi informasi",
    "informatics", "teknik informatika", "informatika", "data science", "sains data", "data analytics",
    "statistics", "statistika", "mathematics", "matematika", "actuarial science", "aktuaria",
    # Engineering
    "industrial engineering", "teknik industri", "electrical engineering", "teknik elektro",
    "mechanical engineering", "teknik mesin", "civil engineering", "teknik sipil",
    "chemical engineering", "teknik kimia", "engineering", "teknik",
    # Design & Arts
    "visual communication design", "desain komunikasi visual", "graphic design", "desain grafis",
    "interior design", "desain interior", "product design", "desain produk",
    "multimedia", "fine arts", "seni rupa", "design", "desain", "dkv",
    # Social, Law & Humanities
    "human resource management", "human resources", "sumber daya manusia", "manajemen sdm", "sdm",
    "psychology", "psikologi", "international relations", "hubungan internasional",
    "law", "legal studies", "ilmu hukum", "hukum",
    "english literature", "sastra inggris", "english language", "bahasa inggris", "english",
    "literature", "sastra", "linguistics", "linguistik", "sociology", "sosiologi",
    # Tourism & Hospitality
    "hospitality management", "hotel management", "hospitality", "perhotelan",
    "tourism", "pariwisata", "event management",
    # Health & Science
    "public health", "kesehatan masyarakat", "pharmacy", "farmasi", "nursing", "keperawatan", "medicine", "kedokteran",
    "education studies", "ilmu pendidikan", "keguruan", "teaching"
]


def normalize_major(major_raw: str) -> str:
    """
    Normalisasi nama jurusan dwibahasa (ID & EN): huruf kecil, buang prefiks gelar/jurusan/bachelor,
    buang informasi IPK/tahun, buang tanda kurung gelar, dan bersihkan spasi.
    """
    if not major_raw:
        return ""
    text = major_raw.strip()

    # Buang trailing koma atau delimiter dengan label GPA, IPK, tahun, skala /4.00
    text = re.sub(r"[,\|;].*?(?:gpa|ipk|20[12][0-9]|cum laude|\b4\.00?\b).*$", "", text, flags=re.I)
    text = re.sub(r"\b(?:gpa|ipk)\b.*$", "", text, flags=re.I)

    # Buang singkatan gelar dalam kurung seperti (BBA), (B.Sc), (B.Eng), (S.Kom), (Hons)
    text = re.sub(r"\([A-Za-z\s\.,]{1,25}\)", " ", text)

    for prefix in MAJOR_PREFIXES:
        text = re.sub(prefix, " ", text, flags=re.IGNORECASE)

    # Hapus tanda baca dan spasi berlebih
    text = re.sub(r"[\(\)\[\],.:;/\-–—_#\*]", " ", text)
    tokens = text.split()
    return " ".join(tokens).strip().lower()


def extract_education_details(edu_text: str, full_text: str) -> Dict[str, Any]:
    """
    Mengekstrak kampus, jurusan, tahun lulus / semester dari seksi pendidikan (ID & EN).
    """
    search_text = edu_text if edu_text.strip() else full_text
    lines = [line.strip() for line in search_text.splitlines() if line.strip()]

    campus = None
    campus_status = "tidak_ditemukan"
    major = None
    major_status = "tidak_ditemukan"
    grad_year_or_semester = None

    # Deteksi tahun lulus / semester (ID & EN)
    sem_match = re.search(r"\b(?:semester|sem\.?)\s*([1-8])\b", search_text, re.IGNORECASE)
    if not sem_match:
        sem_match = re.search(r"\b([1-8])(?:th|st|nd|rd)?\s*(?:semester|sem\.?)\b", search_text, re.IGNORECASE)

    # Deteksi tahun kelulusan dengan label eksplisit (Class of 2024, Expected Graduation: 2025, Graduated 2023)
    exp_grad_match = re.search(r"\b(?:class\s+of|expected\s+graduation|graduation|graduated|lulus(?:an)?)\s*[:\-]?\s*(20[12][0-9])\b", search_text, re.I)
    year_match = exp_grad_match or re.search(r"\b(20[12][0-9])\b", search_text)

    if sem_match:
        grad_year_or_semester = f"Semester {sem_match.group(1)}"
    elif year_match:
        grad_year_or_semester = f"Lulus {year_match.group(1)}"

    # Kata-kata generik derajat yang tidak boleh dianggap sebagai jurusan akhir
    GENERIC_DEGREE_WORDS = {"science", "arts", "applied science", "degree", "bachelor", "master", "sarjana", "undergraduate", "study"}

    for line in lines:
        line_lower = line.lower()

        # Lewati baris yang merupakan judul/header seksi atau daftar skill
        clean_header = re.sub(r"^[#\*\s\-_:]+", "", line_lower).strip().rstrip(":")
        if clean_header in (
            "education", "pendidikan", "academic background", "educational background",
            "riwayat pendidikan", "academics", "qualifications", "study", "studies"
        ):
            continue

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
            # 1. Coba pola eksplisit berlabel (e.g. "Major: Marketing", "Field of Study: Business Administration")
            label_match = re.search(
                r"\b(?:major|field\s+of\s+study|area\s+of\s+study|specialization|concentration|program\s+studi|prodi|jurusan|bidang\s+studi)\s*[:\-]\s*([A-Za-z\s/&]{2,45})",
                line,
                re.IGNORECASE
            )
            if label_match:
                extracted_raw = label_match.group(1).split(",")[0].strip()
                norm = normalize_major(extracted_raw)
                if norm and len(norm) >= 3 and norm not in GENERIC_DEGREE_WORDS:
                    major = norm
                    major_status = "ok"

            # 2. Coba pola gelar lengkap dengan spesialisasi (e.g. "Bachelor of Science in Computer Science")
            if not major:
                degree_in_match = re.search(
                    r"\b(?:bachelor|master|magister|sarjana)\s+(?:of\s+[A-Za-z\s]+?\s+in|in)\s+([a-zA-Z\s/&]{3,40})",
                    line,
                    re.IGNORECASE
                )
                if degree_in_match:
                    extracted_raw = degree_in_match.group(1).split(",")[0].strip()
                    norm = normalize_major(extracted_raw)
                    if norm and len(norm) >= 3 and norm not in GENERIC_DEGREE_WORDS:
                        major = norm
                        major_status = "ok"

            # 3. Coba pola umum gelar / jenjang (e.g. "Bachelor of Business Administration", "B.S. in Marketing", "S1 Akuntansi")
            if not major:
                degree_match = re.search(
                    r"\b(?:bachelor\s+(?:of|in)?|b\.?s\.?c?\.?|b\.?a\.?|bba|b\.?eng\.?|b\.?com\.?|mba|sarjana|s1|d4|d3|jurusan|prodi|program\s+studi|major\s+in)\s*[:\-]?\s+([a-zA-Z\s/&]{3,40})",
                    line,
                    re.IGNORECASE
                )
                if degree_match:
                    extracted_raw = degree_match.group(1).split(",")[0].strip()
                    norm = normalize_major(extracted_raw)
                    if norm and len(norm) >= 3 and norm not in GENERIC_DEGREE_WORDS:
                        major = norm
                        major_status = "ok"

            # 4. Fallback jika ada kata kunci rumpun ilmu/jurusan dwibahasa (ID & EN)
            if not major:
                for kw in BILINGUAL_MAJOR_KEYWORDS:
                    kw_esc = re.escape(kw)
                    if re.search(rf"\b{kw_esc}\b", line_lower):
                        first_part = line.split(",")[0].strip()
                        norm = normalize_major(first_part)
                        if norm and len(norm) >= 3 and norm not in GENERIC_DEGREE_WORDS:
                            major = norm
                            major_status = "ok"
                        else:
                            if kw not in GENERIC_DEGREE_WORDS:
                                major = kw
                                major_status = "ok"
                        break

    # 5. Global Fallback: jika seksi pendidikan tidak mendeteksi jurusan, cari di seluruh dokumen CV
    if not major and full_text.strip():
        # Pola eksplisit berlabel di seluruh dokumen
        global_label_match = re.search(
            r"\b(?:major|field\s+of\s+study|program\s+studi|prodi|jurusan)\s*[:\-]\s*([A-Za-z\s/&]{2,40})",
            full_text,
            re.IGNORECASE
        )
        if global_label_match:
            cand_norm = normalize_major(global_label_match.group(1).split(",")[0].strip())
            if cand_norm and len(cand_norm) >= 3:
                major = cand_norm
                major_status = "ok"
        else:
            # Pola gelar "Bachelor of ... in XYZ" di seluruh teks
            global_deg_match = re.search(
                r"\b(?:bachelor|master|sarjana)\s+(?:of\s+[A-Za-z\s]+?\s+in|in)\s+([a-zA-Z\s/&]{3,40})",
                full_text,
                re.IGNORECASE
            )
            if global_deg_match:
                cand_norm = normalize_major(global_deg_match.group(1).split(",")[0].strip())
                if cand_norm and len(cand_norm) >= 3:
                    major = cand_norm
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
    Mengklasifikasikan pengalaman dwibahasa (ID & EN):
    - 'kepanitiaan/volunteer'
    - 'organisasi'
    - 'kerja/magang'
    """
    lower = title_and_desc.lower()
    volunteer_keywords = [
        "kepanitiaan", "panitia", "volunteer", "volunteering", "relawan", "event",
        "acara", "liaison officer", "organizing committee", "committee member",
        "committee", "volunteer experience"
    ]
    org_keywords = [
        "organisasi", "himpunan", "bem", "senat", "club", "komunitas", "divisi",
        "departemen", "organization", "student council", "student association",
        "student union", "society", "board member", "executive board", "association",
        "extracurricular"
    ]
    if any(k in lower for k in volunteer_keywords):
        return "kepanitiaan/volunteer"
    elif any(k in lower for k in org_keywords):
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
    Memperkirakan durasi pengalaman dalam satuan bulan dari teks tanggal (ID & EN).
    Contoh: '3 bulan', '6 months', 'Jan 2022 - Dec 2022', '01/2022 - 12/2022', 'Aug 2021 to Present'.
    """
    now_dt = datetime.datetime.now()
    curr_year = now_dt.year
    curr_month = now_dt.month
    present_keywords = ("sekarang", "present", "now", "saat ini", "current", "ongoing")

    # 1. Pola eksplisit 'X bulan' / 'X months'
    bulan_match = re.search(r"(\d+)\s*(?:bulan|months?|bln|mos?)\b", text, re.IGNORECASE)
    if bulan_match:
        try:
            return min(int(bulan_match.group(1)), 48)
        except ValueError:
            pass

    # 2. Pola numerik MM/YYYY - MM/YYYY atau MM/YYYY - Present (e.g. 06/2022 - 08/2023)
    num_range_match = re.search(
        r"\b(0?[1-9]|1[0-2])\s*[\/\.]\s*(20[12][0-9])\s*(?:[-–—]|to|until)\s*(?:(0?[1-9]|1[0-2])\s*[\/\.]\s*)?(20[12][0-9]|sekarang|present|now|saat\s*ini|current|ongoing)?\b",
        text,
        re.IGNORECASE
    )
    if num_range_match:
        try:
            m1 = int(num_range_match.group(1))
            y1 = int(num_range_match.group(2))
            m2_str = num_range_match.group(3)
            y2_str = (num_range_match.group(4) or "").lower()
            if y2_str in present_keywords or not y2_str:
                y2 = curr_year
                m2 = curr_month
            else:
                y2 = int(y2_str)
                m2 = int(m2_str) if m2_str else 12
            total_months = (y2 - y1) * 12 + (m2 - m1 + 1)
            if 1 <= total_months <= 60:
                return total_months
        except ValueError:
            pass

    # 3. Pola bulan kata + tahun: 'Jan 2022 - Dec 2022' atau 'January 2023 to Present'
    month_range_pattern = re.compile(
        r"\b([A-Za-z]+)\s+(20[12][0-9])\s*(?:[-–—]|to|until)\s*([A-Za-z]+)?\s*(20[12][0-9]|sekarang|present|now|saat\s*ini|current|ongoing)?\b",
        re.IGNORECASE
    )
    m_match = month_range_pattern.search(text)
    if m_match:
        m1_str = (m_match.group(1) or "").lower()
        y1_str = m_match.group(2)
        m2_str = (m_match.group(3) or "").lower()
        y2_str = (m_match.group(4) or "").lower()

        m1 = MONTH_NAMES.get(m1_str, 1)
        y1 = int(y1_str) if y1_str else curr_year

        if y2_str in present_keywords or m2_str in present_keywords or not y2_str:
            y2 = curr_year
            m2 = curr_month
        else:
            try:
                y2 = int(y2_str)
            except ValueError:
                y2 = y1
            m2 = MONTH_NAMES.get(m2_str, 12)

        total_months = (y2 - y1) * 12 + (m2 - m1 + 1)
        if 1 <= total_months <= 60:
            return total_months

    # 4. Pola tahun '2022 - 2023' atau '2022 to Present'
    year_range_match = re.search(r"\b(20[12][0-9])\s*(?:[-–—]|to|until)\s*(20[12][0-9]|sekarang|present|now|saat\s*ini|current|ongoing)\b", text, re.IGNORECASE)
    if year_range_match:
        try:
            y1 = int(year_range_match.group(1))
            y2_str = year_range_match.group(2).lower()
            y2 = curr_year if y2_str in present_keywords else int(y2_str)
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
        # Cari pola eksplisit "Nama: ...", "Name: ...", "Nama Lengkap: ..."
        # Menggunakan regex per-baris agar tidak menyerap teks baris berikutnya (seperti Email: atau No HP:)
        name_match = re.search(r"(?:nama lengkap|nama|name|full name)\s*[:\-]\s*([A-Za-z \t\.,']{2,60})", full_text, re.IGNORECASE)
        if name_match:
            candidate_raw = name_match.group(1).splitlines()[0].strip()
            # Bersihkan jika ada trailing label
            candidate_raw = re.sub(r"\s+(?:email|phone|hp|telepon|no\b).*$", "", candidate_raw, flags=re.IGNORECASE).strip()
            if candidate_raw:
                name = candidate_raw
        
        if not name:
            # Fallback ke baris awal yang bukan judul 'curriculum vitae' / 'resume'
            lines = [l.strip() for l in full_text.splitlines() if l.strip()]
            for line in lines[:6]:
                clean_l = re.sub(r"^[#\*\s\-_]+", "", line).strip()
                if clean_l.lower() not in ("curriculum vitae", "resume", "cv", "biodata", "data pribadi", "profil"):
                    name = clean_l[:80]
                    break
            if not name:
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
