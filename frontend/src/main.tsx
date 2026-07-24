import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { CandlestickSeries, ColorType, createChart } from 'lightweight-charts';
import {
  Activity,
  BarChart3,
  Bell,
  BrainCircuit,
  Globe2,
  LayoutDashboard,
  Newspaper,
  Search,
  Settings,
  Star,
  TrendingUp,
} from 'lucide-react';
import './styles.css';

const API = '/api';
const FORECAST_HORIZONS = [15, 30, 60, 120, 240, 1440, 2880, 7200, 14400];

type Pair = { symbol: string; base_asset: string; quote_asset: string };
type Page = 'dashboard' | 'markets' | 'signals' | 'future' | 'news' | 'analytics' | 'settings';
type Language = 'ru' | 'en';

const dictionary = {
  ru: {
    dashboard: 'Обзор', markets: 'Рынки', signals: 'Сигналы', future: 'Будущие сигналы',
    news: 'Новости', analytics: 'Аналитика', settings: 'Настройки', pair: 'Торговая пара',
    timeframe: 'Таймфрейм', refresh: 'Обновить', current: 'Текущий сигнал',
    forecast: 'Прогноз движения', latest: 'Последние новости', confidence: 'Уверенность',
    search: 'Поиск пары', entry: 'Вход', stop: 'Стоп-лосс', take: 'Тейк-профит',
    minute: 'мин', hour: 'ч', day: 'день', days: 'дня', noNews: 'Нет доступных новостей или источники временно недоступны.',
    sourceImpact: 'влияние', marketOverview: 'Обзор выбранного рынка',
    signalDetails: 'Параметры торгового сигнала', forecastDetails: 'Прогнозы по горизонтам',
    newsMonitor: 'Мониторинг мировых криптоновостей', analyticsTitle: 'Сводная аналитика',
    settingsTitle: 'Настройки интерфейса', language: 'Язык интерфейса',
    activePair: 'Активная пара', activeTimeframe: 'Активный таймфрейм',
    forecastsCount: 'Доступно прогнозов', newsCount: 'Найдено новостей',
    up: 'РОСТ', down: 'СНИЖЕНИЕ', sideways: 'БОКОВИК', uncertain: 'НЕОПРЕДЕЛЁННО',
    long: 'ПОКУПКА', short: 'ПРОДАЖА', wait: 'ОЖИДАНИЕ', neutral: 'НЕЙТРАЛЬНО',
  },
  en: {
    dashboard: 'Dashboard', markets: 'Markets', signals: 'Signals', future: 'Future signals',
    news: 'News', analytics: 'Analytics', settings: 'Settings', pair: 'Trading pair',
    timeframe: 'Timeframe', refresh: 'Refresh', current: 'Current signal',
    forecast: 'Movement forecast', latest: 'Latest news', confidence: 'Confidence',
    search: 'Search pair', entry: 'Entry', stop: 'Stop loss', take: 'Take profit',
    minute: 'min', hour: 'h', day: 'day', days: 'days', noNews: 'No news is available or the sources are temporarily unavailable.',
    sourceImpact: 'impact', marketOverview: 'Selected market overview',
    signalDetails: 'Trading signal parameters', forecastDetails: 'Forecasts by horizon',
    newsMonitor: 'Global crypto news monitoring', analyticsTitle: 'Analytics summary',
    settingsTitle: 'Interface settings', language: 'Interface language',
    activePair: 'Active pair', activeTimeframe: 'Active timeframe',
    forecastsCount: 'Available forecasts', newsCount: 'News items found',
    up: 'UP', down: 'DOWN', sideways: 'SIDEWAYS', uncertain: 'UNCERTAIN',
    long: 'LONG', short: 'SHORT', wait: 'WAIT', neutral: 'NEUTRAL',
  },
} as const;

