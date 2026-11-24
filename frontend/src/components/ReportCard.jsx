// The unified report (Phase 10): key observations first, then how trustworthy the numbers are
// (traceability, validation), the data limitations, sources and a plain language glossary.
import { useState } from 'react'
import { BookOpen, Calculator, CheckCircle, DownloadSimple, LinkSimple, Robot, Warning } from '@phosphor-icons/react'
import { Button, Card, Meta } from './ui'
import { downloadReportPdf, errorMessage } from '../services/api'
import { fmtDate } from '../utils/format'

function Section({ icon: Icon, title, count, children }) {
  return (
    <details className="group rounded-xl border border-line">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded-xl px-4 py-3 body-5 text-ink transition-colors duration-300 ease-nv hover:bg-raised/50">
        <Icon size={16} className="text-ink-muted" aria-hidden="true" />
        <span>{title}</span>
        {count != null && <Meta>{count}</Meta>}
        <span className="ml-auto caption-5 text-ink-muted group-open:hidden">Show</span>
        <span className="ml-auto hidden caption-5 text-ink-muted group-open:inline">Hide</span>
      </summary>
      <div className="border-t border-line px-4 py-3">{children}</div>
    </details>
  )
}

export function PdfButton({ reportId, size = 'sm', variant = 'secondary' }) {
  const [state, setState] = useState({ busy: false, error: null })
  if (!reportId) return null
  const download = async () => {
    setState({ busy: true, error: null })
    try {
      await downloadReportPdf(reportId)
      setState({ busy: false, error: null })
    } catch (err) {
      setState({ busy: false, error: errorMessage(err) })
    }
  }
  return (
    <span className="inline-flex flex-col items-end gap-1">
      <Button variant={variant} size={size} onClick={download} disabled={state.busy}>
        <DownloadSimple size={16} aria-hidden="true" />
        {state.busy ? 'Preparing PDF' : 'Download PDF'}
      </Button>
      {state.error && <span role="alert" className="caption-5 text-critical">{state.error}</span>}
    </span>
  )
}

export default function ReportCard({ report, reportId }) {
  if (!report?.key_observations) return null
  const obs = report.key_observations
  const fromLlm = obs.source === 'llm'
  const trace = report.traceability || {}
  const issues = report.execution?.validation_issue_count ?? 0
  const retries = (report.execution?.retries || []).filter((r) => r.retried).length
  return (
    <Card
      title="Analysis report"
      subtitle={`Generated ${fmtDate(report.generated_at)} · ${report.request?.symbols?.join(', ')}`}
      actions={<PdfButton reportId={reportId} />}
    >
      <div className="space-y-6">
        <div className="flex flex-wrap gap-x-6 gap-y-2 caption-2 text-ink-secondary">
          <span className="inline-flex items-center gap-2">
            {trace.ok ? <CheckCircle size={16} className="text-good" aria-hidden="true" /> : <Warning size={16} className="text-warning" aria-hidden="true" />}
            {trace.ok ? `All ${trace.numbers_checked} numbers traced to agent results` : 'Some numbers could not be traced'}
          </span>
          <span className="inline-flex items-center gap-2">
            {issues === 0 ? <CheckCircle size={16} className="text-good" aria-hidden="true" /> : <Warning size={16} className="text-warning" aria-hidden="true" />}
            {issues === 0 ? 'Output validation found no issues' : `Output validation found ${issues} issue(s)`}
          </span>
          {retries > 0 && <span>{retries} step(s) retried after a temporary error</span>}
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 caption-4 text-ink-muted">
            {fromLlm ? <Robot size={16} aria-hidden="true" /> : <Calculator size={16} aria-hidden="true" />}
            {fromLlm
              ? `Key observations by the local ${obs.model} model, checked against the computed readings`
              : `Key observations from NeuralVest's rule based readings${obs.reason ? ` (${obs.reason})` : ''}`}
          </div>
          <ul className="list-disc space-y-1 pl-5 body-6 text-ink">
            {obs.items.map((o) => <li key={o}>{o}</li>)}
          </ul>
          {report.unavailable_sections?.length > 0 && (
            <p className="mt-3 caption-5 text-warning">
              Unavailable: {report.unavailable_sections.map((s) => s.replace(':', ' for ').replaceAll('_', ' ')).join('; ')}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Section icon={Warning} title="Data limitations" count={report.data_limitations?.length}>
            <ul className="list-disc space-y-1 pl-5 caption-2 text-ink-secondary">
              {report.data_limitations.map((l) => <li key={l}>{l}</li>)}
            </ul>
          </Section>
          <Section icon={LinkSimple} title="Sources" count={report.source_references?.length}>
            <ul className="space-y-1 caption-2 text-ink-secondary">
              {report.source_references.map((s) => (
                <li key={`${s.agent}-${s.symbol}-${s.source}-${s.detail}`}>
                  <span className="text-ink">{s.source}</span>
                  {s.detail ? ` · ${s.detail}` : ''}
                  {s.symbol ? ` · ${s.symbol}` : ''}
                  {s.data_as_of ? ` · data as of ${s.data_as_of}` : ''}
                  <span className="text-ink-muted"> ({s.agent?.replaceAll('_', ' ')})</span>
                </li>
              ))}
            </ul>
          </Section>
          <Section icon={BookOpen} title="Glossary" count={Object.keys(report.glossary || {}).length}>
            <ul className="space-y-2 caption-2 text-ink-secondary">
              {Object.entries(report.glossary).map(([k, v]) => <li key={k}>{v}</li>)}
            </ul>
          </Section>
        </div>
        <p className="caption-5 text-ink-muted">{report.disclaimers?.join(' ')}</p>
      </div>
    </Card>
  )
}
