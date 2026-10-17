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
 * Mendeteksi nama kolom secara otomatis berdasarkan header CSV.
 */
export function autoDetectColumns(headers: string[]): CsvColumnMapping {
  const mapping: CsvColumnMapping = {};

  const clean = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

  for (const h of headers) {
    const c = clean(h);

    if (!mapping.nameCol && (c.includes("nama") || c.includes("name") || c === "namalengkap")) {
      mapping.nameCol = h;
    } else if (!mapping.driveLinkCol && (c.includes("cv") || c.includes("resume") || c.includes("drive") || c.includes("berkas") || c.includes("unggah"))) {
      mapping.driveLinkCol = h;
    } else if (!mapping.divisionCol && (c.includes("divisi1") || c.includes("pilihan1") || c.includes("divisiutama") || c.includes("firstchoice"))) {
      mapping.divisionCol = h;
    } else if (!mapping.divisionCol2 && (c.includes("divisi2") || c.includes("pilihan2") || c.includes("divisicadangan") || c.includes("secondchoice"))) {
      mapping.divisionCol2 = h;
    } else if (!mapping.divisionCol && (c.includes("divisi") || c.includes("posisi") || c.includes("lowongan") || c.includes("role") || c.includes("departemen"))) {
      mapping.divisionCol = h;
    } else if (!mapping.emailCol && (c.includes("email") || c.includes("surel"))) {
      mapping.emailCol = h;
    } else if (!mapping.phoneCol && (c.includes("telepon") || c.includes("phone") || c.includes("hp") || c.includes("wa") || c.includes("whatsapp") || c.includes("kontak"))) {
      mapping.phoneCol = h;
    } else if (!mapping.timestampCol && (c.includes("timestamp") || c.includes("waktu") || c.includes("tanggal"))) {
      mapping.timestampCol = h;
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

    // Pisahkan divisi jika kandidat memilih beberapa pilihan
    const splittedDivisions = splitDivisionCell(rawDivision);
    const mappedChoices: string[] = [];

    if (splittedDivisions.length === 0 && rawDivision.trim()) {
      splittedDivisions.push(rawDivision.trim());
    }

    for (const divToken of splittedDivisions) {
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
