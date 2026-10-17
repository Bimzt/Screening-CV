"""
Modul parsing dokumen CV (PDF dan DOCX).
Mengekstrak teks dengan memperhatikan tata letak dan mengekstrak tautan (hyperlink).
Mendeteksi apakah dokumen merupakan hasil scan/gambar (karakter < 200).
"""

import io
import re
from typing import Dict, Any, List, Tuple
from pypdf import PdfReader
from docx import Document
from .config import MIN_EXTRACTED_CHARS_FOR_VALID_PDF


def extract_links_from_text(text: str) -> List[str]:
    """
    Mengekstrak URL dari teks biasa menggunakan regex.
    """
    url_pattern = re.compile(
        r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
    )
    matches = url_pattern.findall(text)
    # Bersihkan tanda baca di akhir URL
    cleaned = []
    for m in matches:
        clean_url = m.rstrip(".,;)>]\"'")
        if clean_url not in cleaned:
            cleaned.append(clean_url)
    return cleaned


def extract_from_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Mengekstrak teks dan hyperlink dari berkas PDF menggunakan pypdf.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return {
                    "text": "",
                    "links": [],
                    "is_scan": False,
                    "error": "PDF terenkripsi/memerlukan password",
                }

        page_texts = []
        found_links = set()

        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                page_texts.append(t.strip())

            # Ekstrak anotasi hyperlink di halaman PDF
            if "/Annots" in page:
                try:
                    annots = page["/Annots"]
                    for annot in annots:
                        obj = annot.get_object() if hasattr(annot, "get_object") else annot
                        if isinstance(obj, dict) and obj.get("/Subtype") == "/Link":
                            action = obj.get("/A")
                            if action and hasattr(action, "get_object"):
                                action = action.get_object()
                            if isinstance(action, dict) and "/URI" in action:
                                uri = str(action["/URI"]).strip()
                                if uri.startswith("http://") or uri.startswith("https://"):
                                    found_links.add(uri)
                except Exception:
                    pass

        full_text = "\n\n".join(page_texts).strip()

        # Tambahkan tautan yang ditemukan dari teks
        text_links = extract_links_from_text(full_text)
        for tl in text_links:
            found_links.add(tl)

        char_count = len(full_text.strip())
        is_scan = char_count < MIN_EXTRACTED_CHARS_FOR_VALID_PDF

        return {
            "text": full_text,
            "links": sorted(list(found_links)),
            "is_scan": is_scan,
            "error": "PDF scan/gambar, OCR belum didukung di V1" if is_scan else None,
        }
    except Exception as e:
        return {
            "text": "",
            "links": [],
            "is_scan": False,
            "error": f"Berkas PDF korup atau rusak: {str(e)}",
        }


def extract_from_docx(docx_bytes: bytes) -> Dict[str, Any]:
    """
    Mengekstrak teks dan hyperlink dari berkas DOCX menggunakan python-docx.
    """
    try:
        doc = Document(io.BytesIO(docx_bytes))
        paragraphs = []
        found_links = set()

        # Baca seluruh paragraf
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                paragraphs.append(text)

        # Baca teks di tabel
        for table in doc.tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_texts:
                    paragraphs.append(" | ".join(row_texts))

        # Ekstrak hyperlinks dari relationships dokumen
        try:
            for rel in doc.part.rels.values():
                if "hyperlink" in rel.reltype:
                    target = rel.target_ref
                    if target.startswith("http://") or target.startswith("https://"):
                        found_links.add(target.strip())
        except Exception:
            pass

        full_text = "\n\n".join(paragraphs).strip()

        # Tambahkan tautan dari teks biasa
        text_links = extract_links_from_text(full_text)
        for tl in text_links:
            found_links.add(tl)

        char_count = len(full_text.strip())
        is_scan = char_count < MIN_EXTRACTED_CHARS_FOR_VALID_PDF

        return {
            "text": full_text,
            "links": sorted(list(found_links)),
            "is_scan": is_scan,
            "error": "Dokumen kosong atau teks tidak terbaca" if is_scan else None,
        }
    except Exception as e:
        return {
            "text": "",
            "links": [],
            "is_scan": False,
            "error": f"Berkas DOCX rusak atau tidak valid: {str(e)}",
        }


def parse_cv_document(file_bytes: bytes, mime_type: str, filename: str) -> Dict[str, Any]:
    """
    Mendeteksi tipe berkas dan mengekstrak teks serta tautan dokumen CV.
    """
    mime_lower = mime_type.lower()
    fn_lower = filename.lower()

    if "pdf" in mime_lower or fn_lower.endswith(".pdf"):
        return extract_from_pdf(file_bytes)
    elif (
        "wordprocessingml" in mime_lower
        or "msword" in mime_lower
        or fn_lower.endswith(".docx")
    ):
        return extract_from_docx(file_bytes)
    else:
        return {
            "text": "",
            "links": [],
            "is_scan": False,
            "error": f"Format berkas '{filename}' ({mime_type}) tidak didukung. Harap unggah PDF atau DOCX.",
        }
