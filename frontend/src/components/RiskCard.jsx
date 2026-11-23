// Results of the Risk Assessment Agent: historical risk metrics, rule-based readings,
// the AI explanation (labelled) and the "not a forecast" disclaimer.
import { Bot, Calculator } from 'lucide-react'
import { Card, Chip, ToneBadge } from './ui'
import { fmtDate, num } from '../utils/format'

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-lg border border-line p-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="mt-0.5 text-lg font-semibold text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-muted">{sub}</div>}
    </div>
  )
}

export default function RiskCard({ risk }) {
  if (!risk) return null
  if (risk.status === 'failed') {
    return (
      <Card title="Historical risk">
        <p className="text-sm text-ink-secondary">{risk.errors?.[0] || 'Risk could not be measured for this stock.'}</p>
      </Card>
    )
  }
  const md = risk.max_drawdown || {}
  const dist = risk.return_distribution || {}
  const readings = Object.values(risk.readings || {})
  const fromLlm = risk.llm?.source === 'llm'
  return (
    <Card
      title="Historical risk"
      subtitle={`Daily returns ${fmtDate(risk.window?.from)} – ${fmtDate(risk.window?.to)} (${risk.window?.observations} trading days)`}
      actions={<ToneBadge value={risk.risk_classification} />}
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Annualised volatility" value={risk.annualized_volatility_pct == null ? '—' : `${num(risk.annualized_volatility_pct)}%`}
              sub={`Average annualised return ${risk.annualized_return_pct == null ? '—' : `${num(risk.annualized_return_pct)}%`}`} />
        <Stat label="Beta vs NIFTY 50" value={risk.beta?.value == null ? '—' : num(risk.beta.value, 2)}
              sub={risk.beta?.value == null ? risk.beta?.reason : `${risk.market_sensitivity} · correlation ${num(risk.beta.correlation_with_benchmark, 2)}`} />
        <Stat label="Maximum drawdown" value={md.max_drawdown_pct == null ? '—' : `${num(md.max_drawdown_pct)}%`}
              sub={md.peak_date ? `${fmtDate(md.peak_date)} → ${fmtDate(md.trough_date)} · ${md.recovered ? `recovered ${fmtDate(md.recovery_date)}` : 'not yet recovered'}` : null} />
        <Stat label="Sharpe ratio" value={risk.sharpe?.value == null ? '—' : num(risk.sharpe.value, 2)}
              sub={risk.sharpe?.value == null ? `Unavailable: ${risk.sharpe?.reason}` : `Risk-free rate ${num(risk.risk_free_rate?.value_pct)}% (${risk.risk_free_rate?.source}, ${fmtDate(risk.risk_free_rate?.as_of_date)})`} />
      </div>

      {dist.worst_day && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Chip>Worst day {num(dist.worst_day.return_pct)}% ({fmtDate(dist.worst_day.date)})</Chip>
          <Chip>Best day +{num(dist.best_day.return_pct)}% ({fmtDate(dist.best_day.date)})</Chip>
          <Chip>5% of days below {num(dist.p5_pct)}%</Chip>
          <Chip>Up days {num(dist.positive_days_pct, 1)}%</Chip>
        </div>
      )}

      {readings.length > 0 && (
        <div className="mt-4">
          <div className="mb-1 flex items-center gap-1.5 text-xs text-ink-muted">
            <Calculator className="h-3.5 w-3.5" aria-hidden="true" /> Key readings (computed by NeuralVest rules)
          </div>
          <ul className="list-disc space-y-0.5 pl-5 text-sm text-ink">
            {readings.map((r) => <li key={r}>{r.charAt(0).toUpperCase() + r.slice(1)}.</li>)}
          </ul>
        </div>
      )}

      {risk.explanation && (
        <div className="mt-4 rounded-lg border border-line bg-white/[0.02] p-3">
          <div className="mb-1 flex items-center gap-1.5 text-xs text-ink-muted">
            <Bot className="h-3.5 w-3.5" aria-hidden="true" />
            {fromLlm ? `AI explanation (local ${risk.llm.model}; may contain wording errors)` : 'Explanation (generated without the AI model)'}
          </div>
          <p className="text-sm text-ink-secondary">{risk.explanation}</p>
        </div>
      )}
      <p className="mt-3 text-xs text-ink-muted">
        {risk.disclaimer} Rules: {Object.values(risk.rules || {}).join('; ')}.
      </p>
    </Card>
  )
}
