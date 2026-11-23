// MVP dashboard (Phase 6): run an analysis for one stock and show the results of the
// Market Research and Financial News agents.
import { useState } from 'react'
import { Play, Search } from 'lucide-react'
import AgentStatus from '../components/AgentStatus'
import { MacdChart, PriceChart, RsiChart } from '../components/charts'
import { Explanation, MarketTiles } from '../components/MarketSummary'
import Fundamentals from '../components/Fundamentals'
import NewsList from '../components/NewsList'
import { Card, EmptyState, ErrorState, Loading } from '../components/ui'
import { useAnalysis } from '../hooks/useAnalysis'

const SUGGESTIONS = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']

export default function DashboardPage() {
  const [symbol, setSymbol] = useState('RELIANCE')
  const [includeGdelt, setIncludeGdelt] = useState(false)
  const { status, result, indicators, error, busy, run, rerun } = useAnalysis()

  const submit = (e) => {
    e.preventDefault()
    if (symbol.trim()) run(symbol.trim(), includeGdelt)
  }

  const key = result?.symbols?.[0]
  const mr = key ? result.market_research?.[key] : null
  const news = key ? result.financial_news?.[key] : null
  const sa = key ? result.stock_analysis?.[key] : null
  const series = indicators?.series || []

  return (
    <div className="space-y-5">
      <Card title="Analyse an Indian stock" subtitle="NSE symbols like RELIANCE or TCS; BSE codes like 500325">
        <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1">
            <span className="mb-1 block text-xs text-ink-muted">Symbol</span>
            <div className="flex items-center gap-2 rounded-lg border border-line bg-page px-3 py-2 focus-within:border-accent">
              <Search className="h-4 w-4 text-ink-muted" aria-hidden="true" />
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="e.g. RELIANCE"
                maxLength={30}
                className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted"
                aria-label="Stock symbol"
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
        <div className="mt-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" onClick={() => setSymbol(s)}
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

      {sa && <Fundamentals sa={sa} />}

      {news && <NewsList news={news} />}
    </div>
  )
}
