# Catatan Keputusan Arsitektur & Desain (DECISIONS.md)

Dokumen ini mencatat keputusan teknis, asumsi, dan hasil investigasi untuk aplikasi **CV Screener**.

---

## 1. Lingkungan Runtime Vercel: Next.js + Python Serverless

### Hasil Pengecekan Dokumentasi & Batasan Vercel
1. **Model Penempatan Fungsi**:
   - Struktur satu proyek (monorepo) didukung oleh Vercel. Next.js App Router mengelola halaman UI dan route auth (`/auth/login`, `/auth/logout`), sementara file Python di folder `/api/*.py` secara otomatis dijalankan oleh runtime Python Vercel (`@vercel/python`).
   - Modul bersama diletakkan di `api/_lib/` (awalan `_` mencegah Vercel mengeksposnya sebagai endpoint publik).
2. **Ukuran Bundle (Maksimal 250 MB Unzipped)**:
   - Library Python dibatasi hanya paket esensial: `pypdf`, `python-docx`, `scikit-learn`, `openpyxl`, `google-api-python-client`, `google-auth`.
   - Dependensi berat seperti PyTorch, TensorFlow, sentence-transformers, atau SpaCy **dilarang keras** untuk menjamin bundle tetap jauh di bawah 250 MB.
3. **Batas Ukuran Payload Body (~4.5 MB)**:
   - Vercel Serverless Functions memiliki batasan request dan response body sebesar 4.5 MB.
   - Mitigasi: Pada `/api/process`, teks tiap seksi dipotong maksimal 4.000 karakter sebelum dikembalikan ke klien. Jumlah CV per batch dibatasi maksimal 400. Klien menyimpan hasil per CV di IndexedDB dan mengirimkan payload yang terkompresi/terpotong ke `/api/rank`.
4. **Batas Eksekusi (`maxDuration`)**:
   - Disetel ke `60` detik pada `vercel.json` (maksimal untuk paket Hobby, dapat ditingkatkan hingga 300s jika menggunakan paket Pro).
   - Proses per-CV dilakukan satu per satu via client-side concurrency pool (4 request simultan), sehingga masing-masing request `/api/process` hanya memerlukan beberapa detik.
5. **Region**:
   - Ditetapkan ke `sin1` (Singapura) pada `vercel.json` untuk latensi terendah bagi pengguna di Indonesia.
6. **Rencana Fallback**:
   - Jika ada kendala routing gabungan antara Next.js App Router dan Python di satu repo Vercel pada deployment produksi, backend Python dapat dipisah menjadi proyek Vercel kedua (mis. `cv-screener-api.vercel.app`) dengan konfigurasi CORS dan env `NEXT_PUBLIC_API_URL`.

---

## 2. Keamanan & Autentikasi

1. **Shared Password & Timing-Safe Equal**:
   - Nilai dari `APP_PASSWORD` diverifikasi menggunakan `crypto.timingSafeEqual` (di Node.js) dan `hmac.compare_digest` (di Python) untuk mencegah serangan timing attack.
2. **HMAC Signed Session Cookie**:
   - Nama cookie: `cv_session`.
   - Format: `<timestamp>.<hmac_signature>`.
   - Cookie flags: `HttpOnly`, `SameSite=Strict`, `Secure` (di production), `Path=/`, `Max-Age=28800` (8 jam).
   - Validasi ganda: Middleware Next.js memverifikasi sesi untuk melindungi halaman web, dan setiap endpoint Python (`/api/process`, `/api/rank`, `/api/export`, `/api/hello`) memverifikasi cookie sesi secara mandiri menggunakan modul `api/_lib/auth.py`.
3. **Perlindungan Tambahan CSRF**:
   - Semua endpoint POST Python memverifikasi keberadaan header `X-Requested-With: XMLHttpRequest` atau `X-CV-Screener: 1`.
4. **Google Drive & SSRF Mitigation**:
   - Hanya menerima Google Drive File ID yang cocok dengan regex `^[A-Za-z0-9_-]{10,}$`.
   - Aplikasi tidak pernah mem-fetch URL arbitrer dari CSV atau internet.
5. **Excel Formula Injection Mitigation**:
   - Sel yang diawali dengan karakter formula (`=`, `+`, `-`, `@`) diberi awalan tanda petik satu (`'`) untuk memaksa interpretasi sebagai string teks murni.

---

## 3. Asumsi Default & Parameter Penilaian

1. **Bobot Kategori Default**:
   - Pengalaman: 35%
   - Project / Portofolio: 30%
   - Sertifikasi & Pendidikan: 20%
   - Kompetensi: 15%
   - *Catatan: Bobot dapat dikustomisasi per profil lowongan dan dinormalisasi otomatis menjadi 100%.*
2. **Ambang Penilaian**:
   - Ambang durasi pengalaman: 12 bulan (level intern/fresh graduate).
   - Ambang jumlah project: 3 project.
   - Rentang normalisasi IPK: 2.50 – 4.00 (`clamp((IPK - 2.5) / 1.5, 0, 1) * 100`).
   - Deteksi scan PDF: teks hasil ekstraksi kurang dari 200 karakter.
   - Ambang korpus fit TF-IDF: jika pelamar per divisi >= 20, fit per divisi; jika < 20, fit pada seluruh korpus batch (semua divisi) + JD.
3. **Konkurensi Klien**:
   - 4 request paralel secara bersamaan.
