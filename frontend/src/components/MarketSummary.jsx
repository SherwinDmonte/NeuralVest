// Headline numbers from the Market Research Agent (stat tiles), plus its readings and explanation.
import { Card, StatTile, ToneBadge } from './ui'
import { AiNote, Readings } from './explain'
import { fmtDate, inr, num, pct } from '../utils/format'

export function MarketTiles({ mr }) {
  if (!mr) return null
  const bench = mr.benchmark_comparison
  const ind = mr.indicators || {}
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile
        label="Last close"
        value={inr(mr.last_close)}
        sub={`As of ${fmtDate(mr.last_close_date)}${mr.last_bar_may_be_incomplete ? ' · market open, may change until close' : ''}`}
        traced="market research"
      />
      <StatTile
        label="1 year price change"
        value={pct(mr.period_return_pct)}
        sub={bench?.available ? `NIFTY 50 ${pct(bench.benchmark_return_pct)} · ${bench.relative_pct > 0 ? '+' : ''}${num(bench.relative_pct)} pts vs NIFTY 50` : 'NIFTY 50 comparison unavailable'}
        traced="market research"
      />
      <StatTile
        label="Trend from moving averages"
        value={<ToneBadge value={mr.trend?.classification} />}
        sub={mr.trend?.rules_triggered?.[0]}
        traced="market research"
      />
      <StatTile label="RSI 14" value={num(ind.rsi_14)} sub={mr.rsi_zone ? `${mr.rsi_zone} zone` : 'Not enough data'} traced="market research" />
    </div>
  )
}

const READING_ORDER = ['rsi_reading', 'macd_reading', 'long_term_reading', 'benchmark_reading']

export function Explanation({ mr }) {
  if (!mr?.explanation) return null
  return (
    <Card title="What the indicators say" subtitle={mr.company_name ? `${mr.company_name} · ${mr.symbol}` : mr.symbol}>
      <div className="space-y-4">
        <Readings items={READING_ORDER.map((k) => mr.readings?.[k])} />
        <AiNote llm={mr.llm} text={mr.explanation} />
        {mr.warnings?.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 caption-5 text-ink-muted">
            {mr.warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        )}
      </div>
    </Card>
  )
}
