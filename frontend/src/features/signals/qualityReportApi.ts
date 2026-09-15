export type Counts = {
  total: number; open: number; terminal: number; unknown_status: number;
  entered: number; tp1: number; tp2: number; tp3: number;
  stopped: number; expired: number; cancelled: number;
  without_events: number; manual_transitions: number;
};
type Group = Counts & {
  source: string; exchange: string; market_type: string; symbol: string;
  side: string; timeframe: string; strategy: string;
};
export type Report = {
  generated_from: string; as_of: string; source: string; summary: Counts;
  transition_origin: 'ALL' | 'AUTOMATIC' | 'MANUAL' | 'UNKNOWN';
  groups: Group[]; total_groups: number; limit: number; offset: number;
};
export type QualityQuery = {
  days: number;
  source: string;
  transition_origin: Report['transition_origin'];
  offset: number;
};

export async function fetchQualityReport(query: QualityQuery, signal: AbortSignal): Promise<Report> {
  const params = new URLSearchParams({ days: String(query.days), source: query.source,
    transition_origin: query.transition_origin, offset: String(query.offset), limit: '25' });
  const response = await fetch(`/api/v3/signals/quality?${params}`, {
    signal, headers: { Accept: 'application/json' }, cache: 'no-store',
  });
  if (!response.ok) throw new Error('Request failed');
  const report = await response.json();
  // A legacy server can ignore an unknown query parameter and return ALL.
  // Never display those totals under a selected automatic/manual cohort.
  if (!report || report.transition_origin !== query.transition_origin
    || report.source !== query.source || report.offset !== query.offset || report.limit !== 25
    || !report.summary || !Array.isArray(report.groups)) {
    throw new Error('Report does not match the requested filters');
  }
  return report;
}
