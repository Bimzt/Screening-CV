# Arsitektur Sistem: CV Screener

Aplikasi internal berbasis web untuk menyaring dan memeringkatkan berkas CV pelamar (level intern / fresh graduate) lintas banyak divisi.

---

## 1. Ikhtisar Arsitektur

```
[ Browser Klien ]
   │
   ├─► 1. Login (Shared Password -> Session Cookie HMAC)
   ├─► 2. Olah Profil JSON (Validasi skema, simpan lokal)
   ├─► 3. Parse CSV respons Form (Papa Parse, pemetaan kolom & divisi)
   ├─► 4. Antrean Konkurensi (Pool 4 worker paralel)
   │     ├─► POST /api/process (per CV: Drive API -> Ekstraksi teks & seksi)
   │     └─► Simpan parsial ke IndexedDB browser
   ├─► 5. POST /api/rank (Batch rank: Grouping per divisi -> TF-IDF + Hard Req)
   └─► 6. POST /api/export -> Unduh file Excel (openpyxl, 3 sheet)
```

---

## 2. Komponen Utama

### A. Frontend (Next.js App Router + TypeScript + Tailwind CSS)
- **Halaman `/login`**: Antarmuka otentikasi tim rekrutmen.
- **Route `/auth/login` & `/auth/logout`**: Mengelola penerbitan dan penghapusan session cookie bertanda tangan HMAC.
- **Proxy / Middleware (`proxy.ts`)**: Memproteksi rute privat dan memastikan hanya pengguna dengan sesi valid yang dapat mengakses dashboard (sesuai konvensi Next.js 16).
- **Halaman Utama (`/`)**: Satu alur terpadu yang memandu rekruter mulai dari impor/edit profil lowongan, unggah dan pemetaan CSV, pemrosesan batch CV, hingga pratinjau ranking interaktif dan pengunduhan Excel.
- **Client Concurrency Pool (`lib/pool.ts`)**: Menjalankan pemrosesan CV dengan konkurensi 4 request simultan, menyediakan indikator progres real-time, estimasi waktu, dan tombol pembatalan.

### B. Backend Python Serverless (Vercel Functions)
- Berada di direktori root `/api/` dan runtime `@vercel/python`:
  - `POST /api/process`: Menerima `{ fileId }`, mengunduh berkas dari Google Drive via Service Account, mengekstrak teks PDF/DOCX, mendeteksi scan, dan mengekstrak field/seksi.
  - `POST /api/rank`: Mengelompokkan kandidat per divisi, menghitung kemiripan TF-IDF (unigram + bigram) terhadap teks JD, mengevaluasi hard requirement, menghitung skor kategori dan skor akhir, serta menyusun alasan penilaian.
  - `POST /api/export`: Mengonversi hasil pemeringkatan menjadi berkas Excel `.xlsx` dengan sheet rekapitulasi, detail pelamar, dan perbandingan pilihan 1 & 2 berstandar HR.
- Modul bersama di `api/_lib/`:
  - `config.py`: Seluruh konstanta dan batas sistem.
  - `auth.py`: Verifikasi HMAC session cookie dan header CSRF secara mandiri.
  - `drive.py`: Klien Google Drive API (Service Account, read-only, exponential backoff).
  - `parsing.py`: Ekstraksi teks PDF (`pypdf`) dan DOCX (`python-docx`).
  - `sections.py`: Segmentasi heading teks multibahasa (Indonesia / Inggris).
  - `extract.py`: Ekstraksi data terstruktur (IPK, kontak, kampus, skill, pengalaman).
  - `scoring.py`: TF-IDF vectorizer, cosine similarity, evaluasi hard requirements, dan formulasi skor.
  - `excel.py`: Pembuatan lembar kerja Excel 3 sheet dengan perlindungan formula injection.

---

## 3. Prinsip Tanpa Database (Zero Server-Side Storage)
- Server **sama sekali tidak menyimpan** berkas CV, teks hasil ekstraksi, maupun data pribadi kandidat di basis data atau filesystem persisten.
- Semua state sementara selama proses screening disimpan di **IndexedDB browser lokal milik rekruter** dan dapat dibersihkan kapan saja lewat tombol "Hapus data lokal".
- Hasil akhir langsung diunduh ke komputer rekruter sebagai berkas Excel `.xlsx`.
