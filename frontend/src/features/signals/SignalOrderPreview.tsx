import {
  FlaskConical,
  LoaderCircle,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import {
  FormEvent,
  useEffect,
  useMemo,
  useState,
} from 'react';

import './SignalOrderPreview.css';

import {
  ExchangeApiError,
  fetchExchangeAccounts,
  previewExchangeAccountSignalOrder,
  readAccessToken,
} from '../exchange/api';
import type {
  ExchangeAccount,
  SignalOrderPreviewPlan,
} from '../exchange/types';
import type {
  TradingSignal,
} from './types';

type Language = 'ru' | 'en';

interface SignalOrderPreviewProps {
  signal: TradingSignal;
  language: Language;
}

const copy = {
  ru: {
    title: 'Торговый план',
    subtitle:
      'Безопасная проверка AI-сигнала через Binance TESTNET',
    readOnly: 'Только preview',
    unavailable:
      'Для preview подходят только активные BINANCE SPOT LONG сигналы.',
    login:
      'Войдите в разделе Binance, чтобы проверить торговый план.',
    noAccounts:
      'Нет проверенного TESTNET-аккаунта с разрешением на торговлю.',
    loadingAccounts:
      'Загрузка TESTNET-аккаунтов…',
    account: 'TESTNET-аккаунт',
    quantity: 'Количество актива',
    preview: 'Проверить торговый план',
    previewing: 'Проверяем план…',
    invalidQuantity:
      'Введите положительное количество актива.',
    genericError:
      'Не удалось проверить торговый план.',
    valid: 'План прошёл risk-check',
    invalid: 'План заблокирован',
    side: 'Сторона',
    type: 'Тип',
    price: 'Цена входа',
    normalizedQuantity: 'Количество после округления',
    notional: 'Расчётная стоимость',
    balance: 'Доступный баланс',
    warnings: 'Предупреждения',
    errors: 'Блокирующие причины',
    noSubmission:
      'Этот экран не отправляет и не отменяет ордера.',
  },
  en: {
    title: 'Trading plan',
    subtitle:
      'Safe AI signal validation through Binance TESTNET',
    readOnly: 'Preview only',
    unavailable:
      'Only active BINANCE SPOT LONG signals are eligible.',
    login:
      'Sign in in the Binance section to preview the trading plan.',
    noAccounts:
      'No verified TESTNET account with trading permission is available.',
    loadingAccounts:
      'Loading TESTNET accounts…',
    account: 'TESTNET account',
    quantity: 'Asset quantity',
    preview: 'Preview trading plan',
    previewing: 'Previewing plan…',
    invalidQuantity:
      'Enter a positive asset quantity.',
    genericError:
      'Unable to preview the trading plan.',
    valid: 'Plan passed risk checks',
    invalid: 'Plan was blocked',
    side: 'Side',
    type: 'Type',
    price: 'Entry price',
    normalizedQuantity: 'Normalized quantity',
    notional: 'Estimated notional',
    balance: 'Available balance',
    warnings: 'Warnings',
    errors: 'Blocking reasons',
    noSubmission:
      'This screen does not submit or cancel orders.',
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

  return value.toLocaleString(
    undefined,
    {
      maximumFractionDigits: 8,
    },
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

export function SignalOrderPreview({
  signal,
  language,
}: SignalOrderPreviewProps) {
  const t = copy[language];
  const token = readAccessToken();

  const [
    accounts,
    setAccounts,
  ] = useState<ExchangeAccount[]>([]);

  const [
    accountId,
    setAccountId,
  ] = useState('');

  const [
    quantity,
    setQuantity,
  ] = useState('');

  const [
    plan,
    setPlan,
  ] = useState<
    SignalOrderPreviewPlan | null
  >(null);

  const [
    loadingAccounts,
    setLoadingAccounts,
  ] = useState(false);

  const [
    previewing,
    setPreviewing,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const eligible = useMemo(
    () =>
      signal.exchange === 'BINANCE'
      && signal.market_type === 'SPOT'
      && signal.side === 'LONG'
      && (
        signal.status === 'ACTIVE'
        || signal.status
          === 'ENTRY_REACHED'
      ),
    [
      signal.exchange,
      signal.market_type,
      signal.side,
      signal.status,
    ],
  );

  useEffect(() => {
    setPlan(null);
    setError(null);
    setAccounts([]);
    setAccountId('');

    if (!eligible || !token) {
      setLoadingAccounts(false);
      return;
    }

    let active = true;

    setLoadingAccounts(true);

    void fetchExchangeAccounts(token)
      .then((items) => {
        if (!active) {
          return;
        }

        const candidates = items.filter(
          (account) =>
            account.environment === 'TESTNET'
            && account.status === 'CONNECTED'
            && account.can_trade === true,
        );

        setAccounts(candidates);
        setAccountId(
          candidates.length > 0
            ? String(candidates[0].id)
            : '',
        );
      })
      .catch((loadError) => {
        if (active) {
          setError(
            errorText(
              loadError,
              t.genericError,
            ),
          );
        }
      })
      .finally(() => {
        if (active) {
          setLoadingAccounts(false);
        }
      });

    return () => {
      active = false;
    };
  }, [
    eligible,
    signal.id,
    token,
    t.genericError,
  ]);

  async function requestPreview(
    event: FormEvent,
  ) {
    event.preventDefault();

    const parsedQuantity = Number(quantity);
    const parsedAccountId = Number(accountId);

    if (
      !Number.isFinite(parsedQuantity)
      || parsedQuantity <= 0
    ) {
      setError(t.invalidQuantity);
      setPlan(null);
      return;
    }

    if (
      !token
      || !Number.isInteger(parsedAccountId)
      || parsedAccountId <= 0
    ) {
      setError(t.noAccounts);
      setPlan(null);
      return;
    }

    setPreviewing(true);
    setError(null);
    setPlan(null);

    try {
      const nextPlan = (
        await previewExchangeAccountSignalOrder(
          token,
          parsedAccountId,
          signal.id,
          {
            quantity: parsedQuantity,
          },
        )
      );

      setPlan(nextPlan);
    } catch (previewError) {
      setError(
        errorText(
          previewError,
          t.genericError,
        ),
      );
    } finally {
      setPreviewing(false);
    }
  }

  return (
    <section className="signal-order-preview">
      <header className="signal-order-preview__header">
        <div>
          <span>
            <FlaskConical size={15} />
            {t.readOnly}
          </span>

          <h3>{t.title}</h3>
          <p>{t.subtitle}</p>
        </div>

        <ShieldCheck size={24} />
      </header>

      {!eligible ? (
        <div className="signal-order-preview__notice">
          <ShieldAlert size={17} />
          {t.unavailable}
        </div>
      ) : !token ? (
        <div className="signal-order-preview__notice">
          <ShieldAlert size={17} />
          {t.login}
        </div>
      ) : loadingAccounts ? (
        <div className="signal-order-preview__notice">
          <LoaderCircle
            size={17}
            className="is-spinning"
          />
          {t.loadingAccounts}
        </div>
      ) : accounts.length === 0 ? (
        <div className="signal-order-preview__notice">
          <ShieldAlert size={17} />
          {t.noAccounts}
        </div>
      ) : (
        <form
          className="signal-order-preview__form"
          onSubmit={(event) =>
            void requestPreview(event)
          }
        >
          <label>
            <span>{t.account}</span>
            <select
              value={accountId}
              onChange={(event) => {
                setAccountId(
                  event.target.value,
                );
                setPlan(null);
              }}
            >
              {accounts.map(
                (account) => (
                  <option
                    key={account.id}
                    value={account.id}
                  >
                    {account.label}
                    {' · TESTNET'}
                  </option>
                ),
              )}
            </select>
          </label>

          <label>
            <span>{t.quantity}</span>
            <input
              type="number"
              min="0"
              step="any"
              inputMode="decimal"
              value={quantity}
              onChange={(event) => {
                setQuantity(
                  event.target.value,
                );
                setPlan(null);
              }}
              placeholder="0.001"
            />
          </label>

          <button
            type="submit"
            disabled={previewing}
          >
            {previewing ? (
              <LoaderCircle
                size={17}
                className="is-spinning"
              />
            ) : (
              <ShieldCheck size={17} />
            )}

            {previewing
              ? t.previewing
              : t.preview}
          </button>
        </form>
      )}

      {error && (
        <div className="signal-order-preview__error">
          <ShieldAlert size={17} />
          {error}
        </div>
      )}

      {plan && (
        <div
          className={[
            'signal-order-preview__result',
            plan.preview.valid
              ? 'is-valid'
              : 'is-invalid',
          ].join(' ')}
        >
          <div className="signal-order-preview__result-title">
            <strong>
              {plan.preview.valid
                ? t.valid
                : t.invalid}
            </strong>

            <span>
              {plan.read_only
                ? t.readOnly
                : ''}
            </span>
          </div>

          <dl>
            <div>
              <dt>{t.side}</dt>
              <dd>{plan.intent.side}</dd>
            </div>

            <div>
              <dt>{t.type}</dt>
              <dd>{plan.intent.order_type}</dd>
            </div>

            <div>
              <dt>{t.price}</dt>
              <dd>
                {amount(
                  plan.preview.normalized_price,
                )}
              </dd>
            </div>

            <div>
              <dt>{t.normalizedQuantity}</dt>
              <dd>
                {amount(
                  plan.preview
                    .normalized_quantity,
                )}
              </dd>
            </div>

            <div>
              <dt>{t.notional}</dt>
              <dd>
                {amount(
                  plan.preview
                    .estimated_notional,
                )}
              </dd>
            </div>

            <div>
              <dt>{t.balance}</dt>
              <dd>
                {amount(
                  plan.preview
                    .available_balance,
                )}
                {' '}
                {
                  plan.preview
                    .balance_asset
                }
              </dd>
            </div>
          </dl>

          {plan.preview.warnings.length > 0 && (
            <div className="signal-order-preview__messages">
              <strong>{t.warnings}</strong>
              <ul>
                {plan.preview.warnings.map(
                  (warning) => (
                    <li key={warning}>
                      {warning}
                    </li>
                  ),
                )}
              </ul>
            </div>
          )}

          {plan.preview.errors.length > 0 && (
            <div className="signal-order-preview__messages is-error">
              <strong>{t.errors}</strong>
              <ul>
                {plan.preview.errors.map(
                  (item) => (
                    <li key={item}>
                      {item}
                    </li>
                  ),
                )}
              </ul>
            </div>
          )}
        </div>
      )}

      <small className="signal-order-preview__safety">
        {t.noSubmission}
      </small>
    </section>
  );
}
