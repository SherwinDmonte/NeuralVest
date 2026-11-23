// Results of the Stock Analysis Agent: ratios (with period and reason when unavailable),
// rule-based assessments, strengths/weaknesses and the AI explanation.
import { Bot, Calculator } from 'lucide-react'
import { Card, Chip, ToneBadge } from './ui'
import { fmtDate, num } from '../utils/format'

const METRICS = [
  ['revenue_growth_yoy_pct', 'Revenue growth (YoY)'],
  ['revenue_cagr_pct', 'Revenue growth (CAGR)'],
  ['net_profit_growth_yoy_pct', 'Net profit growth (YoY)'],
  ['eps', 'EPS'],
  ['pe', 'P/E'],
  ['pb', 'P/B'],
  ['roe_pct', 'Return on equity'],
  ['roa_pct', 'Return on assets'],
  ['debt_to_equity', 'Debt-to-equity'],
  ['current_ratio', 'Current ratio'],
  ['operating_margin_pct', 'Operating margin'],
  ['net_margin_pct', 'Net profit margin'],
]

const ASSESSMENT_LABELS = { profitability: 'Profitability', growth: 'Growth', leverage: 'Debt', liquidity: 'Liquidity' }

function formatMetric(m) {
  if (m?.value == null) return '—'
  if (m.unit === '%') return `${num(m.value)}%`
  if (m.unit === 'INR') return `₹${num(m.value)}`
  return `${num(m.value)}×`
}

export default function Fundamentals({ sa }) {
  if (!sa) return null
  if (sa.status === 'skipped') return null
  const fromLlm = sa.llm?.source === 'llm'
  return (
    <Card
      title="Fundamentals"
      subtitle={`Annual statements ${sa.statement_periods?.income_statement ? `(year ended ${fmtDate(sa.statement_periods.income_statement)})` : ''}${sa.is_bank ? ' · bank' : ''}`}
      actions={<ToneBadge value={sa.overall} />}
    >
      {sa.status === 'failed' ? (
        <p className="text-sm text-ink-secondary">{sa.errors?.[0] || 'Financial statements are not available for this company.'}</p>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            {Object.entries(sa.assessments || {}).map(([k, v]) => (
              <Chip key={k}>{ASSESSMENT_LABELS[k] || k}: {v.replaceAll('_', ' ')}</Chip>
            ))}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Fundamental ratios</caption>
              <thead className="text-xs text-ink-muted">
                <tr>
                  <th className="py-1.5 pr-3 font-medium">Metric</th>
                  <th className="py-1.5 pr-3 text-right font-medium">Value</th>
                  <th className="py-1.5 font-medium">How it is computed / note</th>
                </tr>
              </thead>
              <tbody>
                {METRICS.map(([key, label]) => {
                  const m = sa.metrics?.[key]
                  if (!m) return null
                  return (
                    <tr key={key} className="border-t border-line align-top">
                      <td className="py-1.5 pr-3 text-ink-secondary">{label}</td>
                      <td className="tabular py-1.5 pr-3 text-right text-ink">{formatMetric(m)}</td>
                      <td className="py-1.5 text-xs text-ink-muted">
                        {m.value == null ? <span className="text-warning">Unavailable: {m.reason}</span> : m.formula}
                        {m.value != null && m.reason ? <span className="block">{m.reason}</span> : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {sa.price_used != null && (
            <p className="mt-2 text-xs text-ink-muted">P/E and P/B use the close of ₹{num(sa.price_used)} ({fmtDate(sa.price_date)}).</p>
          )}

          {(sa.strengths?.length > 0 || sa.weaknesses?.length > 0) && (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <div className="mb-1 text-xs text-ink-muted">Strengths (rule-based)</div>
                <ul className="list-disc space-y-0.5 pl-5 text-sm text-ink">
                  {(sa.strengths || []).map((s) => <li key={s}>{s}</li>)}
                  {!sa.strengths?.length && <li className="list-none text-ink-muted">None identified</li>}
                </ul>
              </div>
              <div>
                <div className="mb-1 text-xs text-ink-muted">Weaknesses (rule-based)</div>
                <ul className="list-disc space-y-0.5 pl-5 text-sm text-ink">
                  {(sa.weaknesses || []).map((s) => <li key={s}>{s}</li>)}
                  {!sa.weaknesses?.length && <li className="list-none text-ink-muted">None identified</li>}
                </ul>
              </div>
            </div>
          )}

          {sa.explanation && (
            <div className="mt-4 rounded-lg border border-line bg-white/[0.02] p-3">
              <div className="mb-1 flex items-center gap-1.5 text-xs text-ink-muted">
                <Bot className="h-3.5 w-3.5" aria-hidden="true" />
                {fromLlm ? `AI explanation (local ${sa.llm.model}; may contain wording errors)` : 'Explanation (generated without the AI model)'}
              </div>
              <p className="text-sm text-ink-secondary">{sa.explanation}</p>
            </div>
          )}
          <p className="mt-3 flex items-start gap-1.5 text-xs text-ink-muted">
            <Calculator className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            Ratios computed by NeuralVest from Yahoo Finance annual statements; assessments use fixed rules
            ({Object.values(sa.assessment_rules || {}).join('; ')}). Missing values are shown as unavailable, never estimated.
          </p>
        </>
      )}
    </Card>
  )
}
