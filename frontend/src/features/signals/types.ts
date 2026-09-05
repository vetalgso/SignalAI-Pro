export type SignalSide = 'LONG' | 'SHORT';

export type SignalStatus =
  | 'ACTIVE'
  | 'ENTRY_REACHED'
  | 'TP1_REACHED'
  | 'TP2_REACHED'
  | 'TP3_REACHED'
  | 'STOPPED'
  | 'EXPIRED'
  | 'CANCELLED';

export type SignalRiskLevel =
  | 'LOW'
  | 'MEDIUM'
  | 'HIGH';

export interface TradingSignal {
  id: number;
  fingerprint: string;

  exchange: string;
  market_type: string;
  symbol: string;
  timeframe: string;
  side: SignalSide;
  strategy: string;
  status: SignalStatus;

  confidence: string;
  risk_level: SignalRiskLevel;
  risk_reward: string;

  entry_min: string;
  entry_max: string;
  stop_loss: string;
  take_profit_1: string;
  take_profit_2: string | null;
  take_profit_3: string | null;
  current_price: string | null;

  reasons: string[];
  metadata_payload: Record<string, unknown>;
  source: string;

  generated_at: string;
  expires_at: string | null;
  activated_at: string | null;
  entry_reached_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SignalPage {
  items: TradingSignal[];
  total: number;
  limit: number;
  offset: number;
}

export interface SignalScanResult {
  scanned_assets: number;
  successful_assets: number;
  failed_assets: number;
  opportunities_found: number;

  created_count: number;
  duplicate_count: number;
  skipped_count: number;

  created: TradingSignal[];
  duplicates: Array<{
    symbol: string;
    existing_signal_id: number;
  }>;
  skipped: Array<{
    symbol: string;
    reason: string;
  }>;
  scanner_errors: Array<{
    asset?: string;
    error?: string;
  }>;
}

export interface SignalFilters {
  search: string;
  side: string;
  status: string;
  riskLevel: string;
  minConfidence: number;
}

export interface MarketCandle {
  open_time: number;
  close_time?: number;
  open: string | number;
  high: string | number;
  low: string | number;
  close: string | number;
  volume?: string | number;
}

export interface MarketKlinesResponse {
  symbol?: string;
  interval?: string;
  candles: MarketCandle[];
}
