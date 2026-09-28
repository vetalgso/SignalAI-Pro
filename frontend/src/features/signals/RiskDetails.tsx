import type { RiskAssessment } from './aiAdmissionApi';

const reasons: Record<string, [string, string]> = {
  FORECAST_HIGH: ['Хотя бы один прогнозный горизонт имеет высокий риск.', 'At least one forecast horizon has high risk.'],
  MULTIPLE_ELEVATED: ['Не менее двух прогнозных горизонтов имеют повышенный риск.', 'At least two forecast horizons have elevated risk.'],
  PROFILE_WITH_ELEVATED: ['Один повышенный риск прогноза при профиле high.', 'One elevated forecast risk with the high profile.'],
  INVALID_VOLUME: ['Отсутствует или некорректно отношение объёма к среднему.', 'Volume ratio is missing or invalid.'],
  SIGNAL_WARNINGS: ['Технический сигнал содержит не менее двух предупреждений.', 'The technical signal contains at least two warnings.'],
  LOW_VOLUME: ['Отношение объёма к среднему ниже 0,25.', 'Volume ratio is below 0.25.'],
  PROFILE: ['Использован уровень риска профиля сканирования.', 'The scan profile risk level was used.'],
};
const levels: Record<string, [string, string]> = {
  low: ['Низкий', 'Low'], normal: ['Обычный', 'Normal'], medium: ['Средний', 'Medium'],
  elevated: ['Повышенный', 'Elevated'], high: ['Высокий', 'High'],
};
export function RiskDetails({ language, risk }: { language: 'ru' | 'en'; risk: RiskAssessment | null }) {
  const ru = language === 'ru';
  if (!risk) return <p>{ru ? 'Причина высокого риска не записана.' : 'High-risk details were not recorded.'}</p>;
  const volumeLabel = { AVAILABLE: ru ? 'Данные доступны' : 'Available', MISSING: ru ? 'Данные отсутствуют' : 'Missing', INVALID: ru ? 'Некорректное значение' : 'Invalid', NONFINITE: ru ? 'Неконечное значение' : 'Non-finite' };
  const label = (level: string) => levels[level]?.[ru ? 0 : 1] ?? level;
  return <details className="quality-penalty-details">
    <summary>{ru ? 'Причина риска' : 'Risk explanation'}</summary>
    <p>{reasons[risk.reason]?.[ru ? 0 : 1] ?? (ru ? 'Неизвестная причина.' : 'Unknown reason.')}</p>
    <p>{ru ? 'Первое сработавшее правило; остальные факторы могут присутствовать.'
      : 'The first matching rule; other factors may also be present.'}</p>
    <p>{ru ? 'Профиль' : 'Profile'}: {label(risk.profile_risk)}; {ru ? 'результат' : 'result'}: {label(risk.level)}.</p>
    <ul>{risk.horizons.map((h, i) => <li key={i}>
      {h.horizon_minutes === null ? (ru ? 'Горизонт неизвестен' : 'Unknown horizon')
        : `${h.horizon_minutes} ${ru ? 'мин' : 'min'}`}: {label(h.level)}
    </li>)}</ul>
    <p>{ru ? 'Предупреждений технического сигнала' : 'Technical signal warnings'}: {risk.warning_count}.</p>
    <p>{ru ? 'Отношение объёма к среднему' : 'Volume / average'}: {risk.volume_ratio ?? '—'} ({volumeLabel[risk.volume_state]}).</p>
    {!risk.signal_available && <p>{ru ? 'Технический сигнал отсутствовал.' : 'Technical signal was unavailable.'}</p>}
    <p>{ru ? 'Рассчитано' : 'Calculated'}: {new Date(risk.calculated_at).toLocaleString(ru ? 'ru-RU' : 'en-US')}.</p>
  </details>;
}
