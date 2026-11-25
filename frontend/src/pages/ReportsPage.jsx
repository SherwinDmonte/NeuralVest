// Reports (task 12.3.8): your reports (paginated, filters), one report with its agent outputs,
// two reports compared side by side, and PDF download.
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, CaretLeft, CaretRight, FileText, Scales } from '@phosphor-icons/react'
import Fundamentals from '../components/Fundamentals'
import { Explanation, MarketTiles } from '../components/MarketSummary'
import NewsList from '../components/NewsList'
import PortfolioCard from '../components/PortfolioCard'
import ReportCard, { PdfButton } from '../components/ReportCard'
import RiskCard from '../components/RiskCard'
import { Button, Card, CardSkeleton, EmptyState, ErrorState, Meta, PageHeader, Select, Tabs, ToneBadge, table } from '../components/ui'
import { errorMessage, getReport, listReports } from '../services/api'
import { useApi } from '../hooks/useApi'
import { Modal } from '../components/motion'
import { fmtDate, fmtDateTime, inr, num, pct } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

const PAGE_SIZE = 10
const STATUSES = ['', 'completed', 'partial', 'failed', 'interrupted', 'running', 'queued']

// ------------------------------------------------------------------ list
function ReportPreview({ id }) {
  const { data, error, loading } = useApi(() => getReport(id), [id], { key: `report-${id}`, ttl: 5 * 60 * 1000, enabled: Boolean(id) })
  if (!id) {
    return <EmptyState icon={FileText} title="Select a report">Its key observations, checks and agents appear here.</EmptyState>
  }
  if (loading && !data) return <CardSkeleton rows={6} />
  if (error) return <ErrorState message={error} />
  if (!data) return null
  const r = data.report
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="title-2 text-ink">{data.symbols.join(', ')}</p>
          <Meta>{fmtDateTime(data.requested_at)}{data.completed_at ? ` · finished ${fmtDateTime(data.completed_at)}` : ''}</Meta>
        </div>
        <ToneBadge value={data.status} />
      </div>
      {r ? (
        <>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-lg border border-line bg-raised px-2 py-0.5 caption-4 text-ink-secondary">{r.traceability?.ok ? `${r.traceability.numbers_checked} numbers traced` : 'Some numbers not traced'}</span>
            <span className="rounded-lg border border-line bg-raised px-2 py-0.5 caption-4 text-ink-secondary">{r.execution?.validation_issue_count ?? 0} validation issues</span>
            {r.request?.investment_amount && <span className="rounded-lg border border-line bg-raised px-2 py-0.5 caption-4 text-ink-secondary">Portfolio {inr(r.request.investment_amount, 0)}</span>}
          </div>
          <div>
            <p className="mb-2 caption-3 text-ink-muted">Key observations</p>
            <ul className="space-y-2">
              {r.key_observations?.items?.map((o) => (
                <li key={o} className="flex gap-3 body-6 text-ink"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden="true" />{o}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="mb-2 caption-3 text-ink-muted">Agents</p>
            <ul className="grid grid-cols-2 gap-2">
              {Object.entries(r.execution?.agent_status || {}).filter(([k]) => !['validate_input', 'output_validation'].includes(k)).map(([k, v]) => (
                <li key={k} className="flex items-center justify-between gap-2 rounded-lg border border-line px-2 py-1 caption-5 text-ink-secondary">{k.replaceAll('_', ' ')}<ToneBadge value={v} /></li>
              ))}
            </ul>
          </div>
        </>
      ) : <p className="body-6 text-ink-secondary">This analysis is {data.status}; its report appears when it finishes.</p>}
      <div className="flex flex-wrap gap-2 border-t border-line pt-4">
        <Button size="sm" to={`/app/reports/${id}`}>Open the report</Button>
        <Button size="sm" variant="secondary" to={`/app/agents?request=${data.request_id}`}>Agents</Button>
        {r && <PdfButton reportId={id} />}
      </div>
    </div>
  )
}

export function ReportsPage() {
  usePageTitle('Reports')
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const [picked, setPicked] = useState([])
  const [previewId, setPreviewId] = useState(null)
  const [mobilePreview, setMobilePreview] = useState(false)

  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true }))
    listReports({ page, page_size: PAGE_SIZE, ...(status ? { status } : {}) })
      .then((data) => {
        if (!alive) return
        setState({ data, error: null, loading: false })
        setPreviewId((id) => id || data.items[0]?.report_id || null)
      })
      .catch((err) => alive && setState({ data: null, error: errorMessage(err), loading: false }))
    return () => { alive = false }
  }, [page, status])

  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p.slice(-1), id]))
  const pages = state.data ? Math.max(1, Math.ceil(state.data.total / PAGE_SIZE)) : 1
  const select = (id) => {
    setPreviewId(id)
    if (window.matchMedia('(max-width: 1279px)').matches) setMobilePreview(true)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Your reports"
        description="Every analysis you ran while logged in. Preview one, open it, compare two, or download a PDF."
        actions={
          <>
            <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} aria-label="Filter by status" className="w-auto">
              {STATUSES.map((s) => <option key={s} value={s}>{s ? s.charAt(0).toUpperCase() + s.slice(1) : 'All statuses'}</option>)}
            </Select>
            <Button variant="secondary" size="sm" disabled={picked.length !== 2}
                    onClick={() => navigate(`/app/reports/compare?a=${picked[0]}&b=${picked[1]}`)}>
              <Scales size={16} aria-hidden="true" /> Compare {picked.length}/2
            </Button>
          </>
        }
      />
      {state.error && <ErrorState message={state.error} />}
      {state.loading && !state.data && <CardSkeleton rows={6} />}
      {state.data && (
        state.data.items.length ? (
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_1fr]">
            <Card bodyClass="-m-2">
              <ul className="divide-y divide-line">
                {state.data.items.map((r) => (
                  <li key={r.report_id}
                      className={`flex flex-wrap items-center gap-4 rounded-xl px-3 py-4 transition-colors duration-300 ease-nv ${previewId === r.report_id ? 'bg-raised' : 'hover:bg-raised/50'}`}>
                    <input type="checkbox" className="h-4 w-4 accent-[var(--nv-accent)]" checked={picked.includes(r.report_id)}
                           onChange={() => toggle(r.report_id)} disabled={!r.report_ready}
                           aria-label={`Select the report for ${r.symbols.join(', ')} to compare`} />
                    <button type="button" onClick={() => select(r.report_id)} className="min-w-0 flex-1 text-left" aria-pressed={previewId === r.report_id}>
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="body-5 text-ink">{r.symbols.join(', ')}</span>
                        <span className="rounded-md border border-line px-1.5 caption-5 text-ink-muted">{r.request_type === 'portfolio' || r.investment_amount ? 'Portfolio' : 'Analysis'}</span>
                      </span>
                      <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                        <Meta>{fmtDateTime(r.requested_at)}</Meta>
                        {r.investment_amount && <Meta>{inr(r.investment_amount, 0)}</Meta>}
                        {r.retry_of && <Meta>re-run</Meta>}
                      </span>
                      {r.key_observations?.[0] && <span className="mt-2 line-clamp-2 block caption-2 text-ink-secondary">{r.key_observations[0]}</span>}
                    </button>
                    <ToneBadge value={r.status} />
                  </li>
                ))}
              </ul>
              {pages > 1 && (
                <nav aria-label="Pages" className="mt-2 flex items-center justify-between gap-3 border-t border-line px-3 pt-4">
                  <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><CaretLeft size={16} aria-hidden="true" /> Newer</Button>
                  <Meta>page {page} of {pages} · {state.data.total} reports</Meta>
                  <Button size="sm" variant="secondary" disabled={!state.data.has_next} onClick={() => setPage((p) => p + 1)}>Older <CaretRight size={16} aria-hidden="true" /></Button>
                </nav>
              )}
            </Card>
            <div className="hidden xl:block">
              <div className="sticky top-24 rounded-2xl border border-line glass p-6 shadow-float">
                <span className="pointer-events-none absolute inset-x-6 top-0 h-px bg-brand" aria-hidden="true" />
                <ReportPreview id={previewId} />
              </div>
            </div>
            <Modal open={mobilePreview} onClose={() => setMobilePreview(false)} title="Report preview">
              <div className="max-h-[70vh] overflow-y-auto p-4"><ReportPreview id={previewId} /></div>
            </Modal>
          </div>
        ) : (
          <EmptyState icon={FileText} title={status ? `No ${status} reports` : 'No reports yet'}
                      action={!status && <Button to="/app/analysis" size="sm">Run your first analysis</Button>}>
            {status ? 'Try another filter.' : 'Analyses you run while logged in are saved here. Reports created before you had an account can be assigned to it with scripts/assign_reports.py (see the setup guide).'}
          </EmptyState>
        )
      )}
    </div>
  )
}

