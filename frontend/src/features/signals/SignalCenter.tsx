import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Crosshair,
  LoaderCircle,
  RefreshCw,
  Search,
  ShieldAlert,
  Target,
  X,
} from 'lucide-react';
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  fetchSignals,
  scanSignals,
} from './api';
import type {
  SignalFilters,
  SignalScanResult,
  TradingSignal,
} from './types';

type Language = 'ru' | 'en';

interface SignalCenterProps {
  language: Language;
}

const copy = {
  ru: {
    title: 'Торговые сигналы',
    subtitle:
      'Подтверждённые точки входа, рассчитанные SignalAI Pro',
    refresh: 'Обновить',
    scan: 'Сканировать рынок',
    scanning: 'Анализ рынка…',
    search: 'Поиск монеты',
    allSides: 'Все направления',
    allStatuses: 'Все статусы',
    allRisks: 'Любой риск',
    minConfidence: 'Мин. уверенность',
    active: 'Активные',
    long: 'LONG',
    short: 'SHORT',
    averageConfidence: 'Средняя уверенность',
    noSignals: 'Подтверждённых сигналов пока нет',
    noSignalsText:
      'Запустите сканирование. SignalAI покажет сигнал только при достаточном подтверждении входа.',
    entry: 'Диапазон входа',
    stopLoss: 'Stop Loss',
    targets: 'Цели',
    confidence: 'Уверенность',
    risk: 'Риск',
    riskReward: 'Risk / Reward',
    generated: 'Сформирован',
    expires: 'Истекает',
    reasons: 'Почему создан сигнал',
    source: 'Источник',
    strategy: 'Стратегия',
    market: 'Рынок',
    currentPrice: 'Текущая цена',
    close: 'Закрыть',
    details: 'Подробнее',
    loading: 'Загрузка сигналов…',
    found: 'Найдено',
    scanCreated: 'Создано новых сигналов',
    scanNone:
      'Новых подтверждённых входов сейчас нет',
    duplicates: 'Уже существующих',
    skipped: 'Отклонено',
    error: 'Не удалось загрузить сигналы',
  },
  en: {
    title: 'Trading signals',
    subtitle:
      'Confirmed entry opportunities calculated by SignalAI Pro',
    refresh: 'Refresh',
    scan: 'Scan market',
    scanning: 'Scanning market…',
    search: 'Search symbol',
    allSides: 'All directions',
    allStatuses: 'All statuses',
    allRisks: 'Any risk',
    minConfidence: 'Min. confidence',
    active: 'Active',
    long: 'LONG',
    short: 'SHORT',
    averageConfidence: 'Average confidence',
    noSignals: 'No confirmed signals yet',
    noSignalsText:
      'Run a market scan. SignalAI only shows opportunities with sufficient confirmation.',
    entry: 'Entry range',
    stopLoss: 'Stop Loss',
    targets: 'Targets',
    confidence: 'Confidence',
    risk: 'Risk',
    riskReward: 'Risk / Reward',
    generated: 'Generated',
    expires: 'Expires',
    reasons: 'Why this signal exists',
    source: 'Source',
    strategy: 'Strategy',
    market: 'Market',
    currentPrice: 'Current price',
    close: 'Close',
    details: 'Details',
    loading: 'Loading signals…',
    found: 'Found',
    scanCreated: 'New signals created',
    scanNone:
      'No new confirmed entries right now',
    duplicates: 'Already existing',
    skipped: 'Rejected',
    error: 'Failed to load signals',
  },
} as const;

const initialFilters: SignalFilters = {
  search: '',
  side: '',
  status: 'ACTIVE',
  riskLevel: '',
  minConfidence: 0,
};

function numeric(value: string | null): number {
  const parsed = Number(value);

  return Number.isFinite(parsed)
    ? parsed
    : 0;
}

function formatPrice(
  value: string | null,
): string {
  if (value === null) {
    return '—';
  }

  const number = Number(value);

  if (!Number.isFinite(number)) {
    return '—';
  }

  const maximumFractionDigits =
    Math.abs(number) < 1 ? 8 : 4;

  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits,
  }).format(number);
}

