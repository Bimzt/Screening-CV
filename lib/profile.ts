import { JobProfile, ScoringCategoryConfig } from "./types";

export const MAX_PROFILE_FILE_SIZE_BYTES = 200 * 1024; // 200 KB
export const SUPPORTED_PROFILE_VERSION = "1.0";

const ALLOWED_TOP_LEVEL_KEYS = new Set([
  "version",
  "division",
  "divisionAliases",
  "title",
  "jd",
  "hardRequirements",
  "additionalSkills",
  "categories",
  "thresholds",
  "customSectionHeadings",
]);

/**
 * Membersihkan dan memastikan karakter regex dieksekusi secara literal
 * untuk mencegah serangan ReDoS.
 */
export function escapeRegexLiteral(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Normalisasi bobot kategori aktif agar berjumlah tepat 100.
 */
export function normalizeProfileWeights(profile: JobProfile): JobProfile {
  const cloned: JobProfile = JSON.parse(JSON.stringify(profile));
  const activeEntries = Object.entries(cloned.categories).filter(
    ([, config]) => config.active
  );

  const totalActiveWeight = activeEntries.reduce(
    (sum, [, config]) => sum + (config.weight || 0),
    0
  );

  if (totalActiveWeight <= 0) {
    // Jika semua bobot 0, bagi rata
    const equalShare = Math.round(100 / (activeEntries.length || 1));
    activeEntries.forEach(([, config]) => {
      config.weight = equalShare;
    });
    return cloned;
  }

  // Normalisasi proporsional
  let runningSum = 0;
  activeEntries.forEach(([key, config], idx) => {
    if (idx === activeEntries.length - 1) {
      // Sisa pembulatan diberikan ke item terakhir
      config.weight = Math.max(0, 100 - runningSum);
    } else {
      const normalized = Math.round((config.weight / totalActiveWeight) * 100);
      config.weight = normalized;
      runningSum += normalized;
    }
  });

  return cloned;
}

/**
 * Validasi ketat profil JSON: tipe, batas ukuran, panjang teks, dan tolak field tak dikenal.
 */
export function parseAndValidateProfileJson(jsonString: string): {
  valid: boolean;
  profile?: JobProfile;
  error?: string;
} {
  if (!jsonString || typeof jsonString !== "string") {
    return { valid: false, error: "Data JSON profil kosong atau tidak valid." };
  }

  const byteLength = new TextEncoder().encode(jsonString).length;
  if (byteLength > MAX_PROFILE_FILE_SIZE_BYTES) {
    return {
      valid: false,
      error: `Ukuran berkas profil (${(byteLength / 1024).toFixed(1)} KB) melebihi batas maksimum 200 KB.`,
    };
  }

  let data: any;
  try {
    data = JSON.parse(jsonString);
  } catch (err) {
    return { valid: false, error: "Sintaks JSON tidak valid atau rusak." };
  }

  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    return { valid: false, error: "Root JSON profil harus berupa object." };
  }

  // Tolak field tak dikenal
  for (const key of Object.keys(data)) {
    if (!ALLOWED_TOP_LEVEL_KEYS.has(key)) {
      return {
        valid: false,
        error: `Field '${key}' tidak dikenali dalam skema profil lowongan.`,
      };
    }
  }

  // Validasi version
  if (data.version !== SUPPORTED_PROFILE_VERSION) {
    return {
      valid: false,
      error: `Versi profil '${data.version}' tidak didukung. Versi yang didukung: ${SUPPORTED_PROFILE_VERSION}.`,
    };
  }

  // Validasi division & title
  if (!data.division || typeof data.division !== "string" || data.division.length > 100) {
    return { valid: false, error: "Nama divisi wajib diisi (string, maks 100 karakter)." };
  }

  if (!data.title || typeof data.title !== "string" || data.title.length > 150) {
    return { valid: false, error: "Judul lowongan wajib diisi (string, maks 150 karakter)." };
  }

  // Validasi JD
  if (!data.jd || typeof data.jd !== "string" || data.jd.length > 10000) {
    return { valid: false, error: "Deskripsi pekerjaan (JD) wajib diisi (maks 10.000 karakter)." };
  }

  // Validasi divisionAliases
  if (data.divisionAliases) {
    if (!Array.isArray(data.divisionAliases) || data.divisionAliases.length > 15) {
      return { valid: false, error: "divisionAliases harus berupa array maksimal 15 item." };
    }
    for (const alias of data.divisionAliases) {
      if (typeof alias !== "string" || alias.length > 50) {
        return { valid: false, error: "Alias divisi harus berupa teks maksimal 50 karakter." };
      }
    }
  } else {
    data.divisionAliases = [];
  }

  // Validasi categories
  if (!data.categories || typeof data.categories !== "object") {
    return { valid: false, error: "Kategori penilaian ('categories') wajib berupa object." };
  }

  const requiredCategories = ["experience", "projects", "cert_edu", "competencies"];
  for (const catKey of requiredCategories) {
    const cat = data.categories[catKey];
    if (!cat || typeof cat !== "object") {
      return { valid: false, error: `Kategori '${catKey}' wajib ada dalam profil.` };
    }
    if (typeof cat.label !== "string" || !cat.label) {
      return { valid: false, error: `Label untuk kategori '${catKey}' wajib diisi.` };
    }
    if (typeof cat.weight !== "number" || cat.weight < 0) {
      return { valid: false, error: `Bobot untuk kategori '${catKey}' harus berupa angka >= 0.` };
    }
    if (typeof cat.active !== "boolean") {
      cat.active = true;
    }
  }

  // Validasi thresholds
  if (!data.thresholds || typeof data.thresholds !== "object") {
    data.thresholds = { durationMonths: 12, projectsCount: 3 };
  } else {
    if (typeof data.thresholds.durationMonths !== "number" || data.thresholds.durationMonths <= 0) {
      data.thresholds.durationMonths = 12;
    }
    if (typeof data.thresholds.projectsCount !== "number" || data.thresholds.projectsCount <= 0) {
      data.thresholds.projectsCount = 3;
    }
  }

  // Validasi hardRequirements jika ada
  if (data.hardRequirements) {
    if (typeof data.hardRequirements !== "object") {
      return { valid: false, error: "hardRequirements harus berupa object." };
    }
    if (data.hardRequirements.minGpa !== undefined) {
      const gpa = data.hardRequirements.minGpa;
      if (typeof gpa !== "number" || gpa < 0 || gpa > 4.0) {
        return { valid: false, error: "minGpa harus berupa angka antara 0.0 hingga 4.0." };
      }
    }
    if (data.hardRequirements.allowedMajors !== undefined) {
      if (!Array.isArray(data.hardRequirements.allowedMajors) || data.hardRequirements.allowedMajors.length > 50) {
        return { valid: false, error: "allowedMajors harus berupa array maksimal 50 jurusan." };
      }
    }
    if (data.hardRequirements.mandatorySkills !== undefined) {
      const ms = data.hardRequirements.mandatorySkills;
      if (typeof ms !== "object" || !Array.isArray(ms.items) || ms.items.length > 30) {
        return { valid: false, error: "mandatorySkills.items harus berupa array maksimal 30 item." };
      }
      if (ms.rule !== "all" && ms.rule !== "min_n") {
        return { valid: false, error: "mandatorySkills.rule harus bernilai 'all' atau 'min_n'." };
      }
    }
  }

  // Normalisasi bobot otomatis
  const normalized = normalizeProfileWeights(data as JobProfile);

  return { valid: true, profile: normalized };
}

/**
 * Ekspor profil ke string JSON terformat
 */
export function exportProfileToJson(profile: JobProfile): string {
  return JSON.stringify(profile, null, 2);
}
