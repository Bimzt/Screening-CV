"""
Modul segmentasi seksi dokumen CV berdasarkan heading (Indonesia / Inggris).
Mendukung heading kustom dari profil lowongan dan pemotongan teks seksi maksimal 4.000 karakter.
"""

import re
from typing import Dict, List, Optional, Tuple
from .config import MAX_SECTION_TEXT_CHARS

# Heading default per seksi (ID & EN)
DEFAULT_SECTION_HEADINGS = {
    "education": [
        "pendidikan", "education", "riwayat pendidikan", "latar belakang pendidikan",
        "academic background", "educational background", "riwayat studi", "pendidikan formal",
        "latar belakang akademis", "academics", "academic history", "education & qualifications",
        "education and qualifications", "qualifications", "study history", "educational history",
        "tertiary education", "university education"
    ],
    "experience": [
        "pengalaman dan pelatihan", "pengalaman kerja", "pengalaman organisasi",
        "pengalaman kerja & organisasi", "pengalaman profesional", "riwayat pengalaman",
        "work experience", "professional experience", "working experience", "work experiences",
        "employment history", "career history", "relevant experience", "work history",
        "pengalaman", "experience", "organisasi", "organization", "kepanitiaan",
        "volunteer", "volunteering", "sukarelawan", "riwayat kerja", "employment", "magang", "internship",
        "internships", "practical experience", "leadership experience", "volunteer experience",
        "pengalaman kepanitiaan", "pengalaman volunteer", "organizational experience",
        "pengalaman kerja / magang", "riwayat organisasi", "extracurricular activities",
        "extracurriculars", "co-curricular activities", "committee experience"
    ],
    "projects": [
        "project", "projects", "proyek", "portofolio", "portfolio", "karya",
        "personal project", "personal projects", "konten", "content creation",
        "selected projects", "proyek unggulan", "projects & portfolio", "project & portofolio",
        "proyek & portofolio", "key projects", "academic projects", "capstone project",
        "featured projects", "independent projects", "side projects", "client projects",
        "design portfolio"
    ],
    "certifications": [
        "sertifikasi dan pelatihan", "sertifikasi & pelatihan", "sertifikasi", "certification",
        "certifications", "pelatihan", "training", "kursus", "bootcamp", "licenses", "lisensi",
        "sertifikat", "certificates", "courses & certifications", "licenses & certifications",
        "licenses and certifications", "certifications & credentials", "credentials",
        "professional development", "training & certifications", "honors & certifications", "courses"
    ],
    "skills": [
        "kemampuan, sertifikasi, dan projects", "kemampuan, sertifikasi & projects",
        "kemampuan, sertifikasi, dan proyek", "kemampuan, sertifikasi & proyek",
        "kemampuan dan keahlian", "keahlian dan kemampuan",
        "skill", "skills", "keahlian", "kemampuan", "technical skills",
        "kompetensi", "hard skills", "soft skills", "tools", "skills & tools",
        "technical & soft skills", "keahlian teknis", "core competencies",
        "key competencies", "skills & abilities", "skills & expertise",
        "areas of expertise", "tools & technologies", "tech stack", "technologies",
        "software & tools", "skills and tools"
    ],
}


def build_heading_pattern(custom_headings: Optional[Dict[str, List[str]]] = None) -> List[Tuple[str, re.Pattern]]:
    """
    Menyusun daftar regex pattern untuk mengenali baris heading seksi.
    """
    headings_map = {k: list(v) for k, v in DEFAULT_SECTION_HEADINGS.items()}

    if custom_headings:
        for section, keywords in custom_headings.items():
            if section in headings_map:
                headings_map[section].extend(keywords)
            else:
                headings_map[section] = list(keywords)

    patterns = []
    for section_name, keywords in headings_map.items():
        # Urutkan keyword terpanjang terlebih dahulu
        sorted_kw = sorted(set(keywords), key=lambda x: -len(x))
        escaped = [re.escape(k.strip()) for k in sorted_kw if k.strip()]
        if not escaped:
            continue
        kw_regex = "|".join(escaped)
        # Cocokkan jika baris diawali atau seluruhnya memuat kata kunci heading tersebut
        pat = re.compile(
            rf"^(?:[•\-\*\d\.\)\s]*)\b({kw_regex})\b(?:\s*[:\-\|\/]?\s*)$",
            re.IGNORECASE
        )
        patterns.append((section_name, pat))

    return patterns


def segment_cv_sections(
    full_text: str,
    custom_headings: Optional[Dict[str, List[str]]] = None
) -> Tuple[Dict[str, str], List[str]]:
    """
    Membagi teks CV ke dalam seksi-seksi: education, experience, projects, certifications, skills, lainnya.
    Mengembalikan (sections_dict, flags).
    """
    sections = {
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "skills": [],
        "others": [],
    }
    flags = []

    if not full_text or not full_text.strip():
        return {k: "" for k in sections}, ["teks_cv_kosong"]

    heading_patterns = build_heading_pattern(custom_headings)

    lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    current_section = "others"
    recognized_sections_count = 0

    for line in lines:
        matched_section = None
        # Cek apakah baris ini adalah judul seksi
        # Baris heading biasanya pendek (< 60 karakter)
        if len(line) <= 60:
            for sec_name, pattern in heading_patterns:
                if pattern.match(line):
                    matched_section = sec_name
                    break

        if matched_section:
            current_section = matched_section
            recognized_sections_count += 1
        else:
            # Item-level smart sub-routing untuk seksi campuran (e.g. Kemampuan, Sertifikasi, dan Projects)
            clean_l = re.sub(r"^[•\-\*\d\.\)\s\uE000-\uF8FF]+", "", line).strip()
            clean_lower = clean_l.lower()

            target_sec = current_section
            if re.match(r"^(?:sertifikasi|sertifikat|certification|certificates?|lisensi|licenses?)\b", clean_lower):
                target_sec = "certifications"
            elif re.match(r"^(?:project|projects|proyek|portfolio|portofolio)\b", clean_lower):
                target_sec = "projects"
            elif re.match(r"^(?:hard\s+skills?|soft\s+skills?|technical\s+skills?|keahlian|tools)\b", clean_lower):
                target_sec = "skills"

            sections[target_sec].append(line)

    # Gabungkan baris tiap seksi dan potong maksimal MAX_SECTION_TEXT_CHARS karakter
    result = {}
    for sec_name, sec_lines in sections.items():
        joined = "\n".join(sec_lines).strip()
        if len(joined) > MAX_SECTION_TEXT_CHARS:
            joined = joined[:MAX_SECTION_TEXT_CHARS]
        result[sec_name] = joined

    # Jika tidak ada satu pun seksi yang dikenali, beri flag peringatan
    if recognized_sections_count == 0:
        flags.append("seksi_tidak_terdeteksi")

    return result, flags
