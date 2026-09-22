import { useEffect, useState } from 'react';
import { fetchAdmission, type AdmissionPage } from './aiAdmissionApi';
import './AIReviewJournal.css';
import { QualityPenaltyDetails } from './QualityPenaltyDetails';

type Language = 'ru' | 'en';
const reasons: Record<string, [string, string]> = {
  AI_REVIEW_DISABLED: ['AI-проверка выключена', 'AI review disabled'],
  AI_NOT_CONFIGURED: ['AI не настроен', 'AI not configured'],
  UNSUPPORTED_REJECTION_REASON: ['Причина не подходит для AI', 'Unsupported rejection reason'],
  NO_ACTIONABLE_DIRECTION: ['Нет направления LONG/SHORT', 'No LONG/SHORT direction'],
  DIRECTION_CONFLICT: ['Направления не совпадают', 'Direction conflict'],
  INVALID_TRADE_GEOMETRY: ['Некорректные торговые уровни', 'Invalid trade geometry'],
  STOP_DISTANCE_TOO_TIGHT: ['Стоп слишком близко', 'Stop distance too tight'],
  TARGET_DISTANCE_TOO_TIGHT: ['Цель слишком близко', 'Target distance too tight'],
  LOW_RISK_REWARD: ['Недостаточное отношение цели к риску', 'Risk/reward below minimum'],
  INCOMPLETE_CANDIDATE: ['Недостаточно данных', 'Incomplete candidate'],
  LOW_CONFIDENCE: ['Оценка confidence ниже порога', 'Confidence below minimum'],
  LOW_RANKING_SCORE: ['Рейтинг ниже порога', 'Ranking below minimum'],
  LOW_CONSENSUS: ['Недостаточное согласие модулей', 'Module consensus below minimum'],
  LOW_TIMEFRAME_CONSENSUS: ['Недостаточное согласие таймфреймов', 'Timeframe consensus below minimum'],
  EXCESSIVE_QUALITY_PENALTY: ['Превышен штраф за качество', 'Quality penalty too high'],
  STALE_CANDIDATE: ['Кандидат устарел', 'Stale candidate'],
  LEVELS_UNAVAILABLE: ['Нет торговых уровней', 'Trading levels unavailable'],
  INVALID_LEVELS: ['Некорректные уровни', 'Invalid levels'],
  INVALID_LEVEL_DIRECTION: ['Уровни не соответствуют направлению', 'Levels conflict with direction'],
  HIGH_RISK: ['Высокий риск', 'High risk'],
  BATCH_LIMIT: ['Не вошёл в лимит AI-проверок', 'Outside AI review batch limit'],
  ELIGIBLE: ['Условия выполнены', 'Eligibility conditions met'],
};

