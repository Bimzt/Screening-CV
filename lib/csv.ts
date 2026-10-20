import Papa from "papaparse";
import { JobProfile } from "./types";

export interface CsvColumnMapping {
  nameCol?: string;
  driveLinkCol?: string;
  divisionCol?: string;
  divisionCol2?: string;
  emailCol?: string;
  phoneCol?: string;
  timestampCol?: string;
}

export interface RawCsvRow {
  rowIndex: number;
  data: Record<string, string>;
  name: string;
  driveLink: string;
  rawDivision: string;
  rawChoice1?: string;
  rawChoice2?: string;
  email?: string;
  phone?: string;
  timestamp?: string;
  divisionChoices: string[];
  isDuplicate?: boolean;
}

export interface DivisionMappingResult {
  csvValue: string;
  mappedDivision?: string;
  count: number;
  isUnmapped: boolean;
}

/**
 * Mendeteksi nama kolom secara otomatis berdasarkan header CSV dan konten baris sampel (jika ada).
 */
export function autoDetectColumns(
  headers: string[],
  sampleRows?: Record<string, string>[]
): CsvColumnMapping {
  const mapping: CsvColumnMapping = {};
  const clean = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

  // 1. Deteksi Kolom Nama
  // Prioritas 1: nama lengkap / full name persis
  for (const h of headers) {
    const c = clean(h);
    if (c === "namalengkap" || c === "fullname" || c === "nama" || c === "name") {
      mapping.nameCol = h;
      break;
    }
  }
  // Prioritas 2: nama mengandung "nama" atau "name" tapi bukan nama instansi/kampus/divisi/ortu
  if (!mapping.nameCol) {
    for (const h of headers) {
      const c = clean(h);
      if (
        (c.includes("nama") || c.includes("name")) &&
        !c.includes("perusahaan") &&
        !c.includes("kampus") &&
        !c.includes("univ") &&
        !c.includes("sekolah") &&
        !c.includes("divisi") &&
        !c.includes("jabatan") &&
        !c.includes("ayah") &&
        !c.includes("ibu") &&
        !c.includes("ortu")
      ) {
        mapping.nameCol = h;
        break;
      }
    }
  }

  // 2. Deteksi Kolom Link Drive CV
  // Prioritas 1: Jika ada sampleRows, periksa kolom yang isi selnya berisi link drive.google.com
  if (sampleRows && sampleRows.length > 0) {
    for (const h of headers) {
      const c = clean(h);
      // Hindari kolom yang jelas-jelas foto, ktp, atau portofolio
      if (
        c.includes("foto") ||
        c.includes("photo") ||
        c.includes("ktp") ||
        c.includes("ktm") ||
        c.includes("portofolio") ||
        c.includes("portfolio") ||
        c.includes("sertifikat")
      ) {
        continue;
      }
      // Hitung baris yang memuat link google drive / docs / pdf di kolom ini
      const driveMatchCount = sampleRows.slice(0, 15).filter((r) => {
        const val = (r[h] || "").toLowerCase();
        return (
          val.includes("drive.google.com") ||
          val.includes("docs.google.com") ||
          val.includes("/file/d/") ||
          val.includes("/folders/") ||
          val.endsWith(".pdf")
        );
      }).length;

      if (driveMatchCount > 0 && (c.includes("cv") || c.includes("resume") || c.includes("berkas") || c.includes("unggah") || c.includes("link") || c.includes("tautan") || c.includes("drive"))) {
        mapping.driveLinkCol = h;
        break;
      }
    }
  }

  // Prioritas 2: Kolom yang memuat kata "cv", "resume", "curriculum" (eksklusif bukan portofolio/foto)
  if (!mapping.driveLinkCol) {
    for (const h of headers) {
      const c = clean(h);
      if (
        (c.includes("cv") || c.includes("resume") || c.includes("curriculumvitae")) &&
        !c.includes("portofolio") &&
        !c.includes("portfolio") &&
        !c.includes("foto") &&
        !c.includes("photo") &&
        !c.includes("ktp") &&
        !c.includes("ktm") &&
        !c.includes("sertifikat")
      ) {
        mapping.driveLinkCol = h;
        break;
      }
    }
  }

  // Prioritas 3: Kolom yang memuat kata "drive", "link", atau "tautan" (bukan medsos/foto/portofolio)
  if (!mapping.driveLinkCol) {
    for (const h of headers) {
      const c = clean(h);
      if (
        (c.includes("drive") || c.includes("link") || c.includes("tautan")) &&
        !c.includes("portofolio") &&
        !c.includes("portfolio") &&
        !c.includes("foto") &&
        !c.includes("photo") &&
        !c.includes("ktp") &&
        !c.includes("ktm") &&
        !c.includes("sertifikat") &&
        !c.includes("linkedin") &&
        !c.includes("instagram") &&
        !c.includes("tiktok")
      ) {
        mapping.driveLinkCol = h;
        break;
      }
    }
  }

  // Prioritas 4: Kolom yang memuat "berkas", "unggah", "upload", "dokumen" (bukan foto/portofolio/karya)
  if (!mapping.driveLinkCol) {
    for (const h of headers) {
      const c = clean(h);
      if (
        (c.includes("berkas") || c.includes("unggah") || c.includes("upload") || c.includes("dokumen")) &&
        !c.includes("portofolio") &&
        !c.includes("portfolio") &&
        !c.includes("foto") &&
        !c.includes("photo") &&
        !c.includes("ktp") &&
        !c.includes("ktm") &&
        !c.includes("sertifikat") &&
        !c.includes("karya") &&
        !c.includes("video")
      ) {
        mapping.driveLinkCol = h;
        break;
      }
    }
  }

  // 3. Deteksi Kolom Divisi Pilihan 1 & 2
  for (const h of headers) {
    const c = clean(h);
    if (!mapping.divisionCol && (
      c.includes("divisi1") || c.includes("pilihan1") || c.includes("divisiutama") || 
      c.includes("firstchoice") || c.includes("pilihanpertama") || c.includes("divisipertama") ||
      c.includes("pilihani") || c.includes("divisii") || c.includes("prioritas1") || c.includes("opsi1")
    )) {
      mapping.divisionCol = h;
    } else if (!mapping.divisionCol2 && (
      c.includes("divisi2") || c.includes("pilihan2") || c.includes("divisicadangan") || 
      c.includes("secondchoice") || c.includes("pilihankedua") || c.includes("divisikedua") ||
      c.includes("pilihanii") || c.includes("divisiii") || c.includes("prioritas2") || c.includes("opsi2") ||
      c.includes("alternatif") || c.includes("cadangan")
    )) {
      mapping.divisionCol2 = h;
    } else if (!mapping.emailCol && (c.includes("email") || c.includes("surel"))) {
      mapping.emailCol = h;
    } else if (!mapping.phoneCol && (c.includes("telepon") || c.includes("phone") || c.includes("hp") || c.includes("wa") || c.includes("whatsapp") || c.includes("kontak"))) {
      mapping.phoneCol = h;
    } else if (!mapping.timestampCol && (c.includes("timestamp") || c.includes("waktu") || c.includes("tanggal"))) {
      mapping.timestampCol = h;
    }
  }

  // Second pass: jika divisionCol belum terisi tapi ada kolom berbau divisi / lowongan
  if (!mapping.divisionCol) {
    for (const h of headers) {
      if (h === mapping.nameCol || h === mapping.driveLinkCol || h === mapping.divisionCol2) continue;
      const c = clean(h);
      if (c.includes("divisi") || c.includes("posisi") || c.includes("lowongan") || c.includes("role") || c.includes("departemen") || c.includes("jabatan")) {
        mapping.divisionCol = h;
        break;
      }
    }
  }

  // Second pass: jika divisionCol2 belum terisi dan ada kolom divisi kedua
  if (!mapping.divisionCol2 && mapping.divisionCol) {
    for (const h of headers) {
      if (h === mapping.nameCol || h === mapping.driveLinkCol || h === mapping.divisionCol) continue;
      const c = clean(h);
      if (
        c.includes("divisi") || c.includes("posisi") || c.includes("lowongan") || 
        c.includes("role") || c.includes("pilihan") || c.includes("opsi")
      ) {
        mapping.divisionCol2 = h;
        break;
      }
    }
  }

  return mapping;
}

