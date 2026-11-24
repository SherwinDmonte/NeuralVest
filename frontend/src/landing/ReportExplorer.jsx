// "Explore a real report": the numbers the agents computed in the stored run, in four tabs.
// Charts redraw each time a tab opens. Keyboard: arrow keys move between tabs.
import { useRef, useState } from 'react'
import { ArrowRight } from '@phosphor-icons/react'
import { Button } from '../components/ui'
import { useAuth } from '../auth/AuthContext'
import { fmtDate, inr, num, shortSymbol } from '../utils/format'
import { CTA, RUN_LABEL, fmtPct, fmtSigned, snapshot } from './content'
import { useMountVisible } from './hooks'
import { Bar, Donut, LineChart } from './MiniCharts'
import { Section, SectionHeading } from './Section'

const SYMS = snapshot.run.symbols
const COLORS = ['var(--nv-series-1)', 'var(--nv-series-2)', 'var(--nv-series-3)', 'var(--nv-series-4)']
const stock = (s) => snapshot.stocks[s]

function Panel({ children }) {
  const ref = useMountVisible()
  return <div ref={ref} className="lp-scope lp-swap">{children}</div>
}

function Legend({ items }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 caption-2 text-ink-secondary">
      {items.map(([label, color]) => (
        <li key={label} className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: color }} aria-hidden="true" />{label}</li>
      ))}
    </ul>
  )
}

