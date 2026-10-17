"use client";

import React, { useState } from "react";
import { JobProfile, ProcessedCVResult, RankingResponse, RankedCandidate } from "@/lib/types";
import {
  UploadCloud,
  FileText,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  X,
  Loader2,
  Award,
  ChevronRight,
  User,
  GraduationCap,
  Briefcase,
  Layers,
  ArrowRight,
} from "lucide-react";

interface QuickTestModalProps {
  isOpen: boolean;
  profiles: JobProfile[];
  onClose: () => void;
}

export default function QuickTestModal({
  isOpen,
  profiles,
  onClose,
}: QuickTestModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [processedCV, setProcessedCV] = useState<ProcessedCVResult | null>(null);
  const [divisionRankings, setDivisionRankings] = useState<RankedCandidate[]>([]);
  const [selectedDivisionDetail, setSelectedDivisionDetail] = useState<RankedCandidate | null>(null);

  if (!isOpen) return null;

  const handleFileChange = async (file: File) => {
    const fn = file.name.toLowerCase();
    if (!fn.endsWith(".pdf") && !fn.endsWith(".docx")) {
      setErrorMessage("Harap pilih berkas berekstensi PDF atau DOCX.");
      return;
    }

    setSelectedFile(file);
    setErrorMessage(null);
    setProcessedCV(null);
    setDivisionRankings([]);
    setSelectedDivisionDetail(null);
    setIsProcessing(true);

    try {
      // 1. Baca berkas sebagai Base64
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const result = reader.result as string;
          const b64 = result.split(",")[1];
          resolve(b64);
        };
        reader.onerror = () => reject(new Error("Gagal membaca berkas."));
        reader.readAsDataURL(file);
      });

      // Daftar seluruh divisi aktif dari profil
      const allDivisions = profiles.map((p) => p.division);

      // 2. Ekstrak teks dan field via /api/process
      const procRes = await fetch("/api/process", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          rawBase64: base64,
          filename: file.name,
          mimeType: file.type || (fn.endsWith(".pdf") ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
          candidateName: file.name.replace(/\.[^/.]+$/, ""),
          divisionChoices: allDivisions,
          sourceRowIndex: 1,
        }),
      });

      if (!procRes.ok) {
        const errData = await procRes.json().catch(() => ({}));
        throw new Error(errData.message || `Gagal mengekstrak CV: HTTP ${procRes.status}`);
      }

      const procJson = await procRes.json();
      const cvResult = procJson.result as ProcessedCVResult;
      setProcessedCV(cvResult);

      if (cvResult.error && !cvResult.isScanPdf) {
        throw new Error(cvResult.error);
      }

      // 3. Evaluasi kecocokan di SEMUA profil divisi via /api/rank
      const rankRes = await fetch("/api/rank", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          candidates: [cvResult],
          profiles: profiles,
        }),
      });

      if (!rankRes.ok) {
        const errData = await rankRes.json().catch(() => ({}));
        throw new Error(errData.message || `Gagal menghitung skor: HTTP ${rankRes.status}`);
      }

      const rankJson = await rankRes.json();
      const rankData = rankJson.data as RankingResponse;

      // Kumpulkan hasil evaluasi untuk setiap divisi dan urutkan dari skor tertinggi
      const allRanked: RankedCandidate[] = [];
      for (const divName of allDivisions) {
        const divResults = rankData.divisionResults[divName] || [];
        if (divResults.length > 0) {
          allRanked.push(divResults[0]);
        }
      }

      // Urutkan rekomendasi divisi berdasarkan kecocokan kompetensi dan pemenuhan syarat
      allRanked.sort((a, b) => {
        const aFailed = a.hardRequirementStatus === "Tidak memenuhi";
        const bFailed = b.hardRequirementStatus === "Tidak memenuhi";
        if (aFailed !== bFailed) {
          // Divisi yang gagal syarat wajib ditaruh di bawah divisi yang memenuhi/viable
          return aFailed ? 1 : -1;
        }

        // Bobot status untuk rekomendasi kecocokan
        const getWeight = (c: RankedCandidate) => {
          if (c.hardRequirementStatus === "Memenuhi") return 1.0;
          if (c.hardRequirementStatus === "Perlu dicek") return 0.95;
          if (c.hardRequirementStatus === "Tidak ada syarat wajib") {
            return c.finalScore < 15 ? 0.7 : 0.98;
          }
          return 0.5;
        };

        const scoreA = a.finalScore * getWeight(a);
        const scoreB = b.finalScore * getWeight(b);
        return scoreB - scoreA;
      });

      setDivisionRankings(allRanked);
      if (allRanked.length > 0) {
        setSelectedDivisionDetail(allRanked[0]);
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Terjadi kesalahan saat memproses CV.");
    } finally {
      setIsProcessing(false);
    }
  };

  const bestMatch = divisionRankings.length > 0 ? divisionRankings[0] : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-4xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                Uji Coba Langsung 1 CV (Quick Test)
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-semibold">
                  Tanpa Perlu CSV
                </span>
              </h3>
              <p className="text-xs text-slate-400">
                Unggah 1 berkas CV untuk melihat hasil ekstraksi dan rekomendasi divisi yang paling cocok.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-200">
          {/* Upload Dropzone */}
          <div>
            <label className="border-2 border-dashed border-slate-800 hover:border-indigo-500/50 rounded-2xl p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-slate-950/40 group">
              <UploadCloud className="w-10 h-10 text-slate-600 group-hover:text-indigo-400 transition-colors mb-2" />
              <span className="text-sm font-semibold text-slate-200">
                {selectedFile ? selectedFile.name : "Klik atau seret 1 berkas CV ke sini (PDF / DOCX)"}
              </span>
              <span className="text-xs text-slate-500 mt-1">
                Aplikasi akan mengevaluasi berkas ini ke {profiles.length} profil divisi secara otomatis
              </span>
              <input
                type="file"
                accept=".pdf,.docx"
                disabled={isProcessing}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFileChange(f);
                }}
                className="hidden"
              />
            </label>
          </div>

          {errorMessage && (
            <div className="p-4 rounded-xl bg-red-950/60 border border-red-800 text-red-200 flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {isProcessing && (
            <div className="p-8 rounded-2xl bg-slate-950/60 border border-slate-800 flex flex-col items-center justify-center text-center space-y-3">
              <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
              <div className="font-semibold text-white">Membaca & Membedah Berkas CV...</div>
              <p className="text-slate-400 text-xs max-w-sm">
                Mengekstrak pendidikan, pengalaman kerja, portofolio, dan mencocokkan ke semua profil lowongan...
              </p>
            </div>
          )}

          {/* Result Presentation */}
          {divisionRankings.length > 0 && processedCV && !isProcessing && (
            <div className="space-y-6">
              {/* Top Best Match Highlight Banner */}
              {bestMatch && (
                <div className="p-5 rounded-2xl bg-gradient-to-r from-indigo-950/80 via-slate-900 to-indigo-950/40 border border-indigo-500/40 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start gap-3.5">
                    <div className="w-12 h-12 rounded-2xl bg-indigo-600/30 border border-indigo-400/30 flex items-center justify-center text-indigo-300 shrink-0 shadow-inner">
                      <Award className="w-6 h-6" />
                    </div>
                    <div>
                      <div className="text-[11px] font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Rekomendasi Divisi Paling Cocok</span>
                      </div>
                      <h4 className="text-lg font-bold text-white mt-0.5">
                        Divisi {bestMatch.division}
                      </h4>
                      <p className="text-xs text-slate-300 mt-1 line-clamp-1">
                        {bestMatch.reasons}
                      </p>
                    </div>
                  </div>

                  <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center border-t sm:border-t-0 pt-3 sm:pt-0 border-slate-800">
                    <span className="text-slate-400 text-[11px]">Skor Kecocokan</span>
                    <span className="text-2xl font-mono font-bold text-indigo-400">
                      {bestMatch.finalScore.toFixed(1)}
                      <span className="text-xs font-normal text-slate-500"> / 100</span>
                    </span>
                  </div>
                </div>
              )}

              {/* Extracted Profile Snippet */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <span className="text-slate-500 block mb-0.5">Nama Kandidat</span>
                  <span className="font-semibold text-white">
                    {processedCV.fields.name || "Tidak Terdeteksi"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Pendidikan & IPK</span>
                  <span className="text-slate-200">
                    {processedCV.fields.major || "Jurusan -"}{" "}
                    {processedCV.fields.gpa !== undefined && processedCV.fields.gpa !== null
                      ? `(IPK ${processedCV.fields.gpa.toFixed(2)})`
                      : ""}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Kontak Terbaca</span>
                  <span className="text-slate-200">
                    {processedCV.fields.email || processedCV.fields.phone || "Tidak ditemukan"}
                  </span>
                </div>
              </div>

              {/* Division Match Comparison Grid */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-white flex items-center gap-2">
                    <Layers className="w-4 h-4 text-indigo-400" />
                    <span>Perbandingan Kecocokan di Semua Divisi</span>
                  </h4>
                  <span className="text-slate-500 text-[11px]">
                    Klik divisi untuk melihat rincian nilai
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {divisionRankings.map((cand, idx) => {
                    const isSelected = selectedDivisionDetail?.division === cand.division;
                    const isTop = idx === 0;

                    let statusBadge = (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400">
                        {cand.hardRequirementStatus}
                      </span>
                    );

                    if (cand.hardRequirementStatus === "Memenuhi") {
                      statusBadge = (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                          Memenuhi
                        </span>
                      );
                    } else if (cand.hardRequirementStatus === "Perlu dicek") {
                      statusBadge = (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">
                          Perlu Dicek
                        </span>
                      );
                    } else if (cand.hardRequirementStatus === "Tidak memenuhi") {
                      statusBadge = (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 font-semibold">
                          Tidak Memenuhi
                        </span>
                      );
                    }

                    return (
                      <div
                        key={cand.division}
                        onClick={() => setSelectedDivisionDetail(cand)}
                        className={`p-4 rounded-xl border transition-all cursor-pointer relative ${
                          isSelected
                            ? "bg-indigo-950/40 border-indigo-500 ring-1 ring-indigo-500/50"
                            : "bg-slate-900/70 border-slate-800 hover:border-slate-700"
                        }`}
                      >
                        {isTop && (
                          <div className="absolute top-2 right-2 flex items-center gap-1 text-[10px] font-bold text-amber-400 bg-amber-950/60 px-2 py-0.5 rounded-full border border-amber-800/60">
                            <Sparkles className="w-3 h-3" />
                            <span>Paling Cocok</span>
                          </div>
                        )}

                        <div className="flex items-center justify-between mb-2">
                          <span className="font-bold text-sm text-white">
                            {cand.division}
                          </span>
                        </div>

                        <div className="flex items-baseline gap-1.5 mb-2">
                          <span className="text-xl font-mono font-bold text-indigo-400">
                            {cand.finalScore.toFixed(1)}
                          </span>
                          <span className="text-slate-500 text-[10px]">/ 100</span>
                        </div>

                        <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                          {statusBadge}
                          <span className="text-[11px] text-indigo-400 font-medium flex items-center gap-0.5">
                            Lihat Rincian &rarr;
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Selected Division Detailed Breakdown */}
              {selectedDivisionDetail && (
                <div className="p-5 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                    <div>
                      <h4 className="font-bold text-white text-sm">
                        Rincian Skor untuk Divisi: {selectedDivisionDetail.division}
                      </h4>
                      <p className="text-slate-400 text-[11px] mt-0.5">
                        Status Syarat Wajib:{" "}
                        <span className="font-semibold text-slate-200">
                          {selectedDivisionDetail.hardRequirementStatus}
                        </span>
                      </p>
                    </div>
                    <span className="text-xl font-mono font-bold text-indigo-400">
                      {selectedDivisionDetail.finalScore.toFixed(1)}%
                    </span>
                  </div>

                  {/* 4 Category Breakdown */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                      <span className="text-slate-400 block text-[10px] mb-1">
                        Pengalaman (Relevansi & Durasi)
                      </span>
                      <span className="font-mono font-bold text-slate-200">
                        {selectedDivisionDetail.categoryScores.experience ?? "-"} / 100
                      </span>
                    </div>

                    <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                      <span className="text-slate-400 block text-[10px] mb-1">
                        Project / Portofolio
                      </span>
                      <span className="font-mono font-bold text-slate-200">
                        {selectedDivisionDetail.categoryScores.projects ?? "-"} / 100
                      </span>
                    </div>

                    <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                      <span className="text-slate-400 block text-[10px] mb-1">
                        Sertifikasi & Pendidikan
                      </span>
                      <span className="font-mono font-bold text-slate-200">
                        {selectedDivisionDetail.categoryScores.cert_edu ?? "-"} / 100
                      </span>
                    </div>

                    <div className="p-3 bg-slate-900 rounded-xl border border-slate-800">
                      <span className="text-slate-400 block text-[10px] mb-1">
                        Kompetensi / Skill
                      </span>
                      <span className="font-mono font-bold text-slate-200">
                        {selectedDivisionDetail.categoryScores.competencies ?? "-"} / 100
                      </span>
                    </div>
                  </div>

                  {/* Reasons & Skills */}
                  <div className="space-y-2 text-xs pt-1">
                    <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800 text-slate-300">
                      <span className="font-semibold text-indigo-300 block mb-1">
                        Alasan Penilaian Lengkap:
                      </span>
                      {selectedDivisionDetail.reasons}
                    </div>

                    {selectedDivisionDetail.skillsFound &&
                      selectedDivisionDetail.skillsFound.length > 0 && (
                        <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800 text-slate-300">
                          <span className="font-semibold text-emerald-400 block mb-1">
                            Skill yang Cocok dengan Divisi Ini:
                          </span>
                          <span>{selectedDivisionDetail.skillsFound.join(", ")}</span>
                        </div>
                      )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
          <span className="text-[11px] text-slate-500">
            Hasil screening mandiri ini bersifat simulasi dan tidak mengubah batch rekrutmen.
          </span>
          <button
            onClick={onClose}
            className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs rounded-xl cursor-pointer transition-colors"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
}
