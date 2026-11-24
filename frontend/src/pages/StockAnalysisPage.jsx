// Stock Analysis page (task 12.3.3): run an analysis for one or more stocks, then read the
// overview, price chart, performance, indicators, fundamentals, news and risk for each stock.
// ?request=<id> opens an existing analysis.
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ChartLineUp, Play, TreeStructure } from '@phosphor-icons/react'
import { useCurrentAnalysis } from '../analysis/AnalysisContext'
import AgentStatus from '../components/AgentStatus'
import { MacdChart, PriceChart, RsiChart } from '../components/charts'
import { Explanation, MarketTiles } from '../components/MarketSummary'
import Fundamentals from '../components/Fundamentals'
import NewsList from '../components/NewsList'
import PortfolioCard from '../components/PortfolioCard'
import ReportCard from '../components/ReportCard'
import RiskCard from '../components/RiskCard'
import SymbolPicker from '../components/SymbolPicker'
import WatchButton from '../components/WatchButton'
import { Button, Card, CardSkeleton, Checkbox, EmptyState, ErrorState, Field, Input, PageHeader, Select, Tabs, TileSkeletons } from '../components/ui'
import { usePageTitle } from '../hooks/usePageTitle'

const PREFERENCES = [
  { value: 'conservative', label: 'Conservative: lowest volatility, at most 25% a stock' },
  { value: 'moderate', label: 'Moderate: best past return per unit of risk, at most 35%' },
  { value: 'aggressive', label: 'Aggressive: higher volatility allowed, at most 50%' },
]

export default function StockAnalysisPage() {
  usePageTitle('Stock analysis')
  const [params, setParams] = useSearchParams()
  const { requestId, status, result, indicators, error, busy, run, rerun, open, showIndicators } = useCurrentAnalysis()
  const [symbols, setSymbols] = useState(() => (params.get('symbol') ? [params.get('symbol')] : []))
  const [includeGdelt, setIncludeGdelt] = useState(false)
  const [amount, setAmount] = useState('100000')
  const [preference, setPreference] = useState('moderate')
  const [selected, setSelected] = useState(null)
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
    setParams({})
    run(symbols, includeGdelt, multi && amountValue > 0 ? { investmentAmount: amountValue, riskPreference: preference } : null)
  }

  const choose = (s) => {
    setSelected(s)
    showIndicators(s)
  }

  const key = selected || result?.symbols?.[0]
  const mr = key ? result?.market_research?.[key] : null
  const series = indicators?.series || []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Stock analysis"
        description="NSE symbols like RELIANCE or TCS, BSE codes like 500325. With two or more stocks and an amount, the Portfolio agent also suggests an illustrative allocation."
      />

      <Card>
        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
            <SymbolPicker value={symbols} onChange={setSymbols} label="Stocks" placeholder="Search RELIANCE, TCS or a company name"
                          hint="Up to 10 stocks. Press Enter to add a symbol that is not suggested." />
            <Button type="submit" disabled={busy} className="lg:mb-6">
              <Play size={16} weight="fill" aria-hidden="true" />
              {busy ? 'Analysing' : 'Run analysis'}
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
      </Card>

      {error && <ErrorState message={error} />}

      {!status && !error && (
        <EmptyState icon={ChartLineUp} title="Pick a stock to start">
          Five agents read the price history, recent news, the annual statements and the historical risk, then write a
          report you can download as a PDF. One stock takes about 30 to 60 seconds on a laptop CPU, two stocks about
          90 seconds.
        </EmptyState>
      )}

      {status && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="xl:col-span-1">
            <AgentStatus
              status={status}
              onRerun={rerun}
              footer={
                <Link to={`/app/agents${requestId ? `?request=${requestId}` : ''}`} className="mt-4 inline-flex items-center gap-2 caption-2 text-accent-ink underline-offset-4 hover:underline">
                  <TreeStructure size={16} aria-hidden="true" /> Open agent monitoring
                </Link>
              }
            />
          </div>
          <div className="space-y-6 xl:col-span-2">
            {busy && !result && (
              <>
                <TileSkeletons />
                <CardSkeleton rows={4} />
              </>
            )}
            {result && !mr && <ErrorState message={result.errors?.[0]?.message || 'No market data could be produced for this stock.'} />}
            {result?.symbols?.length > 1 && (
              <Tabs label="Stock shown in the details" value={key} onChange={choose}
                    tabs={result.symbols.map((s) => ({ value: s, label: s }))} />
            )}
            {mr && (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="heading-6 text-ink">{mr.company_name || key}</h2>
                  <p className="caption-2 text-ink-muted">{key}</p>
                </div>
                <WatchButton symbol={key} />
              </div>
            )}
            {mr && <MarketTiles mr={mr} />}
            {mr && <Explanation mr={mr} />}
          </div>
        </div>
      )}

      {result?.report && <ReportCard report={result.report} reportId={result.report_id} />}

      {mr && series.length > 0 && (
        <div className="space-y-6">
          <PriceChart data={series} />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <RsiChart data={series} />
            <MacdChart data={series} />
          </div>
        </div>
      )}
      {mr && !indicators && !busy && (
        <ErrorState message="The indicator charts could not be loaded because the price source is unavailable. The analysis above is still valid." />
      )}

      {result?.portfolio_optimization && <PortfolioCard portfolio={result.portfolio_optimization} />}
      {key && result?.stock_analysis?.[key] && <Fundamentals sa={result.stock_analysis[key]} />}
      {key && result?.risk_assessment?.[key] && <RiskCard risk={result.risk_assessment[key]} />}
      {key && result?.financial_news?.[key] && <NewsList news={result.financial_news[key]} />}
    </div>
  )
}
