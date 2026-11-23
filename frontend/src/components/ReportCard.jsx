// The unified report (Phase 10): key observations first, then how trustworthy the numbers
// are (traceability, validation), the data limitations, sources and a plain-language glossary.
import { AlertTriangle, BookOpen, Bot, Calculator, CheckCircle2, Link2 } from 'lucide-react'
import { Card, Chip } from './ui'
import { fmtDate } from '../utils/format'

function Section({ icon: Icon, title, count, children }) {
  return (
    <details className="group rounded-lg border border-line">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm text-ink hover:bg-white/[0.02]">
        <Icon className="h-4 w-4 text-ink-muted" aria-hidden="true" />
        <span className="font-medium">{title}</span>
        {count != null && <span className="text-xs text-ink-muted">({count})</span>}
        <span className="ml-auto text-xs text-ink-muted group-open:hidden">Show</span>
        <span className="ml-auto hidden text-xs text-ink-muted group-open:inline">Hide</span>
      </summary>
      <div className="border-t border-line px-3 py-2">{children}</div>
    </details>
  )
}

export default function ReportCard({ report }) {
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
      actions={
        <div className="flex flex-wrap gap-2">
          <Chip>
            {trace.ok ? (
              <CheckCircle2 className="mr-1 inline h-3.5 w-3.5 text-good" aria-hidden="true" />
            ) : (
              <AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-warning" aria-hidden="true" />
            )}
            {trace.ok ? `All ${trace.numbers_checked} numbers traced to agent results` : 'Some numbers could not be traced'}
          </Chip>
          <Chip>{issues === 0 ? 'Output validation: no issues' : `Output validation: ${issues} issue(s)`}</Chip>
          {retries > 0 && <Chip>{retries} step(s) retried</Chip>}
        </div>
      }
    >
      <div className="mb-1 flex items-center gap-1.5 text-xs text-ink-muted">
        {fromLlm ? <Bot className="h-3.5 w-3.5" aria-hidden="true" /> : <Calculator className="h-3.5 w-3.5" aria-hidden="true" />}
        {fromLlm
          ? `Key observations (local ${obs.model}, checked against the computed readings)`
          : `Key observations (from NeuralVest's rule-based readings${obs.reason ? `: ${obs.reason}` : ''})`}
      </div>
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
        {obs.items.map((o) => <li key={o}>{o}</li>)}
      </ul>

      {report.unavailable_sections?.length > 0 && (
        <p className="mt-3 text-xs text-warning">
          Unavailable: {report.unavailable_sections.map((s) => s.replace(':', ' for ').replace(/_/g, ' ')).join('; ')}
        </p>
      )}

      <div className="mt-4 space-y-2">
        <Section icon={AlertTriangle} title="Data limitations" count={report.data_limitations?.length}>
          <ul className="list-disc space-y-1 pl-5 text-xs text-ink-secondary">
            {report.data_limitations.map((l) => <li key={l}>{l}</li>)}
          </ul>
        </Section>
        <Section icon={Link2} title="Sources" count={report.source_references?.length}>
          <ul className="space-y-1 text-xs text-ink-secondary">
            {report.source_references.map((s) => (
              <li key={`${s.agent}-${s.symbol}-${s.source}-${s.detail}`}>
                <span className="text-ink">{s.source}</span>
                {s.detail ? ` · ${s.detail}` : ''}
                {s.symbol ? ` · ${s.symbol}` : ''}
                {s.data_as_of ? ` · data as of ${s.data_as_of}` : ''}
                <span className="text-ink-muted"> ({s.agent?.replace(/_/g, ' ')})</span>
              </li>
            ))}
          </ul>
        </Section>
        <Section icon={BookOpen} title="Glossary" count={Object.keys(report.glossary || {}).length}>
          <ul className="space-y-1.5 text-xs text-ink-secondary">
            {Object.entries(report.glossary).map(([k, v]) => <li key={k}>{v}</li>)}
          </ul>
        </Section>
      </div>
      <p className="mt-3 text-xs text-ink-muted">{report.disclaimers?.join(' ')}</p>
    </Card>
  )
}
