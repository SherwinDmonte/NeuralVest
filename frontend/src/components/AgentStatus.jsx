// Agent execution views: the compact status list (Stock Analysis page), the LangGraph workflow
// diagram and the per-agent cards (Agent Monitoring page, task 12.3.4).
import {
  ArrowClockwise,
  CheckCircle,
  Circle,
  CircleNotch,
  MinusCircle,
  Warning,
  XCircle,
} from '@phosphor-icons/react'
import { Button, Card, Meta } from './ui'
import { num, pct } from '../utils/format'

export const AGENTS = [
  { key: 'market_research', name: 'Market Research', does: 'Prices, indicators, trend and the NIFTY 50 comparison' },
  { key: 'financial_news', name: 'Financial News', does: 'News collection, AI summaries and sentiment' },
  { key: 'stock_analysis', name: 'Stock Analysis', does: 'Financial statements, ratios and financial health' },
  { key: 'risk_assessment', name: 'Risk Assessment', does: 'Volatility, beta, drawdown and the Sharpe ratio' },
  { key: 'portfolio_optimization', name: 'Portfolio Optimization', does: 'Allocation, whole shares and a backtest, for 2 or more stocks with an amount' },
  { key: 'report', name: 'Report Generation', does: 'Output checks, key observations, sources and glossary' },
]

export const STATE = {
  pending: { Icon: Circle, cls: 'text-ink-muted', label: 'Waiting' },
  running: { Icon: CircleNotch, cls: 'text-accent-ink motion-safe:animate-spin', label: 'Running' },
  completed: { Icon: CheckCircle, cls: 'text-good', label: 'Completed' },
  partial: { Icon: Warning, cls: 'text-warning', label: 'Partial' },
  failed: { Icon: XCircle, cls: 'text-critical', label: 'Failed' },
  interrupted: { Icon: XCircle, cls: 'text-critical', label: 'Interrupted' },
  skipped: { Icon: MinusCircle, cls: 'text-ink-muted', label: 'Skipped' },
}

export const JOB_TEXT = {
  queued: 'Queued, waiting for the analysis worker',
  running: 'Analysis in progress',
  completed: 'Analysis completed',
  partial: 'Completed with some data missing',
  failed: 'Analysis failed',
  interrupted: 'Interrupted: the server stopped during this analysis',
}

export function StateIcon({ state, size = 16 }) {
  const s = STATE[state] || STATE.pending
  return <s.Icon size={size} weight={state === 'completed' ? 'fill' : 'regular'} className={`shrink-0 ${s.cls}`} aria-hidden="true" />
}

export function progressOf(agents) {
  const states = AGENTS.map((a) => agents?.[a.key] || 'pending')
  const done = states.filter((s) => !['pending', 'running'].includes(s)).length
  return { done, total: AGENTS.length }
}

export default function AgentStatus({ status, onRerun, footer }) {
  if (!status) return null
  const job = status.status
  const { done, total } = progressOf(status.agents)
  return (
    <Card title="Agent execution" subtitle={`${done} of ${total} steps finished`}>
      <p className="mb-4 body-6 text-ink-secondary" aria-live="polite">
        {JOB_TEXT[job] || job}
        {status.queue_position ? `, position ${status.queue_position} in the queue` : ''}
      </p>
      <div className="mb-4 h-1 overflow-hidden rounded bg-raised" aria-hidden="true">
        <div className="h-full origin-left rounded bg-accent transition-transform duration-500 ease-nv" style={{ transform: `scaleX(${done / total})` }} />
      </div>
      <ol className="space-y-1">
        {AGENTS.map((a) => {
          const state = status.agents?.[a.key] || 'pending'
          return (
            <li key={a.key} className="flex items-center gap-3 rounded-lg px-2 py-2">
              <StateIcon state={state} />
              <span className="min-w-0 flex-1 body-5 text-ink">{a.name}</span>
              <span className="caption-5 text-ink-muted">{(STATE[state] || STATE.pending).label}</span>
            </li>
          )
        })}
      </ol>
      {(job === 'interrupted' || job === 'failed') && onRerun && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRerun}>
          <ArrowClockwise size={16} aria-hidden="true" /> Run again
        </Button>
      )}
      {footer}
    </Card>
  )
}

// ------------------------------------------------------------------ workflow diagram
// The LangGraph graph as built in orchestration/graph.py: validate, market research, then news,
// fundamentals and risk (sequential by default, parallel when configured), output validation,
// the optional portfolio step and the report.
const FLOW = [
  [{ key: 'validate_input', name: 'Validate input' }],
  [{ key: 'market_research', name: 'Market research' }],
  [
    { key: 'financial_news', name: 'Financial news' },
    { key: 'stock_analysis', name: 'Stock analysis' },
    { key: 'risk_assessment', name: 'Risk assessment' },
  ],
  [{ key: 'output_validation', name: 'Output validation' }],
  [{ key: 'portfolio_optimization', name: 'Portfolio' }],
  [{ key: 'report', name: 'Report' }],
]

function nodeState(key, status, runs) {
  if (status?.agents?.[key]) return status.agents[key]
  if (runs?.[key]?.status) return runs[key].status
  if (key === 'validate_input') return status?.status && status.status !== 'queued' ? 'completed' : 'pending'
  if (key === 'output_validation') {
    const r = status?.agents?.report
    return r && r !== 'pending' ? 'completed' : 'pending' // it runs just before the report
  }
  return 'pending'
}