/**
 * Normalisasi teks string untuk perbandingan fleksibel.
 */
function normalizeString(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]/g, "").trim();
}

/**
 * Mencocokkan nilai teks divisi dari CSV ke profil lowongan yang tersedia.
 */
export function matchDivisionToProfile(
  rawDiv: string,
  profiles: JobProfile[]
): string | undefined {
  if (!rawDiv || !rawDiv.trim()) return undefined;

  const cleanInput = normalizeString(rawDiv);

  // 1. Cocokkan langsung dengan nama divisi
  for (const p of profiles) {
    if (normalizeString(p.division) === cleanInput) {
      return p.division;
    }
  }

  // 2. Cocokkan dengan alias-alias divisi
  for (const p of profiles) {
    for (const alias of p.divisionAliases || []) {
      if (normalizeString(alias) === cleanInput) {
        return p.division;
      }
    }
  }

  // 3. Cocokkan substring parsial
  for (const p of profiles) {
    const pNorm = normalizeString(p.division);
    if (cleanInput.includes(pNorm) || pNorm.includes(cleanInput)) {
      return p.division;
    }
  }

  return undefined;
}

/**
 * Mengurai sel divisi yang mungkin memuat lebih dari satu pilihan (dipisah koma / titik koma / baris baru).
 */
