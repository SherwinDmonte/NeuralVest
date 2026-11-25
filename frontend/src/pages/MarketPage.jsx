// Market intelligence (Phase 12B, task 12B.4.2): NIFTY 50 and SENSEX charts, NIFTY technicals,
// breadth and a sortable table of NeuralVest's 30 curated stocks, and news for the movers.
// End of day data from Yahoo Finance; breadth is not whole market data and says so.
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUp, ChartLineUp, Globe, Newspaper, Scales } from '@phosphor-icons/react'
import { MacdChart, MarketAreaChart, RsiChart, Sparkline } from '../components/charts'
import { AnimatedNumber, AnimatedTabs, Reveal } from '../components/motion'
import { ArticleList } from '../components/NewsList'
import { Card, Change, ErrorState, Meta, PageHeader, Skeleton, table } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { getIndicators, getMarketBreadth, getMarketIndices, getNews, getStockHistory } from '../services/api'
import { fmtDate, num, shortSymbol } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

const RANGES = [
  { value: '1mo', label: '1M' }, { value: '3mo', label: '3M' }, { value: '6mo', label: '6M' },
  { value: '1y', label: '1Y' }, { value: '2y', label: '2Y' },
]
const INDEX = { '^NSEI': 'NIFTY 50', '^BSESN': 'SENSEX' }

function IndexChart() {
  const [symbol, setSymbol] = useState('^NSEI')
  const [range, setRange] = useState('1y')
  const { data, error, loading } = useApi(() => getStockHistory(symbol, range), [symbol, range], { key: `hist-${symbol}-${range}`, ttl: 10 * 60 * 1000 })
  const series = data?.records || []
  return (
    <div>
      {error && !data && <ErrorState message={`${INDEX[symbol]} history is unavailable. ${error}`} />}
      {loading && !data ? <Skeleton className="h-[430px] rounded-2xl" /> : series.length > 1 && (
        <MarketAreaChart title={INDEX[symbol]} icon={Globe} height={340} data={series} name={`${INDEX[symbol]} close`}
                         subtitle={`Daily close · ${fmtDate(series[0].date)} to ${fmtDate(series[series.length - 1].date)}`}
                         actions={<>
                           <AnimatedTabs size="sm" label="Index" value={symbol} onChange={setSymbol} tabs={Object.entries(INDEX).map(([v, l]) => ({ value: v, label: l }))} />
                           <AnimatedTabs size="sm" label="Date range" value={range} onChange={setRange} tabs={RANGES} />
                         </>} />
      )}
    </div>
  )
}

function BreadthBar({ b }) {
  const total = b.advancers + b.decliners + b.unchanged || 1
  return (
    <div>
      <div className="flex h-3 gap-0.5 overflow-hidden rounded-full" role="img" aria-label={`${b.advancers} advancers, ${b.unchanged} unchanged, ${b.decliners} decliners`}>
        <span className="bg-good" style={{ width: `${(100 * b.advancers) / total}%` }} />
        {b.unchanged > 0 && <span className="bg-ink-muted" style={{ width: `${(100 * b.unchanged) / total}%` }} />}
        <span className="bg-critical" style={{ width: `${(100 * b.decliners) / total}%` }} />
      </div>
      <div className="mt-3 flex flex-wrap justify-between gap-2 caption-2">
        <span className="flex items-center gap-2 text-ink-secondary"><span className="h-2 w-2 rounded-sm bg-good" />Advancers <span className="figure text-ink">{b.advancers}</span></span>
        <span className="flex items-center gap-2 text-ink-secondary"><span className="h-2 w-2 rounded-sm bg-ink-muted" />Unchanged <span className="figure text-ink">{b.unchanged}</span></span>
        <span className="flex items-center gap-2 text-ink-secondary"><span className="h-2 w-2 rounded-sm bg-critical" />Decliners <span className="figure text-ink">{b.decliners}</span></span>
      </div>
    </div>
  )
}

function SortTh({ k, children, right, sort, setSort }) {
  return (
    <th className={right ? table.thR : table.th} aria-sort={sort.key === k ? (sort.dir > 0 ? 'ascending' : 'descending') : 'none'}>
      <button type="button" onClick={() => setSort((s) => ({ key: k, dir: s.key === k ? -s.dir : -1 }))}
              className={`inline-flex items-center gap-1 transition-colors duration-300 ease-nv hover:text-ink ${right ? 'flex-row-reverse' : ''}`}>
        {children}
        {sort.key === k && (sort.dir > 0 ? <ArrowUp size={12} aria-hidden="true" /> : <ArrowDown size={12} aria-hidden="true" />)}
      </button>
    </th>
  )
}

