// Landing page (task 12.3.1), built with the landing-page-design skill (layout A: classic hero
// plus sections) and unslop (asymmetric hero with a product preview built in code).
// One offer, one audience (Indian retail investors and finance students), one primary action:
// "Create a free account". Every fact on this page is true of the project; the preview uses
// figures from a real run on 23 Nov 2026 and says so.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CaretDown, CheckCircle, GithubLogo, List, X } from '@phosphor-icons/react'
import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/ui'
import { Logo } from '../components/Logo'
import { useReveal, useWordReveal } from '../hooks/useReveal'
import { usePageTitle } from '../hooks/usePageTitle'

const REPO = 'https://github.com/SherwinDmonte/NeuralVest'
const CTA = 'Create a free account'
const LINKS = [
  { href: '#how', label: 'How it works' },
  { href: '#agents', label: 'Agents' },
  { href: '#faq', label: 'FAQ' },
]

// ------------------------------------------------------------------ navigation
function Nav() {
  const [open, setOpen] = useState(false)
  const { user } = useAuth()
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])
  const primary = user ? { to: '/app', label: 'Open the app' } : { to: '/register', label: CTA }

  return (
    <>
      <header className="fixed inset-x-0 top-4 z-40 flex justify-center px-4">
        <nav aria-label="Main" className="flex w-full max-w-3xl items-center justify-between gap-4 rounded-2xl border border-line bg-page/70 py-2 pl-4 pr-2 backdrop-blur-xl md:w-fit md:max-w-none">
          <Logo />
          <ul className="hidden items-center gap-1 md:flex">
            {LINKS.map((l) => (
              <li key={l.href}>
                <a href={l.href} className="rounded-lg px-3 py-2 body-5 text-ink-secondary transition-colors duration-300 ease-nv hover:text-ink">{l.label}</a>
              </li>
            ))}
          </ul>
          <div className="hidden items-center gap-1 md:flex">
            {!user && <Link to="/login" className="rounded-lg px-3 py-2 body-5 text-ink-secondary transition-colors duration-300 ease-nv hover:text-ink">Log in</Link>}
            <Button to={primary.to} size="sm">{primary.label}</Button>
          </div>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            aria-controls="landing-menu"
            aria-label={open ? 'Close menu' : 'Open menu'}
            className="relative grid h-10 w-10 place-items-center rounded-lg text-ink transition-colors duration-300 ease-nv hover:bg-raised md:hidden"
          >
            <List size={20} className={`absolute transition-[transform,opacity] duration-500 ease-nv ${open ? 'rotate-90 opacity-0' : 'opacity-100'}`} aria-hidden="true" />
            <X size={20} className={`absolute transition-[transform,opacity] duration-500 ease-nv ${open ? 'opacity-100' : '-rotate-90 opacity-0'}`} aria-hidden="true" />
          </button>
        </nav>
      </header>
      <div
        id="landing-menu"
        inert={!open}
        className={`fixed inset-0 z-30 flex flex-col bg-page/95 px-6 pb-8 pt-24 backdrop-blur-xl transition-opacity duration-500 ease-nv md:hidden ${open ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
      >
        <ul className="space-y-2">
          {[...LINKS, ...(user ? [] : [{ to: '/login', label: 'Log in' }])].map((l, i) => {
            const cls = `block py-2 heading-5 text-ink transition-[transform,opacity] duration-500 ease-nv ${open ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'}`
            const style = { transitionDelay: open ? `${Math.min(i * 60, 400)}ms` : '0ms' }
            return (
              <li key={l.label}>
                {l.to ? <Link to={l.to} className={cls} style={style}>{l.label}</Link>
                  : <a href={l.href} onClick={() => setOpen(false)} className={cls} style={style}>{l.label}</a>}
              </li>
            )
          })}
        </ul>
        <Button to={primary.to} className="mt-auto w-full">{primary.label}</Button>
      </div>
    </>
  )
}