export function AIAdmissionJournal({ language }: { language: Language }) {
  const ru = language === 'ru';
  const [query, setQuery] = useState({ runId: null as number | null, offset: 0, reload: 0 });
  const [page, setPage] = useState<AdmissionPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const label = (reason: string) => reasons[reason]?.[ru ? 0 : 1] ?? (ru ? 'Неизвестная причина' : 'Unknown reason');
  const date = (value: string) => new Date(value).toLocaleString(ru ? 'ru-RU' : 'en-US');
  const number = (value: number | null) => value === null ? '—' : value.toLocaleString(ru ? 'ru-RU' : 'en-US', { maximumFractionDigits: 2 });

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setFailed(false);
    setPage(null);
    void fetchAdmission(query.runId, query.offset, controller.signal).then(data => {
      if (!controller.signal.aborted) setPage(data);
    }).catch(() => {
      if (!controller.signal.aborted) setFailed(true);
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [query]);

  function move(offset: number) {
    if (page?.run) setQuery({ ...query, runId: page.run.id, offset });
  }

  return <section className="ai-review-journal" aria-label={ru ? 'Допуск к AI-проверке' : 'AI admission'}>
    <div className="ai-review-journal__heading">
      <h3>{ru ? 'Допуск к AI-проверке' : 'AI review admission'}</h3>
      <button type="button" className="product-button product-button--secondary" disabled={loading}
        onClick={() => setQuery({ runId: null, offset: 0, reload: query.reload + 1 })}>
        {ru ? 'Последний проход' : 'Latest scan'}
      </button>
    </div>
    <p>{ru
      ? 'Кандидаты с конфликтом технического направления и итоговой рекомендации. Показано первое невыполненное условие отбора. Confidence — оценка системы, а не вероятность прибыли и не ответ AI.'
      : 'Candidates with a conflict between technical direction and final recommendation. The first unmet selection condition is shown. Confidence is a system score, not a profit probability or an AI response.'}</p>
    <p>{ru
      ? '«Выбран» означает отбор для AI-проверки; её результат смотрите в журнале ниже. Порог сохранён на момент отбора. Отсутствие записи не означает отказ.'
      : '“Selected” means chosen for AI review; see the review journal below for its outcome. The threshold is saved at selection time. A missing record does not mean rejection.'}</p>
    <div role="status" aria-live="polite">
      {loading && (ru ? 'Загрузка…' : 'Loading…')}
      {failed && (ru ? 'Не удалось загрузить допуск к AI. Повторите обновление.' : 'Unable to load AI admission. Try refreshing.')}
      {page && !page.run && (ru ? 'Проходов сканера пока нет.' : 'No scanner runs yet.')}
      {page?.run && <>
        <p>{ru ? 'Проход' : 'Scan'} #{page.run.id} · {date(page.run.completed_at)} · {ru ? 'Проверено активов' : 'Assets scanned'}: {page.run.scanned_assets} · {ru ? 'Кандидатов с конфликтом' : 'Conflicting candidates'}: {page.total}</p>
        <ul className="ai-admission-summary">
          {Object.entries(page.reason_counts).map(([reason, count]) => <li key={reason}>{label(reason)}: <strong>{count}</strong></li>)}
          {page.not_recorded_count > 0 && <li>{ru ? 'Результат отбора не записан' : 'Selection not recorded'}: <strong>{page.not_recorded_count}</strong></li>}
        </ul>
        {page.total === 0 && <p>{ru ? 'В этом проходе нет кандидатов с конфликтом рекомендаций.' : 'No recommendation-conflict candidates in this scan.'}</p>}
      </>}
    </div>
    {page && page.items.length > 0 && <div className="ai-review-journal__scroll" tabIndex={0} role="region" aria-label={ru ? 'Условия допуска к AI' : 'AI admission conditions'}>
      <table>
        <thead><tr>{(ru
          ? ['Монета', 'Отбор', 'Причина', 'Confidence', 'Минимум confidence', 'Лимит AI', 'Штраф за качество', 'Проверено']
          : ['Symbol', 'Selection', 'Reason', 'Confidence', 'Minimum confidence', 'AI batch limit', 'Quality penalty', 'Evaluated']
        ).map(title => <th key={title} scope="col">{title}</th>)}</tr></thead>
        <tbody>{page.items.map(row => <tr key={row.candidate_id}>
          <td>{row.symbol}</td>
          <td>{!row.decision ? (ru ? 'Не записан' : 'Not recorded') : row.decision.action === 'SELECTED' ? (ru ? 'Выбран' : 'Selected') : (ru ? 'Пропущен' : 'Skipped')}</td>
          <td>{row.decision ? label(row.decision.reason) : '—'}</td>
          <td>{number(row.decision?.confidence ?? null)}</td>
          <td>{number(row.decision?.minimum_confidence ?? null)}</td>
          <td>{row.decision?.max_candidates ?? '—'}</td>
          <td><QualityPenaltyDetails language={language} quality={row.quality ?? null}
            maximum={row.decision?.maximum_quality_penalty ?? null} /></td>
          <td>{row.decision ? <time dateTime={row.decision.evaluated_at}>{date(row.decision.evaluated_at)}</time> : '—'}</td>
        </tr>)}</tbody>
      </table>
    </div>}
    {page && page.total > 0 && <div className="ai-review-journal__pagination">
      <button type="button" disabled={loading || query.offset === 0} onClick={() => move(Math.max(0, query.offset - 25))}>{ru ? 'Назад' : 'Previous'}</button>
      <span>{ru ? 'Страница' : 'Page'} {Math.floor(query.offset / 25) + 1} · {ru ? 'Всего' : 'Total'}: {page.total}</span>
      <button type="button" disabled={loading || query.offset + 25 >= page.total} onClick={() => move(query.offset + 25)}>{ru ? 'Далее' : 'Next'}</button>
    </div>}
  </section>;
}
