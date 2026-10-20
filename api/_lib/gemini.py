"""
Modul Evaluasi Semantik Tier 2 menggunakan Google Gemini AI (REST API).
Menganalisis 10 kandidat teratas per divisi untuk membedakan pengalaman riil
(action verbs, kepemimpinan, kepemilikan proyek) vs klaim kata kunci pasif.
Bekerja secara stateless via REST API (tanpa dependensi berat) dan graceful fallback jika API key belum disetel.
Dilengkapi proteksi timeout & fallback otomatis ke gemini-3.5-flash-lite jika model utama sedang sibuk/503.
"""

import os
import json
import base64
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"
FALLBACK_GEMINI_MODEL = "gemini-3.1-flash-lite"


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Konversi aman nilai skor AI yang mungkin berformat string seperti '85', '85/100', atau '85%'."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val_clean = val.split("/")[0].replace("%", "").strip()
        try:
            return float(val_clean)
        except ValueError:
            return default
    return default


def evaluate_candidates_tier2(
    candidates: List[Dict[str, Any]],
    profile: Dict[str, Any],
    max_candidates: int = 10,
    api_key: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Mengevaluasi hingga max_candidates teratas dalam satu divisi menggunakan Gemini REST API.
    Mencoba model utama (default: gemini-3.8-flash) dengan timeout 3.0 detik, dan jika gagal/503,
    otomatis fallback ke gemini-3.5-flash-lite (~1 detik).
    Mengembalikan dictionary: { fileId: { contextualScore, practicalLevel, executiveSummary, keyStrength } }
    """
    key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not key:
        return {}

    if not candidates:
        return {}

    # Ambil konfigurasi model (default: gemini-3.8-flash)
    model_name = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    if model_name.startswith("models/"):
        model_name = model_name[len("models/"):]

    target_candidates = candidates[:max_candidates]
    div_name = profile.get("division", "Umum")
    div_title = profile.get("title", div_name)
    jd_summary = (profile.get("jd") or "")[:800]

    # Ringkas profil kandidat untuk prompt
    candidate_prompts = []
    for idx, c in enumerate(target_candidates, start=1):
        c_id = str(c.get("fileId") or c.get("email") or c.get("sourceRowIndex") or c.get("rank") or idx)
        name = c.get("name") or c.get("candidateName") or f"Pelamar #{idx}"
        
        # Ringkasan pengalaman
        exp_list = []
        for exp in (c.get("experiences") or [])[:5]:
            if not exp:
                continue
            if isinstance(exp, dict):
                t = exp.get("type", "kerja/magang")
                role = exp.get("title") or exp.get("role") or ""
                dur = exp.get("durationMonths", 0)
                exp_list.append(f"- [{t}] {role} ({dur} bln)")
            elif isinstance(exp, str):
                exp_list.append(f"- {exp[:100]}")
            else:
                exp_list.append(f"- {str(exp)[:100]}")
        exp_text = "\n".join(exp_list) if exp_list else "Tidak ada data pengalaman terstruktur."

        # Ringkasan proyek
        proj_list = []
        for p in (c.get("projects") or [])[:4]:
            if not p:
                continue
            if isinstance(p, dict):
                proj_list.append(f"- {p.get('title', '')}")
            elif isinstance(p, str):
                proj_list.append(f"- {p[:80]}")
            else:
                proj_list.append(f"- {str(p)[:80]}")
        proj_text = "\n".join(proj_list) if proj_list else "Tidak ada data proyek terstruktur."

        # Skills & Sertifikasi
        skills = ", ".join(str(s) for s in (c.get("skillsFound") or []) if s)[:200] or "-"
        
        cert_items = []
        for ct in (c.get("certifications") or []):
            if not ct:
                continue
            if isinstance(ct, dict):
                cert_items.append(str(ct.get("title") or ct.get("name") or ""))
            else:
                cert_items.append(str(ct))
        certs = ", ".join(cert_items)[:200] or "-"

        candidate_prompts.append({
            "candidateId": c_id,
            "name": name,
            "gpa": c.get("gpa"),
            "major": c.get("major"),
            "university": c.get("university"),
            "experiences": exp_text,
            "projects": proj_text,
            "skillsFound": skills,
            "certifications": certs,
        })

    user_prompt = f"""LOWONGAN DIVISI: {div_name} ({div_title})
DESKRIPSI PEKERJAAN (JD):
{jd_summary}

DATA KANDIDAT TERATAS UNTUK DIEVALUASI:
{json.dumps(candidate_prompts, indent=2, ensure_ascii=False)}

INSTRUKSI PENILAIAN KOMPREHENSIF (DETAIL & MENDALAM):
Sebagai Senior Talent Assessor & Recruiting Lead, berikan evaluasi mendalam, objektif, dan jelas (JANGAN TERLALU RINGKAS) untuk setiap kandidat:
- DUKUNGAN DWIBAHASA PENUH: CV kandidat dapat ditulis dalam Bahasa Inggris (English), Bahasa Indonesia, atau campuran keduanya. Nilai secara adil berdasarkan substansi kompetensi dan pengalaman nyata kandidat tanpa bias bahasa. Seluruh teks evaluasi ('executiveSummary', 'keyStrength', 'strengths', 'areasToProbe', 'interviewQuestion') WAJIB disajikan dalam Bahasa Indonesia yang profesional dan tajam.
1. 'contextualScore' (skor angka 0 - 100): evaluasi kesiapan kerja praktis terhadap JD.
2. 'practicalLevel': 'Tinggi' (bukti eksekusi/portofolio kuat), 'Sedang' (ada pengalaman relevan), atau 'Dasar' (hanya kursus/teori/kata kunci).
3. 'executiveSummary': Uraian evaluasi mendalam dan jelas (3 - 5 kalimat komprehensif) yang menjelaskan:
   - Bukti eksekusi nyata dari proyek/pengalaman yang pernah dikerjakan.
   - Relevansi langsung pengalaman tersebut terhadap tanggung jawab utama di Job Description.
   - Kesiapan kandidat untuk langsung bekerja mandiri vs butuh pelatihan awal.
4. 'keyStrength': Uraian 1-2 kalimat tentang keunggulan kompetitif terbesar kandidat dibanding pelamar lain.
5. 'strengths': Array string berisi 2 - 3 poin kekuatan teknis/pengalaman spesifik yang terbukti di CV.
6. 'areasToProbe': Array string berisi 1 - 2 poin catatan atau hal yang perlu dikonfirmasi rekruter saat wawancara.
7. 'interviewQuestion': 1 pertanyaan wawancara teknis/situasional yang paling tajam dan relevan untuk memvalidasi kemampuannya.

Kembalikan HANYA format JSON valid tanpa markdown formatting tambahan dengan struktur:
{{
  "evaluations": [
    {{
      "candidateId": "...",
      "contextualScore": 85,
      "practicalLevel": "Tinggi",
      "executiveSummary": "...",
      "keyStrength": "...",
      "strengths": ["...", "..."],
      "areasToProbe": ["..."],
      "interviewQuestion": "..."
    }}
  ]
}}"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": user_prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    # Daftar model yang dicoba secara berurutan jika terjadi timeout / 503 / 429
    models_to_try = [model_name]
    if model_name != FALLBACK_GEMINI_MODEL:
        models_to_try.append(FALLBACK_GEMINI_MODEL)

    for current_model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={key}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            # Timeout 18.0 detik per request agar cukup waktu untuk respons analisis mendalam dari Gemini
            with urllib.request.urlopen(req, timeout=18.0) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)

            candidates_content = res_json.get("candidates", [])
            if not candidates_content:
                continue

            text_out = candidates_content[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not text_out:
                continue

            raw_text = text_out.strip()
            # Bersihkan format markdown block jika model membungkusnya dalam ```json ... ```
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_text = "\n".join(lines).strip()

            parsed_eval = json.loads(raw_text)
            
            # Dukung baik format {"evaluations": [...]} maupun array langsung [...]
            if isinstance(parsed_eval, list):
                eval_list = parsed_eval
            elif isinstance(parsed_eval, dict):
                eval_list = parsed_eval.get("evaluations", [])
                if not eval_list and "candidates" in parsed_eval:
                    eval_list = parsed_eval.get("candidates", [])
            else:
                eval_list = []

            result_map = {}
            for item_idx, ev in enumerate(eval_list, start=1):
                if not isinstance(ev, dict):
                    continue
                cid = ev.get("candidateId")
                eval_data = {
                    "contextualScore": _safe_float(ev.get("contextualScore", 0)),
                    "practicalLevel": str(ev.get("practicalLevel", "Sedang")),
                    "executiveSummary": str(ev.get("executiveSummary", "")),
                    "keyStrength": str(ev.get("keyStrength", "")),
                    "strengths": [str(s) for s in ev.get("strengths", []) if s],
                    "areasToProbe": [str(a) for a in ev.get("areasToProbe", []) if a],
                    "interviewQuestion": str(ev.get("interviewQuestion", "")),
                    "modelUsed": current_model,
                }
                if cid:
                    result_map[str(cid)] = eval_data
                # Fallback mapping berdasarkan indeks urutan jika LLM mengubah id
                result_map[str(item_idx)] = eval_data
                # Fallback mapping berdasarkan kandidat asal pada urutan yang sama
                if item_idx - 1 < len(target_candidates):
                    orig_cand = target_candidates[item_idx - 1]
                    for alt_key in ["fileId", "email", "sourceRowIndex", "rank", "name"]:
                        val = orig_cand.get(alt_key)
                        if val is not None and str(val):
                            result_map[str(val)] = eval_data

            if result_map:
                return result_map

        except urllib.error.HTTPError as e:
            print(f"[Tier 2 AI Warning] Model {current_model} HTTP {e.code}, mencoba fallback...")
            continue
        except Exception as e:
            print(f"[Tier 2 AI Warning] Model {current_model} gagal ({str(e)}), mencoba fallback...")
            continue

    return {}


def extract_text_via_gemini_vision(
    file_bytes: bytes,
    mime_type: str,
    api_key: Optional[str] = None,
    timeout: int = 25
) -> Optional[str]:
    """
    Mengekstrak seluruh teks dan informasi dari berkas gambar CV (PNG/JPG/WEBP) atau PDF scan
    menggunakan Google Gemini Multimodal Vision API.
    """
    key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not key or not file_bytes:
        return None

    # Normalisasi MIME type untuk input Gemini API
    m = mime_type.lower()
    if "pdf" in m:
        norm_mime = "application/pdf"
    elif "png" in m:
        norm_mime = "image/png"
    elif "webp" in m:
        norm_mime = "image/webp"
    else:
        norm_mime = "image/jpeg"

    b64_data = base64.b64encode(file_bytes).decode("utf-8")

    prompt = (
        "Anda adalah asisten OCR ahli dan sangat teliti untuk berkas CV/Resume rekrutmen kerja.\n"
        "Tugas Anda: Bacalah dokumen/gambar CV ini dan salin SELURUH teks serta informasi di dalamnya secara lengkap dan terstruktur tanpa ada bagian yang terlewat.\n\n"
        "Pastikan mengekstrak seluruh informasi yang tertulis:\n"
        "1. Identitas & Kontak: Nama lengkap, email, nomor HP/WhatsApp, kota domisili, link LinkedIn, GitHub, portofolio, dan media sosial.\n"
        "2. Pendidikan: Nama universitas/institut/sekolah, jenjang (S1/D3/D4/SMA), jurusan/program studi, nilai IPK/GPA (contoh: 3.75), dan tahun kelulusan/semester.\n"
        "3. Pengalaman Kerja / Magang / Organisasi: Nama instansi/perusahaan, posisi/jabatan, durasi/periode kerja (bulan & tahun), serta seluruh uraian tugas dan pencapaian.\n"
        "4. Proyek / Portofolio: Judul proyek, deskripsi, teknologi/tools yang digunakan, serta tautan terkait.\n"
        "5. Keahlian & Tools: Semua skill teknis (hard skills), soft skills, aplikasi/software yang dikuasai, dan bahasa.\n"
        "6. Sertifikasi & Penghargaan: Nama sertifikasi/kursus, lembaga penerbit, dan tahun.\n\n"
        "Salin teks secara akurat dan lengkap sesuai dokumen aslinya. Gunakan heading seksi yang jelas (Pendidikan, Pengalaman, Proyek, Keahlian, Sertifikasi)."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": norm_mime,
                            "data": b64_data
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1
        }
    }

    model_name = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    if model_name.startswith("models/"):
        model_name = model_name[len("models/"):]

    models_to_try = [model_name]
    if FALLBACK_GEMINI_MODEL not in models_to_try:
        models_to_try.append(FALLBACK_GEMINI_MODEL)

    data_json = json.dumps(payload).encode("utf-8")

    for current_model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={key}"
        try:
            req = urllib.request.Request(
                url,
                data=data_json,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_bytes = resp.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))
                candidates = resp_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        extracted = parts[0]["text"].strip()
                        if len(extracted) >= 50:
                            return extracted
        except Exception as e:
            print(f"[Gemini Vision OCR Warning with model {current_model}]: {e}")
            continue

    return None

