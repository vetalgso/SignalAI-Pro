import {
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  LoaderCircle,
  ShieldCheck,
} from 'lucide-react';
import {
  FormEvent,
  useEffect,
  useMemo,
  useState,
} from 'react';

import './ExchangeOrderCenter.css';

import {
  ExchangeOrderActivity,
} from './ExchangeOrderActivity';
import {
  ExchangeApiError,
  executeExchangeAccountOrder,
  previewExchangeAccountOrder,
} from './api';
import type {
  AccountOrderJournal,
  AccountOrderPreview,
  AccountOrderRequest,
  AccountOrderSide,
  AccountOrderType,
  ExchangeAccount,
  Language,
} from './types';

interface ExchangeOrderCenterProps {
  account: ExchangeAccount;
  language: Language;
  token: string;
}

const copy = {
  ru: {
    title: 'Торговый терминал',
    subtitle:
      'Предварительная проверка и безопасная симуляция ордера',
    symbol: 'Торговая пара',
    side: 'Сторона',
    buy: 'Покупка',
    sell: 'Продажа',
    orderType: 'Тип ордера',
    market: 'Рыночный',
    limit: 'Лимитный',
    quantity: 'Количество',
    price: 'Лимитная цена',
    preview: 'Проверить ордер',
    previewing: 'Проверяем',
    dryRun: 'Выполнить dry-run',
    executing: 'Симуляция',
    safeMode: 'Безопасный режим',
    safeDescription:
      'Отправка на биржу отключена. Dry-run создаёт запись в журнале без реального ордера.',
    unavailable:
      'Торговля доступна только для проверенного TESTNET-аккаунта с разрешением на торговлю.',
    invalidFields:
      'Проверьте символ, количество и цену лимитного ордера.',
    previewFailed:
      'Не удалось проверить ордер.',
    executionFailed:
      'Не удалось выполнить dry-run.',
    previewTitle: 'Результат проверки',
    valid: 'Ордер прошёл проверку',
    invalid: 'Ордер не прошёл проверку',
    requestedQuantity: 'Запрошено',
    normalizedQuantity: 'После округления',
    estimatedNotional: 'Расчётная стоимость',
    availableBalance: 'Доступный баланс',
    warnings: 'Предупреждения',
    errors: 'Ошибки',
    resultTitle: 'Результат dry-run',
    status: 'Статус',
    journalId: 'Запись журнала',
    idempotency: 'Ключ операции',
    simulated: 'Симуляция',
    yes: 'Да',
    no: 'Нет',
  },
  en: {
    title: 'Trading terminal',
    subtitle:
      'Order preview and safe execution simulation',
    symbol: 'Trading pair',
    side: 'Side',
    buy: 'Buy',
    sell: 'Sell',
    orderType: 'Order type',
    market: 'Market',
    limit: 'Limit',
    quantity: 'Quantity',
    price: 'Limit price',
    preview: 'Preview order',
    previewing: 'Previewing',
    dryRun: 'Execute dry-run',
    executing: 'Simulating',
    safeMode: 'Safe mode',
    safeDescription:
      'Exchange submission is disabled. Dry-run creates a journal entry without placing a real order.',
    unavailable:
      'Trading requires a verified TESTNET account with trading permission.',
    invalidFields:
      'Check the symbol, quantity and limit order price.',
    previewFailed:
      'Unable to preview the order.',
    executionFailed:
      'Unable to execute the dry-run.',
    previewTitle: 'Preview result',
    valid: 'Order passed validation',
    invalid: 'Order failed validation',
    requestedQuantity: 'Requested',
    normalizedQuantity: 'Normalized',
    estimatedNotional: 'Estimated notional',
    availableBalance: 'Available balance',
    warnings: 'Warnings',
    errors: 'Errors',
    resultTitle: 'Dry-run result',
    status: 'Status',
    journalId: 'Journal entry',
    idempotency: 'Operation key',
    simulated: 'Simulated',
    yes: 'Yes',
    no: 'No',
  },
} as const;

