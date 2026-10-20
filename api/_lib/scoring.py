"""
Modul perhitungan skor, TF-IDF vectorizer, evaluasi hard requirements, dan pemeringkatan per divisi.
Stateless dan deterministic.
"""

import os
import re
import math
from typing import Dict, Any, List, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .config import (
    DEFAULT_WEIGHTS,
    DEFAULT_DURATION_THRESHOLD_MONTHS,
    DEFAULT_PROJECTS_THRESHOLD,
    DEFAULT_MIN_GPA_RANGE,
    DEFAULT_MAX_GPA_RANGE,
    MIN_APPLICANTS_FOR_DIVISION_IDF,
)
from .gemini import evaluate_candidates_tier2

# Stopwords bahasa Indonesia dan Inggris buatan sendiri (tanpa dependensi NLTK eksternal)
STOPWORDS = set([
    # ID
    "dan", "di", "ke", "dari", "yang", "pada", "untuk", "dengan", "ini", "itu",
    "adalah", "sebagai", "dalam", "bisa", "dapat", "akan", "telah", "sudah",
    "kami", "saya", "anda", "dia", "mereka", "kita", "oleh", "secara", "atau",
    "karena", "jika", "maka", "agar", "supaya", "tetapi", "namun", "serta",
    "tentang", "antara", "hingga", "sampai", "setiap", "bagi", "hal", "ada",
    "tahun", "bulan", "hari", "saat", "waktu", "tempat", "bagian", "selama",
    # EN
    "and", "in", "on", "at", "to", "for", "with", "this", "that", "is", "are",
    "was", "were", "be", "as", "by", "from", "an", "the", "or", "of", "it",
    "we", "i", "you", "they", "he", "she", "will", "have", "has", "had",
    "been", "can", "could", "would", "should", "about", "which", "into",
    "through", "during", "before", "after", "above", "below", "between",
])


