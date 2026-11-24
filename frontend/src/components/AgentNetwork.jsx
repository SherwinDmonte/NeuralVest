// The multi-agent network (Phase 12B, task 12B.4.4): the LangGraph supervisor in the centre,
// connected to the five specialist agents and the report step. Node states, flowing
// connections and pulse rings come only from the status API; nothing is simulated.
import { useId, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  ChartLineUp,
  ChartPieSlice,
  FileText,
  Graph,
  Newspaper,
  Receipt,
  ShieldWarning,
} from '@phosphor-icons/react'
import { AGENTS, STATE, StateIcon, agentErrors, outputSummary } from './AgentStatus'
import { Card, Meta } from './ui'
import { num } from '../utils/format'

// Positions in percent of the canvas (the SVG uses the same 0..100 space).
const LAYOUT = {
  supervisor: { x: 50, y: 50 },
  market_research: { x: 15, y: 20 },
  financial_news: { x: 50, y: 10 },
  stock_analysis: { x: 85, y: 20 },
  risk_assessment: { x: 85, y: 80 },
  portfolio_optimization: { x: 50, y: 90 },
  report: { x: 15, y: 80 },
}
const ICONS = {
  market_research: ChartLineUp, financial_news: Newspaper, stock_analysis: Receipt,
  risk_assessment: ShieldWarning, portfolio_optimization: ChartPieSlice, report: FileText,
}
const RING = {
  running: 'border-accent shadow-[0_0_0_4px_color-mix(in_srgb,var(--nv-accent)_25%,transparent),0_0_32px_-4px_var(--nv-accent)]',
  completed: 'border-good/60',
  partial: 'border-warning/70',
  failed: 'border-critical/70',
  interrupted: 'border-critical/70',
  skipped: 'border-line opacity-60',
  pending: 'border-line',
}

function supervisorState(status) {
  const s = status?.status
  if (!s) return 'pending'
  if (s === 'queued' || s === 'running') return 'running'
  return s
}

