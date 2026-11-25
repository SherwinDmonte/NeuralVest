// Risk analysis (Phase 12, redesigned in 12B): an overview, volatility and drawdown across the
// stocks, the distribution of daily returns with historical VaR (95%, from the same returns),
// per stock metrics, correlation, concentration and warnings. POST /risk/analyze computes the
// same metrics as the Risk Assessment agent, without AI text and without storing anything.
import { useState } from 'react'
import { ChartBar, ShieldWarning, Warning, Waveform } from '@phosphor-icons/react'
import { CorrelationHeatmap, MetricBars, ReturnHistogram } from '../components/charts'
import { Readings } from '../components/explain'
import { AnimatedNumber, AnimatedTabs, Reveal } from '../components/motion'
import { RiskStats } from '../components/RiskCard'
import SymbolPicker from '../components/SymbolPicker'
import { Button, Card, CardSkeleton, EmptyState, ErrorState, Field, Meta, PageHeader, Select, StatTile, ToneBadge, table } from '../components/ui'
import { analyzeRisk, errorMessage } from '../services/api'
import { fmtDate, num, shortSymbol } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

const label = (k) => k.replaceAll('_', ' ').replace(/\bpct\b/, '%').replace(/^./, (c) => c.toUpperCase())

const KV_LABELS = { hhi: 'HHI (Herfindahl index)', largest_weight_pct: 'Largest weight, %', smallest_weight_pct: 'Smallest weight, %' }

function KeyValues({ data }) {
  const rows = Object.entries(data || {}).filter(([, v]) => v != null && typeof v !== 'object')
  if (!rows.length) return null
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-baseline justify-between gap-3 border-b border-line pb-2">
          <dt className="caption-2 text-ink-secondary">{KV_LABELS[k] || label(k)}</dt>
          <dd className="figure caption-2 text-ink">{typeof v === 'number' ? num(v, 2) : String(v).replaceAll('_', ' ')}</dd>
        </div>
      ))}
    </dl>
  )
}

// Warnings come only from computed fields (class, drawdown, Sharpe, beta).
function warningsFor(per) {
  const out = []
  for (const [s, r] of Object.entries(per)) {
    if (r.status === 'failed') continue
    if (r.risk_classification === 'high') out.push([s, `high historical risk (volatility ${num(r.annualized_volatility_pct)}%)`])
    if (r.max_drawdown?.max_drawdown_pct != null && r.max_drawdown.max_drawdown_pct <= -30) out.push([s, `fell ${num(r.max_drawdown.max_drawdown_pct)}% from a peak${r.max_drawdown.recovered ? '' : ' and has not recovered'}`])
    if (r.sharpe?.value != null && r.sharpe.value < 0) out.push([s, `returns below the risk free rate (Sharpe ${num(r.sharpe.value)})`])
    if (r.beta?.value != null && r.beta.value > 1.2) out.push([s, `moves more than the NIFTY 50 (beta ${num(r.beta.value)})`])
  }
  return out
}