def safe_skill_match(skill: str, text: str) -> bool:
    """
    Pencocokan skill yang aman terhadap regex (literal escape)
    dan peka batas kata (word boundary), aman untuk c++, c#, .net, power bi.
    Mendukung sinonim umum (google spreadsheet -> google sheets, dsb).
    """
    if not skill or not text:
        return False

    cleaned_skill = skill.strip().lower()
    cleaned_text = text.lower()

    # Karakter khusus seperti c++, c#, .net membutuhkan boundary non-alfanumerik
    escaped = re.escape(cleaned_skill)
    pattern = rf"(?:^|[\s,;:\(\)\[\]\/\-\|\.\*•])({escaped})(?:$|[\s,;:\(\)\[\]\/\-\|\.\*•])"
    if bool(re.search(pattern, cleaned_text)):
        return True

    # Kamus sinonim dan padanan kompetensi dwibahasa (ID & EN)
    synonyms = {
        # Riset & Analisis
        "riset pasar": ["market research", "market analysis", "industry research"],
        "market research": ["riset pasar", "market analysis", "industry research"],
        "riset kompetitor": ["competitor research", "competitive analysis", "competitor analysis", "analisis kompetitor"],
        "competitor research": ["riset kompetitor", "competitive analysis", "competitor analysis", "analisis kompetitor"],
        "analisis data": ["data analysis", "data analytics", "data analytic"],
        "data analysis": ["analisis data", "data analytics", "data analytic"],
        "analisis keuangan": ["financial analysis", "financial modeling", "analisa keuangan"],
        "financial analysis": ["analisis keuangan", "financial modeling"],

        # Bisnis, Penjualan & Kemitraan
        "negosiasi": ["negotiation", "negotiating", "deal closing", "contract negotiation"],
        "negotiation": ["negosiasi", "negotiating", "deal closing"],
        "penjualan": ["sales", "selling", "b2b sales", "b2c sales", "direct sales"],
        "sales": ["penjualan", "selling", "b2b sales", "b2c sales", "sales pipeline"],
        "kemitraan": ["partnership", "partnerships", "strategic partnership", "kerja sama", "kerjasama", "business partnership"],
        "partnership": ["kemitraan", "partnerships", "strategic partnership", "kerja sama", "kerjasama"],
        "pengembangan bisnis": ["business development", "bizdev", "busdev"],
        "business development": ["pengembangan bisnis", "bizdev", "busdev"],
        "pengelolaan database leads": ["lead management", "leads management", "crm", "lead generation", "prospecting"],
        "lead management": ["pengelolaan leads", "database leads", "crm", "lead generation"],
        "pitch deck": ["pitching", "pitched", "pitch", "presentation deck", "proposal bisnis", "business proposal"],
        "pitching": ["pitch deck", "pitched", "pitch", "presentation deck", "presentasi proposal", "client pitching"],
        "proposal": ["business proposal", "proposal bisnis", "penyusunan proposal", "proposal preparation"],

        # Konten & Media Kreatif
        "pembuatan konten": ["content creation", "content creator", "content producing", "membuat konten"],
        "content creation": ["pembuatan konten", "content creator", "content production", "membuat konten"],
        "manajemen media sosial": ["social media management", "smm", "social media marketing", "kelola media sosial"],
        "social media management": ["manajemen media sosial", "smm", "social media strategy", "kelola sosmed"],
        "penulisan naskah": ["copywriting", "copywriter", "scriptwriting", "content writing", "penulisan konten"],
        "copywriting": ["penulisan naskah", "copywriter", "penulisan konten", "content writing"],
        "penyuntingan video": ["video editing", "video editor", "edit video", "video production"],
        "video editing": ["penyuntingan video", "video editor", "edit video", "video production"],
        "desain grafis": ["graphic design", "graphic designer", "visual design", "desain grafis"],
        "graphic design": ["desain grafis", "graphic designer", "visual design"],
        "perencanaan konten": ["content planning", "content calendar", "editorial calendar", "jadwal konten"],
        "content planning": ["perencanaan konten", "content calendar", "editorial calendar"],
        "fotografi": ["photography", "photographer"],
        "photography": ["fotografi", "photographer"],
        "videografi": ["videography", "videographer"],
        "videography": ["videografi", "videographer"],

        # Pemasaran Digital
        "pemasaran digital": ["digital marketing", "online marketing", "internet marketing"],
        "digital marketing": ["pemasaran digital", "online marketing"],
        "search engine optimization": ["seo", "optimasi mesin pencari"],
        "seo": ["search engine optimization", "optimasi mesin pencari"],
        "social media advertising": ["meta ads", "facebook ads", "fb ads", "instagram ads", "tiktok ads", "google ads"],

        # Komunikasi & Hubungan Masyarakat
        "komunikasi": ["communication", "communications", "interpersonal skills", "komunikasi interpersonal"],
        "communication": ["komunikasi", "interpersonal communication", "interpersonal skills"],
        "public speaking": ["berbicara di depan umum", "presentasi", "presentation skills"],
        "hubungan masyarakat": ["public relations", "pr", "humas"],
        "public relations": ["hubungan masyarakat", "humas", "pr", "media relations"],
        "layanan pelanggan": ["customer service", "customer support", "client handling", "customer relationship"],
        "customer service": ["layanan pelanggan", "customer support", "client relations"],

        # Manajemen & Soft Skills
        "manajemen waktu": ["time management", "pengelolaan waktu"],
        "time management": ["manajemen waktu", "pengelolaan waktu"],
        "tim management": ["team management", "time management"],
        "kepemimpinan": ["leadership", "leading a team", "team leadership", "memimpin tim"],
        "leadership": ["kepemimpinan", "team leadership", "leading teams", "memimpin tim"],
        "kerja sama tim": ["teamwork", "team collaboration", "collaboration", "bekerja sama dalam tim"],
        "teamwork": ["kerja sama tim", "team collaboration", "collaboration", "kerjasama tim"],
        "pemecahan masalah": ["problem solving", "critical thinking", "penyelesaian masalah"],
        "problem solving": ["pemecahan masalah", "critical thinking", "solutif"],
        "berpikir kritis": ["critical thinking", "analytical thinking", "berpikir analitis"],
        "critical thinking": ["berpikir kritis", "analytical thinking"],
        "perhatian terhadap detail": ["attention to detail", "detail oriented", "teliti"],
        "attention to detail": ["perhatian terhadap detail", "detail oriented", "teliti"],
        "manajemen proyek": ["project management", "project coordinator", "manajemen proyek"],
        "project management": ["manajemen proyek", "project coordination"],
        "manajemen acara": ["event management", "event organizing", "manajemen event", "eo"],
        "event management": ["manajemen acara", "event organizing", "event organizer"],

        # Alat Kerja & Software
        "google spreadsheet": ["google sheet", "google sheets", "spreadsheet", "spreadsheets"],
        "google docs": ["google doc", "gdocs", "gdoc"],
        "google workspace": ["google suite", "gsuite", "g-suite", "google worskpace"],
        "microsoft office": ["ms office", "ms. office", "ms-office", "office 365", "msoffice"],
        "microsoft excel": ["ms excel", "excel", "spreadsheet"],
        "excel": ["microsoft excel", "ms excel", "spreadsheet"],
        "canva": ["canva design"],
        "capcut": ["capcut editing", "cap cut"],
        "adobe": ["adobe premiere", "adobe photoshop", "photoshop", "illustrator", "premiere"],
        "adobe premiere": ["premiere pro", "adobe premiere pro"],
        "adobe photoshop": ["photoshop", "ps"],
        "adobe illustrator": ["illustrator", "ai"],
        "figma": ["figma design", "ui/ux design"],
        "storytelling": ["story telling", "bercerita"],
        "story telling": ["storytelling"],
    }

    # 1. Cek langsung dari kamus
    alt_list = list(synonyms.get(cleaned_skill, []))

    # 2. Cek apakah cleaned_skill ada di dalam salah satu nilai sinonim (pencocokan dua arah)
    if not alt_list:
        for key, val_list in synonyms.items():
            if cleaned_skill in val_list:
                alt_list.append(key)
                alt_list.extend([v for v in val_list if v != cleaned_skill])
                break

    for alt in alt_list:
        alt_esc = re.escape(alt)
        alt_pattern = rf"(?:^|[\s,;:\(\)\[\]\/\-\|\.\*•])({alt_esc})(?:$|[\s,;:\(\)\[\]\/\-\|\.\*•])"
        if bool(re.search(alt_pattern, cleaned_text)):
            return True

    return False


