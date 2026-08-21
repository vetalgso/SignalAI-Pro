import type {
  AccountOrderExecuteRequest,
  AccountOrderHistoryQuery,
  AccountOrderJournal,
  AccountOrderPreview,
  AccountOrderRequest,
  AccountOrderResult,
  AccountOrderRiskStatus,
  AuthTokenResponse,
  AuthUser,
  ExchangeAccount,
  ExchangeAccountCreate,
  PortfolioSnapshot,
} from './types';

const API = '/api';
const TOKEN_KEY =
  'signalai_session_access_token';

interface ApiErrorPayload {
  detail?: unknown;
  message?: unknown;
}

export class ExchangeApiError extends Error {
  readonly status: number;

  constructor(
    message: string,
    status: number,
  ) {
    super(message);
    this.name = 'ExchangeApiError';
    this.status = status;
  }
}

function errorMessage(
  payload: ApiErrorPayload | null,
  fallback: string,
): string {
  if (
    payload
    && typeof payload.detail === 'string'
  ) {
    return payload.detail;
  }

  if (
    payload
    && payload.detail
    && typeof payload.detail === 'object'
  ) {
    const detail = payload.detail as {
      message?: unknown;
    };

    if (typeof detail.message === 'string') {
      return detail.message;
    }
  }

  if (
    payload
    && typeof payload.message === 'string'
  ) {
    return payload.message;
  }

  return fallback;
}

async function readJson<T>(
  response: Response,
): Promise<T> {
  let payload: unknown = null;

  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new ExchangeApiError(
      errorMessage(
        payload as ApiErrorPayload | null,
        `Request failed: ${response.status}`,
      ),
      response.status,
    );
  }

  return payload as T;
}

function authHeaders(
  token: string,
): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
  };
}

export function readAccessToken(): string | null {
  return sessionStorage.getItem(
    TOKEN_KEY,
  );
}

export function saveAccessToken(
  token: string,
): void {
  sessionStorage.setItem(
    TOKEN_KEY,
    token,
  );
}

export function removeAccessToken(): void {
  sessionStorage.removeItem(
    TOKEN_KEY,
  );
}

export async function registerUser(
  username: string,
  password: string,
  email: string,
): Promise<AuthUser> {
  const response = await fetch(
    `${API}/v1/auth/register`,
    {
      method: 'POST',
      headers: {
        'Content-Type':
          'application/json',
      },
      body: JSON.stringify({
        username,
        password,
        email:
          email.trim().length > 0
            ? email.trim()
            : null,
      }),
    },
  );

  return readJson<AuthUser>(response);
}

export async function loginUser(
  username: string,
  password: string,
): Promise<AuthTokenResponse> {
  const body = new URLSearchParams({
    username,
    password,
  });

  const response = await fetch(
    `${API}/v1/auth/token`,
    {
      method: 'POST',
      headers: {
        'Content-Type':
          'application/x-www-form-urlencoded',
      },
      body,
    },
  );

  return readJson<AuthTokenResponse>(
    response,
  );
}

export async function fetchCurrentUser(
  token: string,
): Promise<AuthUser> {
  const response = await fetch(
    `${API}/v1/auth/me`,
    {
      headers: authHeaders(token),
    },
  );

  return readJson<AuthUser>(response);
}

export async function fetchExchangeAccounts(
  token: string,
): Promise<ExchangeAccount[]> {
  const response = await fetch(
    `${API}/v3/exchange/accounts`,
    {
      headers: authHeaders(token),
    },
  );

  return readJson<ExchangeAccount[]>(
    response,
  );
}

export async function saveExchangeAccount(
  token: string,
  payload: ExchangeAccountCreate,
): Promise<ExchangeAccount> {
  const response = await fetch(
    `${API}/v3/exchange/accounts`,
    {
      method: 'POST',
      headers: {
        ...authHeaders(token),
        'Content-Type':
          'application/json',
      },
      body: JSON.stringify(payload),
    },
  );

  return readJson<ExchangeAccount>(
    response,
  );
}

export async function verifyExchangeAccount(
  token: string,
  accountId: number,
): Promise<ExchangeAccount> {
  const response = await fetch(
    (
      `${API}/v3/exchange/accounts/`
      + `${accountId}/verify`
    ),
    {
      method: 'POST',
      headers: authHeaders(token),
    },
  );

  return readJson<ExchangeAccount>(
    response,
  );
}

export async function fetchExchangePortfolio(
  token: string,
  accountId: number,
): Promise<PortfolioSnapshot> {
  const response = await fetch(
    (
      `${API}/v3/exchange/accounts/`
      + `${accountId}/portfolio`
    ),
    {
      headers: authHeaders(token),
    },
  );

  return readJson<PortfolioSnapshot>(
    response,
  );
}

