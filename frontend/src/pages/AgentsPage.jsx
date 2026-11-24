// AI agents (Phase 12, redesigned in 12B): the agent network, progress, the LangGraph pipeline,
// a card per step, execution history, status history and output validation. Follows the running
// analysis, or the one named by ?request=<id>. Everything comes from the status/result API.
import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowClockwise, ClockCounterClockwise, Lightning, ShieldCheck } from '@phosphor-icons/react'
import { useCurrentAnalysis } from '../analysis/AnalysisContext'
import AgentNetwork from '../components/AgentNetwork'
import { AgentCards, JOB_TEXT, WorkflowGraph, progressOf } from '../components/AgentStatus'
import { AnimatedNumber, Reveal } from '../components/motion'
import { Button, Card, ErrorState, Meta, PageHeader, Skeleton, ToneBadge } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { listReports } from '../services/api'
import { fmtDateTime, num } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

function History({ current }) {
  const { data, loading } = useApi(() => listReports({ page_size: 8 }), [current], { key: `agents-history-${current}`, ttl: 15000 })
  return (
    <Card title="Execution history" subtitle="Your recent analyses; open one to replay its agents" icon={ClockCounterClockwise}>
      {loading && !data && <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div>}
      {data && !data.items.length && <p className="caption-2 text-ink-muted">No analyses yet.</p>}
      {data?.items?.length > 0 && (
        <ol className="relative space-y-1 border-l border-line pl-4">
          {data.items.map((r) => (
            <li key={r.request_id} className="relative">
              <span className={`absolute -left-[21px] top-3 h-2.5 w-2.5 rounded-full border-2 border-surface ${r.request_id === current ? 'bg-accent' : 'bg-line-strong'}`} aria-hidden="true" />
              <Link to={`/app/agents?request=${r.request_id}`}
                    className={`flex flex-wrap items-center justify-between gap-2 rounded-xl px-3 py-2 transition-colors duration-300 ease-nv hover:bg-raised ${r.request_id === current ? 'bg-raised' : ''}`}>
                <span className="min-w-0"><span className="block truncate body-5 text-ink">{r.symbols.join(', ')}</span><Meta>{fmtDateTime(r.requested_at)}</Meta></span>
                <ToneBadge value={r.status} />
              </Link>
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}

export default function AgentsPage() {
  usePageTitle('AI agents')
  const [params] = useSearchParams()
  const { requestId, status, result, error, open, rerun } = useCurrentAnalysis()
  const requested = params.get('request')

  useEffect(() => {
    if (requested && requested !== requestId) open(requested)
  }, [requested, requestId, open])

  const runs = result?.agent_runs
  const { done, total } = progressOf(status?.agents)
  const longest = runs ? Object.values(runs).reduce((s, r) => Math.max(s, r.duration_s ?? 0), 0) : null

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Multi agent intelligence" title="AI agents"
                  description={status ? `${status.symbols?.join(', ')} · ${JOB_TEXT[status.status] || status.status}` : 'A LangGraph supervisor coordinates five specialist agents and a report step. Start or open an analysis to watch them work.'}
                  actions={
                    <>
                      {['failed', 'interrupted'].includes(status?.status) && <Button variant="secondary" size="sm" onClick={rerun}><ArrowClockwise size={16} aria-hidden="true" /> Run again</Button>}
                      {!status && <Button to="/app/analysis" size="sm"><Lightning size={16} weight="fill" aria-hidden="true" /> Start an analysis</Button>}
                    </>
                  } />
      {error && <ErrorState message={error} />}

      {status && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
            <div className="caption-2 text-ink-secondary">Progress</div>
            <div className="mt-2 figure-1 text-ink"><AnimatedNumber value={done} format={(v) => Math.round(v)} /> of {total}</div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-raised" aria-hidden="true">
              <div className="h-full origin-left rounded-full bg-brand transition-transform duration-500 ease-nv" style={{ transform: `scaleX(${done / total})` }} />
            </div>
          </div>
          <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
            <div className="caption-2 text-ink-secondary">Started</div>
            <div className="mt-2 figure-2 text-ink">{fmtDateTime(status.requested_at)}</div>
            <Meta className="mt-1 block">{status.completed_at ? `finished ${fmtDateTime(status.completed_at)}` : 'still running'}</Meta>
          </div>
          <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
            <div className="caption-2 text-ink-secondary">Longest step</div>
            <div className="mt-2 figure-2 text-ink">{longest ? `${num(longest, 1)} s` : 'n/a'}</div>
            <Meta className="mt-1 block">{longest ? 'measured by the workflow' : 'timings appear when the run finishes'}</Meta>
          </div>
        </div>
      )}

      <AgentNetwork status={status} result={result} runs={runs} />

      <Reveal>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2"><WorkflowGraph status={status} runs={runs} /></div>
          <History current={requestId} />
        </div>
      </Reveal>

      {status && <Reveal><AgentCards status={status} result={result} runs={runs} /></Reveal>}

      {status?.status_history?.length > 0 && (
        <Reveal>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card title="Status history" icon={ClockCounterClockwise}>
              <ol className="space-y-2">
                {status.status_history.map((e) => (
                  <li key={`${e.status}-${e.at}`} className="flex flex-wrap items-center gap-x-4 gap-y-1">
                    <Meta className="w-36">{fmtDateTime(e.at)}</Meta>
                    <ToneBadge value={e.status} />
                    {e.reason && <span className="caption-5 text-ink-muted">{e.reason}</span>}
                  </li>
                ))}
              </ol>
            </Card>
            {result?.validation_summary && (
              <Card title="Output validation" subtitle="Checks run on every agent result before the report is written" icon={ShieldCheck}>
                <dl className="grid grid-cols-2 gap-4">
                  <div><dt className="caption-5 text-ink-muted">Issues found</dt><dd className="figure-1 text-ink">{result.validation_summary.issue_count ?? 0}</dd></div>
                  <div><dt className="caption-5 text-ink-muted">AI texts replaced</dt><dd className="figure-1 text-ink">{result.validation_summary.text_replacements ?? 0}</dd></div>
                  <div><dt className="caption-5 text-ink-muted">Portfolio candidates</dt><dd className="figure-1 text-ink">{result.validation_summary.portfolio_candidates?.length ?? 0}</dd></div>
                  <div><dt className="caption-5 text-ink-muted">Left out of portfolio</dt><dd className="figure-1 text-ink">{Object.keys(result.validation_summary.excluded_from_portfolio || {}).length}</dd></div>
                </dl>
              </Card>
            )}
          </div>
        </Reveal>
      )}
    </div>
  )
}
