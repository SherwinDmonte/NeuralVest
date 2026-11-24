// How it works, told as a scroll story: the supervisor diagram stays pinned while each step
// scrolls past and lights up its agent. On phones it is a simple vertical timeline.
import { ChartLineUp, ChartPieSlice, CheckCircle, FileText, Graph, Newspaper, Receipt, ShieldWarning, User } from '@phosphor-icons/react'
import { num, shortSymbol } from '../utils/format'
import { RUN_DATE, RUN_SYMBOLS, STORY } from './content'
import { useActiveStep } from './hooks'
import { Section, SectionHeading } from './Section'

const ICONS = {
  input: User, market_research: ChartLineUp, financial_news: Newspaper, stock_analysis: Receipt,
  risk_assessment: ShieldWarning, portfolio_optimization: ChartPieSlice, report: FileText,
}
const NODES = STORY.slice(1) // the six steps around the supervisor
const POS = NODES.map((_, i) => {
  const a = (-90 + i * 60) * (Math.PI / 180)
  return { x: 50 + 36 * Math.cos(a), y: 50 + 36 * Math.sin(a) }
})

function Diagram({ active }) {
  return (
    <div className="relative aspect-square w-full max-w-[460px]">
      <div className="absolute inset-[8%] rounded-full border border-dashed border-line" aria-hidden="true" />
      <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" aria-hidden="true">
        {POS.map((p, i) => {
          const step = i + 1
          const state = active > step ? 'done' : active === step ? 'on' : 'off'
          return (
            <line key={i} x1="50" y1="50" x2={p.x} y2={p.y} strokeWidth={state === 'on' ? 0.9 : 0.5} strokeLinecap="round"
                  stroke={state === 'off' ? 'var(--nv-line-strong)' : state === 'done' ? 'var(--nv-good)' : 'var(--nv-accent)'}
                  className={state === 'on' ? 'nv-flow' : ''}
                  style={{ transition: 'stroke 500ms var(--ease-nv)', ...(state === 'on' ? { strokeDasharray: '1.6 1.4' } : {}) }} />
          )
        })}
      </svg>
      <div className="absolute left-1/2 top-1/2 grid -translate-x-1/2 -translate-y-1/2 place-items-center">
        <div className={`grid h-20 w-20 place-items-center rounded-2xl border bg-surface shadow-float transition-colors duration-500 ease-nv ${active === 0 || active === 6 ? 'border-accent' : 'border-line-strong'}`}>
          <Graph size={28} className="text-accent-ink" aria-hidden="true" />
        </div>
        <span className="mt-2 rounded-md bg-page/90 px-1.5 caption-3 text-ink">Supervisor</span>
      </div>
      {NODES.map((n, i) => {
        const Icon = ICONS[n.key]
        const step = i + 1
        const state = active > step ? 'done' : active === step ? 'on' : 'off'
        return (
          <div key={n.key} className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center" style={{ left: `${POS[i].x}%`, top: `${POS[i].y}%` }}>
            <div className={`relative grid h-12 w-12 place-items-center rounded-xl border bg-surface transition-[border-color,transform,box-shadow] duration-500 ease-nv ${
              state === 'on' ? 'scale-110 border-accent shadow-float' : state === 'done' ? 'border-good/60' : 'border-line'}`}>
              <Icon size={20} className={state === 'off' ? 'text-ink-muted' : 'text-ink'} aria-hidden="true" />
              {state === 'done' && <CheckCircle size={14} weight="fill" className="absolute -right-1.5 -top-1.5 rounded-full bg-surface text-good" aria-hidden="true" />}
            </div>
            <span className={`mt-1 whitespace-nowrap rounded-md bg-page/90 px-1.5 caption-4 transition-colors duration-500 ease-nv ${state === 'off' ? 'text-ink-muted' : 'text-ink'}`}>{n.title.replace('A report you can check', 'Report')}</span>
          </div>
        )
      })}
      <div className={`absolute left-1/2 top-[-2%] -translate-x-1/2 rounded-full border px-3 py-1 figure caption-4 transition-colors duration-500 ease-nv ${active === 0 ? 'border-accent bg-accent/10 text-ink' : 'border-line bg-surface text-ink-muted'}`}>
        {RUN_SYMBOLS.map(shortSymbol).join(' · ')}
      </div>
    </div>
  )
}

export default function AgentStory() {
  const [active, register] = useActiveStep(STORY.length)
  return (
    <Section id="how">
      <SectionHeading eyebrow="How it works" title="Five specialists and a supervisor that checks their work">
        A LangGraph supervisor runs each agent in order, retries a step once when a data source is briefly down, and
        validates every output before the report is written.
      </SectionHeading>

      <div className="mt-12 grid gap-12 lg:grid-cols-2">
        <div className="hidden lg:block">
          <div className="sticky top-28 flex justify-center pt-6"><Diagram active={active} /></div>
        </div>
        <ol className="relative border-l border-line pl-6 lg:border-l-0 lg:pl-0">
          {STORY.map((s, i) => {
            const Icon = ICONS[s.key]
            const on = active === i
            return (
              <li key={s.key} ref={register(i)} data-step={i}
                  className={`relative py-6 transition-opacity duration-500 ease-nv lg:flex lg:min-h-[46vh] lg:items-center lg:py-0 ${on ? 'lg:opacity-100' : 'lg:opacity-40'}`}>
                <span className="absolute -left-[37px] top-7 grid h-6 w-6 place-items-center rounded-full border border-line bg-surface lg:hidden" aria-hidden="true">
                  <Icon size={12} className="text-ink-secondary" />
                </span>
                <div>
                  <p className="flex items-center gap-3 figure caption-3 text-accent-ink">
                    {String(i + 1).padStart(2, '0')}
                    {s.agent && <span className="caption-4 font-sans text-ink-muted">{s.agent}</span>}
                  </p>
                  <h3 className="mt-2 heading-6 text-ink">{s.title}</h3>
                  <p className="mt-2 max-w-md body-3 text-ink-secondary">{s.text}</p>
                  {s.seconds != null && (
                    <p className="mt-3 figure caption-5 text-ink-muted">{num(s.seconds, 1)} s in the {RUN_DATE} run</p>
                  )}
                </div>
              </li>
            )
          })}
        </ol>
      </div>
    </Section>
  )
}
