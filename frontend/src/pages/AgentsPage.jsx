// AI Agent Monitoring (task 12.3.4): the five agents and the report step as cards (status,
// progress, time, output, errors) and the LangGraph workflow. Follows the analysis that is
// running, or the one named by ?request=<id>.
import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArrowClockwise, TreeStructure } from '@phosphor-icons/react'
import { useCurrentAnalysis } from '../analysis/AnalysisContext'
import { AgentCards, JOB_TEXT, WorkflowGraph, progressOf } from '../components/AgentStatus'
import { Button, Card, EmptyState, ErrorState, Meta, PageHeader } from '../components/ui'
import { fmtDateTime, num } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

export default function AgentsPage() {
  usePageTitle('Agent monitoring')
  const [params] = useSearchParams()
  const { requestId, status, result, error, open, rerun } = useCurrentAnalysis()
  const requested = params.get('request')

  useEffect(() => {
    if (requested && requested !== requestId) open(requested)
  }, [requested, requestId, open])

  if (!status && !error) {
    return (
      <div className="space-y-6">
        <PageHeader title="Agent monitoring" description="Follow each agent of an analysis: what it is doing, how long it took and what it produced." />
        <EmptyState icon={TreeStructure} title="No analysis to follow"
                    action={<div className="flex gap-2"><Button to="/app/analysis" size="sm">Start an analysis</Button><Button to="/app/reports" size="sm" variant="secondary">Open a past report</Button></div>}>
          Start an analysis, or open one from Reports, and its agents appear here while they work.
        </EmptyState>
      </div>
    )
  }

  const runs = result?.agent_runs
  const { done, total } = progressOf(status?.agents)
  const totalSeconds = runs ? Object.values(runs).reduce((s, r) => Math.max(s, r.duration_s ?? 0), 0) : null
  const started = status?.requested_at
  const finished = status?.completed_at

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent monitoring"
        description={status ? `${status.symbols?.join(', ')} · ${JOB_TEXT[status.status] || status.status}` : undefined}
        actions={['failed', 'interrupted'].includes(status?.status) && (
          <Button variant="secondary" size="sm" onClick={rerun}><ArrowClockwise size={16} aria-hidden="true" /> Run again</Button>
        )}
      />
      {error && <ErrorState message={error} />}

      {status && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card>
            <div className="caption-2 text-ink-secondary">Progress</div>
            <div className="mt-2 figure-1 text-ink">{done} of {total}</div>
            <div className="mt-3 h-1 overflow-hidden rounded bg-raised" aria-hidden="true">
              <div className="h-full origin-left rounded bg-accent transition-transform duration-500 ease-nv" style={{ transform: `scaleX(${done / total})` }} />
            </div>
          </Card>
          <Card>
            <div className="caption-2 text-ink-secondary">Started</div>
            <div className="mt-2 figure-2 text-ink">{fmtDateTime(started)}</div>
            <Meta className="mt-1 block">{finished ? `finished ${fmtDateTime(finished)}` : 'still running'}</Meta>
          </Card>
          <Card>
            <div className="caption-2 text-ink-secondary">Longest step</div>
            <div className="mt-2 figure-2 text-ink">{totalSeconds ? `${num(totalSeconds, 1)} s` : 'n/a'}</div>
            <Meta className="mt-1 block">{totalSeconds ? 'of the workflow steps' : 'timings appear when the run finishes'}</Meta>
          </Card>
        </div>
      )}

      <WorkflowGraph status={status} runs={runs} />
      <AgentCards status={status} result={result} runs={runs} />

      {status?.status_history?.length > 0 && (
        <Card title="Status history">
          <ol className="space-y-2">
            {status.status_history.map((e) => (
              <li key={`${e.status}-${e.at}`} className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <Meta className="w-36">{fmtDateTime(e.at)}</Meta>
                <span className="body-6 text-ink">{e.status}</span>
                {e.reason && <span className="caption-5 text-ink-muted">{e.reason}</span>}
              </li>
            ))}
          </ol>
        </Card>
      )}
      {result?.validation_summary && (
        <Card title="Output validation" subtitle="Checks run on every agent result before the report is written">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div><dt className="caption-5 text-ink-muted">Issues found</dt><dd className="figure-2 text-ink">{result.validation_summary.issue_count ?? 0}</dd></div>
            <div><dt className="caption-5 text-ink-muted">AI texts replaced</dt><dd className="figure-2 text-ink">{result.validation_summary.text_replacements ?? 0}</dd></div>
            <div><dt className="caption-5 text-ink-muted">Portfolio candidates</dt><dd className="figure-2 text-ink">{result.validation_summary.portfolio_candidates?.length ?? 0}</dd></div>
            <div><dt className="caption-5 text-ink-muted">Left out of portfolio</dt><dd className="figure-2 text-ink">{Object.keys(result.validation_summary.excluded_from_portfolio || {}).length}</dd></div>
          </dl>
        </Card>
      )}
    </div>
  )
}
