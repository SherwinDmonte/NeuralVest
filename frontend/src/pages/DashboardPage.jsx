// Dashboard (task 12.3.2): market overview, search, watchlist, recently analysed stocks, latest
// news, the running analysis and recent reports. Every figure comes from the API as computed
// by the backend; the page does no arithmetic on market data.
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, FileText, Newspaper, Star, TreeStructure } from '@phosphor-icons/react'
import { useCurrentAnalysis } from '../analysis/AnalysisContext'
import { progressOf, JOB_TEXT } from '../components/AgentStatus'
import { MiniLine } from '../components/charts'
import SymbolPicker from '../components/SymbolPicker'
import { Button, Card, EmptyState, ErrorState, Meta, PageHeader, Skeleton, ToneBadge, Traced } from '../components/ui'
import { useWatchlist } from '../hooks/useWatchlist'
import { errorMessage, getIndicators, getNews, listReports } from '../services/api'
import { fmtDate, fmtDateTime, inr, num, safeUrl, shortSymbol } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

function useLoad(fn, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true }))
    fn()
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((err) => alive && setState({ data: null, error: errorMessage(err), loading: false }))
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}

function MarketOverview() {
  const { data, error, loading } = useLoad(() => getIndicators('^NSEI', '6mo'), [])
  return (
    <Card title="NIFTY 50" subtitle={data ? `End of day data as of ${fmtDate(data.data_as_of)}` : 'India’s main stock index'}
          className="lg:col-span-2">
      {loading && <Skeleton className="h-36 w-full" />}
      {error && <ErrorState message={`Index data is unavailable right now. ${error}`} />}
      {data && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-x-8 gap-y-3">
            <div>
              <div className="caption-5 text-ink-muted">Last close</div>
              <div className="figure-1 text-ink">{num(data.series?.[data.series.length - 1]?.close)}</div>
            </div>
            <div>
              <div className="caption-5 text-ink-muted">Trend</div>
              <div className="mt-1"><ToneBadge value={data.trend?.classification} /></div>
            </div>
            <div>
              <div className="caption-5 text-ink-muted">RSI 14</div>
              <div className="figure-2 text-ink">{num(data.latest?.rsi_14)}</div>
            </div>
          </div>
          <MiniLine data={data.series} name="NIFTY 50 close" />
          <Traced agent="market research" />
        </div>
      )}
    </Card>
  )
}

function CurrentAnalysis() {
  const { status, requestId } = useCurrentAnalysis()
  if (!status) {
    return (
      <Card title="Agent status">
        <EmptyState icon={TreeStructure} title="No analysis running"
                    action={<Button to="/app/analysis" size="sm" variant="secondary">Start an analysis</Button>}>
          Start one from Stock analysis and follow the five agents here.
        </EmptyState>
      </Card>
    )
  }
  const { done, total } = progressOf(status.agents)
  return (
    <Card title="Agent status" subtitle={status.symbols?.join(', ')}>
      <p className="body-6 text-ink-secondary">{JOB_TEXT[status.status] || status.status}</p>
      <div className="mt-4 h-1 overflow-hidden rounded bg-raised" aria-hidden="true">
        <div className="h-full origin-left rounded bg-accent transition-transform duration-500 ease-nv" style={{ transform: `scaleX(${done / total})` }} />
      </div>
      <Meta className="mt-2 block">{done} of {total} steps finished</Meta>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button to={`/app/analysis${requestId ? `?request=${requestId}` : ''}`} size="sm" variant="secondary">Open results</Button>
        <Button to={`/app/agents${requestId ? `?request=${requestId}` : ''}`} size="sm" variant="ghost">Agent monitoring</Button>
      </div>
    </Card>
  )
}

