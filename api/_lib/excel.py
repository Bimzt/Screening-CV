"""
Modul pembuatan berkas Excel (.xlsx) dengan openpyxl.
Menghasilkan 3 sheet: Ranking, Perlu Dicek, dan Ringkasan Lowongan.
Menerapkan mitigasi formula injection, freeze panes, auto-filter, dan styling HR.
"""

import io
import datetime
from typing import Dict, Any, List
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def sanitize_excel_cell(val: Any) -> Any:
    """
    Mitigasi Formula Injection:
    Jika nilai bertipe string dan diawali =, +, -, @, beri awalan tanda petik (')
    agar program spreadsheet mengevaluasinya sebagai teks biasa.
    """
    if val is None:
        return ""
    if isinstance(val, (int, float)):
        return val
    s = str(val).strip()
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
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
        # Terapkan batas lebar kolom wajar
        limit = max_widths.get(col_idx, 40) if max_widths else 40
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), limit)


def generate_screening_excel(
    ranking_data: Dict[str, Any],
    profiles_by_division: Dict[str, Dict[str, Any]]
) -> bytes:
    """
    Membuat file Excel 3 sheet berstandar HR dengan openpyxl.
    """
    wb = Workbook()
    
    # Border halus untuk data
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    # -------------------------------------------------------------
    # SHEET 1: Ranking
    # -------------------------------------------------------------
    ws_rank = wb.active
    ws_rank.title = "Ranking"
    ws_rank.views.sheetView[0].showGridLines = True

    rank_headers = [
        "Divisi",
        "Peringkat",
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
        "Alasan Penilaian",
        "Catatan Khusus",
        "Link CV Drive",
    ]

    ws_rank.append([sanitize_excel_cell(h) for h in rank_headers])
    style_header_row(ws_rank, 1, len(rank_headers), fill_color="1E3A8A")

    division_results = ranking_data.get("divisionResults", {})
    current_row = 2

    status_fills = {
        "Memenuhi": PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid"),
        "Perlu dicek": PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid"),
        "Tidak memenuhi": PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid"),
        "Tidak ada syarat wajib": PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid"),
    }

    for div_name, candidates in division_results.items():
        for cand in candidates:
            exp_summary_items = []
            for exp in cand.get("experiences", []):
                t = exp.get("type", "kerja/magang")
                exp_summary_items.append(f"[{t}] {exp.get('title')} ({exp.get('durationMonths')} bln)")
            exp_summary = " | ".join(exp_summary_items)

            proj_items = [p.get("title", "") for p in cand.get("projects", [])]
            proj_summary = " | ".join(proj_items)

            cert_summary = " | ".join(cand.get("certifications", []))
            port_links = " | ".join(cand.get("portfolioLinks", []))
            skills_found = ", ".join(cand.get("skillsFound", []))

            cat_scores = cand.get("categoryScores", {})

            row_data = [
                sanitize_excel_cell(cand.get("division")),
                cand.get("rank"),
                sanitize_excel_cell(cand.get("name")),
                sanitize_excel_cell(cand.get("email")),
                sanitize_excel_cell(cand.get("phone")),
                sanitize_excel_cell(cand.get("university")),
                sanitize_excel_cell(cand.get("major")),
                cand.get("gpa") if cand.get("gpa") is not None else "-",
                sanitize_excel_cell(cand.get("graduationYearOrSemester")),
                sanitize_excel_cell(skills_found),
                sanitize_excel_cell(exp_summary),
                sanitize_excel_cell(proj_summary),
                sanitize_excel_cell(cert_summary),
                sanitize_excel_cell(port_links),
                cat_scores.get("experience", 0.0),
                cat_scores.get("projects", 0.0),
                cat_scores.get("cert_edu", 0.0),
                cat_scores.get("competencies", 0.0),
                cand.get("finalScore", 0.0),
                sanitize_excel_cell(cand.get("hardRequirementStatus")),
                sanitize_excel_cell(cand.get("reasons")),
                sanitize_excel_cell(cand.get("multiDivisionNote")),
                sanitize_excel_cell(cand.get("driveLink")),
            ]

            ws_rank.append(row_data)

            # Styling sel data
            status_val = cand.get("hardRequirementStatus")
            status_cell = ws_rank.cell(row=current_row, column=20)
            if status_val in status_fills:
                status_cell.fill = status_fills[status_val]

            # Wrap text untuk kolom alasan (kolom 21)
            reason_cell = ws_rank.cell(row=current_row, column=21)
            reason_cell.alignment = Alignment(wrap_text=True, vertical="top")

            # Border halus
            for c in range(1, len(row_data) + 1):
                ws_rank.cell(row=current_row, column=c).border = thin_border

            current_row += 1

    # Freeze header & Auto filter
    ws_rank.freeze_panes = "A2"
    ws_rank.auto_filter.ref = f"A1:{get_column_letter(len(rank_headers))}{current_row - 1}"
    auto_fit_columns(ws_rank, {21: 50, 11: 45, 12: 35, 14: 30, 23: 35})

    # -------------------------------------------------------------
    # SHEET 2: Perlu Dicek
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

    review_list = ranking_data.get("reviewList", [])
    rev_row = 2
    for item in review_list:
        rev_data = [
            item.get("rowIndex") or "-",
            sanitize_excel_cell(item.get("name")),
            sanitize_excel_cell(item.get("division")),
            sanitize_excel_cell(item.get("issueType")),
            sanitize_excel_cell(item.get("suggestedAction")),
            sanitize_excel_cell(item.get("driveLink")),
        ]
        ws_review.append(rev_data)
        for c in range(1, len(rev_data) + 1):
            cell = ws_review.cell(row=rev_row, column=c)
            cell.border = thin_border
            if c == 5:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        rev_row += 1

    ws_review.freeze_panes = "A2"
    ws_review.auto_filter.ref = f"A1:{get_column_letter(len(review_headers))}{rev_row - 1}"
    auto_fit_columns(ws_review, {5: 60, 4: 30, 6: 35})

    # -------------------------------------------------------------
    # SHEET 3: Ringkasan Lowongan
    # -------------------------------------------------------------
    ws_summary = wb.create_sheet(title="Ringkasan Lowongan")
    ws_summary.views.sheetView[0].showGridLines = True

    ws_summary.append(["RINGKASAN PROSES SCREENING CV - SOKO FINANCIAL"])
    ws_summary.cell(row=1, column=1).font = Font(name="Calibri", size=14, bold=True, color="1E3A8A")

    ws_summary.append(["Keterangan Kerahasiaan:", "RAHASIA - Hanya untuk keperluan rekrutmen internal Soko Financial."])
    ws_summary.append(["Pernyataan Etika:", "Skor adalah alat bantu pengurutan, bukan keputusan otomatis. Rekruter yang menentukan hasil akhir."])
    ws_summary.append(["Keterbatasan Sistem:", "Kompetensi non-teknis hanya terdeteksi jika tertulis eksplisit di CV. Kualitas estetika portofolio visual/konten tidak dinilai."])
    ws_summary.append(["Waktu Proses:", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    ws_summary.append(["Total Berkas Diproses:", ranking_data.get("meta", {}).get("totalProcessed", 0)])
    ws_summary.append(["Total Perlu Dicek:", len(review_list)])
    ws_summary.append([])

    s_row = 9
    for div_name, profile in profiles_by_division.items():
        ws_summary.cell(row=s_row, column=1, value=f"DIVISI: {div_name.upper()} - {profile.get('title', '')}")
        ws_summary.cell(row=s_row, column=1).font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
        ws_summary.cell(row=s_row, column=1).fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        ws_summary.merge_cells(start_row=s_row, start_column=1, end_row=s_row, end_column=2)
        s_row += 1

        jd_preview = (profile.get("jd") or "")[:200] + ("..." if len(profile.get("jd", "")) > 200 else "")
        ws_summary.append(["Deskripsi JD Singkat:", jd_preview])
        
        # Hard Requirements
        hard_req = profile.get("hardRequirements", {})
        hard_desc = []
        if hard_req.get("minGpa"):
            hard_desc.append(f"Min IPK: {hard_req.get('minGpa')}")
        if hard_req.get("allowedMajors"):
            hard_desc.append(f"Jurusan: {', '.join(hard_req.get('allowedMajors'))}")
        if hard_req.get("mandatorySkills"):
            ms = hard_req.get("mandatorySkills", {})
            hard_desc.append(f"Skill Wajib ({ms.get('rule')}): {', '.join(ms.get('items', []))}")
        ws_summary.append(["Syarat Wajib (Hard Req):", " | ".join(hard_desc) if hard_desc else "Tidak ada syarat wajib"])

        # Bobot Kategori
        weights_desc = []
        for ck, cv in profile.get("categories", {}).items():
            if cv.get("active"):
                weights_desc.append(f"{cv.get('label')}: {cv.get('weight')}%")
        ws_summary.append(["Bobot Kategori Aktif:", " | ".join(weights_desc)])

        # Metode Fit IDF
        fit_method = ranking_data.get("meta", {}).get("fitMethods", {}).get(div_name, "Fit korpus batch")
        ws_summary.append(["Metode TF-IDF Fit:", fit_method])

        cand_count = len(division_results.get(div_name, []))
        ws_summary.append(["Jumlah Pelamar Dinilai:", cand_count])
        ws_summary.append([])
        s_row += 7

    ws_summary.column_dimensions["A"].width = 28
    ws_summary.column_dimensions["B"].width = 75

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