function formatMoney(value: unknown): string {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPercent(value: unknown): string {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`;
}

function formatHorizon(minutes: number, lang: Language): string {
  if (minutes < 60) return `+${minutes} ${dictionary[lang].minute}`;
  if (minutes < 1440) return `+${minutes / 60} ${dictionary[lang].hour}`;
  const days = minutes / 1440;
  const unit = days === 1 ? dictionary[lang].day : dictionary[lang].days;
  return `+${days} ${unit}`;
}

function App() {
  const storedLanguage = localStorage.getItem('lang');
  const initialLanguage: Language = storedLanguage === 'en' ? 'en' : 'ru';
  const [lang, setLang] = useState<Language>(initialLanguage);
  const [page, setPage] = useState<Page>('dashboard');
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [interval, setInterval] = useState('1h');
  const [query, setQuery] = useState('');
  const [data, setData] = useState<any>({});
  const [news, setNews] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const t = dictionary[lang];

  const navigation = [
    { id: 'dashboard' as Page, icon: LayoutDashboard, label: t.dashboard },
    { id: 'markets' as Page, icon: TrendingUp, label: t.markets },
    { id: 'signals' as Page, icon: Activity, label: t.signals },
    { id: 'future' as Page, icon: BarChart3, label: t.future },
    { id: 'news' as Page, icon: Newspaper, label: t.news },
    { id: 'analytics' as Page, icon: Globe2, label: t.analytics },
    { id: 'settings' as Page, icon: Settings, label: t.settings },
  ];

  useEffect(() => {
    fetch(`${API}/v1/market/symbols?quote_asset=USDT`)
      .then((response) => response.json())
      .then((payload) => setPairs(payload.pairs || []))
      .catch(() => setPairs([]));
  }, []);

  async function load() {
    setLoading(true);
    try {
      const asset = symbol.replace(/USDT$|USDC$|BUSD$|FDUSD$/, '');
      const horizons = FORECAST_HORIZONS.join(',');
      const [klines, signal, forecast, newsPayload] = await Promise.all([
        fetch(`${API}/v1/market/klines?symbol=${symbol}&interval=${interval}&limit=500`).then((response) => response.json()),
        fetch(`${API}/v1/signal-engine/analyze?symbol=${symbol}&interval=${interval}&limit=250`).then((response) => response.json()),
        fetch(`${API}/v2/forecasts/current?symbol=${symbol}&horizons=${horizons}`).then((response) => response.json()),
        fetch(`${API}/v2/news?limit=20&asset=${asset}`).then((response) => response.json()),
      ]);
      setData({ k: klines, s: signal, f: forecast });
      setNews(newsPayload.articles || []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [symbol, interval]);

  const showChart = page === 'dashboard' || page === 'markets';
  useEffect(() => {
    if (!showChart || !chartRef.current || !data.k?.candles?.length) return;
    chartRef.current.innerHTML = '';
    const chart = createChart(chartRef.current, {
      height: 430,
      layout: { background: { type: ColorType.Solid, color: '#08131f' }, textColor: '#8fa7bb' },
      grid: { vertLines: { color: '#142536' }, horzLines: { color: '#142536' } },
      rightPriceScale: { borderColor: '#22384a' },
      timeScale: { borderColor: '#22384a' },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#16c784', downColor: '#ea3943', wickUpColor: '#16c784',
      wickDownColor: '#ea3943', borderVisible: false,
    });
    series.setData(data.k.candles.map((candle: any) => ({
      time: Math.floor(candle.open_time / 1000),
      open: Number(candle.open), high: Number(candle.high), low: Number(candle.low), close: Number(candle.close),
    })));
    chart.timeScale().fitContent();
    const resizeObserver = new ResizeObserver(() => chart.applyOptions({ width: chartRef.current?.clientWidth || 800 }));
    resizeObserver.observe(chartRef.current);
    return () => { resizeObserver.disconnect(); chart.remove(); };
  }, [data.k, showChart]);

  const filteredPairs = useMemo(
    () => pairs.filter((pair) => pair.symbol.includes(query.toUpperCase())).slice(0, 100),
    [pairs, query],
  );
  const action = String(data.s?.action || 'WAIT').toUpperCase();
  const forecasts = data.f?.forecasts || [];
  const baseAsset = symbol.replace(/USDT$|USDC$|BUSD$|FDUSD$/, '');

  const translateDirection = (value: string) => {
    const key = value.toLowerCase() as keyof typeof t;
    return (t as any)[key] || value;
  };

  const controls = (
    <section className="controls">
      <label>{t.pair}
        <div className="combo">
          <Search size={15} />
          <input
            ref={searchRef}
            value={query}
            placeholder={t.search}
            onChange={(event) => setQuery(event.target.value)}
          />
          <select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
            {(query ? filteredPairs : pairs.slice(0, 300)).map((pair) => (
              <option key={pair.symbol} value={pair.symbol}>{pair.base_asset}/{pair.quote_asset}</option>
            ))}
          </select>
        </div>
      </label>
      <label>{t.timeframe}
        <select value={interval} onChange={(event) => setInterval(event.target.value)}>
          {['1m', '5m', '15m', '30m', '1h', '4h', '1d'].map((value) => <option key={value}>{value}</option>)}
        </select>
      </label>
      <button className="primary" onClick={() => void load()}>{loading ? '…' : t.refresh}</button>
    </section>
  );

  const marketPanel = (
    <div className="panel chart-panel">
      <div className="panel-title"><div><h2>{symbol}</h2><span>{interval} · Binance Spot</span></div><Star size={18} /></div>
      <div ref={chartRef} />
    </div>
  );

  const signalPanel = (
    <div className={`panel signal ${action.toLowerCase()}`}>
      <span>{t.current}</span><strong>{translateDirection(action)}</strong>
      <small>{t.confidence}: {data.s?.confidence ?? '—'}%</small>
      <div className="levels">
        <div><b>{t.entry}</b>{formatMoney(data.s?.levels?.entry)}</div>
        <div><b>{t.stop}</b>{formatMoney(data.s?.levels?.stop_loss)}</div>
        <div><b>{t.take}</b>{formatMoney(data.s?.levels?.take_profit)}</div>
      </div>
    </div>
  );

  const forecastPanel = (
    <section className="forecasts">
      <h2>{t.forecast}</h2>
      <div className="forecast-grid">
        {forecasts.map((forecast: any) => (
          <article key={forecast.horizon_minutes} className={`forecast-card ${String(forecast.direction).toLowerCase()}`}>
            <div><span>{formatHorizon(forecast.horizon_minutes, lang)}</span><b>{translateDirection(forecast.direction)}</b></div>
            <strong>{forecast.confidence}%</strong>
            <p>{formatPercent(forecast.expected_change_percent)}</p>
            <small>{formatMoney(forecast.price_range.low)} — {formatMoney(forecast.price_range.high)}</small>
          </article>
        ))}
      </div>
    </section>
  );

  const newsPanel = (
    <section className="panel news">
      <div className="panel-title"><h2>{t.latest}</h2><span>{baseAsset}</span></div>
      {news.length ? news.map((item, index) => (
        <a key={`${item.url}-${index}`} href={item.url} target="_blank" rel="noreferrer">
          <div>
            <span className={`badge ${item.sentiment}`}>{translateDirection(item.sentiment)}</span>
            <b>{item.title}</b>
            <small>{item.source} · {t.sourceImpact} {item.impact_score}/100</small>
          </div>
        </a>
      )) : <p>{t.noNews}</p>}
    </section>
  );

  return (
    <div className="app">
      <aside>
        <div className="brand"><BrainCircuit />SignalAI <b>Pro</b></div>
        {navigation.map(({ id, icon: Icon, label }) => (
          <button key={id} type="button" className={page === id ? 'active' : ''} onClick={() => setPage(id)}>
            <Icon size={18} />{label}
          </button>
        ))}
      </aside>
      <main>
        <header>
          <div><h1>{navigation.find((item) => item.id === page)?.label}</h1><p>SignalAI Pro 2.0 RC1.2</p></div>
          <div className="header-actions"><Bell /><select value={lang} onChange={(event) => { const value = event.target.value as Language; setLang(value); localStorage.setItem('lang', value); }}><option value="ru">Русский</option><option value="en">English</option></select></div>
        </header>

        {(page === 'dashboard' || page === 'markets' || page === 'signals' || page === 'future' || page === 'news') && controls}

        {page === 'dashboard' && <><section className="grid">{marketPanel}{signalPanel}</section>{forecastPanel}{newsPanel}</>}
        {page === 'markets' && <><h2 className="section-heading">{t.marketOverview}</h2>{marketPanel}</>}
        {page === 'signals' && <><h2 className="section-heading">{t.signalDetails}</h2><section className="single-column">{signalPanel}</section></>}
        {page === 'future' && <><h2 className="section-heading">{t.forecastDetails}</h2>{forecastPanel}</>}
        {page === 'news' && <><h2 className="section-heading">{t.newsMonitor}</h2>{newsPanel}</>}
        {page === 'analytics' && <section className="page-panel"><h2>{t.analyticsTitle}</h2><div className="stats-grid"><article><span>{t.activePair}</span><strong>{symbol}</strong></article><article><span>{t.activeTimeframe}</span><strong>{interval}</strong></article><article><span>{t.forecastsCount}</span><strong>{forecasts.length}</strong></article><article><span>{t.newsCount}</span><strong>{news.length}</strong></article></div></section>}
        {page === 'settings' && <section className="page-panel"><h2>{t.settingsTitle}</h2><label className="settings-row"><span>{t.language}</span><select value={lang} onChange={(event) => { const value = event.target.value as Language; setLang(value); localStorage.setItem('lang', value); }}><option value="ru">Русский</option><option value="en">English</option></select></label></section>}
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