function Watchlist() {
  const { symbols, loading, error, toggle } = useWatchlist()
  return (
    <Card title="Watchlist" subtitle="Up to 20 stocks, saved to your account">
      {loading && <Skeleton className="h-24 w-full" />}
      {error && <ErrorState message={error} />}
      {!loading && !symbols.length && (
        <EmptyState icon={Star} title="Nothing watched yet">
          Use Add to watchlist on a stock&apos;s analysis, and its latest news appears on this page.
        </EmptyState>
      )}
      {symbols.length > 0 && (
        <ul className="divide-y divide-line">
          {symbols.map((s) => (
            <li key={s} className="flex items-center justify-between gap-3 py-2">
              <Link to={`/app/analysis?symbol=${encodeURIComponent(s)}`} className="figure body-6 text-ink transition-colors duration-300 ease-nv hover:text-accent-ink">{s}</Link>
              <span className="flex gap-1">
                <Button to={`/app/news?symbol=${encodeURIComponent(s)}`} size="xs" variant="ghost">News</Button>
                <Button size="xs" variant="ghost" onClick={() => toggle(s)} aria-label={`Remove ${s} from the watchlist`}>Remove</Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function LatestNews({ symbols }) {
  const key = symbols.slice(0, 3).join(',')
  const { data, loading } = useLoad(
    () => Promise.all(symbols.slice(0, 3).map((s) => getNews(s, { page_size: 3 }).then((r) => r.items).catch(() => []))).then((lists) =>
      lists.flat().sort((a, b) => (b.publication_date || '').localeCompare(a.publication_date || '')).slice(0, 6)),
    [key],
  )
  return (
    <Card title="Latest news" subtitle={symbols.length ? `Stored articles for ${symbols.slice(0, 3).map(shortSymbol).join(', ')}` : 'From your watchlist'}>
      {!symbols.length && <EmptyState icon={Newspaper}>Watch a stock or run an analysis to collect its news.</EmptyState>}
      {symbols.length > 0 && loading && (
        <div className="space-y-3"><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-2/3" /><Skeleton className="h-4 w-full" /></div>
      )}
      {symbols.length > 0 && !loading && !data?.length && (
        <EmptyState icon={Newspaper}>No stored articles yet. Analysing a stock collects its news from the last 14 days.</EmptyState>
      )}
      {data?.length > 0 && (
        <ul className="divide-y divide-line">
          {data.map((a) => {
            const href = safeUrl(a.article_url)
            return (
              <li key={a.url_hash} className="py-3 first:pt-0 last:pb-0">
                {href ? (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="body-5 text-ink transition-colors duration-300 ease-nv hover:text-accent-ink">{a.headline}</a>
                ) : <span className="body-5 text-ink">{a.headline}</span>}
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Meta>{shortSymbol(a.symbol)}</Meta>
                  <Meta>{a.publisher}</Meta>
                  <Meta>{fmtDate(a.publication_date)}</Meta>
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

export default function DashboardPage() {
  usePageTitle('Dashboard')
  const navigate = useNavigate()
  const { symbols: watched } = useWatchlist()
  const reports = useLoad(() => listReports({ page_size: 8 }), [])
  const recent = useMemo(() => [...new Set((reports.data?.items || []).flatMap((r) => r.symbols))].slice(0, 8), [reports.data])
  const newsSymbols = watched.length ? watched : recent

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="Your watchlist, recent analyses and the latest stored news. Market data is end of day, never real time." />

      <Card>
        <SymbolPicker value={[]} single label="Find a stock" placeholder="Search a symbol or company name"
                      onChange={(v) => v[0] && navigate(`/app/analysis?symbol=${encodeURIComponent(v[0])}`)} />
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <MarketOverview />
        <CurrentAnalysis />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <LatestNews symbols={newsSymbols} />
          <Card title="Recent reports" actions={<Button to="/app/reports" size="xs" variant="ghost">All reports <ArrowRight size={14} aria-hidden="true" /></Button>}>
            {reports.loading && <div className="space-y-3"><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-2/3" /></div>}
            {reports.error && <ErrorState message={reports.error} />}
            {reports.data && !reports.data.items.length && (
              <EmptyState icon={FileText} title="No reports yet" action={<Button to="/app/analysis" size="sm">Run your first analysis</Button>}>
                Each analysis becomes a report you can reopen, compare and download as a PDF.
              </EmptyState>
            )}
            {reports.data?.items?.length > 0 && (
              <ul className="divide-y divide-line">
                {reports.data.items.slice(0, 5).map((r) => (
                  <li key={r.report_id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <Link to={`/app/reports/${r.report_id}`} className="body-5 text-ink transition-colors duration-300 ease-nv hover:text-accent-ink">
                        {r.symbols.join(', ')}
                      </Link>
                      <div className="mt-1 flex flex-wrap gap-x-3">
                        <Meta>{fmtDateTime(r.requested_at)}</Meta>
                        {r.investment_amount && <Meta>portfolio {inr(r.investment_amount, 0)}</Meta>}
                      </div>
                    </div>
                    <ToneBadge value={r.status} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
        <div className="space-y-6">
          <Watchlist />
          <Card title="Recently analysed">
            {recent.length ? (
              <ul className="flex flex-wrap gap-2">
                {recent.map((s) => (
                  <li key={s}><Button to={`/app/analysis?symbol=${encodeURIComponent(s)}`} size="xs" variant="secondary">{s}</Button></li>
                ))}
              </ul>
            ) : (
              <p className="body-6 text-ink-muted">Stocks from your reports appear here.</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