# Klaster Sinonim Jurusan Dwibahasa (Bahasa Indonesia & Bahasa Inggris)
MAJOR_SYNONYM_CLUSTERS = [
    # Manajemen & Bisnis
    {"manajemen", "management", "mgmt", "managerial", "business management", "manajemen bisnis"},
    {"bisnis", "business", "biz", "bba", "administrasi bisnis", "business administration", "administrasi niaga", "niaga", "commerce"},
    {"administrasi", "administration", "administrasi publik", "public administration", "administrasi negara", "administrative"},
    {"pemasaran", "marketing", "digital marketing", "market research", "brand management", "branding", "sales"},
    {"keuangan", "finance", "financial", "banking", "perbankan", "finansial", "financial management"},
    {"akuntansi", "accounting", "accountancy", "audit", "auditing", "perpajakan", "tax", "taxation"},
    {"ekonomi", "economics", "economy", "ekonomi pembangunan", "development economics", "ilmu ekonomi"},
    {"kewirausahaan", "entrepreneurship", "entrepreneur"},

    # Komunikasi & Media
    {"komunikasi", "communication", "communications", "communication studies", "communication science", "ilmu komunikasi", "mass communication", "komunikasi massa", "broadcasting", "penyiaran"},
    {"humas", "hubungan masyarakat", "public relations", "pr"},
    {"jurnalistik", "journalism", "journalist"},
    {"media", "mass media", "digital media", "media studies"},

    # Teknologi, Komputer & Sains
    {"ilmu komputer", "computer science", "cs", "comp sci", "computational science"},
    {"informatika", "teknik informatika", "informatics", "software engineering", "rekayasa perangkat lunak", "rpl"},
    {"sistem informasi", "information systems", "is", "information system", "management information systems", "mis", "sistem informasi manajemen"},
    {"teknologi informasi", "information technology", "it", "ti"},
    {"sains data", "data science", "data sains", "data analytics", "analitika data", "artificial intelligence", "ai", "kecerdasan buatan"},
    {"statistika", "statistics", "applied statistics", "statistika terapan", "aktuarial", "actuarial science", "aktuaria"},
    {"matematika", "mathematics", "math", "applied mathematics"},

    # Desain, Kreatif & Seni
    {"desain grafis", "graphic design", "graphics design", "graphic designer"},
    {"desain komunikasi visual", "dkv", "visual communication design", "vcd"},
    {"desain", "design", "desain produk", "product design", "industrial design", "desain interior", "interior design"},
    {"multimedia", "digital multimedia", "animasi", "animation", "seni rupa", "fine arts", "visual arts", "arts"},

    # Sosial, Humaniora, Bahasa & Hukum
    {"psikologi", "psychology", "psychological science"},
    {"sdm", "sumber daya manusia", "human resources", "human resource", "hr", "hrd", "manajemen sdm", "people management"},
    {"hukum", "ilmu hukum", "law", "legal", "legal studies", "jurisprudence", "sh"},
    {"hubungan internasional", "hi", "international relations", "ir", "global affairs", "international studies"},
    {"sosiologi", "sociology"},
    {"sastra inggris", "english literature", "english", "bahasa inggris", "english language", "english language and literature"},
    {"sastra", "literature", "linguistik", "linguistics"},

    # Rekayasa & Teknik (Engineering)
    {"teknik industri", "industrial engineering", "ie"},
    {"teknik mesin", "mechanical engineering", "mech eng"},
    {"teknik elektro", "electrical engineering", "ee"},
    {"teknik sipil", "civil engineering"},
    {"teknik kimia", "chemical engineering"},
    {"teknik lingkungan", "environmental engineering"},
    {"teknik", "engineering", "engineer"},

    # Pariwisata & Hospitality
    {"pariwisata", "tourism", "travel", "hospitality", "perhotelan", "hotel management", "event management"},

    # Kesehatan & Pendidikan
    {"kesehatan masyarakat", "public health"},
    {"farmasi", "pharmacy"},
    {"keperawatan", "nursing"},
    {"kedokteran", "medicine"},
    {"pendidikan", "education", "keguruan", "teaching"}
]


def is_bilingual_major_match(allowed_major: str, candidate_major: str) -> bool:
    """
    Memeriksa apakah jurusan pelamar cocok dengan kriteria jurusan yang diizinkan / diprioritaskan,
    mendukung padanan dwibahasa (Bahasa Indonesia & Bahasa Inggris) secara menyeluruh.
    """
    if not allowed_major or not candidate_major:
        return False

    a = allowed_major.lower().strip()
    c = candidate_major.lower().strip()

    # 1. Direct match & substring match
    if a in c or c in a:
        return True

    # 2. Tokenized match (e.g. "Manajemen Bisnis" vs "Bisnis")
    a_tokens = set(re.findall(r"\b[a-z]{3,}\b", a))
    c_tokens = set(re.findall(r"\b[a-z]{3,}\b", c))
    if a_tokens and c_tokens and (a_tokens.issubset(c_tokens) or c_tokens.issubset(a_tokens)):
        return True

    # 3. Cluster / Synonym lookup
    for cluster in MAJOR_SYNONYM_CLUSTERS:
        # Cek apakah allowed_major memiliki elemen di cluster ini
        a_matches_cluster = False
        for term in cluster:
            if term in a or a in term or (term in a_tokens):
                a_matches_cluster = True
                break

        if a_matches_cluster:
            # Cek apakah candidate_major juga memiliki elemen di cluster ini
            for term in cluster:
                if term in c or c in term or (term in c_tokens):
                    return True

    return False


def compute_cosine_similarity(vec: TfidfVectorizer, text_a: str, text_b: str) -> float:
    """
    Menghitung kemiripan cosine antara dua teks menggunakan model TF-IDF yang sudah di-fit.
    """
    if not text_a.strip() or not text_b.strip():
        return 0.0

    try:
        matrix = vec.transform([text_a, text_b])
        sim = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
        return float(max(0.0, min(1.0, sim)))
    except Exception:
        return 0.0


def extract_top_contributing_keywords(vec: TfidfVectorizer, text: str, top_k: int = 4) -> List[str]:
    """
    Mengekstrak kata kunci berbobot TF-IDF tertinggi dari seksi teks.
    """
    if not text.strip():
        return []

    try:
        tfidf = vec.transform([text])
        feature_names = vec.get_feature_names_out()
        scores = tfidf.toarray()[0]
        top_indices = scores.argsort()[-top_k:][::-1]
        results = []
        for idx in top_indices:
            if scores[idx] > 0.05:
                results.append(feature_names[idx])
        return results
    except Exception:
        return []


