import {
  CandlestickSeries,
  ColorType,
  LineStyle,
  createChart,
} from 'lightweight-charts';
import type {
  CandlestickData,
  IChartApi,
  UTCTimestamp,
} from 'lightweight-charts';
import {
  BarChart3,
  LoaderCircle,
  ShieldAlert,
} from 'lucide-react';
import {
  useEffect,
  useRef,
  useState,
} from 'react';

import {
  fetchSignalCandles,
} from './api';
import type {
  MarketCandle,
  TradingSignal,
} from './types';

type Language = 'ru' | 'en';

interface SignalChartProps {
  signal: TradingSignal;
  language: Language;
}

const chartCopy = {
  ru: {
    title: 'График сигнала',
    subtitle:
      'Свечи Binance и торговые уровни SignalAI',
    loading: 'Загрузка графика…',
    error:
      'Не удалось загрузить свечи для графика',
    entry: 'Вход',
    current: 'Текущая цена',
  },
  en: {
    title: 'Signal chart',
    subtitle:
      'Binance candles and SignalAI trade levels',
    loading: 'Loading chart…',
    error: 'Failed to load chart candles',
    entry: 'Entry',
    current: 'Current price',
  },
} as const;

interface ChartLevel {
  title: string;
  price: number;
  color: string;
  lineStyle: LineStyle;
  lineWidth: 1 | 2 | 3 | 4;
}

function priceNumber(
  value: string | number | null,
): number | null {
  if (value === null) {
    return null;
  }

  const result = Number(value);

  if (
    !Number.isFinite(result)
    || result <= 0
  ) {
    return null;
  }

  return result;
}

function candleData(
  candles: MarketCandle[],
): CandlestickData<UTCTimestamp>[] {
  const points = candles
    .map((candle) => {
      const time = Math.floor(
        Number(candle.open_time) / 1000,
      );

      const open = Number(candle.open);
      const high = Number(candle.high);
      const low = Number(candle.low);
      const close = Number(candle.close);

      if (
        !Number.isFinite(time)
        || !Number.isFinite(open)
        || !Number.isFinite(high)
        || !Number.isFinite(low)
        || !Number.isFinite(close)
      ) {
        return null;
      }

      return {
        time: time as UTCTimestamp,
        open,
        high,
        low,
        close,
      };
    })
    .filter(
      (
        point,
      ): point is CandlestickData<UTCTimestamp> =>
        point !== null,
    )
    .sort(
      (left, right) =>
        Number(left.time)
        - Number(right.time),
    );

  const unique = new Map<
    number,
    CandlestickData<UTCTimestamp>
  >();

  for (const point of points) {
    unique.set(
      Number(point.time),
      point,
    );
  }

  return [...unique.values()];
}

function buildLevels(
  signal: TradingSignal,
  language: Language,
): ChartLevel[] {
  const t = chartCopy[language];

  const entryMin = priceNumber(
    signal.entry_min,
  );
  const entryMax = priceNumber(
    signal.entry_max,
  );
  const stopLoss = priceNumber(
    signal.stop_loss,
  );
  const tp1 = priceNumber(
    signal.take_profit_1,
  );
  const tp2 = priceNumber(
    signal.take_profit_2,
  );
  const tp3 = priceNumber(
    signal.take_profit_3,
  );
  const current = priceNumber(
    signal.current_price,
  );

  const levels: ChartLevel[] = [];

  if (
    entryMin !== null
    && entryMax !== null
    && Math.abs(entryMin - entryMax)
      < Number.EPSILON
  ) {
    levels.push({
      title: t.entry.toUpperCase(),
      price: entryMin,
      color: '#299fe5',
      lineStyle: LineStyle.Dashed,
      lineWidth: 2,
    });
  } else {
    if (entryMin !== null) {
      levels.push({
        title: 'ENTRY MIN',
        price: entryMin,
        color: '#299fe5',
        lineStyle: LineStyle.Dashed,
        lineWidth: 2,
      });
    }

    if (entryMax !== null) {
      levels.push({
        title: 'ENTRY MAX',
        price: entryMax,
        color: '#299fe5',
        lineStyle: LineStyle.Dashed,
        lineWidth: 2,
      });
    }
  }

  if (stopLoss !== null) {
    levels.push({
      title: 'STOP LOSS',
      price: stopLoss,
      color: '#ea5a64',
      lineStyle: LineStyle.Solid,
      lineWidth: 2,
    });
  }

  if (tp1 !== null) {
    levels.push({
      title: 'TP1',
      price: tp1,
      color: '#18b978',
      lineStyle: LineStyle.Solid,
      lineWidth: 2,
    });
  }

  if (tp2 !== null) {
    levels.push({
      title: 'TP2',
      price: tp2,
      color: '#20a96f',
      lineStyle: LineStyle.Dashed,
      lineWidth: 2,
    });
  }

  if (tp3 !== null) {
    levels.push({
      title: 'TP3',
      price: tp3,
      color: '#288c61',
      lineStyle: LineStyle.Dotted,
      lineWidth: 2,
    });
  }

  const existingPrices = levels.map(
    (level) => level.price,
  );

  if (
    current !== null
    && !existingPrices.some(
      (price) =>
        Math.abs(price - current)
        < Number.EPSILON,
    )
  ) {
    levels.push({
      title: t.current.toUpperCase(),
      price: current,
      color: '#a8b8c5',
      lineStyle: LineStyle.Dotted,
      lineWidth: 1,
    });
  }

  return levels;
}