// ------------------------------------------------------------------ one report
function useReport(id) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  useEffect(() => {
    if (!id) return undefined
    let alive = true
    setState({ data: null, error: null, loading: true })
    getReport(id)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((err) => alive && setState({ data: null, error: errorMessage(err), loading: false }))
    return () => { alive = false }
  }, [id])
  return state
}

function AgentOutputs({ data }) {
  const agents = ['market_research', 'financial_news', 'stock_analysis', 'risk_assessment', 'portfolio_optimization']
  return (
    <Card title="Agent outputs" subtitle="The stored result of each agent, exactly as saved. Every number in the report comes from these.">
      <div className="space-y-2">
        {agents.filter((a) => data[a]).map((a) => (
          <details key={a} className="group rounded-xl border border-line">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-4 py-3 body-5 text-ink transition-colors duration-300 ease-nv hover:bg-raised/50">
              {a.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase())}
              <Meta>{a === 'portfolio_optimization' ? 'request' : `${Object.keys(data[a]).length} result(s)`}</Meta>
            </summary>
            <pre className="max-h-96 overflow-auto border-t border-line p-4 figure caption-5 text-ink-secondary">{JSON.stringify(data[a], null, 2)}</pre>
          </details>
        ))}
      </div>
    </Card>
  )
}

