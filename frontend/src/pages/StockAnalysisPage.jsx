// Stock analysis (Phase 12, redesigned in 12B): run the agents on one or more stocks, then read
// each stock through tabs (overview, chart, technicals, fundamentals, statements, news, risk,
// portfolio, report). ?request=<id> opens an existing analysis; ?symbol= prefills the picker.
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ChartBar,
  ChartLineUp,
  ChartPieSlice,
  FileText,
  Gauge,
  Lightning,
  Newspaper,
  Play,
  Receipt,
  ShieldWarning,
  Sparkle,
  TreeStructure,
  Waveform,
} from '@phosphor-icons/react'
import { useCurrentAnalysis } from '../analysis/AnalysisContext'
import AgentStatus from '../components/AgentStatus'
import { MacdChart, PriceChart, RsiChart, VolumeChart } from '../components/charts'
import { Explanation, MarketTiles } from '../components/MarketSummary'
import Fundamentals from '../components/Fundamentals'
import NewsList from '../components/NewsList'
import PortfolioCard from '../components/PortfolioCard'
import ReportCard from '../components/ReportCard'
import RiskCard from '../components/RiskCard'
import Statements from '../components/Statements'
import SymbolPicker from '../components/SymbolPicker'
import WatchButton from '../components/WatchButton'
import { AnimatedTabs, Reveal } from '../components/motion'
import { Button, Card, CardSkeleton, Change, Checkbox, EmptyState, ErrorState, Field, Input, Meta, Select, Tabs, TileSkeletons } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { getIndicators } from '../services/api'
import { fmtDate, inr, shortSymbol } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

const PREFERENCES = [
  { value: 'conservative', label: 'Conservative: lowest volatility, at most 25% a stock' },
  { value: 'moderate', label: 'Moderate: best past return per unit of risk, at most 35%' },
  { value: 'aggressive', label: 'Aggressive: higher volatility allowed, at most 50%' },
]

function exchangeOf(symbol) {
  if (symbol?.endsWith('.NS')) return 'NSE'
  if (symbol?.endsWith('.BO')) return 'BSE'
  return 'Index'
}

function StockHeader({ symbol, mr, sa }) {
  return (
    <section className="relative overflow-hidden rounded-3xl border border-line bg-surface p-6 shadow-card">
      <div className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-accent/20 blur-3xl" aria-hidden="true" />
      <div className="relative flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-lg border border-line bg-raised px-2 py-0.5 figure caption-3 text-ink">{shortSymbol(symbol)}</span>
            <span className="rounded-lg bg-brand-button px-2 py-0.5 caption-3 text-white">{exchangeOf(symbol)}</span>
            {sa?.sector && <Meta>{sa.sector}{sa.industry ? ` · ${sa.industry}` : ''}</Meta>}
          </div>
          <h2 className="mt-3 heading-5 text-ink sm:heading-4">{mr?.company_name || symbol}</h2>
        </div>
        <div className="flex flex-wrap items-end gap-6">
          <div>
            <p className="caption-5 text-ink-muted">Last close · {fmtDate(mr?.last_close_date)}</p>
            <p className="heading-5 figure text-ink">{inr(mr?.last_close)}</p>
          </div>
          <div>
            <p className="caption-5 text-ink-muted">1 year change</p>
            <Change value={mr?.period_return_pct} className="mt-2" />
          </div>
          <WatchButton symbol={symbol} />
        </div>
      </div>
      {mr?.last_bar_may_be_incomplete && <p className="relative mt-3 caption-5 text-warning">The last bar may be incomplete: the market was open when it was fetched.</p>}
    </section>
  )
}

function ChartTab({ symbol }) {
  const [period, setPeriod] = useState('1y')
  const { data, error, loading } = useApi(() => getIndicators(symbol, period), [symbol, period], { key: `ind-${symbol}-${period}`, ttl: 10 * 60 * 1000 })
  const series = data?.series || []
  const ranges = <AnimatedTabs size="sm" label="Date range" value={period} onChange={setPeriod} tabs={[{ value: '6mo', label: '6M' }, { value: '1y', label: '1Y' }]} />
  if (loading && !data) return <CardSkeleton rows={8} />
  if (error && !data) return <ErrorState message={`The price chart is unavailable. ${error}`} />
  return (
    <div className="space-y-6">
      <PriceChart data={series} actions={ranges} />
      <VolumeChart data={series} />
      <Meta>Prices as of {fmtDate(data?.data_as_of)} · {data?.source}</Meta>
    </div>
  )
}

