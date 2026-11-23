// MVP dashboard (Phase 6, extended each phase): analyse one stock, or several stocks with an
// investment amount for an illustrative portfolio (Phase 9). Detail cards show one stock at a time.
import { useState } from 'react'
import { Play, Search } from 'lucide-react'
import AgentStatus from '../components/AgentStatus'
import { MacdChart, PriceChart, RsiChart } from '../components/charts'
import { Explanation, MarketTiles } from '../components/MarketSummary'
import Fundamentals from '../components/Fundamentals'
import PortfolioCard from '../components/PortfolioCard'
import RiskCard from '../components/RiskCard'
import NewsList from '../components/NewsList'
import { Card, EmptyState, ErrorState, Loading } from '../components/ui'
import { useAnalysis } from '../hooks/useAnalysis'

const SUGGESTIONS = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
const PREFERENCES = [
  { value: 'conservative', label: 'Conservative (lowest volatility, max 25% per stock)' },
  { value: 'moderate', label: 'Moderate (best past return per risk, max 35%)' },
  { value: 'aggressive', label: 'Aggressive (higher volatility allowed, max 50%)' },
]

const parseSymbols = (text) => [...new Set(text.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean))]

export default function DashboardPage() {
  const [symbol, setSymbol] = useState('RELIANCE')
  const [includeGdelt, setIncludeGdelt] = useState(false)
  const [amount, setAmount] = useState('100000')
  const [preference, setPreference] = useState('moderate')
  const [selected, setSelected] = useState(null)
  const { status, result, indicators, error, busy, run, rerun, showIndicators } = useAnalysis()
  const symbols = parseSymbols(symbol)
  const multi = symbols.length >= 2
  const amountValue = Number(amount)
  const amountError = multi && amount !== '' && !(amountValue > 0) ? 'Enter a positive amount' : null

  const submit = (e) => {
    e.preventDefault()
    if (!symbols.length || amountError) return
    setSelected(null)
    const portfolio = multi && amountValue > 0 ? { investmentAmount: amountValue, riskPreference: preference } : null
    run(symbols.slice(0, 10), includeGdelt, portfolio)
  }

  // A suggestion is ADDED to the list (click one stock, clear the field to start again).
  const addSuggestion = (s) => {
    if (!symbols.includes(s)) setSymbol([...symbols, s].join(', '))
  }

  const choose = (s) => {
    setSelected(s)
    showIndicators(s)
  }

  const key = selected || result?.symbols?.[0]
  const mr = key ? result.market_research?.[key] : null
  const news = key ? result.financial_news?.[key] : null
  const sa = key ? result.stock_analysis?.[key] : null
  const risk = key ? result.risk_assessment?.[key] : null
  const portfolio = result?.portfolio_optimization
  const series = indicators?.series || []

  return (
    <div className="space-y-5">
      <Card title="Analyse Indian stocks" subtitle="NSE symbols like RELIANCE or TCS; BSE codes like 500325. Separate several stocks with commas.">
        <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1">
            <span className="mb-1 block text-xs text-ink-muted">Symbol(s)</span>
            <div className="flex items-center gap-2 rounded-lg border border-line bg-page px-3 py-2 focus-within:border-accent">
              <Search className="h-4 w-4 text-ink-muted" aria-hidden="true" />
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="e.g. RELIANCE or RELIANCE, TCS, INFY"
                maxLength={200}
                className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted"
                aria-label="Stock symbols"
              />
            </div>
          </label>
          <label className="flex items-center gap-2 text-xs text-ink-secondary sm:pb-2.5">
            <input type="checkbox" checked={includeGdelt} onChange={(e) => setIncludeGdelt(e.target.checked)} />
            Include GDELT news (slower)
          </label>
          <button
            type="submit"
            disabled={busy}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-page hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play className="h-4 w-4" aria-hidden="true" />
            {busy ? 'Analysing…' : 'Run analysis'}
          </button>
        </form>
        {multi && (
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label>
              <span className="mb-1 block text-xs text-ink-muted">Investment amount (₹) for an illustrative portfolio</span>
              <input
                type="number" min="1" step="1000" value={amount} onChange={(e) => setAmount(e.target.value)}
                placeholder="leave empty to analyse the stocks only"
                aria-invalid={Boolean(amountError)}
                className="w-full rounded-lg border border-line bg-page px-3 py-2 text-sm text-ink outline-none focus:border-accent"
              />
              {amountError && <span className="mt-1 block text-xs text-critical">{amountError}</span>}
            </label>
            <label>
              <span className="mb-1 block text-xs text-ink-muted">Risk preference</span>
              <select value={preference} onChange={(e) => setPreference(e.target.value)}
                      className="w-full rounded-lg border border-line bg-page px-3 py-2 text-sm text-ink outline-none focus:border-accent">
                {PREFERENCES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </label>
          </div>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" onClick={() => addSuggestion(s)}
                    className="rounded-full border border-line px-2.5 py-0.5 text-xs text-ink-secondary hover:bg-white/5">
              {s}
            </button>
          ))}
        </div>
      </Card>

      {error && <ErrorState message={error} />}

      {!status && !error && (
        <Card>
          <EmptyState>
            Run an analysis to see the price chart, technical indicators, an AI explanation and recent news.
            The first run takes about 15–60 seconds on a CPU.
          </EmptyState>
        </Card>
      )}

      {status && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <AgentStatus status={status} onRerun={rerun} />
          </div>
          <div className="space-y-5 lg:col-span-2">
            {busy && !result && <Card><Loading label="Agents are working… results appear when they finish." /></Card>}
            {result && !mr && (
              <ErrorState message={result.errors?.[0]?.message || 'No market data could be produced for this symbol.'} />
            )}
            {result?.symbols?.length > 1 && (
              <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Stock shown in the detail cards">
                <span className="text-xs text-ink-muted">Details for:</span>
                {result.symbols.map((s) => (
                  <button key={s} type="button" onClick={() => choose(s)} aria-pressed={s === key}
                          className={`rounded-full border px-2.5 py-0.5 text-xs ${s === key ? 'border-accent text-ink' : 'border-line text-ink-secondary hover:bg-white/5'}`}>
                    {s}
                  </button>
                ))}
              </div>
            )}
            {mr && <MarketTiles mr={mr} />}
            {mr && <Explanation mr={mr} />}
          </div>
        </div>
      )}

      {mr && series.length > 0 && (
        <div className="space-y-5">
          <PriceChart data={series} />
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <RsiChart data={series} />
            <MacdChart data={series} />
          </div>
        </div>
      )}
      {mr && !indicators && !busy && (
        <ErrorState message="Indicator charts could not be loaded (price source unavailable). The analysis above is still valid." />
      )}

      {portfolio && <PortfolioCard portfolio={portfolio} />}

      {sa && <Fundamentals sa={sa} />}

      {risk && <RiskCard risk={risk} />}

      {news && <NewsList news={news} />}
    </div>
  )
}