export function ReportViewPage() {
  const { reportId } = useParams()
  const { data, error, loading } = useReport(reportId)
  const [selected, setSelected] = useState(null)
  usePageTitle(data ? `Report ${data.symbols.join(', ')}` : 'Report')
  const key = selected || data?.symbols?.[0]
  const mr = key ? data?.market_research?.[key] : null

  return (
    <div className="space-y-6">
      <Link to="/app/reports" className="inline-flex items-center gap-2 caption-2 text-ink-secondary transition-colors duration-300 ease-nv hover:text-ink">
        <ArrowLeft size={16} aria-hidden="true" /> All reports
      </Link>
      {loading && <CardSkeleton rows={6} />}
      {error && <ErrorState message={error} />}
      {data && (
        <>
          <PageHeader
            title={data.symbols.join(', ')}
            description={`Requested ${fmtDateTime(data.requested_at)}${data.completed_at ? ` · finished ${fmtDateTime(data.completed_at)}` : ''}`}
            actions={
              <>
                <ToneBadge value={data.status} />
                <Button to={`/app/agents?request=${data.request_id}`} variant="ghost" size="sm">Agent monitoring</Button>
                {data.report && <PdfButton reportId={reportId} />}
              </>
            }
          />
          {!data.report && <EmptyState title="The report is not ready">This analysis is {data.status}. Its report appears when it finishes.</EmptyState>}
          {data.report && <ReportCard report={data.report} />}
          {data.symbols.length > 1 && (
            <Tabs label="Stock shown in the details" value={key} onChange={setSelected} tabs={data.symbols.map((s) => ({ value: s, label: s }))} />
          )}
          {mr && <MarketTiles mr={mr} />}
          {mr && <Explanation mr={mr} />}
          {data.portfolio_optimization && <PortfolioCard portfolio={data.portfolio_optimization} />}
          {key && data.stock_analysis?.[key] && <Fundamentals sa={data.stock_analysis[key]} />}
          {key && data.risk_assessment?.[key] && <RiskCard risk={data.risk_assessment[key]} />}
          {key && data.financial_news?.[key] && <NewsList news={data.financial_news[key]} />}
          <AgentOutputs data={data} />
        </>
      )}
    </div>
  )
}

