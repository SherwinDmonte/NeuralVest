// Overview (Phase 12B, task 12B.4.1). Every figure comes from the API (computed in Python):
// indices and breadth from /market, the chart from /stocks/^NSEI/history, insights from your
// latest report. Breadth covers the 30 curated stocks only and says so.
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  ArrowsDownUp,
  CalendarBlank,
  ChartLineUp,
  Clock,
  FileText,
  Globe,
  Lightning,
  Newspaper,
  Robot,
  Sparkle,
  Star,
  TrendDown,
  TrendUp,
} from '@phosphor-icons/react'
import { useAuth } from '../auth/AuthContext'
import { useCurrentAnalysis } from '../analysis/AnalysisContext'
import { JOB_TEXT, progressOf } from '../components/AgentStatus'
import { MarketAreaChart, Sparkline } from '../components/charts'
import { AnimatedNumber, AnimatedTabs, Reveal } from '../components/motion'
import { Button, Card, Change, EmptyState, ErrorState, Meta, Skeleton, ToneBadge, Traced } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { useWatchlist } from '../hooks/useWatchlist'
import { getIndicators, getMarketBreadth, getMarketIndices, getNews, getQuotes, getStockHistory, listReports } from '../services/api'
import { fmtDate, fmtDateTime, num, safeUrl, shortSymbol } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

const RANGES = [
  { value: '1mo', label: '1M' }, { value: '3mo', label: '3M' }, { value: '6mo', label: '6M' },
  { value: '1y', label: '1Y' }, { value: '2y', label: '2Y' },
]

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

