"""
Modul Evaluasi Semantik Tier 2 menggunakan Google Gemini AI (REST API).
Menganalisis 10 kandidat teratas per divisi untuk membedakan pengalaman riil
(action verbs, kepemimpinan, kepemilikan proyek) vs klaim kata kunci pasif.
Bekerja secara stateless via REST API (tanpa dependensi berat) dan graceful fallback jika API key belum disetel.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from .config import MAX_SECTION_TEXT_CHARS

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")


def evaluate_candidates_tier2(
    candidates: List[Dict[str, Any]],
    profile: Dict[str, Any],
    max_candidates: int = 10,
    api_key: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Mengevaluasi hingga max_candidates teratas dalam satu divisi menggunakan Gemini Flash.
    Mengembalikan dictionary: { fileId: { contextualScore, practicalLevel, executiveSummary, keyStrength } }
    Jika GEMINI_API_KEY tidak disetel atau terjadi error koneksi, mengembalikan dict kosong secara graceful.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        return {}

    if not candidates:
        return {}

    target_candidates = candidates[:max_candidates]
    div_name = profile.get("division", "Umum")
    div_title = profile.get("title", div_name)
    jd_summary = (profile.get("jd") or "")[:800]

    # Ringkas profil kandidat untuk prompt
    candidate_prompts = []
    for idx, c in enumerate(target_candidates, start=1):
        c_id = c.get("fileId") or c.get("email") or str(c.get("sourceRowIndex") or idx)
        name = c.get("name") or c.get("candidateName") or f"Pelamar #{idx}"
        
        # Ringkasan pengalaman
        exp_list = []
        for exp in (c.get("experiences") or [])[:5]:
            if isinstance(exp, dict):
                t = exp.get("type", "kerja/magang")
                role = exp.get("title") or exp.get("role") or ""
                dur = exp.get("durationMonths", 0)
                exp_list.append(f"- [{t}] {role} ({dur} bln)")
            elif isinstance(exp, str):
                exp_list.append(f"- {exp[:100]}")
        exp_text = "\n".join(exp_list) if exp_list else "Tidak ada data pengalaman terstruktur."

        # Ringkasan proyek
        proj_list = []
        for p in (c.get("projects") or [])[:4]:
            if isinstance(p, dict):
                proj_list.append(f"- {p.get('title', '')}")
            elif isinstance(p, str):
                proj_list.append(f"- {p[:80]}")
        proj_text = "\n".join(proj_list) if proj_list else "Tidak ada data proyek terstruktur."

        # Skills & Sertifikasi
        skills = ", ".join(c.get("skillsFound") or [])[:200] or "-"
        certs = ", ".join(str(ct.get("title") if isinstance(ct, dict) else ct) for ct in (c.get("certifications") or []))[:200] or "-"

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

    system_instruction = (
        "Anda adalah Senior HR Talent Assessor & Recruiting Lead. "
        "Tugas Anda adalah menilai secara kritis dan objektif kedalaman pengalaman riil pelamar kerja "
        "dibandingkan dengan Job Description. Bedakan pelamar yang memiliki rekam jejak praktis nyata "
        "(memimpin, merancang, mengimplementasikan, eksekusi mandiri) vs pelamar yang hanya mencantumkan kata kunci / teori dasar."
    )

    user_prompt = f"""LOWONGAN DIVISI: {div_name} ({div_title})
DESKRIPSI PEKERJAAN (JD):
{jd_summary}

DATA KANDIDAT TERATAS UNTUK DIEVALUASI:
{json.dumps(candidate_prompts, indent=2, ensure_ascii=False)}

INSTRUKSI PENILAIAN:
Untuk setiap kandidat di atas, berikan evaluasi:
1. 'contextualScore' (skor angka 0 - 100): nilai kedalaman kontekstual dan kesiapan kerja riil.
2. 'practicalLevel': 'Tinggi' (bukti eksekusi/portofolio kuat), 'Sedang' (ada pengalaman relevan), atau 'Dasar' (hanya kursus/teori/kata kunci).
3. 'executiveSummary': 1-2 kalimat padat untuk rekruter yang menjelaskan kekuatan riil dan potensi catatan kandidat.
4. 'keyStrength': 3-5 kata tentang keunggulan terbesar kandidat.

Kembalikan HANYA format JSON valid tanpa markdown formatting tambahan dengan struktur:
{{
  "evaluations": [
    {{
      "candidateId": "...",
      "contextualScore": 85,
      "practicalLevel": "Tinggi",
      "executiveSummary": "...",
      "keyStrength": "..."
    }}
  ]
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
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

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)

        candidates_content = res_json.get("candidates", [])
        if not candidates_content:
            return {}

        text_out = candidates_content[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text_out:
            return {}

        parsed_eval = json.loads(text_out)
        eval_list = parsed_eval.get("evaluations", [])

        result_map = {}
        for ev in eval_list:
            cid = ev.get("candidateId")
            if cid:
                result_map[str(cid)] = {
                    "contextualScore": float(ev.get("contextualScore", 0)),
                    "practicalLevel": str(ev.get("practicalLevel", "Sedang")),
                    "executiveSummary": str(ev.get("executiveSummary", "")),
                    "keyStrength": str(ev.get("keyStrength", "")),
                }

        return result_map
    except Exception as e:
        # Fallback gracefully jika timeout atau quota limit tercapai
        print(f"[Tier 2 AI Evaluation Warning] Gagal mengevaluasi via Gemini: {str(e)}")
        return {}