def evaluate_hard_requirements(
    candidate: Dict[str, Any],
    profile: Dict[str, Any],
    all_cv_text: str
) -> Tuple[str, List[str]]:
    """
    Mengevaluasi syarat wajib (Hard Requirements).
    Mengembalikan (status: Memenuhi | Tidak memenuhi | Perlu dicek | Tidak ada syarat wajib, daftar_alasan).
    """
    hard_req = profile.get("hardRequirements")
    if not hard_req or not isinstance(hard_req, dict):
        return "Tidak ada syarat wajib", ["Tidak ada syarat wajib yang ditentukan pada profil lowongan."]

    reasons = []
    has_any_rule = False
    needs_review = False
    failed = False

    fields = candidate.get("fields", {})
    field_status = candidate.get("fieldStatus", {})

    # 1. Evaluasi IPK Minimum
    min_gpa = hard_req.get("minGpa")
    if min_gpa is not None:
        try:
            min_gpa_float = float(min_gpa)
            has_any_rule = True
            gpa_raw = fields.get("gpa")
            gpa_stat = field_status.get("gpa", "tidak_ditemukan")

            gpa_val = None
            if gpa_raw is not None:
                try:
                    gpa_val = float(str(gpa_raw).replace(",", "."))
                except (ValueError, TypeError):
                    gpa_val = None

            if gpa_stat in ("ambigu", "tidak_ditemukan") or gpa_val is None:
                needs_review = True
                reasons.append(f"IPK tidak terbaca atau ambigu (syarat minimum {min_gpa_float:.2f}).")
            else:
                if gpa_val >= min_gpa_float:
                    reasons.append(f"IPK {gpa_val:.2f} memenuhi syarat (min {min_gpa_float:.2f}).")
                else:
                    failed = True
                    reasons.append(f"IPK {gpa_val:.2f} di bawah syarat minimum {min_gpa_float:.2f}.")
        except (ValueError, TypeError):
            pass

    # 2. Evaluasi Jurusan
    # 2. Evaluasi Jurusan (Dukungan Dwibahasa ID & EN)
    allowed_majors = hard_req.get("allowedMajors")
    if allowed_majors and isinstance(allowed_majors, list) and len(allowed_majors) > 0:
        has_any_rule = True
        cand_major = fields.get("major")
        major_stat = field_status.get("major", "tidak_ditemukan")

        # Cek apakah profil menerima semua jurusan
        is_all_majors = any("semua" in str(m).lower() for m in allowed_majors)

        # Ekstrak jurusan prioritas (membersihkan kata 'diutamakan', 'atau', 'semua')
        priority_majors = []
        for m in allowed_majors:
            cleaned_m = re.sub(r'^(diutamakan|atau)\s+', '', str(m).strip(), flags=re.I).strip()
            if cleaned_m and not re.search(r'\bsemua\b', cleaned_m, re.I):
                priority_majors.append(cleaned_m)

        # Fallback cerdas dwibahasa: Jika jurusan pelamar belum terdeteksi dari parsing awal,
        # periksa apakah ada penyebutan jurusan yang cocok di seksi pendidikan atau seluruh teks CV
        if not cand_major or major_stat == "tidak_ditemukan":
            edu_text = candidate.get("sections", {}).get("education", "")
            search_pool = (edu_text + "\n" + all_cv_text).lower()
            target_list = priority_majors if is_all_majors else allowed_majors
            for target in target_list:
                cleaned_target = re.sub(r'^(diutamakan|atau)\s+', '', str(target).strip(), flags=re.I).strip()
                matched_term = None
                for cluster in MAJOR_SYNONYM_CLUSTERS:
                    if any(term in cleaned_target.lower() for term in cluster):
                        for term in cluster:
                            if re.search(rf"\b{re.escape(term)}\b", search_pool):
                                matched_term = term
                                break
                    if matched_term:
                        break
                if not matched_term:
                    if re.search(rf"\b{re.escape(cleaned_target.lower())}\b", search_pool):
                        matched_term = cleaned_target.lower()

                if matched_term:
                    cand_major = matched_term
                    major_stat = "ok"
                    fields["major"] = cand_major
                    field_status["major"] = "ok"
                    break

        if is_all_majors:
            if cand_major and major_stat != "tidak_ditemukan":
                matched_priority = False
                for p_major in priority_majors:
                    if is_bilingual_major_match(p_major, cand_major):
                        matched_priority = True
                        break
                if matched_priority:
                    reasons.append(f"Jurusan '{cand_major}' sesuai kriteria prioritas.")
                else:
                    reasons.append(f"Jurusan '{cand_major}' memenuhi syarat (terbuka semua jurusan).")
            else:
                reasons.append("Terbuka untuk semua jurusan.")
        else:
            if major_stat == "tidak_ditemukan" or not cand_major:
                needs_review = True
                reasons.append("Jurusan pelamar tidak terdeteksi pada CV.")
            else:
                matched_major = False
                for allowed in allowed_majors:
                    cleaned_allowed = re.sub(r'^(diutamakan|atau)\s+', '', str(allowed).strip(), flags=re.I).strip()
                    if is_bilingual_major_match(cleaned_allowed, cand_major):
                        matched_major = True
                        break

                if matched_major:
                    reasons.append(f"Jurusan '{cand_major}' sesuai kriteria.")
                else:
                    has_diutamakan = any("diutamakan" in str(m).lower() for m in allowed_majors)
                    if has_diutamakan:
                        reasons.append(f"Jurusan '{cand_major}' dapat dipertimbangkan (diutamakan: {', '.join(priority_majors or allowed_majors)}).")
                    else:
                        failed = True
                        reasons.append(f"Jurusan '{cand_major}' tidak masuk dalam daftar yang diterima.")

    # 3. Evaluasi Kompetensi Wajib
    mand_skills_obj = hard_req.get("mandatorySkills")
    if mand_skills_obj and isinstance(mand_skills_obj, dict):
        items = mand_skills_obj.get("items", [])
        rule = mand_skills_obj.get("rule", "all")
        min_count = mand_skills_obj.get("minCount", len(items))

        if items:
            has_any_rule = True
            found_skills = [s for s in items if safe_skill_match(s, all_cv_text)]
            if rule == "all":
                if len(found_skills) == len(items):
                    reasons.append(f"Seluruh kompetensi wajib terpenuhi ({', '.join(found_skills)}).")
                else:
                    missing = [s for s in items if s not in found_skills]
                    failed = True
                    reasons.append(f"Kompetensi wajib belum lengkap. Belum ditemukan: {', '.join(missing)}.")
            elif rule == "min_n":
                if len(found_skills) >= min_count:
                    reasons.append(f"Kompetensi wajib terpenuhi {len(found_skills)}/{min_count} ({', '.join(found_skills)}).")
                else:
                    failed = True
                    reasons.append(f"Kompetensi wajib hanya ditemukan {len(found_skills)} dari minimal {min_count}.")

    if not has_any_rule:
        return "Tidak ada syarat wajib", ["Tidak ada syarat wajib pada profil ini."]

    if failed:
        return "Tidak memenuhi", reasons
    if needs_review:
        return "Perlu dicek", reasons

    return "Memenuhi", reasons


