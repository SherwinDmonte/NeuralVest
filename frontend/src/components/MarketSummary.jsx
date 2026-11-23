// Headline numbers from the Market Research Agent (stat tiles), plus its explanation.
import { Bot, Calculator } from 'lucide-react'
import { Card, ToneBadge } from './ui'
import { fmtDate, inr, num, pct } from '../utils/format'

function Tile({ label, value, sub, children }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-ink">{value}</div>
      {children}
      {sub && <div className="mt-1 text-xs text-ink-muted">{sub}</div>}
    </div>
  )
}

export function MarketTiles({ mr }) {
  if (!mr) return null
  const bench = mr.benchmark_comparison
  const ind = mr.indicators || {}
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Tile
        label="Last close"
        value={inr(mr.last_close)}
        sub={`As of ${fmtDate(mr.last_close_date)}${mr.last_bar_may_be_incomplete ? ' · market open: may change until close' : ''}`}
      />
      <Tile label="1-year return" value={pct(mr.period_return_pct)}
            sub={bench?.available ? `NIFTY 50: ${pct(bench.benchmark_return_pct)} · difference ${pct(bench.relative_pct)} pts` : 'Benchmark unavailable'} />
      <Tile label="Trend (moving averages)" value={<ToneBadge value={mr.trend?.classification} />}
            sub={mr.trend?.rules_triggered?.[0]} />
      <Tile label="RSI (14)" value={num(ind.rsi_14)} sub={mr.rsi_zone ? `Zone: ${mr.rsi_zone}` : 'Not enough data'} />
    </div>
  )
}

export function Explanation({ mr }) {
  if (!mr?.explanation) return null
  const fromLlm = mr.llm?.source === 'llm'
  return (
    <Card title="What the indicators say" subtitle={mr.company_name ? `${mr.company_name} (${mr.symbol})` : mr.symbol}>
      <p className="text-sm leading-relaxed text-ink-secondary">{mr.explanation}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-ink-muted">
        <span className="inline-flex items-center gap-1">
          <Bot className="h-3.5 w-3.5" aria-hidden="true" />
          {fromLlm ? `Written by local AI (${mr.llm.model})` : 'Generated without the AI model'}
        </span>
        <span className="inline-flex items-center gap-1">
          <Calculator className="h-3.5 w-3.5" aria-hidden="true" />
          Numbers computed in Python and checked in this text
        </span>
      </div>
      {mr.warnings?.length > 0 && (
        <ul className="mt-3 list-disc space-y-0.5 pl-5 text-xs text-ink-muted">
          {mr.warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}
    </Card>
  )
}
