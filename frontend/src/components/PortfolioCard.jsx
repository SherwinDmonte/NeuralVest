// Results of the Portfolio Optimization Agent: allocation (weights, rupees, whole shares),
// in-sample figures, the backtest against equal weights and the NIFTY 50, readings, the AI
// explanation and the "illustrative, not advice" disclaimer.
import { Warning } from '@phosphor-icons/react'
import { Card, Meta, StatTile, Traced, table } from './ui'
import { AiNote, Readings } from './explain'
import { ComparisonBars, DonutChart, EquityChart, RiskReturnScatter } from './charts'
import { fmtDate, inr, num, pct } from '../utils/format'

export default function PortfolioCard({ portfolio }) {
  if (!portfolio) return null
  if (portfolio.status === 'failed') {
    return (
      <Card title="Illustrative portfolio">
        <p className="body-6 text-ink-secondary">{portfolio.errors?.[0] || 'The portfolio could not be optimised.'}</p>
      </Card>
    )
  }
  const em = portfolio.expected_metrics || {}
  const bk = portfolio.backtest
  const eq = bk?.vs_benchmark?.equal_weight
  const nifty = bk?.vs_benchmark?.nifty50
  const c = portfolio.constraints || {}
  return (
    <div className="space-y-6">
      <Card
        title="Illustrative portfolio"
        subtitle={`${inr(portfolio.investment_amount, 0)} · ${portfolio.risk_preference} risk preference · ${portfolio.method_label}`}
        actions={<Meta>max {num(c.max_weight_pct, 0)}% per stock · no short selling</Meta>}
      >
        <div className="space-y-6">
          {portfolio.fallback_reason && (
            <div className="flex gap-2 rounded-xl border border-line bg-raised/50 p-4 body-6 text-ink-secondary">
              <Warning size={18} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
              <span><span className="body-5 text-ink">Method changed. </span>{portfolio.fallback_reason}.</span>
            </div>
          )}

          <div className="grid gap-6 2xl:grid-cols-[1.3fr_1fr]">
            <div>
              <div className={table.wrap}>
                <table className={table.table}>
                  <caption className="sr-only">Allocation by stock</caption>
                  <thead className={table.thead}>
                    <tr>
                      <th className={table.th}>Stock</th>
                      <th className={table.thR}>Weight</th>
                      <th className={table.thR}>Shares</th>
                      <th className={`${table.thR} hidden sm:table-cell`}>Last price</th>
                      <th className={table.thR}>Amount</th>
                      <th className={`${table.thR} hidden md:table-cell`}>Past return a year</th>
                      <th className={`${table.thR} hidden md:table-cell`}>Volatility</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portfolio.allocations.map((a) => (
                      <tr key={a.symbol} className={table.tr}>
                        <td className="px-3 py-2 body-5 text-ink">{a.symbol}</td>
                        <td className={table.tdR}>{num(a.weight_pct)}%</td>
                        <td className={table.tdR}>{a.shares}</td>
                        <td className={`${table.tdR} hidden sm:table-cell`}>{inr(a.last_price)}</td>
                        <td className={table.tdR}>{inr(a.amount_inr, 0)}</td>
                        <td className={`${table.tdR} hidden md:table-cell`}>{pct(a.expected_return_pct)}</td>
                        <td className={`${table.tdR} hidden md:table-cell`}>{num(a.volatility_pct)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 caption-5 text-ink-muted">
                Whole shares at the last close ({fmtDate(portfolio.allocations[0]?.last_price_date)}): {inr(portfolio.invested_inr, 0)} invested,
                {' '}{inr(portfolio.leftover_cash_inr, 0)} left as cash. Past return a year is the average daily return × 252 over the
                last {portfolio.assumptions?.lookback_days ?? 252} trading days (the optimiser&apos;s input), so it differs from the 1 year price change.
              </p>
            </div>
            <div>
              <div className="mb-3 caption-4 text-ink-muted">Target weights</div>
              <DonutChart rows={portfolio.allocations} />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile label="Past return of this mix" value={pct(em.annual_return_pct)} sub="Average a year, estimation window" traced="portfolio" />
            <StatTile label="Past volatility of this mix" value={em.annual_volatility_pct == null ? 'n/a' : `${num(em.annual_volatility_pct)}%`} sub="Annualised" traced="portfolio" />
            <StatTile label="Backtest CAGR" value={bk ? pct(bk.cagr_pct) : 'n/a'}
                      sub={bk ? `Equal weights ${pct(eq?.cagr_pct)} · NIFTY 50 ${pct(nifty?.cagr_pct)}` : portfolio.backtest_reason} traced="portfolio" />
            <StatTile label="Backtest max drawdown" value={bk?.max_drawdown_pct == null ? 'n/a' : `${num(bk.max_drawdown_pct)}%`}
                      sub={bk ? `Sharpe ${bk.sharpe == null ? 'n/a' : num(bk.sharpe, 2)} · costs ${inr(bk.total_costs_inr, 0)}` : null} traced="portfolio" />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-line bg-raised/40 p-4">
              <p className="title-4 text-ink">Risk and return, estimation window</p>
              <p className="caption-5 text-ink-muted">Historical estimates from the last {portfolio.assumptions?.lookback_days ?? 252} trading days; the diamond is this mix. Not a forecast.</p>
              <RiskReturnScatter
                points={portfolio.allocations.filter((a) => a.volatility_pct != null && a.expected_return_pct != null).map((a) => ({ label: a.symbol, vol: a.volatility_pct, ret: a.expected_return_pct }))}
                portfolio={em.annual_volatility_pct != null && em.annual_return_pct != null ? { label: 'This mix', vol: em.annual_volatility_pct, ret: em.annual_return_pct } : null} />
            </div>
            <div className="rounded-2xl border border-line bg-raised/40 p-4">
              <p className="title-4 text-ink">Backtest CAGR comparison</p>
              <p className="mb-4 caption-5 text-ink-muted">{bk ? `Historical, out of sample, ${fmtDate(bk.period.from)} to ${fmtDate(bk.period.to)}, after costs` : portfolio.backtest_reason || 'No backtest'}</p>
              {bk && <ComparisonBars rows={[{ label: 'This allocation rule', value: bk.cagr_pct }, { label: 'Equal weights', value: eq?.cagr_pct }, { label: 'NIFTY 50', value: nifty?.cagr_pct }]} />}
            </div>
          </div>

          <Readings items={Object.values(portfolio.readings || {})} />
          <AiNote llm={portfolio.llm} text={portfolio.explanation} />

          {portfolio.warnings?.length > 0 && (
            <ul className="space-y-1 caption-5 text-ink-secondary">
              {portfolio.warnings.map((w) => (
                <li key={w} className="flex gap-2">
                  <Warning size={14} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />{w}
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap items-end justify-between gap-2">
            <p className="max-w-3xl caption-5 text-ink-muted">{portfolio.disclaimer}</p>
            <Traced agent="portfolio" />
          </div>
        </div>
      </Card>

      {bk?.equity_curve?.length > 0 && (
        <div>
          <EquityChart data={bk.equity_curve} capital={portfolio.investment_amount} />
          <p className="mt-2 caption-5 text-ink-muted">
            {fmtDate(bk.period.from)} to {fmtDate(bk.period.to)}: weights recomputed {bk.settings.rebalancing} from the previous
            {' '}{bk.settings.lookback_days} trading days only, {num(bk.settings.transaction_cost_bps, 0)} bps a trade. Limits: {bk.limitations.join(' ')}
          </p>
        </div>
      )}
    </div>
  )
}
