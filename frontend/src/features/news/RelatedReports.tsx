type Report = {
  source: string; title: string; url: string; published_at: string;
  basis: { family: string; asset: string; amount: string; unit: string; direction: string; shared_terms: string[] };
};
type Coverage = { version: number; other_publishers_count: number; reports: Report[] };
const publishers: Record<string, string> = {
  CoinDesk: 'coindesk.com', Cointelegraph: 'cointelegraph.com', Decrypt: 'decrypt.co',
};
function safeReport(report: Report) {
  try {
    const url = new URL(report.url);
    return url.protocol === 'https:' && !url.username && !url.password && !url.port
      && url.hostname.replace(/^www\./, '') === publishers[report.source];
  } catch { return false; }
}
export function RelatedReports({ coverage, language }: { coverage?: Coverage | null; language: 'ru' | 'en' }) {
  const ru = language === 'ru';
  const reports = coverage?.version === 1 && Array.isArray(coverage.reports)
    ? coverage.reports.filter(safeReport) : [];
  const count = new Set(reports.map(report => report.source)).size;
  return <div className="news-related">
    <p>{ru ? 'Проверка фактов не выполнена (unverified).' : 'Facts have not been verified (unverified).'}</p>
    {reports.length ? <details>
      <summary>{ru ? `Похожие сообщения: других изданий — ${count}` : `Related reports: ${count} other publishers`}</summary>
      <p>{ru
        ? 'Совпали признаки в RSS-заголовках за последние 24 часа. Издания могут пересказывать один источник; это не подтверждение фактов.'
        : 'Matching clues in RSS headlines published within the last 24 hours. Publishers may repeat one source; this does not verify the claims.'}</p>
      <ul>{reports.map(report => <li key={report.url}>
        <a href={report.url} target="_blank" rel="noopener noreferrer">{report.source}: {report.title}</a>
        <span>{report.published_at}</span>
        <p>{ru ? 'Совпадение: ' : 'Match: '}{report.basis.family === 'ETF_FLOW'
          ? (ru ? 'поток средств ETF' : 'ETF flow') : (ru ? 'возврат активов после инцидента' : 'asset recovery after an incident')}
          {' · '}{report.basis.asset}{' · '}{report.basis.amount} {report.basis.unit}
          {report.basis.shared_terms.length > 0 && ` · ${report.basis.shared_terms.join(', ')}`}
        </p>
      </li>)}</ul>
    </details> : <p>{coverage?.version === 1
      ? (ru ? 'Похожие сообщения по текущим правилам не найдены. Это не означает, что новость ложная.'
        : 'No related reports found by the current rules. This does not mean the story is false.')
      : (ru ? 'Сопоставление сообщений ещё не записано.' : 'Related-report matching has not been recorded.')}</p>}
  </div>;
}
