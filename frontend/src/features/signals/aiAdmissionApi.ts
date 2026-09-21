export type QualityBreakdown = {
  version: 1;
  calculated_at: string;
  forecast: {
    points: number; state: 'AVAILABLE' | 'MISSING'; uncertain_count: number;
    horizons: { horizon_minutes: number | null; direction: 'UP' | 'DOWN' | 'SIDEWAYS' | 'UNCERTAIN' | 'UNKNOWN' }[];
  };
  volume: { points: number; state: 'AVAILABLE' | 'MISSING' | 'INVALID'; ratio: number | null };
  news: { points: number; state: 'AVAILABLE' | 'MISSING'; article_count: number; unverified_count: number };
  uncapped_total: number; cap: number; total: number;
};

export type AdmissionDecision = {
  version: 1;
  action: 'SELECTED' | 'SKIPPED';
  reason: string;
  confidence: number | null;
  minimum_confidence: number;
  maximum_quality_penalty?: number | null;
  candidate_age_seconds: number;
  max_candidates: number;
  evaluated_at: string;
};
export type AdmissionPage = {
  run: { id: number; completed_at: string; scanned_assets: number } | null;
  items: { candidate_id: number; symbol: string; decision: AdmissionDecision | null; quality?: QualityBreakdown | null }[];
  total: number; limit: number; offset: number;
  reason_counts: Record<string, number>;
  not_recorded_count: number;
};

export async function fetchAdmission(
  runId: number | null, offset: number, signal: AbortSignal,
): Promise<AdmissionPage> {
  const params = new URLSearchParams({ limit: '25', offset: String(offset) });
  if (runId !== null) params.set('run_id', String(runId));
  const response = await fetch(`/api/v3/signals/ai-admission?${params}`, {
    signal, cache: 'no-store', headers: { Accept: 'application/json' },
  });
  if (!response.ok) throw new Error('Admission request failed');
  const page: AdmissionPage = await response.json();
  if (!Array.isArray(page.items) || !Number.isInteger(page.total) || page.total < 0
    || page.limit !== 25 || page.offset !== offset
    || !page.reason_counts || !Number.isInteger(page.not_recorded_count)
    || (runId !== null && page.run?.id !== runId)
    || (page.run === null && (page.total !== 0 || page.items.length !== 0))) {
    throw new Error('Admission response does not match the requested scan');
  }
  return page;
}