// ------------------------------------------------------------------ compare two
const ROWS = [
  ['Last close', (d, s) => inr(d.market_research?.[s]?.last_close)],
  ['Close date', (d, s) => fmtDate(d.market_research?.[s]?.last_close_date)],
  ['1 year price change', (d, s) => pct(d.market_research?.[s]?.period_return_pct)],
  ['vs NIFTY 50, points', (d, s) => num(d.market_research?.[s]?.benchmark_comparison?.relative_pct)],
  ['Trend', (d, s) => d.market_research?.[s]?.trend?.classification],
  ['RSI 14', (d, s) => num(d.market_research?.[s]?.indicators?.rsi_14)],
  ['Fundamentals overall', (d, s) => d.stock_analysis?.[s]?.overall?.replaceAll('_', ' ')],
  ['P/E', (d, s) => num(d.stock_analysis?.[s]?.metrics?.pe?.value)],
  ['Return on equity, %', (d, s) => num(d.stock_analysis?.[s]?.metrics?.roe_pct?.value)],
  ['Risk class', (d, s) => d.risk_assessment?.[s]?.risk_classification?.replaceAll('_', ' ')],
  ['Volatility, %', (d, s) => num(d.risk_assessment?.[s]?.annualized_volatility_pct)],
  ['Beta', (d, s) => num(d.risk_assessment?.[s]?.beta?.value)],
  ['Max drawdown, %', (d, s) => num(d.risk_assessment?.[s]?.max_drawdown?.max_drawdown_pct)],
  ['Sharpe ratio', (d, s) => num(d.risk_assessment?.[s]?.sharpe?.value)],
  ['News sentiment', (d, s) => d.financial_news?.[s]?.overall_sentiment?.replaceAll('_', ' ')],
]

export function ReportComparePage() {
  usePageTitle('Compare reports')
  const [params] = useSearchParams()
  const a = useReport(params.get('a'))
  const b = useReport(params.get('b'))
  const symbols = useMemo(() => [...new Set([...(a.data?.symbols || []), ...(b.data?.symbols || [])])], [a.data, b.data])
  const [selected, setSelected] = useState(null)
  const key = selected && symbols.includes(selected) ? selected : symbols[0]
  const both = a.data && b.data

  return (
    <div className="space-y-6">
      <Link to="/app/reports" className="inline-flex items-center gap-2 caption-2 text-ink-secondary transition-colors duration-300 ease-nv hover:text-ink">
        <ArrowLeft size={16} aria-hidden="true" /> All reports
      </Link>
      <PageHeader title="Two reports side by side" description="The same measures, as each report stored them on its own date." />
      {(a.loading || b.loading) && <CardSkeleton rows={8} />}
      {a.error && <ErrorState message={`First report: ${a.error}`} />}
      {b.error && <ErrorState message={`Second report: ${b.error}`} />}
      {both && (
        <>
          {symbols.length > 1 && <Tabs label="Stock" value={key} onChange={setSelected} tabs={symbols.map((s) => ({ value: s, label: s }))} />}
          <Card>
            <div className={table.wrap}>
              <table className={table.table}>
                <caption className="sr-only">Comparison for {key}</caption>
                <thead className={table.thead}>
                  <tr>
                    <th className={table.th}>{key}</th>
                    <th className={table.thR}><Link to={`/app/reports/${params.get('a')}`} className="hover:text-ink">{fmtDateTime(a.data.requested_at)}</Link></th>
                    <th className={table.thR}><Link to={`/app/reports/${params.get('b')}`} className="hover:text-ink">{fmtDateTime(b.data.requested_at)}</Link></th>
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map(([label, get]) => (
                    <tr key={label} className={table.tr}>
                      <td className={table.td}>{label}</td>
                      <td className={table.tdR}>{a.data.symbols.includes(key) ? get(a.data, key) || 'n/a' : 'not in this report'}</td>
                      <td className={table.tdR}>{b.data.symbols.includes(key) ? get(b.data, key) || 'n/a' : 'not in this report'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {[a.data, b.data].map((d, i) => (
              <Card key={i} title={`Key observations, ${fmtDateTime(d.requested_at)}`} subtitle={d.symbols.join(', ')}>
                <ul className="list-disc space-y-1 pl-5 body-6 text-ink">
                  {(d.report?.key_observations?.items || ['No report yet']).map((o) => <li key={o}>{o}</li>)}
                </ul>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