function formatDate(
  value: string | null,
  language: Language,
): string {
  if (!value) {
    return '—';
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return '—';
  }

  return date.toLocaleString(
    language === 'ru'
      ? 'ru-RU'
      : 'en-US',
    {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    },
  );
}

function sideIcon(
  side: TradingSignal['side'],
) {
  return side === 'LONG'
    ? ArrowUpRight
    : ArrowDownRight;
}

function scanMessage(
  result: SignalScanResult,
  language: Language,
): string {
  const t = copy[language];

  if (result.created_count > 0) {
    return [
      `${t.scanCreated}: ${result.created_count}.`,
      `${t.duplicates}: ${result.duplicate_count}.`,
      `${t.skipped}: ${result.skipped_count}.`,
    ].join(' ');
  }

  return [
    `${t.scanNone}.`,
    `${t.duplicates}: ${result.duplicate_count}.`,
    `${t.skipped}: ${result.skipped_count}.`,
  ].join(' ');
}

export function SignalCenter({
  language,
}: SignalCenterProps) {
  const t = copy[language];

  const [
    signals,
    setSignals,
  ] = useState<TradingSignal[]>([]);

  const [
    total,
    setTotal,
  ] = useState(0);

  const [
    filters,
    setFilters,
  ] = useState<SignalFilters>(
    initialFilters,
  );

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    scanning,
    setScanning,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const [
    message,
    setMessage,
  ] = useState<string | null>(null);

  const [
    selectedSignal,
    setSelectedSignal,
  ] = useState<TradingSignal | null>(
    null,
  );

  const loadSignals = useCallback(
    async () => {
      setLoading(true);
      setError(null);

      try {
        const page = await fetchSignals(
          filters,
        );

        setSignals(page.items);
        setTotal(page.total);
      } catch (loadError) {
        setSignals([]);
        setTotal(0);

        setError(
          loadError instanceof Error
            ? loadError.message
            : t.error,
        );
      } finally {
        setLoading(false);
      }
    },
    [
      filters.side,
      filters.status,
      filters.riskLevel,
      filters.minConfidence,
      t.error,
    ],
  );

  useEffect(() => {
    void loadSignals();
  }, [loadSignals]);

  const visibleSignals = useMemo(
    () => {
      const query = filters.search
        .trim()
        .toUpperCase();

      if (!query) {
        return signals;
      }

      return signals.filter(
        (signal) =>
          signal.symbol.includes(query)
          || signal.strategy
            .toUpperCase()
            .includes(query),
      );
    },
    [
      signals,
      filters.search,
    ],
  );

  const summary = useMemo(
    () => {
      const active = signals.filter(
        (signal) =>
          signal.status === 'ACTIVE'
          || signal.status
            === 'ENTRY_REACHED',
      );

      const longs = active.filter(
        (signal) =>
          signal.side === 'LONG',
      ).length;

      const shorts = active.filter(
        (signal) =>
          signal.side === 'SHORT',
      ).length;

      const average = active.length
        ? active.reduce(
            (sum, signal) =>
              sum
              + numeric(
                signal.confidence,
              ),
            0,
          ) / active.length
        : 0;

      return {
        active: active.length,
        longs,
        shorts,
        average,
      };
    },
    [signals],
  );

  async function runScan() {
    setScanning(true);
    setError(null);
    setMessage(null);

    try {
      const result = await scanSignals();

      setMessage(
        scanMessage(
          result,
          language,
        ),
      );

      await loadSignals();
    } catch (scanError) {
      setError(
        scanError instanceof Error
          ? scanError.message
          : t.error,
      );
    } finally {
      setScanning(false);
    }
  }

  return (
    <section className="product-signals">
      <div className="product-signals__header">
        <div>
          <span className="product-signals__eyebrow">
            SignalAI Product
          </span>

          <h2>{t.title}</h2>

          <p>{t.subtitle}</p>
        </div>

        <div className="product-signals__actions">
          <button
            type="button"
            className="product-button product-button--secondary"
            onClick={() =>
              void loadSignals()
            }
            disabled={loading}
          >
            <RefreshCw
              size={17}
              className={
                loading
                  ? 'is-spinning'
                  : ''
              }
            />
            {t.refresh}
          </button>

          <button
            type="button"
            className="product-button product-button--primary"
            onClick={() => void runScan()}
            disabled={scanning}
          >
            {scanning ? (
              <LoaderCircle
                size={17}
                className="is-spinning"
              />
            ) : (
              <Activity size={17} />
            )}

            {scanning
              ? t.scanning
              : t.scan}
          </button>
        </div>
      </div>

      {message && (
        <div className="product-message product-message--success">
          {message}
        </div>
      )}

      {error && (
        <div className="product-message product-message--error">
          <ShieldAlert size={18} />
          {error}
        </div>
      )}

      <div className="signal-summary">
        <article>
          <span>{t.active}</span>
          <strong>{summary.active}</strong>
          <Activity size={19} />
        </article>

        <article className="signal-summary__long">
          <span>{t.long}</span>
          <strong>{summary.longs}</strong>
          <ArrowUpRight size={19} />
        </article>

        <article className="signal-summary__short">
          <span>{t.short}</span>
          <strong>{summary.shorts}</strong>
          <ArrowDownRight size={19} />
        </article>

        <article>
          <span>
            {t.averageConfidence}
          </span>
          <strong>
            {summary.average.toFixed(0)}%
          </strong>
          <Crosshair size={19} />
        </article>
      </div>

      <div className="signal-filters">
        <label className="signal-search">
          <Search size={16} />

          <input
            value={filters.search}
            placeholder={t.search}
            onChange={(event) =>
              setFilters(
                (current) => ({
                  ...current,
                  search:
                    event.target.value,
                }),
              )
            }
          />
        </label>

        <select
          value={filters.side}
          onChange={(event) =>
            setFilters(
              (current) => ({
                ...current,
                side:
                  event.target.value,
              }),
            )
          }
        >
          <option value="">
            {t.allSides}
          </option>
          <option value="LONG">
            LONG
          </option>
          <option value="SHORT">
            SHORT
          </option>
        </select>

        <select
          value={filters.status}
          onChange={(event) =>
            setFilters(
              (current) => ({
                ...current,
                status:
                  event.target.value,
              }),
            )
          }
        >
          <option value="">
            {t.allStatuses}
          </option>
          <option value="ACTIVE">
            ACTIVE
          </option>
          <option value="ENTRY_REACHED">
            ENTRY REACHED
          </option>
          <option value="TP1_REACHED">
            TP1 REACHED
          </option>
          <option value="TP2_REACHED">
            TP2 REACHED
          </option>
          <option value="TP3_REACHED">
            TP3 REACHED
          </option>
          <option value="STOPPED">
            STOPPED
          </option>
          <option value="EXPIRED">
            EXPIRED
          </option>
          <option value="CANCELLED">
            CANCELLED
          </option>
        </select>

        <select
          value={filters.riskLevel}
          onChange={(event) =>
            setFilters(
              (current) => ({
                ...current,
                riskLevel:
                  event.target.value,
              }),
            )
          }
        >
          <option value="">
            {t.allRisks}
          </option>
          <option value="LOW">
            LOW
          </option>
          <option value="MEDIUM">
            MEDIUM
          </option>
          <option value="HIGH">
            HIGH
          </option>
        </select>

        <label className="confidence-filter">
          <span>
            {t.minConfidence}
          </span>

          <strong>
            {filters.minConfidence}%
          </strong>

          <input
            type="range"
            min="0"
            max="90"
            step="10"
            value={
              filters.minConfidence
            }
            onChange={(event) =>
              setFilters(
                (current) => ({
                  ...current,
                  minConfidence:
                    Number(
                      event.target.value,
                    ),
                }),
              )
            }
          />
        </label>
      </div>

      <div className="signals-result-line">
        <span>
          {t.found}: {visibleSignals.length}
        </span>

        <small>
          API total: {total}
        </small>
      </div>

      {loading ? (
        <div className="signal-loading">
          <LoaderCircle
            size={26}
            className="is-spinning"
          />
          {t.loading}
        </div>
      ) : visibleSignals.length === 0 ? (
        <div className="signals-empty">
          <div>
            <Target size={30} />
          </div>

          <h3>{t.noSignals}</h3>

          <p>{t.noSignalsText}</p>

          <button
            type="button"
            className="product-button product-button--primary"
            onClick={() => void runScan()}
            disabled={scanning}
          >
            {scanning ? (
              <LoaderCircle
                size={17}
                className="is-spinning"
              />
            ) : (
              <Activity size={17} />
            )}
            {scanning
              ? t.scanning
              : t.scan}
          </button>
        </div>
      ) : (
        <div className="signal-card-grid">
          {visibleSignals.map(
            (signal) => {
              const DirectionIcon =
                sideIcon(signal.side);

              return (
                <article
                  key={signal.id}
                  className={[
                    'product-signal-card',
                    signal.side
                      === 'LONG'
                      ? 'product-signal-card--long'
                      : 'product-signal-card--short',
                  ].join(' ')}
                >
                  <div className="product-signal-card__top">
                    <div>
                      <span>
                        {signal.exchange}
                        {' · '}
                        {signal.timeframe}
                      </span>

                      <h3>
                        {signal.symbol}
                      </h3>
                    </div>

                    <div
                      className={[
                        'signal-side',
                        signal.side
                          === 'LONG'
                          ? 'signal-side--long'
                          : 'signal-side--short',
                      ].join(' ')}
                    >
                      <DirectionIcon
                        size={17}
                      />
                      {signal.side}
                    </div>
                  </div>

                  <div className="signal-status-row">
                    <span
                      className="signal-status"
                    >
                      {signal.status}
                    </span>

                    <span
                      className={[
                        'signal-risk',
                        `signal-risk--${signal.risk_level.toLowerCase()}`,
                      ].join(' ')}
                    >
                      {signal.risk_level}
                    </span>
                  </div>

                  <div className="signal-confidence">
                    <div>
                      <span>
                        {t.confidence}
                      </span>

                      <strong>
                        {numeric(
                          signal.confidence,
                        ).toFixed(0)}
                        %
                      </strong>
                    </div>

                    <div className="signal-confidence__track">
                      <span
                        style={{
                          width: `${Math.min(
                            numeric(
                              signal.confidence,
                            ),
                            100,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>

                  <div className="signal-level-grid">
                    <div className="signal-level signal-level--entry">
                      <span>{t.entry}</span>
                      <strong>
                        {formatPrice(
                          signal.entry_min,
                        )}
                        {' – '}
                        {formatPrice(
                          signal.entry_max,
                        )}
                      </strong>
                    </div>

                    <div className="signal-level signal-level--stop">
                      <span>
                        {t.stopLoss}
                      </span>
                      <strong>
                        {formatPrice(
                          signal.stop_loss,
                        )}
                      </strong>
                    </div>

                    <div className="signal-level">
                      <span>TP1</span>
                      <strong>
                        {formatPrice(
                          signal
                            .take_profit_1,
                        )}
                      </strong>
                    </div>

                    <div className="signal-level">
                      <span>TP2</span>
                      <strong>
                        {formatPrice(
                          signal
                            .take_profit_2,
                        )}
                      </strong>
                    </div>

                    <div className="signal-level">
                      <span>TP3</span>
                      <strong>
                        {formatPrice(
                          signal
                            .take_profit_3,
                        )}
                      </strong>
                    </div>

                    <div className="signal-level">
                      <span>
                        {t.riskReward}
                      </span>
                      <strong>
                        1:
                        {numeric(
                          signal.risk_reward,
                        ).toFixed(2)}
                      </strong>
                    </div>
                  </div>

                  <div className="signal-card-footer">
                    <span>
                      {formatDate(
                        signal.generated_at,
                        language,
                      )}
                    </span>

                    <button
                      type="button"
                      onClick={() =>
                        setSelectedSignal(
                          signal,
                        )
                      }
                    >
                      {t.details}
                    </button>
                  </div>
                </article>
              );
            },
          )}
        </div>
      )}

      {selectedSignal && (
        <div
          className="signal-modal-backdrop"
          role="presentation"
          onMouseDown={() =>
            setSelectedSignal(null)
          }
        >
          <section
            className="signal-modal"
            role="dialog"
            aria-modal="true"
            aria-label={
              selectedSignal.symbol
            }
            onMouseDown={(event) =>
              event.stopPropagation()
            }
          >
            <div className="signal-modal__header">
              <div>
                <span>
                  {selectedSignal.exchange}
                  {' · '}
                  {selectedSignal.market_type}
                  {' · '}
                  {selectedSignal.timeframe}
                </span>

                <h2>
                  {selectedSignal.symbol}
                  {' '}
                  <b
                    className={
                      selectedSignal.side
                        === 'LONG'
                        ? 'text-long'
                        : 'text-short'
                    }
                  >
                    {selectedSignal.side}
                  </b>
                </h2>
              </div>

              <button
                type="button"
                aria-label={t.close}
                onClick={() =>
                  setSelectedSignal(null)
                }
              >
                <X size={21} />
              </button>
            </div>

            <div className="signal-modal__stats">
              <article>
                <span>
                  {t.confidence}
                </span>
                <strong>
                  {numeric(
                    selectedSignal
                      .confidence,
                  ).toFixed(0)}
                  %
                </strong>
              </article>

              <article>
                <span>{t.risk}</span>
                <strong>
                  {
                    selectedSignal
                      .risk_level
                  }
                </strong>
              </article>

              <article>
                <span>
                  {t.riskReward}
                </span>
                <strong>
                  1:
                  {numeric(
                    selectedSignal
                      .risk_reward,
                  ).toFixed(2)}
                </strong>
              </article>

              <article>
                <span>
                  {t.currentPrice}
                </span>
                <strong>
                  {formatPrice(
                    selectedSignal
                      .current_price,
                  )}
                </strong>
              </article>
            </div>

            <div className="signal-modal__levels">
              <article>
                <span>{t.entry}</span>
                <strong>
                  {formatPrice(
                    selectedSignal
                      .entry_min,
                  )}
                  {' – '}
                  {formatPrice(
                    selectedSignal
                      .entry_max,
                  )}
                </strong>
              </article>

              <article className="modal-stop">
                <span>{t.stopLoss}</span>
                <strong>
                  {formatPrice(
                    selectedSignal
                      .stop_loss,
                  )}
                </strong>
              </article>

              <article>
                <span>TP1</span>
                <strong>
                  {formatPrice(
                    selectedSignal
                      .take_profit_1,
                  )}
                </strong>
              </article>

              <article>
                <span>TP2</span>
                <strong>
                  {formatPrice(
                    selectedSignal
                      .take_profit_2,
                  )}
                </strong>
              </article>

              <article>
                <span>TP3</span>
                <strong>
                  {formatPrice(
                    selectedSignal
                      .take_profit_3,
                  )}
                </strong>
              </article>
            </div>

            <div className="signal-modal__section">
              <h3>{t.reasons}</h3>

              {selectedSignal.reasons.length ? (
                <ul>
                  {selectedSignal.reasons.map(
                    (reason, index) => (
                      <li
                        key={`${reason}-${index}`}
                      >
                        {reason}
                      </li>
                    ),
                  )}
                </ul>
              ) : (
                <p>—</p>
              )}
            </div>

            <div className="signal-modal__details">
              <div>
                <span>{t.strategy}</span>
                <strong>
                  {selectedSignal.strategy}
                </strong>
              </div>

              <div>
                <span>{t.source}</span>
                <strong>
                  {selectedSignal.source}
                </strong>
              </div>

              <div>
                <span>{t.generated}</span>
                <strong>
                  {formatDate(
                    selectedSignal
                      .generated_at,
                    language,
                  )}
                </strong>
              </div>

              <div>
                <span>{t.expires}</span>
                <strong>
                  {formatDate(
                    selectedSignal
                      .expires_at,
                    language,
                  )}
                </strong>
              </div>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