export function splitDivisionCell(rawCell: string): string[] {
  if (!rawCell) return [];
  return rawCell
    .split(/[,;\n\r|]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

/**
 * Mengurai berkas CSV dari teks string (Papa Parse) di browser.
 */
export function parseCsvText(csvContent: string): Promise<{
  headers: string[];
  rows: Record<string, string>[];
}> {
  return new Promise((resolve, reject) => {
    Papa.parse<Record<string, string>>(csvContent, {
      header: true,
      skipEmptyLines: "greedy",
      complete: (results) => {
        const headers = results.meta.fields || [];
        resolve({ headers, rows: results.data });
      },
      error: (error: Error) => {
        reject(error);
      },
    });
  });
}

/**
 * Menyiapkan baris pelamar dari data mentah CSV, memetakan kolom,
 * memetakan divisi, dan menandai duplikasi.
 */
export function processRawCsvRows(
  rows: Record<string, string>[],
  mapping: CsvColumnMapping,
  profiles: JobProfile[],
  manualDivisionOverrides: Record<string, string> = {}
): {
  processedRows: RawCsvRow[];
  divisionStats: Record<string, number>;
  unmappedStats: Record<string, number>;
  duplicateCount: number;
} {
  const processedRows: RawCsvRow[] = [];
  const divisionStats: Record<string, number> = {};
  const unmappedStats: Record<string, number> = {};

  // Peta deduplikasi (kunci: email, atau nama + link CV)
  const seenSubmissions = new Map<string, number>();
  let duplicateCount = 0;

  rows.forEach((row, index) => {
    const rowIndex = index + 2; // Baris 1 adalah header di spreadsheet
    const name = (mapping.nameCol ? row[mapping.nameCol] : "") || `Pelamar ${rowIndex}`;
    const driveLink = (mapping.driveLinkCol ? row[mapping.driveLinkCol] : "") || "";
    const rawDiv1 = (mapping.divisionCol ? row[mapping.divisionCol] : "") || "";
    const rawDiv2 = (mapping.divisionCol2 ? row[mapping.divisionCol2] : "") || "";
    const rawDivision = [rawDiv1.trim(), rawDiv2.trim()].filter(Boolean).join(", ");

    const email = mapping.emailCol ? row[mapping.emailCol]?.trim().toLowerCase() : undefined;
    const phone = mapping.phoneCol ? row[mapping.phoneCol]?.trim() : undefined;
    const timestamp = mapping.timestampCol ? row[mapping.timestampCol] : undefined;

    // Kumpulkan daftar token divisi dengan urutan: Pilihan 1 diikuti Pilihan 2
    const tokensToProcess: string[] = [];
    if (mapping.divisionCol && mapping.divisionCol2 && mapping.divisionCol !== mapping.divisionCol2) {
      if (rawDiv1.trim()) tokensToProcess.push(rawDiv1.trim());
      if (rawDiv2.trim()) tokensToProcess.push(rawDiv2.trim());
    } else {
      const splitted = splitDivisionCell(rawDivision);
      if (splitted.length === 0 && rawDivision.trim()) {
        splitted.push(rawDivision.trim());
      }
      tokensToProcess.push(...splitted);
    }

    const mappedChoices: string[] = [];

    for (const divToken of tokensToProcess) {
      // Periksa override manual terlebih dahulu
      const override = manualDivisionOverrides[divToken];
      const matched = override || matchDivisionToProfile(divToken, profiles);

      if (matched) {
        if (!mappedChoices.includes(matched)) {
          mappedChoices.push(matched);
        }
        divisionStats[matched] = (divisionStats[matched] || 0) + 1;
      } else {
        unmappedStats[divToken] = (unmappedStats[divToken] || 0) + 1;
      }
    }

    // Deteksi duplikasi (jika email sama atau nama + link CV sama)
    const dedupKey = email || `${normalizeString(name)}_${driveLink.trim()}`;
    let isDuplicate = false;
    if (dedupKey && dedupKey !== "_") {
      if (seenSubmissions.has(dedupKey)) {
        isDuplicate = true;
        duplicateCount++;
      } else {
        seenSubmissions.set(dedupKey, rowIndex);
      }
    }

    processedRows.push({
      rowIndex,
      data: row,
      name: name.trim(),
      driveLink: driveLink.trim(),
      rawDivision: rawDivision.trim(),
      rawChoice1: rawDiv1.trim() || undefined,
      rawChoice2: rawDiv2.trim() || undefined,
      email,
      phone,
      timestamp,
      divisionChoices: mappedChoices,
      isDuplicate,
    });
  });

  return {
    processedRows,
    divisionStats,
    unmappedStats,
    duplicateCount,
  };
}
