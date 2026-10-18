# CV Screener

Aplikasi web internal penyaring dan pemeringkat CV pelamar multi-divisi (level intern/fresh graduate) menggunakan **Next.js (App Router, TypeScript, Tailwind)** dan **Python Serverless Functions di Vercel**.

> **Pernyataan Etika Rekrutmen:**  
> Skor pemeringkatan adalah **alat bantu pengurutan, bukan keputusan otomatis**. Rekruter yang menentukan hasil akhir. Aplikasi **tidak menggunakan** data pribadi sensitif (nama, jenis kelamin, usia, agama, foto, alamat, atau nama kampus) dalam perhitungan skor.

---

## Fitur Utama

- **Multi-Divisi dalam Satu Batch**: Memproses pelamar dari divisi teknis dan non-teknis sekaligus (HROD, HRTA, Sosial Media, CS, Data Analyst, dll.).
- **Scoring Tanpa LLM/Embedding**: Menggunakan **TF-IDF (unigram + bigram)** dan kamus kompetensi yang dapat dikustomisasi per divisi dengan normalisasi bobot dinamis.
- **Dukungan Hard Requirement Opsional**: Syarat kompetensi wajib (aturan all / min_n), IPK minimum, dan jurusan/program studi yang diterima beserta alias.
- **Zero Server Storage**: Tidak ada database dan tidak ada file CV yang disimpan di server. Hasil screening diekspor langsung dalam format **Excel (.xlsx)** 3 sheet.
- **Integrasi Google Drive Aman**: Mengunduh berkas CV secara langsung menggunakan Service Account Google Drive (Viewer scope) dengan mitigasi SSRF ketat.
- **Penyimpanan Lokal Browser**: Data batch tersimpan sementara di IndexedDB perangkat rekruter untuk ketahanan koneksi, dilengkapi opsi pembersihan data lokal.

---

## Prasyarat Lingkungan

- Node.js 18+ (direkomendasikan v20+)
- Python 3.10+ (direkomendasikan 3.12)
- Akun Google Cloud dengan Google Drive API aktif & Service Account

---

## Panduan Instalasi & Menjalankan Lokal

### 1. Salin Environment Variables
Salin berkas contoh konfigurasi:
```bash
cp .env.example .env.local
```
Isi variabel berikut di `.env.local`:
- `APP_PASSWORD`: Password bersama untuk tim rekrutmen.
- `SESSION_SECRET`: Kunci acak minimal 32 karakter untuk HMAC session cookie.
- `GOOGLE_SERVICE_ACCOUNT_JSON_B64`: String Base64 dari berkas JSON service account.

### 2. Instalasi Dependensi
```bash
# Dependensi Next.js & Frontend
npm install

# Dependensi Python Serverless
pip install -r requirements.txt
```

### 3. Menjalankan Server Pengembangan
Jalankan server Python dev dan Next.js secara bersamaan:

**Terminal 1 (Python Dev Server):**
```bash
python scripts/dev_server.py
```
*Server Python akan berjalan di http://127.0.0.1:8000 dan melayani permintaan `/api/*`.*

**Terminal 2 (Next.js Frontend):**
```bash
npm run dev
```
*Buka browser di http://localhost:3000.*

---

## Pengujian Otomatis

Jalankan rangkaian unit test dan integrasi:
```bash
# Menjalankan pengujian Python (pytest)
python -m pytest tests/ -v

# Menjalankan build TypeScript & Next.js
npm run build
```

---

## Deployment ke Vercel

1. Hubungkan repositori GitHub **private** ini ke Vercel.
2. Pada menu **Project Settings > Environment Variables**, tambahkan:
   - `APP_PASSWORD`
   - `SESSION_SECRET`
   - `GOOGLE_SERVICE_ACCOUNT_JSON_B64`
3. Konfigurasi region dan batas eksekusi telah ditentukan di `vercel.json`:
   - Region: `sin1` (Singapura)
   - Batas durasi fungsi: 60 detik (sesuai paket Vercel Hobby / Pro)
4. Klik **Deploy**. Vercel akan otomatis membangun Next.js dan mendeploy Python Serverless Functions di folder `/api`.

---

## Dokumentasi Teknis

- [Arsitektur Sistem](docs/ARCHITECTURE.md)
- [Catatan Keputusan Desain (DECISIONS.md)](docs/DECISIONS.md)
- [Kebijakan Keamanan & Privasi](docs/SECURITY.md)

---

## Lisensi & Privasi

Proyek ini merupakan perangkat lunak internal rekrutmen. Seluruh data pelamar bersifat rahasia dan dilindungi oleh prinsip perlindungan data pribadi.