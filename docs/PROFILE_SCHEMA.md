# Spesifikasi Skema Profil Lowongan (PROFILE_SCHEMA.md)

Setiap profil lowongan divisi diekspor dan diimpor sebagai berkas JSON mandiri. Berkas ini adalah **input tidak tepercaya** sehingga divalidasi dengan aturan keamanan ketat.

---

## 1. Aturan Validasi Keamanan
1. **Batas Ukuran Berkas**: Maksimal **200 KB**. Berkas yang lebih besar akan ditolak.
2. **Versi Skema**: Wajib memuat field `"version": "1.0"`.
3. **Penolakan Field Tak Dikenal (Reject Unknown Fields)**: Properti di luar skema akan menyebabkan penolakan impor.
4. **Perlindungan ReDoS (Regular Expression Denial of Service)**: Seluruh teks kompetensi, alias divisi, dan alias jurusan diproses sebagai **teks literal** (`re.escape`), bukan regex pengguna.
5. **Batasan Panjang dan Jumlah**:
   - Nama divisi & judul lowongan: maks 100 karakter.
   - Teks JD: maks 10.000 karakter.
   - Jumlah alias divisi: maks 15 item.
   - Jumlah kompetensi wajib / tambahan: maks 30 item, masing-masing dengan maks 10 alias.

---

## 2. Struktur Skema JSON (Contoh)

```json
{
  "version": "1.0",
  "division": "Data Analyst",
  "divisionAliases": ["da", "data", "business intelligence", "bi"],
  "title": "Data Analyst Intern / Fresh Graduate",
  "jd": "Menganalisis data transaksi, membuat visualisasi dashboard, dan query SQL...",
  "hardRequirements": {
    "mandatorySkills": {
      "items": ["SQL", "Python"],
      "rule": "all",
      "minCount": 2
    },
    "minGpa": 3.0,
    "allowedMajors": ["Teknik Informatika", "Sistem Informasi", "Statistika", "Matematika"]
  },
  "additionalSkills": ["Power BI", "Tableau", "Excel", "ETL"],
  "categories": {
    "experience": {
      "label": "Pengalaman",
      "weight": 35,
      "active": true
    },
    "projects": {
      "label": "Project / Portofolio",
      "weight": 30,
      "active": true
    },
    "cert_edu": {
      "label": "Sertifikasi & Pendidikan",
      "weight": 20,
      "active": true
    },
    "competencies": {
      "label": "Kompetensi",
      "weight": 15,
      "active": true
    }
  },
  "thresholds": {
    "durationMonths": 12,
    "projectsCount": 3
  },
  "customSectionHeadings": ["Karya Analitik", "Portfolio Data"]
}
```
