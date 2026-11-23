// Live status of the analysis and of each agent (polled every 2 s).
import { AlertTriangle, CheckCircle2, Circle, Loader2, MinusCircle, RotateCcw, XCircle } from 'lucide-react'
import { Card } from './ui'

const AGENTS = [
  { key: 'market_research', name: 'Market Research Agent', does: 'Prices, indicators, trend, NIFTY 50 comparison' },
  { key: 'financial_news', name: 'Financial News Agent', does: 'News collection, AI summaries and sentiment' },
  { key: 'stock_analysis', name: 'Stock Analysis Agent', does: 'Financial statements, ratios, financial health' },
  { key: 'risk_assessment', name: 'Risk Assessment Agent', does: 'Volatility, beta, drawdown, Sharpe ratio' },
]

const STATE = {
  pending: { Icon: Circle, cls: 'text-ink-muted', label: 'Waiting' },
  running: { Icon: Loader2, cls: 'text-accent animate-spin', label: 'Running' },
  completed: { Icon: CheckCircle2, cls: 'text-good', label: 'Completed' },
  partial: { Icon: AlertTriangle, cls: 'text-warning', label: 'Partial' },
  failed: { Icon: XCircle, cls: 'text-critical', label: 'Failed' },
  interrupted: { Icon: XCircle, cls: 'text-critical', label: 'Interrupted' },
  skipped: { Icon: MinusCircle, cls: 'text-ink-muted', label: 'Skipped' },
}

const JOB_TEXT = {
  queued: 'Queued: waiting for the analysis worker',
  running: 'Analysis in progress',
  completed: 'Analysis completed',
  partial: 'Completed with some data missing',
  failed: 'Analysis failed',
  interrupted: 'Interrupted: the server stopped during this analysis',
}

export default function AgentStatus({ status, onRerun }) {
  if (!status) return null
  const job = status.status
  return (
    <Card title="Agent execution" subtitle="LangGraph workflow: validate input, Market Research, Financial News, Stock Analysis, then Risk Assessment">
      <p className="mb-3 text-sm text-ink-secondary" aria-live="polite">
        {JOB_TEXT[job] || job}
        {status.queue_position ? ` (position ${status.queue_position} in queue)` : ''}
      </p>
      <ol className="space-y-2">
        {AGENTS.map((a, i) => {
          const s = STATE[status.agents?.[a.key]] || STATE.pending
          return (
            <li key={a.key} className="flex items-start gap-3 rounded-lg border border-line px-3 py-2">
              <s.Icon className={`mt-0.5 h-4 w-4 shrink-0 ${s.cls}`} aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-medium text-ink">{i + 1}. {a.name}</span>
                  <span className="text-xs text-ink-secondary">{s.label}</span>
                </div>
                <p className="text-xs text-ink-muted">{a.does}</p>
              </div>
            </li>
          )
        })}
      </ol>
      {(job === 'interrupted' || job === 'failed') && onRerun && (
        <button
          type="button"
          onClick={onRerun}
          className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-sm text-ink hover:bg-white/5"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" /> Re-run analysis
        </button>
      )}
    </Card>
  )
}