function CuratedTable({ rows }) {
  const [sort, setSort] = useState({ key: 'change_pct', dir: -1 })
  const sorted = useMemo(() => [...rows].sort((a, b) => {
    const x = a[sort.key], y = b[sort.key]
    return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sort.dir
  }), [rows, sort])
  return (
    <div className={`${table.wrap} max-h-[560px]`}>
      <table className={table.table}>
        <caption className="sr-only">The 30 curated stocks, sortable</caption>
        <thead className={`${table.thead} sticky top-0 z-10`}>
          <tr><SortTh k="symbol" sort={sort} setSort={setSort}>Stock</SortTh><SortTh k="last_close" right sort={sort} setSort={setSort}>Last close</SortTh><SortTh k="previous_close" right sort={sort} setSort={setSort}>Previous</SortTh><SortTh k="change_pct" right sort={sort} setSort={setSort}>Change</SortTh></tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.symbol} className={table.tr}>
              <td className="px-3 py-2"><Link to={`/app/analysis?symbol=${encodeURIComponent(r.symbol)}`} className="body-5 text-ink transition-colors duration-300 ease-nv hover:text-accent-ink">{shortSymbol(r.symbol)}</Link></td>
              <td className={table.tdR}>{num(r.last_close)}</td>
              <td className={`${table.tdR} text-ink-secondary`}>{num(r.previous_close)}</td>
              <td className="px-3 py-2 text-right"><Change value={r.change_pct} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MoverNews({ breadth }) {
  const movers = [...(breadth.data?.gainers || []).slice(0, 2), ...(breadth.data?.losers || []).slice(0, 2)].map((r) => r.symbol)
  const key = movers.join(',')
  const { data, loading } = useApi(
    () => Promise.all(movers.map((s) => getNews(s, { page_size: 2 }).then((r) => r.items).catch(() => [])))
      .then((l) => l.flat().sort((a, b) => (b.publication_date || '').localeCompare(a.publication_date || '')).slice(0, 6)),
    [key], { key: `mover-news-${key}`, enabled: movers.length > 0 },
  )
  return (
    <Card title="News on the movers" subtitle={movers.length ? `Stored articles for ${movers.map(shortSymbol).join(', ')}` : 'Biggest gainers and losers'} icon={Newspaper}>
      {loading && !data && <div className="space-y-3"><Skeleton className="h-10" /><Skeleton className="h-10" /></div>}
      {data && (data.length ? <ArticleList articles={data} /> : <p className="body-6 text-ink-muted">No stored articles for these stocks yet. News is collected when a stock is analysed.</p>)}
    </Card>
  )
}

export default function MarketPage() {
  usePageTitle('Market intelligence')
  const indices = useApi(getMarketIndices, [], { key: 'indices', ttl: 10 * 60 * 1000 })
  const breadth = useApi(() => getMarketBreadth(5), [], { key: 'breadth', ttl: 10 * 60 * 1000 })
  const tech = useApi(() => getIndicators('^NSEI', '1y'), [], { key: 'nifty-ind-1y', ttl: 10 * 60 * 1000 })

  return (
    <div className="space-y-6">
      <PageHeader title="Indian market at the last close"
                  description="NIFTY 50 and SENSEX with their history, NIFTY 50 technicals and the breadth of NeuralVest's 30 curated stocks. End of day data, never real time." />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {indices.loading && !indices.data && [0, 1].map((i) => <Skeleton key={i} className="h-36 rounded-2xl" />)}
        {indices.data?.items.map((it) => (
          <div key={it.symbol} className="relative overflow-hidden rounded-2xl border border-line bg-surface p-6 shadow-card">
            <span className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-accent/15 blur-3xl" aria-hidden="true" />
            <div className="relative grid grid-cols-[minmax(0,1fr)_96px] items-end gap-4 sm:grid-cols-[minmax(0,1fr)_160px]">
              <div>
                <div className="flex items-center gap-3"><span className="title-2 text-ink">{it.name}</span><Change value={it.change_pct} /></div>
                <div className="mt-2 heading-5 figure text-ink"><AnimatedNumber value={it.last_close} format={(v) => num(v)} /></div>
                <Meta className="mt-1 block">{fmtDate(it.date)} close · previous {num(it.previous_close)}</Meta>
              </div>
              <Sparkline data={it.series} height={64} up={it.change_pct >= 0} />
            </div>
          </div>
        ))}
      </div>

      <Reveal><IndexChart /></Reveal>

      <Reveal>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <Card title="Breadth" icon={Scales} className="xl:col-span-1"
                subtitle={breadth.data ? `${fmtDate(breadth.data.as_of)} · ${breadth.data.counted} of 30 curated stocks compared` : 'Across the 30 curated stocks'}>
            {breadth.loading && !breadth.data && <div className="space-y-3"><Skeleton className="h-3" /><Skeleton className="h-24" /><p className="caption-5 text-ink-muted">The first load fetches 30 stocks and can take up to a minute.</p></div>}
            {breadth.error && !breadth.data && <ErrorState message={breadth.error} />}
            {breadth.data && (
              <div className="space-y-6">
                <BreadthBar b={breadth.data} />
                <p className="caption-5 text-ink-muted">{breadth.data.universe}. Rule: {breadth.data.rule}.</p>
                {breadth.data.left_out.different_last_date.length > 0 && (
                  <p className="caption-5 text-ink-muted">Not compared (last close on another day): {breadth.data.left_out.different_last_date.map(shortSymbol).join(', ')}.</p>
                )}
              </div>
            )}
          </Card>
          <Card title="Curated stocks" subtitle="Click a column to sort; click a stock to analyse it" icon={ChartLineUp} className="xl:col-span-2">
            {breadth.data ? <CuratedTable rows={breadth.data.rows} /> : <Skeleton className="h-80" />}
          </Card>
        </div>
      </Reveal>

      {tech.data?.series?.length > 0 && (
        <Reveal>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <RsiChart data={tech.data.series} />
            <MacdChart data={tech.data.series} />
          </div>
        </Reveal>
      )}
      <Reveal><MoverNews breadth={breadth} /></Reveal>
    </div>
  )
}
