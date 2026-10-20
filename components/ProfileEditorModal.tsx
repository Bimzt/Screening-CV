"use client";

import React, { useState } from "react";
import { JobProfile } from "@/lib/types";
import { normalizeProfileWeights } from "@/lib/profile";
import { X, Check, AlertCircle, Sparkles } from "lucide-react";

interface ProfileEditorModalProps {
  isOpen: boolean;
  profile: JobProfile | null;
  onSave: (updatedProfile: JobProfile) => void;
  onClose: () => void;
}

export default function ProfileEditorModal({
  isOpen,
  profile,
  onSave,
  onClose,
}: ProfileEditorModalProps) {
  if (!isOpen) return null;

  return (
    <ProfileEditorContent
      key={profile?.division || "new-profile"}
      profile={profile}
      onSave={onSave}
      onClose={onClose}
    />
  );
}

function ProfileEditorContent({
  profile,
  onSave,
  onClose,
}: {
  profile: JobProfile | null;
  onSave: (updatedProfile: JobProfile) => void;
  onClose: () => void;
}) {
  const [formData, setFormData] = useState<JobProfile>(() => {
    if (profile) return JSON.parse(JSON.stringify(profile));
    return {
      version: "1.0",
      division: "",
      divisionAliases: [],
      title: "",
      jd: "",
      hardRequirements: {
        minGpa: undefined,
        allowedMajors: [],
        mandatorySkills: {
          items: [],
          rule: "all",
        },
      },
      additionalSkills: [],
      categories: {
        experience: { label: "Pengalaman", weight: 35, active: true },
        projects: { label: "Project / Portofolio", weight: 30, active: true },
        cert_edu: { label: "Sertifikasi & Pendidikan", weight: 20, active: true },
        competencies: { label: "Kompetensi", weight: 15, active: true },
      },
      thresholds: {
        durationMonths: 0,
        projectsCount: 0,
      },
    };
  });

  const [error, setError] = useState<string | null>(null);

  // State teks lokal agar pengguna bebas mengetik spasi, koma, dsb. tanpa terpotong
  const [aliasesText, setAliasesText] = useState<string>(() => (profile?.divisionAliases || []).join(", "));
  const [allowedMajorsText, setAllowedMajorsText] = useState<string>(() => (profile?.hardRequirements?.allowedMajors || []).join(", "));
  const [mandatorySkillsText, setMandatorySkillsText] = useState<string>(() => (profile?.hardRequirements?.mandatorySkills?.items || []).join(", "));
  const [additionalSkillsText, setAdditionalSkillsText] = useState<string>(() => (profile?.additionalSkills || []).join(", "));

  const totalWeight = Object.values(formData.categories)
    .filter((c) => c.active)
    .reduce((sum, c) => sum + (c.weight || 0), 0);

  const handleNormalizeWeights = () => {
    const normalized = normalizeProfileWeights(formData);
    setFormData(normalized);
  };

  const handleSave = () => {
    if (!formData.division.trim()) {
      setError("Nama divisi wajib diisi.");
      return;
    }
    if (!formData.title.trim()) {
      setError("Judul lowongan wajib diisi.");
      return;
    }
    if (!formData.jd.trim()) {
      setError("Deskripsi pekerjaan (JD) wajib diisi.");
      return;
    }

    // Parse teks berpisah koma ke array saat simpan
    const parsedAliases = aliasesText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const parsedMajors = allowedMajorsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const parsedMandatorySkills = mandatorySkillsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const parsedAdditionalSkills = additionalSkillsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const updatedProfile: JobProfile = {
      ...formData,
      division: formData.division.trim(),
      title: formData.title.trim(),
      jd: formData.jd.trim(),
      divisionAliases: parsedAliases,
      hardRequirements: {
        ...formData.hardRequirements,
        minGpa: formData.hardRequirements?.minGpa,
        allowedMajors: parsedMajors,
        mandatorySkills: {
          rule: formData.hardRequirements?.mandatorySkills?.rule || "all",
          items: parsedMandatorySkills,
          minCount: formData.hardRequirements?.mandatorySkills?.minCount,
        },
      },
      additionalSkills: parsedAdditionalSkills,
    };

    // Normalisasi bobot jika tidak tepat 100
    const finalProfile = normalizeProfileWeights(updatedProfile);
    onSave(finalProfile);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
          <div>
            <h3 className="text-base font-bold text-white">
              {profile ? `Edit Profil: ${profile.division}` : "Buat Profil Lowongan Baru"}
            </h3>
            <p className="text-xs text-slate-400">
              Konfigurasi kriteria penilaian dan syarat wajib untuk divisi ini
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-200">
          {error && (
            <div className="p-3 bg-red-950/60 border border-red-800 rounded-xl text-red-200 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Divisi & Judul */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold mb-1 text-slate-300">
                Nama Divisi <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={formData.division}
                onChange={(e) => setFormData({ ...formData, division: e.target.value })}
                placeholder="mis. Data Analyst, HRTA"
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block font-semibold mb-1 text-slate-300">
                Judul Lowongan <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="mis. Talent Acquisition Intern"
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>

          {/* Alias Divisi */}
          <div>
            <label className="block font-semibold mb-1 text-slate-300">
              Alias Penulisan Divisi di Form (pisahkan dengan koma)
            </label>
            <input
              type="text"
              value={aliasesText}
              onChange={(e) => setAliasesText(e.target.value)}
              placeholder="mis. da, data, business intelligence, bi"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Membantu aplikasi memetakan teks pilihan divisi pelamar di form secara otomatis.
            </p>
          </div>

          {/* Deskripsi JD */}
          <div>
            <label className="block font-semibold mb-1 text-slate-300">
              Teks Deskripsi Pekerjaan (JD) <span className="text-red-400">*</span>
            </label>
            <textarea
              rows={4}
              value={formData.jd}
              onChange={(e) => setFormData({ ...formData, jd: e.target.value })}
              placeholder="Masukkan teks JD lengkap sebagai acuan kemiripan TF-IDF..."
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Hard Requirements (Syarat Wajib) */}
          <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-3">
            <div className="font-semibold text-indigo-400 flex items-center justify-between">
              <span>Syarat Wajib (Hard Requirements - Opsional)</span>
              <span className="text-[11px] text-slate-500 font-normal">
                Kandidat tidak memenuhi tetap diperingkat dengan alasan eksplisit
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-slate-400 mb-1">IPK Minimum (0.0 - 4.0)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="4"
                  value={formData.hardRequirements?.minGpa ?? ""}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      hardRequirements: {
                        ...formData.hardRequirements,
                        minGpa: e.target.value ? parseFloat(e.target.value) : undefined,
                      },
                    })
                  }
                  placeholder="Kosongkan jika tidak ada syarat IPK"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">
                  Jurusan yang Diterima (pisahkan dengan koma)
                </label>
                <input
                  type="text"
                  value={allowedMajorsText}
                  onChange={(e) => setAllowedMajorsText(e.target.value)}
                  placeholder="Kosongkan jika semua jurusan diterima"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-slate-400">
                  Kompetensi Wajib (pisahkan dengan koma)
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500 text-[11px]">Aturan:</span>
                  <select
                    value={formData.hardRequirements?.mandatorySkills?.rule || "all"}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        hardRequirements: {
                          ...formData.hardRequirements,
                          mandatorySkills: {
                            items: formData.hardRequirements?.mandatorySkills?.items || [],
                            rule: e.target.value as "all" | "min_n",
                            minCount: formData.hardRequirements?.mandatorySkills?.minCount,
                          },
                        },
                      })
                    }
                    className="bg-slate-900 border border-slate-800 text-white text-[11px] px-2 py-0.5 rounded-lg focus:outline-none"
                  >
                    <option value="all">Semua harus ada</option>
                    <option value="min_n">Minimal N kompetensi</option>
                  </select>
                </div>
              </div>

              <input
                type="text"
                value={mandatorySkillsText}
                onChange={(e) => setMandatorySkillsText(e.target.value)}
                placeholder="mis. SQL, Python, Excel"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>

          {/* Kompetensi Tambahan (Nilai Plus) */}
          <div>
            <label className="block font-semibold mb-1 text-slate-300">
              Kompetensi Tambahan / Nilai Plus (pisahkan dengan koma)
            </label>
            <input
              type="text"
              value={additionalSkillsText}
              onChange={(e) => setAdditionalSkillsText(e.target.value)}
              placeholder="mis. Tableau, Power BI, Excel, Pandas"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Bobot Kategori Penilaian */}
          <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/80 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-semibold text-slate-300 block">Bobot Kategori Penilaian</span>
                <span className="text-[11px] text-slate-500">
                  Total saat ini:{" "}
                  <span className={totalWeight === 100 ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                    {totalWeight}%
                  </span>
                </span>
              </div>
              {totalWeight !== 100 && (
                <button
                  type="button"
                  onClick={handleNormalizeWeights}
                  className="px-3 py-1 bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 rounded-lg hover:bg-indigo-600/30 flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Normalisasi Otomatis ke 100%</span>
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(Object.keys(formData.categories) as Array<keyof typeof formData.categories>).map((key) => {
                const cat = formData.categories[key];
                return (
                  <div key={key} className="p-3 bg-slate-900 rounded-xl border border-slate-800 flex items-center justify-between gap-3">
                    <div className="flex-1">
                      <input
                        type="text"
                        value={cat.label}
                        onChange={(e) => {
                          const updated = { ...formData.categories };
                          updated[key].label = e.target.value;
                          setFormData({ ...formData, categories: updated });
                        }}
                        className="bg-transparent border-b border-transparent hover:border-slate-700 text-xs font-semibold text-white focus:outline-none"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={cat.weight}
                        onChange={(e) => {
                          const updated = { ...formData.categories };
                          updated[key].weight = parseInt(e.target.value) || 0;
                          setFormData({ ...formData, categories: updated });
                        }}
                        className="w-16 px-2 py-1 bg-slate-950 border border-slate-700 rounded-lg text-right font-mono text-white focus:outline-none"
                      />
                      <span className="text-slate-400">%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Ambang Batas Durasi & Project */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-slate-400 mb-1">Ambang Durasi Pengalaman Penuh (Bulan)</label>
              <input
                type="number"
                min="0"
                value={formData.thresholds.durationMonths}
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  setFormData({
                    ...formData,
                    thresholds: {
                      ...formData.thresholds,
                      durationMonths: isNaN(val) ? 0 : Math.max(0, val),
                    },
                  });
                }}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none"
              />
              <span className="text-[11px] text-slate-500">0 = Tanpa ambang batas durasi (skor durasi penuh)</span>
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Ambang Jumlah Project Penuh</label>
              <input
                type="number"
                min="0"
                value={formData.thresholds.projectsCount}
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  setFormData({
                    ...formData,
                    thresholds: {
                      ...formData.thresholds,
                      projectsCount: isNaN(val) ? 0 : Math.max(0, val),
                    },
                  });
                }}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none"
              />
              <span className="text-[11px] text-slate-500">0 = Tanpa ambang batas project (skor jumlah penuh)</span>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors cursor-pointer"
          >
            Batal
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-semibold shadow-lg shadow-indigo-600/20 flex items-center gap-1.5 transition-all cursor-pointer"
          >
            <Check className="w-4 h-4" />
            <span>Simpan Profil</span>
          </button>
        </div>
      </div>
    </div>
  );
}
