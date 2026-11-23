// Results of the Portfolio Optimization Agent: allocation table (weights, rupees, whole
// shares), in-sample figures, backtest vs equal weights and NIFTY 50, rule-based readings,
// the labelled AI explanation and the "illustrative, not advice" disclaimer.
import { AlertTriangle, Bot, Calculator } from 'lucide-react'
import { Card, Chip } from './ui'
import { EquityChart } from './charts'
import { fmtDate, inr, num, pct } from '../utils/format'

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-lg border border-line p-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="mt-0.5 text-lg font-semibold text-ink tabular">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-muted">{sub}</div>}
    </div>
  )
}

export default function PortfolioCard({ portfolio }) {
  if (!portfolio) return null
  if (portfolio.status === 'failed') {
    return (
      <Card title="Illustrative portfolio">
        <p className="text-sm text-ink-secondary">{portfolio.errors?.[0] || 'The portfolio could not be optimised.'}</p>
      </Card>
    )
  }
  const em = portfolio.expected_metrics || {}
  const bk = portfolio.backtest
  const eq = bk?.vs_benchmark?.equal_weight
  const nifty = bk?.vs_benchmark?.nifty50
  const fromLlm = portfolio.llm?.source === 'llm'
  const c = portfolio.constraints || {}
  return (
    <div className="space-y-5">
      <Card
        title="Illustrative portfolio"
        subtitle={`${inr(portfolio.investment_amount, 0)} · ${portfolio.risk_preference} risk preference · ${portfolio.method_label}`}
        actions={<Chip>Max {num(c.max_weight_pct, 0)}% per stock · no short selling</Chip>}
      >
        {portfolio.fallback_reason && (
          <div className="mb-4 flex gap-2 rounded-lg border border-warning/40 p-3 text-sm text-ink-secondary">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
            <span><span className="font-medium text-warning">Method changed: </span>{portfolio.fallback_reason}.</span>
          </div>
        )}

        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Allocation by stock</caption>
            <thead className="bg-white/[0.02] text-xs text-ink-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Stock</th>
                <th className="px-3 py-2 text-right font-medium">Weight</th>
                <th className="px-3 py-2 text-right font-medium">Shares</th>
                <th className="px-3 py-2 text-right font-medium">Last price</th>
                <th className="px-3 py-2 text-right font-medium">Amount</th>
                <th className="px-3 py-2 text-right font-medium">Past return / yr</th>
                <th className="px-3 py-2 text-right font-medium">Volatility</th>
              </tr>
            </thead>
            <tbody className="tabular">
              {portfolio.allocations.map((a) => (
                <tr key={a.symbol} className="border-t border-line">
                  <td className="px-3 py-2 font-medium text-ink">{a.symbol}</td>
                  <td className="px-3 py-2 text-right text-ink">
                    <div className="flex items-center justify-end gap-2">
                      {/* single-hue magnitude bar; the number carries the value */}
                      <span className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-white/5 sm:inline-block" aria-hidden="true">
                        <span className="block h-full rounded-full bg-accent" style={{ width: `${a.weight_pct}%` }} />
                      </span>
                      {num(a.weight_pct)}%
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right text-ink">{a.shares}</td>
                  <td className="px-3 py-2 text-right text-ink-secondary">{inr(a.last_price)}</td>
                  <td className="px-3 py-2 text-right text-ink">{inr(a.amount_inr, 0)}</td>
                  <td className="px-3 py-2 text-right text-ink-secondary">{pct(a.expected_return_pct)}</td>
                  <td className="px-3 py-2 text-right text-ink-secondary">{num(a.volatility_pct)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          Whole shares at the last close ({fmtDate(portfolio.allocations[0]?.last_price_date)}): {inr(portfolio.invested_inr, 0)} invested,
          {' '}{inr(portfolio.leftover_cash_inr, 0)} left as cash.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Stat label="Past return of this mix" value={pct(em.annual_return_pct)} sub="Average per year, estimation window" />
          <Stat label="Past volatility of this mix" value={em.annual_volatility_pct == null ? '—' : `${num(em.annual_volatility_pct)}%`} sub="Annualised" />
          <Stat label="Backtest CAGR" value={bk ? pct(bk.cagr_pct) : '—'}
                sub={bk ? `Equal weights ${pct(eq?.cagr_pct)} · NIFTY 50 ${pct(nifty?.cagr_pct)}` : portfolio.backtest_reason} />
          <Stat label="Backtest max drawdown" value={bk?.max_drawdown_pct == null ? '—' : `${num(bk.max_drawdown_pct)}%`}
                sub={bk ? `Sharpe ${bk.sharpe == null ? '—' : num(bk.sharpe, 2)} · costs ${inr(bk.total_costs_inr, 0)}` : null} />
        </div>

        {Object.keys(portfolio.readings || {}).length > 0 && (
          <div className="mt-4">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-ink-muted">
              <Calculator className="h-3.5 w-3.5" aria-hidden="true" /> Key readings (computed by NeuralVest rules)
            </div>
            <ul className="list-disc space-y-0.5 pl-5 text-sm text-ink">
              {Object.values(portfolio.readings).map((r) => <li key={r}>{r.charAt(0).toUpperCase() + r.slice(1)}.</li>)}
            </ul>
          </div>
        )}

        {portfolio.explanation && (
          <div className="mt-4 rounded-lg border border-line bg-white/[0.02] p-3">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-ink-muted">
              <Bot className="h-3.5 w-3.5" aria-hidden="true" />
              {fromLlm ? `AI explanation (local ${portfolio.llm.model}; may contain wording errors, the readings above are authoritative)` : 'Explanation (generated without the AI model)'}
            </div>
            <p className="text-sm text-ink-secondary">{portfolio.explanation}</p>
          </div>
        )}

        {portfolio.warnings?.length > 0 && (
          <ul className="mt-4 space-y-1 text-xs text-ink-secondary">
            {portfolio.warnings.map((w) => (
              <li key={w} className="flex gap-1.5">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" aria-hidden="true" />{w}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-ink-muted">{portfolio.disclaimer}</p>
      </Card>

      {bk?.equity_curve?.length > 0 && (
        <div>
          <EquityChart data={bk.equity_curve} capital={portfolio.investment_amount} />
          <p className="mt-2 text-xs text-ink-muted">
            {fmtDate(bk.period.from)} – {fmtDate(bk.period.to)}: weights recomputed {bk.settings.rebalancing} from the previous {bk.settings.lookback_days} trading days only,
            {' '}{num(bk.settings.transaction_cost_bps, 0)} bps per trade. Limits: {bk.limitations.join(' ')}
          </p>
        </div>
      )}
    </div>
  )
}
