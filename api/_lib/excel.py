"""
Modul pembuatan berkas Excel (.xlsx) dengan openpyxl.
Menghasilkan 4 sheet: Ranking, Perbandingan Pilihan 1 & 2, Perlu Dicek, dan Ringkasan Lowongan.
Menerapkan mitigasi formula injection, sanitasi karakter kontrol XML, freeze panes, auto-filter,
format angka & hyperlink interaktif, zebra striping, dan styling HR berstandar eksekutif.
"""

import io
import re
import datetime
from typing import Dict, Any, List, Optional
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

try:
    from _lib.extract import clean_campus_name
except ImportError:
    try:
        from api._lib.extract import clean_campus_name
    except ImportError:
        clean_campus_name = None


def sanitize_excel_cell(val: Any) -> Any:
    """
    1. Mitigasi Karakter Ilegal XML di openpyxl:
       Bersihkan karakter kontrol non-printable (ASCII 0-8, 11-12, 14-31)
       yang sering terbawa dari ekstraksi PDF teks.
    2. Mitigasi Formula Injection:
       Jika nilai bertipe string dan diawali =, +, -, @, beri awalan tanda petik (')
       agar program spreadsheet mengevaluasinya sebagai teks biasa.
       (Khusus string tanda hubung tunggal '-' dibiarkan apa adanya agar tidak berubah jadi '-).
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
    if s == "-":
        return s
    if s.startswith(("=", "+", "-", "@")):
        s = "'" + s
    return s


def format_candidate_name(raw: Any) -> str:
    """Membersihkan nama pelamar dari ekstensi berkas (.pdf) atau karakter bullet."""
    if not raw:
        return "Tanpa Nama"
    s = str(raw).strip()
    s = re.sub(r"\.(?:pdf|docx?|xlsx?)$", "", s, flags=re.I).strip()
    s = re.sub(r"^[•\-\*\d\.\)\s\uE000-\uF8FF·]+", "", s).strip()
    return s if s else "Tanpa Nama"


def format_campus_display(raw: Any) -> str:
    """
    Memformat nama kampus secara konsisten untuk lembar Excel:
    Membuang bullet points, pipe delimiter, degree text, GPA, tahun,
    dan trailing lokasi kota tanpa memotong nama resmi kampus.
    """
    if not raw or str(raw).strip() in ("", "-", "None"):
        return "-"
    raw_str = str(raw).strip()
    if clean_campus_name:
        cleaned = clean_campus_name(raw_str)
        if cleaned:
            return cleaned
    # Fallback jika modul eksternal tidak tersedia
    s = re.sub(r"^[•\-\*\d\.\)\s\uE000-\uF8FF·]+", "", raw_str).strip()
    parts = re.split(r"\s+[|;—–]\s+|\s+-\s+", s)
    s = parts[0].strip() if parts else s
    s = re.sub(r"\b(?:20[12][0-9]|gpa|ipk|cum laude).*$", "", s, flags=re.I).strip()
    s = re.sub(r"[,:\-–—\s/|]+$", "", s).strip()
    return s if s else "-"


def format_major_display(raw: Any) -> str:
    """
    Mengonversi nama jurusan menjadi Title Case elegan dengan
    akronim standar (DKV, IT, SDM, BBA, CS, AI, UI/UX, S1, D4, D3) tetap kapital.
    """
    if not raw or str(raw).strip() in ("", "-", "None"):
        return "-"
    words = str(raw).strip().split()
    caps = []
    acronyms = {
        "IT", "DKV", "SDM", "BBA", "CS", "AI", "UI", "UX", "UI/UX",
        "S1", "D4", "D3", "D2", "D1", "S2", "S3", "MBA", "BSC", "MSC", "B.ENG", "B.SC"
    }
    for w in words:
        w_clean = w.strip("(),.").upper()
        if w_clean in acronyms:
            prefix = "(" if w.startswith("(") else ""
            suffix = ")" if w.endswith(")") else ""
            caps.append(f"{prefix}{w_clean}{suffix}")
        elif w.lower() in ("dan", "and", "of", "&", "in", "the", "studi"):
            caps.append(w.lower())
        else:
            caps.append(w.capitalize())
    result = " ".join(caps).strip()
    return result if result else "-"


def format_gpa_display(val: Any) -> Any:
    """Mengembalikan nilai IPK dalam format float 2 desimal atau '-' jika tidak ada."""
    if val is None or str(val).strip() in ("", "-", "None"):
        return "-"
    try:
        f_val = float(val)
        if 0.0 <= f_val <= 5.0:
            return round(f_val, 2)
    except (ValueError, TypeError):
        pass
    return "-"


def format_phone_display(val: Any) -> str:
    """Membersihkan nomor HP dan memastikan tersimpan sebagai teks murni."""
    if not val or str(val).strip() in ("", "-", "None"):
        return "-"
    s = str(val).strip()
    # Jika diawali '+', beri awalan "'" agar Excel tidak menganggap formula
    if s.startswith("+"):
        return f"'{s}"
    return s


def format_skills_display(skills: Any) -> str:
    """Memformat daftar kompetensi menjadi string terpisah koma."""
    if not skills or not isinstance(skills, (list, tuple)):
        return "-"
    items = [str(sk).strip() for sk in skills if sk and str(sk).strip()]
    return ", ".join(items) if items else "-"


def format_experiences_display(experiences: Any) -> str:
    """
    Memformat pengalaman kandidat menjadi baris-baris ber-bullet (\n)
    agar terbaca rapi di dalam sel dengan wrap text aktif.
    """
    if not experiences or not isinstance(experiences, (list, tuple)):
        return "-"
    lines = []
    for exp in experiences:
        if isinstance(exp, dict):
            t = exp.get("type") or "kerja/magang"
            title = exp.get("title") or exp.get("role") or ""
            dur = exp.get("durationMonths", 0)
            dur_str = f" ({dur} bln)" if dur else ""
            lines.append(f"• [{t}] {title}{dur_str}")
        elif isinstance(exp, str) and exp.strip():
            lines.append(f"• {exp.strip()}")
    return "\n".join(lines) if lines else "-"


def format_projects_display(projects: Any) -> str:
    """Memformat daftar proyek menjadi baris-baris ber-bullet (\n)."""
    if not projects or not isinstance(projects, (list, tuple)):
        return "-"
    lines = []
    for p in projects:
        if isinstance(p, dict):
            title = str(p.get("title") or "").strip()
            if title:
                lines.append(f"• {title}")
        elif isinstance(p, str) and p.strip():
            lines.append(f"• {p.strip()}")
    return "\n".join(lines) if lines else "-"


def format_certs_display(certs: Any) -> str:
    """Memformat sertifikasi menjadi baris-baris ber-bullet (\n)."""
    if not certs or not isinstance(certs, (list, tuple)):
        return "-"
    lines = []
    for c in certs:
        if isinstance(c, dict):
            name = str(c.get("title") or c.get("name") or "").strip()
            if name:
                lines.append(f"• {name}")
        elif isinstance(c, str) and c.strip():
            lines.append(f"• {c.strip()}")
    return "\n".join(lines) if lines else "-"


def format_portfolio_display(links: Any) -> str:
    """Memformat daftar tautan portofolio menjadi baris terpisah (\n)."""
    if not links or not isinstance(links, (list, tuple)):
        return "-"
    items = [f"• {str(l).strip()}" for l in links if l and str(l).strip()]
    return "\n".join(items) if items else "-"


def format_ai_eval_display(ai_eval: Any) -> str:
    """
    Menata hasil evaluasi AI (Gemini) secara komprehensif, terstruktur,
    dan mudah dibaca oleh rekruter dengan pemisah baris (\n).
    """
    if not ai_eval or not isinstance(ai_eval, dict):
        return "-"

    model = ai_eval.get("modelUsed") or "Gemini"
    level = ai_eval.get("practicalLevel") or "Dasar"
    score = ai_eval.get("contextualScore", "-")

    parts = [f"[{model} | {level} | Skor {score}]"]

    summary = ai_eval.get("executiveSummary")
    if summary:
        parts.append(f"• Ringkasan Eksekutif: {summary}")

    strength = ai_eval.get("keyStrength")
    if strength:
        parts.append(f"• Keunggulan Utama: {strength}")

    strengths = ai_eval.get("strengths") or []
    if strengths:
        parts.append(f"• Bukti Kekuatan: {', '.join(str(s) for s in strengths)}")

    areas = ai_eval.get("areasToProbe") or []
    if areas:
        parts.append(f"• Catatan Wawancara: {', '.join(str(a) for a in areas)}")

    question = ai_eval.get("interviewQuestion")
    if question:
        parts.append(f"• Pertanyaan Validasi: {question}")

    return "\n".join(parts) if parts else "-"


def set_drive_link_cell(cell, url: Any):
    """Menjadikan tautan Google Drive sebagai hyperlink interaktif berwarna biru bergaris bawah."""
    url_str = str(url or "").strip()
    if url_str.startswith(("http://", "https://")):
        cell.value = url_str
        cell.hyperlink = url_str
        cell.font = Font(name="Calibri", size=10, color="1D4ED8", underline="single")
        cell.alignment = Alignment(horizontal="left", vertical="center")
    else:
        cell.value = "-"
        cell.alignment = Alignment(horizontal="center", vertical="center")


def style_header_row(ws, row_idx: int, col_count: int, fill_color: str = "1E293B"):
    """Memberikan format baris header tebal, tinggi 28pt, latar solid, dan teks putih di tengah."""
    ws.row_dimensions[row_idx].height = 28.0
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
    align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col in range(1, col_count + 1):
        cell = ws.cell(row=row_idx, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align


def apply_column_widths(ws, width_map: Dict[int, int]):
    """Mengatur lebar kolom secara eksplisit sesuai pemetaan per sheet."""
    for col_idx, width in width_map.items():
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width


def generate_screening_excel(
    ranking_data: Dict[str, Any],
    profiles_by_division: Dict[str, Dict[str, Any]]
) -> bytes:
    """
    Membuat berkas spreadsheet Excel 4 sheet berstandar HR:
    1. Ranking (Peringkat per divisi lengkap dengan detail kandidat, skor, dan evaluasi AI)
    2. Perbandingan Pilihan 1 & 2 (Master kandidat dan analisis komparasi pilihan divisi)
    3. Perlu Dicek (Log audit kandidat berkas scan, IPK ambigu, akses Drive, dsb.)
    4. Ringkasan Lowongan (Metadata screening, kriteria lowongan, dan konfigurasi bobot)
    """
    wb = Workbook()

    # Border data halus
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    # Status fills dan fonts untuk konsistensi HR
    status_styles = {
        "Memenuhi": {
            "fill": PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid"),
            "font": Font(name="Calibri", size=10, bold=True, color="166534"),
        },
        "Perlu dicek": {
            "fill": PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid"),
            "font": Font(name="Calibri", size=10, bold=True, color="92400E"),
        },
        "Tidak memenuhi": {
            "fill": PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid"),
            "font": Font(name="Calibri", size=10, bold=True, color="991B1B"),
        },
        "Tidak ada syarat wajib": {
            "fill": PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid"),
            "font": Font(name="Calibri", size=10, color="475569"),
        },
    }

    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    division_results = ranking_data.get("divisionResults", {}) or {}

    # Peta indeks kandidat lintas divisi
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
        "Evaluasi AI (Gemini)",
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

    for div_name, candidates in division_results.items():
        if not candidates:
            continue
        for cand in candidates:
            if not cand:
                continue

            cand_key = cand.get("fileId") or cand.get("email") or str(cand.get("sourceRowIndex") or "")
            peer_map = candidates_by_key.get(cand_key, {})

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

            # Format data terstruktur
            name_str = format_candidate_name(cand.get("name"))
            campus_str = format_campus_display(cand.get("university"))
            major_str = format_major_display(cand.get("major"))
            gpa_val = format_gpa_display(cand.get("gpa"))
            phone_str = format_phone_display(cand.get("phone"))
            skills_str = format_skills_display(cand.get("skillsFound"))
            exp_str = format_experiences_display(cand.get("experiences"))
            proj_str = format_projects_display(cand.get("projects"))
            cert_str = format_certs_display(cand.get("certifications"))
            port_str = format_portfolio_display(cand.get("portfolioLinks"))

            cat_scores = cand.get("categoryScores") or {}
            exp_score = round(float(cat_scores.get("experience", 0.0)), 1)
            proj_score = round(float(cat_scores.get("projects", 0.0)), 1)
            cert_score = round(float(cat_scores.get("cert_edu", 0.0)), 1)
            comp_score = round(float(cat_scores.get("competencies", 0.0)), 1)
            final_score = round(float(cand.get("finalScore", 0.0)), 1)

            p1_score = c1.get("finalScore")
            p1_score_str = f"{p1_score:.1f}" if isinstance(p1_score, (int, float)) else str(p1_score or "-")
            p1_str = f"{c1.get('division', p1_name)} ({p1_score_str})" if (c1 and p1_name) else "-"

            p2_score = c2.get("finalScore")
            p2_score_str = f"{p2_score:.1f}" if isinstance(p2_score, (int, float)) else str(p2_score or "-")
            p2_str = f"{c2.get('division', p2_name)} ({p2_score_str})" if (c2 and p2_name) else "-"

            rec_note = cand.get("recommendationNote") or cand.get("multiDivisionNote") or "-"
            ai_eval_text = format_ai_eval_display(cand.get("aiEvaluation"))

            rank_val = cand.get("rank") or (current_row - 1)

            row_data = [
                div_name,
                rank_val,
                choice_rank_str,
                name_str,
                cand.get("email") or "-",
                phone_str,
                campus_str,
                major_str,
                gpa_val,
                cand.get("graduationYearOrSemester") or "-",
                skills_str,
                exp_str,
                proj_str,
                cert_str,
                port_str,
                exp_score,
                proj_score,
                cert_score,
                comp_score,
                final_score,
                cand.get("hardRequirementStatus") or "Tidak ada syarat wajib",
                ai_eval_text,
                p1_str,
                p2_str,
                rec_note,
                cand.get("reasons") or "-",
                cand.get("multiDivisionNote") or "-",
                cand.get("driveLink") or "-",
            ]

            ws_rank.append([sanitize_excel_cell(x) for x in row_data])
            ws_rank.row_dimensions[current_row].height = 22.0

            # Zebra striping untuk baris genap
            is_even_row = (current_row % 2 == 0)

            for col_idx in range(1, len(row_data) + 1):
                cell = ws_rank.cell(row=current_row, column=col_idx)
                cell.border = thin_border
                if is_even_row:
                    cell.fill = zebra_fill

            # Styling spesifik kolom
            ws_rank.cell(row=current_row, column=1).alignment = Alignment(horizontal="center", vertical="center")
            
            # Peringkat
            rank_cell = ws_rank.cell(row=current_row, column=2)
            rank_cell.alignment = Alignment(horizontal="center", vertical="center")
            rank_cell.font = Font(name="Calibri", size=11, bold=True)
            rank_cell.number_format = '0'

            # Pilihan Ke-
            ws_rank.cell(row=current_row, column=3).alignment = Alignment(horizontal="center", vertical="center")

            # Nama Pelamar
            name_cell = ws_rank.cell(row=current_row, column=4)
            name_cell.font = Font(name="Calibri", size=11, bold=True, color="0F172A")
            name_cell.alignment = Alignment(horizontal="left", vertical="center")

            # No. HP
            phone_cell = ws_rank.cell(row=current_row, column=6)
            phone_cell.alignment = Alignment(horizontal="center", vertical="center")
            phone_cell.number_format = '@'

            # Kampus & Jurusan
            ws_rank.cell(row=current_row, column=7).alignment = Alignment(horizontal="left", vertical="center")
            ws_rank.cell(row=current_row, column=8).alignment = Alignment(horizontal="left", vertical="center")

            # IPK
            gpa_cell = ws_rank.cell(row=current_row, column=9)
            gpa_cell.alignment = Alignment(horizontal="center", vertical="center")
            if isinstance(gpa_val, (int, float)):
                gpa_cell.number_format = '0.00'

            # Tahun Lulus / Semester
            ws_rank.cell(row=current_row, column=10).alignment = Alignment(horizontal="center", vertical="center")

            # Multiline text wrap: Kompetensi, Pengalaman, Project, Sertifikasi, Portofolio
            for col_i in (11, 12, 13, 14, 15):
                ws_rank.cell(row=current_row, column=col_i).alignment = Alignment(wrap_text=True, vertical="top")

            # Skor Kategori
            for col_i in (16, 17, 18, 19):
                s_cell = ws_rank.cell(row=current_row, column=col_i)
                s_cell.alignment = Alignment(horizontal="right", vertical="center")
                s_cell.number_format = '0.0'

            # Skor Akhir
            final_cell = ws_rank.cell(row=current_row, column=20)
            final_cell.alignment = Alignment(horizontal="right", vertical="center")
            final_cell.font = Font(name="Calibri", size=11, bold=True, color="0F172A")
            final_cell.number_format = '0.0'

            # Status Syarat Wajib
            status_val = cand.get("hardRequirementStatus") or "Tidak ada syarat wajib"
            status_cell = ws_rank.cell(row=current_row, column=21)
            status_cell.alignment = Alignment(horizontal="center", vertical="center")
            if status_val in status_styles:
                status_cell.fill = status_styles[status_val]["fill"]
                status_cell.font = status_styles[status_val]["font"]

            # Evaluasi AI & Rekomendasi (Wrap Text)
            ws_rank.cell(row=current_row, column=22).alignment = Alignment(wrap_text=True, vertical="top")
            ws_rank.cell(row=current_row, column=25).alignment = Alignment(wrap_text=True, vertical="top")
            ws_rank.cell(row=current_row, column=26).alignment = Alignment(wrap_text=True, vertical="top")
            ws_rank.cell(row=current_row, column=27).alignment = Alignment(wrap_text=True, vertical="top")

            # Link CV Drive interaktif
            set_drive_link_cell(ws_rank.cell(row=current_row, column=28), cand.get("driveLink"))

            current_row += 1

    ws_rank.freeze_panes = "A2"
    ws_rank.auto_filter.ref = f"A1:{get_column_letter(len(rank_headers))}{max(current_row - 1, 1)}"

    rank_widths = {
        1: 18, 2: 12, 3: 14, 4: 26, 5: 28, 6: 18, 7: 32, 8: 28, 9: 10,
        10: 22, 11: 35, 12: 42, 13: 36, 14: 30, 15: 32, 16: 16, 17: 15,
        18: 16, 19: 16, 20: 15, 21: 22, 22: 55, 23: 25, 24: 25, 25: 35,
        26: 45, 27: 30, 28: 38
    }
    apply_column_widths(ws_rank, rank_widths)

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
            p1_score_val = round(float(p1_score), 1) if isinstance(p1_score, (int, float)) else None
            p1_status = c1.get("hardRequirementStatus", "-") if c1 else "-"

            p2_score = c2.get("finalScore")
            p2_score_val = round(float(p2_score), 1) if isinstance(p2_score, (int, float)) else None
            p2_status = c2.get("hardRequirementStatus", "-") if c2 else "-"

            best_fit = cand.get("bestFitChoice")
            if not best_fit:
                if c1 and c2 and isinstance(p1_score, (int, float)) and isinstance(p2_score, (int, float)):
                    best_fit = 2 if p2_score > p1_score else 1
                else:
                    best_fit = 1

            best_label = f"Pilihan {best_fit}" if best_fit in [1, 2] else ("Berimbang" if best_fit == "equal" else "Pilihan 1")
            rec_note = cand.get("recommendationNote") or cand.get("multiDivisionNote") or "-"

            name_str = format_candidate_name(cand.get("name"))
            campus_str = format_campus_display(cand.get("university"))
            major_str = format_major_display(cand.get("major"))
            gpa_val = format_gpa_display(cand.get("gpa"))
            phone_str = format_phone_display(cand.get("phone"))

            comp_data = [
                comp_idx,
                name_str,
                cand.get("email") or "-",
                phone_str,
                campus_str,
                major_str,
                gpa_val,
                p1_name or "-",
                p1_score_val if p1_score_val is not None else "-",
                p1_status,
                p2_name or "-",
                p2_score_val if p2_score_val is not None else "-",
                p2_status,
                best_label,
                rec_note,
                cand.get("driveLink") or "-",
            ]
            ws_compare.append([sanitize_excel_cell(x) for x in comp_data])
            ws_compare.row_dimensions[comp_row].height = 22.0

            is_even = (comp_row % 2 == 0)
            for c_i in range(1, len(comp_data) + 1):
                cell = ws_compare.cell(row=comp_row, column=c_i)
                cell.border = thin_border
                if is_even:
                    cell.fill = zebra_fill

            # Formatting kolom Sheet 2
            ws_compare.cell(row=comp_row, column=1).alignment = Alignment(horizontal="center", vertical="center")
            ws_compare.cell(row=comp_row, column=2).font = Font(name="Calibri", size=11, bold=True, color="0F172A")
            ws_compare.cell(row=comp_row, column=4).alignment = Alignment(horizontal="center", vertical="center")
            ws_compare.cell(row=comp_row, column=4).number_format = '@'

            # IPK
            gpa_c = ws_compare.cell(row=comp_row, column=7)
            gpa_c.alignment = Alignment(horizontal="center", vertical="center")
            if isinstance(gpa_val, (int, float)):
                gpa_c.number_format = '0.00'

            # Skor P1
            s1_cell = ws_compare.cell(row=comp_row, column=9)
            s1_cell.alignment = Alignment(horizontal="right", vertical="center")
            if p1_score_val is not None:
                s1_cell.number_format = '0.0'

            # Status P1
            p1_cell = ws_compare.cell(row=comp_row, column=10)
            p1_cell.alignment = Alignment(horizontal="center", vertical="center")
            if p1_status in status_styles:
                p1_cell.fill = status_styles[p1_status]["fill"]
                p1_cell.font = status_styles[p1_status]["font"]

            # Skor P2
            s2_cell = ws_compare.cell(row=comp_row, column=12)
            s2_cell.alignment = Alignment(horizontal="right", vertical="center")
            if p2_score_val is not None:
                s2_cell.number_format = '0.0'

            # Status P2
            p2_cell = ws_compare.cell(row=comp_row, column=13)
            p2_cell.alignment = Alignment(horizontal="center", vertical="center")
            if p2_status in status_styles:
                p2_cell.fill = status_styles[p2_status]["fill"]
                p2_cell.font = status_styles[p2_status]["font"]

            # Rekomendasi
            best_cell = ws_compare.cell(row=comp_row, column=14)
            best_cell.alignment = Alignment(horizontal="center", vertical="center")
            best_cell.font = Font(name="Calibri", size=10, bold=True)

            ws_compare.cell(row=comp_row, column=15).alignment = Alignment(wrap_text=True, vertical="top")

            # Link Drive interaktif
            set_drive_link_cell(ws_compare.cell(row=comp_row, column=16), cand.get("driveLink"))

            comp_row += 1
            comp_idx += 1

    ws_compare.freeze_panes = "A2"
    ws_compare.auto_filter.ref = f"A1:{get_column_letter(len(compare_headers))}{max(comp_row - 1, 1)}"

    compare_widths = {
        1: 8, 2: 26, 3: 28, 4: 18, 5: 32, 6: 28, 7: 10,
        8: 22, 9: 15, 10: 20, 11: 22, 12: 15, 13: 20,
        14: 22, 15: 45, 16: 38
    }
    apply_column_widths(ws_compare, compare_widths)

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
            format_candidate_name(item.get("name")),
            item.get("division") or "-",
            item.get("issueType") or "-",
            item.get("suggestedAction") or "-",
            item.get("driveLink") or "-",
        ]
        ws_review.append([sanitize_excel_cell(x) for x in rev_data])
        ws_review.row_dimensions[rev_row].height = 22.0

        is_even = (rev_row % 2 == 0)
        for c in range(1, len(rev_data) + 1):
            cell = ws_review.cell(row=rev_row, column=c)
            cell.border = thin_border
            if is_even:
                cell.fill = zebra_fill

        ws_review.cell(row=rev_row, column=1).alignment = Alignment(horizontal="center", vertical="center")
        ws_review.cell(row=rev_row, column=2).font = Font(name="Calibri", size=11, bold=True, color="0F172A")
        ws_review.cell(row=rev_row, column=4).font = Font(name="Calibri", size=10, bold=True, color="B45309")
        ws_review.cell(row=rev_row, column=5).alignment = Alignment(wrap_text=True, vertical="top")

        # Link Drive interaktif
        set_drive_link_cell(ws_review.cell(row=rev_row, column=6), item.get("driveLink"))

        rev_row += 1

    ws_review.freeze_panes = "A2"
    ws_review.auto_filter.ref = f"A1:{get_column_letter(len(review_headers))}{max(rev_row - 1, 1)}"

    review_widths = {
        1: 14, 2: 26, 3: 22, 4: 30, 5: 60, 6: 38
    }
    apply_column_widths(ws_review, review_widths)

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
    ws_summary.row_dimensions[1].height = 28.0

    for r_idx in range(2, 8):
        ws_summary.cell(row=r_idx, column=1).font = Font(name="Calibri", size=10, bold=True, color="334155")
        ws_summary.cell(row=r_idx, column=2).font = Font(name="Calibri", size=10, color="0F172A")
        ws_summary.row_dimensions[r_idx].height = 20.0

    for div_name, profile in profiles_by_division.items():
        if not profile:
            continue
        title_str = sanitize_excel_cell(profile.get("title") or "")
        ws_summary.append([sanitize_excel_cell(f"DIVISI: {str(div_name).upper()} - {title_str}")])
        header_row = ws_summary.max_row
        ws_summary.row_dimensions[header_row].height = 24.0
        ws_summary.cell(row=header_row, column=1).font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        ws_summary.cell(row=header_row, column=1).fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        ws_summary.merge_cells(start_row=header_row, start_column=1, end_row=header_row, end_column=2)

        jd_text = str(profile.get("jd") or "")
        jd_preview = jd_text[:250] + ("..." if len(jd_text) > 250 else "")
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
    ws_summary.column_dimensions["B"].width = 85

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
