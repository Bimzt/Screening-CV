"""
Modul pembuatan berkas Excel (.xlsx) dengan openpyxl.
Menghasilkan 4 sheet: Ranking, Perbandingan Pilihan 1 & 2, Perlu Dicek, dan Ringkasan Lowongan.
Menerapkan mitigasi formula injection, sanitasi karakter kontrol XML, freeze panes, auto-filter, dan styling HR.
"""

import io
import datetime
from typing import Dict, Any, List
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE


def sanitize_excel_cell(val: Any) -> Any:
    """
    1. Mitigasi Karakter Ilegal XML di openpyxl:
       Bersihkan karakter kontrol non-printable (ASCII 0-8, 11-12, 14-31)
       yang sering terbawa dari ekstraksi PDF teks.
    2. Mitigasi Formula Injection:
       Jika nilai bertipe string dan diawali =, +, -, @, beri awalan tanda petik (')
       agar program spreadsheet mengevaluasinya sebagai teks biasa.
    3. Truncate teks melebihi batas sel Excel (32,767 karakter).
    """
    if val is None:
        return ""
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, (list, tuple)):
        items = []
        for x in val:
            if x is not None:
                if isinstance(x, dict):
                    items.append(str(x.get("title") or x.get("name") or x))
                else:
                    items.append(str(x))
        return ", ".join(items)
    if isinstance(val, dict):
        items = []
        for k, v in val.items():
            items.append(f"{k}: {v}")
        return " | ".join(items)

    s = str(val)
    # Hapus karakter kontrol XML ilegal agar openpyxl tidak melempar IllegalCharacterError
    s = ILLEGAL_CHARACTERS_RE.sub("", s).strip()
    # Excel batas maksimum panjang karakter per sel adalah 32,767
    if len(s) > 32000:
        s = s[:32000] + "..."
    # Formula injection mitigation
    if s.startswith(("=", "+", "-", "@")):
        s = "'" + s
    return s


def style_header_row(ws, row_idx: int, col_count: int, fill_color: str = "1E293B"):
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
    align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col in range(1, col_count + 1):
        cell = ws.cell(row=row_idx, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align


def auto_fit_columns(ws, max_widths: Dict[int, int] = None):
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        col_idx = col[0].column
        max_len = 0
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        limit = max_widths.get(col_idx, 40) if max_widths else 40
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), limit)


