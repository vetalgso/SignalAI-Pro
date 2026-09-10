import { useEffect, useState } from 'react';
import './SignalQualityReport.css';

type Counts = {
  total: number; open: number; terminal: number; unknown_status: number;
  entered: number; tp1: number; tp2: number; tp3: number;
  stopped: number; expired: number; cancelled: number;
  without_events: number; manual_transitions: number;
};
type Group = Counts & {
  source: string; exchange: string; market_type: string; symbol: string;
  side: string; timeframe: string; strategy: string;
};
type Report = {
  generated_from: string; as_of: string; source: string; summary: Counts;
  transition_origin: 'ALL' | 'AUTOMATIC' | 'MANUAL' | 'UNKNOWN';
  groups: Group[]; total_groups: number; limit: number; offset: number;
};
const columns: [keyof Counts, string, string][] = [
  ['total', 'Создано', 'Created'], ['open', 'Открыто', 'Open'],
  ['entered', 'Вход достигнут', 'Entry reached'],
  ['tp1', 'Достигли TP1', 'Reached TP1'], ['tp2', 'Достигли TP2', 'Reached TP2'],
  ['tp3', 'Достигли TP3', 'Reached TP3'], ['stopped', 'Стоп', 'Stopped'],
  ['expired', 'Истекли', 'Expired'], ['cancelled', 'Отменены', 'Cancelled'],
];

