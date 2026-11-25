// Help (Phase 12B): getting started, what each page does, data sources, shortcuts and terms.
import { Link } from 'react-router-dom'
import { BookOpen, CaretDown, Keyboard, Lightning, Database } from '@phosphor-icons/react'
import { Card, PageHeader } from '../components/ui'
import { NAV } from '../layouts/nav'
import { usePageTitle } from '../hooks/usePageTitle'

const STEPS = [
  ['Pick stocks', 'Open Stock analysis, type an NSE symbol like RELIANCE or a BSE code like 500325, and add up to 10.'],
  ['Watch the agents', 'Five agents work in turn; AI agents shows each step live. Two stocks take about 90 seconds on a laptop CPU.'],
  ['Read the report', 'Key observations, sources, data limitations and a glossary. Download it as a PDF or compare it with another report.'],
]

const TERMS = [
  ['RSI 14', 'A 0 to 100 gauge of recent gains against losses. Above 70 is often called overbought, below 30 oversold.'],
  ['MACD', 'The gap between a fast and a slow average of prices. Above its signal line means upward momentum has been strengthening.'],
  ['Volatility', 'How much the price usually swings in a year, from daily price changes.'],
  ['Beta', 'How strongly a stock moved with the NIFTY 50. 1 means in step.'],
  ['Maximum drawdown', 'The largest fall from a previous high to a later low.'],
  ['Sharpe ratio', 'Return above the risk free rate (91 day T bill) per unit of volatility.'],
  ['Historical VaR 95%', 'The daily loss that was exceeded on only 5% of days in the period. It describes the past, not a limit on future losses.'],
  ['Breadth', 'How many of the 30 curated stocks rose or fell on the last trading day. Not whole market data.'],
]

const FAQ = [
  ['Why is a number missing?', 'Missing data is shown as n/a with the reason, never estimated. Yahoo Finance does not have every line item for every company.'],
  ['Why did the AI text change between runs?', 'The local model writes new wording each time. The computed readings stay the same for the same data and are the reference.'],
  ['Why is the smaller AI model used?', 'The larger model needs about 1.8 GB of free memory. With less free, the smaller one answers; Settings shows which.'],
  ['Is anything real time?', 'No. Prices are end of day; the top bar shows the date of the latest close.'],
]

export default function HelpPage() {
  usePageTitle('Help')
  return (
    <div className="space-y-6">
      <PageHeader title="How NeuralVest works" description="A short guide to the pages, the data and the terms used in reports." />
      <Card title="Getting started" icon={Lightning} accent>
        <ol className="grid gap-4 md:grid-cols-3">
          {STEPS.map(([t, d], i) => (
            <li key={t} className="rounded-2xl border border-line bg-raised/50 p-4">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-button figure caption-3 text-white">{i + 1}</span>
              <h3 className="mt-3 title-3 text-ink">{t}</h3>
              <p className="mt-1 body-6 text-ink-secondary">{d}</p>
            </li>
          ))}
        </ol>
      </Card>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Pages" icon={BookOpen}>
          <ul className="space-y-2">
            {NAV.map(({ to, label, Icon, description }) => (
              <li key={to}>
                <Link to={to} className="flex items-start gap-3 rounded-xl p-2 transition-colors duration-300 ease-nv hover:bg-raised">
                  <Icon size={18} className="mt-0.5 text-accent-ink" aria-hidden="true" />
                  <span><span className="block body-5 text-ink">{label}</span><span className="caption-5 text-ink-muted">{description}</span></span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <div className="space-y-6">
          <Card title="Keyboard" icon={Keyboard}>
            <ul className="space-y-2 body-6 text-ink-secondary">
              <li className="flex justify-between gap-3"><span>Search stocks and pages</span><kbd className="rounded-md border border-line bg-raised px-1.5 figure caption-4 text-ink">Ctrl K</kbd></li>
              <li className="flex justify-between gap-3"><span>Move through results, open, close</span><kbd className="rounded-md border border-line bg-raised px-1.5 figure caption-4 text-ink">↑ ↓ Enter Esc</kbd></li>
              <li className="flex justify-between gap-3"><span>Skip to the page content</span><kbd className="rounded-md border border-line bg-raised px-1.5 figure caption-4 text-ink">Tab</kbd></li>
            </ul>
          </Card>
          <Card title="Data sources" icon={Database}>
            <ul className="list-disc space-y-1 pl-5 body-6 text-ink-secondary">
              <li>Prices and annual statements: Yahoo Finance via yfinance, end of day.</li>
              <li>News: public RSS feeds from Indian business publishers (GDELT when enabled).</li>
              <li>Risk free rate: the 91 day T bill yield entered in the backend settings, with its date and source.</li>
              <li>The NSE website is never scraped.</li>
            </ul>
          </Card>
        </div>
      </div>
      <Card title="Terms" icon={BookOpen}>
        <dl className="grid gap-x-8 gap-y-4 md:grid-cols-2">
          {TERMS.map(([t, d]) => <div key={t}><dt className="body-5 text-ink">{t}</dt><dd className="mt-1 body-6 text-ink-secondary">{d}</dd></div>)}
        </dl>
      </Card>
      <Card title="Questions">
        {FAQ.map(([q, a]) => (
          <details key={q} className="group border-b border-line last:border-0">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-3 body-5 text-ink">
              {q}<CaretDown size={16} className="shrink-0 text-ink-muted transition-transform duration-500 ease-nv group-open:rotate-180" aria-hidden="true" />
            </summary>
            <p className="pb-3 body-6 text-ink-secondary">{a}</p>
          </details>
        ))}
      </Card>
    </div>
  )
}
