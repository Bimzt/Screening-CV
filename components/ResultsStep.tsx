"use client";

import React, { useState } from "react";
import {
  RankingResponse,
  JobProfile,
} from "@/lib/types";
import { saveLocalData, clearLocalData } from "@/lib/idb";
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
  Sparkles,
  Award,
  FileText,
  AlertCircle,
  HelpCircle,
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
  const [rankingState, setRankingState] = useState<RankingResponse>(rankingData);
  const divisions = Object.keys(rankingState.divisionResults || {});
  const [selectedDivision, setSelectedDivision] = useState<string>(
    divisions[0] || "Semua"
  );
  const [statusFilter, setStatusFilter] = useState<string>("Semua");
  const [choiceFilter, setChoiceFilter] = useState<"Semua" | "Pilihan 1" | "Pilihan 2">("Semua");
  const [activeTab, setActiveTab] = useState<"ranking" | "review">("ranking");
  const [expandedCandidateId, setExpandedCandidateId] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [isEvaluatingAi, setIsEvaluatingAi] = useState(false);
  const [evaluatingSingleId, setEvaluatingSingleId] = useState<string | null>(null);
  const [aiSuccessMessage, setAiSuccessMessage] = useState<string | null>(null);

  React.useEffect(() => {
    setRankingState(rankingData);
  }, [rankingData]);

  // Peta kandidat lintas divisi agar Pilihan 1 & Pilihan 2 selalu tersinkronisasi
  const candidatesPeerMap = React.useMemo(() => {
    const map: Record<string, Record<string, typeof rankingState.divisionResults[string][0]>> = {};
    for (const [div, cands] of Object.entries(rankingState.divisionResults || {})) {
      for (const c of cands || []) {
        const key = c.fileId || c.email || (c.sourceRowIndex !== undefined && c.sourceRowIndex !== null ? String(c.sourceRowIndex) : "") || c.name;
        if (key) {
          if (!map[key]) map[key] = {};
          map[key][div] = c;
        }
      }
    }
    return map;
  }, [rankingState]);

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
    rankingState.divisionResults[selectedDivision] || []
  ).filter((c) => {
    const info = getCandidateChoiceInfo(c);
    if (statusFilter !== "Semua" && c.hardRequirementStatus !== statusFilter) return false;
    if (choiceFilter === "Pilihan 1" && info.choiceRank !== 1) return false;
    if (choiceFilter === "Pilihan 2" && info.choiceRank !== 2) return false;
    return true;
  });

  const handleRunGeminiAssessment = async () => {
    const currentList = rankingState.divisionResults[selectedDivision] || [];
    if (currentList.length === 0) return;

    const currentProfile = profiles.find(
      (p) => p.division.toLowerCase() === selectedDivision.toLowerCase()
    ) || { division: selectedDivision, title: selectedDivision, jd: "" };

    setIsEvaluatingAi(true);
    setAiSuccessMessage(null);

    try {
      const top10 = currentList.slice(0, 10);
      const res = await fetch("/api/evaluate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          division: selectedDivision,
          candidates: top10,
          profile: currentProfile,
          maxCandidates: 10,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.message || `HTTP ${res.status}`);
      }

      const jsonRes = await res.json();
      const aiEvals = jsonRes.data || {};
      const modelUsed = jsonRes.modelUsed || "Gemini";

      const updatedList = currentList.map((cand) => {
        const cKey = String(cand.fileId || cand.email || cand.sourceRowIndex || cand.rank || "");
        const ev = aiEvals[cKey] || aiEvals[String(cand.rank)];
        if (ev) {
          const summary = ev.executiveSummary || "";
          return {
            ...cand,
            aiEvaluation: {
              ...ev,
              modelUsed: ev.modelUsed || modelUsed,
            },
            reasons: cand.reasons.includes("[✨ AI:")
              ? cand.reasons
              : `[✨ AI: ${summary}] | ${cand.reasons}`,
          };
        }
        return cand;
      });

      const updatedRanking: RankingResponse = {
        ...rankingState,
        divisionResults: {
          ...rankingState.divisionResults,
          [selectedDivision]: updatedList,
        },
      };

      setRankingState(updatedRanking);
      await saveLocalData("last_ranking_response", updatedRanking);
      setAiSuccessMessage(`Berhasil mengevaluasi 10 kandidat teratas divisi ${selectedDivision} dengan ${modelUsed}!`);
      if (updatedList.length > 0) {
        setExpandedCandidateId(updatedList[0].fileId);
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Gagal mengevaluasi dengan Gemini AI");
    } finally {
      setIsEvaluatingAi(false);
    }
  };

  const handleEvaluateSingleCandidate = async (cand: typeof rankingState.divisionResults[string][0]) => {
    const currentProfile = profiles.find(
      (p) => p.division.toLowerCase() === cand.division.toLowerCase()
    ) || { division: cand.division, title: cand.division, jd: "" };

    setEvaluatingSingleId(cand.fileId);
    try {
      const res = await fetch("/api/evaluate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          division: cand.division,
          candidates: [cand],
          profile: currentProfile,
          maxCandidates: 1,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.message || `HTTP ${res.status}`);
      }

      const jsonRes = await res.json();
      const aiEvals = jsonRes.data || {};
      const modelUsed = jsonRes.modelUsed || "Gemini";
      const cKey = String(cand.fileId || cand.email || cand.sourceRowIndex || cand.rank || "");
      const ev = aiEvals[cKey] || Object.values(aiEvals)[0];

      if (ev) {
        const evObj = ev as any;
        const summary = evObj.executiveSummary || "";
        const divList = rankingState.divisionResults[cand.division] || [];
        const updatedList = divList.map((c) => {
          if (c.fileId === cand.fileId) {
            return {
              ...c,
              aiEvaluation: {
                ...evObj,
                modelUsed: evObj.modelUsed || modelUsed,
              },
              reasons: c.reasons.includes("[✨ AI:") ? c.reasons : `[✨ AI: ${summary}] | ${c.reasons}`,
            };
          }
          return c;
        });

        const updatedRanking: RankingResponse = {
          ...rankingState,
          divisionResults: {
            ...rankingState.divisionResults,
            [cand.division]: updatedList,
          },
        };
        setRankingState(updatedRanking);
        await saveLocalData("last_ranking_response", updatedRanking);
        setExpandedCandidateId(cand.fileId);
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Gagal mengevaluasi kandidat dengan Gemini AI");
    } finally {
      setEvaluatingSingleId(null);
    }
  };

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
          rankingData: rankingState,
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
            onClick={handleRunGeminiAssessment}
            disabled={isEvaluatingAi || currentCandidates.length === 0}
            className="px-4 py-2 bg-gradient-to-r from-amber-500/20 via-indigo-500/20 to-purple-500/20 hover:from-amber-500/30 hover:to-purple-500/30 border border-amber-500/40 text-amber-300 rounded-xl text-xs font-semibold flex items-center gap-2 shadow-lg shadow-amber-500/10 transition-all cursor-pointer disabled:opacity-50"
            title="Jalankan Evaluasi AI (Google Gemini) untuk 10 kandidat teratas divisi ini"
          >
            <Sparkles className="w-4 h-4 text-amber-400 animate-pulse" />
            <span>{isEvaluatingAi ? "Menganalisis Gemini..." : "✨ Evaluasi AI Gemini"}</span>
          </button>

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

      {aiSuccessMessage && (
        <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-500/30 text-xs text-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-md">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="font-medium">{aiSuccessMessage}</span>
          </div>
          <span className="text-[11px] text-amber-300 bg-amber-500/10 px-2.5 py-1 rounded-lg border border-amber-500/25 font-semibold shrink-0">
            👇 Hasil tampil di kolom &quot;Evaluasi AI (Gemini)&quot; &amp; klik baris pelamar untuk buka telaah lengkap
          </span>
        </div>
      )}

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

          {/* Active AI Status Pill */}
          {currentCandidates.some(c => c.aiEvaluation) && (
            <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-gradient-to-r from-amber-500/10 via-indigo-500/10 to-purple-500/10 border border-amber-500/30 text-xs">
              <div className="flex items-center gap-2 text-amber-300 font-medium">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <span>
                  Evaluasi Kontekstual Aktif: <strong>{currentCandidates.find(c => c.aiEvaluation)?.aiEvaluation?.modelUsed || "Google Gemini"}</strong> menganalisis kesiapan kerja kandidat teratas.
                </span>
              </div>
              <span className="text-[10px] text-amber-200/80 bg-amber-500/10 px-2 py-0.5 rounded-md border border-amber-500/20">
                Tier 2 AI Active
              </span>
            </div>
          )}

          {/* Candidates Table */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-200">
                <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 font-semibold">
                  <tr>
                    <th className="py-3 px-4 w-12 text-center">Rank</th>
                    <th className="py-3 px-4">Nama Pelamar</th>
                    <th className="py-3 px-4">Kampus &amp; Jurusan</th>
                    <th className="py-3 px-4 text-center">IPK</th>
                    <th className="py-3 px-4 text-center">Skor Akhir</th>
                    <th className="py-3 px-4">Syarat Wajib</th>
                    <th className="py-3 px-4 min-w-[220px]">
                      <div className="flex items-center gap-1.5 text-amber-300">
                        <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                        <span>Evaluasi AI (Gemini)</span>
                      </div>
                    </th>
                    <th className="py-3 px-4">Alasan Penilaian</th>
                    <th className="py-3 px-4 text-center">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {currentCandidates.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="py-12 text-center text-slate-500">
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
                          <tr
                            onClick={() =>
                              setExpandedCandidateId(isExpanded ? null : cand.fileId)
                            }
                            className={`hover:bg-slate-800/40 transition-colors cursor-pointer ${
                              isExpanded ? "bg-slate-800/25" : ""
                            }`}
                          >
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
                                {cand.aiEvaluation && (
                                  <span
                                    className="px-2 py-0.5 rounded-full text-[10px] bg-gradient-to-r from-amber-500/20 to-indigo-500/20 text-amber-300 border border-amber-500/30 font-bold flex items-center gap-1"
                                    title={`Evaluated by ${cand.aiEvaluation.modelUsed || "Gemini"}`}
                                  >
                                    <Sparkles className="w-2.5 h-2.5 text-amber-400" />
                                    <span>AI: {cand.aiEvaluation.modelUsed ? cand.aiEvaluation.modelUsed.replace("gemini-", "") : "Gemini"}</span>
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

                            {/* NEW DEDICATED COLUMN: Evaluasi AI (Gemini) */}
                            <td className="py-3 px-4 min-w-[220px] max-w-xs">
                              {cand.aiEvaluation ? (
                                <div className="space-y-1">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span
                                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                        cand.aiEvaluation.practicalLevel === "Tinggi"
                                          ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                                          : cand.aiEvaluation.practicalLevel === "Sedang"
                                          ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
                                          : "bg-slate-800 text-slate-300 border-slate-700"
                                      }`}
                                    >
                                      Praktikal: {cand.aiEvaluation.practicalLevel || "Sedang"}
                                    </span>
                                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/20 font-mono font-bold">
                                      Skor AI: {cand.aiEvaluation.contextualScore ?? cand.finalScore.toFixed(0)}/100
                                    </span>
                                  </div>
                                  <p className="text-[11px] text-slate-300 line-clamp-2 leading-snug">
                                    {cand.aiEvaluation.keyStrength || cand.aiEvaluation.executiveSummary || "Kandidat telah dievaluasi oleh Gemini."}
                                  </p>
                                  <span className="text-[10px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-0.5">
                                    <span>Klik baris untuk telaah lengkap</span>
                                    <ChevronDown className="w-3 h-3" />
                                  </span>
                                </div>
                              ) : (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleEvaluateSingleCandidate(cand);
                                  }}
                                  disabled={evaluatingSingleId === cand.fileId}
                                  className="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 text-[11px] font-medium flex items-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
                                  title="Evaluasi kandidat ini dengan Gemini AI"
                                >
                                  <Sparkles className="w-3 h-3 text-amber-400" />
                                  <span>{evaluatingSingleId === cand.fileId ? "Menganalisis..." : "✨ Evaluasi AI"}</span>
                                </button>
                              )}
                            </td>

                            <td className="py-3 px-4 max-w-xs text-[11px] text-slate-400 truncate">
                              {cand.reasons}
                            </td>
                            <td className="py-3 px-4 text-center">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setExpandedCandidateId(isExpanded ? null : cand.fileId);
                                }}
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
                              <td colSpan={9} className="p-4 space-y-3 border-t border-slate-800">
                                {/* Tier 2 AI Contextual Assessment Card (Comprehensive HR View) */}
                                {cand.aiEvaluation ? (
                                  <div className="p-4 rounded-2xl bg-gradient-to-br from-slate-900 via-amber-950/20 to-indigo-950/20 border border-amber-500/30 space-y-3.5 mb-3 shadow-lg">
                                    {/* Header Info */}
                                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2.5 border-b border-amber-500/20">
                                      <div className="flex items-center gap-2.5">
                                        <div className="w-7 h-7 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center shrink-0">
                                          <Sparkles className="w-4 h-4 text-amber-400" />
                                        </div>
                                        <div>
                                          <h4 className="text-xs font-bold text-white flex items-center gap-2">
                                            <span>Hasil Evaluasi Mendalam AI: {cand.name}</span>
                                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-normal">
                                              Model: {cand.aiEvaluation.modelUsed || "gemini-3.8-flash"}
                                            </span>
                                          </h4>
                                          <p className="text-[11px] text-slate-400">
                                            Penilaian semantik kesiapan kerja riil &amp; relevansi proyek terhadap Job Description {cand.division}
                                          </p>
                                        </div>
                                      </div>
                                      <div className="flex items-center gap-2 self-start sm:self-auto flex-wrap">
                                        <span className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-700 text-slate-300">
                                          Kesiapan Praktikal:{" "}
                                          <strong className={
                                            cand.aiEvaluation.practicalLevel === "Tinggi"
                                              ? "text-emerald-400"
                                              : cand.aiEvaluation.practicalLevel === "Sedang"
                                              ? "text-amber-400"
                                              : "text-slate-300"
                                          }>
                                            {cand.aiEvaluation.practicalLevel || "Sedang"}
                                          </strong>
                                        </span>
                                        <span className="text-[11px] px-2.5 py-1 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-300 font-mono font-bold">
                                          Skor AI: {cand.aiEvaluation.contextualScore ?? cand.finalScore.toFixed(0)}/100
                                        </span>
                                        <button
                                          type="button"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            handleEvaluateSingleCandidate(cand);
                                          }}
                                          disabled={evaluatingSingleId === cand.fileId}
                                          className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-[11px] font-medium flex items-center gap-1 transition-colors cursor-pointer"
                                          title="Analisis ulang dengan Gemini AI"
                                        >
                                          <RotateCcw className={`w-3 h-3 ${evaluatingSingleId === cand.fileId ? "animate-spin" : ""}`} />
                                          <span>{evaluatingSingleId === cand.fileId ? "Menganalisis..." : "Evaluasi Ulang"}</span>
                                        </button>
                                      </div>
                                    </div>

                                    {/* Section 1: Ringkasan Eksekutif & Analisis Kesiapan Kerja */}
                                    <div className="space-y-1.5">
                                      <div className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                                        <FileText className="w-3.5 h-3.5 text-indigo-400" />
                                        <span>Analisis Eksekutif &amp; Kesiapan Kerja Praktis</span>
                                      </div>
                                      <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs text-slate-200 leading-relaxed">
                                        <p className="whitespace-pre-line">
                                          {cand.aiEvaluation.executiveSummary || "Kandidat telah dievaluasi memiliki kesesuaian terhadap profil divisi."}
                                        </p>
                                      </div>
                                    </div>

                                    {/* Section 2: Keunggulan Kompetitif Utama */}
                                    {cand.aiEvaluation.keyStrength && (
                                      <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-start gap-2.5 text-xs">
                                        <Award className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                                        <div>
                                          <span className="font-bold text-amber-300">Keunggulan Kompetitif Utama: </span>
                                          <span className="text-amber-100/90 leading-relaxed">{cand.aiEvaluation.keyStrength}</span>
                                        </div>
                                      </div>
                                    )}

                                    {/* Grid: Bukti Kekuatan Nyata & Catatan Validasi Interview */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                                      {/* Bukti Kekuatan Nyata */}
                                      <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2">
                                        <span className="font-bold text-emerald-400 flex items-center gap-1.5 text-[11px]">
                                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                                          Bukti Kekuatan Teknis &amp; Pengalaman Nyata
                                        </span>
                                        {cand.aiEvaluation.strengths && cand.aiEvaluation.strengths.length > 0 ? (
                                          <ul className="space-y-1.5 pl-1">
                                            {cand.aiEvaluation.strengths.map((strItem, sIdx) => (
                                              <li key={sIdx} className="text-slate-300 flex items-start gap-2 text-[11px] leading-relaxed">
                                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0 mt-1.5" />
                                                <span>{strItem}</span>
                                              </li>
                                            ))}
                                          </ul>
                                        ) : (
                                          <p className="text-[11px] text-slate-400 italic">
                                            Terdapat bukti kepemilikan proyek/pengalaman relevan pada portofolio dan rekam jejak CV.
                                          </p>
                                        )}
                                      </div>

                                      {/* Catatan Validasi Wawancara */}
                                      <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2">
                                        <span className="font-bold text-amber-400 flex items-center gap-1.5 text-[11px]">
                                          <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                                          Poin Validasi Saat Wawancara (Area to Probe)
                                        </span>
                                        {cand.aiEvaluation.areasToProbe && cand.aiEvaluation.areasToProbe.length > 0 ? (
                                          <ul className="space-y-1.5 pl-1">
                                            {cand.aiEvaluation.areasToProbe.map((probeItem, pIdx) => (
                                              <li key={pIdx} className="text-slate-300 flex items-start gap-2 text-[11px] leading-relaxed">
                                                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0 mt-1.5" />
                                                <span>{probeItem}</span>
                                              </li>
                                            ))}
                                          </ul>
                                        ) : (
                                          <p className="text-[11px] text-slate-400 italic">
                                            Konfirmasi kontribusi individu vs kerja tim pada proyek portofolio utama saat wawancara.
                                          </p>
                                        )}
                                      </div>
                                    </div>

                                    {/* Section 4: Rekomendasi Pertanyaan Interview */}
                                    {cand.aiEvaluation.interviewQuestion && (
                                      <div className="p-3 rounded-xl bg-indigo-950/30 border border-indigo-500/30 space-y-1 text-xs">
                                        <div className="text-[11px] font-bold text-indigo-300 flex items-center gap-1.5">
                                          <HelpCircle className="w-3.5 h-3.5 text-indigo-400" />
                                          <span>Rekomendasi Pertanyaan Teknis/Situasional untuk Rekruter:</span>
                                        </div>
                                        <p className="text-slate-200 italic pl-5 leading-relaxed text-[11px]">
                                          &ldquo;{cand.aiEvaluation.interviewQuestion}&rdquo;
                                        </p>
                                      </div>
                                    )}
                                  </div>
                                ) : (
                                  <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2">
                                    <div className="text-xs text-slate-400 flex items-center gap-2">
                                      <Sparkles className="w-4 h-4 text-slate-500" />
                                      <span>Belum ada evaluasi AI untuk kandidat ini. Analisis mendalam akan menilai bukti proyek riil, kekuatan teknis, dan panduan wawancara.</span>
                                    </div>
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleEvaluateSingleCandidate(cand);
                                      }}
                                      disabled={evaluatingSingleId === cand.fileId}
                                      className="px-3.5 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer self-start sm:self-auto disabled:opacity-50 shrink-0"
                                    >
                                      <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                                      <span>{evaluatingSingleId === cand.fileId ? "Menganalisis..." : "✨ Evaluasi dengan Gemini"}</span>
                                    </button>
                                  </div>
                                )}

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
