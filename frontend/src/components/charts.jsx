// Charts (task 12.1.3). Rules (dataviz skill): one y-axis per chart (never dual-axis), the
// categorical palette in fixed order (validated on the #1F1F1F surface), 2px lines, a recessive
// grid with muted mono labels, a crosshair tooltip, a legend for every multi-series chart and a
// table view for every chart. Text wears text colours; colour marks carry identity.
import { useState } from 'react'
import { ChartLine, Table as TableIcon } from '@phosphor-icons/react'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Card, table } from './ui'
import { num } from '../utils/format'

// Hex values (Recharts writes SVG attributes, where var() is not reliably resolved).
// Same values as the tokens in index.css.
export const C = {
  s1: '#3987e5',
  s2: '#d95926',
  s3: '#199e70',
  s4: '#c98500',
  grid: '#2b2b2b',
  axis: '#3a3a3a',
  muted: '#8a8a8f',
  surface: '#1f1f1f',
  neutral: '#5f5f63', // MACD histogram: the sign is shown by position, not colour
  good: '#0ca30c',
  critical: '#d03b3b',
}

const shortDate = (d) => new Date(d).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
const longDate = (d) => new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

// One tick on the first trading day of each month (thinned to at most `max`).
function monthTicks(data, max) {
  const firsts = []
  let prev = null
  for (const row of data) {
    const month = row.date.slice(0, 7)
    if (month !== prev) firsts.push(row.date)
    prev = month
  }
  const step = Math.ceil(firsts.length / max)
  return firsts.filter((_, i) => i % step === 0)
}

const priceDomain = [(min) => Math.floor(min * 0.97), (max) => Math.ceil(max * 1.03)]
const tick = { fill: C.muted, fontSize: 12, fontFamily: '"Geist Mono Variable", ui-monospace, monospace' }
const axisProps = { stroke: C.axis, tick, tickLine: false }
const cursor = { stroke: C.muted, strokeWidth: 1 }

function Swatch({ s }) {
  return s.kind === 'bar' ? (
    <span className="inline-block h-2 w-2 rounded-sm" style={{ background: s.color }} aria-hidden="true" />
  ) : (
    <span className="inline-block h-0.5 w-3 rounded" style={{ background: s.color }} aria-hidden="true" />
  )
}

function ChartTooltip({ active, payload, label, series }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-line bg-raised px-3 py-2 caption-5">
      <div className="mb-1 caption-4 text-ink">{longDate(label)}</div>
      {series.map((s) => {
        const p = payload.find((x) => x.dataKey === s.key)
        return (
          <div key={s.key} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-2 text-ink-secondary"><Swatch s={s} />{s.name}</span>
            <span className="figure text-ink">{p?.value == null ? 'n/a' : num(p.value, s.digits ?? 2)}</span>
          </div>
        )
      })}
    </div>
  )
}

// Legend with the latest value of each series: identity never by colour alone.
function Legend({ series, last }) {
  if (series.length < 2) return null
  return (
    <ul className="mb-4 flex flex-wrap gap-x-4 gap-y-1 caption-5">
      {series.map((s) => (
        <li key={s.key} className="flex items-center gap-2 text-ink-secondary">
          <Swatch s={s} />
          <span>{s.name}</span>
          <span className="figure text-ink">{last?.[s.key] == null ? 'n/a' : num(last[s.key], s.digits ?? 2)}</span>
        </li>
      ))}
    </ul>
  )
}

