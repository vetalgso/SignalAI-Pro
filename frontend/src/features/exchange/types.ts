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