function TechnicalsTab({ symbol }) {
  const { data, error, loading } = useApi(() => getIndicators(symbol, '1y'), [symbol], { key: `ind-${symbol}-1y`, ttl: 10 * 60 * 1000 })
  if (loading && !data) return <CardSkeleton rows={6} />
  if (error && !data) return <ErrorState message={error} />
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <RsiChart data={data.series} />
      <MacdChart data={data.series} />
    </div>
  )
}

export default function StockAnalysisPage() {
  usePageTitle('Stock analysis')
  const [params, setParams] = useSearchParams()
  const { requestId, status, result, error, busy, run, rerun, open } = useCurrentAnalysis()
  const [symbols, setSymbols] = useState(() => (params.get('symbol') ? [params.get('symbol')] : []))
  const [includeGdelt, setIncludeGdelt] = useState(false)
  const [amount, setAmount] = useState('100000')
  const [preference, setPreference] = useState('moderate')
  const [selected, setSelected] = useState(null)
  const [tab, setTab] = useState('overview')
  const [formError, setFormError] = useState(null)

  const requested = params.get('request')
  useEffect(() => {
    if (requested && requested !== requestId) open(requested)
  }, [requested, requestId, open])

  const multi = symbols.length >= 2
  const amountValue = Number(amount)

  const submit = (e) => {
    e.preventDefault()
    if (!symbols.length) return setFormError('Add at least one stock')
    if (multi && amount !== '' && !(amountValue > 0)) return setFormError('Enter a positive amount, or leave it empty to skip the portfolio')
    setFormError(null)
    setSelected(null)
    setTab('overview')
    setParams({})
    run(symbols, includeGdelt, multi && amountValue > 0 ? { investmentAmount: amountValue, riskPreference: preference } : null)
  }

  const key = selected || result?.symbols?.[0]
  const mr = key ? result?.market_research?.[key] : null
  const sa = key ? result?.stock_analysis?.[key] : null
  const tabs = [
    { value: 'overview', label: 'Overview', icon: Gauge },
    { value: 'chart', label: 'Chart', icon: ChartLineUp },
    { value: 'technicals', label: 'Technicals', icon: Waveform },
    { value: 'fundamentals', label: 'Fundamentals', icon: ChartBar },
    { value: 'statements', label: 'Statements', icon: Receipt },
    { value: 'news', label: 'News', icon: Newspaper },
    { value: 'risk', label: 'Risk', icon: ShieldWarning },
    ...(result?.portfolio_optimization ? [{ value: 'portfolio', label: 'Portfolio', icon: ChartPieSlice }] : []),
    { value: 'report', label: 'AI report', icon: Sparkle },
  ]

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl border border-line bg-surface/70 p-6 shadow-float">
        <div className="pointer-events-none absolute inset-0 grid-lines opacity-50 [mask-image:radial-gradient(ellipse_at_top_left,black,transparent_70%)]" aria-hidden="true" />
        <div className="relative">
          <h1 className="heading-5 text-ink">Research any NSE or BSE stock with five agents</h1>
          <p className="mt-2 max-w-2xl body-6 text-ink-secondary">Symbols like RELIANCE or TCS, BSE codes like 500325. With two or more stocks and an amount, the Portfolio agent adds an illustrative allocation.</p>
          <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
            <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
              <SymbolPicker value={symbols} onChange={setSymbols} label="Stocks" placeholder="Search RELIANCE, TCS or a company name"
                            hint="Up to 10 stocks. Press Enter to add a symbol that is not suggested." />
              <Button type="submit" size="lg" disabled={busy} className="lg:mb-6">
                {busy ? <Lightning size={18} weight="fill" className="motion-safe:animate-pulse" aria-hidden="true" /> : <Play size={18} weight="fill" aria-hidden="true" />}
                {busy ? 'Agents are working' : 'Run analysis'}
              </Button>
            </div>
            {multi && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Investment amount in ₹ for an illustrative portfolio" hint="Leave empty to analyse the stocks only">
                  {(p) => <Input {...p} type="number" min="1" step="1000" value={amount} onChange={(e) => setAmount(e.target.value)} />}
                </Field>
                <Field label="Risk preference">
                  {(p) => (
                    <Select {...p} value={preference} onChange={(e) => setPreference(e.target.value)}>
                      {PREFERENCES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </Select>
                  )}
                </Field>
              </div>
            )}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Checkbox label="Also search GDELT news (slower, often rate limited)" checked={includeGdelt} onChange={(e) => setIncludeGdelt(e.target.checked)} />
              {formError && <p role="alert" className="caption-5 text-critical">{formError}</p>}
            </div>
          </form>
        </div>
      </section>

      {error && <ErrorState message={error} />}

      {!status && !error && (
        <EmptyState icon={ChartLineUp} title="Pick a stock to start">
          Five agents read the price history, recent news, the annual statements and the historical risk, then write a
          report you can download as a PDF. One stock takes about 30 to 60 seconds on a laptop CPU, two about 90 seconds.
        </EmptyState>
      )}

      {status && !result && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <AgentStatus status={status} onRerun={rerun}
                       footer={<Link to={`/app/agents${requestId ? `?request=${requestId}` : ''}`} className="mt-4 inline-flex items-center gap-2 caption-2 text-accent-ink hover:underline"><TreeStructure size={16} aria-hidden="true" /> Watch the agent network</Link>} />
          <div className="space-y-6 xl:col-span-2"><TileSkeletons /><CardSkeleton rows={4} /></div>
        </div>
      )}

      {result && (
        <>
          {result.symbols?.length > 1 && (
            <Tabs label="Stock shown" value={key} onChange={(s) => setSelected(s)} tabs={result.symbols.map((s) => ({ value: s, label: shortSymbol(s) }))} />
          )}
          {!mr && <ErrorState message={result.errors?.[0]?.message || 'No market data could be produced for this stock.'} />}
          {mr && <StockHeader symbol={key} mr={mr} sa={sa} />}
          <div className="sticky top-16 z-20 -mx-1 overflow-x-auto px-1 py-2">
            <AnimatedTabs label="Sections" tabs={tabs} value={tab} onChange={setTab} />
          </div>
          <Reveal key={`${key}-${tab}`}>
            {tab === 'overview' && (
              <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
                <div className="space-y-6 xl:col-span-2">
                  {mr && <MarketTiles mr={mr} />}
                  {mr && <Explanation mr={mr} />}
                </div>
                <AgentStatus status={status} onRerun={rerun}
                             footer={<Link to={`/app/agents?request=${requestId}`} className="mt-4 inline-flex items-center gap-2 caption-2 text-accent-ink hover:underline"><TreeStructure size={16} aria-hidden="true" /> Open the agent network</Link>} />
              </div>
            )}
            {tab === 'chart' && key && <ChartTab symbol={key} />}
            {tab === 'technicals' && key && <TechnicalsTab symbol={key} />}
            {tab === 'fundamentals' && (sa ? <Fundamentals sa={sa} /> : <EmptyState title="No fundamentals">The Stock Analysis agent has no result for this stock.</EmptyState>)}
            {tab === 'statements' && key && <Statements symbol={key} />}
            {tab === 'news' && (result.financial_news?.[key] ? <NewsList news={result.financial_news[key]} /> : <EmptyState icon={Newspaper} title="No news result" />)}
            {tab === 'risk' && (result.risk_assessment?.[key] ? <RiskCard risk={result.risk_assessment[key]} /> : <EmptyState icon={ShieldWarning} title="No risk result" />)}
            {tab === 'portfolio' && result.portfolio_optimization && <PortfolioCard portfolio={result.portfolio_optimization} />}
            {tab === 'report' && (result.report ? <ReportCard report={result.report} reportId={result.report_id} /> : (
              <Card><EmptyState icon={FileText} title="The report is not ready">It appears when the analysis finishes.</EmptyState></Card>
            ))}
          </Reveal>
        </>
      )}
    </div>
  )
}
