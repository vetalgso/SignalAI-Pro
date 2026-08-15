import {
  AlertTriangle,
  CheckCircle2,
  CircleDollarSign,
  KeyRound,
  LoaderCircle,
  LogIn,
  LogOut,
  PlugZap,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UserPlus,
  WalletCards,
} from 'lucide-react';
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  ExchangeOrderCenter,
} from './ExchangeOrderCenter';
import {
  deleteExchangeAccount,
  ExchangeApiError,
  fetchCurrentUser,
  fetchExchangeAccounts,
  fetchExchangePortfolio,
  loginUser,
  readAccessToken,
  registerUser,
  removeAccessToken,
  saveAccessToken,
  saveExchangeAccount,
  verifyExchangeAccount,
} from './api';
import type {
  AuthUser,
  ExchangeAccount,
  ExchangeEnvironment,
  Language,
  PortfolioSnapshot,
} from './types';

interface ExchangeCenterProps {
  language: Language;
}

type AuthMode = 'login' | 'register';

const copy = {
  ru: {
    title: 'Подключение Binance',
    subtitle:
      'Защищённое подключение аккаунта, балансы, позиции и открытые ордера',
    authTitle: 'Вход в SignalAI Pro',
    authSubtitle:
      'Binance-аккаунты доступны только авторизованному владельцу',
    login: 'Войти',
    register: 'Создать аккаунт',
    username: 'Имя пользователя',
    email: 'Email — необязательно',
    password: 'Пароль',
    loggingIn: 'Выполняется вход…',
    registering: 'Создаётся аккаунт…',
    accountOwner: 'Пользователь',
    logout: 'Выйти',
    connectTitle: 'Подключить Binance',
    connectSubtitle:
      'Ключи шифруются до сохранения и никогда не возвращаются через API',
    label: 'Название подключения',
    environment: 'Среда',
    apiKey: 'API-ключ',
    secretKey: 'Secret key',
    connect: 'Сохранить подключение',
    saving: 'Сохранение…',
    securityTitle: 'Требования безопасности',
    securityOne:
      'Используйте отдельный API-ключ только для SignalAI Pro.',
    securityTwo:
      'Разрешение на вывод средств должно быть отключено.',
    securityThree:
      'До этапа автоматической торговли используйте TESTNET.',
    accounts: 'Подключённые аккаунты',
    noAccounts: 'Binance-аккаунты ещё не подключены',
    verify: 'Проверить',
    verifying: 'Проверка…',
    portfolio: 'Загрузить портфель',
    loadingPortfolio: 'Синхронизация…',
    remove: 'Удалить',
    confirmDelete:
      'Удалить это Binance-подключение?',
    connected: 'Подключён',
    unverified: 'Не проверен',
    error: 'Ошибка',
    unsafe: 'Небезопасный ключ',
    trading: 'Торговля',
    deposits: 'Пополнение',
    withdrawals: 'Вывод средств',
    yes: 'Да',
    no: 'Нет',
    unknown: 'Не определено',
    lastCheck: 'Последняя проверка',
    balances: 'Балансы',
    positions: 'Позиции',
    orders: 'Открытые ордера',
    noBalances: 'Ненулевых балансов нет',
    noPositions: 'Позиций нет',
    noOrders: 'Открытых ордеров нет',
    asset: 'Актив',
    free: 'Свободно',
    locked: 'Заблокировано',
    total: 'Всего',
    symbol: 'Инструмент',
    quantity: 'Количество',
    entryPrice: 'Цена входа',
    unrealizedPnl: 'Нереализованный PnL',
    side: 'Сторона',
    type: 'Тип',
    price: 'Цена',
    executed: 'Исполнено',
    status: 'Статус',
    captured: 'Снимок портфеля',
    refreshAccounts: 'Обновить список',
    sessionExpired:
      'Сессия завершена. Выполните вход повторно.',
    genericError:
      'Не удалось выполнить операцию',
    accountSaved:
      'Binance-подключение сохранено. Выполните проверку.',
    accountVerified:
      'Binance-подключение успешно проверено.',
    accountDeleted:
      'Binance-подключение удалено.',
    testnet: 'TESTNET',
    live: 'LIVE',
    liveWarning:
      'LIVE подключает реальный аккаунт. Автоматическая торговля пока не включена.',
  },
  en: {
    title: 'Binance connection',
    subtitle:
      'Secure account connection, balances, positions and open orders',
    authTitle: 'Sign in to SignalAI Pro',
    authSubtitle:
      'Binance accounts are available only to their authenticated owner',
    login: 'Sign in',
    register: 'Create account',
    username: 'Username',
    email: 'Email — optional',
    password: 'Password',
    loggingIn: 'Signing in…',
    registering: 'Creating account…',
    accountOwner: 'User',
    logout: 'Sign out',
    connectTitle: 'Connect Binance',
    connectSubtitle:
      'Keys are encrypted before storage and are never returned by the API',
    label: 'Connection label',
    environment: 'Environment',
    apiKey: 'API key',
    secretKey: 'Secret key',
    connect: 'Save connection',
    saving: 'Saving…',
    securityTitle: 'Security requirements',
    securityOne:
      'Use a separate API key only for SignalAI Pro.',
    securityTwo:
      'Withdrawal permission must be disabled.',
    securityThree:
      'Use TESTNET until automated trading is introduced.',
    accounts: 'Connected accounts',
    noAccounts: 'No Binance accounts connected yet',
    verify: 'Verify',
    verifying: 'Verifying…',
    portfolio: 'Load portfolio',
    loadingPortfolio: 'Synchronizing…',
    remove: 'Delete',
    confirmDelete:
      'Delete this Binance connection?',
    connected: 'Connected',
    unverified: 'Unverified',
    error: 'Error',
    unsafe: 'Unsafe key',
    trading: 'Trading',
    deposits: 'Deposits',
    withdrawals: 'Withdrawals',
    yes: 'Yes',
    no: 'No',
    unknown: 'Unknown',
    lastCheck: 'Last check',
    balances: 'Balances',
    positions: 'Positions',
    orders: 'Open orders',
    noBalances: 'No non-zero balances',
    noPositions: 'No positions',
    noOrders: 'No open orders',
    asset: 'Asset',
    free: 'Free',
    locked: 'Locked',
    total: 'Total',
    symbol: 'Symbol',
    quantity: 'Quantity',
    entryPrice: 'Entry price',
    unrealizedPnl: 'Unrealized PnL',
    side: 'Side',
    type: 'Type',
    price: 'Price',
    executed: 'Executed',
    status: 'Status',
    captured: 'Portfolio snapshot',
    refreshAccounts: 'Refresh accounts',
    sessionExpired:
      'Session expired. Please sign in again.',
    genericError:
      'The operation could not be completed',
    accountSaved:
      'Binance connection saved. Run verification.',
    accountVerified:
      'Binance connection verified successfully.',
    accountDeleted:
      'Binance connection deleted.',
    testnet: 'TESTNET',
    live: 'LIVE',
    liveWarning:
      'LIVE connects a real account. Automated trading is not enabled yet.',
  },
} as const;

