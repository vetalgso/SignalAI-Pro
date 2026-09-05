import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  PauseCircle,
  RefreshCw,
} from 'lucide-react';
import {
  useEffect,
  useState,
} from 'react';

import './ExchangeOrderReconciliation.css';

import {
  ExchangeApiError,
  fetchExchangeAccountOrderReconciliationStatus,
} from './api';
import type {
  AccountOrderReconciliationStatus,
  ExchangeAccount,
  Language,
} from './types';

interface ExchangeOrderReconciliationProps {
  account: ExchangeAccount;
  language: Language;
  refreshKey: number;
  token: string;
}

const copy = {
  ru: {
    title: 'Синхронизация журнала',
    subtitle:
      'Автоматическая сверка открытых ордеров с Binance Testnet',
    refresh: 'Обновить',
    loading: 'Загружаем состояние worker',
    unavailable:
      'Автоматическая сверка доступна только для TESTNET-аккаунта.',
    failed:
      'Не удалось загрузить состояние синхронизации.',
    healthy: 'Автосверка работает',
    degraded: 'Автосверка требует внимания',
    disabled: 'Автосверка выключена',
    healthyDescription:
      'Worker регулярно проверяет удалённые статусы без создания или отмены ордеров.',
    degradedDescription:
      'Worker включён, но остановлен или сообщил об ошибке.',
    disabledDescription:
      'Фоновая синхронизация отключена настройками сервера.',
    readOnly: 'Только чтение',
    running: 'Работает',
    yes: 'Да',
    no: 'Нет',
    iterations: 'Итерации',
    failures: 'Ошибки',
    interval: 'Интервал',
    batch: 'Размер пакета',
    seconds: 'сек.',
    lastAction: 'Последнее действие',
    lastTick: 'Последняя проверка',
    lastError: 'Последняя ошибка',
    never: 'Ещё не выполнялась',
    noError: 'Нет',
    source: 'Источник',
  },
  en: {
    title: 'Journal synchronization',
    subtitle:
      'Automatic open-order reconciliation with Binance Testnet',
    refresh: 'Refresh',
    loading: 'Loading worker status',
    unavailable:
      'Automatic reconciliation is available only for a TESTNET account.',
    failed:
      'Unable to load reconciliation status.',
    healthy: 'Reconciliation is running',
    degraded: 'Reconciliation needs attention',
    disabled: 'Reconciliation is disabled',
    healthyDescription:
      'The worker checks remote status without creating or cancelling orders.',
    degradedDescription:
      'The worker is enabled but stopped or has reported an error.',
    disabledDescription:
      'Background reconciliation is disabled by server settings.',
    readOnly: 'Read only',
    running: 'Running',
    yes: 'Yes',
    no: 'No',
    iterations: 'Iterations',
    failures: 'Failures',
    interval: 'Interval',
    batch: 'Batch size',
    seconds: 'sec.',
    lastAction: 'Last action',
    lastTick: 'Last check',
    lastError: 'Last error',
    never: 'Not run yet',
    noError: 'None',
    source: 'Source',
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

function dateTime(
  value: string | null,
  language: Language,
  fallback: string,
): string {
  if (!value) {
    return fallback;
  }

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
        timeStyle: 'medium',
      },
    )
    + ' UTC'
  );
}

