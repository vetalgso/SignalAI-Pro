import { useEffect, useState } from 'react';
import './AIReviewJournal.css';

type Language = 'ru' | 'en';
type Row = {
  id: number; candidate_id: number; run_id: number; symbol: string;
  status: string; ai_confidence: number | null; created_at: string;
  promotion_action: string; promotion_reason: string | null;
  signal_id: number | null;
};
type Page = { items: Row[]; total: number; limit: number; offset: number };

const labels: Record<string, [string, string]> = {
  PENDING: ['Ожидает AI', 'Pending AI'],
  PROCESSING: ['На проверке AI', 'AI processing'],
  APPROVED: ['Одобрено AI', 'AI approved'],
  REJECTED: ['Отклонено AI', 'AI rejected'],
  FAILED: ['Ошибка', 'Failed'],
  UNKNOWN: ['Неизвестно', 'Unknown'],
  CREATED: ['Сигнал создан', 'Signal created'],
  DUPLICATE: ['Найден существующий сигнал', 'Existing signal found'],
  LINKED: ['Сигнал связан; результат не записан', 'Signal linked; outcome not recorded'],
  BLOCKED: ['Создание заблокировано', 'Creation blocked'],
  NOT_RECORDED: ['Нет записи', 'Not recorded'],
  AI_REVIEW_NOT_APPROVED: ['Нет одобрения AI', 'AI approval missing'],
  PROMOTION_DIRECTION_CONFLICT: ['Направления не совпадают', 'Direction conflict'],
  PROMOTION_HIGH_RISK: ['Высокий риск', 'High risk'],
  PROMOTION_TIMEFRAMES_UNAVAILABLE: ['Недостаточно данных таймфреймов', 'Timeframe data missing'],
  PROMOTION_TIMEFRAME_CONFLICT: ['Таймфреймы не согласованы', 'Timeframe conflict'],
  PROMOTION_BLOCKING_RISK: ['Обнаружен блокирующий риск', 'Blocking risk detected'],
  PROMOTION_INTERNAL_ERROR: ['Внутренняя ошибка создания сигнала', 'Internal signal creation error'],
  PROMOTION_REQUEST_REJECTED: ['Параметры сигнала не прошли проверку', 'Signal parameters rejected'],
  PROMOTION_UNKNOWN_REASON: ['Причина не определена', 'Reason unavailable'],
};

export function AIReviewJournal({ language }: { language: Language }) {
  const ru = language === 'ru';
  const [page, setPage] = useState<Page | null>(null);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const label = (code: string) => labels[code]?.[ru ? 0 : 1] ?? (ru ? 'Неизвестно' : 'Unknown');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setFailed(false);
    setPage(null);
    void (async () => {
      try {
        const response = await fetch(`/api/v3/signals/ai-reviews?limit=25&offset=${offset}`, {
          signal: controller.signal,
          headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error('Request failed');
        const data: Page = await response.json();
        if (!Array.isArray(data.items) || !Number.isInteger(data.total)) throw new Error('Invalid page');
        if (!controller.signal.aborted) setPage(data);
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [offset, reload]);

  return <section className="ai-review-journal" aria-label="AI Review">
    <div className="ai-review-journal__heading">
      <h3>{ru ? 'Журнал AI Review' : 'AI Review journal'}</h3>
      <button type="button" className="product-button product-button--secondary" disabled={loading}
        onClick={() => setReload(value => value + 1)}>{ru ? 'Обновить журнал' : 'Refresh journal'}</button>
    </div>
    <p>{ru
      ? 'Одобрение AI и создание сигнала — отдельные этапы. «Нет записи» означает отсутствие сохранённого результата создания.'
      : 'AI approval and signal creation are separate steps. “Not recorded” means no creation outcome was saved.'}</p>
    <div role="status" aria-live="polite">
      {loading && (ru ? 'Загрузка…' : 'Loading…')}
      {failed && (ru ? 'Не удалось загрузить журнал. Повторите обновление.' : 'Unable to load the journal. Try refreshing.')}
      {!loading && !failed && page?.items.length === 0 && (ru ? 'Записей на этой странице нет.' : 'No reviews on this page.')}
    </div>
    {page && page.items.length > 0 && <div className="ai-review-journal__scroll" tabIndex={0} role="region" aria-label={ru ? 'Результаты AI Review' : 'AI Review results'}>
      <table>
        <thead><tr>{(ru
          ? ['Дата', 'Монета', 'Решение AI', 'Уверенность AI', 'Создание сигнала', 'Причина', 'Сигнал']
          : ['Date', 'Symbol', 'AI decision', 'AI confidence', 'Signal creation', 'Reason', 'Signal']
        ).map(title => <th key={title} scope="col">{title}</th>)}</tr></thead>
        <tbody>{page.items.map(row => <tr key={row.id}>
          <td><time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString(ru ? 'ru-RU' : 'en-US')}</time></td>
          <td>{row.symbol}</td><td>{label(row.status)}</td>
          <td>{row.ai_confidence === null ? '—' : `${row.ai_confidence.toFixed(1)}%`}</td>
          <td>{label(row.promotion_action)}</td>
          <td>{row.promotion_reason ? label(row.promotion_reason) : '—'}</td>
          <td>{row.signal_id === null ? '—' : `#${row.signal_id}`}</td>
        </tr>)}</tbody>
      </table>
    </div>}
    <div className="ai-review-journal__pagination">
      <button type="button" disabled={loading || offset === 0} onClick={() => setOffset(value => Math.max(0, value - 25))}>{ru ? 'Назад' : 'Previous'}</button>
      <span>{ru ? 'Страница' : 'Page'} {Math.floor(offset / 25) + 1}{page ? ` · ${ru ? 'Всего' : 'Total'}: ${page.total}` : ''}</span>
      <button type="button" disabled={loading || !page || offset + 25 >= page.total} onClick={() => setOffset(value => value + 25)}>{ru ? 'Далее' : 'Next'}</button>
    </div>
  </section>;
}