// ------------------------------------------------------------------ hero
function Hero({ indices, reports }) {
  const { user } = useAuth()
  const { symbols } = useWatchlist()
  const navigate = useNavigate()
  const first = user?.name?.split(' ')[0]
  const asOf = indices.data?.items?.[0]
  return (
    <section className="relative overflow-hidden rounded-3xl border border-line bg-surface/70 p-6 shadow-float sm:p-8">
      <div className="pointer-events-none absolute inset-0 grid-lines opacity-60 [mask-image:radial-gradient(ellipse_at_top_right,black,transparent_70%)]" aria-hidden="true" />
      <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-accent/25 blur-3xl" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-32 left-1/3 h-72 w-72 rounded-full bg-violet/20 blur-3xl" aria-hidden="true" />
      <div className="relative grid gap-8 lg:grid-cols-[1.4fr_1fr] lg:items-center">
        <div>
          <p className="flex items-center gap-2 caption-3 text-ink-muted"><CalendarBlank size={14} aria-hidden="true" />
            {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</p>
          <h1 className="mt-3 heading-5 text-ink sm:heading-3">
            {greeting()}{first ? `, ${first}` : ''}. <span className="text-brand">Your market desk is ready.</span>
          </h1>
          <p className="mt-3 max-w-xl body-6 text-ink-secondary sm:body-3">
            Five AI agents research Indian stocks on your own computer. Every figure below is computed in Python
            from named sources, and every report shows its working.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button size="lg" to="/app/analysis"><Lightning size={18} weight="fill" aria-hidden="true" /> Analyze a stock</Button>
            <Button size="lg" variant="glass" onClick={() => navigate('/app/market')}><Globe size={18} aria-hidden="true" /> Market intelligence</Button>
          </div>
          <p className="mt-6 flex flex-wrap items-center gap-2 caption-5 text-ink-muted">
            <Clock size={14} aria-hidden="true" />
            {asOf ? <>Last data update: {fmtDate(asOf.date)} close · fetched {fmtDateTime(asOf.fetched_at)} · end of day, not real time</> : 'Loading the latest end of day data'}
          </p>
        </div>
        <dl className="grid grid-cols-3 gap-3">
          {[
            ['Reports', reports.data?.total, FileText, '/app/reports'],
            ['Watchlist', symbols.length, Star, '/app/watchlist'],
            ['Agents', 5, Robot, '/app/agents'],
          ].map(([label, value, Icon, to]) => (
            <Link key={label} to={to} className="group rounded-2xl border border-line glass p-4 transition-[transform,border-color] duration-300 ease-nv hover:-translate-y-0.5 hover:border-line-strong">
              <Icon size={18} className="text-accent-ink" aria-hidden="true" />
              <dd className="mt-3 figure-1 text-ink">{value == null ? '…' : <AnimatedNumber value={value} format={(v) => Math.round(v)} />}</dd>
              <dt className="caption-5 text-ink-muted">{label}</dt>
            </Link>
          ))}
        </dl>
      </div>
    </section>
  )
}

// ------------------------------------------------------------------ market cards
function IndexCard({ item }) {
  return (
    <div className="group relative flex flex-col overflow-hidden rounded-2xl border border-line bg-surface p-4 shadow-card transition-[transform,border-color] duration-300 ease-nv hover:-translate-y-0.5 hover:border-line-strong">
      <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-brand opacity-60" aria-hidden="true" />
      <div className="flex items-center justify-between gap-2">
        <span className="caption-2 text-ink-secondary">{item.name}</span>
        <Change value={item.change_pct} />
      </div>
      <div className="mt-2 figure-1 text-ink"><AnimatedNumber value={item.last_close} format={(v) => num(v)} /></div>
      <div className="mt-1 caption-5 text-ink-muted">vs {num(item.previous_close)} on {fmtDate(item.previous_date)}</div>
      <div className="mt-3"><Sparkline data={item.series} up={item.change_pct >= 0} /></div>
    </div>
  )
}

function MiniStat({ label, value, sub, icon: Icon, tone }) {
  return (
    <div className="flex flex-col rounded-2xl border border-line bg-surface p-4 shadow-card transition-[transform,border-color] duration-300 ease-nv hover:-translate-y-0.5 hover:border-line-strong">
      <div className="flex items-center justify-between gap-2">
        <span className="caption-2 text-ink-secondary">{label}</span>
        <Icon size={16} className={tone || 'text-ink-muted'} aria-hidden="true" />
      </div>
      <div className="mt-2 figure-1 text-ink">{value}</div>
      <div className="mt-auto pt-1 caption-5 text-ink-muted">{sub}</div>
    </div>
  )
}

function MarketCards({ indices, breadth }) {
  const trend = useApi(() => getIndicators('^NSEI', '6mo'), [], { key: 'nifty-ind-6mo', ttl: 10 * 60 * 1000 })
  if (indices.error && !indices.data) return <ErrorState message={`Index prices are unavailable right now. ${indices.error}`} />
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
      {indices.loading && !indices.data
        ? [0, 1].map((i) => <Skeleton key={i} className="h-40 rounded-2xl" />)
        : indices.data?.items.map((it) => <IndexCard key={it.symbol} item={it} />)}
      <MiniStat label="Market trend" icon={ArrowsDownUp}
                value={trend.data ? <ToneBadge value={trend.data.trend?.classification} /> : <Skeleton className="h-6 w-24" />}
                sub={trend.data ? `NIFTY 50 moving averages · RSI ${num(trend.data.latest?.rsi_14)}` : 'NIFTY 50 moving averages'} />
      <MiniStat label="Advancers" icon={TrendUp} tone="text-good"
                value={breadth.data ? <AnimatedNumber value={breadth.data.advancers} format={(v) => Math.round(v)} /> : <Skeleton className="h-8 w-12" />}
                sub={breadth.data ? `of ${breadth.data.counted} curated stocks` : breadth.error ? 'unavailable' : 'measuring 30 curated stocks'} />
      <MiniStat label="Decliners" icon={TrendDown} tone="text-critical"
                value={breadth.data ? <AnimatedNumber value={breadth.data.decliners} format={(v) => Math.round(v)} /> : <Skeleton className="h-8 w-12" />}
                sub={breadth.data ? `of ${breadth.data.counted} curated stocks` : breadth.error ? 'unavailable' : 'measuring 30 curated stocks'} />
      <MiniStat label="Data freshness" icon={Clock}
                value={<span className="title-1">{indices.data?.items?.[0] ? fmtDate(indices.data.items[0].date) : '…'}</span>}
                sub="End of day close, Yahoo Finance" />
    </div>
  )
}