export function WorkflowGraph({ status, runs }) {
  return (
    <Card title="Workflow" subtitle="LangGraph supervisor: each step runs when the one before it finishes; failed data steps are retried once">
      <ol className="flex flex-col gap-2 xl:flex-row xl:items-stretch xl:gap-0">
        {FLOW.map((column, i) => (
          <li key={column[0].key} className="flex min-w-0 flex-col items-stretch xl:flex-1 xl:flex-row xl:items-center">
            <div className="flex min-w-0 flex-col gap-2 xl:flex-1">
              {column.map((n) => {
                const state = nodeState(n.key, status, runs)
                const secs = runs?.[n.key]?.duration_s
                return (
                  <div key={n.key}
                       className={`rounded-xl border bg-raised/50 px-3 py-2 ${state === 'running' ? 'border-accent' : 'border-line'}`}>
                    <div className="flex items-center gap-2">
                      <StateIcon state={state} size={14} />
                      <span className="body-5 text-ink">{n.name}</span>
                    </div>
                    <Meta className="mt-1 block">{secs != null ? `${num(secs, 1)} s` : (STATE[state] || STATE.pending).label.toLowerCase()}</Meta>
                  </div>
                )
              })}
            </div>
            {i < FLOW.length - 1 && (
              <span className="mx-auto h-3 w-px bg-line-strong xl:mx-0 xl:h-px xl:w-3 xl:shrink-0" aria-hidden="true" />
            )}
          </li>
        ))}
      </ol>
    </Card>
  )
}

// ------------------------------------------------------------------ per agent cards
export function outputSummary(key, result) {
  if (!result) return null
  const first = (obj) => Object.entries(obj || {}).filter(([k]) => k !== '__request__')
  switch (key) {
    case 'market_research':
      return first(result.market_research).map(([s, v]) => `${s}: ${v.trend?.classification || 'n/a'} trend, 1 year ${pct(v.period_return_pct)}`)
    case 'financial_news':
      return first(result.financial_news).map(([s, v]) => `${s}: ${v.articles_analyzed ?? 0} ${v.articles_analyzed === 1 ? 'article' : 'articles'}, ${(v.overall_sentiment || 'n/a').replaceAll('_', ' ')} sentiment`)
    case 'stock_analysis':
      return first(result.stock_analysis).map(([s, v]) => `${s}: ${(v.overall || v.status || 'n/a').replaceAll('_', ' ')} overall`)
    case 'risk_assessment':
      return first(result.risk_assessment).map(([s, v]) => `${s}: ${(v.risk_classification || 'n/a').replaceAll('_', ' ')} risk, volatility ${num(v.annualized_volatility_pct)}%`)
    case 'portfolio_optimization': {
      const p = result.portfolio_optimization
      return p ? [`${p.method_label || p.method}`, `${p.allocations?.length ?? 0} stocks, ₹${num(p.invested_inr, 0)} invested`] : null
    }
    case 'report': {
      const r = result.report
      return r ? [`${r.key_observations?.items?.length ?? 0} key observations`, r.traceability?.ok ? `all ${r.traceability.numbers_checked} numbers traced` : 'some numbers not traced'] : null
    }
    default:
      return null
  }
}

export function agentErrors(key, result) {
  return (result?.errors || []).filter((e) => e.agent === key || (key === 'report' && e.agent === 'validate_input'))
}

export function AgentCards({ status, result, runs }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {AGENTS.map((a) => {
        const state = status?.agents?.[a.key] || runs?.[a.key]?.status || 'pending'
        const run = runs?.[a.key]
        const summary = outputSummary(a.key, result)
        const errors = agentErrors(a.key, result)
        const retried = (run?.retries || []).filter((r) => r.retried).length
        return (
          <section key={a.key} className="flex flex-col rounded-2xl border border-line bg-surface p-4">
            <header className="flex items-start justify-between gap-3">
              <div>
                <h3 className="title-3 text-ink">{a.name}</h3>
                <p className="mt-1 caption-5 text-ink-muted">{a.does}</p>
              </div>
              <span className="inline-flex items-center gap-1 caption-4 text-ink-secondary">
                <StateIcon state={state} size={14} />
                {(STATE[state] || STATE.pending).label}
              </span>
            </header>
            <dl className="mt-4 grid grid-cols-2 gap-3">
              <div>
                <dt className="caption-5 text-ink-muted">Time</dt>
                <dd className="figure-2 text-ink">{run?.duration_s != null ? `${num(run.duration_s, 1)} s` : 'n/a'}</dd>
              </div>
              <div>
                <dt className="caption-5 text-ink-muted">Retries</dt>
                <dd className="figure-2 text-ink">{retried}</dd>
              </div>
            </dl>
            {summary?.length > 0 && (
              <ul className="mt-4 space-y-1 caption-2 text-ink-secondary">
                {summary.map((s) => <li key={s}>{s}</li>)}
              </ul>
            )}
            {errors.length > 0 && (
              <ul className="mt-4 space-y-1 caption-5 text-critical">
                {errors.map((e) => <li key={`${e.symbol}-${e.message}`}>{e.symbol ? `${e.symbol}: ` : ''}{e.message}</li>)}
              </ul>
            )}
          </section>
        )
      })}
    </div>
  )
}