def calculate_category_scores(
    candidate: Dict[str, Any],
    profile: Dict[str, Any],
    vec: TfidfVectorizer,
    jd_text: str,
    all_cv_text: str
) -> Tuple[Dict[str, float], float, List[str]]:
    """
    Menghitung skor tiap kategori aktif (0-100) dan skor akhir terbobot (0-100).
    Mengembalikan (category_scores, final_score, reason_snippets).
    """
    sections = candidate.get("sections", {})
    fields = candidate.get("fields", {})
    categories_cfg = profile.get("categories", {})
    thresholds = profile.get("thresholds", {})
    hard_req = profile.get("hardRequirements", {})

    dur_raw = thresholds.get("durationMonths")
    if dur_raw is None:
        dur_threshold = DEFAULT_DURATION_THRESHOLD_MONTHS
    else:
        try:
            dur_threshold = float(dur_raw)
        except (ValueError, TypeError):
            dur_threshold = DEFAULT_DURATION_THRESHOLD_MONTHS

    proj_raw = thresholds.get("projectsCount")
    if proj_raw is None:
        proj_threshold = DEFAULT_PROJECTS_THRESHOLD
    else:
        try:
            proj_threshold = float(proj_raw)
        except (ValueError, TypeError):
            proj_threshold = DEFAULT_PROJECTS_THRESHOLD

    category_scores = {}
    reasons = []

    # Kumpulan seluruh skill relevan untuk penyesuaian semantik dwibahasa
    mand_items_all = (hard_req.get("mandatorySkills", {}).get("items", []) if hard_req else []) + (profile.get("additionalSkills", []) or [])

    # 1. Kategori Pengalaman
    exp_text = sections.get("experience", "")
    exp_sim = compute_cosine_similarity(vec, exp_text, jd_text) * 100.0
    experiences = fields.get("experiences", [])
    total_months = sum(e.get("durationMonths", 0) for e in experiences if isinstance(e, dict))
    if dur_threshold <= 0:
        dur_score = 100.0
    else:
        dur_score = min(total_months / dur_threshold, 1.0) * 100.0

    # Dukungan dwibahasa: padukan kesesuaian skill kompetensi ke dalam skor semantik pengalaman
    if mand_items_all and exp_text:
        matched_in_exp = [s for s in mand_items_all if safe_skill_match(s, exp_text)]
        if matched_in_exp:
            exp_target_count = max(1, min(2, len(mand_items_all)))
            exp_skill_density = min(100.0, (len(matched_in_exp) / exp_target_count) * 100.0)
            exp_sim = max(exp_sim, (0.30 * exp_sim + 0.70 * exp_skill_density))

    exp_score = (0.70 * exp_sim) + (0.30 * dur_score)
    category_scores["experience"] = round(exp_score, 1)

    top_exp_words = extract_top_contributing_keywords(vec, exp_text)
    if top_exp_words:
        reasons.append(f"Kata kunci pengalaman relevan: {', '.join(top_exp_words)}")

    # 2. Kategori Project / Portofolio
    proj_text = sections.get("projects", "")
    proj_sim = compute_cosine_similarity(vec, proj_text, jd_text) * 100.0
    projects = fields.get("projects", [])
    if proj_threshold <= 0:
        count_score = 100.0
    else:
        count_score = min(len(projects) / proj_threshold, 1.0) * 100.0

    # Dukungan dwibahasa: padukan kesesuaian skill kompetensi ke dalam skor semantik project
    if mand_items_all and proj_text:
        matched_in_proj = [s for s in mand_items_all if safe_skill_match(s, proj_text)]
        if matched_in_proj:
            proj_target_count = max(1, min(2, len(mand_items_all)))
            proj_skill_density = min(100.0, (len(matched_in_proj) / proj_target_count) * 100.0)
            proj_sim = max(proj_sim, (0.30 * proj_sim + 0.70 * proj_skill_density))

    proj_score = (0.70 * proj_sim) + (0.30 * count_score)
    category_scores["projects"] = round(proj_score, 1)

    top_proj_words = extract_top_contributing_keywords(vec, proj_text)
    if top_proj_words:
        reasons.append(f"Kata kunci project relevan: {', '.join(top_proj_words)}")

    # 3. Kategori Sertifikasi & Pendidikan
    cert_text = sections.get("certifications", "")
    cert_sim = compute_cosine_similarity(vec, cert_text, jd_text) * 100.0

    # Evaluasi relevansi sertifikasi dwibahasa (ID & EN)
    if cert_text.strip():
        is_cert_relevant = (
            any(safe_skill_match(s, cert_text) for s in mand_items_all)
            or (profile.get("title", "").lower() in cert_text.lower())
            or (profile.get("division", "").lower() in cert_text.lower())
        )
        cert_score = max(cert_sim, 90.0 if is_cert_relevant else 70.0)
    else:
        cert_score = 0.0

    # Cek apakah profil mensyaratkan jurusan & IPK
    allowed_majors = hard_req.get("allowedMajors") or []
    is_all_majors = any("semua" in str(m).lower() for m in allowed_majors)
    priority_majors = []
    for m in allowed_majors:
        cleaned_m = re.sub(r'^(diutamakan|atau)\s+', '', str(m).strip(), flags=re.I).strip()
        if cleaned_m and not re.search(r'\bsemua\b', cleaned_m, re.I):
            priority_majors.append(cleaned_m)

    uses_major = bool(allowed_majors) and not (is_all_majors and not priority_majors)
    uses_gpa = hard_req.get("minGpa") is not None

    cand_major = fields.get("major", "")
    if cand_major:
        if priority_majors:
            matched_p = any(is_bilingual_major_match(p, cand_major) for p in priority_majors)
            major_match_score = 100.0 if matched_p else (80.0 if is_all_majors else 50.0)
        else:
            major_match_score = 100.0
    else:
        major_match_score = 75.0 if is_all_majors else 50.0

    gpa_val = fields.get("gpa")
    if gpa_val is not None:
        gpa_norm = max(0.0, min(1.0, (gpa_val - DEFAULT_MIN_GPA_RANGE) / (DEFAULT_MAX_GPA_RANGE - DEFAULT_MIN_GPA_RANGE))) * 100.0
    else:
        gpa_norm = 0.0 if uses_gpa else 50.0

    # Distribusi bobot sub-komponen dinamis
    has_cert = bool(cert_text.strip())
    if has_cert:
        if uses_major and uses_gpa:
            edu_score = (0.30 * cert_score) + (0.35 * major_match_score) + (0.35 * gpa_norm)
        elif uses_major or uses_gpa:
            edu_score = (0.40 * cert_score) + (0.60 * (major_match_score if uses_major else gpa_norm))
        else:
            edu_score = cert_score
    else:
        if uses_major and uses_gpa:
            edu_score = (0.50 * major_match_score) + (0.50 * gpa_norm)
        elif uses_major or uses_gpa:
            edu_score = major_match_score if uses_major else gpa_norm
        else:
            edu_score = 50.0

    category_scores["cert_edu"] = round(edu_score, 1)

    # 4. Kategori Kompetensi
    mand_items = hard_req.get("mandatorySkills", {}).get("items", []) if hard_req else []
    add_items = profile.get("additionalSkills", []) or []

    found_mand = [s for s in mand_items if safe_skill_match(s, all_cv_text)]
    found_add = [s for s in add_items if safe_skill_match(s, all_cv_text)]

    all_found_skills = list(dict.fromkeys(found_mand + found_add))
    fields["skillsFound"] = all_found_skills

    pct_mand = (len(found_mand) / len(mand_items)) * 100.0 if mand_items else 0.0
    pct_add = (len(found_add) / len(add_items)) * 100.0 if add_items else 0.0

    if mand_items and add_items:
        comp_score = (0.70 * pct_mand) + (0.30 * pct_add)
    elif mand_items:
        comp_score = pct_mand
    elif add_items:
        comp_score = pct_add
    else:
        comp_score = 0.0

    category_scores["competencies"] = round(comp_score, 1)
    if all_found_skills:
        reasons.append(f"Kompetensi cocok: {', '.join(all_found_skills)}")

    # Hitung Skor Akhir Terbobot
    total_active_weight = 0.0
    weighted_sum = 0.0

    for cat_key, cat_cfg in categories_cfg.items():
        if cat_cfg.get("active", True):
            w = float(cat_cfg.get("weight", 0.0))
            score = category_scores.get(cat_key, 0.0)
            weighted_sum += (w * score)
            total_active_weight += w

    if total_active_weight > 0:
        final_score = round(weighted_sum / total_active_weight, 2)
    else:
        final_score = 0.0

    return category_scores, final_score, reasons