function amount(
  value: number | null,
): string {
  if (
    value === null
    || !Number.isFinite(value)
  ) {
    return '—';
  }

  const digits =
    Math.abs(value) < 1
      ? 8
      : 4;

  return new Intl.NumberFormat(
    undefined,
    {
      maximumFractionDigits: digits,
    },
  ).format(value);
}

function dateTime(
  value: string | null,
  language: Language,
): string {
  if (!value) {
    return '—';
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return '—';
  }

  return date.toLocaleString(
    language === 'ru'
      ? 'ru-RU'
      : 'en-US',
  );
}

function errorText(
  error: unknown,
  fallback: string,
): string {
  if (error instanceof ExchangeApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

function statusText(
  account: ExchangeAccount,
  language: Language,
): string {
  const t = copy[language];

  const values = {
    CONNECTED: t.connected,
    UNVERIFIED: t.unverified,
    ERROR: t.error,
    UNSAFE: t.unsafe,
  };

  return values[account.status];
}

function permissionText(
  value: boolean | null,
  language: Language,
): string {
  const t = copy[language];

  if (value === true) {
    return t.yes;
  }

  if (value === false) {
    return t.no;
  }

  return t.unknown;
}

export function ExchangeCenter({
  language,
}: ExchangeCenterProps) {
  const t = copy[language];

  const [
    token,
    setToken,
  ] = useState<string | null>(
    () => readAccessToken(),
  );

  const [
    user,
    setUser,
  ] = useState<AuthUser | null>(null);

  const [
    accounts,
    setAccounts,
  ] = useState<ExchangeAccount[]>([]);

  const [
    selectedAccountId,
    setSelectedAccountId,
  ] = useState<number | null>(null);

  const [
    portfolio,
    setPortfolio,
  ] = useState<PortfolioSnapshot | null>(
    null,
  );

  const [
    authMode,
    setAuthMode,
  ] = useState<AuthMode>('login');

  const [
    username,
    setUsername,
  ] = useState('');

  const [
    email,
    setEmail,
  ] = useState('');

  const [
    password,
    setPassword,
  ] = useState('');

  const [
    authBusy,
    setAuthBusy,
  ] = useState(false);

  const [
    sessionBusy,
    setSessionBusy,
  ] = useState(Boolean(token));

  const [
    accountBusy,
    setAccountBusy,
  ] = useState(false);

  const [
    verifyingId,
    setVerifyingId,
  ] = useState<number | null>(null);

  const [
    portfolioBusy,
    setPortfolioBusy,
  ] = useState(false);

  const [
    deletingId,
    setDeletingId,
  ] = useState<number | null>(null);

  const [
    label,
    setLabel,
  ] = useState('Binance');

  const [
    environment,
    setEnvironment,
  ] = useState<ExchangeEnvironment>(
    'TESTNET',
  );

  const [
    apiKey,
    setApiKey,
  ] = useState('');

  const [
    secretKey,
    setSecretKey,
  ] = useState('');

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const [
    notice,
    setNotice,
  ] = useState<string | null>(null);

  const selectedAccount = useMemo(
    () =>
      accounts.find(
        (account) =>
          account.id === selectedAccountId,
      ) ?? null,
    [
      accounts,
      selectedAccountId,
    ],
  );

  const establishSession = useCallback(
    async (
      currentToken: string,
    ): Promise<void> => {
      setSessionBusy(true);
      setError(null);

      try {
        const [
          currentUser,
          currentAccounts,
        ] = await Promise.all([
          fetchCurrentUser(currentToken),
          fetchExchangeAccounts(
            currentToken,
          ),
        ]);

        setUser(currentUser);
        setAccounts(currentAccounts);

        setSelectedAccountId(
          (current) => {
            if (
              current !== null
              && currentAccounts.some(
                (account) =>
                  account.id === current,
              )
            ) {
              return current;
            }

            return (
              currentAccounts[0]?.id
              ?? null
            );
          },
        );
      } catch (loadError) {
        removeAccessToken();
        setToken(null);
        setUser(null);
        setAccounts([]);
        setPortfolio(null);

        setError(
          loadError instanceof ExchangeApiError
          && loadError.status === 401
            ? t.sessionExpired
            : errorText(
                loadError,
                t.genericError,
              ),
        );
      } finally {
        setSessionBusy(false);
      }
    },
    [
      t.genericError,
      t.sessionExpired,
    ],
  );

  useEffect(() => {
    if (token) {
      void establishSession(token);
    } else {
      setSessionBusy(false);
    }
  }, [
    token,
    establishSession,
  ]);

  const refreshAccounts = useCallback(
    async (
      currentToken: string,
    ): Promise<ExchangeAccount[]> => {
      const loaded =
        await fetchExchangeAccounts(
          currentToken,
        );

      setAccounts(loaded);

      setSelectedAccountId(
        (current) => {
          if (
            current !== null
            && loaded.some(
              (account) =>
                account.id === current,
            )
          ) {
            return current;
          }

          return loaded[0]?.id ?? null;
        },
      );

      return loaded;
    },
    [],
  );

  async function submitAuth(
    event: FormEvent,
  ): Promise<void> {
    event.preventDefault();

    setAuthBusy(true);
    setError(null);
    setNotice(null);

    try {
      if (authMode === 'register') {
        await registerUser(
          username.trim(),
          password,
          email,
        );
      }

      const result = await loginUser(
        username.trim(),
        password,
      );

      saveAccessToken(
        result.access_token,
      );

      setPassword('');
      setToken(result.access_token);
    } catch (authError) {
      setError(
        errorText(
          authError,
          t.genericError,
        ),
      );
    } finally {
      setAuthBusy(false);
    }
  }

  async function submitConnection(
    event: FormEvent,
  ): Promise<void> {
    event.preventDefault();

    if (!token) {
      return;
    }

    setAccountBusy(true);
    setError(null);
    setNotice(null);

    try {
      const saved =
        await saveExchangeAccount(
          token,
          {
            label: label.trim(),
            environment,
            api_key: apiKey,
            secret_key: secretKey,
          },
        );

      setApiKey('');
      setSecretKey('');
      setSelectedAccountId(saved.id);
      setPortfolio(null);

      await refreshAccounts(token);

      setNotice(t.accountSaved);
    } catch (saveError) {
      setError(
        errorText(
          saveError,
          t.genericError,
        ),
      );
    } finally {
      setAccountBusy(false);
    }
  }

  async function verifyAccount(
    accountId: number,
  ): Promise<void> {
    if (!token) {
      return;
    }

    setVerifyingId(accountId);
    setError(null);
    setNotice(null);

    try {
      await verifyExchangeAccount(
        token,
        accountId,
      );

      await refreshAccounts(token);

      setSelectedAccountId(accountId);
      setNotice(t.accountVerified);
    } catch (verifyError) {
      await refreshAccounts(token)
        .catch(() => undefined);

      setError(
        errorText(
          verifyError,
          t.genericError,
        ),
      );
    } finally {
      setVerifyingId(null);
    }
  }

  async function loadPortfolio(
    accountId: number,
  ): Promise<void> {
    if (!token) {
      return;
    }

    setPortfolioBusy(true);
    setError(null);
    setNotice(null);
    setSelectedAccountId(accountId);

    try {
      const snapshot =
        await fetchExchangePortfolio(
          token,
          accountId,
        );

      setPortfolio(snapshot);

      await refreshAccounts(token);
    } catch (portfolioError) {
      await refreshAccounts(token)
        .catch(() => undefined);

      setPortfolio(null);

      setError(
        errorText(
          portfolioError,
          t.genericError,
        ),
      );
    } finally {
      setPortfolioBusy(false);
    }
  }

  async function removeAccount(
    accountId: number,
  ): Promise<void> {
    if (
      !token
      || !window.confirm(
        t.confirmDelete,
      )
    ) {
      return;
    }

    setDeletingId(accountId);
    setError(null);
    setNotice(null);

    try {
      await deleteExchangeAccount(
        token,
        accountId,
      );

      const remaining =
        await refreshAccounts(token);

      if (
        selectedAccountId
        === accountId
      ) {
        setSelectedAccountId(
          remaining[0]?.id ?? null,
        );
        setPortfolio(null);
      }

      setNotice(t.accountDeleted);
    } catch (deleteError) {
      setError(
        errorText(
          deleteError,
          t.genericError,
        ),
      );
    } finally {
      setDeletingId(null);
    }
  }

  function logout(): void {
    removeAccessToken();
    setToken(null);
    setUser(null);
    setAccounts([]);
    setSelectedAccountId(null);
    setPortfolio(null);
    setError(null);
    setNotice(null);
  }

  if (sessionBusy) {
    return (
      <section className="exchange-center">
        <div className="exchange-state">
          <LoaderCircle
            className="is-spinning"
            size={25}
          />
        </div>
      </section>
    );
  }

  if (!token || !user) {
    return (
      <section className="exchange-center">
        <div className="exchange-page-heading">
          <div>
            <span>
              <WalletCards size={16} />
              Binance
            </span>

            <h2>{t.title}</h2>
            <p>{t.subtitle}</p>
          </div>
        </div>

        <div className="exchange-auth-layout">
          <form
            className="exchange-auth-card"
            onSubmit={(event) =>
              void submitAuth(event)
            }
          >
            <div className="exchange-auth-icon">
              {authMode === 'login'
                ? <LogIn size={25} />
                : <UserPlus size={25} />}
            </div>

            <h3>{t.authTitle}</h3>
            <p>{t.authSubtitle}</p>

            <div className="exchange-auth-tabs">
              <button
                type="button"
                className={
                  authMode === 'login'
                    ? 'active'
                    : ''
                }
                onClick={() =>
                  setAuthMode('login')
                }
              >
                {t.login}
              </button>

              <button
                type="button"
                className={
                  authMode === 'register'
                    ? 'active'
                    : ''
                }
                onClick={() =>
                  setAuthMode('register')
                }
              >
                {t.register}
              </button>
            </div>

            <label>
              <span>{t.username}</span>
              <input
                required
                minLength={3}
                maxLength={64}
                autoComplete="username"
                value={username}
                onChange={(event) =>
                  setUsername(
                    event.target.value,
                  )
                }
              />
            </label>

            {authMode === 'register' && (
              <label>
                <span>{t.email}</span>
                <input
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) =>
                    setEmail(
                      event.target.value,
                    )
                  }
                />
              </label>
            )}

            <label>
              <span>{t.password}</span>
              <input
                required
                type="password"
                minLength={8}
                maxLength={128}
                autoComplete={
                  authMode === 'login'
                    ? 'current-password'
                    : 'new-password'
                }
                value={password}
                onChange={(event) =>
                  setPassword(
                    event.target.value,
                  )
                }
              />
            </label>

            {error && (
              <div className="exchange-alert exchange-alert--error">
                <AlertTriangle size={17} />
                {error}
              </div>
            )}

            <button
              type="submit"
              className="exchange-primary-button"
              disabled={authBusy}
            >
              {authBusy && (
                <LoaderCircle
                  className="is-spinning"
                  size={17}
                />
              )}

              {authBusy
                ? (
                    authMode === 'login'
                      ? t.loggingIn
                      : t.registering
                  )
                : (
                    authMode === 'login'
                      ? t.login
                      : t.register
                  )}
            </button>
          </form>

          <aside className="exchange-security-card">
            <ShieldCheck size={28} />
            <h3>{t.securityTitle}</h3>

            <ul>
              <li>{t.securityOne}</li>
              <li>{t.securityTwo}</li>
              <li>{t.securityThree}</li>
            </ul>
          </aside>
        </div>
      </section>
    );
  }

  return (
    <section className="exchange-center">
      <div className="exchange-page-heading">
        <div>
          <span>
            <WalletCards size={16} />
            Binance
          </span>

          <h2>{t.title}</h2>
          <p>{t.subtitle}</p>
        </div>

        <div className="exchange-user">
          <div>
            <span>{t.accountOwner}</span>
            <strong>{user.username}</strong>
          </div>

          <button
            type="button"
            onClick={logout}
          >
            <LogOut size={16} />
            {t.logout}
          </button>
        </div>
      </div>

      {error && (
        <div className="exchange-alert exchange-alert--error">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}

      {notice && (
        <div className="exchange-alert exchange-alert--success">
          <CheckCircle2 size={18} />
          {notice}
        </div>
      )}

      <div className="exchange-connect-grid">
        <form
          className="exchange-connect-card"
          onSubmit={(event) =>
            void submitConnection(event)
          }
        >
          <div className="exchange-card-title">
            <div>
              <KeyRound size={19} />
              <div>
                <h3>{t.connectTitle}</h3>
                <p>{t.connectSubtitle}</p>
              </div>
            </div>
          </div>

          <div className="exchange-form-grid">
            <label>
              <span>{t.label}</span>
              <input
                required
                maxLength={80}
                value={label}
                onChange={(event) =>
                  setLabel(
                    event.target.value,
                  )
                }
              />
            </label>

            <label>
              <span>{t.environment}</span>
              <select
                value={environment}
                onChange={(event) =>
                  setEnvironment(
                    event.target.value as ExchangeEnvironment,
                  )
                }
              >
                <option value="TESTNET">
                  {t.testnet}
                </option>
                <option value="LIVE">
                  {t.live}
                </option>
              </select>
            </label>

            <label>
              <span>{t.apiKey}</span>
              <input
                required
                type="password"
                minLength={8}
                maxLength={512}
                autoComplete="off"
                value={apiKey}
                onChange={(event) =>
                  setApiKey(
                    event.target.value,
                  )
                }
              />
            </label>

            <label>
              <span>{t.secretKey}</span>
              <input
                required
                type="password"
                minLength={8}
                maxLength={512}
                autoComplete="off"
                value={secretKey}
                onChange={(event) =>
                  setSecretKey(
                    event.target.value,
                  )
                }
              />
            </label>
          </div>

          {environment === 'LIVE' && (
            <div className="exchange-live-warning">
              <AlertTriangle size={16} />
              {t.liveWarning}
            </div>
          )}

          <button
            type="submit"
            className="exchange-primary-button"
            disabled={accountBusy}
          >
            {accountBusy
              ? (
                  <LoaderCircle
                    className="is-spinning"
                    size={17}
                  />
                )
              : <PlugZap size={17} />}

            {accountBusy
              ? t.saving
              : t.connect}
          </button>
        </form>

        <aside className="exchange-security-card exchange-security-card--compact">
          <ShieldCheck size={25} />
          <h3>{t.securityTitle}</h3>

          <ul>
            <li>{t.securityOne}</li>
            <li>{t.securityTwo}</li>
            <li>{t.securityThree}</li>
          </ul>
        </aside>
      </div>

      <section className="exchange-accounts-section">
        <div className="exchange-section-title">
          <div>
            <h3>{t.accounts}</h3>
            <span>{accounts.length}</span>
          </div>

          <button
            type="button"
            onClick={() => {
              if (token) {
                void refreshAccounts(token);
              }
            }}
          >
            <RefreshCw size={16} />
            {t.refreshAccounts}
          </button>
        </div>

        {accounts.length === 0 ? (
          <div className="exchange-empty-state">
            <PlugZap size={28} />
            <strong>{t.noAccounts}</strong>
          </div>
        ) : (
          <div className="exchange-account-grid">
            {accounts.map((account) => (
              <article
                key={account.id}
                className={[
                  'exchange-account-card',
                  (
                    selectedAccountId
                    === account.id
                      ? 'selected'
                      : ''
                  ),
                ].join(' ')}
                onClick={() => {
                  setSelectedAccountId(
                    account.id,
                  );
                  setPortfolio(null);
                }}
              >
                <div className="exchange-account-card__top">
                  <div>
                    <span>
                      {account.exchange}
                      {' · '}
                      {account.environment}
                    </span>

                    <h4>{account.label}</h4>
                    <code>
                      {account.api_key_hint}
                    </code>
                  </div>

                  <b
                    className={[
                      'exchange-status',
                      (
                        `exchange-status--${
                          account.status
                          .toLowerCase()
                        }`
                      ),
                    ].join(' ')}
                  >
                    {statusText(
                      account,
                      language,
                    )}
                  </b>
                </div>

                <div className="exchange-permissions">
                  <span>
                    {t.trading}
                    <b>
                      {permissionText(
                        account.can_trade,
                        language,
                      )}
                    </b>
                  </span>

                  <span>
                    {t.deposits}
                    <b>
                      {permissionText(
                        account.can_deposit,
                        language,
                      )}
                    </b>
                  </span>

                  <span>
                    {t.withdrawals}
                    <b
                      className={
                        account.can_withdraw
                          ? 'is-danger'
                          : ''
                      }
                    >
                      {permissionText(
                        account.can_withdraw,
                        language,
                      )}
                    </b>
                  </span>
                </div>

                {account.last_error && (
                  <p className="exchange-account-error">
                    <AlertTriangle size={14} />
                    {account.last_error}
                  </p>
                )}

                <div className="exchange-account-date">
                  {t.lastCheck}
                  {': '}
                  {dateTime(
                    account.last_checked_at,
                    language,
                  )}
                </div>

                <div className="exchange-account-actions">
                  <button
                    type="button"
                    disabled={
                      verifyingId
                      === account.id
                    }
                    onClick={(event) => {
                      event.stopPropagation();

                      void verifyAccount(
                        account.id,
                      );
                    }}
                  >
                    {verifyingId
                      === account.id
                      ? (
                          <LoaderCircle
                            size={15}
                            className="is-spinning"
                          />
                        )
                      : (
                          <ShieldCheck
                            size={15}
                          />
                        )}

                    {verifyingId
                      === account.id
                      ? t.verifying
                      : t.verify}
                  </button>

                  <button
                    type="button"
                    disabled={
                      portfolioBusy
                      && selectedAccountId
                      === account.id
                    }
                    onClick={(event) => {
                      event.stopPropagation();

                      void loadPortfolio(
                        account.id,
                      );
                    }}
                  >
                    {portfolioBusy
                      && selectedAccountId
                      === account.id
                      ? (
                          <LoaderCircle
                            size={15}
                            className="is-spinning"
                          />
                        )
                      : (
                          <CircleDollarSign
                            size={15}
                          />
                        )}

                    {portfolioBusy
                      && selectedAccountId
                      === account.id
                      ? t.loadingPortfolio
                      : t.portfolio}
                  </button>

                  <button
                    type="button"
                    className="danger"
                    disabled={
                      deletingId
                      === account.id
                    }
                    onClick={(event) => {
                      event.stopPropagation();

                      void removeAccount(
                        account.id,
                      );
                    }}
                  >
                    {deletingId
                      === account.id
                      ? (
                          <LoaderCircle
                            size={15}
                            className="is-spinning"
                          />
                        )
                      : <Trash2 size={15} />}

                    {t.remove}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {selectedAccount && token && (
        <ExchangeOrderCenter
          account={selectedAccount}
          language={language}
          token={token}
        />
      )}

      {selectedAccount && portfolio && (
        <section className="exchange-portfolio">
          <div className="exchange-section-title">
            <div>
              <h3>
                {selectedAccount.label}
              </h3>

              <span>
                {t.captured}
                {': '}
                {dateTime(
                  portfolio.captured_at,
                  language,
                )}
              </span>
            </div>

            <button
              type="button"
              disabled={portfolioBusy}
              onClick={() =>
                void loadPortfolio(
                  selectedAccount.id,
                )
              }
            >
              <RefreshCw size={16} />
              {t.loadingPortfolio}
            </button>
          </div>

          <div className="exchange-portfolio-grid">
            <article className="exchange-data-card">
              <div className="exchange-data-card__title">
                <WalletCards size={18} />
                <h4>{t.balances}</h4>
                <span>
                  {portfolio.balances.length}
                </span>
              </div>

              {portfolio.balances.length === 0 ? (
                <div className="exchange-table-empty">
                  {t.noBalances}
                </div>
              ) : (
                <div className="exchange-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>{t.asset}</th>
                        <th>{t.free}</th>
                        <th>{t.locked}</th>
                        <th>{t.total}</th>
                      </tr>
                    </thead>

                    <tbody>
                      {portfolio.balances.map(
                        (balance) => (
                          <tr
                            key={balance.asset}
                          >
                            <td>
                              <strong>
                                {balance.asset}
                              </strong>
                            </td>
                            <td>
                              {amount(
                                balance.free,
                              )}
                            </td>
                            <td>
                              {amount(
                                balance.locked,
                              )}
                            </td>
                            <td>
                              {amount(
                                balance.free
                                + balance.locked,
                              )}
                            </td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </article>

            <article className="exchange-data-card">
              <div className="exchange-data-card__title">
                <CircleDollarSign
                  size={18}
                />
                <h4>{t.positions}</h4>
                <span>
                  {portfolio.positions.length}
                </span>
              </div>

              {portfolio.positions.length === 0 ? (
                <div className="exchange-table-empty">
                  {t.noPositions}
                </div>
              ) : (
                <div className="exchange-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>{t.symbol}</th>
                        <th>{t.quantity}</th>
                        <th>{t.entryPrice}</th>
                        <th>
                          {t.unrealizedPnl}
                        </th>
                      </tr>
                    </thead>

                    <tbody>
                      {portfolio.positions.map(
                        (
                          position,
                          index,
                        ) => (
                          <tr
                            key={
                              `${position.symbol}-${index}`
                            }
                          >
                            <td>
                              <strong>
                                {position.symbol}
                              </strong>
                            </td>
                            <td>
                              {amount(
                                position.quantity,
                              )}
                            </td>
                            <td>
                              {amount(
                                position.entry_price,
                              )}
                            </td>
                            <td
                              className={
                                position
                                  .unrealized_pnl
                                  < 0
                                  ? 'is-negative'
                                  : 'is-positive'
                              }
                            >
                              {amount(
                                position
                                  .unrealized_pnl,
                              )}
                            </td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </article>
          </div>

          <article className="exchange-data-card exchange-orders-card">
            <div className="exchange-data-card__title">
              <PlugZap size={18} />
              <h4>{t.orders}</h4>
              <span>
                {portfolio.open_orders.length}
              </span>
            </div>

            {portfolio.open_orders.length === 0 ? (
              <div className="exchange-table-empty">
                {t.noOrders}
              </div>
            ) : (
              <div className="exchange-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t.symbol}</th>
                      <th>{t.side}</th>
                      <th>{t.type}</th>
                      <th>{t.price}</th>
                      <th>{t.quantity}</th>
                      <th>{t.executed}</th>
                      <th>{t.status}</th>
                    </tr>
                  </thead>

                  <tbody>
                    {portfolio.open_orders.map(
                      (order) => (
                        <tr
                          key={
                            order
                              .exchange_order_id
                          }
                        >
                          <td>
                            <strong>
                              {order.symbol}
                            </strong>
                          </td>
                          <td>
                            <b
                              className={
                                order.side
                                === 'BUY'
                                  ? 'is-positive'
                                  : 'is-negative'
                              }
                            >
                              {order.side}
                            </b>
                          </td>
                          <td>
                            {order.order_type}
                          </td>
                          <td>
                            {amount(
                              order.price,
                            )}
                          </td>
                          <td>
                            {amount(
                              order
                                .original_quantity,
                            )}
                          </td>
                          <td>
                            {amount(
                              order
                                .executed_quantity,
                            )}
                          </td>
                          <td>
                            {order.status}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </article>
        </section>
      )}
    </section>
  );
}