export default function AgentNetwork({ status, result, runs }) {
  const [selected, setSelected] = useState('supervisor')
  const gradId = `edge-${useId().replace(/:/g, '')}`
  const stateOf = (key) => (key === 'supervisor' ? supervisorState(status) : status?.agents?.[key] || runs?.[key]?.status || 'pending')
  const nodes = ['supervisor', ...AGENTS.map((a) => a.key)]
  const info = selected === 'supervisor'
    ? { name: 'Supervisor (LangGraph)', does: 'Validates the request, runs each agent in order, retries a step once when a data source is briefly down, validates every output and decides whether the portfolio step runs.' }
    : AGENTS.find((a) => a.key === selected)
  const run = runs?.[selected]
  const summary = selected === 'supervisor' ? null : outputSummary(selected, result)
  const errors = selected === 'supervisor' ? (result?.errors || []).filter((e) => e.agent === 'validate_input') : agentErrors(selected, result)

  return (
    <Card title="Agent network" icon={Graph} accent
          subtitle="Live from the status API. A glowing node is working; a flowing line is the supervisor handing it work. Select a node for its details.">
      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <div className="relative mx-auto aspect-[16/10] w-full max-w-4xl overflow-hidden rounded-2xl border border-line bg-page/60">
          <div className="pointer-events-none absolute inset-0 grid-lines opacity-70" aria-hidden="true" />
          <div className="pointer-events-none absolute left-1/2 top-1/2 h-56 w-56 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent/20 blur-3xl" aria-hidden="true" />
          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              {/* user space units: a bounding box gradient paints nothing on a vertical line */}
              <linearGradient id={gradId} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="100" y2="100">
                <stop offset="0%" stopColor="var(--nv-teal)" />
                <stop offset="55%" stopColor="var(--nv-accent)" />
                <stop offset="100%" stopColor="var(--nv-violet)" />
              </linearGradient>
            </defs>
            {AGENTS.map((a) => {
              const p = LAYOUT[a.key]
              const st = stateOf(a.key)
              const active = st === 'running'
              const done = ['completed', 'partial'].includes(st)
              return (
                <g key={a.key}>
                  <line x1="50" y1="50" x2={p.x} y2={p.y} stroke={done || active ? `url(#${gradId})` : 'var(--nv-line-strong)'}
                        strokeWidth={active ? 2.5 : 1.5} vectorEffect="non-scaling-stroke" opacity={st === 'skipped' ? 0.35 : 1} />
                  {active && <line x1="50" y1="50" x2={p.x} y2={p.y} stroke="var(--nv-ink)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" className="nv-flow" opacity="0.8" />}
                </g>
              )
            })}
          </svg>
          {nodes.map((key) => {
            const p = LAYOUT[key]
            const st = stateOf(key)
            const Icon = key === 'supervisor' ? Graph : ICONS[key]
            const name = key === 'supervisor' ? 'Supervisor' : AGENTS.find((a) => a.key === key).name
            const isSel = selected === key
            return (
              <button key={key} type="button" onClick={() => setSelected(key)} aria-pressed={isSel}
                      aria-label={`${name}: ${(STATE[st] || STATE.pending).label}`}
                      className="group absolute -translate-x-1/2 -translate-y-1/2 focus-visible:outline-none" style={{ left: `${p.x}%`, top: `${p.y}%` }}>
                <span className={`relative flex items-center gap-2 rounded-2xl border bg-surface/90 px-3 py-2 shadow-card backdrop-blur transition-[transform,box-shadow,border-color] duration-300 ease-nv group-hover:-translate-y-0.5 group-focus-visible:ring-2 group-focus-visible:ring-accent ${RING[st] || RING.pending} ${isSel ? 'scale-105' : ''} ${key === 'supervisor' ? 'px-4 py-3' : ''}`}>
                  {st === 'running' && <span className="absolute -inset-1 rounded-2xl border border-accent/60 motion-safe:animate-ping" aria-hidden="true" />}
                  <span className={`grid place-items-center rounded-xl ${key === 'supervisor' ? 'h-9 w-9 bg-brand-button text-white' : 'h-7 w-7 border border-line bg-raised text-accent-ink'}`}>
                    <Icon size={key === 'supervisor' ? 20 : 16} weight={key === 'supervisor' ? 'fill' : 'regular'} aria-hidden="true" />
                  </span>
                  <span className="hidden text-left md:block">
                    <span className={`block whitespace-nowrap ${key === 'supervisor' ? 'title-4' : 'caption-1'} text-ink`}>{name}</span>
                    <span className="flex items-center gap-1 caption-5 text-ink-muted"><StateIcon state={st} size={12} />{(STATE[st] || STATE.pending).label}</span>
                  </span>
                </span>
              </button>
            )
          })}
        </div>

        <AnimatePresence mode="wait">
          <motion.aside key={selected} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }}
                        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                        className="rounded-2xl border border-line glass p-4">
            <div className="flex items-start justify-between gap-3">
              <h3 className="title-3 text-ink">{info?.name}</h3>
              <span className="inline-flex items-center gap-1 caption-4 text-ink-secondary"><StateIcon state={stateOf(selected)} size={14} />{(STATE[stateOf(selected)] || STATE.pending).label}</span>
            </div>
            <p className="mt-2 caption-2 text-ink-secondary">{info?.does}</p>
            {selected !== 'supervisor' && (
              <dl className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-line bg-raised/60 p-3"><dt className="caption-5 text-ink-muted">Time</dt><dd className="figure-2 text-ink">{run?.duration_s != null ? `${num(run.duration_s, 1)} s` : 'n/a'}</dd></div>
                <div className="rounded-xl border border-line bg-raised/60 p-3"><dt className="caption-5 text-ink-muted">Retries</dt><dd className="figure-2 text-ink">{(run?.retries || []).filter((r) => r.retried).length}</dd></div>
              </dl>
            )}
            {selected === 'supervisor' && status && (
              <p className="mt-4 caption-2 text-ink-secondary">{status.symbols?.join(', ')} · {status.status}{status.queue_position ? ` · position ${status.queue_position} in the queue` : ''}</p>
            )}
            {summary?.length > 0 && (
              <div className="mt-4">
                <p className="mb-1 caption-3 text-ink-muted">Output</p>
                <ul className="space-y-1 caption-2 text-ink">{summary.map((s) => <li key={s}>{s}</li>)}</ul>
              </div>
            )}
            {errors.length > 0 && (
              <ul className="mt-4 space-y-1 caption-5 text-critical">{errors.map((e) => <li key={`${e.symbol}-${e.message}`}>{e.symbol ? `${e.symbol}: ` : ''}{e.message}</li>)}</ul>
            )}
            {!status && <Meta className="mt-4 block">Start or open an analysis to see this agent work.</Meta>}
          </motion.aside>
        </AnimatePresence>
      </div>
    </Card>
  )
}