def rank_candidates_for_batch(
    candidates: List[Dict[str, Any]],
    profiles_by_division: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Mengelompokkan pelamar per divisi, menghitung TF-IDF dan skor, serta menyusun urutan ranking.
    Mengembalikan { divisionResults: { div: [RankedCandidate] }, reviewList: [ReviewItem], meta: {...} }
    """
    division_groups: Dict[str, List[Dict[str, Any]]] = {}
    review_list = []
    all_batch_texts = []

    # Siapkan korpus teks gabungan
    for c in candidates:
        sections = c.get("sections", {})
        combined_text = " ".join([
            sections.get("experience", ""),
            sections.get("projects", ""),
            sections.get("certifications", ""),
            sections.get("skills", ""),
            sections.get("education", ""),
            sections.get("others", "")
        ]).strip()
        c["_combined_text"] = combined_text
        if combined_text:
            all_batch_texts.append(combined_text)

        # Cek apakah kandidat gagal proses
        if c.get("isScanPdf"):
            review_list.append({
                "rowIndex": c.get("sourceRowIndex"),
                "name": c.get("candidateName", "Pelamar"),
                "division": ", ".join(c.get("divisionChoices", [])),
                "issueType": "PDF Scan / Gambar",
                "suggestedAction": c.get("error") or "Lakukan pengecekan manual. OCR tidak berhasil mengekstrak teks dari gambar/scan ini.",
                "driveLink": c.get("driveLink")
            })
            continue

        if c.get("error"):
            review_list.append({
                "rowIndex": c.get("sourceRowIndex"),
                "name": c.get("candidateName", "Pelamar"),
                "division": ", ".join(c.get("divisionChoices", [])),
                "issueType": "Gagal Ekstraksi / Format Tidak Didukung",
                "suggestedAction": c["error"],
                "driveLink": c.get("driveLink")
            })
            continue

        # Pengelompokan divisi
        div_choices = c.get("divisionChoices", [])
        if not div_choices:
            review_list.append({
                "rowIndex": c.get("sourceRowIndex"),
                "name": c.get("candidateName", "Pelamar"),
                "issueType": "Divisi Kosong",
                "suggestedAction": "Petakan divisi pelamar secara manual.",
                "driveLink": c.get("driveLink")
            })
            continue

        for raw_div_name in div_choices:
            if not raw_div_name:
                continue
            # Resolusi nama divisi kanonikal dari profil/alias
            prof = profiles_by_division.get(raw_div_name)
            if not prof:
                for pk, pv in profiles_by_division.items():
                    if pk.strip().lower() == raw_div_name.strip().lower():
                        prof = pv
                        break
            canonical_div = prof.get("division") if prof else raw_div_name.strip()

            if canonical_div not in division_groups:
                division_groups[canonical_div] = []
            division_groups[canonical_div].append(c)

    results_by_division = {}
    fit_methods_used = {}

    for div_name, div_candidates in division_groups.items():
        profile = profiles_by_division.get(div_name)
        if not profile:
            for pk, pv in profiles_by_division.items():
                if pk.strip().lower() == div_name.strip().lower():
                    profile = pv
                    break

        if not profile:
            for cand in div_candidates:
                review_list.append({
                    "rowIndex": cand.get("sourceRowIndex"),
                    "name": cand.get("candidateName", "Pelamar"),
                    "division": div_name,
                    "issueType": "Divisi Tidak Terpetakan",
                    "suggestedAction": f"Profil divisi '{div_name}' belum dibuat. Buat profil untuk menilai pelamar ini.",
                    "driveLink": cand.get("driveLink")
                })
            continue

        jd_text = profile.get("jd", "")
        div_texts = [c["_combined_text"] for c in div_candidates if c["_combined_text"]]

        # Aturan Fit TF-IDF:
        # Jika pelamar >= 20, fit pada teks divisi + JD.
        # Jika < 20, fit pada seluruh batch + JD.
        if len(div_candidates) >= MIN_APPLICANTS_FOR_DIVISION_IDF:
            corpus = div_texts + [jd_text]
            fit_method = f"Fit khusus korpus divisi {div_name} ({len(div_candidates)} pelamar)"
        else:
            corpus = all_batch_texts + [jd_text]
            fit_method = f"Fit korpus seluruh batch ({len(all_batch_texts)} CV) + JD (karena pelamar < 20)"

        fit_methods_used[div_name] = fit_method

        vec = TfidfVectorizer(
            sublinear_tf=True,
            ngram_range=(1, 2),
            stop_words=list(STOPWORDS)
        )
        try:
            vec.fit(corpus if corpus else [jd_text])
        except Exception:
            vec.fit([jd_text, "pengalaman kerja kemampuan pendidikan project"])

        ranked_list = []
        for cand in div_candidates:
            combined = cand.get("_combined_text", "")
            fields = cand.get("fields", {})

            # Evaluasi Syarat Wajib
            hard_status, hard_reasons = evaluate_hard_requirements(cand, profile, combined)

            # Hitung Skor
            cat_scores, final_score, score_reasons = calculate_category_scores(
                candidate=cand,
                profile=profile,
                vec=vec,
                jd_text=jd_text,
                all_cv_text=combined
            )

            all_reasons = hard_reasons + score_reasons
            reason_text = " | ".join(all_reasons)

            multi_div_note = ""
            if len(cand.get("divisionChoices", [])) > 1:
                multi_div_note = f"Kandidat juga melamar di divisi: {', '.join([d for d in cand['divisionChoices'] if d != div_name])}"

            ranked_item = {
                "division": div_name,
                "fileId": cand.get("fileId", ""),
                "sourceRowIndex": cand.get("sourceRowIndex"),
                "name": fields.get("name") or cand.get("candidateName") or "Tanpa Nama",
                "candidateName": fields.get("name") or cand.get("candidateName") or "Tanpa Nama",
                "email": fields.get("email"),
                "phone": fields.get("phone"),
                "university": fields.get("university"),
                "major": fields.get("major"),
                "gpa": fields.get("gpa"),
                "graduationYearOrSemester": fields.get("graduationYearOrSemester"),
                "portfolioLinks": fields.get("portfolioLinks", []),
                "skillsFound": fields.get("skillsFound", []),
                "experiences": fields.get("experiences", []),
                "projects": fields.get("projects", []),
                "certifications": fields.get("certifications", []),
                "categoryScores": cat_scores,
                "finalScore": final_score,
                "hardRequirementStatus": hard_status,
                "reasons": reason_text,
                "flags": cand.get("flags", []),
                "driveLink": cand.get("driveLink"),
                "multiDivisionNote": multi_div_note,
                "divisionChoices": cand.get("divisionChoices", []),
            }
            ranked_list.append(ranked_item)

        # Pengurutan: Memenuhi -> Perlu dicek -> Tidak memenuhi, masing-masing berdasarkan finalScore desc
        status_priority = {
            "Memenuhi": 1,
            "Tidak ada syarat wajib": 1,
            "Perlu dicek": 2,
            "Tidak memenuhi": 3,
        }

        ranked_list.sort(key=lambda x: (
            status_priority.get(x["hardRequirementStatus"], 4),
            -x["finalScore"]
        ))

        # Beri nomor peringkat 1..N dalam divisi
        for rank_num, item in enumerate(ranked_list, start=1):
            item["rank"] = rank_num

        results_by_division[div_name] = ranked_list

    # -------------------------------------------------------------
    # Pass 1.5: Tier 2 Evaluasi Kontekstual AI Mendalam (Paralel, Non-Blocking, Max 4.5s)
    # -------------------------------------------------------------
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if api_key and results_by_division:
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

        division_tasks = {}
        for div_k, r_list in results_by_division.items():
            if r_list:
                prof = profiles_by_division.get(div_k) or {}
                division_tasks[div_k] = (r_list, prof)

        if division_tasks:
            def _eval_worker(task_item):
                d_name, (candidates_list, d_profile) = task_item
                try:
                    return d_name, evaluate_candidates_tier2(candidates_list, d_profile, max_candidates=10, api_key=api_key)
                except Exception as ex:
                    print(f"[Tier 2 Worker Error for {d_name}]: {ex}")
                    return d_name, {}

            max_w = min(len(division_tasks), 4)
            executor = ThreadPoolExecutor(max_workers=max_w)
            try:
                futures = {executor.submit(_eval_worker, item): item[0] for item in division_tasks.items()}
                try:
                    # Batas waktu total 20 detik untuk seluruh batch evaluasi AI paralel
                    for fut in as_completed(futures, timeout=20.0):
                        try:
                            d_name, ai_evals = fut.result()
                            if ai_evals and d_name in results_by_division:
                                for item in results_by_division[d_name]:
                                    c_key = str(item.get("fileId") or item.get("email") or item.get("sourceRowIndex") or item.get("rank") or "")
                                    ev = ai_evals.get(c_key) or ai_evals.get(str(item.get("rank", "")))
                                    if ev:
                                        item["aiEvaluation"] = ev
                                        summary = ev.get("executiveSummary")
                                        if summary:
                                            item["reasons"] = f"[✨ AI: {summary}] | {item.get('reasons', '')}"
                        except Exception:
                            continue
                except TimeoutError:
                    print("[Tier 2 AI Warning] Batas waktu tercapai. Melanjutkan dengan data ranking yang sudah siap.")
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

    # -------------------------------------------------------------
    # Pass 2: Evaluasi & Perbandingan Lintas Pilihan (Pilihan 1 vs Pilihan 2)
    # -------------------------------------------------------------
    evals_by_candidate = {}
    for div_k, cand_list in results_by_division.items():
        for item in cand_list:
            cand_key = item.get("fileId") or item.get("email") or str(item.get("sourceRowIndex"))
            if cand_key not in evals_by_candidate:
                evals_by_candidate[cand_key] = {}
            evals_by_candidate[cand_key][div_k] = item

    for div_k, cand_list in results_by_division.items():
        for item in cand_list:
            cand_key = item.get("fileId") or item.get("email") or str(item.get("sourceRowIndex"))
            cand_map = evals_by_candidate.get(cand_key, {})
            choices = item.get("divisionChoices", [])
            
            p1_name = choices[0] if len(choices) > 0 else div_k
            p2_name = choices[1] if len(choices) > 1 else None

            item["pilihan1"] = p1_name
            item["pilihan2"] = p2_name
            item["choiceRank"] = 1 if div_k == p1_name else (2 if div_k == p2_name else 1)
            item["isFirstChoice"] = (div_k == p1_name)

            c1 = cand_map.get(p1_name)
            c2 = cand_map.get(p2_name) if p2_name else None

            if c1:
                item["choice1Result"] = {
                    "division": p1_name,
                    "rank": c1.get("rank"),
                    "finalScore": c1.get("finalScore", 0.0),
                    "hardRequirementStatus": c1.get("hardRequirementStatus", ""),
                    "categoryScores": c1.get("categoryScores", {}),
                    "reasons": c1.get("reasons", ""),
                }
            if c2:
                item["choice2Result"] = {
                    "division": p2_name,
                    "rank": c2.get("rank"),
                    "finalScore": c2.get("finalScore", 0.0),
                    "hardRequirementStatus": c2.get("hardRequirementStatus", ""),
                    "categoryScores": c2.get("categoryScores", {}),
                    "reasons": c2.get("reasons", ""),
                }

            # Analisis Perbandingan & Rekomendasi
            if c1 and c2:
                s1 = c1.get("finalScore", 0.0)
                s2 = c2.get("finalScore", 0.0)
                st1 = c1.get("hardRequirementStatus", "")
                st2 = c2.get("hardRequirementStatus", "")

                prio1 = 1 if st1 in ["Memenuhi", "Tidak ada syarat wajib"] else (2 if st1 == "Perlu dicek" else 3)
                prio2 = 1 if st2 in ["Memenuhi", "Tidak ada syarat wajib"] else (2 if st2 == "Perlu dicek" else 3)

                if prio2 < prio1:
                    item["bestFitChoice"] = 2
                    rec = f"⚠️ Lebih direkomendasikan di Pilihan 2 ({p2_name}): Status '{st2}' & Skor {s2} (Pilihan 1 '{p1_name}': '{st1}', Skor {s1})"
                elif prio1 < prio2:
                    item["bestFitChoice"] = 1
                    rec = f"Direkomendasikan di Pilihan 1 ({p1_name}): Status '{st1}' & Skor {s1} (Pilihan 2 '{p2_name}': '{st2}', Skor {s2})"
                else:
                    diff = round(s2 - s1, 1)
                    if diff >= 5.0:
                        item["bestFitChoice"] = 2
                        rec = f"💡 Lebih unggul di Pilihan 2 ({p2_name}): Skor {s2} vs {s1} di Pilihan 1 (+{diff} poin)"
                    elif diff <= -5.0:
                        item["bestFitChoice"] = 1
                        rec = f"Unggul di Pilihan 1 ({p1_name}): Skor {s1} vs {s2} di Pilihan 2 (+{round(abs(diff), 1)} poin)"
                    elif s1 >= s2:
                        item["bestFitChoice"] = 1
                        rec = f"Direkomendasikan di Pilihan 1 ({p1_name}): Skor {s1} (Pilihan 2: {s2})"
                    else:
                        item["bestFitChoice"] = "equal"
                        rec = f"Skor berimbang: Pilihan 1 ({s1}) vs Pilihan 2 ({s2})"

                item["recommendationNote"] = rec
                item["multiDivisionNote"] = rec
            elif p2_name:
                item["bestFitChoice"] = 1
                item["recommendationNote"] = f"Pilihan 1: {p1_name}. Pilihan 2: {p2_name} (Profil lowongan belum dibuat)"
                item["multiDivisionNote"] = f"Pilihan 2: {p2_name} (Profil lowongan belum dibuat)"
            else:
                item["bestFitChoice"] = 1
                item["recommendationNote"] = f"Kandidat hanya memilih 1 divisi ({p1_name})"

    return {
        "divisionResults": results_by_division,
        "reviewList": review_list,
        "meta": {
            "totalProcessed": len(candidates),
            "fitMethods": fit_methods_used,
        }
    }