def generate_screening_excel(
    ranking_data: Dict[str, Any],
    profiles_by_division: Dict[str, Dict[str, Any]]
) -> bytes:
    """
    Membuat file Excel 4 sheet berstandar HR dengan openpyxl:
    1. Ranking (Detail peringkat per divisi lengkap dengan Pilihan 1 & 2)
    2. Perbandingan Pilihan 1 & 2 (Master kandidat dan analisis rekomendasi divisi terbaik)
    3. Perlu Dicek (Log berkas scan/gagal ekstraksi/perlu audit rekruter)
    4. Ringkasan Lowongan (Kriteria, bobot, dan JD per divisi)
    """
    wb = Workbook()
    
    # Border halus untuk data
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    division_results = ranking_data.get("divisionResults", {}) or {}

    # Peta indeks kandidat lintas divisi untuk resolusi komparasi Pilihan 1 & 2 (fallback data lama)
    candidates_by_key = {}
    for div_k, c_list in division_results.items():
        if not c_list:
            continue
        for c in c_list:
            if not c:
                continue
            cand_key = c.get("fileId") or c.get("email") or str(c.get("sourceRowIndex") or "")
            if cand_key:
                if cand_key not in candidates_by_key:
                    candidates_by_key[cand_key] = {}
                candidates_by_key[cand_key][div_k] = c

    # -------------------------------------------------------------
    # SHEET 1: Ranking
    # -------------------------------------------------------------
    ws_rank = wb.active
    ws_rank.title = "Ranking"
    ws_rank.views.sheetView[0].showGridLines = True

    rank_headers = [
        "Divisi",
        "Peringkat",
        "Pilihan Ke-",
        "Nama Pelamar",
        "Email",
        "No. HP",
        "Kampus",
        "Jurusan",
        "IPK",
        "Tahun Lulus / Semester",
        "Kompetensi Ditemukan",
        "Ringkasan Pengalaman",
        "Project / Portofolio",
        "Sertifikasi",
        "Tautan Portofolio",
        "Skor Pengalaman",
        "Skor Project",
        "Skor Sert & Pend",
        "Skor Kompetensi",
        "Skor Akhir",
        "Status Syarat Wajib",
        "Pilihan 1 & Skor",
        "Pilihan 2 & Skor",
        "Rekomendasi Sistem",
        "Alasan Penilaian",
        "Catatan Khusus",
        "Link CV Drive",
    ]

    ws_rank.append([sanitize_excel_cell(h) for h in rank_headers])
    style_header_row(ws_rank, 1, len(rank_headers), fill_color="1E3A8A")

    current_row = 2

    status_fills = {
        "Memenuhi": PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid"),
        "Perlu dicek": PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid"),
        "Tidak memenuhi": PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid"),
        "Tidak ada syarat wajib": PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid"),
    }

    for div_name, candidates in division_results.items():
        if not candidates:
            continue
        for cand in candidates:
            if not cand:
                continue

            cand_key = cand.get("fileId") or cand.get("email") or str(cand.get("sourceRowIndex") or "")
            peer_map = candidates_by_key.get(cand_key, {})

            # Ekstraksi pilihan divisi
            choices = cand.get("divisionChoices") or []
            if not choices and cand.get("multiDivisionNote"):
                note = str(cand.get("multiDivisionNote") or "")
                if "melamar di divisi:" in note:
                    other_part = note.split("melamar di divisi:")[-1]
                    choices = [div_name] + [d.strip() for d in other_part.split(",") if d.strip()]

            p1_name = cand.get("pilihan1") or (choices[0] if len(choices) > 0 else div_name)
            p2_name = cand.get("pilihan2") or (choices[1] if len(choices) > 1 else None)

            c1 = cand.get("choice1Result") or peer_map.get(p1_name) or {}
            c2 = cand.get("choice2Result") or (peer_map.get(p2_name) if p2_name else {}) or {}

            choice_rank = cand.get("choiceRank")
            if not choice_rank:
                choice_rank = 2 if (p2_name and div_name == p2_name) else 1
            choice_rank_str = f"Pilihan {choice_rank}"

            exp_summary_items = []
            for exp in (cand.get("experiences") or []):
                if isinstance(exp, dict):
                    t = exp.get("type") or "kerja/magang"
                    title = exp.get("title") or exp.get("role") or ""
                    dur = exp.get("durationMonths", 0)
                    exp_summary_items.append(f"[{t}] {title} ({dur} bln)")
                elif isinstance(exp, str):
                    exp_summary_items.append(exp)
            exp_summary = " | ".join(exp_summary_items)

            proj_items = []
            for p in (cand.get("projects") or []):
                if isinstance(p, dict):
                    proj_items.append(str(p.get("title", "")))
                elif isinstance(p, str):
                    proj_items.append(p)
            proj_summary = " | ".join(proj_items)

            cert_items = []
            for c in (cand.get("certifications") or []):
                if isinstance(c, dict):
                    cert_items.append(str(c.get("title") or c.get("name") or ""))
                else:
                    cert_items.append(str(c))
            cert_summary = " | ".join(cert_items)

            port_items = [str(link) for link in (cand.get("portfolioLinks") or [])]
            port_links = " | ".join(port_items)

            skills_items = [str(sk) for sk in (cand.get("skillsFound") or [])]
            skills_found = ", ".join(skills_items)

            cat_scores = cand.get("categoryScores") or {}

            p1_score = c1.get("finalScore")
            p1_score_str = f"{p1_score:.1f}" if isinstance(p1_score, (int, float)) else str(p1_score or "-")
            p1_str = f"{c1.get('division', p1_name)} ({p1_score_str})" if (c1 and p1_name) else "-"

            p2_score = c2.get("finalScore")
            p2_score_str = f"{p2_score:.1f}" if isinstance(p2_score, (int, float)) else str(p2_score or "-")
            p2_str = f"{c2.get('division', p2_name)} ({p2_score_str})" if (c2 and p2_name) else "-"

            rec_note = cand.get("recommendationNote") or cand.get("multiDivisionNote") or ""

            row_data = [
                cand.get("division"),
                cand.get("rank"),
                choice_rank_str,
                cand.get("name"),
                cand.get("email"),
                cand.get("phone"),
                cand.get("university"),
                cand.get("major"),
                cand.get("gpa") if cand.get("gpa") is not None else "-",
                cand.get("graduationYearOrSemester"),
                skills_found,
                exp_summary,
                proj_summary,
                cert_summary,
                port_links,
                cat_scores.get("experience", 0.0),
                cat_scores.get("projects", 0.0),
                cat_scores.get("cert_edu", 0.0),
                cat_scores.get("competencies", 0.0),
                cand.get("finalScore", 0.0),
                cand.get("hardRequirementStatus"),
                p1_str,
                p2_str,
                rec_note,
                cand.get("reasons"),
                cand.get("multiDivisionNote"),
                cand.get("driveLink"),
            ]

            ws_rank.append([sanitize_excel_cell(x) for x in row_data])

            # Styling sel data
            status_val = cand.get("hardRequirementStatus")
            status_cell = ws_rank.cell(row=current_row, column=21)
            if status_val in status_fills:
                status_cell.fill = status_fills[status_val]

            # Wrap text untuk kolom alasan dan rekomendasi
            ws_rank.cell(row=current_row, column=24).alignment = Alignment(wrap_text=True, vertical="top")
            ws_rank.cell(row=current_row, column=25).alignment = Alignment(wrap_text=True, vertical="top")

            for c in range(1, len(row_data) + 1):
                ws_rank.cell(row=current_row, column=c).border = thin_border

            current_row += 1

    # Freeze header & Auto filter
    ws_rank.freeze_panes = "A2"
    ws_rank.auto_filter.ref = f"A1:{get_column_letter(len(rank_headers))}{max(current_row - 1, 1)}"
    auto_fit_columns(ws_rank, {24: 45, 25: 50, 12: 45, 13: 35, 15: 30, 27: 35})

    # -------------------------------------------------------------
    # SHEET 2: Perbandingan Pilihan 1 & 2 (Master Kandidat)
    # -------------------------------------------------------------
    ws_compare = wb.create_sheet(title="Perbandingan Pilihan 1 & 2")
    ws_compare.views.sheetView[0].showGridLines = True
    compare_headers = [
        "No",
        "Nama Pelamar",
        "Email",
        "No. HP",
        "Kampus",
        "Jurusan",
        "IPK",
        "Divisi Pilihan 1",
        "Skor Pilihan 1",
        "Status Pilihan 1",
        "Divisi Pilihan 2",
        "Skor Pilihan 2",
        "Status Pilihan 2",
        "Rekomendasi Terbaik",
        "Catatan Komparasi",
        "Link CV Drive",
    ]
    ws_compare.append([sanitize_excel_cell(h) for h in compare_headers])
    style_header_row(ws_compare, 1, len(compare_headers), fill_color="4338CA")

    seen_compare = set()
    comp_row = 2
    comp_idx = 1
    for div_name, candidates in division_results.items():
        if not candidates:
            continue
        for cand in candidates:
            if not cand:
                continue
            c_key = cand.get("fileId") or cand.get("email") or str(cand.get("sourceRowIndex") or "")
            if not c_key or c_key in seen_compare:
                continue
            seen_compare.add(c_key)

            peer_map = candidates_by_key.get(c_key, {})

            choices = cand.get("divisionChoices") or []
            if not choices and cand.get("multiDivisionNote"):
                note = str(cand.get("multiDivisionNote") or "")
                if "melamar di divisi:" in note:
                    other_part = note.split("melamar di divisi:")[-1]
                    choices = [div_name] + [d.strip() for d in other_part.split(",") if d.strip()]

            p1_name = cand.get("pilihan1") or (choices[0] if len(choices) > 0 else div_name)
            p2_name = cand.get("pilihan2") or (choices[1] if len(choices) > 1 else None)

            c1 = cand.get("choice1Result") or peer_map.get(p1_name) or (cand if div_name == p1_name else {})
            c2 = cand.get("choice2Result") or (peer_map.get(p2_name) if p2_name else {}) or (cand if div_name == p2_name else {})

            p1_score = c1.get("finalScore")
            p1_score_str = f"{p1_score:.1f}" if isinstance(p1_score, (int, float)) else str(p1_score or "-")
            p1_status = c1.get("hardRequirementStatus", "-") if c1 else "-"

            p2_score = c2.get("finalScore")
            p2_score_str = f"{p2_score:.1f}" if isinstance(p2_score, (int, float)) else str(p2_score or "-")
            p2_status = c2.get("hardRequirementStatus", "-") if c2 else "-"

            best_fit = cand.get("bestFitChoice")
            if not best_fit:
                if c1 and c2 and isinstance(p1_score, (int, float)) and isinstance(p2_score, (int, float)):
                    best_fit = 2 if p2_score > p1_score else 1
                else:
                    best_fit = 1

            best_label = f"Pilihan {best_fit}" if best_fit in [1, 2] else ("Berimbang" if best_fit == "equal" else "Pilihan 1")
            rec_note = cand.get("recommendationNote") or cand.get("multiDivisionNote") or ""

            comp_data = [
                comp_idx,
                cand.get("name"),
                cand.get("email"),
                cand.get("phone"),
                cand.get("university"),
                cand.get("major"),
                cand.get("gpa") if cand.get("gpa") is not None else "-",
                p1_name,
                p1_score_str,
                p1_status,
                p2_name or "-",
                p2_score_str,
                p2_status,
                best_label,
                rec_note,
                cand.get("driveLink"),
            ]
            ws_compare.append([sanitize_excel_cell(x) for x in comp_data])

            if p1_status in status_fills:
                ws_compare.cell(row=comp_row, column=10).fill = status_fills[p1_status]
            if p2_status in status_fills:
                ws_compare.cell(row=comp_row, column=13).fill = status_fills[p2_status]

            for c in range(1, len(comp_data) + 1):
                ws_compare.cell(row=comp_row, column=c).border = thin_border
                if c == 15:
                    ws_compare.cell(row=comp_row, column=c).alignment = Alignment(wrap_text=True, vertical="top")

            comp_row += 1
            comp_idx += 1

    ws_compare.freeze_panes = "A2"
    ws_compare.auto_filter.ref = f"A1:{get_column_letter(len(compare_headers))}{max(comp_row - 1, 1)}"
    auto_fit_columns(ws_compare, {15: 55, 16: 35, 5: 30})

    # -------------------------------------------------------------
    # SHEET 3: Perlu Dicek
    # -------------------------------------------------------------
    ws_review = wb.create_sheet(title="Perlu Dicek")
    ws_review.views.sheetView[0].showGridLines = True

    review_headers = [
        "No. Baris CSV",
        "Nama Pelamar",
        "Divisi",
        "Jenis Masalah",
        "Saran Tindakan Rekruter",
        "Link CV Drive",
    ]
    ws_review.append([sanitize_excel_cell(h) for h in review_headers])
    style_header_row(ws_review, 1, len(review_headers), fill_color="B45309")

    review_list = ranking_data.get("reviewList") or []
    rev_row = 2
    for item in review_list:
        if not item:
            continue
        rev_data = [
            item.get("rowIndex") or "-",
            item.get("name"),
            item.get("division"),
            item.get("issueType"),
            item.get("suggestedAction"),
            item.get("driveLink"),
        ]
        ws_review.append([sanitize_excel_cell(x) for x in rev_data])
        for c in range(1, len(rev_data) + 1):
            cell = ws_review.cell(row=rev_row, column=c)
            cell.border = thin_border
            if c == 5:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        rev_row += 1

    ws_review.freeze_panes = "A2"
    ws_review.auto_filter.ref = f"A1:{get_column_letter(len(review_headers))}{max(rev_row - 1, 1)}"
    auto_fit_columns(ws_review, {5: 60, 4: 30, 6: 35})

    # -------------------------------------------------------------
    # SHEET 4: Ringkasan Lowongan
    # -------------------------------------------------------------
    ws_summary = wb.create_sheet(title="Ringkasan Lowongan")
    ws_summary.views.sheetView[0].showGridLines = True

    summary_meta_rows = [
        ["RINGKASAN PROSES SCREENING CV"],
        ["Keterangan Kerahasiaan:", "RAHASIA - Hanya untuk keperluan rekrutmen internal."],
        ["Pernyataan Etika:", "Skor adalah alat bantu pengurutan, bukan keputusan otomatis. Rekruter yang menentukan hasil akhir."],
        ["Keterbatasan Sistem:", "Kompetensi non-teknis hanya terdeteksi jika tertulis eksplisit di CV. Kualitas estetika portofolio visual/konten tidak dinilai."],
        ["Waktu Proses:", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["Total Berkas Diproses:", (ranking_data.get("meta") or {}).get("totalProcessed", 0)],
        ["Total Perlu Dicek:", len(review_list)],
        [],
    ]
    for r in summary_meta_rows:
        ws_summary.append([sanitize_excel_cell(x) for x in r])
    ws_summary.cell(row=1, column=1).font = Font(name="Calibri", size=14, bold=True, color="1E3A8A")

    for div_name, profile in profiles_by_division.items():
        if not profile:
            continue
        title_str = sanitize_excel_cell(profile.get("title") or "")
        ws_summary.append([sanitize_excel_cell(f"DIVISI: {str(div_name).upper()} - {title_str}")])
        header_row = ws_summary.max_row
        ws_summary.cell(row=header_row, column=1).font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
        ws_summary.cell(row=header_row, column=1).fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        ws_summary.merge_cells(start_row=header_row, start_column=1, end_row=header_row, end_column=2)

        jd_text = str(profile.get("jd") or "")
        jd_preview = jd_text[:200] + ("..." if len(jd_text) > 200 else "")
        ws_summary.append([sanitize_excel_cell("Deskripsi JD Singkat:"), sanitize_excel_cell(jd_preview)])
        
        # Hard Requirements
        hard_req = profile.get("hardRequirements") or {}
        hard_desc = []
        if isinstance(hard_req, dict):
            if hard_req.get("minGpa"):
                hard_desc.append(f"Min IPK: {hard_req.get('minGpa')}")
            if hard_req.get("allowedMajors"):
                majors = hard_req.get("allowedMajors")
                if isinstance(majors, list):
                    hard_desc.append(f"Jurusan: {', '.join(str(m) for m in majors)}")
                else:
                    hard_desc.append(f"Jurusan: {str(majors)}")
            if hard_req.get("mandatorySkills"):
                ms = hard_req.get("mandatorySkills") or {}
                if isinstance(ms, dict):
                    items = ms.get("items") or []
                    rule_str = ms.get("rule") or "all"
                    hard_desc.append(f"Skill Wajib ({rule_str}): {', '.join(str(i) for i in items)}")
        ws_summary.append([sanitize_excel_cell("Syarat Wajib (Hard Req):"), sanitize_excel_cell(" | ".join(hard_desc) if hard_desc else "Tidak ada syarat wajib")])

        # Bobot Kategori
        weights_desc = []
        categories = profile.get("categories") or {}
        if isinstance(categories, dict):
            for ck, cv in categories.items():
                if isinstance(cv, dict) and cv.get("active"):
                    weights_desc.append(f"{cv.get('label', ck)}: {cv.get('weight', 0)}%")
        ws_summary.append([sanitize_excel_cell("Bobot Kategori Aktif:"), sanitize_excel_cell(" | ".join(weights_desc))])

        # Metode Fit IDF
        meta_dict = ranking_data.get("meta") or {}
        fit_dict = meta_dict.get("fitMethods") or {}
        fit_method = fit_dict.get(div_name, "Fit korpus batch")
        ws_summary.append([sanitize_excel_cell("Metode TF-IDF Fit:"), sanitize_excel_cell(fit_method)])

        cand_list = division_results.get(div_name) or []
        ws_summary.append([sanitize_excel_cell("Jumlah Pelamar Dinilai:"), len(cand_list)])
        ws_summary.append([])

    ws_summary.column_dimensions["A"].width = 28
    ws_summary.column_dimensions["B"].width = 75

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
