"use client";

import React, { useRef, useState } from "react";
import { JobProfile } from "@/lib/types";
import { parseAndValidateProfileJson } from "@/lib/profile";
import { DEFAULT_EXAMPLE_PROFILES } from "@/lib/defaultProfiles";
import ProfileEditorModal from "./ProfileEditorModal";
import {
  Plus,
  Upload,
  Download,
  Edit2,
  Trash2,
  Sparkles,
  AlertCircle,
  Briefcase,
  CheckCircle,
} from "lucide-react";

interface ProfileManagerProps {
  profiles: JobProfile[];
  onProfilesChange: (profiles: JobProfile[]) => void;
  onProceedToCsv: () => void;
}

export default function ProfileManager({
  profiles,
  onProfilesChange,
  onProceedToCsv,
}: ProfileManagerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [editingProfile, setEditingProfile] = useState<JobProfile | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

  const handleLoadExamples = () => {
    onProfilesChange(DEFAULT_EXAMPLE_PROFILES);
    setImportError(null);
  };

  const handleSaveProfile = (updated: JobProfile) => {
    const existingIndex = profiles.findIndex((p) => p.division === updated.division);
    if (existingIndex >= 0) {
      const next = [...profiles];
      next[existingIndex] = updated;
      onProfilesChange(next);
    } else {
      onProfilesChange([...profiles, updated]);
    }
  };

  const handleDeleteProfile = (division: string) => {
    onProfilesChange(profiles.filter((p) => p.division !== division));
  };

  const handleExportAll = () => {
    const jsonStr = JSON.stringify(profiles, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `CV_Screener_Profiles_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      setImportError(null);

      try {
        const parsed = JSON.parse(content);
        if (Array.isArray(parsed)) {
          // Impor array profil
          const validProfiles: JobProfile[] = [];
          for (let i = 0; i < parsed.length; i++) {
            const itemStr = JSON.stringify(parsed[i]);
            const res = parseAndValidateProfileJson(itemStr);
            if (!res.valid || !res.profile) {
              setImportError(`Profil ke-${i + 1} tidak valid: ${res.error}`);
              return;
            }
            validProfiles.push(res.profile);
          }
          onProfilesChange(validProfiles);
        } else {
          // Impor single profil
          const res = parseAndValidateProfileJson(content);
          if (!res.valid || !res.profile) {
            setImportError(res.error || "Format profil tidak valid.");
            return;
          }
          const existingIdx = profiles.findIndex((p) => p.division === res.profile!.division);
          if (existingIdx >= 0) {
            const next = [...profiles];
            next[existingIdx] = res.profile!;
            onProfilesChange(next);
          } else {
            onProfilesChange([...profiles, res.profile!]);
          }
        }
      } catch {
        setImportError("Gagal membaca berkas JSON profil.");
      }
    };
    reader.readAsText(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="space-y-6">
      {/* Action Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-indigo-400" />
            Profil Lowongan Divisi
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Konfigurasi kriteria penilaian dan JD untuk setiap divisi pelamar.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleLoadExamples}
            className="px-3.5 py-2 bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600/30 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Mulai dari Contoh (10 Divisi)</span>
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleImportFile}
            className="hidden"
          />

          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-3.5 py-2 bg-slate-800 text-slate-300 hover:text-white border border-slate-700 hover:bg-slate-700 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Impor JSON</span>
          </button>

          {profiles.length > 0 && (
            <button
              onClick={handleExportAll}
              className="px-3.5 py-2 bg-slate-800 text-slate-300 hover:text-white border border-slate-700 hover:bg-slate-700 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Ekspor JSON</span>
            </button>
          )}

          <button
            onClick={() => {
              setEditingProfile(null);
              setIsModalOpen(true);
            }}
            className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Tambah Divisi</span>
          </button>
        </div>
      </div>

      {importError && (
        <div className="p-4 rounded-xl bg-red-950/60 border border-red-800 text-red-200 text-xs flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{importError}</span>
        </div>
      )}

      {/* Profiles Cards Grid */}
      {profiles.length === 0 ? (
        <div className="text-center py-16 px-4 rounded-2xl border border-dashed border-slate-800 bg-slate-900/20 space-y-3">
          <Briefcase className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-sm font-semibold text-slate-300">Belum Ada Profil Lowongan</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Klik tombol &ldquo;Mulai dari Contoh&rdquo; untuk memuat 5 profil standar HR (HRTA, HROD, Sosmed, CS, Data Analyst), atau buat profil baru.
          </p>
          <button
            onClick={handleLoadExamples}
            className="mt-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold cursor-pointer"
          >
            Muat Contoh Profil
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {profiles.map((p) => {
            const hardCount =
              (p.hardRequirements?.minGpa ? 1 : 0) +
              (p.hardRequirements?.allowedMajors?.length ? 1 : 0) +
              (p.hardRequirements?.mandatorySkills?.items?.length ? 1 : 0);

            return (
              <div
                key={p.division}
                className="bg-slate-900/70 border border-slate-800/90 rounded-2xl p-5 hover:border-slate-700 transition-all flex flex-col justify-between group relative"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      {p.division}
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => {
                          setEditingProfile(p);
                          setIsModalOpen(true);
                        }}
                        className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
                        title="Edit Profil"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteProfile(p.division)}
                        className="p-1.5 text-slate-400 hover:text-red-400 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
                        title="Hapus Profil"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <h3 className="font-semibold text-sm text-white mb-1.5">{p.title}</h3>
                  <p className="text-xs text-slate-400 line-clamp-3 mb-4">{p.jd}</p>

                  {/* Badges Info */}
                  <div className="space-y-2 pt-3 border-t border-slate-800/80 text-[11px]">
                    <div className="flex items-center justify-between text-slate-400">
                      <span>Syarat Wajib:</span>
                      <span className={hardCount > 0 ? "text-amber-400 font-medium" : "text-slate-500"}>
                        {hardCount > 0 ? `${hardCount} kriteria aktif` : "Tidak ada"}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-slate-400">
                      <span>Bobot Pengalaman/Project:</span>
                      <span className="text-slate-300 font-mono">
                        {p.categories.experience.weight}% / {p.categories.projects.weight}%
                      </span>
                    </div>

                    {p.divisionAliases && p.divisionAliases.length > 0 && (
                      <div className="text-slate-500 truncate">
                        Alias: {p.divisionAliases.join(", ")}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Proceed Button */}
      {profiles.length > 0 && (
        <div className="flex justify-end pt-4">
          <button
            onClick={onProceedToCsv}
            className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/25 flex items-center gap-2 cursor-pointer transition-all"
          >
            <span>Lanjut ke Langkah 2: Unggah CSV</span>
            <CheckCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Profile Editor Modal */}
      <ProfileEditorModal
        isOpen={isModalOpen}
        profile={editingProfile}
        onSave={handleSaveProfile}
        onClose={() => {
          setIsModalOpen(false);
          setEditingProfile(null);
        }}
      />
    </div>
  );
}