export default function RiskPage() {
  usePageTitle('Risk analysis')
  const [symbols, setSymbols] = useState([])
  const [period, setPeriod] = useState('1y')
  const [state, setState] = useState({ busy: false, error: null, data: null })
  const [selected, setSelected] = useState(null)
  const [formError, setFormError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!symbols.length) return setFormError('Add at least one stock')
    setFormError(null)
    setState({ busy: true, error: null, data: null })
    try {
      const data = await analyzeRisk({ symbols, period })
      setSelected(Object.keys(data.symbols)[0])
      setState({ busy: false, error: null, data })
    } catch (err) {
      setState({ busy: false, error: errorMessage(err), data: null })
    }
  }

  const per = state.data?.symbols || {}
  const pf = state.data?.portfolio
  const current = selected && per[selected]
  const ok = Object.entries(per).filter(([, r]) => r.status !== 'failed')
  const warnings = warningsFor(per)
  const mostVolatile = ok.reduce((best, [s, r]) => (!best || (r.annualized_volatility_pct ?? -1) > best[1] ? [s, r.annualized_volatility_pct] : best), null)

  return (
    <div className="space-y-6">
      <PageHeader title="How risky were they?" description="How much each stock has moved, how it moved with the NIFTY 50 and with each other. Historical measurements, not forecasts." />
      <Card>
        <form onSubmit={submit} noValidate className="grid gap-4 lg:grid-cols-[1fr_200px_auto] lg:items-end">
          <SymbolPicker value={symbols} onChange={setSymbols} label="Stocks" placeholder="Search and add up to 10 stocks" />
          <Field label="Period">
            {(p) => (
              <Select {...p} value={period} onChange={(e) => setPeriod(e.target.value)}>
                <option value="6mo">6 months</option>
                <option value="1y">1 year</option>
                <option value="2y">2 years</option>
              </Select>
            )}
          </Field>
          <Button type="submit" size="lg" disabled={state.busy}><ShieldWarning size={18} aria-hidden="true" />{state.busy ? 'Measuring' : 'Measure risk'}</Button>
        </form>
        {formError && <p role="alert" className="mt-2 caption-5 text-critical">{formError}</p>}
      </Card>

      {state.error && <ErrorState message={state.error} />}
      {state.busy && <CardSkeleton rows={6} />}
      {!state.busy && !state.data && !state.error && (
        <EmptyState icon={ShieldWarning} title="Add stocks to measure">
          With two or more stocks you also get their correlations, diversification and how concentrated an equal split would be.
        </EmptyState>
      )}

      {state.data && (
        <>
          {state.data.not_found?.length > 0 && <ErrorState message={`No price data for: ${state.data.not_found.join(', ')}`} />}

          <Reveal>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatTile label="Stocks measured" value={<AnimatedNumber value={ok.length} format={(v) => Math.round(v)} />} sub={`Period ${state.data.period}`} />
              <StatTile label="Most volatile" value={mostVolatile ? shortSymbol(mostVolatile[0]) : 'n/a'} sub={mostVolatile ? `${num(mostVolatile[1])}% a year` : null} traced="risk assessment" />
              <StatTile label="Average correlation" value={pf?.diversification?.average_pairwise_correlation != null ? num(pf.diversification.average_pairwise_correlation) : 'n/a'}
                        sub={pf ? <ToneBadge value={pf.diversification?.assessment} label={`${pf.diversification?.assessment} diversification`} /> : 'Needs 2 or more stocks'} traced={pf ? 'risk assessment' : undefined} />
              <StatTile label="Effective number of stocks" value={pf?.concentration?.effective_number_of_stocks != null ? num(pf.concentration.effective_number_of_stocks) : 'n/a'}
                        sub={pf ? `with ${pf.weights_assumption}` : 'Needs 2 or more stocks'} />
            </div>
          </Reveal>

          <Reveal>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Card title="Volatility by stock" subtitle="Annualised, from daily returns" icon={ChartBar}>
                <MetricBars rows={ok.map(([s, r]) => ({ label: shortSymbol(s), value: r.annualized_volatility_pct, tone: r.risk_classification === 'high' ? 'critical' : r.risk_classification === 'moderate' ? 'warning' : undefined }))} />
              </Card>
              <Card title="Largest fall from a peak" subtitle="Maximum drawdown in the period" icon={ChartBar}>
                <MetricBars rows={ok.map(([s, r]) => ({ label: shortSymbol(s), value: r.max_drawdown?.max_drawdown_pct, tone: 'critical' }))} />
              </Card>
            </div>
          </Reveal>

          <Card title="Summary" subtitle={`Period ${state.data.period}${state.data.risk_free_rate ? ` · risk free rate ${num(state.data.risk_free_rate.value_pct)}% (${state.data.risk_free_rate.source}, ${fmtDate(state.data.risk_free_rate.as_of_date)})` : ' · risk free rate not configured, so no Sharpe ratio'}`}>
            <div className={table.wrap}>
              <table className={table.table}>
                <caption className="sr-only">Risk by stock</caption>
                <thead className={table.thead}>
                  <tr>
                    <th className={table.th}>Stock</th><th className={table.th}>Class</th><th className={table.thR}>Volatility</th><th className={table.thR}>Beta</th>
                    <th className={`${table.thR} hidden sm:table-cell`}>Max drawdown</th><th className={`${table.thR} hidden sm:table-cell`}>Sharpe</th><th className={`${table.thR} hidden md:table-cell`}>VaR 95%, 1 day</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(per).map(([s, r]) => (
                    <tr key={s} className={`${table.tr} cursor-pointer`} onClick={() => setSelected(s)}>
                      <td className="px-3 py-2 body-5 text-ink">{s}</td>
                      <td className="px-3 py-2"><ToneBadge value={r.risk_classification} /></td>
                      <td className={table.tdR}>{r.annualized_volatility_pct == null ? 'n/a' : `${num(r.annualized_volatility_pct)}%`}</td>
                      <td className={table.tdR}>{num(r.beta?.value, 2)}</td>
                      <td className={`${table.tdR} hidden sm:table-cell`}>{r.max_drawdown?.max_drawdown_pct == null ? 'n/a' : `${num(r.max_drawdown.max_drawdown_pct)}%`}</td>
                      <td className={`${table.tdR} hidden sm:table-cell`}>{num(r.sharpe?.value, 2)}</td>
                      <td className={`${table.tdR} hidden md:table-cell`}>{r.return_distribution?.p5_pct == null ? 'n/a' : `${num(r.return_distribution.p5_pct)}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 caption-5 text-ink-muted">VaR 95%, 1 day (historical): 5% of trading days in the period fell more than this. It describes the past, not a limit on future losses.</p>
          </Card>

          {Object.keys(per).length > 1 && (
            <AnimatedTabs label="Stock shown in detail" value={selected} onChange={setSelected} tabs={Object.keys(per).map((s) => ({ value: s, label: shortSymbol(s) }))} />
          )}
          {current && current.status !== 'failed' && (
            <div className="space-y-6">
              <RiskStats risk={current} />
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.4fr_1fr]">
                <Card title="Distribution of daily returns" icon={Waveform}
                      subtitle={`${state.data.distribution?.[selected]?.observations ?? 'n/a'} trading days · losses in red, gains in green · the dashed line marks the worst 5% of days`}>
                  <ReturnHistogram bins={state.data.distribution?.[selected]?.bins} p5={current.return_distribution?.p5_pct} />
                </Card>
                <Card title="Key readings"><Readings items={Object.values(current.readings || {})} /></Card>
              </div>
            </div>
          )}
          {current?.status === 'failed' && <ErrorState message={current.errors?.[0] || 'Risk could not be measured for this stock.'} />}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {pf && <CorrelationHeatmap matrix={pf.correlation?.matrix} />}
            <Card title="Risk warnings" subtitle="From the computed figures above" icon={Warning}>
              {warnings.length ? (
                <ul className="space-y-2">
                  {warnings.map(([s, w]) => (
                    <li key={`${s}-${w}`} className="flex items-start gap-3 rounded-xl border border-warning/25 bg-warning/5 p-3">
                      <Warning size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
                      <span className="body-6 text-ink"><span className="body-5">{shortSymbol(s)}</span>: {w}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="body-6 text-ink-secondary">None of the warning rules applies to these stocks in this period.</p>}
              <p className="mt-3 caption-5 text-ink-muted">Rules: high risk class; a fall of 30% or more from a peak; Sharpe below 0; beta above 1.2.</p>
            </Card>
          </div>

          {pf && (
            <Card title="Diversification and concentration" subtitle={pf.weights_assumption ? `Weights: ${pf.weights_assumption}` : undefined}>
              <div className="grid gap-6 lg:grid-cols-2">
                <div><p className="mb-3 caption-2 text-ink-secondary">Diversification</p><KeyValues data={pf.diversification} /></div>
                <div><p className="mb-3 caption-2 text-ink-secondary">Concentration</p><KeyValues data={pf.concentration} /></div>
              </div>
            </Card>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="max-w-3xl caption-5 text-ink-muted">{state.data.disclaimer}</p>
            <Meta>nothing is stored for this page</Meta>
          </div>
        </>
      )}
    </div>
  )
}
