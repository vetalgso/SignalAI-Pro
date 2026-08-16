import {
  AlertTriangle,
  History,
  LoaderCircle,
  RefreshCw,
  RotateCw,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import {
  useEffect,
  useState,
} from 'react';

import './ExchangeOrderActivity.css';

import {
  cancelExchangeAccountOrder,
  ExchangeApiError,
  fetchExchangeAccountOpenOrders,
  fetchExchangeAccountOrderHistory,
  fetchExchangeAccountOrderStatus,
} from './api';
import type {
  AccountOrderJournal,
  AccountOrderResult,
  ExchangeAccount,
  Language,
} from './types';

interface ExchangeOrderActivityProps {
  account: ExchangeAccount;
  language: Language;
  refreshKey: number;
  token: string;
}

type ActivityView =
  | 'history'
  | 'open';

const copy = {
  ru: {
    title: 'Ордера аккаунта',
    subtitle:
      'Локальный журнал и состояние Binance Testnet',
    history: 'Журнал',
    open: 'Открытые',
    filter: 'Фильтр по символу',
    apply: 'Обновить',
    loading: 'Загрузка',
    emptyHistory: 'Записей в журнале пока нет',
    emptyOpen: 'Открытых ордеров нет',
    date: 'Дата',
    symbol: 'Пара',
    side: 'Сторона',
    type: 'Тип',
    quantity: 'Количество',
    filled: 'Исполнено',
    status: 'Статус',
    mode: 'Режим',
    actions: 'Действия',
    dryRun: 'Dry-run',
    exchange: 'Биржа',
    refreshStatus: 'Статус',
    cancel: 'Отменить',
    confirmCancel: 'Подтвердить',
    cancelHint:
      'Нажмите ещё раз для подтверждения отмены TESTNET-ордера.',
    loadFailed:
      'Не удалось загрузить данные ордеров.',
    statusFailed:
      'Не удалось обновить статус ордера.',
    cancelFailed:
      'Не удалось отменить ордер.',
    unavailable:
      'Удалённые операции доступны только для подключённого TESTNET-аккаунта с разрешением торговли.',
  },
  en: {
    title: 'Account orders',
    subtitle:
      'Local journal and Binance Testnet state',
    history: 'History',
    open: 'Open',
    filter: 'Filter by symbol',
    apply: 'Refresh',
    loading: 'Loading',
    emptyHistory: 'No journal entries yet',
    emptyOpen: 'No open orders',
    date: 'Date',
    symbol: 'Symbol',
    side: 'Side',
    type: 'Type',
    quantity: 'Quantity',
    filled: 'Filled',
    status: 'Status',
    mode: 'Mode',
    actions: 'Actions',
    dryRun: 'Dry-run',
    exchange: 'Exchange',
    refreshStatus: 'Status',
    cancel: 'Cancel',
    confirmCancel: 'Confirm',
    cancelHint:
      'Click again to confirm TESTNET order cancellation.',
    loadFailed:
      'Unable to load order data.',
    statusFailed:
      'Unable to refresh order status.',
    cancelFailed:
      'Unable to cancel the order.',
    unavailable:
      'Remote operations require a connected TESTNET account with trading permission.',
  },
} as const;

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

function amount(
  value: number | null,
): string {
  if (value === null) {
    return '—';
  }

  return value.toLocaleString(
    undefined,
    {
      maximumFractionDigits: 8,
    },
  );
}

function dateTime(
  value: string,
  language: Language,
): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString(
    language === 'ru'
      ? 'ru-RU'
      : 'en-US',
  );
}

