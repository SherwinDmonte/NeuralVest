// Annual financial statements as reported (GET /stocks/{symbol}/financials). Shown in crore
// rupees (1 crore = 10,000,000) for reading; per share items stay as reported. Missing items
// stay missing.
import { useState } from 'react'
import { Receipt } from '@phosphor-icons/react'
import { AnimatedTabs } from './motion'
import { Card, ErrorState, Meta, Skeleton, Checkbox, table } from './ui'
import { useApi } from '../hooks/useApi'
import { getFinancials } from '../services/api'
import { fmtDate, num } from '../utils/format'

const KEY_ITEMS = {
  income_statement: ['Total Revenue', 'Gross Profit', 'Operating Income', 'EBITDA', 'Pretax Income', 'Tax Provision', 'Net Income', 'Basic EPS', 'Diluted EPS'],
  balance_sheet: ['Total Assets', 'Current Assets', 'Cash And Cash Equivalents', 'Total Liabilities Net Minority Interest', 'Current Liabilities', 'Total Debt', 'Stockholders Equity', 'Retained Earnings'],
  cash_flow: ['Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow', 'Capital Expenditure', 'Free Cash Flow', 'Cash Dividends Paid'],
}
const TABS = [
  { value: 'income_statement', label: 'Income statement' },
  { value: 'balance_sheet', label: 'Balance sheet' },
  { value: 'cash_flow', label: 'Cash flow' },
]
const PER_SHARE = /EPS|Per Share/i

const fmt = (item, v) => (v == null ? 'n/a' : PER_SHARE.test(item) ? num(v) : num(v / 1e7, 0))

export default function Statements({ symbol }) {
  const [tab, setTab] = useState('income_statement')
  const [all, setAll] = useState(false)
  const { data, error, loading } = useApi(() => getFinancials(symbol), [symbol], { key: `fin-${symbol}`, ttl: 30 * 60 * 1000 })
  const periods = data ? Object.keys(data.statements[tab] || {}).slice(0, 4) : []
  const items = data ? (all
    ? [...new Set(periods.flatMap((p) => Object.keys(data.statements[tab][p] || {})))].sort()
    : KEY_ITEMS[tab].filter((i) => periods.some((p) => data.statements[tab][p]?.[i] != null))) : []

  return (
    <Card title="Financial statements" icon={Receipt}
          subtitle={data ? `Annual, as reported · amounts in ₹ crore except per share items · ${data.source}` : 'Annual, as reported'}
          actions={<AnimatedTabs size="sm" label="Statement" tabs={TABS} value={tab} onChange={setTab} />}>
      {loading && !data && <div className="space-y-2">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-8" />)}</div>}
      {error && <ErrorState message={error} />}
      {data && (
        <div className="space-y-4">
          {periods.length === 0 ? <p className="body-6 text-ink-muted">This statement is not available for {symbol}.</p> : (
            <div className={table.wrap}>
              <table className={table.table}>
                <caption className="sr-only">{TABS.find((t) => t.value === tab).label}</caption>
                <thead className={table.thead}>
                  <tr><th className={table.th}>Line item</th>{periods.map((p) => <th key={p} className={table.thR}>FY ending {fmtDate(p)}</th>)}</tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item} className={table.tr}>
                      <td className={table.td}>{item}</td>
                      {periods.map((p) => <td key={p} className={table.tdR}>{fmt(item, data.statements[tab][p]?.[item])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Checkbox label="Show every line item" checked={all} onChange={(e) => setAll(e.target.checked)} />
            <Meta>{data.is_stale ? 'latest annual statement is more than a year old · ' : ''}fetched {fmtDate(data.fetched_at)}</Meta>
          </div>
          {data.missing_key_items?.[tab]?.length > 0 && <p className="caption-5 text-ink-muted">Not reported: {data.missing_key_items[tab].join(', ')}.</p>}
        </div>
      )}
    </Card>
  )
}
