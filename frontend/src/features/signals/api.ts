import type {
  SignalFilters,
  SignalPage,
  SignalScanResult,
} from './types';

const SIGNALS_API = '/api/v3/signals';

async function readJson<T>(
  response: Response,
): Promise<T> {
  if (!response.ok) {
    let message = `HTTP ${response.status}`;

    try {
      const payload = await response.json();

      if (typeof payload?.detail === 'string') {
        message = payload.detail;
      }
    } catch {
      // Response body may be empty.
    }

    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function fetchSignals(
  filters: SignalFilters,
): Promise<SignalPage> {
  const query = new URLSearchParams({
    limit: '200',
    offset: '0',
  });

  if (filters.side) {
    query.set('side', filters.side);
  }

  if (filters.status) {
    query.set('status', filters.status);
  }

  if (filters.riskLevel) {
    query.set(
      'risk_level',
      filters.riskLevel,
    );
  }

  if (filters.minConfidence > 0) {
    query.set(
      'min_confidence',
      String(filters.minConfidence),
    );
  }

  const response = await fetch(
    `${SIGNALS_API}?${query.toString()}`,
  );

  return readJson<SignalPage>(response);
}

export async function scanSignals(): Promise<
  SignalScanResult
> {
  const response = await fetch(
    `${SIGNALS_API}/scan`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        assets: [
          'BTC',
          'ETH',
          'BNB',
          'SOL',
          'XRP',
          'ADA',
          'DOGE',
          'AVAX',
        ],
        risk_level: 'medium',
        limit: 8,
        min_confidence: 60,
      }),
    },
  );

  return readJson<SignalScanResult>(
    response,
  );
}

export async function fetchSignalCandles(
  symbol: string,
  timeframe: string,
  limit = 240,
): Promise<import('./types').MarketKlinesResponse> {
  const interval = timeframe
    .trim()
    .toLowerCase();

  const query = new URLSearchParams({
    symbol: symbol.toUpperCase(),
    interval,
    limit: String(limit),
  });

  const response = await fetch(
    `/api/v1/market/klines?${query.toString()}`,
  );

  return readJson<
    import('./types').MarketKlinesResponse
  >(response);
}
