import {
  AlertTriangle,
  LoaderCircle,
  Send,
  ShieldCheck,
} from 'lucide-react';
import {
  useEffect,
  useState,
} from 'react';

import './ExchangeTestnetExecution.css';

import {
  ExchangeApiError,
  executeExchangeAccountOrder,
} from './api';
import type {
  AccountOrderJournal,
  AccountOrderRequest,
  ExchangeAccount,
  Language,
} from './types';

interface ExchangeTestnetExecutionProps {
  account: ExchangeAccount;
  busy: boolean;
  language: Language;
  onBusyChange: (
    busy: boolean,
  ) => void;
  onExecuted: (
    journal: AccountOrderJournal,
  ) => void;
  request: AccountOrderRequest;
  token: string;
}

const copy = {
  ru: {
    title: 'Отправка в Binance Testnet',
    description:
      'Это создаст настоящий ордер в тестовой среде Binance. Реальные средства не используются.',
    acknowledgment:
      'Я понимаю, что ордер будет отправлен во внешнюю тестовую биржу.',
    confirmation:
      'Введите TESTNET для подтверждения',
    placeholder: 'TESTNET',
    execute: 'Отправить TESTNET-ордер',
    executing: 'Отправляем ордер',
    unavailable:
      'Аккаунт не готов к TESTNET-торговле.',
    confirmationRequired:
      'Подтвердите действие и введите TESTNET.',
    failed:
      'Не удалось отправить TESTNET-ордер.',
    protection:
      'LIVE-торговля заблокирована интерфейсом и backend.',
  },
  en: {
    title: 'Submit to Binance Testnet',
    description:
      'This creates an actual order in the Binance test environment. No real funds are used.',
    acknowledgment:
      'I understand that the order will be submitted to an external test exchange.',
    confirmation:
      'Type TESTNET to confirm',
    placeholder: 'TESTNET',
    execute: 'Submit TESTNET order',
    executing: 'Submitting order',
    unavailable:
      'The account is not ready for TESTNET trading.',
    confirmationRequired:
      'Acknowledge the action and type TESTNET.',
    failed:
      'Unable to submit the TESTNET order.',
    protection:
      'LIVE trading is blocked by both the UI and backend.',
  },
} as const;

function operationKey(): string {
  if (
    typeof crypto !== 'undefined'
    && typeof crypto.randomUUID === 'function'
  ) {
    return (
      `testnet-ui-${crypto.randomUUID()}`
    );
  }

  return (
    `testnet-ui-${Date.now()}-`
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

export function ExchangeTestnetExecution({
  account,
  busy,
  language,
  onBusyChange,
  onExecuted,
  request,
  token,
}: ExchangeTestnetExecutionProps) {
  const t = copy[language];

  const [
    acknowledged,
    setAcknowledged,
  ] = useState(false);

  const [
    confirmation,
    setConfirmation,
  ] = useState('');

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const accountReady = (
    account.environment === 'TESTNET'
    && account.status === 'CONNECTED'
    && account.can_trade === true
  );

  const confirmed = (
    acknowledged
    && confirmation.trim().toUpperCase()
      === 'TESTNET'
  );

  useEffect(
    () => {
      setAcknowledged(false);
      setConfirmation('');
      setError(null);
    },
    [
      account.id,
      request,
    ],
  );

  async function executeTestnetOrder():
    Promise<void> {
    if (!accountReady) {
      setError(t.unavailable);
      return;
    }

    if (!confirmed) {
      setError(t.confirmationRequired);
      return;
    }

    onBusyChange(true);
    setError(null);

    try {
      const journal = (
        await executeExchangeAccountOrder(
          token,
          account.id,
          {
            ...request,
            idempotency_key:
              operationKey(),
            dry_run: false,
          },
        )
      );

      onExecuted(journal);
      setAcknowledged(false);
      setConfirmation('');
    } catch (caught) {
      setError(
        errorText(
          caught,
          t.failed,
        ),
      );
    } finally {
      onBusyChange(false);
    }
  }

  return (
    <section className="exchange-testnet-execution">
      <header>
        <div>
          <Send size={18} />
          <div>
            <h4>{t.title}</h4>
            <p>{t.description}</p>
          </div>
        </div>

        <span>
          <ShieldCheck size={13} />
          TESTNET
        </span>
      </header>

      <div className="exchange-testnet-protection">
        <ShieldCheck size={15} />
        <span>{t.protection}</span>
      </div>

      {!accountReady && (
        <div className="exchange-testnet-error">
          <AlertTriangle size={15} />
          <span>{t.unavailable}</span>
        </div>
      )}

      {error && (
        <div className="exchange-testnet-error">
          <AlertTriangle size={15} />
          <span>{error}</span>
        </div>
      )}

      <label className="exchange-testnet-checkbox">
        <input
          type="checkbox"
          checked={acknowledged}
          disabled={!accountReady || busy}
          onChange={(event) =>
            setAcknowledged(
              event.target.checked,
            )
          }
        />
        <span>{t.acknowledgment}</span>
      </label>

      <div className="exchange-testnet-confirmation">
        <label>
          <span>{t.confirmation}</span>
          <input
            value={confirmation}
            placeholder={t.placeholder}
            autoComplete="off"
            disabled={!accountReady || busy}
            onChange={(event) =>
              setConfirmation(
                event.target.value,
              )
            }
          />
        </label>

        <button
          type="button"
          disabled={
            !accountReady
            || !confirmed
            || busy
          }
          onClick={() =>
            void executeTestnetOrder()
          }
        >
          {busy
            ? (
                <LoaderCircle
                  size={15}
                  className="is-spinning"
                />
              )
            : <Send size={15} />}
          {busy
            ? t.executing
            : t.execute}
        </button>
      </div>
    </section>
  );
}