function renderChart(
  container: HTMLDivElement,
  candles: MarketCandle[],
  signal: TradingSignal,
  language: Language,
): IChartApi {
  const chart = createChart(
    container,
    {
      width: container.clientWidth || 900,
      height: 410,
      layout: {
        background: {
          type: ColorType.Solid,
          color: '#07111c',
        },
        textColor: '#8fa7bb',
        attributionLogo: false,
      },
      grid: {
        vertLines: {
          color: '#112536',
        },
        horzLines: {
          color: '#112536',
        },
      },
      rightPriceScale: {
        borderColor: '#22384a',
        scaleMargins: {
          top: 0.12,
          bottom: 0.12,
        },
      },
      timeScale: {
        borderColor: '#22384a',
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: {
          color: '#49657b',
          labelBackgroundColor: '#1c3b52',
        },
        horzLine: {
          color: '#49657b',
          labelBackgroundColor: '#1c3b52',
        },
      },
    },
  );

  const series = chart.addSeries(
    CandlestickSeries,
    {
      upColor: '#16c784',
      downColor: '#ea5a64',
      wickUpColor: '#16c784',
      wickDownColor: '#ea5a64',
      borderVisible: false,
      priceLineVisible: false,
      lastValueVisible: true,
    },
  );

  series.setData(
    candleData(candles),
  );

  for (
    const level
    of buildLevels(signal, language)
  ) {
    series.createPriceLine({
      price: level.price,
      color: level.color,
      lineWidth: level.lineWidth,
      lineStyle: level.lineStyle,
      axisLabelVisible: true,
      title: level.title,
    });
  }

  chart.timeScale().fitContent();

  return chart;
}

export function SignalChart({
  signal,
  language,
}: SignalChartProps) {
  const t = chartCopy[language];

  const chartRef = useRef<
    HTMLDivElement
  >(null);

  const [
    candles,
    setCandles,
  ] = useState<MarketCandle[]>([]);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError(null);

    fetchSignalCandles(
      signal.symbol,
      signal.timeframe,
      240,
    )
      .then((payload) => {
        if (!active) {
          return;
        }

        setCandles(
          Array.isArray(payload.candles)
            ? payload.candles
            : [],
        );
      })
      .catch((loadError) => {
        if (!active) {
          return;
        }

        setCandles([]);

        setError(
          loadError instanceof Error
            ? loadError.message
            : t.error,
        );
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [
    signal.symbol,
    signal.timeframe,
    t.error,
  ]);

  useEffect(() => {
    const container = chartRef.current;

    if (
      !container
      || candles.length === 0
    ) {
      return;
    }

    container.innerHTML = '';

    const chart = renderChart(
      container,
      candles,
      signal,
      language,
    );

    const resizeObserver =
      new ResizeObserver(() => {
        chart.applyOptions({
          width:
            container.clientWidth
            || 900,
        });
      });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [
    candles,
    signal,
    language,
  ]);

  const levels = buildLevels(
    signal,
    language,
  );

  return (
    <section className="signal-chart">
      <div className="signal-chart__header">
        <div>
          <h3>
            <BarChart3 size={18} />
            {t.title}
          </h3>

          <p>
            {signal.symbol}
            {' · '}
            {signal.timeframe}
            {' · '}
            {t.subtitle}
          </p>
        </div>

        <div className="signal-chart__legend">
          {levels.map((level) => (
            <span
              key={`${level.title}-${level.price}`}
            >
              <i
                style={{
                  background:
                    level.color,
                }}
              />
              {level.title}
            </span>
          ))}
        </div>
      </div>

      {loading && (
        <div className="signal-chart__state">
          <LoaderCircle
            size={24}
            className="is-spinning"
          />
          {t.loading}
        </div>
      )}

      {!loading && error && (
        <div className="signal-chart__state signal-chart__state--error">
          <ShieldAlert size={21} />
          {t.error}: {error}
        </div>
      )}

      {!loading
        && !error
        && candles.length === 0
        && (
          <div className="signal-chart__state signal-chart__state--error">
            <ShieldAlert size={21} />
            {t.error}
          </div>
        )}

      <div
        ref={chartRef}
        className={[
          'signal-chart__canvas',
          loading || error
            ? 'signal-chart__canvas--hidden'
            : '',
        ].join(' ')}
      />
    </section>
  );
}
