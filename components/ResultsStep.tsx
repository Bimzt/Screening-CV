"use client";

import React, { useState } from "react";
import {
  RankingResponse,
  JobProfile,
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
  const [choiceFilter, setChoiceFilter] = useState<"Semua" | "Pilihan 1" | "Pilihan 2">("Semua");
  const [activeTab, setActiveTab] = useState<"ranking" | "review">("ranking");
  const [expandedCandidateId, setExpandedCandidateId] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  // Peta kandidat lintas divisi agar Pilihan 1 & Pilihan 2 selalu tersinkronisasi (kompatibel data baru & lama)
  const candidatesPeerMap = React.useMemo(() => {
    const map: Record<string, Record<string, typeof rankingData.divisionResults[string][0]>> = {};
    for (const [div, cands] of Object.entries(rankingData.divisionResults || {})) {
      for (const c of cands || []) {
        const key = c.fileId || c.email || (c.sourceRowIndex !== undefined && c.sourceRowIndex !== null ? String(c.sourceRowIndex) : "") || c.name;
        if (key) {
          if (!map[key]) map[key] = {};
          map[key][div] = c;
        }
      }
    }
    return map;
  }, [rankingData]);

  // Helper untuk mendapatkan info komparasi pilihan pelamar
  const getCandidateChoiceInfo = (cand: typeof rankingData.divisionResults[string][0]) => {
    const candKey = cand.fileId || cand.email || (cand.sourceRowIndex !== undefined && cand.sourceRowIndex !== null ? String(cand.sourceRowIndex) : "") || cand.name;
    const peerMap = candidatesPeerMap[candKey] || {};

    let choices = cand.divisionChoices || [];
    if (!choices.length && cand.multiDivisionNote) {
      if (cand.multiDivisionNote.includes("melamar di divisi:")) {
        const other = cand.multiDivisionNote.split("melamar di divisi:")[1]?.split(",") || [];
        choices = [cand.division, ...other.map((d) => d.trim()).filter(Boolean)];
      }
    }

    const p1Name = cand.pilihan1 || choices[0] || cand.division;
    const p2Name = cand.pilihan2 || choices[1];

    let choiceRank = cand.choiceRank;
    if (!choiceRank) {
      choiceRank = p2Name && cand.division === p2Name ? 2 : 1;
    }

    const c1 = cand.choice1Result || peerMap[p1Name] || (cand.division === p1Name ? cand : undefined);
    const c2 = cand.choice2Result || (p2Name ? peerMap[p2Name] : undefined) || (p2Name && cand.division === p2Name ? cand : undefined);

    let bestFitChoice = cand.bestFitChoice;
    if (!bestFitChoice && c1 && c2) {
      bestFitChoice = c2.finalScore > c1.finalScore ? 2 : 1;
    }

    return {
      p1Name,
      p2Name,
      choiceRank,
      c1,
      c2,
      bestFitChoice,
    };
  };

  const currentCandidates = (
    rankingData.divisionResults[selectedDivision] || []
  ).filter((c) => {
    const info = getCandidateChoiceInfo(c);
    if (statusFilter !== "Semua" && c.hardRequirementStatus !== statusFilter) return false;
    if (choiceFilter === "Pilihan 1" && info.choiceRank !== 1) return false;
    if (choiceFilter === "Pilihan 2" && info.choiceRank !== 2) return false;
    return true;
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
        let errMsg = `Gagal mengunduh Excel: HTTP ${res.status}`;
        try {
          const errText = await res.text();
          try {
            const errJson = JSON.parse(errText);
            if (errJson.message) errMsg = errJson.message;
          } catch {
            if (errText) errMsg = `${errMsg} - ${errText.slice(0, 150)}`;
          }
        } catch {
          // ignore
        }
        throw new Error(errMsg);
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
      onStartNewBatch();
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
          {/* Row 1: Division Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto pb-2 border-b border-slate-800/60">
            {divisions.map((div) => (
              <button
                key={div}
                onClick={() => setSelectedDivision(div)}
                className={`px-3.5 py-2 rounded-xl font-medium transition-colors cursor-pointer whitespace-nowrap text-xs flex items-center gap-2 ${
                  selectedDivision === div
                    ? "bg-indigo-600 text-white font-semibold shadow-md shadow-indigo-600/20"
                    : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
                }`}
              >
                <span>{div}</span>
                <span className={`px-1.5 py-0.5 rounded-md text-[10px] font-bold ${
                  selectedDivision === div ? "bg-white/20 text-white" : "bg-slate-800 text-slate-400"
                }`}>
                  {rankingData.divisionResults[div]?.length || 0}
                </span>
              </button>
            ))}
          </div>

          {/* Row 2: Filter Toolbar (Pilihan 1 & 2 + Status Syarat Wajib) */}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs bg-slate-900/60 p-3 rounded-2xl border border-slate-800">
            {/* Filter Pilihan 1 vs Pilihan 2 */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-semibold text-[11px] flex items-center gap-1">
                <Briefcase className="w-3.5 h-3.5 text-indigo-400" />
                Filter Pilihan:
              </span>
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
                {(["Semua", "Pilihan 1", "Pilihan 2"] as const).map((ch) => (
                  <button
                    key={ch}
                    onClick={() => setChoiceFilter(ch)}
                    className={`px-3 py-1 rounded-lg transition-all cursor-pointer text-xs font-semibold ${
                      choiceFilter === ch
                        ? ch === "Pilihan 2"
                          ? "bg-purple-600 text-white shadow-sm"
                          : "bg-indigo-600 text-white shadow-sm"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {ch}
                  </button>
                ))}
              </div>
            </div>

            {/* Filter Status Syarat Wajib */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-semibold text-[11px]">Status Syarat Wajib:</span>
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
                {["Semua", "Memenuhi", "Perlu dicek", "Tidak memenuhi"].map((st) => (
                  <button
                    key={st}
                    onClick={() => setStatusFilter(st)}
                    className={`px-2.5 py-1 rounded-lg transition-colors cursor-pointer text-[11px] ${
                      statusFilter === st
                        ? "bg-indigo-600/30 text-indigo-300 font-bold border border-indigo-500/30"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {st}
                  </button>
                ))}
              </div>
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
                      const info = getCandidateChoiceInfo(cand);
                      const isChoice2 = info.choiceRank === 2;

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
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-white">{cand.name}</span>
                                {isChoice2 ? (
                                  <span className="px-2 py-0.5 rounded-full text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 font-bold">
                                    Pilihan 2
                                  </span>
                                ) : (
                                  <span className="px-2 py-0.5 rounded-full text-[10px] bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-bold">
                                    Pilihan 1
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] text-slate-400">{cand.email || "-"}</div>
                              {info.c1 && info.c2 ? (
                                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px]">
                                  <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">
                                    P1: {info.c1.division} ({info.c1.finalScore.toFixed(1)})
                                  </span>
                                  <span className="text-slate-500">&bull;</span>
                                  <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">
                                    P2: {info.c2.division} ({info.c2.finalScore.toFixed(1)})
                                  </span>
                                  {info.bestFitChoice === 2 && (
                                    <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-semibold">
                                      ⭐ Lebih Cocok di P2
                                    </span>
                                  )}
                                </div>
                              ) : info.p2Name ? (
                                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px]">
                                  <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">
                                    P1: {info.p1Name}
                                  </span>
                                  <span className="text-slate-500">&bull;</span>
                                  <span className="px-1.5 py-0.5 rounded bg-purple-950/40 border border-purple-800/40 text-purple-300 font-medium">
                                    P2: {info.p2Name}
                                  </span>
                                </div>
                              ) : cand.multiDivisionNote ? (
                                <div className="text-[10px] text-indigo-400 font-medium mt-0.5">
                                  {cand.multiDivisionNote}
                                </div>
                              ) : null}
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
                                {/* Dual Choice Comparison Card */}
                                {(info.c1 || info.p2Name) && (
                                  <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-3 mb-2">
                                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                                      <span className="text-xs font-bold text-white flex items-center gap-1.5">
                                        <Briefcase className="w-4 h-4 text-indigo-400" />
                                        Komparasi Hasil: Pilihan 1 vs Pilihan 2
                                      </span>
                                      {info.bestFitChoice === 2 ? (
                                        <span className="text-[11px] font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 rounded-full self-start">
                                          💡 Rekomendasi: Lebih Unggul di Pilihan 2 ({info.p2Name})
                                        </span>
                                      ) : (
                                        <span className="text-[11px] font-semibold text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-0.5 rounded-full self-start">
                                          ✓ Rekomendasi: Sesuai di Pilihan 1 ({info.p1Name})
                                        </span>
                                      )}
                                    </div>

                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                                      {/* Card Pilihan 1 */}
                                      <div className={`p-3 rounded-xl border ${!isChoice2 ? 'border-indigo-500/50 bg-indigo-950/20' : 'border-slate-800 bg-slate-950/40'}`}>
                                        <div className="flex items-center justify-between mb-1">
                                          <span className="font-bold text-white flex items-center gap-1.5">
                                            <span className="w-4 h-4 rounded-full bg-indigo-600/30 text-indigo-300 flex items-center justify-center text-[10px]">1</span>
                                            {info.p1Name}
                                          </span>
                                          <span className="font-mono font-bold text-indigo-400 text-sm">
                                            {info.c1 ? info.c1.finalScore.toFixed(1) : "-"}
                                          </span>
                                        </div>
                                        <div className="text-[11px] text-slate-400 mb-2">
                                          Status Syarat Wajib: <span className="font-semibold text-slate-200">{info.c1?.hardRequirementStatus || "-"}</span>
                                        </div>
                                        {info.c1?.categoryScores && (
                                          <div className="grid grid-cols-2 gap-1 text-[10px] text-slate-400">
                                            <div>Pengalaman: {info.c1.categoryScores.experience ?? "-"}</div>
                                            <div>Project: {info.c1.categoryScores.projects ?? "-"}</div>
                                            <div>Sert & Pend: {info.c1.categoryScores.cert_edu ?? "-"}</div>
                                            <div>Kompetensi: {info.c1.categoryScores.competencies ?? "-"}</div>
                                          </div>
                                        )}
                                      </div>

                                      {/* Card Pilihan 2 */}
                                      <div className={`p-3 rounded-xl border ${isChoice2 ? 'border-purple-500/50 bg-purple-950/20' : 'border-slate-800 bg-slate-950/40'}`}>
                                        <div className="flex items-center justify-between mb-1">
                                          <span className="font-bold text-white flex items-center gap-1.5">
                                            <span className="w-4 h-4 rounded-full bg-purple-600/30 text-purple-300 flex items-center justify-center text-[10px]">2</span>
                                            {info.p2Name || "Tidak Ada"}
                                          </span>
                                          <span className="font-mono font-bold text-purple-400 text-sm">
                                            {info.c2 ? info.c2.finalScore.toFixed(1) : "-"}
                                          </span>
                                        </div>
                                        <div className="text-[11px] text-slate-400 mb-2">
                                          Status Syarat Wajib: <span className="font-semibold text-slate-200">{info.c2?.hardRequirementStatus || "-"}</span>
                                        </div>
                                        {info.c2?.categoryScores && (
                                          <div className="grid grid-cols-2 gap-1 text-[10px] text-slate-400">
                                            <div>Pengalaman: {info.c2.categoryScores.experience ?? "-"}</div>
                                            <div>Project: {info.c2.categoryScores.projects ?? "-"}</div>
                                            <div>Sert & Pend: {info.c2.categoryScores.cert_edu ?? "-"}</div>
                                            <div>Kompetensi: {info.c2.categoryScores.competencies ?? "-"}</div>
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {(cand.recommendationNote || cand.multiDivisionNote) && (
                                      <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] text-slate-300">
                                        <strong className="text-indigo-400">Catatan Komparasi: </strong>
                                        {cand.recommendationNote || cand.multiDivisionNote}
                                      </div>
                                    )}
                                  </div>
                                )}
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