// ------------------------------------------------------------------ main chart and movers
function NiftyChart() {
  const [range, setRange] = useState('1y')
  const { data, error, loading } = useApi(() => getStockHistory('^NSEI', range), [range], { key: `nifty-hist-${range}`, ttl: 10 * 60 * 1000 })
  const series = data?.records || []
  return (
    <div className="xl:col-span-2">
      {error && !data && <ErrorState message={`The NIFTY 50 history is unavailable. ${error}`} />}
      {loading && !data ? <Skeleton className="h-[420px] rounded-2xl" /> : series.length > 1 && (
        <MarketAreaChart title="NIFTY 50" icon={ChartLineUp} height={320} data={series} name="NIFTY 50 close"
                         subtitle={`Daily close · ${fmtDate(series[0].date)} to ${fmtDate(series[series.length - 1].date)}`}
                         actions={<AnimatedTabs size="sm" label="Date range" tabs={RANGES} value={range} onChange={setRange} />} />
      )}
    </div>
  )
}

function Movers({ breadth }) {
  const [side, setSide] = useState('gainers')
  const rows = breadth.data?.[side] || []
  return (
    <Card title="Top movers" subtitle={breadth.data ? `${fmtDate(breadth.data.as_of)} · among 30 curated stocks, not the whole market` : 'Among 30 curated stocks'}
          actions={<AnimatedTabs size="sm" label="Movers" value={side} onChange={setSide} tabs={[{ value: 'gainers', label: 'Gainers' }, { value: 'losers', label: 'Losers' }]} />}>
      {breadth.loading && !breadth.data && <div className="space-y-3">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-10" />)}<p className="caption-5 text-ink-muted">The first load fetches 30 stocks and can take up to a minute.</p></div>}
      {breadth.error && !breadth.data && <ErrorState message={breadth.error} />}
      {breadth.data && (rows.length ? (
        <ul className="divide-y divide-line">
          {rows.map((r, i) => (
            <li key={r.symbol} className="flex items-center gap-3 py-2">
              <span className="w-5 figure caption-5 text-ink-muted">{i + 1}</span>
              <Link to={`/app/analysis?symbol=${encodeURIComponent(r.symbol)}`} className="flex-1 truncate body-5 text-ink transition-colors duration-300 ease-nv hover:text-accent-ink">{shortSymbol(r.symbol)}</Link>
              <span className="figure caption-2 text-ink-secondary">{num(r.last_close)}</span>
              <Change value={r.change_pct} />
            </li>
          ))}
        </ul>
      ) : <p className="body-6 text-ink-muted">No {side} on {fmtDate(breadth.data.as_of)}.</p>)}
      {breadth.data && <p className="mt-3 caption-5 text-ink-muted">{breadth.data.rule}</p>}
    </Card>
  )
}

// ------------------------------------------------------------------ lower row
function Insights({ reports }) {
  const latest = reports.data?.items?.find((r) => r.report_ready)
  return (
    <Card title="AI insights" subtitle={latest ? `From your latest report · ${latest.symbols.join(', ')}` : 'From your reports'} icon={Sparkle} accent>
      {reports.loading && !reports.data && <div className="space-y-2"><Skeleton className="h-4" /><Skeleton className="h-4 w-2/3" /></div>}
      {!reports.loading && !latest && (
        <EmptyState icon={Robot} title="No insights yet" action={<Button size="sm" to="/app/analysis">Run your first analysis</Button>}>
          Key observations from your latest analysis appear here. They are written by the local model and checked against the computed readings.
        </EmptyState>
      )}
      {latest && (
        <>
          <ul className="space-y-3">
            {latest.key_observations.map((o) => (
              <li key={o} className="flex gap-3 body-6 text-ink">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden="true" />{o}
              </li>
            ))}
          </ul>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
            <Meta>{fmtDateTime(latest.requested_at)} · {latest.traceability_ok ? 'all numbers traced' : 'see the report for untraced numbers'}</Meta>
            <Button size="xs" variant="ghost" to={`/app/reports/${latest.report_id}`}>Open the report <ArrowRight size={14} aria-hidden="true" /></Button>
          </div>
        </>
      )}
    </Card>
  )
}

function WatchlistSummary() {
  const { symbols, loading } = useWatchlist()
  const key = symbols.slice(0, 6).join(',')
  const quotes = useApi(() => getQuotes(symbols.slice(0, 6)), [key], { key: `quotes-${key}`, enabled: symbols.length > 0 })
  return (
    <Card title="Watchlist" subtitle="End of day prices" icon={Star}
          actions={<Button size="xs" variant="ghost" to="/app/watchlist">Manage <ArrowRight size={14} aria-hidden="true" /></Button>}>
      {!loading && !symbols.length && (
        <EmptyState icon={Star} title="Nothing watched yet">Add stocks from their analysis page or from the Watchlist page.</EmptyState>
      )}
      {symbols.length > 0 && quotes.loading && !quotes.data && <div className="space-y-3">{symbols.slice(0, 4).map((s) => <Skeleton key={s} className="h-10" />)}</div>}
      {quotes.data && (
        <ul className="divide-y divide-line">
          {quotes.data.items.map((q) => (
            <li key={q.symbol} className="grid grid-cols-[minmax(0,1fr)_72px_auto] items-center gap-3 py-2">
              <Link to={`/app/analysis?symbol=${encodeURIComponent(q.symbol)}`} className="truncate body-5 text-ink transition-colors duration-300 ease-nv hover:text-accent-ink">{shortSymbol(q.symbol)}</Link>
              <Sparkline data={q.series.slice(-30)} height={28} up={q.change_pct >= 0} />
              <span className="flex items-center gap-2"><span className="figure caption-2 text-ink">{num(q.last_close)}</span><Change value={q.change_pct} /></span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function LatestNews({ symbols }) {
  const key = symbols.slice(0, 3).join(',')
  const { data, loading } = useApi(
    () => Promise.all(symbols.slice(0, 3).map((s) => getNews(s, { page_size: 3 }).then((r) => r.items).catch(() => [])))
      .then((lists) => lists.flat().sort((a, b) => (b.publication_date || '').localeCompare(a.publication_date || '')).slice(0, 5)),
    [key], { key: `news-${key}`, enabled: symbols.length > 0 },
  )
  return (
    <Card title="Latest news" subtitle={symbols.length ? `Stored articles for ${symbols.slice(0, 3).map(shortSymbol).join(', ')}` : 'From your watchlist and analyses'} icon={Newspaper}
          actions={<Button size="xs" variant="ghost" to="/app/news">All news <ArrowRight size={14} aria-hidden="true" /></Button>}>
      {!symbols.length && <EmptyState icon={Newspaper}>Watch a stock or run an analysis to collect its news.</EmptyState>}
      {symbols.length > 0 && loading && !data && <div className="space-y-3"><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /></div>}
      {symbols.length > 0 && data && !data.length && <EmptyState icon={Newspaper}>No stored articles yet. An analysis collects the last 14 days of news.</EmptyState>}
      {data?.length > 0 && (
        <ul className="space-y-1">
          {data.map((a) => {
            const href = safeUrl(a.article_url)
            return (
              <li key={a.url_hash} className="rounded-xl p-2 transition-colors duration-300 ease-nv hover:bg-raised/60">
                {href ? <a href={href} target="_blank" rel="noopener noreferrer" className="body-5 text-ink hover:text-accent-ink">{a.headline}</a>
                  : <span className="body-5 text-ink">{a.headline}</span>}
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="rounded-md bg-accent/10 px-1.5 figure caption-5 text-accent-ink">{shortSymbol(a.symbol)}</span>
                  <Meta>{a.publisher}</Meta><Meta>{fmtDate(a.publication_date)}</Meta>
                  <ToneBadge value={a.sentiment} />
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

function AgentActivity({ reports }) {
  const { status, requestId } = useCurrentAnalysis()
  const { done, total } = progressOf(status?.agents)
  return (
    <Card title="Agent activity" icon={Robot} actions={<Button size="xs" variant="ghost" to="/app/agents">Agents <ArrowRight size={14} aria-hidden="true" /></Button>}>
      {status ? (
        <div className="rounded-2xl border border-line bg-raised/50 p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="body-5 text-ink">{status.symbols?.join(', ')}</span>
            <ToneBadge value={status.status} />
          </div>
          <p className="mt-1 caption-2 text-ink-secondary">{JOB_TEXT[status.status] || status.status}</p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-raised" aria-hidden="true">
            <div className="h-full origin-left rounded-full bg-brand transition-transform duration-500 ease-nv" style={{ transform: `scaleX(${done / total})` }} />
          </div>
          <div className="mt-2 flex justify-between"><Meta>{done} of {total} steps</Meta>
            <Link to={`/app/agents${requestId ? `?request=${requestId}` : ''}`} className="caption-4 text-accent-ink hover:underline">Follow live</Link></div>
        </div>
      ) : (
        <p className="caption-2 text-ink-muted">No analysis is running.</p>
      )}
      {reports.data?.items?.length > 0 && (
        <ul className="mt-4 space-y-2">
          {reports.data.items.slice(0, 4).map((r) => (
            <li key={r.report_id} className="flex items-center justify-between gap-3">
              <Link to={`/app/reports/${r.report_id}`} className="min-w-0 truncate caption-2 text-ink transition-colors duration-300 ease-nv hover:text-accent-ink">{r.symbols.join(', ')}</Link>
              <span className="flex shrink-0 items-center gap-2"><Meta>{fmtDate(r.requested_at)}</Meta><ToneBadge value={r.status} /></span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function RecentlyAnalysed({ recent }) {
  return (
    <Card title="Recently analysed" icon={ChartLineUp}>
      {recent.length ? (
        <ul className="flex flex-wrap gap-2">
          {recent.map((s) => (
            <li key={s}><Button to={`/app/analysis?symbol=${encodeURIComponent(s)}`} size="xs" variant="secondary">{s}</Button></li>
          ))}
        </ul>
      ) : <p className="caption-2 text-ink-muted">Stocks from your reports appear here.</p>}
    </Card>
  )
}

export default function DashboardPage() {
  usePageTitle('Overview')
  const { symbols: watched } = useWatchlist()
  const indices = useApi(getMarketIndices, [], { key: 'indices', ttl: 10 * 60 * 1000 })
  const breadth = useApi(() => getMarketBreadth(5), [], { key: 'breadth', ttl: 10 * 60 * 1000 })
  const reports = useApi(() => listReports({ page_size: 8 }), [], { key: 'reports-recent', ttl: 30 * 1000 })
  const recent = useMemo(() => [...new Set((reports.data?.items || []).flatMap((r) => r.symbols))].slice(0, 10), [reports.data])
  const newsSymbols = watched.length ? watched : recent

  return (
    <div className="space-y-6">
      <Hero indices={indices} reports={reports} />
      <Reveal><MarketCards indices={indices} breadth={breadth} /></Reveal>
      <Reveal>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <NiftyChart />
          <Movers breadth={breadth} />
        </div>
      </Reveal>
      <Reveal>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="space-y-6 xl:col-span-2">
            <Insights reports={reports} />
            <LatestNews symbols={newsSymbols} />
          </div>
          <div className="space-y-6">
            <WatchlistSummary />
            <AgentActivity reports={reports} />
            <RecentlyAnalysed recent={recent} />
          </div>
        </div>
      </Reveal>
      <p className="flex items-center gap-2 caption-5 text-ink-muted"><Traced agent="market data" /> Index and breadth figures are end of day from Yahoo Finance; breadth covers NeuralVest&apos;s 30 curated stocks only.</p>
    </div>
  )
}
