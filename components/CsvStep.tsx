"use client";

import React, { useState } from "react";
import { JobProfile } from "@/lib/types";
import {
  parseCsvText,
  autoDetectColumns,
  processRawCsvRows,
  matchDivisionToProfile,
  CsvColumnMapping,
  RawCsvRow,
} from "@/lib/csv";
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
  Users,
  CopyCheck,
  Sparkles,
} from "lucide-react";

interface CsvStepProps {
  profiles: JobProfile[];
  onStartProcessing: (processedRows: RawCsvRow[]) => void;
  onBackToProfiles: () => void;
  onOpenQuickTest?: () => void;
}

export default function CsvStep({
  profiles,
  onStartProcessing,
  onBackToProfiles,
  onOpenQuickTest,
}: CsvStepProps) {
  const [csvFileName, setCsvFileName] = useState<string | null>(null);
  const [rawHeaders, setRawHeaders] = useState<string[]>([]);
  const [rawRowsData, setRawRowsData] = useState<Record<string, string>[]>([]);
  const [columnMapping, setColumnMapping] = useState<CsvColumnMapping>({});
  const [manualDivisionOverrides, setManualDivisionOverrides] = useState<Record<string, string>>({});
  const [parsingError, setParsingError] = useState<string | null>(null);

  const handleFileUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setParsingError("Harap unggah berkas berekstensi .csv");
      return;
    }

    setCsvFileName(file.name);
    setParsingError(null);

    try {
      const text = await file.text();
      const { headers, rows } = await parseCsvText(text);

      if (rows.length === 0) {
        setParsingError("Berkas CSV kosong atau tidak memiliki baris data.");
        return;
      }

      setRawHeaders(headers);
      setRawRowsData(rows);

      // Auto detect columns
      const detected = autoDetectColumns(headers);
      setColumnMapping(detected);
    } catch {
      setParsingError("Gagal membaca atau mem-parse berkas CSV.");
    }
  };

  // Kalkulasi pemetaan jika baris & profil tersedia
  const calculationResult = React.useMemo(() => {
    if (rawRowsData.length === 0) return null;
    return processRawCsvRows(
      rawRowsData,
      columnMapping,
      profiles,
      manualDivisionOverrides
    );
  }, [rawRowsData, columnMapping, profiles, manualDivisionOverrides]);

  const uniqueRawDivisions = React.useMemo(() => {
    if (!calculationResult) return [];
    const set = new Set<string>();
    for (const r of calculationResult.processedRows) {
      if (r.rawDivision) {
        for (const token of r.rawDivision.split(/[,;\n\r|]+/)) {
          if (token.trim()) set.add(token.trim());
        }
      }
    }
    return Array.from(set);
  }, [calculationResult]);

  const totalUnmapped = calculationResult
    ? Object.values(calculationResult.unmappedStats).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="space-y-6">
      {/* Quick Test Highlight Banner */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-indigo-950/60 via-slate-900 to-indigo-950/30 border border-indigo-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
            <Sparkles className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <div className="text-xs font-bold text-white">
              Ingin uji coba 1 CV langsung tanpa menunggu CSV?
            </div>
            <div className="text-[11px] text-slate-400">
              Unggah 1 berkas CV langsung dan sistem akan otomatis merekomendasikan divisi mana yang paling cocok.
            </div>
          </div>
        </div>
        {onOpenQuickTest && (
          <button
            onClick={onOpenQuickTest}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white rounded-xl text-xs font-semibold shrink-0 flex items-center gap-1.5 shadow-md shadow-indigo-600/20 cursor-pointer transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Uji Coba 1 CV Langsung</span>
          </button>
        )}
      </div>

      {/* Upload Zone */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-indigo-400" />
              Unggah CSV Respons Formulir Pelamar
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              CSV diekstrak dan di-parse sepenuhnya di browser Anda tanpa diunggah ke server.
            </p>
          </div>
          {csvFileName && (
            <button
              onClick={() => {
                setCsvFileName(null);
                setRawRowsData([]);
                setRawHeaders([]);
              }}
              className="px-3 py-1.5 text-xs text-slate-400 hover:text-white rounded-lg border border-slate-700 hover:bg-slate-800 flex items-center gap-1.5 cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Ganti File</span>
            </button>
          )}
        </div>

        {!csvFileName ? (
          <label className="border-2 border-dashed border-slate-800 hover:border-indigo-500/50 rounded-2xl p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-slate-950/40 group">
            <UploadCloud className="w-12 h-12 text-slate-600 group-hover:text-indigo-400 transition-colors mb-3" />
            <span className="text-sm font-semibold text-slate-200">
              Pilih atau seret berkas CSV ke sini
            </span>
            <span className="text-xs text-slate-500 mt-1">
              Maksimal 400 baris pelamar per batch respons form
            </span>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFileUpload(f);
              }}
              className="hidden"
            />
          </label>
        ) : (
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between text-xs">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <div className="font-semibold text-white">{csvFileName}</div>
                <div className="text-slate-400">
                  {rawRowsData.length} baris pelamar ditemukan &bull; {rawHeaders.length} kolom
                </div>
              </div>
            </div>
            {calculationResult?.duplicateCount ? (
              <div className="flex items-center gap-1.5 text-amber-400 bg-amber-950/40 px-3 py-1.5 rounded-lg border border-amber-800/40">
                <CopyCheck className="w-4 h-4" />
                <span>{calculationResult.duplicateCount} duplikat ditandai</span>
              </div>
            ) : null}
          </div>
        )}

        {parsingError && (
          <div className="mt-4 p-3.5 rounded-xl bg-red-950/60 border border-red-800 text-red-200 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{parsingError}</span>
          </div>
        )}
      </div>

      {/* Column Mapping Section */}
      {csvFileName && rawHeaders.length > 0 && (
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <span>Pemetaan Kolom CSV</span>
            <span className="text-xs font-normal text-slate-400">
              (Pastikan kolom Link CV dan Divisi sudah sesuai)
            </span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block text-slate-400 mb-1 font-semibold">
                Kolom Nama Pelamar
              </label>
              <select
                value={columnMapping.nameCol || ""}
                onChange={(e) => setColumnMapping({ ...columnMapping, nameCol: e.target.value })}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="">-- Pilih Kolom Nama --</option>
                {rawHeaders.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-semibold">
                Kolom Link Google Drive CV <span className="text-red-400">*</span>
              </label>
              <select
                value={columnMapping.driveLinkCol || ""}
                onChange={(e) => setColumnMapping({ ...columnMapping, driveLinkCol: e.target.value })}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="">-- Pilih Kolom Link CV --</option>
                {rawHeaders.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-semibold">
                Kolom Divisi Pilihan 1 (Utama) <span className="text-red-400">*</span>
              </label>
              <select
                value={columnMapping.divisionCol || ""}
                onChange={(e) => setColumnMapping({ ...columnMapping, divisionCol: e.target.value })}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="">-- Pilih Kolom Divisi 1 --</option>
                {rawHeaders.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-semibold flex items-center justify-between">
                <span>Kolom Divisi Pilihan 2 (Alternatif)</span>
                <span className="text-[10px] text-indigo-400 font-normal">Ikut Dinilai</span>
              </label>
              <select
                value={columnMapping.divisionCol2 || ""}
                onChange={(e) => setColumnMapping({ ...columnMapping, divisionCol2: e.target.value })}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="">-- Lewati jika hanya 1 kolom pilihan --</option>
                {rawHeaders.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>

            {columnMapping.divisionCol2 && (
              <div className="col-span-full p-3 rounded-xl bg-indigo-950/40 border border-indigo-500/30 text-xs text-indigo-300 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
                <span>
                  <strong>Mode Penilaian Ganda (Pilihan 1 & 2) Aktif:</strong> Pelamar akan dinilai dan diranking di kedua divisi sekaligus, lengkap dengan analisis komparasi rekomendasi kecocokan.
                </span>
              </div>
            )}

            <div>
              <label className="block text-slate-400 mb-1 font-semibold">
                Kolom Email
              </label>
              <select
                value={columnMapping.emailCol || ""}
                onChange={(e) => setColumnMapping({ ...columnMapping, emailCol: e.target.value })}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none"
              >
                <option value="">-- Lewati / Kosong --</option>
                {rawHeaders.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-semibold">
                Kolom Nomor HP
              </label>
              <select
                value={columnMapping.phoneCol || ""}
                onChange={(e) => setColumnMapping({ ...columnMapping, phoneCol: e.target.value })}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none"
              >
                <option value="">-- Lewati / Kosong --</option>
                {rawHeaders.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-semibold">
                Kolom Waktu (Timestamp)
              </label>
              <select
                value={columnMapping.timestampCol || ""}
                onChange={(e) => setColumnMapping({ ...columnMapping, timestampCol: e.target.value })}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none"
              >
                <option value="">-- Lewati / Kosong --</option>
                {rawHeaders.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Division Mapping Matrix */}
      {csvFileName && calculationResult && uniqueRawDivisions.length > 0 && (
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Users className="w-4 h-4 text-indigo-400" />
                <span>Pemetaan Teks Divisi CSV ke Profil Lowongan</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Nilai teks yang tidak terpetakan akan dimasukkan ke lembar &ldquo;Perlu Dicek&rdquo;.
              </p>
            </div>

            {totalUnmapped > 0 && (
              <span className="text-xs px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                {totalUnmapped} pelamar belum terpetakan
              </span>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-200">
              <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3 font-semibold">Teks Pilihan di CSV</th>
                  <th className="py-2.5 px-3 font-semibold">Petakan ke Profil Divisi</th>
                  <th className="py-2.5 px-3 font-semibold">Jumlah Pelamar</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {uniqueRawDivisions.map((token) => {
                  const mapped =
                    manualDivisionOverrides[token] ||
                    matchDivisionToProfile(token, profiles) ||
                    "";
                  const count = calculationResult.processedRows.filter((r) =>
                    r.rawDivision.includes(token)
                  ).length;

                  return (
                    <tr key={token} className="hover:bg-slate-950/30">
                      <td className="py-2.5 px-3 font-mono text-indigo-300">{token}</td>
                      <td className="py-2.5 px-3">
                        <select
                          value={mapped}
                          onChange={(e) => {
                            setManualDivisionOverrides({
                              ...manualDivisionOverrides,
                              [token]: e.target.value,
                            });
                          }}
                          className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none"
                        >
                          <option value="">-- Tidak Terpetakan (Perlu Dicek) --</option>
                          {profiles.map((p) => (
                            <option key={p.division} value={p.division}>
                              {p.division} ({p.title})
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">{count} pelamar</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-4">
        <button
          onClick={onBackToProfiles}
          className="px-4 py-2 text-xs text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors cursor-pointer"
        >
          &larr; Kembali ke Profil
        </button>

        {calculationResult && calculationResult.processedRows.length > 0 && (
          <button
            onClick={() => onStartProcessing(calculationResult.processedRows)}
            disabled={!columnMapping.driveLinkCol || !columnMapping.divisionCol}
            className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/25 flex items-center gap-2 cursor-pointer transition-all"
          >
            <span>Mulai Screening ({calculationResult.processedRows.length} Pelamar)</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
