"""
Modul perhitungan skor, TF-IDF vectorizer, evaluasi hard requirements, dan pemeringkatan per divisi.
Stateless dan deterministic.
"""

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
    """
    if not skill or not text:
        return False

    cleaned_skill = skill.strip().lower()
    cleaned_text = text.lower()

    # Karakter khusus seperti c++, c#, .net membutuhkan boundary non-alfanumerik
    escaped = re.escape(cleaned_skill)
    pattern = rf"(?:^|[\s,;:\(\)\[\]\/\-\|\.\*•])({escaped})(?:$|[\s,;:\(\)\[\]\/\-\|\.\*•])"
    return bool(re.search(pattern, cleaned_text))


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
    allowed_majors = hard_req.get("allowedMajors")
    if allowed_majors and isinstance(allowed_majors, list) and len(allowed_majors) > 0:
        has_any_rule = True
        cand_major = fields.get("major")
        major_stat = field_status.get("major", "tidak_ditemukan")

        if major_stat == "tidak_ditemukan" or not cand_major:
            needs_review = True
            reasons.append("Jurusan pelamar tidak terdeteksi pada CV.")
        else:
            matched_major = False
            for allowed in allowed_majors:
                if allowed.lower() in cand_major.lower() or cand_major.lower() in allowed.lower():
                    matched_major = True
                    break

            if matched_major:
                reasons.append(f"Jurusan '{cand_major}' sesuai kriteria.")
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

    dur_threshold = thresholds.get("durationMonths", DEFAULT_DURATION_THRESHOLD_MONTHS) or DEFAULT_DURATION_THRESHOLD_MONTHS
    proj_threshold = thresholds.get("projectsCount", DEFAULT_PROJECTS_THRESHOLD) or DEFAULT_PROJECTS_THRESHOLD

    category_scores = {}
    reasons = []

    # 1. Kategori Pengalaman
    exp_text = sections.get("experience", "")
    exp_sim = compute_cosine_similarity(vec, exp_text, jd_text) * 100.0
    experiences = fields.get("experiences", [])
    total_months = sum(e.get("durationMonths", 0) for e in experiences)
    dur_score = min(total_months / dur_threshold, 1.0) * 100.0
    exp_score = (0.70 * exp_sim) + (0.30 * dur_score)
    category_scores["experience"] = round(exp_score, 1)

    top_exp_words = extract_top_contributing_keywords(vec, exp_text)
    if top_exp_words:
        reasons.append(f"Kata kunci pengalaman relevan: {', '.join(top_exp_words)}")

    # 2. Kategori Project / Portofolio
    proj_text = sections.get("projects", "")
    proj_sim = compute_cosine_similarity(vec, proj_text, jd_text) * 100.0
    projects = fields.get("projects", [])
    count_score = min(len(projects) / proj_threshold, 1.0) * 100.0
    proj_score = (0.70 * proj_sim) + (0.30 * count_score)
    category_scores["projects"] = round(proj_score, 1)

    top_proj_words = extract_top_contributing_keywords(vec, proj_text)
    if top_proj_words:
        reasons.append(f"Kata kunci project relevan: {', '.join(top_proj_words)}")

    # 3. Kategori Sertifikasi & Pendidikan
    cert_text = sections.get("certifications", "")
    cert_sim = compute_cosine_similarity(vec, cert_text, jd_text) * 100.0

    # Cek apakah profil mensyaratkan jurusan & IPK
    uses_major = bool(hard_req.get("allowedMajors"))
    uses_gpa = hard_req.get("minGpa") is not None

    cand_major = fields.get("major", "")
    major_match_score = 100.0 if (uses_major and cand_major) else 50.0

    gpa_val = fields.get("gpa")
    if gpa_val is not None:
        gpa_norm = max(0.0, min(1.0, (gpa_val - DEFAULT_MIN_GPA_RANGE) / (DEFAULT_MAX_GPA_RANGE - DEFAULT_MIN_GPA_RANGE))) * 100.0
    else:
        gpa_norm = 0.0 if uses_gpa else 50.0

    # Distribusi bobot sub-komponen dinamis
    if uses_major and uses_gpa:
        edu_score = (0.50 * cert_sim) + (0.25 * major_match_score) + (0.25 * gpa_norm)
    elif uses_major or uses_gpa:
        edu_score = (0.60 * cert_sim) + (0.40 * (major_match_score if uses_major else gpa_norm))
    else:
        edu_score = cert_sim

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
                "suggestedAction": "Lakukan pengecekan manual. OCR belum didukung di V1.",
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
