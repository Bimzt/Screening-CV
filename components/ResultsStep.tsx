"use client";

import React, { useState } from "react";
import {
  RankingResponse,
  RankedCandidate,
  JobProfile,
  ProcessedCVResult,
} from "@/lib/types";
import { clearLocalData } from "@/lib/idb";
import {
  Download,
  Trash2,
  RotateCcw,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  XCircle,
  FileSpreadsheet,
  Briefcase,
  Layers,
} from "lucide-react";

interface ResultsStepProps {
  rankingData: RankingResponse;
  profiles: JobProfile[];
  onStartNewBatch: () => void;
}

export default function ResultsStep({
  rankingData,
  profiles,
  onStartNewBatch,
}: ResultsStepProps) {
  const divisions = Object.keys(rankingData.divisionResults);
  const [selectedDivision, setSelectedDivision] = useState<string>(
    divisions[0] || "Semua"
  );
  const [statusFilter, setStatusFilter] = useState<string>("Semua");
  const [activeTab, setActiveTab] = useState<"ranking" | "review">("ranking");
  const [expandedCandidateId, setExpandedCandidateId] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  const currentCandidates = (
    rankingData.divisionResults[selectedDivision] || []
  ).filter((c) => {
    if (statusFilter === "Semua") return true;
    return c.hardRequirementStatus === statusFilter;
  });

  const handleDownloadExcel = async () => {
    setIsExporting(true);
    setExportMessage(null);

    try {
      const res = await fetch("/api/export", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          rankingData,
          profiles,
        }),
      });

      if (!res.ok) {
        throw new Error(`Gagal mengunduh Excel: HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Hasil_Screening_CV_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setExportMessage("Berkas Excel berhasil diunduh.");
    } catch (err: unknown) {
      setExportMessage(err instanceof Error ? err.message : "Gagal mengunduh Excel.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleClearData = async () => {
    if (confirm("Apakah Anda yakin ingin menghapus data screening lokal dari browser ini?")) {
      await clearLocalData();
      alert("Data lokal berhasil dibersihkan.");
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Selesai
            </span>
            <h2 className="text-base font-bold text-white">Hasil Pemeringkatan CV</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Total {rankingData.meta.totalProcessed} berkas dievaluasi &bull; {rankingData.reviewList.length} perlu dicek manual
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleDownloadExcel}
            disabled={isExporting}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-lg shadow-emerald-600/20 transition-all cursor-pointer"
          >
            <Download className="w-4 h-4" />
            <span>{isExporting ? "Menyiapkan Excel..." : "Unduh Berkas Excel (.xlsx)"}</span>
          </button>

          <button
            onClick={handleClearData}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold flex items-center gap-1.5 border border-slate-700 transition-colors cursor-pointer"
            title="Bersihkan penyimpanan lokal browser"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Hapus Data Lokal</span>
          </button>

          <button
            onClick={onStartNewBatch}
            className="px-3.5 py-2 bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/30 border border-indigo-500/30 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Batch Baru</span>
          </button>
        </div>
      </div>

      {exportMessage && (
        <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{exportMessage}</span>
        </div>
      )}

      {/* Main Tab Controls */}
      <div className="flex border-b border-slate-800 gap-6 text-xs font-semibold text-slate-400">
        <button
          onClick={() => setActiveTab("ranking")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
            activeTab === "ranking"
              ? "text-indigo-400 border-indigo-500 font-bold"
              : "border-transparent hover:text-white"
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Tabel Ranking Divisi</span>
        </button>

        <button
          onClick={() => setActiveTab("review")}
          className={`pb-3 flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
            activeTab === "review"
              ? "text-amber-400 border-amber-500 font-bold"
              : "border-transparent hover:text-white"
          }`}
        >
          <AlertTriangle className="w-4 h-4" />
          <span>Perlu Dicek ({rankingData.reviewList.length})</span>
        </button>
      </div>

      {activeTab === "ranking" ? (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            {/* Division Selector */}
            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              {divisions.map((div) => (
                <button
                  key={div}
                  onClick={() => setSelectedDivision(div)}
                  className={`px-3 py-1.5 rounded-xl font-medium transition-colors cursor-pointer whitespace-nowrap ${
                    selectedDivision === div
                      ? "bg-indigo-600 text-white font-semibold"
                      : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
                  }`}
                >
                  {div} ({rankingData.divisionResults[div]?.length || 0})
                </button>
              ))}
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-1.5 bg-slate-900 p-1 rounded-xl border border-slate-800 self-start">
              {["Semua", "Memenuhi", "Perlu dicek", "Tidak memenuhi"].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-2.5 py-1 rounded-lg transition-colors cursor-pointer text-[11px] ${
                    statusFilter === st
                      ? "bg-indigo-600/30 text-indigo-300 font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {/* Candidates Table */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-200">
                <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 font-semibold">
                  <tr>
                    <th className="py-3 px-4 w-12 text-center">Rank</th>
                    <th className="py-3 px-4">Nama Pelamar</th>
                    <th className="py-3 px-4">Kampus & Jurusan</th>
                    <th className="py-3 px-4 text-center">IPK</th>
                    <th className="py-3 px-4 text-center">Skor Akhir</th>
                    <th className="py-3 px-4">Syarat Wajib</th>
                    <th className="py-3 px-4">Alasan Penilaian</th>
                    <th className="py-3 px-4 text-center">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {currentCandidates.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-slate-500">
                        Tidak ada kandidat untuk filter yang dipilih.
                      </td>
                    </tr>
                  ) : (
                    currentCandidates.map((cand) => {
                      const isExpanded = expandedCandidateId === cand.fileId;
                      let statusBadge = (
                        <span className="px-2 py-0.5 rounded-md text-[10px] bg-slate-800 text-slate-400">
                          {cand.hardRequirementStatus}
                        </span>
                      );

                      if (cand.hardRequirementStatus === "Memenuhi") {
                        statusBadge = (
                          <span className="px-2 py-0.5 rounded-md text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                            Memenuhi
                          </span>
                        );
                      } else if (cand.hardRequirementStatus === "Perlu dicek") {
                        statusBadge = (
                          <span className="px-2 py-0.5 rounded-md text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">
                            Perlu Dicek
                          </span>
                        );
                      } else if (cand.hardRequirementStatus === "Tidak memenuhi") {
                        statusBadge = (
                          <span className="px-2 py-0.5 rounded-md text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 font-semibold">
                            Tidak Memenuhi
                          </span>
                        );
                      }

                      return (
                        <React.Fragment key={`${cand.division}_${cand.fileId}_${cand.rank}`}>
                          <tr className="hover:bg-slate-950/40 transition-colors">
                            <td className="py-3 px-4 font-mono font-bold text-center text-slate-400">
                              #{cand.rank}
                            </td>
                            <td className="py-3 px-4">
                              <div className="font-semibold text-white">{cand.name}</div>
                              <div className="text-[11px] text-slate-400">{cand.email || "-"}</div>
                              {cand.multiDivisionNote && (
                                <div className="text-[10px] text-indigo-400 font-medium mt-0.5">
                                  {cand.multiDivisionNote}
                                </div>
                              )}
                            </td>
                            <td className="py-3 px-4">
                              <div className="text-slate-300">{cand.university || "-"}</div>
                              <div className="text-[11px] text-slate-500">{cand.major || "-"}</div>
                            </td>
                            <td className="py-3 px-4 text-center font-mono text-slate-300">
                              {cand.gpa !== undefined && cand.gpa !== null ? cand.gpa.toFixed(2) : "-"}
                            </td>
                            <td className="py-3 px-4 text-center font-mono font-bold text-sm text-indigo-400">
                              {cand.finalScore.toFixed(1)}
                            </td>
                            <td className="py-3 px-4">{statusBadge}</td>
                            <td className="py-3 px-4 max-w-xs text-[11px] text-slate-400 truncate">
                              {cand.reasons}
                            </td>
                            <td className="py-3 px-4 text-center">
                              <button
                                onClick={() =>
                                  setExpandedCandidateId(isExpanded ? null : cand.fileId)
                                }
                                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
                                title="Detail Pelamar"
                              >
                                {isExpanded ? (
                                  <ChevronUp className="w-4 h-4" />
                                ) : (
                                  <ChevronDown className="w-4 h-4" />
                                )}
                              </button>
                            </td>
                          </tr>

                          {/* Expanded Breakdown */}
                          {isExpanded && (
                            <tr className="bg-slate-950/70">
                              <td colSpan={8} className="p-4 space-y-3 border-t border-slate-800">
                                <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
                                  <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                                    <span className="text-slate-400 block text-[10px] mb-0.5">
                                      Skor Pengalaman
                                    </span>
                                    <span className="font-mono font-semibold text-slate-200">
                                      {cand.categoryScores.experience ?? "-"} / 100
                                    </span>
                                  </div>
                                  <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                                    <span className="text-slate-400 block text-[10px] mb-0.5">
                                      Skor Project / Portofolio
                                    </span>
                                    <span className="font-mono font-semibold text-slate-200">
                                      {cand.categoryScores.projects ?? "-"} / 100
                                    </span>
                                  </div>
                                  <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                                    <span className="text-slate-400 block text-[10px] mb-0.5">
                                      Skor Sertifikasi & Pendidikan
                                    </span>
                                    <span className="font-mono font-semibold text-slate-200">
                                      {cand.categoryScores.cert_edu ?? "-"} / 100
                                    </span>
                                  </div>
                                  <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                                    <span className="text-slate-400 block text-[10px] mb-0.5">
                                      Skor Kompetensi
                                    </span>
                                    <span className="font-mono font-semibold text-slate-200">
                                      {cand.categoryScores.competencies ?? "-"} / 100
                                    </span>
                                  </div>
                                </div>

                                <div className="text-xs space-y-1.5 pt-1">
                                  <div className="text-slate-300">
                                    <span className="font-semibold text-slate-400">Alasan Lengkap: </span>
                                    {cand.reasons}
                                  </div>

                                  {cand.skillsFound && cand.skillsFound.length > 0 && (
                                    <div className="text-slate-300">
                                      <span className="font-semibold text-slate-400">Kompetensi Ditemukan: </span>
                                      <span className="text-emerald-400">{cand.skillsFound.join(", ")}</span>
                                    </div>
                                  )}

                                  {cand.portfolioLinks && cand.portfolioLinks.length > 0 && (
                                    <div className="text-slate-300">
                                      <span className="font-semibold text-slate-400">Tautan Portofolio: </span>
                                      <span className="text-indigo-400">{cand.portfolioLinks.join(" | ")}</span>
                                    </div>
                                  )}

                                  {cand.driveLink && (
                                    <div className="pt-1">
                                      <a
                                        href={cand.driveLink}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-xs text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1"
                                      >
                                        <span>Buka CV di Google Drive</span>
                                        <ExternalLink className="w-3 h-3" />
                                      </a>
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* Review List Table */
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
          <div className="p-4 bg-amber-950/20 border-b border-slate-800 text-xs text-amber-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>
              Daftar pelamar berikut tidak dapat dinilai secara otomatis (mis. PDF scan gambar, gagal unduh, atau divisi tidak terpetakan).
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-200">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 font-semibold">
                <tr>
                  <th className="py-3 px-4 w-16 text-center">Baris</th>
                  <th className="py-3 px-4">Nama Pelamar</th>
                  <th className="py-3 px-4">Pilihan Divisi</th>
                  <th className="py-3 px-4">Jenis Masalah</th>
                  <th className="py-3 px-4">Saran Tindakan</th>
                  <th className="py-3 px-4 text-center">Link CV</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {rankingData.reviewList.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-500">
                      Tidak ada pelamar yang perlu dicek manual. Semua berkas diproses dengan lancar!
                    </td>
                  </tr>
                ) : (
                  rankingData.reviewList.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-950/40">
                      <td className="py-3 px-4 font-mono text-center text-slate-400">
                        {item.rowIndex || "-"}
                      </td>
                      <td className="py-3 px-4 font-semibold text-white">{item.name || "Pelamar"}</td>
                      <td className="py-3 px-4 text-slate-300">{item.division || "-"}</td>
                      <td className="py-3 px-4 text-amber-400 font-medium">{item.issueType}</td>
                      <td className="py-3 px-4 text-slate-400">{item.suggestedAction}</td>
                      <td className="py-3 px-4 text-center">
                        {item.driveLink ? (
                          <a
                            href={item.driveLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 inline-block text-indigo-400 hover:text-white"
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        ) : (
                          "-"
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
