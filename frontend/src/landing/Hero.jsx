// Hero: the promise on the left, the product on the right. The index card reads the public
// /api/market/indices endpoint (end of day data); if the API cannot be reached it is replaced by
// an excerpt of the real stored run, so nothing on the stage is ever invented.
import { useState } from 'react'
import { ArrowRight, CheckCircle, CircleNotch, Circle, SealCheck } from '@phosphor-icons/react'
import { Button, Change, Skeleton } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { getMarketIndices } from '../services/api'
import { fmtDate, num, shortSymbol } from '../utils/format'
import { CTA, FIRST, RUN_DATE, RUN_SECONDS, STORY, TEST_COUNT, TRACES, snapshot, traceById } from './content'
import { useCycle, useMountVisible, usePointerParallax } from './hooks'
import { LineChart } from './MiniCharts'
import NeuralBackdrop from './NeuralBackdrop'

const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function Float({ depth, className = '', bob = 0, children }) {
  return (
    <div className={className}>
      <div className={bob ? 'lp-float' : ''} style={{ animationDelay: `${bob}s` }}>
        <div className="lp-parallax" style={{ '--depth': `${depth}px` }}>{children}</div>
      </div>
    </div>
  )
}

function IndexChart({ item }) {
  const ref = useMountVisible()
  return (
    <div ref={ref} className="lp-scope mt-4">
      <LineChart data={item.series} series={[{ key: 'close', color: 'var(--nv-accent)' }]} height={170}
                 label={`${item.name} daily close, ${fmtDate(item.series[0].date)} to ${fmtDate(item.date)}`} />
    </div>
  )
}