// ------------------------------------------------------------------ hero preview (the moment)
const PREVIEW_AGENTS = ['Market research', 'Financial news', 'Stock analysis', 'Risk assessment', 'Portfolio', 'Report']
const PREVIEW_FIGURES = [
  ['RELIANCE.NS, 1 year', '−11.44%', 'market research'],
  ['NIFTY 50, same year', '−1.98%', 'market research'],
  ['Annualised volatility', '24.37%', 'risk assessment'],
  ['Beta vs NIFTY 50', '0.97', 'risk assessment'],
  ['Debt to equity', '0.44', 'stock analysis'],
]

function HeroPreview() {
  return (
    <figure className="relative">
      <div className="rounded-2xl border border-line bg-surface p-2 shadow-[0_24px_64px_rgba(0,0,0,0.45)]">
        <div className="rounded-xl border border-line bg-page p-4 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="title-4 text-ink">RELIANCE.NS and TCS.NS</div>
              <div className="caption-5 text-ink-muted">Analysis finished in about 90 seconds on a laptop CPU</div>
            </div>
            <span className="inline-flex items-center gap-1 caption-4 text-ink-secondary">
              <CheckCircle size={14} weight="fill" className="text-good" aria-hidden="true" /> Completed
            </span>
          </div>
          <ol className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {PREVIEW_AGENTS.map((a) => (
              <li key={a} className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 caption-4 text-ink-secondary">
                <CheckCircle size={14} weight="fill" className="shrink-0 text-good" aria-hidden="true" />{a}
              </li>
            ))}
          </ol>
          <div className="mt-4 rounded-lg border border-line bg-surface p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="title-5 text-ink">Report excerpt</span>
              <span className="inline-flex items-center gap-1 caption-5 text-ink-muted">
                <CheckCircle size={12} className="text-good" aria-hidden="true" /> 125 of 125 numbers traced
              </span>
            </div>
            <dl className="mt-3 divide-y divide-line">
              {PREVIEW_FIGURES.map(([label, value, agent]) => (
                <div key={label} className="grid grid-cols-[1fr_auto] items-baseline gap-x-4 py-2">
                  <dt className="caption-2 text-ink-secondary">{label}</dt>
                  <dd className="figure caption-1 text-ink">{value}</dd>
                  <dd className="col-span-2 figure caption-5 text-ink-muted"><span aria-hidden="true">↳ </span>{agent}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 caption-5 text-ink-secondary">The stock underperformed the NIFTY 50 over the period.</p>
          </div>
        </div>
      </div>
      <figcaption className="mt-3 caption-5 text-ink-muted">Figures from a real analysis on 23 Nov 2026. Past data, not a recommendation.</figcaption>
    </figure>
  )
}

// ------------------------------------------------------------------ sections
function Section({ id, children, className = '' }) {
  const ref = useReveal()
  return (
    <section id={id} ref={ref} className={`reveal mx-auto w-full max-w-6xl scroll-mt-24 px-4 py-16 sm:px-6 lg:py-24 ${className}`}>
      {children}
    </section>
  )
}

function Eyebrow({ children }) {
  return <p className="mb-3 caption-1 text-accent-ink">{children}</p>
}

const BENEFITS = [
  ['See the working', 'Every figure in a report is matched to the agent result that produced it. Anything that cannot be matched is listed, not hidden.'],
  ['Runs on your computer', 'The AI model runs locally through Ollama. No paid API, no subscription, and an 8 GB laptop is enough.'],
  ['Plain language', 'Rule based readings sit next to the AI text, and each report explains its own terms in a glossary.'],
  ['A portfolio you can question', 'Rupee amounts in whole shares, tested on past prices against equal weights and the NIFTY 50, with every fallback stated.'],
]

const STEPS = [
  ['Pick your stocks', 'Type NSE symbols like RELIANCE or BSE codes like 500325. Add an amount and a risk preference for an illustrative portfolio.'],
  ['Five agents do the work', 'Prices and indicators, news and sentiment, annual statements, historical risk and the portfolio. Two stocks take about 90 seconds; you can watch each agent.'],
  ['Read and keep the report', 'Key observations, sources, data limitations and a glossary. Reports stay in your account, can be compared and download as a PDF.'],
]

const AGENTS = [
  ['Market Research', 'Daily prices, moving averages, RSI, MACD and the comparison with the NIFTY 50.'],
  ['Financial News', 'Recent headlines from Indian business feeds, summarised with a sentiment for each.'],
  ['Stock Analysis', 'Ratios from the annual statements: growth, margins, return on equity, debt.'],
  ['Risk Assessment', 'Volatility, beta, maximum drawdown and the Sharpe ratio against the 91 day T bill rate.'],
  ['Portfolio Optimization', 'Weights, whole shares and a walk forward backtest for two or more stocks.'],
]

const STACK = ['React and Tailwind', 'FastAPI', 'LangGraph supervisor', 'Ollama with Qwen3', 'MongoDB Atlas', 'ReportLab PDF']

const FAQ = [
  ['Is NeuralVest investment advice?', 'No. It is an educational project and not a SEBI registered adviser. Reports describe what happened in the past and suggest nothing about what you should buy or sell.'],
  ['Is the market data real time?', 'No. Prices are end of day data from Yahoo Finance through the yfinance library and can be delayed. Every report shows the date its data is from.'],
  ['Which stocks can I analyse?', 'Any NSE symbol or BSE code that Yahoo Finance covers, up to 10 in one analysis. The NIFTY 50 is the benchmark for every comparison.'],
  ['How accurate is the AI text?', 'The numbers are always computed in Python. The local model only explains them, and its text is rejected when it uses a number that is not in the data or contradicts a computed reading. Its wording can still be clumsy, so the rule based readings are shown beside it.'],
  ['Does my data leave my computer?', 'The AI model runs on your machine. Prices and news are downloaded from public sources, and your account and reports are stored in your own MongoDB Atlas database.'],
  ['What do I need to run it?', 'Python 3.12, Node, Ollama with a Qwen3 model and a free MongoDB Atlas cluster. It was built and measured on an 8 GB Windows laptop without a graphics card.'],
  ['How long does an analysis take?', 'About 30 to 60 seconds for one stock and about 90 seconds for two on a laptop CPU, most of it spent by the local AI model writing explanations.'],
  ['What does it cost?', 'Nothing. Every tool it uses is free, and the code is open source on GitHub.'],
]

function TaglineReveal() {
  const ref = useWordReveal()
  const lines = ['Every number has a source.', 'Every sentence is checked against it.']
  return (
    <section aria-label="What NeuralVest promises" className="mx-auto w-full max-w-6xl px-4 py-24 sm:px-6 lg:py-24">
      <p ref={ref} className="max-w-[680px] heading-3 lg:heading-1">
        {lines.map((line, li) => (
          <span key={line} className="block">
            {line.split(' ').map((w, wi) => (
              <span key={`${li}-${wi}`} className="tagline-word">{w}{wi < line.split(' ').length - 1 ? ' ' : ''}</span>
            ))}
          </span>
        ))}
      </p>
    </section>
  )
}

function FaqItem({ q, a }) {
  return (
    <details className="group border-b border-line">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 title-3 text-ink">
        <h3>{q}</h3>
        <CaretDown size={16} className="shrink-0 text-ink-muted transition-transform duration-500 ease-nv group-open:rotate-180" aria-hidden="true" />
      </summary>
      <p className="pb-4 body-6 text-ink-secondary">{a}</p>
    </details>
  )
}

function FinalCta() {
  return (
    <div className="rounded-2xl border border-line bg-surface p-6 sm:p-12">
      <h2 className="max-w-[680px] heading-4 text-ink lg:heading-3">Read your next stock with the working shown</h2>
      <p className="mt-4 max-w-[680px] body-3 text-ink-secondary">
        Free and open source. No card, no trial period, nothing to cancel.
      </p>
      <div className="mt-8 flex flex-wrap items-center gap-4">
        <Button to="/register">{CTA}<ArrowRight size={16} aria-hidden="true" /></Button>
        <a href={REPO} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 body-5 text-ink-secondary transition-colors duration-300 ease-nv hover:text-ink">
          <GithubLogo size={18} aria-hidden="true" /> Read the code on GitHub
        </a>
      </div>
    </div>
  )
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-12 sm:px-6 md:flex-row md:justify-between">
        <div className="max-w-md space-y-3">
          <Logo />
          <p className="caption-5 text-ink-muted">
            Educational project, not a SEBI registered adviser and not investment advice. Prices from Yahoo Finance via
            yfinance, end of day and possibly delayed.
          </p>
        </div>
        <nav aria-label="Footer">
          <ul className="flex flex-wrap gap-x-6 gap-y-2 caption-2 text-ink-secondary">
            <li><Link to="/privacy" className="transition-colors duration-300 ease-nv hover:text-ink">Privacy</Link></li>
            <li><Link to="/terms" className="transition-colors duration-300 ease-nv hover:text-ink">Terms</Link></li>
            <li><a href={REPO} target="_blank" rel="noopener noreferrer" className="transition-colors duration-300 ease-nv hover:text-ink">GitHub</a></li>
            <li><Link to="/login" className="transition-colors duration-300 ease-nv hover:text-ink">Log in</Link></li>
          </ul>
        </nav>
      </div>
    </footer>
  )
}

// ------------------------------------------------------------------ page
export default function LandingPage() {
  usePageTitle(null)
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-20 focus:z-50 focus:rounded-lg focus:bg-ink focus:px-3 focus:py-2 focus:text-ink-inverse">
        Skip to content
      </a>
      <Nav />
      <main id="main">
        {/* hero: asymmetric split, text on the left, the product on the right */}
        <section className="mx-auto grid w-full max-w-7xl items-center gap-12 px-4 pb-16 pt-32 sm:px-6 lg:pb-24 lg:pt-40 xl:grid-cols-[minmax(0,680px)_1fr]">
          <div>
            <h1 className="max-w-[680px] heading-3 text-ink sm:heading-2">
              <span className="block">Understand an Indian stock</span>
              <span className="block text-ink-secondary">with every number traced</span>
            </h1>
            <p className="mt-6 max-w-[680px] body-3 text-ink-secondary lg:body-7">
              NeuralVest runs five AI agents on your own computer. They read prices, news, annual statements and risk
              for NSE and BSE stocks, then write a report in which every figure traces back to a Python calculation.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Button to="/register">{CTA}<ArrowRight size={16} aria-hidden="true" /></Button>
              <a href="#how" className="body-5 text-ink-secondary underline-offset-4 transition-colors duration-300 ease-nv hover:text-ink hover:underline">See how it works</a>
            </div>
            <p className="mt-8 figure caption-5 text-ink-muted">Open source on GitHub · 425 automated tests · runs on an 8 GB laptop</p>
          </div>
          <HeroPreview />
        </section>

        <Section>
          <div className="grid gap-8 lg:grid-cols-2">
            <div>
              <Eyebrow>The problem</Eyebrow>
              <h2 className="max-w-[680px] heading-4 text-ink lg:heading-3">Stock summaries hand you a verdict without the working</h2>
            </div>
            <div className="space-y-4 body-3 text-ink-secondary">
              <p>
                Ask a chatbot about a stock and you get confident sentences with numbers you cannot check. Some are
                rounded, some are from another year, a few belong to a different company.
              </p>
              <p>
                NeuralVest splits the job. Python computes every number from named sources. A small local model only
                explains them, and its text is thrown out when it invents a figure or contradicts a reading.
              </p>
            </div>
          </div>
        </Section>

        <Section>
          <Eyebrow>Why it helps</Eyebrow>
          <h2 className="max-w-[680px] heading-4 text-ink lg:heading-3">Analysis you can check line by line</h2>
          <ul className="mt-12 grid gap-4 sm:grid-cols-2">
            {BENEFITS.map(([title, text]) => (
              <li key={title} className="rounded-2xl border border-line bg-surface p-6">
                <h3 className="title-2 text-ink">{title}</h3>
                <p className="mt-2 body-6 text-ink-secondary">{text}</p>
              </li>
            ))}
          </ul>
        </Section>

        <TaglineReveal />

        <Section id="how">
          <Eyebrow>How it works</Eyebrow>
          <h2 className="max-w-[680px] heading-4 text-ink lg:heading-3">From a symbol to a report in three steps</h2>
          <ol className="mt-12 grid gap-8 md:grid-cols-3">
            {STEPS.map(([title, text], i) => (
              <li key={title} className="border-t border-line pt-6">
                <span className="figure caption-3 text-accent-ink">0{i + 1}</span>
                <h3 className="mt-2 title-2 text-ink">{title}</h3>
                <p className="mt-2 body-6 text-ink-secondary">{text}</p>
              </li>
            ))}
          </ol>
        </Section>

        <Section id="agents">
          <div className="grid gap-12 lg:grid-cols-[1fr_1.2fr]">
            <div>
              <Eyebrow>The agents</Eyebrow>
              <h2 className="max-w-[680px] heading-4 text-ink lg:heading-3">Five specialists and a supervisor that checks their work</h2>
              <p className="mt-4 body-3 text-ink-secondary">
                A LangGraph supervisor runs the agents in order, retries a step once when a data source is briefly down,
                and validates every output before the report is written.
              </p>
              <ul className="mt-8 flex flex-wrap gap-2">
                {STACK.map((s) => <li key={s} className="rounded-lg border border-line px-3 py-1 caption-4 text-ink-secondary">{s}</li>)}
              </ul>
            </div>
            <ol className="divide-y divide-line rounded-2xl border border-line bg-surface">
              {AGENTS.map(([name, text], i) => (
                <li key={name} className="grid grid-cols-[32px_1fr] gap-3 p-4 sm:p-6">
                  <span className="figure caption-3 text-ink-muted">{i + 1}</span>
                  <div>
                    <h3 className="title-3 text-ink">{name}</h3>
                    <p className="mt-1 body-6 text-ink-secondary">{text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </Section>

        <Section>
          <Eyebrow>Built in the open</Eyebrow>
          <h2 className="max-w-[680px] heading-4 text-ink lg:heading-3">No testimonials yet, so here is the evidence instead</h2>
          <dl className="mt-12 grid gap-4 sm:grid-cols-3">
            {[
              ['425', 'automated tests, including checks that every report number traces to an agent'],
              ['5.86%', 'risk free rate: the 91 day T bill yield from the RBI release of 18 Nov 2026, with its source and date in every report'],
              ['0', 'paid services: Yahoo Finance data, public news feeds, a local model and a free database tier'],
            ].map(([n, text]) => (
              <div key={text} className="rounded-2xl border border-line bg-surface p-6">
                <dt className="figure-1 text-ink">{n}</dt>
                <dd className="mt-2 body-6 text-ink-secondary">{text}</dd>
              </div>
            ))}
          </dl>
        </Section>

        <Section id="faq">
          <div className="grid gap-12 lg:grid-cols-[1fr_1.4fr]">
            <div>
              <Eyebrow>Questions</Eyebrow>
              <h2 className="max-w-[680px] heading-4 text-ink lg:heading-3">What people ask before they start</h2>
            </div>
            <div className="border-t border-line">
              {FAQ.map(([q, a]) => <FaqItem key={q} q={q} a={a} />)}
            </div>
          </div>
        </Section>

        <Section><FinalCta /></Section>
      </main>
      <SiteFooter />
    </div>
  )
}