function Returns() {
  const rows = [...SYMS.map((s, i) => [shortSymbol(s), stock(s).return_1y_pct, COLORS[i]]), ['NIFTY 50', stock(SYMS[0]).nifty_return_pct, 'var(--nv-ink-muted)']]
  const max = Math.max(...rows.map((r) => Math.abs(r[1])))
  const w = stock(SYMS[0]).window
  return (
    <div className="grid gap-8 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
      <div className="space-y-5">
        <p className="caption-4 text-ink-muted">One year return · {fmtDate(w.from)} to {fmtDate(w.to)}</p>
        {rows.map(([label, v, color], i) => <Bar key={label} label={label} value={v} max={max} display={fmtPct(v)} color={color} delay={i * 120} />)}
      </div>
      <dl className="grid grid-cols-2 content-start gap-3">
        {[['last close', (s) => `₹${num(stock(s).last_close)}`], ['trend', (s) => stock(s).trend], ['RSI 14', (s) => num(stock(s).rsi_14)]]
          .flatMap(([name, f]) => SYMS.map((s) => [`${shortSymbol(s)} ${name}`, f(s)])).map(([k, v]) => (
          <div key={k} className="rounded-xl border border-line bg-page p-3">
            <dt className="caption-4 text-ink-muted">{k}</dt>
            <dd className="mt-1 figure caption-1 capitalize text-ink">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function Risk() {
  const volMax = Math.max(...SYMS.map((s) => stock(s).volatility_pct))
  const ddMax = Math.max(...SYMS.map((s) => Math.abs(stock(s).max_drawdown.pct)))
  const corr = snapshot.correlation?.[SYMS[0]]?.[SYMS[1]]
  return (
    <div className="grid gap-8 md:grid-cols-3">
      <div className="space-y-5">
        <p className="caption-4 text-ink-muted">Annualised volatility</p>
        {SYMS.map((s, i) => <Bar key={s} label={shortSymbol(s)} value={stock(s).volatility_pct} max={volMax} display={`${num(stock(s).volatility_pct)}%`} color={COLORS[i]} delay={i * 120} />)}
      </div>
      <div className="space-y-5">
        <p className="caption-4 text-ink-muted">Largest fall from a peak</p>
        {SYMS.map((s, i) => <Bar key={s} label={shortSymbol(s)} value={stock(s).max_drawdown.pct} max={ddMax} display={fmtPct(stock(s).max_drawdown.pct)} color="var(--nv-critical)" delay={200 + i * 120} />)}
      </div>
      <dl className="grid grid-cols-2 content-start gap-3">
        {SYMS.map((s) => (
          <div key={s} className="rounded-xl border border-line bg-page p-3">
            <dt className="caption-4 text-ink-muted">{shortSymbol(s)} beta</dt>
            <dd className="mt-1 figure caption-1 text-ink">{num(stock(s).beta)}</dd>
          </div>
        ))}
        {corr != null && (
          <div className="col-span-2 rounded-xl border border-line bg-page p-3">
            <dt className="caption-4 text-ink-muted">Correlation of daily returns</dt>
            <dd className="mt-1 figure caption-1 text-ink">{num(corr)} <span className="font-sans caption-5 text-ink-muted">· {snapshot.diversification} diversification</span></dd>
          </div>
        )}
      </dl>
    </div>
  )
}

const FUND_ROWS = [
  ['pe', 'Price to earnings', (v) => num(v)],
  ['roe_pct', 'Return on equity', (v) => `${num(v)}%`],
  ['net_margin_pct', 'Net margin', (v) => `${num(v)}%`],
  ['revenue_growth_yoy_pct', 'Revenue growth', (v) => fmtPct(v)],
  ['debt_to_equity', 'Debt to equity', (v) => num(v)],
]

function Fundamentals() {
  const period = stock(SYMS[0]).fundamentals.pe?.period
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-left">
        <caption className="pb-3 text-left caption-4 text-ink-muted">From the annual statements · {period}</caption>
        <thead>
          <tr className="border-b border-line caption-4 text-ink-muted">
            <th scope="col" className="py-2 pr-4 font-medium">Ratio</th>
            {SYMS.map((s) => <th key={s} scope="col" className="py-2 pr-4 text-right font-medium">{shortSymbol(s)}</th>)}
            <th scope="col" className="hidden py-2 font-medium lg:table-cell">Formula</th>
          </tr>
        </thead>
        <tbody>
          {FUND_ROWS.map(([key, label, fmt]) => (
            <tr key={key} className="border-b border-line last:border-0">
              <th scope="row" className="py-3 pr-4 caption-1 font-medium text-ink">{label}</th>
              {SYMS.map((s) => {
                const m = stock(s).fundamentals[key]
                return <td key={s} className="py-3 pr-4 text-right figure caption-1 text-ink">{m ? fmt(m.value) : 'n/a'}</td>
              })}
              <td className="hidden py-3 caption-5 text-ink-muted lg:table-cell">{stock(SYMS[0]).fundamentals[key]?.formula}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Portfolio() {
  const p = snapshot.portfolio
  const bt = p.backtest
  return (
    <div className="grid gap-8 lg:grid-cols-[auto_minmax(0,1fr)]">
      <div className="flex flex-col items-center gap-5 sm:flex-row lg:flex-col lg:items-start">
        <Donut label="Allocation by weight" parts={p.allocations.map((a, i) => ({ label: a.symbol, value: a.weight_pct, color: COLORS[i] }))}>
          <div>
            <div className="figure caption-1 text-ink">{inr(p.amount_inr, 0)}</div>
            <div className="caption-5 text-ink-muted">illustrative</div>
          </div>
        </Donut>
        <ul className="space-y-2">
          {p.allocations.map((a, i) => (
            <li key={a.symbol} className="flex items-center gap-3 caption-2 text-ink-secondary">
              <span className="h-2 w-2 rounded-full" style={{ background: COLORS[i] }} aria-hidden="true" />
              <span className="w-20 text-ink">{shortSymbol(a.symbol)}</span>
              <span className="figure">{num(a.weight_pct, 0)}% · {a.shares} shares · {inr(a.amount_inr, 0)}</span>
            </li>
          ))}
          <li className="caption-5 text-ink-muted">Method: {p.method_label}</li>
        </ul>
      </div>
      {bt && (
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <p className="caption-4 text-ink-muted">Backtest on past prices · {fmtDate(bt.from)} to {fmtDate(bt.to)}</p>
            <Legend items={[['This allocation rule', 'var(--nv-accent)'], ['NIFTY 50', 'var(--nv-ink-muted)']]} />
          </div>
          <div className="mt-4">
            <LineChart data={bt.curve} height={200} label="Backtest value of the allocation rule and the NIFTY 50"
                       series={[{ key: 'strategy', color: 'var(--nv-accent)' }, { key: 'nifty50', color: 'var(--nv-ink-muted)', width: 1.75, opacity: 0.9 }]} />
          </div>
          <dl className="mt-4 grid grid-cols-3 gap-3">
            {[['This rule', bt.cagr_pct], ['Equal weights', bt.equal_weight_cagr_pct], ['NIFTY 50', bt.nifty50_cagr_pct]].map(([k, v]) => (
              <div key={k} className="rounded-xl border border-line bg-page p-3">
                <dt className="caption-4 text-ink-muted">{k}, a year</dt>
                <dd className="mt-1 figure caption-1 text-ink">{v == null ? 'n/a' : `${fmtSigned(v)}%`}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  )
}

const TABS = [
  { id: 'returns', label: 'Returns', View: Returns },
  { id: 'risk', label: 'Risk', View: Risk },
  { id: 'fundamentals', label: 'Fundamentals', View: Fundamentals },
  ...(snapshot.portfolio ? [{ id: 'portfolio', label: 'Portfolio', View: Portfolio }] : []),
]

export default function ReportExplorer() {
  const [tab, setTab] = useState(TABS[0].id)
  const refs = useRef({})
  const { user } = useAuth()
  const onKey = (e) => {
    const i = TABS.findIndex((t) => t.id === tab)
    const next = e.key === 'ArrowRight' ? (i + 1) % TABS.length : e.key === 'ArrowLeft' ? (i - 1 + TABS.length) % TABS.length : null
    if (next == null) return
    e.preventDefault()
    setTab(TABS[next].id)
    refs.current[TABS[next].id]?.focus()
  }
  const { View } = TABS.find((t) => t.id === tab)

  return (
    <Section id="explore">
      <SectionHeading eyebrow="Explore a real report" title="The numbers from an actual run, not an illustration">
        {RUN_LABEL}. Every figure below was computed by the agents and stored with its source and date.
      </SectionHeading>

      <div className="mt-12 rounded-3xl border border-line bg-surface p-4 shadow-card sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div role="tablist" aria-label="Report sections" onKeyDown={onKey} className="inline-flex max-w-full gap-1 overflow-x-auto rounded-xl border border-line bg-page p-1">
            {TABS.map((t) => (
              <button key={t.id} ref={(n) => { refs.current[t.id] = n }} type="button" role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id}
                      aria-controls="explore-panel" tabIndex={tab === t.id ? 0 : -1} onClick={() => setTab(t.id)}
                      className={`shrink-0 rounded-lg px-3 py-1.5 body-5 transition-colors duration-300 ease-nv ${tab === t.id ? 'bg-raised text-ink shadow-card' : 'text-ink-secondary hover:text-ink'}`}>
                {t.label}
              </button>
            ))}
          </div>
          <span className="caption-5 text-ink-muted">Past data, not a recommendation</span>
        </div>
        <div id="explore-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="mt-8 min-h-[300px]">
          <Panel key={tab}><View /></Panel>
        </div>
        <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6">
          <p className="max-w-md caption-2 text-ink-secondary">Run the same analysis on any NSE or BSE stock. It takes about a minute on a laptop.</p>
          <Button to={user ? '/app/analysis' : '/register'}>{user ? 'Run your own analysis' : CTA}<ArrowRight size={16} aria-hidden="true" /></Button>
        </div>
      </div>
    </Section>
  )
}