function DataTable({ data, series }) {
  const rows = data.slice(-20).reverse()
  return (
    <div className={`${table.wrap} max-h-72`}>
      <table className={table.table}>
        <caption className="sr-only">Last 20 trading days</caption>
        <thead className={`${table.thead} sticky top-0`}>
          <tr>
            <th className={table.th}>Date</th>
            {series.map((s) => <th key={s.key} className={table.thR}>{s.name}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.date} className={table.tr}>
              <td className={table.td}>{longDate(r.date)}</td>
              {series.map((s) => (
                <td key={s.key} className={table.tdR}>{r[s.key] == null ? 'n/a' : num(r[s.key], s.digits ?? 2)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ViewToggle({ table: isTable, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!isTable)}
      aria-pressed={isTable}
      className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 caption-4 text-ink-secondary transition-colors duration-300 ease-nv hover:bg-raised hover:text-ink"
    >
      {isTable ? <ChartLine size={14} aria-hidden="true" /> : <TableIcon size={14} aria-hidden="true" />}
      {isTable ? 'Chart' : 'Table'}
    </button>
  )
}

function ChartCard({ title, subtitle, data, series, height = 260, children }) {
  const [tableView, setTableView] = useState(false)
  return (
    <Card title={title} subtitle={subtitle} actions={<ViewToggle table={tableView} onChange={setTableView} />}>
      <Legend series={series} last={data[data.length - 1]} />
      {tableView ? (
        <DataTable data={data} series={series} />
      ) : (
        <div style={{ height }} className="w-full">
          <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
        </div>
      )}
    </Card>
  )
}

const lineProps = (key, color, width = 2) => ({
  type: 'monotone',
  dataKey: key,
  stroke: color,
  strokeWidth: width,
  dot: false,
  activeDot: { r: 4, stroke: C.surface, strokeWidth: 2 }, // 8px marker with a surface ring
  connectNulls: false,
  isAnimationActive: false,
})

export function PriceChart({ data, height = 320 }) {
  const series = [
    { key: 'close', name: 'Close (₹)', color: C.s1 },
    { key: 'sma_20', name: 'SMA 20', color: C.s2 },
    { key: 'sma_50', name: 'SMA 50', color: C.s3 },
    { key: 'sma_200', name: 'SMA 200', color: C.s4 },
  ]
  return (
    <ChartCard title="Price and moving averages" subtitle="Daily close (unadjusted) with simple moving averages" data={data} series={series} height={height}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="date" ticks={monthTicks(data, 12)} interval={0} tickFormatter={shortDate} {...axisProps} />
        <YAxis domain={priceDomain} width={56} tickFormatter={(v) => num(v, 0)} {...axisProps} />
        <Tooltip cursor={cursor} content={<ChartTooltip series={series} />} />
        {series.map((s, i) => <Line key={s.key} {...lineProps(s.key, s.color, i === 0 ? 2 : 1.5)} />)}
      </LineChart>
    </ChartCard>
  )
}

export function RsiChart({ data }) {
  const series = [{ key: 'rsi_14', name: 'RSI 14', color: C.s1 }]
  const ref = (v, pos) => ({ y: v, stroke: C.muted, strokeWidth: 1, strokeDasharray: '4 4',
    label: { value: String(v), position: pos, fill: C.muted, fontSize: 12 } })
  return (
    <ChartCard title="RSI (14)" subtitle="Above 70 is often read as overbought, below 30 as oversold" data={data} series={series} height={180}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="date" ticks={monthTicks(data, 6)} interval={0} tickFormatter={shortDate} {...axisProps} />
        <YAxis domain={[0, 100]} ticks={[0, 30, 50, 70, 100]} width={56} {...axisProps} />
        <ReferenceLine {...ref(70, 'insideTopRight')} />
        <ReferenceLine {...ref(30, 'insideBottomRight')} />
        <Tooltip cursor={cursor} content={<ChartTooltip series={series} />} />
        <Line {...lineProps('rsi_14', C.s1)} />
      </LineChart>
    </ChartCard>
  )
}

export function MacdChart({ data }) {
  const series = [
    { key: 'macd', name: 'MACD', color: C.s1, digits: 3 },
    { key: 'macd_signal', name: 'Signal', color: C.s2, digits: 3 },
    { key: 'macd_histogram', name: 'Histogram', color: C.neutral, kind: 'bar', digits: 3 },
  ]
  return (
    <ChartCard title="MACD (12, 26, 9)" subtitle="Histogram above zero: MACD above its signal line" data={data} series={series} height={180}>
      <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="date" ticks={monthTicks(data, 6)} interval={0} tickFormatter={shortDate} {...axisProps} />
        <YAxis width={56} tickFormatter={(v) => num(v, 0)} {...axisProps} />
        <ReferenceLine y={0} stroke={C.axis} />
        <Tooltip cursor={{ fill: 'rgba(237,237,237,0.04)' }} content={<ChartTooltip series={series} />} />
        <Bar dataKey="macd_histogram" fill={C.neutral} isAnimationActive={false} />
        <Line {...lineProps('macd', C.s1)} />
        <Line {...lineProps('macd_signal', C.s2, 1.5)} />
      </ComposedChart>
    </ChartCard>
  )
}

// Backtest equity curves: one y-axis (rupees), all series start from the same capital.
export function EquityChart({ data, capital }) {
  const series = [
    { key: 'strategy', name: 'This allocation rule (₹)', color: C.s1, digits: 0 },
    { key: 'equal_weight', name: 'Equal weights (₹)', color: C.s2, digits: 0 },
    { key: 'nifty50', name: 'NIFTY 50 (₹)', color: C.s3, digits: 0 },
  ].filter((s) => data.some((r) => r[s.key] != null))
  return (
    <ChartCard title="Backtest: value of the investment" subtitle="Out of sample, after transaction costs; the dashed line is the starting amount" data={data} series={series} height={280}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="date" ticks={monthTicks(data, 12)} interval={0} tickFormatter={shortDate} {...axisProps} />
        <YAxis domain={priceDomain} width={64} tickFormatter={(v) => num(v, 0)} {...axisProps} />
        <ReferenceLine y={capital} stroke={C.muted} strokeDasharray="4 4" strokeWidth={1} />
        <Tooltip cursor={cursor} content={<ChartTooltip series={series} />} />
        {series.map((s, i) => <Line key={s.key} {...lineProps(s.key, s.color, i === 0 ? 2 : 1.5)} />)}
      </LineChart>
    </ChartCard>
  )
}

// Small single-series line for the market overview (NIFTY 50). The title names the series.
export function MiniLine({ data, dataKey = 'close', height = 140, name = 'Close' }) {
  const series = [{ key: dataKey, name, color: C.s1 }]
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis dataKey="date" ticks={monthTicks(data, 4)} interval={0} tickFormatter={shortDate} {...axisProps} />
          <YAxis domain={priceDomain} width={56} tickFormatter={(v) => num(v, 0)} {...axisProps} />
          <Tooltip cursor={cursor} content={<ChartTooltip series={series} />} />
          <Line {...lineProps(dataKey, C.s1)} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// A share is a ranked list with thin bars (one accent), not a pie.
export function ShareBars({ rows, valueKey = 'weight_pct', labelKey = 'symbol', format = (v) => `${num(v)}%` }) {
  const sorted = [...rows].sort((a, b) => (b[valueKey] ?? 0) - (a[valueKey] ?? 0))
  return (
    <ul className="space-y-3">
      {sorted.map((r) => (
        <li key={r[labelKey]} title={`${r[labelKey]}: ${format(r[valueKey])}`}>
          <div className="flex items-baseline justify-between gap-3 caption-2">
            <span className="text-ink">{r[labelKey]}</span>
            <span className="figure text-ink">{format(r[valueKey])}</span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded bg-raised" aria-hidden="true">
            <div className="h-full rounded bg-accent" style={{ width: `${Math.max(0, Math.min(100, r[valueKey] ?? 0))}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

// Diverging blue (+1) to red (-1) with a neutral grey midpoint (dataviz diverging pair, dark steps).
const BLUE = [57, 135, 229]
const RED = [217, 76, 76]
const MID = [56, 56, 53]
function divergingColor(v) {
  const t = Math.max(-1, Math.min(1, v ?? 0))
  const pole = t >= 0 ? BLUE : RED
  const a = Math.abs(t)
  const mix = MID.map((m, i) => Math.round(m + (pole[i] - m) * a))
  return `rgb(${mix.join(',')})`
}

export function CorrelationHeatmap({ matrix }) {
  const [tableView, setTableView] = useState(false)
  const names = Object.keys(matrix || {})
  if (names.length < 2) return null
  const short = (s) => s.replace(/\.(NS|BO)$/, '')
  return (
    <Card
      title="Correlation of daily returns"
      subtitle="1 means the two stocks moved together; low or negative values help diversification"
      actions={<ViewToggle table={tableView} onChange={setTableView} />}
    >
      {tableView ? (
        <div className={table.wrap}>
          <table className={table.table}>
            <thead className={table.thead}>
              <tr><th className={table.th}>Stock</th>{names.map((n) => <th key={n} className={table.thR}>{short(n)}</th>)}</tr>
            </thead>
            <tbody>
              {names.map((a) => (
                <tr key={a} className={table.tr}>
                  <td className={table.td}>{short(a)}</td>
                  {names.map((b) => <td key={b} className={table.tdR}>{num(matrix[a]?.[b], 2)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div className="inline-grid gap-0.5" style={{ gridTemplateColumns: `auto repeat(${names.length}, minmax(48px, 64px))` }}>
            <span />
            {names.map((n) => <span key={n} className="pb-1 text-center figure caption-5 text-ink-muted">{short(n)}</span>)}
            {names.map((a) => (
              <div key={a} className="contents">
                <span className="pr-2 text-right figure caption-5 leading-10 text-ink-muted">{short(a)}</span>
                {names.map((b) => {
                  const v = matrix[a]?.[b]
                  return (
                    <span key={b} title={`${short(a)} and ${short(b)}: ${num(v, 2)}`}
                          className="flex h-10 items-center justify-center rounded figure caption-5 text-ink"
                          style={{ background: divergingColor(v) }}>
                      {num(v, 2)}
                    </span>
                  )
                })}
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-2 caption-5 text-ink-muted" aria-hidden="true">
            <span className="figure">-1</span>
            <span className="h-2 w-32 rounded" style={{ background: `linear-gradient(to right, ${divergingColor(-1)}, ${divergingColor(0)}, ${divergingColor(1)})` }} />
            <span className="figure">+1</span>
          </div>
        </div>
      )}
    </Card>
  )
}

// One stacked bar for a share of articles; 2px surface gaps between segments; labelled legend.
const SENTIMENT = [
  ['positive', 'Positive', C.good],
  ['neutral', 'Neutral', '#6b6b70'],
  ['uncertain', 'Uncertain', '#46464a'],
  ['negative', 'Negative', C.critical],
]
export function SentimentBar({ breakdown }) {
  const total = SENTIMENT.reduce((s, [k]) => s + (breakdown?.[k] || 0), 0)
  if (!total) return null
  return (
    <div>
      <div className="flex h-3 gap-0.5 overflow-hidden rounded" role="img"
           aria-label={SENTIMENT.map(([k, l]) => `${l} ${breakdown?.[k] || 0}`).join(', ')}>
        {SENTIMENT.filter(([k]) => breakdown?.[k]).map(([k, l, color]) => (
          <span key={k} title={`${l}: ${breakdown[k]}`} style={{ width: `${(100 * breakdown[k]) / total}%`, background: color }} />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 caption-5 text-ink-secondary">
        {SENTIMENT.map(([k, l, color]) => (
          <li key={k} className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: color }} aria-hidden="true" />
            {l} <span className="figure text-ink">{breakdown?.[k] || 0}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
