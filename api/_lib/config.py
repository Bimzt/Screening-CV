"""
Konfigurasi terpusat untuk aplikasi CV Screener.
Memuat konstanta rumus, bobot default, ambang batas, dan pengaturan keamanan.
"""

# Konfigurasi Sesi & Keamanan
SESSION_COOKIE_NAME = "cv_session"
SESSION_MAX_AGE_SECONDS = 8 * 3600  # 8 jam

# Batasan File & Batch
MAX_BATCH_CV_COUNT = 400
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per CV
MAX_SECTION_TEXT_CHARS = 4000  # Pemotongan teks per seksi untuk menjaga batas request body Vercel (~4.5MB)
MIN_EXTRACTED_CHARS_FOR_VALID_PDF = 200  # Di bawah 200 karakter dianggap PDF scan / gambar

# Parameter Default Penilaian (Level Intern / Fresh Graduate)
DEFAULT_DURATION_THRESHOLD_MONTHS = 12  # Ambang batas durasi pengalaman (bulan)
DEFAULT_PROJECTS_THRESHOLD = 3          # Ambang batas jumlah project
DEFAULT_MIN_GPA_RANGE = 2.5             # Nilai bawah untuk normalisasi IPK
DEFAULT_MAX_GPA_RANGE = 4.0             # Nilai atas untuk skala IPK

# Bobot Kategori Default (total 100)
DEFAULT_WEIGHTS = {
    "experience": 35,
    "projects": 30,
    "cert_edu": 20,
    "competencies": 15,
}

# Ambang batas pemilihan metode fit TF-IDF
# Jika jumlah pelamar divisi >= 20, fit per divisi.
# Jika < 20, fit seluruh korpus batch (semua divisi) + JD divisi.
MIN_APPLICANTS_FOR_DIVISION_IDF = 20

# Konkurensi Klien
CLIENT_CONCURRENCY = 4