function numberValue(
  value: string,
): number | null {
  if (value.trim().length === 0) {
    return null;
  }

  const parsed = Number(value);

  return Number.isFinite(parsed)
    ? parsed
    : null;
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

function requestKey(): string {
  if (
    typeof crypto !== 'undefined'
    && typeof crypto.randomUUID === 'function'
  ) {
    return `ui-${crypto.randomUUID()}`;
  }

  return (
    `ui-${Date.now()}-`
    + Math.random()
      .toString(16)
      .slice(2)
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

export function ExchangeOrderCenter({
  account,
  language,
  token,
}: ExchangeOrderCenterProps) {
  const t = copy[language];

  const [
    symbol,
    setSymbol,
  ] = useState('BTCUSDT');

  const [
    side,
    setSide,
  ] = useState<AccountOrderSide>('BUY');

  const [
    orderType,
    setOrderType,
  ] = useState<AccountOrderType>(
    'MARKET',
  );

  const [
    quantity,
    setQuantity,
  ] = useState('0.001');

  const [
    referencePrice,
    setReferencePrice,
  ] = useState('');

  const [
    preview,
    setPreview,
  ] = useState<AccountOrderPreview | null>(
    null,
  );

  const [
    previewRequest,
    setPreviewRequest,
  ] = useState<AccountOrderRequest | null>(
    null,
  );

  const [
    journal,
    setJournal,
  ] = useState<AccountOrderJournal | null>(
    null,
  );

  const [
    previewBusy,
    setPreviewBusy,
  ] = useState(false);

  const [
    executionBusy,
    setExecutionBusy,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const request = useMemo(
    (): AccountOrderRequest | null => {
      const normalizedSymbol = (
        symbol.trim().toUpperCase()
      );
      const parsedQuantity = numberValue(
        quantity,
      );
      const parsedPrice = numberValue(
        referencePrice,
      );

      if (
        normalizedSymbol.length === 0
        || parsedQuantity === null
        || parsedQuantity <= 0
        || (
          orderType === 'LIMIT'
          && (
            parsedPrice === null
            || parsedPrice <= 0
          )
        )
      ) {
        return null;
      }

      return {
        exchange: 'BINANCE',
        market_type: 'SPOT',
        symbol: normalizedSymbol,
        side,
        order_type: orderType,
        quantity: parsedQuantity,
        reference_price:
          orderType === 'LIMIT'
            ? parsedPrice
            : null,
        stop_loss: null,
        take_profit_1: null,
        take_profit_2: null,
        leverage: 1,
        reduce_only: false,
      };
    },
    [
      orderType,
      quantity,
      referencePrice,
      side,
      symbol,
    ],
  );

  const accountReady = (
    account.environment === 'TESTNET'
    && account.status === 'CONNECTED'
    && account.can_trade === true
  );

  useEffect(
    () => {
      setPreview(null);
      setPreviewRequest(null);
      setJournal(null);
      setError(null);
    },
    [
      account.id,
      orderType,
      quantity,
      referencePrice,
      side,
      symbol,
    ],
  );

  async function handlePreview(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    if (!request) {
      setError(t.invalidFields);
      return;
    }

    setPreviewBusy(true);
    setError(null);
    setJournal(null);

    try {
      const result = (
        await previewExchangeAccountOrder(
          token,
          account.id,
          request,
        )
      );

      setPreview(result);
      setPreviewRequest(request);
    } catch (caught) {
      setPreview(null);
      setPreviewRequest(null);
      setError(
        errorText(
          caught,
          t.previewFailed,
        ),
      );
    } finally {
      setPreviewBusy(false);
    }
  }

  async function handleDryRun(): Promise<void> {
    if (
      !request
      || !preview
      || !preview.valid
      || !previewRequest
      || JSON.stringify(request)
        !== JSON.stringify(previewRequest)
    ) {
      setError(t.invalidFields);
      return;
    }

    setExecutionBusy(true);
    setError(null);

    try {
      const result = (
        await executeExchangeAccountOrder(
          token,
          account.id,
          {
            ...request,
            idempotency_key: requestKey(),
            dry_run: true,
          },
        )
      );

      setJournal(result);
    } catch (caught) {
      setJournal(null);
      setError(
        errorText(
          caught,
          t.executionFailed,
        ),
      );
    } finally {
      setExecutionBusy(false);
    }
  }

  return (
    <section className="exchange-order-center">
      <header className="exchange-order-header">
        <div>
          <FlaskConical size={20} />
          <div>
            <h3>{t.title}</h3>
            <p>{t.subtitle}</p>
          </div>
        </div>

        <span className="exchange-order-safe-badge">
          <ShieldCheck size={14} />
          {t.safeMode}
        </span>
      </header>

      <div className="exchange-order-safety">
        <ShieldCheck size={17} />
        <span>{t.safeDescription}</span>
      </div>

      {!accountReady && (
        <div className="exchange-order-warning">
          <AlertTriangle size={17} />
          <span>{t.unavailable}</span>
        </div>
      )}

      {error && (
        <div className="exchange-order-error">
          <AlertTriangle size={17} />
          <span>{error}</span>
        </div>
      )}

      <form
        className="exchange-order-form"
        onSubmit={(event) =>
          void handlePreview(event)
        }
      >
        <div className="exchange-order-fields">
          <label>
            <span>{t.symbol}</span>
            <input
              required
              value={symbol}
              onChange={(event) =>
                setSymbol(
                  event.target.value
                    .toUpperCase()
                    .replace(/\s+/g, ''),
                )
              }
            />
          </label>

          <label>
            <span>{t.side}</span>
            <select
              value={side}
              onChange={(event) =>
                setSide(
                  event.target.value as AccountOrderSide,
                )
              }
            >
              <option value="BUY">
                {t.buy}
              </option>
              <option value="SELL">
                {t.sell}
              </option>
            </select>
          </label>

          <label>
            <span>{t.orderType}</span>
            <select
              value={orderType}
              onChange={(event) =>
                setOrderType(
                  event.target.value as AccountOrderType,
                )
              }
            >
              <option value="MARKET">
                {t.market}
              </option>
              <option value="LIMIT">
                {t.limit}
              </option>
            </select>
          </label>

          <label>
            <span>{t.quantity}</span>
            <input
              required
              min="0"
              step="any"
              type="number"
              value={quantity}
              onChange={(event) =>
                setQuantity(
                  event.target.value,
                )
              }
            />
          </label>

          {orderType === 'LIMIT' && (
            <label>
              <span>{t.price}</span>
              <input
                required
                min="0"
                step="any"
                type="number"
                value={referencePrice}
                onChange={(event) =>
                  setReferencePrice(
                    event.target.value,
                  )
                }
              />
            </label>
          )}
        </div>

        <div className="exchange-order-actions">
          <button
            type="submit"
            disabled={
              !accountReady
              || !request
              || previewBusy
              || executionBusy
            }
          >
            {previewBusy && (
              <LoaderCircle
                size={15}
                className="is-spinning"
              />
            )}
            {previewBusy
              ? t.previewing
              : t.preview}
          </button>

          <button
            type="button"
            className="exchange-order-dry-run"
            disabled={
              !accountReady
              || !preview?.valid
              || previewBusy
              || executionBusy
            }
            onClick={() =>
              void handleDryRun()
            }
          >
            {executionBusy
              ? (
                  <LoaderCircle
                    size={15}
                    className="is-spinning"
                  />
                )
              : <ShieldCheck size={15} />}
            {executionBusy
              ? t.executing
              : t.dryRun}
          </button>
        </div>
      </form>

      {preview && (
        <article
          className={
            preview.valid
              ? 'exchange-order-result valid'
              : 'exchange-order-result invalid'
          }
        >
          <div className="exchange-order-result-title">
            {preview.valid
              ? <CheckCircle2 size={18} />
              : <AlertTriangle size={18} />}
            <div>
              <h4>{t.previewTitle}</h4>
              <span>
                {preview.valid
                  ? t.valid
                  : t.invalid}
              </span>
            </div>
          </div>

          <dl>
            <div>
              <dt>{t.requestedQuantity}</dt>
              <dd>
                {amount(
                  preview.requested_quantity,
                )}
              </dd>
            </div>
            <div>
              <dt>{t.normalizedQuantity}</dt>
              <dd>
                {amount(
                  preview.normalized_quantity,
                )}
              </dd>
            </div>
            <div>
              <dt>{t.estimatedNotional}</dt>
              <dd>
                {amount(
                  preview.estimated_notional,
                )}
              </dd>
            </div>
            <div>
              <dt>{t.availableBalance}</dt>
              <dd>
                {amount(
                  preview.available_balance,
                )}
                {' '}
                {preview.balance_asset ?? ''}
              </dd>
            </div>
          </dl>

          {preview.warnings.length > 0 && (
            <div className="exchange-order-messages warning">
              <strong>{t.warnings}</strong>
              <ul>
                {preview.warnings.map(
                  (message) => (
                    <li key={message}>
                      {message}
                    </li>
                  ),
                )}
              </ul>
            </div>
          )}

          {preview.errors.length > 0 && (
            <div className="exchange-order-messages error">
              <strong>{t.errors}</strong>
              <ul>
                {preview.errors.map(
                  (message) => (
                    <li key={message}>
                      {message}
                    </li>
                  ),
                )}
              </ul>
            </div>
          )}
        </article>
      )}

      {journal && (
        <article className="exchange-order-journal">
          <div>
            <CheckCircle2 size={18} />
            <h4>{t.resultTitle}</h4>
          </div>

          <dl>
            <div>
              <dt>{t.status}</dt>
              <dd>{journal.status}</dd>
            </div>
            <div>
              <dt>{t.journalId}</dt>
              <dd>#{journal.journal_id}</dd>
            </div>
            <div>
              <dt>{t.simulated}</dt>
              <dd>
                {journal.simulated
                  ? t.yes
                  : t.no}
              </dd>
            </div>
            <div>
              <dt>{t.idempotency}</dt>
              <dd>{journal.idempotency_key}</dd>
            </div>
          </dl>
        </article>
      )}
      <ExchangeOrderActivity
        account={account}
        language={language}
        refreshKey={
          journal?.journal_id ?? 0
        }
        token={token}
      />

    </section>
  );
}