export async function deleteExchangeAccount(
  token: string,
  accountId: number,
): Promise<void> {
  const response = await fetch(
    (
      `${API}/v3/exchange/accounts/`
      + `${accountId}`
    ),
    {
      method: 'DELETE',
      headers: authHeaders(token),
    },
  );

  await readJson<{
    deleted: boolean;
    account_id: number;
  }>(response);
}

function accountOrdersPath(
  accountId: number,
): string {
  return (
    `${API}/v3/exchange/accounts/`
    + `${accountId}/orders`
  );
}

export async function fetchExchangeAccountOrderRisk(
  token: string,
  accountId: number,
): Promise<AccountOrderRiskStatus> {
  const response = await fetch(
    `${accountOrdersPath(accountId)}/risk`,
    {
      headers: authHeaders(token),
    },
  );

  return readJson<AccountOrderRiskStatus>(
    response,
  );
}

export async function previewExchangeAccountOrder(
  token: string,
  accountId: number,
  payload: AccountOrderRequest,
): Promise<AccountOrderPreview> {
  const response = await fetch(
    `${accountOrdersPath(accountId)}/preview`,
    {
      method: 'POST',
      headers: {
        ...authHeaders(token),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    },
  );

  return readJson<AccountOrderPreview>(
    response,
  );
}

export async function executeExchangeAccountOrder(
  token: string,
  accountId: number,
  payload: AccountOrderExecuteRequest,
): Promise<AccountOrderJournal> {
  const response = await fetch(
    `${accountOrdersPath(accountId)}/execute`,
    {
      method: 'POST',
      headers: {
        ...authHeaders(token),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    },
  );

  return readJson<AccountOrderJournal>(
    response,
  );
}

function withQuery(
  path: string,
  values: Record<
    string,
    string | number | undefined
  >,
): string {
  const query = new URLSearchParams();

  Object.entries(values).forEach(
    ([key, value]) => {
      if (
        value !== undefined
        && String(value).length > 0
      ) {
        query.set(key, String(value));
      }
    },
  );

  const encoded = query.toString();

  return encoded.length > 0
    ? `${path}?${encoded}`
    : path;
}

export async function fetchExchangeAccountOrderHistory(
  token: string,
  accountId: number,
  query: AccountOrderHistoryQuery = {},
): Promise<AccountOrderJournal[]> {
  const response = await fetch(
    withQuery(
      `${accountOrdersPath(accountId)}/history`,
      {
        limit: query.limit,
        symbol: query.symbol?.trim(),
        status: query.status?.trim(),
      },
    ),
    {
      headers: authHeaders(token),
    },
  );

  return readJson<AccountOrderJournal[]>(
    response,
  );
}

export async function fetchExchangeAccountOrderJournal(
  token: string,
  accountId: number,
  journalId: number,
): Promise<AccountOrderJournal> {
  const response = await fetch(
    (
      `${accountOrdersPath(accountId)}/history/`
      + `${journalId}`
    ),
    {
      headers: authHeaders(token),
    },
  );

  return readJson<AccountOrderJournal>(
    response,
  );
}

export async function fetchExchangeAccountOpenOrders(
  token: string,
  accountId: number,
  symbol?: string,
): Promise<AccountOrderResult[]> {
  const response = await fetch(
    withQuery(
      `${accountOrdersPath(accountId)}/open`,
      {
        symbol: symbol?.trim(),
      },
    ),
    {
      headers: authHeaders(token),
    },
  );

  return readJson<AccountOrderResult[]>(
    response,
  );
}

export async function fetchExchangeAccountOrderStatus(
  token: string,
  accountId: number,
  orderId: string,
  symbol: string,
): Promise<AccountOrderResult> {
  const path = (
    `${accountOrdersPath(accountId)}/`
    + encodeURIComponent(orderId)
  );

  const response = await fetch(
    withQuery(
      path,
      {
        symbol: symbol.trim(),
      },
    ),
    {
      headers: authHeaders(token),
    },
  );

  return readJson<AccountOrderResult>(
    response,
  );
}

export async function cancelExchangeAccountOrder(
  token: string,
  accountId: number,
  orderId: string,
  symbol: string,
): Promise<AccountOrderResult> {
  const path = (
    `${accountOrdersPath(accountId)}/`
    + encodeURIComponent(orderId)
  );

  const response = await fetch(
    withQuery(
      path,
      {
        symbol: symbol.trim(),
      },
    ),
    {
      method: 'DELETE',
      headers: authHeaders(token),
    },
  );

  return readJson<AccountOrderResult>(
    response,
  );
}
