// Results of the Risk Assessment Agent for one stock: historical risk metrics, readings, the AI
// explanation and the "not a forecast" disclaimer.
import { Card, Meta, StatTile, ToneBadge } from './ui'
import { AiNote, Readings } from './explain'
import { fmtDate, num } from '../utils/format'

export function RiskStats({ risk }) {
  const md = risk.max_drawdown || {}
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile label="Annualised volatility" value={risk.annualized_volatility_pct == null ? 'n/a' : `${num(risk.annualized_volatility_pct)}%`}
                sub={`Average annualised return ${risk.annualized_return_pct == null ? 'n/a' : `${num(risk.annualized_return_pct)}%`}`} traced="risk assessment" />
      <StatTile label="Beta vs NIFTY 50" value={risk.beta?.value == null ? 'n/a' : num(risk.beta.value, 2)}
                sub={risk.beta?.value == null ? risk.beta?.reason : `${risk.market_sensitivity} · correlation ${num(risk.beta.correlation_with_benchmark, 2)}`} traced="risk assessment" />
      <StatTile label="Maximum drawdown" value={md.max_drawdown_pct == null ? 'n/a' : `${num(md.max_drawdown_pct)}%`}
                sub={md.peak_date ? `${fmtDate(md.peak_date)} to ${fmtDate(md.trough_date)} · ${md.recovered ? `recovered ${fmtDate(md.recovery_date)}` : 'not yet recovered'}` : null} traced="risk assessment" />
      <StatTile label="Sharpe ratio" value={risk.sharpe?.value == null ? 'n/a' : num(risk.sharpe.value, 2)}
                sub={risk.sharpe?.value == null ? `Unavailable: ${risk.sharpe?.reason}` : `Risk free rate ${num(risk.risk_free_rate?.value_pct)}% (${fmtDate(risk.risk_free_rate?.as_of_date)})`} traced="risk assessment" />
    </div>
  )
}

export default function RiskCard({ risk }) {
  if (!risk) return null
  if (risk.status === 'failed') {
    return (
      <Card title="Historical risk">
        <p className="body-6 text-ink-secondary">{risk.errors?.[0] || 'Risk could not be measured for this stock.'}</p>
      </Card>
    )
  }
  const dist = risk.return_distribution || {}
  return (
    <Card
      title="Historical risk"
      subtitle={`Daily returns ${fmtDate(risk.window?.from)} to ${fmtDate(risk.window?.to)}, ${risk.window?.observations} trading days`}
      actions={<ToneBadge value={risk.risk_classification} label={`${risk.risk_classification?.replaceAll('_', ' ')} risk`} />}
    >
      <div className="space-y-6">
        <RiskStats risk={risk} />
        {dist.worst_day && (
          <div className="flex flex-wrap gap-x-6 gap-y-1">
            <Meta>worst day {num(dist.worst_day.return_pct)}% on {fmtDate(dist.worst_day.date)}</Meta>
            <Meta>best day +{num(dist.best_day.return_pct)}% on {fmtDate(dist.best_day.date)}</Meta>
            <Meta>5% of days below {num(dist.p5_pct)}%</Meta>
            <Meta>up days {num(dist.positive_days_pct, 1)}%</Meta>
          </div>
        )}
        <Readings items={Object.values(risk.readings || {})} />
        <AiNote llm={risk.llm} text={risk.explanation} />
        <p className="caption-5 text-ink-muted">{risk.disclaimer} Rules: {Object.values(risk.rules || {}).join('; ')}.</p>
      </div>
    </Card>
  )
}
