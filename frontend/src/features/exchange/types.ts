export type Language = 'ru' | 'en';

export type ExchangeEnvironment =
  | 'TESTNET'
  | 'LIVE';

export type ExchangeAccountStatus =
  | 'UNVERIFIED'
  | 'CONNECTED'
  | 'ERROR'
  | 'UNSAFE';

export interface AuthUser {
  id: number;
  username: string;
  email: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
}

export interface ExchangeAccount {
  id: number;
  exchange: string;
  environment: ExchangeEnvironment;
  label: string;
  api_key_hint: string;
  status: ExchangeAccountStatus;
  can_trade: boolean | null;
  can_deposit: boolean | null;
  can_withdraw: boolean | null;
  last_checked_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssetBalance {
  asset: string;
  free: number;
  locked: number;
}

export interface ExchangePosition {
  symbol: string;
  quantity: number;
  entry_price: number | null;
  unrealized_pnl: number;
}

export interface ExchangeOpenOrder {
  exchange_order_id: string;
  client_order_id: string | null;
  symbol: string;
  side: 'BUY' | 'SELL';
  order_type: string;
  status: string;
  price: number;
  original_quantity: number;
  executed_quantity: number;
}

export interface PortfolioSnapshot {
  source: 'BINANCE';
  balances: AssetBalance[];
  open_orders: ExchangeOpenOrder[];
  positions: ExchangePosition[];
  total_wallet_balance: number | null;
  captured_at: string;
}

export interface ExchangeAccountCreate {
  label: string;
  environment: ExchangeEnvironment;
  api_key: string;
  secret_key: string;
}

export type ExchangeMarketType =
  | 'SPOT'
  | 'FUTURES';

export type AccountOrderSide =
  | 'BUY'
  | 'SELL';

export type AccountOrderType =
  | 'MARKET'
  | 'LIMIT';

export type AccountOrderStatus =
  | 'FILLED'
  | 'OPEN'
  | 'PARTIALLY_FILLED'
  | 'CANCELED'
  | 'REJECTED'
  | 'FAILED';

export interface AccountOrderRequest {
  exchange: 'BINANCE';
  market_type: ExchangeMarketType;
  symbol: string;
  side: AccountOrderSide;
  order_type: AccountOrderType;
  quantity: number;
  reference_price: number | null;
  stop_loss: number | null;
  take_profit_1: number | null;
  take_profit_2: number | null;
  leverage: number;
  reduce_only: boolean;
}

export interface AccountOrderExecuteRequest
  extends AccountOrderRequest {
  idempotency_key: string | null;
  dry_run: boolean;
}

export interface AccountOrderPreview {
  exchange: string;
  symbol: string;
  side: AccountOrderSide;
  order_type: AccountOrderType;
  valid: boolean;
  requested_quantity: number;
  normalized_quantity: number;
  requested_price: number | null;
  normalized_price: number | null;
  estimated_notional: number | null;
  available_balance: number | null;
  balance_asset: string | null;
  errors: string[];
  warnings: string[];
}

export interface AccountOrderResult {
  exchange: string;
  symbol: string;
  side: AccountOrderSide;
  order_type: AccountOrderType;
  status: AccountOrderStatus;
  client_order_id: string;
  exchange_order_id: string | null;
  requested_quantity: number;
  filled_quantity: number;
  average_price: number | null;
  simulated: boolean;
  message: string;
}

export interface AccountOrderJournal {
  journal_id: number;
  idempotency_key: string;
  replayed: boolean;
  dry_run: boolean;
  exchange: string;
  market_type: string;
  symbol: string;
  side: string;
  order_type: string;
  status: string;
  requested_quantity: number;
  normalized_quantity: number | null;
  requested_price: number | null;
  normalized_price: number | null;
  filled_quantity: number;
  average_price: number | null;
  client_order_id: string | null;
  exchange_order_id: string | null;
  simulated: boolean;
  request_payload: Record<string, unknown>;
  preview_payload: Record<string, unknown> | null;
  execution_payload: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccountOrderHistoryQuery {
  limit?: number;
  symbol?: string;
  status?: string;
}


export interface AccountOrderRiskStatus {
  source: 'BINANCE_TESTNET';
  execution_enabled: boolean;
  max_order_notional: number | null;
  daily_notional: number;
  max_daily_notional: number | null;
  remaining_daily_notional:
    | number
    | null;
  open_orders: number;
  max_open_orders: number | null;
  remaining_open_order_slots:
    | number
    | null;
  allowed_symbols: string[];
  order_submission_available: boolean;
  period_started_at: string;
  resets_at: string;
}
