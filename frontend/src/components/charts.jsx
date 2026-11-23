// Indicator charts (Recharts). Rules followed (dataviz guidance):
// one y-axis per chart (price, RSI and MACD are separate charts, never dual-axis),
// fixed categorical colour order, 2px lines, solid hairline grid, crosshair tooltip,
// a legend for every multi-series chart, and a table view for every chart.
import { useState } from 'react'
import { Table2 } from 'lucide-react'
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
import { Card } from './ui'
import { num } from '../utils/format'

// Hex values (not CSS variables): Recharts writes colours as SVG attributes, where var()
// is not reliably resolved. Same values as --color-series-* in index.css.
const C = {
  s1: '#3987e5',
  s2: '#d95926',
  s3: '#199e70',
  s4: '#c98500',
  grid: '#1f2d4a',
  axis: '#2c3b5c',
  muted: '#898781',
  surface: '#0f1b33',
  histogram: '#5b6a87', // neutral: sign is shown by position above/below zero
}

const shortDate = (d) => new Date(d).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
const longDate = (d) => new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

const axisProps = {
  stroke: C.axis,
  tick: { fill: C.muted, fontSize: 11 },
  tickLine: false,
}

function ChartTooltip({ active, payload, label, series }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-line bg-page/95 px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium text-ink">{longDate(label)}</div>
      {series.map((s) => {
        const p = payload.find((x) => x.dataKey === s.key)
        return (
          <div key={s.key} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-ink-secondary">
              <Swatch s={s} />
              {s.name}
            </span>
            <span className="tabular text-ink">{p?.value == null ? '—' : num(p.value, s.digits ?? 2)}</span>
          </div>
        )
      })}
    </div>
  )
}

function Swatch({ s }) {
  return s.kind === 'bar' ? (
    <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} aria-hidden="true" />
  ) : (
    <span className="inline-block h-0.5 w-3.5 rounded" style={{ background: s.color }} aria-hidden="true" />
  )
}

// Legend with the latest value of each series (identity never by colour alone).
function Legend({ series, last }) {
  return (
    <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {series.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5 text-ink-secondary">
          <Swatch s={s} />
          <span>{s.name}</span>
          <span className="tabular text-ink">{last?.[s.key] == null ? '—' : num(last[s.key], s.digits ?? 2)}</span>
        </li>
      ))}
    </ul>
  )
}

function DataTable({ data, series }) {
  const rows = data.slice(-20).reverse()
  return (
    <div className="max-h-72 overflow-auto rounded-lg border border-line">
      <table className="w-full text-left text-xs">
        <caption className="sr-only">Last 20 trading days</caption>
        <thead className="sticky top-0 bg-surface text-ink-muted">
          <tr>
            <th className="px-3 py-2 font-medium">Date</th>
            {series.map((s) => (
              <th key={s.key} className="px-3 py-2 text-right font-medium">{s.name}</th>
            ))}
          </tr>
        </thead>
        <tbody className="tabular">
          {rows.map((r) => (
            <tr key={r.date} className="border-t border-line">
              <td className="px-3 py-1.5 text-ink-secondary">{longDate(r.date)}</td>
              {series.map((s) => (
                <td key={s.key} className="px-3 py-1.5 text-right text-ink">{r[s.key] == null ? '—' : num(r[s.key], s.digits ?? 2)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ChartCard({ title, subtitle, data, series, height = 260, children }) {
  const [table, setTable] = useState(false)
  const last = data[data.length - 1]
  return (
    <Card
      title={title}
      subtitle={subtitle}
      actions={
        <button
          type="button"
          onClick={() => setTable((t) => !t)}
          aria-pressed={table}
          className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs text-ink-secondary hover:bg-white/5"
        >
          <Table2 className="h-3.5 w-3.5" aria-hidden="true" />
          {table ? 'Chart' : 'Table'}
        </button>
      }
    >
      <Legend series={series} last={last} />
      {table ? (
        <DataTable data={data} series={series} />
      ) : (
        <div style={{ height }} className="w-full">
          <ResponsiveContainer width="100%" height="100%">
            {children}
          </ResponsiveContainer>
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
  isAnimationActive: false, // cheaper on a low-RAM machine
})

const cursor = { stroke: C.muted, strokeWidth: 1 }

export function PriceChart({ data }) {
  const series = [
    { key: 'close', name: 'Close (₹)', color: C.s1 },
    { key: 'sma_20', name: 'SMA 20', color: C.s2 },
    { key: 'sma_50', name: 'SMA 50', color: C.s3 },
    { key: 'sma_200', name: 'SMA 200', color: C.s4 },
  ]
  return (
    <ChartCard title="Price and moving averages" subtitle="Daily close (unadjusted) with simple moving averages" data={data} series={series} height={300}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={40} {...axisProps} />
        <YAxis domain={['auto', 'auto']} width={56} tickFormatter={(v) => num(v, 0)} {...axisProps} />
        <Tooltip cursor={cursor} content={<ChartTooltip series={series} />} />
        {series.map((s, i) => <Line key={s.key} {...lineProps(s.key, s.color, i === 0 ? 2 : 1.5)} />)}
      </LineChart>
    </ChartCard>
  )
}

export function RsiChart({ data }) {
  const series = [{ key: 'rsi_14', name: 'RSI 14', color: C.s1 }]
  return (
    <ChartCard title="RSI (14)" subtitle="Above 70 is often read as overbought, below 30 as oversold" data={data} series={series} height={180}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={40} {...axisProps} />
        <YAxis domain={[0, 100]} ticks={[0, 30, 50, 70, 100]} width={56} {...axisProps} />
        <ReferenceLine y={70} stroke={C.muted} strokeWidth={1} label={{ value: '70', position: 'insideTopRight', fill: C.muted, fontSize: 10 }} />
        <ReferenceLine y={30} stroke={C.muted} strokeWidth={1} label={{ value: '30', position: 'insideBottomRight', fill: C.muted, fontSize: 10 }} />
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
    { key: 'macd_histogram', name: 'Histogram', color: C.histogram, kind: 'bar', digits: 3 },
  ]
  return (
    <ChartCard title="MACD (12, 26, 9)" subtitle="Histogram above zero: MACD above its signal line" data={data} series={series} height={200}>
      <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={C.grid} vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={40} {...axisProps} />
        <YAxis width={56} tickFormatter={(v) => num(v, 0)} {...axisProps} />
        <ReferenceLine y={0} stroke={C.axis} />
        <Tooltip cursor={{ fill: 'rgba(255,255,255,0.04)' }} content={<ChartTooltip series={series} />} />
        <Bar dataKey="macd_histogram" fill={C.histogram} isAnimationActive={false} />
        <Line {...lineProps('macd', C.s1)} />
        <Line {...lineProps('macd_signal', C.s2, 1.5)} />
      </ComposedChart>
    </ChartCard>
  )
}
