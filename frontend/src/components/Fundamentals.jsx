// Results of the Stock Analysis Agent: ratios (with period, or the reason when unavailable),
// rule-based assessments, strengths and weaknesses, and the AI explanation.
import { Card, Meta, Traced, ToneBadge, table } from './ui'
import { AiNote } from './explain'
import { fmtDate, num } from '../utils/format'

const METRICS = [
  ['revenue_growth_yoy_pct', 'Revenue growth, year on year'],
  ['revenue_cagr_pct', 'Revenue growth, CAGR'],
  ['net_profit_growth_yoy_pct', 'Net profit growth, year on year'],
  ['eps', 'EPS'],
  ['pe', 'P/E'],
  ['pb', 'P/B'],
  ['roe_pct', 'Return on equity'],
  ['roa_pct', 'Return on assets'],
  ['debt_to_equity', 'Debt to equity'],
  ['current_ratio', 'Current ratio'],
  ['operating_margin_pct', 'Operating margin'],
  ['net_margin_pct', 'Net profit margin'],
]

const ASSESSMENT_LABELS = { profitability: 'Profitability', growth: 'Growth', leverage: 'Debt', liquidity: 'Liquidity' }

function formatMetric(m) {
  if (m?.value == null) return 'n/a'
  if (m.unit === '%') return `${num(m.value)}%`
  if (m.unit === 'INR') return `₹${num(m.value)}`
  return `${num(m.value)}×`
}

function List({ title, items }) {
  return (
    <div>
      <div className="mb-2 caption-4 text-ink-muted">{title}</div>
      {items?.length ? (
        <ul className="list-disc space-y-1 pl-5 body-6 text-ink">{items.map((s) => <li key={s}>{s}</li>)}</ul>
      ) : (
        <p className="body-6 text-ink-muted">None found by the rules</p>
      )}
    </div>
  )
}

export default function Fundamentals({ sa }) {
  if (!sa || sa.status === 'skipped') return null
  return (
    <Card
      title="Fundamentals"
      subtitle={`Annual statements${sa.statement_periods?.income_statement ? `, year ended ${fmtDate(sa.statement_periods.income_statement)}` : ''}${sa.is_bank ? ' · assessed as a bank' : ''}`}
      actions={<ToneBadge value={sa.overall} />}
    >
      {sa.status === 'failed' ? (
        <p className="body-6 text-ink-secondary">{sa.errors?.[0] || 'Financial statements are not available for this company.'}</p>
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            {Object.entries(sa.assessments || {}).map(([k, v]) => (
              <div key={k} className="caption-2">
                <span className="text-ink-muted">{ASSESSMENT_LABELS[k] || k} </span>
                <span className="text-ink">{v.replaceAll('_', ' ')}</span>
              </div>
            ))}
          </div>

          <div className={table.wrap}>
            <table className={table.table}>
              <caption className="sr-only">Fundamental ratios</caption>
              <thead className={table.thead}>
                <tr>
                  <th className={table.th}>Metric</th>
                  <th className={table.thR}>Value</th>
                  <th className={`${table.th} hidden md:table-cell`}>How it is computed</th>
                </tr>
              </thead>
              <tbody>
                {METRICS.map(([key, label]) => {
                  const m = sa.metrics?.[key]
                  if (!m) return null
                  return (
                    <tr key={key} className={`${table.tr} align-top`}>
                      <td className={table.td}>
                        {label}
                        <span className="block caption-5 text-ink-muted md:hidden">
                          {m.value == null ? `Unavailable: ${m.reason}` : m.formula}
                        </span>
                      </td>
                      <td className={table.tdR}>{formatMetric(m)}</td>
                      <td className="hidden px-3 py-2 caption-5 text-ink-muted md:table-cell">
                        {m.value == null ? <span className="text-warning">Unavailable: {m.reason}</span> : m.formula}
                        {m.value != null && m.reason ? <span className="block">{m.reason}</span> : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            {sa.price_used != null && <Meta>P/E and P/B use the close of ₹{num(sa.price_used)} on {fmtDate(sa.price_date)}</Meta>}
            <Traced agent="stock analysis" />
          </div>

          <div className="grid gap-6 sm:grid-cols-2">
            <List title="Strengths, by the rules" items={sa.strengths} />
            <List title="Weaknesses, by the rules" items={sa.weaknesses} />
          </div>

          <AiNote llm={sa.llm} text={sa.explanation} />
          <p className="caption-5 text-ink-muted">
            Ratios are computed from Yahoo Finance annual statements and assessed with fixed rules
            ({Object.values(sa.assessment_rules || {}).join('; ')}). Missing values are shown as unavailable, never estimated.
          </p>
        </div>
      )}
    </Card>
  )
}
