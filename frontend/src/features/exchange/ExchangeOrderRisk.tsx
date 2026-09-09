import {
  AlertTriangle,
  CheckCircle2,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import {
  useEffect,
  useState,
} from 'react';

import './ExchangeOrderRisk.css';

import {
  ExchangeApiError,
  fetchExchangeAccountOrderRisk,
} from './api';
import type {
  AccountOrderRiskStatus,
  ExchangeAccount,
  Language,
} from './types';

interface ExchangeOrderRiskProps {
  account: ExchangeAccount;
  language: Language;
  refreshKey: number;
  token: string;
}

const copy = {
  ru: {
    title: 'Лимиты TESTNET',
    subtitle:
      'Фактическое использование серверных лимитов аккаунта',
    refresh: 'Обновить',
    loading: 'Загружаем лимиты',
    unavailable:
      'Статус риска доступен для подключённого TESTNET-аккаунта с разрешением на торговлю.',
    failed:
      'Не удалось загрузить статус лимитов.',
    available: 'Отправка ордеров доступна',
    blocked: 'Отправка ордеров заблокирована',
    enabled:
      'Серверный risk guard разрешает TESTNET-исполнение.',
    disabled:
      'Один или несколько серверных лимитов исчерпаны или отключены.',
    daily: 'Дневной объём',
    openOrders: 'Открытые ордера',
    used: 'Использовано',
    remaining: 'Осталось',
    perOrder: 'Максимум на ордер',
    symbols: 'Разрешённые пары',
    allSymbols: 'Все TESTNET-пары',
    periodStart: 'Начало периода',
    reset: 'Сброс дневного лимита',
    unlimited: 'Без лимита',
    orders: 'орд.',
    source: 'Источник',
  },
  en: {
    title: 'TESTNET limits',
    subtitle:
      'Current server-side account risk usage',
    refresh: 'Refresh',
    loading: 'Loading limits',
    unavailable:
      'Risk status requires a connected TESTNET account with trading permission.',
    failed:
      'Unable to load risk status.',
    available: 'Order submission available',
    blocked: 'Order submission blocked',
    enabled:
      'The server risk guard allows TESTNET execution.',
    disabled:
      'One or more server limits are exhausted or disabled.',
    daily: 'Daily notional',
    openOrders: 'Open orders',
    used: 'Used',
    remaining: 'Remaining',
    perOrder: 'Maximum per order',
    symbols: 'Allowed symbols',
    allSymbols: 'All TESTNET symbols',
    periodStart: 'Period started',
    reset: 'Daily limit resets',
    unlimited: 'Unlimited',
    orders: 'orders',
    source: 'Source',
  },
} as const;

function amount(
  value: number,
): string {
  return value.toLocaleString(
    undefined,
    {
      maximumFractionDigits: 8,
    },
  );
}

function percentage(
  value: number,
  maximum: number | null,
): number | null {
  if (
    maximum === null
    || maximum <= 0
  ) {
    return null;
  }

  return Math.min(
    100,
    Math.max(
      0,
      (value / maximum) * 100,
    ),
  );
}

function dateTime(
  value: string,
  language: Language,
): string {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return (
    parsed.toLocaleString(
      language === 'ru'
        ? 'ru-RU'
        : 'en-US',
      {
        timeZone: 'UTC',
        dateStyle: 'medium',
        timeStyle: 'short',
      },
    )
    + ' UTC'
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

export function ExchangeOrderRisk({
  account,
  language,
  refreshKey,
  token,
}: ExchangeOrderRiskProps) {
  const t = copy[language];

  const [
    risk,
    setRisk,
  ] = useState<AccountOrderRiskStatus | null>(
    null,
  );

  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const accountReady = (
    account.environment === 'TESTNET'
    && account.status === 'CONNECTED'
    && account.can_trade === true
  );

  async function loadRisk(): Promise<void> {
    if (!accountReady) {
      setRisk(null);
      setError(null);
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const result = (
        await fetchExchangeAccountOrderRisk(
          token,
          account.id,
        )
      );

      setRisk(result);
    } catch (caught) {
      setError(
        errorText(
          caught,
          t.failed,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  useEffect(
    () => {
      setRisk(null);
      setError(null);

      if (accountReady) {
        void loadRisk();
      }
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

  const dailyUsage = risk
    ? percentage(
        risk.daily_notional,
        risk.max_daily_notional,
      )
    : null;

  const openOrderUsage = risk
    ? percentage(
        risk.open_orders,
        risk.max_open_orders,
      )
    : null;

  return (
    <section className="exchange-order-risk">
      <header className="exchange-order-risk-header">
        <div>
          <ShieldCheck size={19} />
          <div>
            <h3>{t.title}</h3>
            <p>{t.subtitle}</p>
          </div>
        </div>

        <button
          type="button"
          disabled={!accountReady || busy}
          onClick={() =>
            void loadRisk()
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
          {t.refresh}
        </button>
      </header>

      {!accountReady && (
        <div className="exchange-order-risk-warning">
          <ShieldAlert size={16} />
          <span>{t.unavailable}</span>
        </div>
      )}

      {error && (
        <div className="exchange-order-risk-error">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {busy && !risk && (
        <div className="exchange-order-risk-loading">
          <LoaderCircle
            size={16}
            className="is-spinning"
          />
          <span>{t.loading}</span>
        </div>
      )}

      {risk && (
        <>
          <div
            className={
              risk.order_submission_available
                ? 'exchange-order-risk-status available'
                : 'exchange-order-risk-status blocked'
            }
          >
            {risk.order_submission_available
              ? <CheckCircle2 size={18} />
              : <ShieldAlert size={18} />}

            <div>
              <strong>
                {risk.order_submission_available
                  ? t.available
                  : t.blocked}
              </strong>
              <span>
                {risk.order_submission_available
                  ? t.enabled
                  : t.disabled}
              </span>
            </div>
          </div>

          <div className="exchange-order-risk-metrics">
            <article>
              <div>
                <span>{t.daily}</span>
                <strong>
                  {amount(risk.daily_notional)}
                  {' / '}
                  {risk.max_daily_notional === null
                    ? t.unlimited
                    : amount(
                        risk.max_daily_notional,
                      )}
                </strong>
              </div>

              {dailyUsage !== null && (
                <div className="exchange-order-risk-progress">
                  <span
                    style={{
                      width: `${dailyUsage}%`,
                    }}
                  />
                </div>
              )}

              <small>
                {t.remaining}:{' '}
                {risk.remaining_daily_notional
                  === null
                  ? t.unlimited
                  : amount(
                      risk.remaining_daily_notional,
                    )}
              </small>
            </article>

            <article>
              <div>
                <span>{t.openOrders}</span>
                <strong>
                  {risk.open_orders}
                  {' / '}
                  {risk.max_open_orders === null
                    ? t.unlimited
                    : risk.max_open_orders}
                </strong>
              </div>

              {openOrderUsage !== null && (
                <div className="exchange-order-risk-progress">
                  <span
                    style={{
                      width: `${openOrderUsage}%`,
                    }}
                  />
                </div>
              )}

              <small>
                {t.remaining}:{' '}
                {risk.remaining_open_order_slots
                  === null
                  ? t.unlimited
                  : `${risk.remaining_open_order_slots} ${t.orders}`}
              </small>
            </article>
          </div>

          <dl className="exchange-order-risk-details">
            <div>
              <dt>{t.perOrder}</dt>
              <dd>
                {risk.max_order_notional === null
                  ? t.unlimited
                  : amount(
                      risk.max_order_notional,
                    )}
              </dd>
            </div>

            <div>
              <dt>{t.symbols}</dt>
              <dd>
                {risk.allowed_symbols.length === 0
                  ? t.allSymbols
                  : risk.allowed_symbols.join(', ')}
              </dd>
            </div>

            <div>
              <dt>{t.periodStart}</dt>
              <dd>
                {dateTime(
                  risk.period_started_at,
                  language,
                )}
              </dd>
            </div>

            <div>
              <dt>{t.reset}</dt>
              <dd>
                {dateTime(
                  risk.resets_at,
                  language,
                )}
              </dd>
            </div>

            <div>
              <dt>{t.source}</dt>
              <dd>{risk.source}</dd>
            </div>
          </dl>
        </>
      )}
    </section>
  );
}