export function SignalQualityReport({ language }: { language: 'ru' | 'en' }) {
  const ru = language === 'ru';
  const [query, setQuery] = useState({ days: 30, source: 'AI_REVIEW', transition_origin: 'ALL', offset: 0 });
  const [reload, setReload] = useState(0);
  const [data, setData] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(false); setData(null);
    void (async () => {
      try {
        const params = new URLSearchParams({ days: String(query.days), source: query.source,
          transition_origin: query.transition_origin,
          offset: String(query.offset), limit: '25' });
        const response = await fetch(`/api/v3/signals/quality?${params}`, {
          signal: controller.signal, headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error('Request failed');
        const report: Report = await response.json();
        if (!report.summary || !Array.isArray(report.groups)) throw new Error('Invalid report');
        if (!controller.signal.aborted) setData(report);
      } catch {
        if (!controller.signal.aborted) setError(true);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [query, reload]);
  return <section className="signal-quality" aria-label={ru ? 'Статистика сигналов' : 'Signal statistics'}>
    <div className="signal-quality__toolbar">
      <h3>{ru ? 'Статистика качества сигналов' : 'Signal quality statistics'}</h3>
      <label>{ru ? 'Созданы за' : 'Created within'}{' '}
        <select value={query.days} onChange={event => setQuery(value => ({ ...value, days: Number(event.target.value), offset: 0 }))}>
          {[7, 30, 90, 365].map(days => <option key={days} value={days}>{days} {ru ? 'дн.' : 'days'}</option>)}
        </select>
      </label>
      <label>{ru ? 'Источник' : 'Source'}{' '}
        <select value={query.source} onChange={event => setQuery(value => ({ ...value, source: event.target.value, offset: 0 }))}>
          <option value="AI_REVIEW">AI Review</option><option value="SCANNER">Scanner</option>
          <option value="ALL">{ru ? 'Все источники' : 'All sources'}</option>
        </select>
      </label>
      <label>{ru ? 'Происхождение переходов' : 'Transition origin'}{' '}
        <select value={query.transition_origin} onChange={event => setQuery(value => ({ ...value, transition_origin: event.target.value, offset: 0 }))}>
          <option value="ALL">{ru ? 'Все сигналы' : 'All signals'}</option>
          <option value="AUTOMATIC">{ru ? 'Только автоматические' : 'Automatic only'}</option>
          <option value="MANUAL">{ru ? 'С ручными переходами' : 'With manual transitions'}</option>
          <option value="UNKNOWN">{ru ? 'Неизвестное происхождение' : 'Unknown origin'}</option>
        </select>
      </label>
      <button type="button" disabled={loading} onClick={() => setReload(value => value + 1)}>{ru ? 'Обновить отчёт' : 'Refresh report'}</button>
    </div>
    <p>{ru
      ? 'Считаются сигналы, созданные за выбранный период, и их накопленные результаты к моменту обновления. TP учитывается один раз на сигнал по сохранённым переходам, включая ручные. TP1 и стоп могут относиться к одному сигналу; эти столбцы нельзя складывать. Это не доходность исполненных сделок.'
      : 'Signals created within the selected period and their recorded outcomes at refresh time. Each TP is counted once per signal from saved transitions, including manual ones. TP1 and a stop can belong to the same signal; these columns are not additive. This is not executed trade profitability.'}</p>
    <p>{ru
      ? '«Только автоматические»: есть записанные автоматические переходы, нет ручных или переходов неизвестного происхождения. «С ручными переходами» включает смешанную историю. Отсутствие переходов или одно лишь создание сигнала означает неизвестное происхождение. Автоматические переходы не гарантируют полноту истории и не подтверждают прибыльность.'
      : '“Automatic only” requires recorded automatic transitions with no manual or unknown-origin transitions. “With manual transitions” includes mixed history. No transitions or signal creation alone means unknown origin. Automatic transitions do not guarantee a complete history or confirm profitability.'}</p>
    <div role="status" aria-live="polite">
      {loading && (ru ? 'Загрузка отчёта…' : 'Loading report…')}
      {error && (ru ? 'Не удалось загрузить отчёт. Повторите обновление.' : 'Unable to load the report. Try refreshing.')}
    </div>
    {data && <>
      <div className="signal-quality__cards">{columns.map(([key, russian, english]) => <div key={key}>
        <span>{ru ? russian : english}</span><strong>{data.summary[key]}</strong>
      </div>)}</div>
      <p>{ru ? 'Завершено' : 'Terminal'}: {data.summary.terminal} · {ru ? 'Без истории событий' : 'Without event history'}: {data.summary.without_events}
        {' · '}{ru ? 'С ручными переходами' : 'With manual transitions'}: {data.summary.manual_transitions}
        {' · '}{ru ? 'Неизвестный статус' : 'Unknown status'}: {data.summary.unknown_status}</p>
      <p>{ru ? 'Созданы с' : 'Created since'} {new Date(data.generated_from).toLocaleString(ru ? 'ru-RU' : 'en-US')}
        {' · '}{ru ? 'Отчёт на' : 'As of'} {new Date(data.as_of).toLocaleString(ru ? 'ru-RU' : 'en-US')}</p>
      {data.summary.total === 0 ? <p>{ru ? 'По выбранным фильтрам сигналов нет.' : 'No signals match the selected filters.'}</p> :
        <div className="signal-quality__scroll" tabIndex={0} role="region" aria-label={ru ? 'По монете и стратегии' : 'By symbol and strategy'}>
          <table><thead><tr><th scope="col">{ru ? 'Монета / рынок' : 'Symbol / market'}</th>
            <th scope="col">{ru ? 'Стратегия / источник' : 'Strategy / source'}</th>
            {columns.map(([key, russian, english]) => <th scope="col" key={key}>{ru ? russian : english}</th>)}
          </tr></thead><tbody>{data.groups.map(group => <tr key={JSON.stringify([group.source, group.exchange, group.market_type, group.symbol, group.side, group.timeframe, group.strategy])}>
            <td>{group.symbol}<small>{group.exchange} · {group.market_type} · {group.side} · {group.timeframe}</small></td>
            <td>{group.strategy}<small>{group.source}</small></td>
            {columns.map(([key]) => <td key={key}>{group[key]}</td>)}
          </tr>)}</tbody></table>
        </div>}
    </>}
    <div className="signal-quality__toolbar">
      <button type="button" disabled={loading || query.offset === 0} onClick={() => setQuery(value => ({ ...value, offset: Math.max(0, value.offset - 25) }))}>{ru ? 'Назад' : 'Previous'}</button>
      <span>{ru ? 'Страница' : 'Page'} {Math.floor(query.offset / 25) + 1}{data ? ` · ${ru ? 'Групп' : 'Groups'}: ${data.total_groups}` : ''}</span>
      <button type="button" disabled={loading || !data || query.offset + 25 >= data.total_groups} onClick={() => setQuery(value => ({ ...value, offset: value.offset + 25 }))}>{ru ? 'Далее' : 'Next'}</button>
    </div>
  </section>;
}