export function ExchangeOrderReconciliation({
  account,
  language,
  refreshKey,
  token,
}: ExchangeOrderReconciliationProps) {
  const t = copy[language];

  const [
    status,
    setStatus,
  ] = useState<
    AccountOrderReconciliationStatus | null
  >(null);

  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const [
    reloadKey,
    setReloadKey,
  ] = useState(0);

  const accountReady = (
    account.environment === 'TESTNET'
  );

  useEffect(
    () => {
      let active = true;

      if (!accountReady) {
        setStatus(null);
        setError(null);
        setBusy(false);
        return undefined;
      }

      async function load(
        showBusy: boolean,
      ): Promise<void> {
        if (showBusy && active) {
          setBusy(true);
        }

        try {
          const result = (
            await fetchExchangeAccountOrderReconciliationStatus(
              token,
              account.id,
            )
          );

          if (active) {
            setStatus(result);
            setError(null);
          }
        } catch (caught) {
          if (active) {
            setError(
              errorText(
                caught,
                t.failed,
              ),
            );
          }
        } finally {
          if (showBusy && active) {
            setBusy(false);
          }
        }
      }

      void load(true);

      const interval = window.setInterval(
        () => {
          void load(false);
        },
        15_000,
      );

      return () => {
        active = false;
        window.clearInterval(interval);
      };
    },
    [
      account.environment,
      account.id,
      language,
      refreshKey,
      reloadKey,
      token,
    ],
  );

  const healthy = Boolean(
    status?.enabled
    && status.running
    && !status.stopping
    && !status.last_error,
  );

  const stateClass = healthy
    ? 'healthy'
    : status?.enabled
      ? 'degraded'
      : 'disabled';

  return (
    <section
      className="exchange-order-reconciliation"
    >
      <header
        className={
          'exchange-order-reconciliation-header'
        }
      >
        <div>
          <Activity size={19} />
          <div>
            <h3>{t.title}</h3>
            <p>{t.subtitle}</p>
          </div>
        </div>

        <button
          type="button"
          disabled={!accountReady || busy}
          onClick={() => {
            setReloadKey(
              (current) => current + 1,
            );
          }}
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
        <div
          className={
            'exchange-order-reconciliation-warning'
          }
        >
          <AlertTriangle size={16} />
          <span>{t.unavailable}</span>
        </div>
      )}

      {error && (
        <div
          className={
            'exchange-order-reconciliation-error'
          }
        >
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {busy && !status && (
        <div
          className={
            'exchange-order-reconciliation-loading'
          }
        >
          <LoaderCircle
            size={16}
            className="is-spinning"
          />
          <span>{t.loading}</span>
        </div>
      )}

      {status && (
        <>
          <div
            className={
              'exchange-order-reconciliation-state '
              + stateClass
            }
          >
            {healthy
              ? <CheckCircle2 size={18} />
              : status.enabled
                ? <AlertTriangle size={18} />
                : <PauseCircle size={18} />}

            <div>
              <strong>
                {healthy
                  ? t.healthy
                  : status.enabled
                    ? t.degraded
                    : t.disabled}
              </strong>
              <span>
                {healthy
                  ? t.healthyDescription
                  : status.enabled
                    ? t.degradedDescription
                    : t.disabledDescription}
              </span>
            </div>

            <small>{t.readOnly}</small>
          </div>

          <div
            className={
              'exchange-order-reconciliation-metrics'
            }
          >
            <article>
              <span>{t.running}</span>
              <strong>
                {status.running
                  ? t.yes
                  : t.no}
              </strong>
            </article>
            <article>
              <span>{t.iterations}</span>
              <strong>{status.iterations}</strong>
            </article>
            <article>
              <span>{t.failures}</span>
              <strong>{status.failed_ticks}</strong>
            </article>
            <article>
              <span>{t.interval}</span>
              <strong>
                {status.poll_interval_seconds}
                {' '}
                {t.seconds}
              </strong>
            </article>
          </div>

          <dl
            className={
              'exchange-order-reconciliation-details'
            }
          >
            <div>
              <dt>{t.lastAction}</dt>
              <dd>
                {status.last_action
                  ?? t.never}
              </dd>
            </div>
            <div>
              <dt>{t.lastTick}</dt>
              <dd>
                <Clock3 size={12} />
                {dateTime(
                  status.last_tick_finished_at,
                  language,
                  t.never,
                )}
              </dd>
            </div>
            <div>
              <dt>{t.batch}</dt>
              <dd>{status.batch_size}</dd>
            </div>
            <div>
              <dt>{t.source}</dt>
              <dd>{status.source}</dd>
            </div>
            <div>
              <dt>{t.lastError}</dt>
              <dd>
                {status.last_error
                  ?? t.noError}
              </dd>
            </div>
          </dl>
        </>
      )}
    </section>
  );
}