export function ExchangeOrderActivity({
  account,
  language,
  refreshKey,
  token,
}: ExchangeOrderActivityProps) {
  const t = copy[language];

  const [
    view,
    setView,
  ] = useState<ActivityView>('history');

  const [
    symbolFilter,
    setSymbolFilter,
  ] = useState('');

  const [
    history,
    setHistory,
  ] = useState<AccountOrderJournal[]>([]);

  const [
    openOrders,
    setOpenOrders,
  ] = useState<AccountOrderResult[]>([]);

  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    statusBusyId,
    setStatusBusyId,
  ] = useState<string | null>(null);

  const [
    cancelBusyId,
    setCancelBusyId,
  ] = useState<string | null>(null);

  const [
    cancelCandidateId,
    setCancelCandidateId,
  ] = useState<string | null>(null);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const accountReady = (
    account.environment === 'TESTNET'
    && account.status === 'CONNECTED'
    && account.can_trade === true
  );

  async function loadActivity(
    filter: string = symbolFilter,
  ): Promise<void> {
    const normalizedFilter = (
      filter.trim().toUpperCase()
    );

    setBusy(true);
    setError(null);
    setCancelCandidateId(null);

    let loadError: string | null = null;

    try {
      const result = (
        await fetchExchangeAccountOrderHistory(
          token,
          account.id,
          {
            limit: 50,
            symbol:
              normalizedFilter.length > 0
                ? normalizedFilter
                : undefined,
          },
        )
      );

      setHistory(result);
    } catch (caught) {
      setHistory([]);
      loadError = errorText(
        caught,
        t.loadFailed,
      );
    }

    if (accountReady) {
      try {
        const result = (
          await fetchExchangeAccountOpenOrders(
            token,
            account.id,
            normalizedFilter.length > 0
              ? normalizedFilter
              : undefined,
          )
        );

        setOpenOrders(result);
      } catch (caught) {
        setOpenOrders([]);

        loadError = errorText(
          caught,
          t.loadFailed,
        );
      }
    } else {
      setOpenOrders([]);
    }

    setError(loadError);
    setBusy(false);
  }

  useEffect(
    () => {
      setSymbolFilter('');
      setView('history');
      setCancelCandidateId(null);

      void loadActivity('');
    },
    [
      account.can_trade,
      account.environment,
      account.id,
      account.status,
      refreshKey,
      token,
    ],
  );

  async function refreshOrderStatus(
    order: AccountOrderResult,
  ): Promise<void> {
    if (!order.exchange_order_id) {
      return;
    }

    setStatusBusyId(
      order.exchange_order_id,
    );
    setError(null);

    try {
      const result = (
        await fetchExchangeAccountOrderStatus(
          token,
          account.id,
          order.exchange_order_id,
          order.symbol,
        )
      );

      setOpenOrders(
        (current) =>
          current.map(
            (item) =>
              item.exchange_order_id
                === order.exchange_order_id
                ? result
                : item,
          ),
      );
    } catch (caught) {
      setError(
        errorText(
          caught,
          t.statusFailed,
        ),
      );
    } finally {
      setStatusBusyId(null);
    }
  }

  async function requestCancellation(
    order: AccountOrderResult,
  ): Promise<void> {
    const orderId = order.exchange_order_id;

    if (!orderId) {
      return;
    }

    if (cancelCandidateId !== orderId) {
      setCancelCandidateId(orderId);
      setError(null);
      return;
    }

    setCancelBusyId(orderId);
    setError(null);

    try {
      await cancelExchangeAccountOrder(
        token,
        account.id,
        orderId,
        order.symbol,
      );

      setCancelCandidateId(null);

      await loadActivity(
        symbolFilter,
      );
    } catch (caught) {
      setError(
        errorText(
          caught,
          t.cancelFailed,
        ),
      );
    } finally {
      setCancelBusyId(null);
    }
  }

  return (
    <section className="exchange-order-activity">
      <header className="exchange-order-activity-header">
        <div>
          <History size={19} />
          <div>
            <h3>{t.title}</h3>
            <p>{t.subtitle}</p>
          </div>
        </div>

        <button
          type="button"
          disabled={busy}
          onClick={() =>
            void loadActivity()
          }
        >
          <RefreshCw
            size={14}
            className={
              busy
                ? 'is-spinning'
                : undefined
            }
          />
          {busy
            ? t.loading
            : t.apply}
        </button>
      </header>

      {!accountReady && (
        <div className="exchange-order-activity-warning">
          <ShieldAlert size={16} />
          <span>{t.unavailable}</span>
        </div>
      )}

      {error && (
        <div className="exchange-order-activity-error">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="exchange-order-activity-controls">
        <div className="exchange-order-activity-tabs">
          <button
            type="button"
            className={
              view === 'history'
                ? 'active'
                : undefined
            }
            onClick={() =>
              setView('history')
            }
          >
            {t.history}
            <span>{history.length}</span>
          </button>

          <button
            type="button"
            className={
              view === 'open'
                ? 'active'
                : undefined
            }
            disabled={!accountReady}
            onClick={() =>
              setView('open')
            }
          >
            {t.open}
            <span>{openOrders.length}</span>
          </button>
        </div>

        <label>
          <span>{t.filter}</span>
          <input
            value={symbolFilter}
            placeholder="BTCUSDT"
            onChange={(event) =>
              setSymbolFilter(
                event.target.value
                  .toUpperCase()
                  .replace(/\s+/g, ''),
              )
            }
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();

                void loadActivity();
              }
            }}
          />
        </label>
      </div>

      {view === 'history' && (
        history.length === 0
          ? (
              <div className="exchange-order-activity-empty">
                {busy
                  ? t.loading
                  : t.emptyHistory}
              </div>
            )
          : (
              <div className="exchange-order-activity-table">
                <table>
                  <thead>
                    <tr>
                      <th>{t.date}</th>
                      <th>{t.symbol}</th>
                      <th>{t.side}</th>
                      <th>{t.type}</th>
                      <th>{t.quantity}</th>
                      <th>{t.status}</th>
                      <th>{t.mode}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(
                      (order) => (
                        <tr key={order.journal_id}>
                          <td>
                            {dateTime(
                              order.created_at,
                              language,
                            )}
                          </td>
                          <td>{order.symbol}</td>
                          <td>{order.side}</td>
                          <td>{order.order_type}</td>
                          <td>
                            {amount(
                              order.normalized_quantity
                              ?? order.requested_quantity,
                            )}
                          </td>
                          <td>{order.status}</td>
                          <td>
                            {order.dry_run
                              ? t.dryRun
                              : t.exchange}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            )
      )}

      {view === 'open' && (
        openOrders.length === 0
          ? (
              <div className="exchange-order-activity-empty">
                {busy
                  ? t.loading
                  : t.emptyOpen}
              </div>
            )
          : (
              <div className="exchange-order-activity-table">
                <table>
                  <thead>
                    <tr>
                      <th>{t.symbol}</th>
                      <th>{t.side}</th>
                      <th>{t.type}</th>
                      <th>{t.quantity}</th>
                      <th>{t.filled}</th>
                      <th>{t.status}</th>
                      <th>{t.actions}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {openOrders.map(
                      (order) => {
                        const orderId = (
                          order.exchange_order_id
                        );
                        const confirming = (
                          orderId !== null
                          && cancelCandidateId
                            === orderId
                        );

                        return (
                          <tr
                            key={
                              orderId
                              ?? order.client_order_id
                            }
                          >
                            <td>{order.symbol}</td>
                            <td>{order.side}</td>
                            <td>{order.order_type}</td>
                            <td>
                              {amount(
                                order.requested_quantity,
                              )}
                            </td>
                            <td>
                              {amount(
                                order.filled_quantity,
                              )}
                            </td>
                            <td>{order.status}</td>
                            <td>
                              <div className="exchange-order-row-actions">
                                <button
                                  type="button"
                                  title={t.refreshStatus}
                                  disabled={
                                    !orderId
                                    || statusBusyId
                                      === orderId
                                    || cancelBusyId
                                      === orderId
                                  }
                                  onClick={() =>
                                    void refreshOrderStatus(
                                      order,
                                    )
                                  }
                                >
                                  {statusBusyId
                                    === orderId
                                    ? (
                                        <LoaderCircle
                                          size={13}
                                          className="is-spinning"
                                        />
                                      )
                                    : (
                                        <RotateCw
                                          size={13}
                                        />
                                      )}
                                  {t.refreshStatus}
                                </button>

                                <button
                                  type="button"
                                  className={
                                    confirming
                                      ? 'confirm'
                                      : 'danger'
                                  }
                                  title={
                                    confirming
                                      ? t.cancelHint
                                      : t.cancel
                                  }
                                  disabled={
                                    !orderId
                                    || cancelBusyId
                                      === orderId
                                    || statusBusyId
                                      === orderId
                                  }
                                  onClick={() =>
                                    void requestCancellation(
                                      order,
                                    )
                                  }
                                >
                                  {cancelBusyId
                                    === orderId
                                    ? (
                                        <LoaderCircle
                                          size={13}
                                          className="is-spinning"
                                        />
                                      )
                                    : (
                                        <XCircle
                                          size={13}
                                        />
                                      )}
                                  {confirming
                                    ? t.confirmCancel
                                    : t.cancel}
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      },
                    )}
                  </tbody>
                </table>
              </div>
            )
      )}
    </section>
  );
}
