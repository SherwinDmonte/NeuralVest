// Portfolio Optimization (task 12.3.6): stock picker, capital, risk preference, method and
// constraints; then the allocation, rupee amounts, whole shares, metrics and backtest.
// Uses POST /portfolio/optimize (a few seconds, no AI text; saved to your reports).
import { useState } from 'react'
import { ChartPieSlice } from '@phosphor-icons/react'
import PortfolioCard from '../components/PortfolioCard'
import SymbolPicker from '../components/SymbolPicker'
import { Button, Card, CardSkeleton, EmptyState, ErrorState, Field, Input, PageHeader, Select } from '../components/ui'
import { errorMessage, optimizePortfolio } from '../services/api'
import { usePageTitle } from '../hooks/usePageTitle'

const METHODS = [
  { value: '', label: 'From the risk preference' },
  { value: 'min_volatility', label: 'Minimum volatility' },
  { value: 'max_sharpe', label: 'Maximum Sharpe ratio' },
  { value: 'efficient_risk', label: 'Best return for a target volatility' },
  { value: 'efficient_return', label: 'Lowest volatility for a target return' },
  { value: 'hrp', label: 'Hierarchical risk parity' },
  { value: 'inverse_volatility', label: 'Inverse volatility' },
  { value: 'equal_weight', label: 'Equal weights' },
]

export default function PortfolioPage() {
  usePageTitle('Portfolio')
  const [symbols, setSymbols] = useState([])
  const [f, setF] = useState({
    amount: '100000', preference: 'moderate', method: '', minW: '0', maxW: '', targetVol: '', targetRet: '',
    rebalance: 'quarterly', cost: '10',
  })
  const [errors, setErrors] = useState({})
  const [state, setState] = useState({ busy: false, error: null, data: null })
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))

  const validate = () => {
    const e = {}
    if (symbols.length < 2) e.symbols = 'Add at least 2 stocks'
    if (!(Number(f.amount) > 0)) e.amount = 'Enter an amount above 0'
    if (f.maxW !== '' && !(Number(f.maxW) > 0 && Number(f.maxW) <= 100)) e.maxW = 'Between 0 and 100'
    if (f.minW !== '' && !(Number(f.minW) >= 0 && Number(f.minW) <= 100)) e.minW = 'Between 0 and 100'
    if (f.method === 'efficient_risk' && !(Number(f.targetVol) > 0)) e.targetVol = 'Enter a target volatility in %'
    if (f.method === 'efficient_return' && f.targetRet === '') e.targetRet = 'Enter a target return in %'
    return e
  }

  const submit = async (ev) => {
    ev.preventDefault()
    const e = validate()
    setErrors(e)
    if (Object.keys(e).length) return
    setState({ busy: true, error: null, data: null })
    try {
      const data = await optimizePortfolio({
        symbols,
        investment_amount: Number(f.amount),
        risk_preference: f.preference,
        method: f.method || null,
        constraints: { min_weight_pct: Number(f.minW || 0), ...(f.maxW !== '' ? { max_weight_pct: Number(f.maxW) } : {}) },
        ...(f.method === 'efficient_risk' ? { target_volatility_pct: Number(f.targetVol) } : {}),
        ...(f.method === 'efficient_return' ? { target_return_pct: Number(f.targetRet) } : {}),
        rebalance: f.rebalance,
        transaction_cost_bps: Number(f.cost || 0),
      })
      setState({ busy: false, error: null, data })
    } catch (err) {
      setState({ busy: false, error: errorMessage(err), data: null })
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Portfolio optimization" title="Build an illustrative portfolio" description="An illustrative split of an amount across 2 to 10 stocks, in whole shares, with a walk forward backtest. It describes the past and is not advice." />

      <Card>
        <form onSubmit={submit} noValidate className="space-y-6">
          <div>
            <SymbolPicker value={symbols} onChange={setSymbols} label="Stocks" placeholder="Search and add 2 to 10 stocks" />
            {errors.symbols && <p className="mt-1 caption-5 text-critical">{errors.symbols}</p>}
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Amount in ₹" error={errors.amount}>
              {(p) => <Input {...p} type="number" min="1" step="1000" value={f.amount} onChange={set('amount')} />}
            </Field>
            <Field label="Risk preference">
              {(p) => (
                <Select {...p} value={f.preference} onChange={set('preference')}>
                  <option value="conservative">Conservative</option>
                  <option value="moderate">Moderate</option>
                  <option value="aggressive">Aggressive</option>
                </Select>
              )}
            </Field>
            <Field label="Method">
              {(p) => <Select {...p} value={f.method} onChange={set('method')}>{METHODS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}</Select>}
            </Field>
            <Field label="Rebalancing in the backtest">
              {(p) => (
                <Select {...p} value={f.rebalance} onChange={set('rebalance')}>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="none">None (buy and hold)</option>
                </Select>
              )}
            </Field>
            <Field label="Minimum weight a stock, %" error={errors.minW}>
              {(p) => <Input {...p} type="number" min="0" max="100" value={f.minW} onChange={set('minW')} />}
            </Field>
            <Field label="Maximum weight a stock, %" error={errors.maxW} hint="Empty: 25, 35 or 50 from the risk preference">
              {(p) => <Input {...p} type="number" min="1" max="100" value={f.maxW} onChange={set('maxW')} />}
            </Field>
            {f.method === 'efficient_risk' && (
              <Field label="Target volatility, % a year" error={errors.targetVol}>
                {(p) => <Input {...p} type="number" min="1" value={f.targetVol} onChange={set('targetVol')} />}
              </Field>
            )}
            {f.method === 'efficient_return' && (
              <Field label="Target return, % a year" error={errors.targetRet}>
                {(p) => <Input {...p} type="number" value={f.targetRet} onChange={set('targetRet')} />}
              </Field>
            )}
            <Field label="Trading cost, basis points" hint="10 bps is 0.1% of each trade">
              {(p) => <Input {...p} type="number" min="0" max="200" value={f.cost} onChange={set('cost')} />}
            </Field>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="caption-5 text-ink-muted">Uses the last 252 trading days of prices. Takes a few seconds; no AI text is written here.</p>
            <Button type="submit" disabled={state.busy}>{state.busy ? 'Optimising' : 'Build the portfolio'}</Button>
          </div>
        </form>
      </Card>

      {state.error && <ErrorState message={state.error} />}
      {state.busy && <CardSkeleton rows={6} />}
      {!state.busy && !state.data && !state.error && (
        <EmptyState icon={ChartPieSlice} title="No portfolio yet">
          Choose at least two stocks and an amount. The result lists each stock&apos;s weight, rupee amount and whole
          shares, the past return and volatility of the mix, and how the same rule did against equal weights and the NIFTY 50.
        </EmptyState>
      )}
      {state.data?.not_found?.length > 0 && <ErrorState message={`Left out, no price data: ${state.data.not_found.join(', ')}`} />}
      {state.data && <PortfolioCard portfolio={state.data} />}
    </div>
  )
}
