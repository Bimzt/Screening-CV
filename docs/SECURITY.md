# Pedoman Keamanan dan Privasi Data (SECURITY.md)

Aplikasi **CV Screener** memproses dokumen data pribadi (CV pelamar). Seluruh langkah pengamanan berikut bersifat wajib dan telah diterapkan dalam rancangan sistem.

---

## 1. Otentikasi dan Manajemen Sesi

1. **Shared Password**:
   - Disimpan di environment variable `APP_PASSWORD`.
   - Diverifikasi menggunakan perbandingan waktu-konstan (`crypto.subtle` / `hmac.compare_digest`) guna menangkal serangan *timing attack*.
2. **Session Cookie Bertanda Tangan HMAC**:
   - Token sesi ditandatangani menggunakan `SESSION_SECRET` (HMAC-SHA256).
   - Format: `<timestamp>.<signature_hex>`.
   - Masa berlaku maksimum: **8 jam (28.800 detik)**.
   - Atribut cookie: `HttpOnly`, `SameSite=Strict`, `Secure` (di production), `Path=/`.
3. **Verifikasi Mandiri pada Setiap Endpoint Serverless**:
   - Setiap endpoint Python (`api/*.py`) memverifikasi session cookie secara langsung melalui modul `api/_lib/auth.py`.
   - Permintaan tanpa sesi yang valid langsung ditolak dengan kode status **401 Unauthorized**.
4. **Proteksi CSRF**:
   - Seluruh endpoint POST mewajibkan keberadaan header khusus `X-Requested-With: XMLHttpRequest` atau `X-CV-Screener`.

---

## 2. Akses Google Drive & Pencegahan SSRF

1. **Prinsip Hak Akses Terkecil (Least Privilege)**:
   - Menggunakan Service Account Google Cloud dengan ruang lingkup hanya-baca: `https://www.googleapis.com/auth/drive.readonly`.
   - Tim rekrutmen **hanya membagikan folder Google Drive yang memuat respon formulir CV** kepada email service account dengan hak akses *Viewer*. Jangan bagikan root Drive atau folder lain.
2. **Pencegahan Server-Side Request Forgery (SSRF)**:
   - Aplikasi **hanya menerima Google Drive File ID** yang divalidasi dengan ekspresi reguler ketat: `^[A-Za-z0-9_-]{10,}$`.
   - ID diekstrak dari pola URL Drive yang sah (`open?id=`, `/file/d/<id>/`, `/d/<id>/`).
   - Aplikasi **dilarang keras mem-fetch tautan arbitrer** apa pun yang dimasukkan pengguna atau ditemukan di dalam berkas CV. Tautan portofolio (Instagram, Behance, GitHub, Canva, dll.) hanya dicatat secara literal di lembar Excel tanpa dikunjungi.

---

## 3. Privasi Data & Zero Server Storage

1. **Tanpa Penyimpanan di Server**:
   - Serverless functions bersifat stateless. Tidak ada basis data (SQL/NoSQL) dan tidak ada penyimpanan file sementara di disk server.
2. **Larangan Pencatatan Data Pribadi di Log (No PII Logging)**:
   - Dilarang mencetak (`print` / `console.log`) isi CV, nama kandidat, alamat email, nomor telepon, atau teks hasil ekstraksi ke server log Vercel.
   - Pesan galat teknis hanya mencatat nomor baris CSV dan kode kesalahan.
3. **Penyimpanan Lokal Browser Rekruter**:
   - Hasil parsial disimpan secara lokal di browser via IndexedDB agar proses dapat dilanjutkan jika tab browser tidak sengaja tertutup.
   - Tersedia tombol "Hapus data lokal" untuk membersihkan seluruh data dari browser rekruter.

---

## 4. Keamanan Berkas Keluaran (Mitigasi Excel Formula Injection)

- Berkas spreadsheet Excel yang dibuka di aplikasi seperti Microsoft Excel atau Google Sheets rentan terhadap *CSV/Formula Injection* jika sel teks diawali dengan karakter `=, +, -, @`.
- Semua nilai sel teks sebelum ditulis ke Excel melalui pustaka `openpyxl` disanitasi: jika karakter pertama adalah `=`, `+`, `-`, atau `@`, karakter tersebut diberi awalan tanda petik satu (`'`) untuk memastikan program spreadsheet membacanya sebagai teks murni dan tidak mengeksekusinya sebagai rumus atau makro.

---

## 5. Prosedur Rotasi Kredensial & Pencabutan Akses

1. **Rotasi Password**:
   - Ubah nilai `APP_PASSWORD` di pengaturan Environment Variables Vercel.
   - Sesi pengguna lama akan tetap berjalan hingga masa berlaku 8 jam habis, atau Anda dapat mengganti `SESSION_SECRET` untuk langsung membatalkan semua sesi aktif.
2. **Pencabutan Akses Service Account**:
   - Buka Google Drive folder formulir CV.
   - Buka menu "Share" / "Bagikan", lalu hapus email Service Account dari daftar pengguna bersama.
   - Akses API ke berkas CV akan terputus seketika.
