import { ProcessedCVResult } from "./types";
import { RawCsvRow } from "./csv";

export interface PoolProgress {
  completed: number;
  total: number;
  successCount: number;
  failedCount: number;
  currentName?: string;
  isCancelled: boolean;
  isFinished: boolean;
  estimatedRemainingSeconds?: number;
}

export class ConcurrencyPool {
  private concurrency: number;
  private isCancelled: boolean = false;
  private abortController: AbortController = new AbortController();

  constructor(concurrency: number = 4) {
    this.concurrency = concurrency;
  }

  public cancel() {
    this.isCancelled = true;
    this.abortController.abort();
  }

  public async processBatch(
    rows: RawCsvRow[],
    onProgress: (progress: PoolProgress) => void
  ): Promise<ProcessedCVResult[]> {
    this.isCancelled = false;
    this.abortController = new AbortController();

    const results: ProcessedCVResult[] = [];
    const total = rows.length;
    let completed = 0;
    let successCount = 0;
    let failedCount = 0;

    const startTime = performance.now();

    // Salin antrean
    const queue = [...rows];
    let activeWorkers = 0;

    const updateProgress = (currentName?: string) => {
      const elapsedSec = (performance.now() - startTime) / 1000;
      let estimatedRemainingSeconds: number | undefined = undefined;
      if (completed > 0) {
        const avgTimePerItem = elapsedSec / completed;
        estimatedRemainingSeconds = Math.round(avgTimePerItem * (total - completed));
      }

      onProgress({
        completed,
        total,
        successCount,
        failedCount,
        currentName,
        isCancelled: this.isCancelled,
        isFinished: completed === total,
        estimatedRemainingSeconds,
      });
    };

    return new Promise((resolve) => {
      if (total === 0) {
        resolve([]);
        return;
      }

      const next = () => {
        if (this.isCancelled) {
          resolve(results);
          return;
        }

        if (queue.length === 0 && activeWorkers === 0) {
          updateProgress();
          resolve(results);
          return;
        }

        while (activeWorkers < this.concurrency && queue.length > 0 && !this.isCancelled) {
          const item = queue.shift()!;
          activeWorkers++;
          updateProgress(item.name);

          this.processSingleItem(item)
            .then((res) => {
              results.push(res);
              if (res.error || res.isScanPdf) {
                failedCount++;
              } else {
                successCount++;
              }
            })
            .catch((err) => {
              failedCount++;
              results.push({
                fileId: item.driveLink,
                sourceRowIndex: item.rowIndex,
                driveLink: item.driveLink,
                fields: {
                  name: item.name,
                  portfolioLinks: [],
                  skillsFound: [],
                  experiences: [],
                  projects: [],
                  certifications: [],
                },
                sections: {},
                fieldStatus: { process: "tidak_ditemukan" },
                flags: ["kesalahan_jaringan"],
                isScanPdf: false,
                divisionChoices: item.divisionChoices,
                error: err instanceof Error ? err.message : "Kesalahan jaringan",
              });
            })
            .finally(() => {
              completed++;
              activeWorkers--;
              updateProgress();
              next();
            });
        }
      };

      next();
    });
  }

  private async processSingleItem(item: RawCsvRow): Promise<ProcessedCVResult> {
    const response = await fetch("/api/process", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      signal: this.abortController.signal,
      body: JSON.stringify({
        fileId: item.driveLink,
        driveLink: item.driveLink,
        candidateName: item.name,
        divisionChoices: item.divisionChoices,
        sourceRowIndex: item.rowIndex,
      }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.message || `HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.result as ProcessedCVResult;
  }
}
