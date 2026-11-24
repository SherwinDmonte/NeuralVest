// Risk Analysis (task 12.3.7): volatility, beta, drawdown, Sharpe ratio and classification per
// stock, the correlation matrix, concentration and diversification. POST /risk/analyze computes
// the same metrics as the Risk Assessment agent, without AI text and without storing anything.
import { useState } from 'react'
import { ShieldWarning } from '@phosphor-icons/react'
import { CorrelationHeatmap } from '../components/charts'
import { Readings } from '../components/explain'
import { RiskStats } from '../components/RiskCard'
import SymbolPicker from '../components/SymbolPicker'
import { Button, Card, CardSkeleton, EmptyState, ErrorState, Field, Meta, PageHeader, Select, Tabs, ToneBadge, table } from '../components/ui'
import { analyzeRisk, errorMessage } from '../services/api'
import { fmtDate, num } from '../utils/format'
import { usePageTitle } from '../hooks/usePageTitle'

const label = (k) => k.replaceAll('_', ' ').replace(/\bpct\b/, '%').replace(/^./, (c) => c.toUpperCase())

function KeyValues({ data }) {
  const rows = Object.entries(data || {}).filter(([, v]) => v != null && typeof v !== 'object')
  if (!rows.length) return null
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-baseline justify-between gap-3 border-b border-line pb-2">
          <dt className="caption-2 text-ink-secondary">{label(k)}</dt>
          <dd className="figure caption-2 text-ink">{typeof v === 'number' ? num(v, 2) : String(v).replaceAll('_', ' ')}</dd>
        </div>
      ))}
    </dl>
  )
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

  return (
    <div className="space-y-6">
      <PageHeader title="Risk analysis" description="How much each stock has moved, how it moved with the NIFTY 50 and with each other. Historical measurements, not forecasts." />
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
          <Button type="submit" disabled={state.busy}>{state.busy ? 'Measuring' : 'Measure risk'}</Button>
        </form>
        {formError && <p role="alert" className="mt-2 caption-5 text-critical">{formError}</p>}
      </Card>

      {state.error && <ErrorState message={state.error} />}
      {state.busy && <CardSkeleton rows={5} />}
      {!state.busy && !state.data && !state.error && (
        <EmptyState icon={ShieldWarning} title="Add stocks to measure">
          With two or more stocks you also get their correlations and how concentrated an equal split would be.
        </EmptyState>
      )}

      {state.data && (
        <>
          {state.data.not_found?.length > 0 && <ErrorState message={`No price data for: ${state.data.not_found.join(', ')}`} />}
          <Card title="Summary" subtitle={`Period ${state.data.period}${state.data.risk_free_rate ? ` · risk free rate ${num(state.data.risk_free_rate.value_pct)}% (${state.data.risk_free_rate.source}, ${fmtDate(state.data.risk_free_rate.as_of_date)})` : ' · risk free rate not configured, so no Sharpe ratio'}`}>
            <div className={table.wrap}>
              <table className={table.table}>
                <caption className="sr-only">Risk by stock</caption>
                <thead className={table.thead}>
                  <tr>
                    <th className={table.th}>Stock</th>
                    <th className={table.th}>Class</th>
                    <th className={table.thR}>Volatility</th>
                    <th className={table.thR}>Beta</th>
                    <th className={`${table.thR} hidden sm:table-cell`}>Max drawdown</th>
                    <th className={`${table.thR} hidden sm:table-cell`}>Sharpe</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(per).map(([s, r]) => (
                    <tr key={s} className={table.tr}>
                      <td className="px-3 py-2 body-5 text-ink">{s}</td>
                      <td className="px-3 py-2"><ToneBadge value={r.risk_classification} /></td>
                      <td className={table.tdR}>{r.annualized_volatility_pct == null ? 'n/a' : `${num(r.annualized_volatility_pct)}%`}</td>
                      <td className={table.tdR}>{num(r.beta?.value, 2)}</td>
                      <td className={`${table.tdR} hidden sm:table-cell`}>{r.max_drawdown?.max_drawdown_pct == null ? 'n/a' : `${num(r.max_drawdown.max_drawdown_pct)}%`}</td>
                      <td className={`${table.tdR} hidden sm:table-cell`}>{num(r.sharpe?.value, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {Object.keys(per).length > 1 && (
            <Tabs label="Stock shown in detail" value={selected} onChange={setSelected}
                  tabs={Object.keys(per).map((s) => ({ value: s, label: s }))} />
          )}
          {current && current.status !== 'failed' && (
            <div className="space-y-4">
              <RiskStats risk={current} />
              <Card><Readings items={Object.values(current.readings || {})} /></Card>
            </div>
          )}
          {current?.status === 'failed' && <ErrorState message={current.errors?.[0] || 'Risk could not be measured for this stock.'} />}

          {pf && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <CorrelationHeatmap matrix={pf.correlation?.matrix} />
              <Card title="Diversification and concentration" subtitle={pf.weights_assumption ? `Weights: ${pf.weights_assumption}` : undefined}>
                <div className="space-y-6">
                  <div>
                    <div className="mb-3 flex items-center gap-2">
                      <span className="caption-2 text-ink-secondary">Diversification</span>
                      <ToneBadge value={pf.diversification?.assessment} />
                    </div>
                    <KeyValues data={pf.diversification} />
                  </div>
                  <div>
                    <div className="mb-3 caption-2 text-ink-secondary">Concentration</div>
                    <KeyValues data={pf.concentration} />
                  </div>
                </div>
              </Card>
            </div>
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
