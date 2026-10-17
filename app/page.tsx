"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { JobProfile, ProcessedCVResult, RankingResponse } from "@/lib/types";
import { RawCsvRow } from "@/lib/csv";
import { DEFAULT_EXAMPLE_PROFILES } from "@/lib/defaultProfiles";
import { getLocalData, saveLocalData } from "@/lib/idb";
import ProfileManager from "@/components/ProfileManager";
import CsvStep from "@/components/CsvStep";
import ProcessingStep from "@/components/ProcessingStep";
import ResultsStep from "@/components/ResultsStep";
import QuickTestModal from "@/components/QuickTestModal";
import {
  FileText,
  LogOut,
  ShieldCheck,
  AlertTriangle,
  Briefcase,
  UploadCloud,
  Loader2,
  Award,
  ChevronRight,
  Server,
  Sparkles,
} from "lucide-react";

type ActiveStep = "profiles" | "csv" | "processing" | "results";

export default function HomePage() {
  const router = useRouter();

  const [currentStep, setCurrentStep] = useState<ActiveStep>("profiles");
  const [profiles, setProfiles] = useState<JobProfile[]>(DEFAULT_EXAMPLE_PROFILES);
  const [csvRowsToProcess, setCsvRowsToProcess] = useState<RawCsvRow[]>([]);
  const [processedCVs, setProcessedCVs] = useState<ProcessedCVResult[]>([]);
  const [rankingData, setRankingData] = useState<RankingResponse | null>(null);
  const [isQuickTestOpen, setIsQuickTestOpen] = useState(false);


  // Muat data lokal jika ada
  useEffect(() => {
    async function loadStored() {
      const savedProfiles = await getLocalData<JobProfile[]>("profiles_state");
      if (savedProfiles && savedProfiles.length >= DEFAULT_EXAMPLE_PROFILES.length) {
        setProfiles(savedProfiles);
      } else {
        setProfiles(DEFAULT_EXAMPLE_PROFILES);
        saveLocalData("profiles_state", DEFAULT_EXAMPLE_PROFILES);
      }
      const savedRank = await getLocalData<RankingResponse>("last_ranking_response");
      if (savedRank) {
        setRankingData(savedRank);
      }
    }
    loadStored();
  }, []);

  const handleProfilesChange = (updated: JobProfile[]) => {
    setProfiles(updated);
    saveLocalData("profiles_state", updated);
  };

  const handleStartProcessing = (rows: RawCsvRow[]) => {
    setCsvRowsToProcess(rows);
    setCurrentStep("processing");
  };

  const handleProcessingFinish = (
    ranking: RankingResponse,
    cvResults: ProcessedCVResult[]
  ) => {
    setRankingData(ranking);
    setProcessedCVs(cvResults);
    setCurrentStep("results");
  };

  const handleLogout = async () => {
    try {
      await fetch("/auth/logout", { method: "POST" });
    } finally {
      router.push("/login");
      router.refresh();
    }
  };

  const stepsList = [
    { id: "profiles", label: "1. Profil Lowongan", icon: Briefcase },
    { id: "csv", label: "2. Unggah & Petakan CSV", icon: UploadCloud },
    { id: "processing", label: "3. Proses Screening", icon: Loader2 },
    { id: "results", label: "4. Hasil & Ekspor Excel", icon: Award },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="font-bold text-base text-white tracking-tight flex items-center gap-2">
                CV Screener
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  V1.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400">Soko Financial &bull; Internal Recruitment</p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setIsQuickTestOpen(true)}
              className="px-3.5 py-1.5 bg-gradient-to-r from-indigo-600/30 to-purple-600/30 text-indigo-300 hover:text-white border border-indigo-500/40 hover:border-indigo-400 rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Uji Coba 1 CV (Quick Test)</span>
            </button>

            <div className="hidden sm:flex items-center gap-1.5 text-xs bg-emerald-950/40 border border-emerald-800/50 text-emerald-400 px-3 py-1.5 rounded-lg">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Sesi Terverifikasi</span>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Keluar</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-8 space-y-6">
        {/* Recruitment Ethics Notice */}
        <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-800/50 text-amber-200/90 text-xs flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="leading-relaxed">
            <span className="font-bold text-amber-300">Pernyataan Etika Rekrutmen:</span>{" "}
            Skor adalah alat bantu pengurutan, bukan keputusan otomatis. Rekruter yang menentukan keputusan akhir.
            Aplikasi tidak menilai kualitas portofolio visual/konten dan tidak menyertakan data pribadi (nama, foto, gender, usia, agama, alamat, atau nama kampus) dalam perhitungan skor.
          </div>
        </div>

        {/* Wizard Step Navigation */}
        <div className="p-2 bg-slate-900/50 border border-slate-800/80 rounded-2xl flex items-center justify-between overflow-x-auto text-xs">
          {stepsList.map((step, idx) => {
            const Icon = step.icon;
            const isActive = currentStep === step.id;
            return (
              <React.Fragment key={step.id}>
                <button
                  onClick={() => {
                    if (step.id === "results" && !rankingData) return;
                    if (step.id === "processing") return;
                    setCurrentStep(step.id as ActiveStep);
                  }}
                  disabled={
                    (step.id === "results" && !rankingData) ||
                    step.id === "processing"
                  }
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all cursor-pointer whitespace-nowrap ${
                    isActive
                      ? "bg-indigo-600 text-white font-semibold shadow-md shadow-indigo-600/20"
                      : "text-slate-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{step.label}</span>
                </button>
                {idx < stepsList.length - 1 && (
                  <ChevronRight className="w-4 h-4 text-slate-700 shrink-0 mx-1 hidden sm:block" />
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Dynamic Step View */}
        {currentStep === "profiles" && (
          <ProfileManager
            profiles={profiles}
            onProfilesChange={handleProfilesChange}
            onProceedToCsv={() => setCurrentStep("csv")}
          />
        )}

        {currentStep === "csv" && (
          <CsvStep
            profiles={profiles}
            onStartProcessing={handleStartProcessing}
            onBackToProfiles={() => setCurrentStep("profiles")}
            onOpenQuickTest={() => setIsQuickTestOpen(true)}
          />
        )}

        {currentStep === "processing" && (
          <ProcessingStep
            rows={csvRowsToProcess}
            profiles={profiles}
            onFinish={handleProcessingFinish}
            onCancel={() => setCurrentStep("csv")}
          />
        )}

        {currentStep === "results" && rankingData && (
          <ResultsStep
            rankingData={rankingData}
            profiles={profiles}
            onStartNewBatch={() => {
              setCurrentStep("csv");
            }}
          />
        )}

        {/* Quick Test Modal */}
        <QuickTestModal
          isOpen={isQuickTestOpen}
          profiles={profiles}
          onClose={() => setIsQuickTestOpen(false)}
        />
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
        CV Screener V1.0 &bull; Soko Financial &bull; Zero Server Storage &bull; Data Terenkripsi & Dirahasiakan
      </footer>
    </div>
  );
}
