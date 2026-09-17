import { useEffect, useState } from 'react';
import './SignalLifecycleStatus.css';

type Language = 'ru' | 'en';
type StateCode = 'DISABLED' | 'WAITING' | 'STALE' | 'ERRORS' | 'UNKNOWN' | 'OK';
type LifecycleState = {
  as_of: string; enabled: boolean; poll_interval_seconds: number; stale_after_seconds: number;
  state: StateCode; completed_at: string | null; age_seconds: number | null;
  duration_seconds: number | null; error_count: number | null; checked_signals: number | null;
  cycle_status: 'COMPLETED' | 'PARTIAL' | 'FAILED' | 'CANCELLED' | null;
};
const names: Record<StateCode | 'UNAVAILABLE' | 'LOADING' | 'OLD_DATA', [string, string]> = {
  DISABLED: ['Сопровождение выключено', 'Tracking disabled'],
  WAITING: ['Завершённых проверок ещё нет', 'No completed checks yet'],
  STALE: ['Проверка задерживается', 'Check overdue'],
  ERRORS: ['Последняя проверка с ошибками', 'Last check had errors'],
  UNKNOWN: ['Результат проверки неизвестен', 'Check outcome unknown'],
  OK: ['Последняя проверка успешна', 'Last check succeeded'],
  UNAVAILABLE: ['Состояние недоступно', 'Status unavailable'],
  LOADING: ['Загрузка состояния…', 'Loading status…'],
  OLD_DATA: ['Состояние давно не обновлялось', 'Status data is out of date'],
};

function decode(value: unknown): LifecycleState {
  if (!value || typeof value !== 'object') throw new Error('Invalid state');
  const data = value as LifecycleState;
  const finite = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n) && n >= 0;
  if (typeof data.enabled !== 'boolean' || !['DISABLED', 'WAITING', 'STALE', 'ERRORS', 'UNKNOWN', 'OK'].includes(data.state)
    || typeof data.as_of !== 'string' || !Number.isFinite(Date.parse(data.as_of))
    || !finite(data.poll_interval_seconds) || !finite(data.stale_after_seconds)
    || ![data.age_seconds, data.duration_seconds, data.error_count, data.checked_signals].every(n => n === null || finite(n))
    || !(data.completed_at === null || (typeof data.completed_at === 'string' && Number.isFinite(Date.parse(data.completed_at))))
    || ![null, 'COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED'].includes(data.cycle_status)) {
    throw new Error('Invalid state');
  }
  return data;
}

export function SignalLifecycleStatus({ language }: { language: Language }) {
  const ru = language === 'ru';
  const [snapshot, setSnapshot] = useState<{ data: LifecycleState; receivedAt: number } | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [clock, setClock] = useState(() => performance.now());

  useEffect(() => {
    const timer = window.setInterval(() => setClock(performance.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    const load = async () => {
      controller = new AbortController();
      const request = controller;
      const timeout = setTimeout(() => request.abort(), 8000);
      setLoading(true);
      try {
        const response = await fetch('/api/v3/signals/runtime/lifecycle', {
          signal: request.signal, cache: 'no-store', headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error('Request failed');
        const data = decode(await response.json());
        if (!stopped) {
          setSnapshot({ data, receivedAt: performance.now() });
          setFailed(false);
        }
      } catch {
        if (!stopped) {
          setSnapshot(null);
          setFailed(true);
        }
      } finally {
        clearTimeout(timeout);
        if (!stopped) {
          setLoading(false);
          timer = setTimeout(() => void load(), 30000);
        }
      }
    };
    void load();
    return () => {
      stopped = true;
      controller?.abort();
      clearTimeout(timer);
    };
  }, [reload]);

  const data = snapshot?.data;
  const elapsed = snapshot ? Math.max(0, (clock - snapshot.receivedAt) / 1000) : 0;
  const age = data?.age_seconds == null ? null : data.age_seconds + elapsed;
  const code = failed ? 'UNAVAILABLE' : !data ? 'LOADING' : elapsed > 90 ? 'OLD_DATA'
    : !data.enabled ? 'DISABLED' : age !== null && age > data.stale_after_seconds ? 'STALE' : data.state;
  const seconds = (n: number | null | undefined) => n == null ? '—' : n.toLocaleString(ru ? 'ru-RU' : 'en-US', { maximumFractionDigits: 1 }) + (ru ? ' с' : ' s');
  const time = (s: string) => new Date(s).toLocaleString(ru ? 'ru-RU' : 'en-US');

  return <section className="signal-lifecycle-status" aria-labelledby="signal-lifecycle-title">
    <div className="signal-lifecycle-status__heading">
      <div>
        <h3 id="signal-lifecycle-title">{ru ? 'Сопровождение сигналов' : 'Signal tracking'}</h3>
        <p>{ru ? 'Проверка входа, целей и стопа по рыночным данным.' : 'Entry, target and stop checks using market data.'}</p>
      </div>
      <button type="button" className="product-button product-button--secondary"
        disabled={loading} onClick={() => setReload(n => n + 1)}>
        {loading ? (ru ? 'Обновление…' : 'Refreshing…') : (ru ? 'Обновить состояние' : 'Refresh status')}
      </button>
    </div>
    <div role="status" aria-live="polite" className={'signal-lifecycle-status__badge signal-lifecycle-status__badge--' + code.toLowerCase()}>
      {names[code][ru ? 0 : 1]}
    </div>
    {data && <dl className="signal-lifecycle-status__details">
      <div><dt>{ru ? 'Последнее завершение' : 'Last completion'}</dt>
        <dd>{data.completed_at ? <time dateTime={data.completed_at}>{time(data.completed_at)}</time> : '—'}</dd></div>
      <div><dt>{ru ? 'Прошло с завершения' : 'Time since completion'}</dt><dd>{seconds(age)}</dd></div>
      <div><dt>{ru ? 'Длительность проверки' : 'Check duration'}</dt><dd>{seconds(data.duration_seconds)}</dd></div>
      <div><dt>{ru ? 'Проверено сигналов' : 'Signals checked'}</dt><dd>{data.checked_signals ?? '—'}</dd></div>
      <div><dt>{ru ? 'Ошибок' : 'Errors'}</dt><dd>{data.error_count ?? '—'}</dd></div>
    </dl>}
    <p className="signal-lifecycle-status__note">
      {failed ? (ru ? 'Не удалось получить состояние. Повторная попытка выполняется автоматически.' : 'Unable to fetch status. Retrying automatically.')
        : ru ? 'Состояние обновляется каждые 30 с. Показан последний завершённый цикл; это не результат исполнения ордеров.'
        : 'Status refreshes every 30 s. Shows the last finished cycle, not order execution results.'}
      {data && <> {ru ? 'Задержка отмечается после' : 'Overdue after'} {seconds(data.stale_after_seconds)}.
        {data.enabled ? '' : (ru ? ' Показана сохранённая история.' : ' Showing saved history.')}</>}
    </p>
  </section>;
}