function IndexCard({ indices }) {
  const [sym, setSym] = useState('^NSEI')
  const items = indices.data?.items || []
  const item = items.find((i) => i.symbol === sym) || items[0]
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-float sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label="Index" className="inline-flex rounded-xl border border-line bg-page p-1">
          {items.map((i) => (
            <button key={i.symbol} type="button" role="tab" aria-selected={i.symbol === item.symbol} onClick={() => setSym(i.symbol)}
                    className={`rounded-lg px-3 py-1 caption-1 transition-colors duration-300 ease-nv ${i.symbol === item.symbol ? 'bg-raised text-ink shadow-card' : 'text-ink-secondary hover:text-ink'}`}>
              {i.name}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-end gap-x-4 gap-y-1">
        <span className="heading-5 figure text-ink sm:heading-4">{num(item.last_close)}</span>
        <Change value={item.change_pct} />
      </div>
      <p className="mt-1 caption-5 text-ink-muted">
        {fmtDate(item.date)} close · previous {num(item.previous_close)} · last {item.series.length} trading days
      </p>
      <p className="caption-5 text-ink-muted">
        <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-good align-middle" aria-hidden="true" />
        Live from the NeuralVest API · end of day data from Yahoo Finance
      </p>
      <IndexChart key={item.symbol} item={item} />
    </div>
  )
}

// Shown when the API is not running: figures from the stored run, labelled as such.
function ReportExcerpt() {
  const s = snapshot.stocks[FIRST]
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-float sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="title-4 text-ink">{s.name}</p>
          <p className="caption-5 text-ink-muted">Report excerpt · run of {RUN_DATE}</p>
        </div>
        <span className="inline-flex items-center gap-1 caption-4 text-ink-secondary"><SealCheck size={14} weight="fill" className="text-good" aria-hidden="true" />{snapshot.run.numbers_traced} numbers traced</span>
      </div>
      <dl className="mt-4 divide-y divide-line">
        {TRACES.slice(0, 5).map((t) => (
          <div key={t.id} className="flex items-baseline justify-between gap-4 py-2">
            <dt className="caption-2 text-ink-secondary">{t.label}</dt>
            <dd className="figure caption-1 text-ink">{t.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function TracedCard() {
  const t = traceById.beta
  return (
    <a href="#trace" className="group block w-72 rounded-2xl border border-line glass-strong p-4 shadow-float transition-[border-color,transform] duration-500 ease-nv hover:-translate-y-0.5 hover:border-line-strong">
      <span className="inline-flex items-center gap-1 caption-4 text-good"><SealCheck size={14} weight="fill" aria-hidden="true" /> Traced</span>
      <div className="mt-2 flex items-baseline justify-between gap-3">
        <span className="caption-2 text-ink-secondary">{t.label}</span>
        <span className="figure-2 text-ink">{t.value}</span>
      </div>
      <p className="mt-1 figure caption-5 text-ink-muted">↳ {t.agent.toLowerCase()} · {t.data}</p>
      <p className="mt-3 caption-4 text-accent-ink transition-colors duration-300 ease-nv group-hover:text-ink">See how it was computed →</p>
    </a>
  )
}

const SHORT = { market_research: 'Market', financial_news: 'News', stock_analysis: 'Ratios', risk_assessment: 'Risk', portfolio_optimization: 'Portfolio', report: 'Report' }
const STEPS = STORY.slice(1)

function PipelineCard() {
  const tick = useCycle(STEPS.length + 2, 1300)
  const active = reduce ? STEPS.length : Math.min(tick, STEPS.length)
  return (
    <div className="w-[340px] max-w-full rounded-2xl border border-line glass-strong p-4 shadow-float">
      <div className="flex items-center justify-between gap-3">
        <span className="title-5 text-ink">How a run progresses</span>
        <span className="caption-5 text-ink-muted">{active >= STEPS.length ? 'Report ready' : `Step ${active + 1} of ${STEPS.length}`}</span>
      </div>
      <ol className="mt-3 grid grid-cols-2 gap-1.5">
        {STEPS.map((s, i) => {
          const state = i < active ? 'done' : i === active ? 'running' : 'pending'
          return (
            <li key={s.key} className={`flex min-w-0 items-center gap-2 rounded-lg px-2 py-1 caption-4 transition-colors duration-500 ease-nv ${state === 'running' ? 'bg-raised text-ink' : state === 'done' ? 'text-ink-secondary' : 'text-ink-muted'}`}>
              {state === 'done' && <CheckCircle size={14} weight="fill" className="shrink-0 text-good" aria-hidden="true" />}
              {state === 'running' && <CircleNotch size={14} className="shrink-0 animate-spin text-accent-ink" aria-hidden="true" />}
              {state === 'pending' && <Circle size={14} className="shrink-0" aria-hidden="true" />}
              <span className="min-w-0 flex-1 truncate">{SHORT[s.key]}</span>
              {s.seconds != null && state === 'done' && <span className="figure caption-5 text-ink-muted">{num(s.seconds, 1)} s</span>}
            </li>
          )
        })}
      </ol>
      <p className="mt-3 caption-5 text-ink-muted">Step times from the {RUN_DATE} run of {snapshot.run.symbols.map(shortSymbol).join(' and ')}: {RUN_SECONDS} s in all on a laptop CPU</p>
    </div>
  )
}

export default function Hero() {
  const stage = usePointerParallax()
  const indices = useApi(getMarketIndices, [], { key: 'indices', ttl: 10 * 60 * 1000 })
  const live = indices.data?.items?.length > 0

  return (
    <section ref={stage} className="relative isolate overflow-hidden">
      <div className="absolute inset-0 -z-10 [mask-image:radial-gradient(ellipse_80%_70%_at_60%_30%,black,transparent_80%)]">
        <div className="lp-parallax absolute -inset-6" style={{ '--depth': '-10px' }}><NeuralBackdrop /></div>
      </div>
      <div className="mx-auto grid w-full max-w-7xl items-center gap-12 px-4 pb-16 pt-32 sm:px-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:pb-24 lg:pt-40">
        <div className="lp-enter">
          <p className="mb-6 inline-flex items-center gap-2 rounded-full border border-line bg-surface/70 px-3 py-1 caption-4 text-ink-secondary">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" /> Five local AI agents for NSE and BSE stocks
          </p>
          <h1 className="max-w-[680px] heading-3 text-ink sm:heading-2 2xl:heading-1">
            <span className="block">Understand an Indian stock</span>
            <span className="block text-brand">with every number traced</span>
          </h1>
          <p className="mt-6 max-w-[560px] body-3 text-ink-secondary lg:body-7">
            NeuralVest runs five AI agents on your own computer. They read prices, news, annual statements and risk,
            then write a report in which every figure leads back to the Python calculation that produced it.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-4">
            <Button to="/register" size="lg">{CTA}<ArrowRight size={16} aria-hidden="true" /></Button>
            <a href="#explore" className="body-5 text-ink-secondary underline-offset-4 transition-colors duration-300 ease-nv hover:text-ink hover:underline">Explore a real report</a>
          </div>
          <p className="mt-8 figure caption-5 text-ink-muted">Open source · {TEST_COUNT} automated tests · runs on an 8 GB laptop · free</p>
        </div>

        <div className="lp-enter relative [animation-delay:150ms] lg:h-[680px]">
          <Float depth={6} className="lg:absolute lg:left-0 lg:right-10 lg:top-20">
            {indices.loading && !indices.data ? <Skeleton className="h-[380px] rounded-2xl" /> : live ? <IndexCard indices={indices} /> : <ReportExcerpt />}
          </Float>
          <div className="mt-4 flex flex-wrap gap-4 lg:mt-0">
            {live && (
              <Float depth={16} bob={0.4} className="lg:absolute lg:-right-2 lg:top-0 lg:z-10">
                <TracedCard />
              </Float>
            )}
            <Float depth={22} bob={1.6} className="hidden sm:block lg:absolute lg:bottom-0 lg:left-[-16px] lg:z-10">
              <PipelineCard />
            </Float>
          </div>
        </div>
      </div>
    </section>
  )
}
