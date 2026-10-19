/**
 * Definisi tipe data aplikasi CV Screener.
 */

export interface HardRequirementSkills {
  items: string[];
  rule: "all" | "min_n";
  minCount?: number;
}

export interface HardRequirements {
  mandatorySkills?: HardRequirementSkills;
  minGpa?: number;
  allowedMajors?: string[];
}

export interface ScoringCategoryConfig {
  label: string;
  weight: number;
  active: boolean;
}

export interface JobProfileThresholds {
  durationMonths: number;
  projectsCount: number;
}

export interface JobProfile {
  version: string;
  division: string;
  divisionAliases: string[];
  title: string;
  jd: string;
  hardRequirements?: HardRequirements;
  additionalSkills?: string[];
  categories: {
    experience: ScoringCategoryConfig;
    projects: ScoringCategoryConfig;
    cert_edu: ScoringCategoryConfig;
    competencies: ScoringCategoryConfig;
    [customKey: string]: ScoringCategoryConfig;
  };
  thresholds: JobProfileThresholds;
  customSectionHeadings?: string[];
}

export type ExperienceType = "kerja/magang" | "organisasi" | "kepanitiaan/volunteer";

export interface ExperienceEntry {
  title: string;
  organization?: string;
  dateRange?: string;
  durationMonths: number;
  type: ExperienceType;
}

export interface ProjectEntry {
  title: string;
  description?: string;
}

export type FieldStatus = "ok" | "ambigu" | "tidak_ditemukan";

export interface ExtractedFields {
  name?: string;
  email?: string;
  phone?: string;
  university?: string;
  major?: string;
  gpa?: number;
  graduationYearOrSemester?: string;
  portfolioLinks: string[];
  skillsFound: string[];
  experiences: ExperienceEntry[];
  projects: ProjectEntry[];
  certifications: string[];
}

export interface ExtractedSections {
  education?: string;
  experience?: string;
  projects?: string;
  certifications?: string;
  skills?: string;
  others?: string;
}

export interface ProcessedCVResult {
  fileId: string;
  sourceRowIndex?: number;
  driveLink?: string;
  fields: ExtractedFields;
  sections: ExtractedSections;
  fieldStatus: Record<string, FieldStatus>;
  flags: string[];
  isScanPdf: boolean;
  divisionChoices: string[];
  error?: string;
}

export type HardReqStatus =
  | "Memenuhi"
  | "Tidak memenuhi"
  | "Perlu dicek"
  | "Tidak ada syarat wajib";

export interface ChoiceEvaluationSummary {
  division: string;
  rank?: number;
  finalScore: number;
  hardRequirementStatus: HardReqStatus;
  categoryScores?: Record<string, number>;
  reasons?: string;
}

export interface RankedCandidate {
  division: string;
  rank: number;
  fileId: string;
  sourceRowIndex?: number;
  name: string;
  email?: string;
  phone?: string;
  university?: string;
  major?: string;
  gpa?: number;
  graduationYearOrSemester?: string;
  portfolioLinks: string[];
  skillsFound: string[];
  experiences: ExperienceEntry[];
  projects: ProjectEntry[];
  certifications: string[];
  categoryScores: Record<string, number>;
  finalScore: number;
  hardRequirementStatus: HardReqStatus;
  reasons: string;
  flags: string[];
  driveLink?: string;
  multiDivisionNote?: string;
  divisionChoices?: string[];
  choiceRank?: number;
  isFirstChoice?: boolean;
  pilihan1?: string;
  pilihan2?: string;
  choice1Result?: ChoiceEvaluationSummary;
  choice2Result?: ChoiceEvaluationSummary;
  bestFitChoice?: 1 | 2 | "equal";
  recommendationNote?: string;
  aiEvaluation?: {
    contextualScore?: number;
    practicalLevel?: "Tinggi" | "Sedang" | "Dasar" | string;
    executiveSummary?: string;
    keyStrength?: string;
  };
}

export interface ReviewItem {
  rowIndex?: number;
  name?: string;
  division?: string;
  issueType: string;
  suggestedAction: string;
  driveLink?: string;
}

export interface RankingResponse {
  divisionResults: Record<string, RankedCandidate[]>;
  reviewList: ReviewItem[];
  meta: {
    totalProcessed: number;
    fitMethods: Record<string, string>;
    timestamp: number;
  };
}
