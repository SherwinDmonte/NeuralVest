// "Trace any number": an untraced summary (an example written for this page) beside a passage
// built from the real run, where every number opens the calculation behind it.
import { useState } from 'react'
import { ArrowsLeftRight, Cpu, Database, Function as FunctionIcon, Question, SealCheck } from '@phosphor-icons/react'
import { shortSymbol } from '../utils/format'
import { FIRST, RUN_DATE, traceById } from './content'
import { Section, SectionHeading } from './Section'

function Num({ id, active, onPick }) {
  const t = traceById[id]
  if (!t) return null
  const on = active === id
  return (
    <button type="button" aria-pressed={on} onClick={() => onPick(id)} onMouseEnter={() => onPick(id)} onFocus={() => onPick(id)}
            className={`inline-flex items-baseline rounded-md border px-1.5 figure transition-[background-color,border-color,color] duration-300 ease-nv active:scale-[0.98] ${
              on ? 'border-accent bg-accent/15 text-ink' : 'border-line-strong bg-raised text-ink hover:border-accent'}`}>
      {t.value}
    </button>
  )
}

function Detail({ id }) {
  const t = traceById[id]
  return (
    <div key={id} className="lp-swap rounded-xl border border-line bg-page p-4" aria-live="polite">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <span className="title-3 text-ink">{t.label}</span>
        <span className="figure-2 text-ink">{t.value}</span>
      </div>
      <dl className="mt-3 grid gap-3 sm:grid-cols-3">
        {[[Cpu, 'Computed by', `${t.agent} agent`], [FunctionIcon, 'How', t.how], [Database, 'Data', t.data]].map(([Icon, k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="flex items-center gap-1 caption-4 text-ink-muted"><Icon size={13} aria-hidden="true" />{k}</dt>
            <dd className="mt-1 caption-2 text-ink-secondary">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

export default function TraceDemo() {
  const [active, setActive] = useState('ret')
  const n = (id) => <Num id={id} active={active} onPick={setActive} />
  return (
    <Section id="trace">
      <SectionHeading eyebrow="The difference" title="Most stock summaries give you a verdict. This one shows the working.">
        Python computes every number from named sources. A small local model only explains them, and its text is
        rejected when it invents a figure or contradicts a computed reading.
      </SectionHeading>

      <div className="mt-12 grid gap-4 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <figure className="flex flex-col self-start rounded-2xl border border-line bg-surface/60 p-6">
          <figcaption className="flex items-center gap-2 caption-4 text-ink-muted"><Question size={14} aria-hidden="true" /> A typical untraced summary</figcaption>
          <blockquote className="mt-4 heading-6 font-medium text-ink-secondary">
            “Reliance has fallen around 10% this year<sup className="text-warning" aria-hidden="true">?</sup> and looks fairly volatile,
            with roughly market level risk<sup className="text-warning" aria-hidden="true">?</sup> and manageable debt.<sup className="text-warning" aria-hidden="true">?</sup>”
          </blockquote>
          <p className="mt-6 caption-5 text-ink-muted">
            An example written for this page. Which year? Compared with what? Computed how? There is no way to check.
          </p>
        </figure>

        <figure className="rounded-2xl border border-line bg-surface p-6 shadow-card">
          <figcaption className="flex flex-wrap items-center justify-between gap-2 caption-4 text-ink-muted">
            <span className="flex items-center gap-2"><SealCheck size={14} weight="fill" className="text-good" aria-hidden="true" /> NeuralVest report, run of {RUN_DATE}</span>
            <span className="hidden items-center gap-1 sm:inline-flex"><ArrowsLeftRight size={13} aria-hidden="true" /> Select a number</span>
          </figcaption>
          <p className="mt-4 body-2 leading-8 text-ink">
            Over one year {shortSymbol(FIRST)} returned {n('ret')} against {n('nifty')} for the NIFTY 50. Its annualised
            volatility was {n('vol')}, its beta {n('beta')} and its largest fall from a peak {n('dd')}.
            {traceById.de && <> Debt to equity stood at {n('de')}.</>}
          </p>
          <div className="mt-6"><Detail id={active} /></div>
        </figure>
      </div>
    </Section>
  )
}
