import type { QualityBreakdown } from './aiAdmissionApi';

type Props = { language: 'ru' | 'en'; quality: QualityBreakdown | null; maximum: number | null };
const directions: Record<string, [string, string]> = {
  UP: ['Рост', 'Up'], DOWN: ['Падение', 'Down'], SIDEWAYS: ['Боковое движение', 'Sideways'],
  UNCERTAIN: ['Неопределённый', 'Uncertain'], UNKNOWN: ['Неизвестный', 'Unknown'],
};

export function QualityPenaltyDetails({ language, quality, maximum }: Props) {
  const ru = language === 'ru';
  const missing = ru ? 'Не записан' : 'Not recorded';
  const limit = `${ru ? 'Максимум для AI' : 'AI maximum'}: ${maximum ?? missing}`;
  if (!quality) return <div className="quality-penalty-details">
    <span>{ru ? 'Состав штрафа не записан' : 'Penalty breakdown not recorded'}</span>
    <p>{limit}</p>
  </div>;

  const { forecast, volume, news } = quality;
  const points = (n: number) => `${n} ${ru ? 'балл.' : 'pts'}`;
  const horizon = (minutes: number | null) => {
    if (minutes === null) return ru ? 'Горизонт неизвестен' : 'Unknown horizon';
    if (minutes % 1440 === 0) return `${minutes / 1440} ${ru ? 'дн.' : 'd'}`;
    if (minutes % 60 === 0) return `${minutes / 60} ${ru ? 'ч' : 'h'}`;
    return `${minutes} ${ru ? 'мин' : 'min'}`;
  };
  return <details className="quality-penalty-details">
    <summary>{points(quality.total)} · {limit}</summary>
    <p>{ru ? 'Сумма категорий' : 'Component sum'}: {quality.uncapped_total};{' '}
      {ru ? 'ограничение суммы' : 'total cap'}: {quality.cap};{' '}
      {ru ? 'итог' : 'final'}: {quality.total}.</p>
    <ul>
      <li><strong>{ru ? 'Прогнозы' : 'Forecasts'}: {points(forecast.points)}</strong><br />
        {forecast.state === 'MISSING' ? (ru ? 'Данные отсутствуют.' : 'Data missing.')
          : `${ru ? 'Неопределённых или боковых' : 'Uncertain or sideways'}: ${forecast.uncertain_count} / ${forecast.horizons.length}.`}
      </li>
      <li><strong>{ru ? 'Объём' : 'Volume'}: {points(volume.points)}</strong><br />
        {volume.state === 'MISSING' ? (ru ? 'Отношение объёма к среднему отсутствует.' : 'Volume ratio missing.')
          : volume.state === 'INVALID' ? (ru ? 'Некорректное отношение объёма к среднему.' : 'Invalid volume ratio.')
          : `${ru ? 'Отношение объёма к среднему' : 'Volume / average'}: ${volume.ratio?.toLocaleString(ru ? 'ru-RU' : 'en-US', { maximumFractionDigits: 4 })}.`}
      </li>
      <li><strong>{ru ? 'Новости' : 'News'}: {points(news.points)}</strong><br />
        {news.state === 'MISSING' ? (ru ? 'Данные отсутствуют или список пуст.' : 'Data missing or list empty.')
          : `${ru ? 'Без статуса verified' : 'Without verified status'}: ${news.unverified_count} / ${news.article_count}.`}
        {news.diagnostics && <>
          <br />{news.diagnostics.coverage === 'UNSUPPORTED'
            ? (ru ? 'Монета не поддерживается словарём новостей.' : 'Asset is not covered by the news dictionary.')
            : news.diagnostics.coverage === 'SUPPORTED'
              ? (ru ? 'Монета поддерживается словарём новостей.' : 'Asset is covered by the news dictionary.')
              : (ru ? 'Запрос без фильтра монеты.' : 'Query without an asset filter.')}
          <br />{news.diagnostics.sources_state === 'FAILED'
            ? (ru ? 'Ошибка загрузки всех RSS-источников.' : 'All RSS sources failed to load.')
            : news.diagnostics.sources_state === 'PARTIAL'
              ? (ru ? 'Часть RSS-источников недоступна.' : 'Some RSS sources failed to load.')
              : (ru ? 'RSS-источники ответили без ошибок.' : 'RSS sources responded without errors.')}
          <br />{ru ? 'Ошибок источников' : 'Failed sources'}: {news.diagnostics.failed_sources} / {news.diagnostics.total_sources}.
          <br />{ru ? 'Статей в общей подборке' : 'Articles in collected feeds'}: {news.diagnostics.collected_articles};{' '}
          {ru ? 'совпадений до ограничения выдачи' : 'matches before response limit'}: {news.diagnostics.matched_articles}.
          {news.diagnostics.coverage === 'SUPPORTED' && news.diagnostics.sources_state === 'COMPLETE'
            && news.diagnostics.matched_articles === 0 && <p>{ru
              ? 'Совпадений в загруженной подборке нет; это не означает отсутствие новостей вообще.'
              : 'No matches in the loaded feed sample; this does not mean there is no news anywhere.'}</p>}
          <br />{ru ? 'Проверено' : 'Observed'}: {new Date(news.diagnostics.observed_at).toLocaleString(ru ? 'ru-RU' : 'en-US')}.
        </>}
        {!news.diagnostics && <p>{ru ? 'Диагностика источников не записана.' : 'Source diagnostics were not recorded.'}</p>}
      </li>
    </ul>
    {forecast.horizons.length > 0 && <>
      <strong>{ru ? 'Исходные статусы прогнозов' : 'Original forecast statuses'}</strong>
      <ul>{forecast.horizons.map((item, index) => <li key={index}>
        {horizon(item.horizon_minutes)}: {directions[item.direction]?.[ru ? 0 : 1] ?? missing} ({item.direction})
      </li>)}</ul>
      <p>{ru ? 'Это статусы исходного прогноза. Метки LONG/SHORT в анализе таймфреймов рассчитываются отдельно.'
        : 'These are the original forecast statuses. LONG/SHORT timeframe labels are calculated separately.'}</p>
    </>}
    <p>{ru ? 'Рассчитано' : 'Calculated'}: <time dateTime={quality.calculated_at}>
      {new Date(quality.calculated_at).toLocaleString(ru ? 'ru-RU' : 'en-US')}
    </time></p>
  </details>;
}
