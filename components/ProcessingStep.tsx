"use client";

import React, { useEffect, useRef, useState } from "react";
import { RawCsvRow } from "@/lib/csv";
import { JobProfile, ProcessedCVResult, RankingResponse } from "@/lib/types";
import { ConcurrencyPool, PoolProgress } from "@/lib/pool";
import { saveLocalData } from "@/lib/idb";
import { Loader2, AlertTriangle, Clock } from "lucide-react";

interface ProcessingStepProps {
  rows: RawCsvRow[];
  profiles: JobProfile[];
  onFinish: (rankingResponse: RankingResponse, processedCVs: ProcessedCVResult[]) => void;
  onCancel: () => void;
}

export default function ProcessingStep({
  rows,
  profiles,
  onFinish,
  onCancel,
}: ProcessingStepProps) {
  const poolRef = useRef<ConcurrencyPool | null>(null);
  const [progress, setProgress] = useState<PoolProgress>({
    completed: 0,
    total: rows.length,
    successCount: 0,
    failedCount: 0,
    isCancelled: false,
    isFinished: false,
  });
  const [isRanking, setIsRanking] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const pool = new ConcurrencyPool(4);
    poolRef.current = pool;

    pool
      .processBatch(rows, (p) => {
        if (isMounted) setProgress(p);
      })
      .then(async (results) => {
        if (!isMounted || poolRef.current?.["isCancelled"]) return;

        // Simpan hasil parsial ke IndexedDB
        await saveLocalData("last_processed_cvs", results);

        setIsRanking(true);

        // Panggil endpoint /api/rank
        try {
          const res = await fetch("/api/rank", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify({
              candidates: results,
              profiles: profiles,
            }),
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.message || `HTTP ${res.status}`);
          }

          const rankData = await res.json();
          await saveLocalData("last_ranking_response", rankData.data);

          if (isMounted) {
            onFinish(rankData.data, results);
          }
        } catch (err: unknown) {
          if (isMounted) {
            setErrorMessage(
              err instanceof Error ? err.message : "Gagal memproses kalkulasi ranking batch."
            );
          }
        } finally {
          if (isMounted) setIsRanking(false);
        }
      });

    return () => {
      isMounted = false;
      pool.cancel();
    };
  }, [rows, profiles, onFinish]);

  const handleCancelClick = () => {
    poolRef.current?.cancel();
    onCancel();
  };

  const pct = Math.round((progress.completed / (progress.total || 1)) * 100);

  return (
    <div className="max-w-2xl mx-auto py-12 px-4 space-y-6">
      <div className="p-8 rounded-2xl bg-slate-900/80 border border-slate-800 text-center space-y-6 shadow-2xl relative overflow-hidden">
        {/* Ambient background glow */}
        <div className="absolute -top-20 left-1/2 -translate-x-1/2 w-60 h-60 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col items-center">
          <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 mb-4 shadow-inner">
            <Loader2 className="w-8 h-8 animate-spin" />
          </div>
          <h2 className="text-xl font-bold text-white">
            {isRanking ? "Menghitung Skor & Ranking..." : "Sedang Menyaring CV..."}
          </h2>
          <p className="text-xs text-slate-400 mt-1 max-w-sm">
            {isRanking
              ? "Menyesuaikan model TF-IDF, mengevaluasi hard requirements, dan menyusun peringkat per divisi..."
              : `Memproses ${progress.completed} dari ${progress.total} berkas CV dengan 4 worker simultan.`}
          </p>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Progres Batch</span>
            <span className="font-mono font-bold text-indigo-400">{pct}%</span>
          </div>
          <div className="h-3 w-full bg-slate-950 rounded-full overflow-hidden border border-slate-800 p-0.5">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-indigo-400 rounded-full transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Real-time stats */}
        <div className="grid grid-cols-3 gap-3 text-xs pt-2">
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80">
            <span className="text-slate-400 block mb-1">Berhasil</span>
            <span className="font-mono text-emerald-400 font-bold text-base">
              {progress.successCount}
            </span>
          </div>
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80">
            <span className="text-slate-400 block mb-1">Perlu Cek / Scan</span>
            <span className="font-mono text-amber-400 font-bold text-base">
              {progress.failedCount}
            </span>
          </div>
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80">
            <span className="text-slate-400 block mb-1">Estimasi Sisa</span>
            <span className="font-mono text-slate-300 font-bold text-base flex items-center justify-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              {progress.estimatedRemainingSeconds !== undefined
                ? `${progress.estimatedRemainingSeconds}s`
                : "..."}
            </span>
          </div>
        </div>

        {/* Active item */}
        {progress.currentName && !isRanking && (
          <div className="text-xs text-slate-400 font-mono truncate">
            Sedang membaca: <span className="text-indigo-300">{progress.currentName}</span>
          </div>
        )}

        {errorMessage && (
          <div className="p-4 rounded-xl bg-red-950/60 border border-red-800 text-red-200 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Cancel Button */}
        <div>
          <button
            onClick={handleCancelClick}
            className="px-5 py-2 text-xs font-semibold text-slate-400 hover:text-red-400 rounded-xl border border-slate-800 hover:bg-slate-800 transition-colors cursor-pointer"
          >
            Batalkan Screening
          </button>
        </div>
      </div>
    </div>
  );
}
