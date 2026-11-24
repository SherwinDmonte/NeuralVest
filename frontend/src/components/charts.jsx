// Charts (Phase 12, redesigned in 12B). Rules kept from the dataviz method: one y-axis per chart
// (never dual-axis), categorical colours in fixed order (dark steps validated on #111C30, light
// steps on #FFFFFF), 2px lines, a recessive grid with mono labels, a crosshair tooltip, a legend
// for every multi-series chart and a table view. Text wears text colours; marks carry identity.
// New in 12B: theme-aware colours, gradient area fills, sparklines, volume, donut, scatter,
// histogram and comparison bars.
import { useId, useState } from 'react'
import { ChartLine, Table as TableIcon } from '@phosphor-icons/react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import { Card, table } from './ui'
import { useTheme } from '../theme/ThemeContext'
import { num } from '../utils/format'

// SVG attributes need real colours (not var()), so each theme has its own set.
const PALETTES = {
  dark: {
    s: ['#3987e5', '#d95926', '#199e70', '#c98500'],
    grid: 'rgba(148,163,184,0.10)', axis: 'rgba(148,163,184,0.28)', muted: '#7d8ca3', surface: '#111c30',
    neutral: '#4b5b75', good: '#22c55e', critical: '#f0526e', teal: '#16c7b7', blue: '#438bff', violet: '#9b6bff',
    divNeg: [230, 103, 103], divPos: [57, 135, 229], divMid: [42, 52, 72], sentimentNeutral: '#5b6b85', sentimentUncertain: '#3a4760',
  },
  light: {
    s: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'],
    grid: '#e8edf5', axis: '#cbd5e1', muted: '#64748b', surface: '#ffffff',
    neutral: '#94a3b8', good: '#15803d', critical: '#be123c', teal: '#0d9488', blue: '#2563eb', violet: '#7c3aed',
    divNeg: [227, 73, 72], divPos: [42, 120, 214], divMid: [240, 239, 236], sentimentNeutral: '#94a3b8', sentimentUncertain: '#cbd5e1',
  },
}

export function useChartColors() {
  const { resolved } = useTheme()
  return PALETTES[resolved] || PALETTES.dark
}

const shortDate = (d) => new Date(d).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
const longDate = (d) => new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

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
const tickFont = '"Geist Mono Variable", ui-monospace, monospace'
const axisProps = (c) => ({ stroke: c.axis, tick: { fill: c.muted, fontSize: 12, fontFamily: tickFont }, tickLine: false })

function Swatch({ s }) {
  return s.kind === 'bar' ? (
    <span className="inline-block h-2 w-2 rounded-sm" style={{ background: s.color }} aria-hidden="true" />
  ) : (
    <span className="inline-block h-0.5 w-3 rounded" style={{ background: s.color }} aria-hidden="true" />
  )
}

function ChartTooltip({ active, payload, label, series, labelFormat = longDate }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-line-strong glass-strong px-3 py-2 caption-5 shadow-float">
      <div className="mb-1 caption-4 text-ink">{labelFormat(label)}</div>
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

function DataTable({ data, series, rows = 20 }) {
  const shown = data.slice(-rows).reverse()
  return (
    <div className={`${table.wrap} max-h-72`}>
      <table className={table.table}>
        <caption className="sr-only">Last {rows} values</caption>
        <thead className={`${table.thead} sticky top-0`}>
          <tr>
            <th className={table.th}>Date</th>
            {series.map((s) => <th key={s.key} className={table.thR}>{s.name}</th>)}
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.date} className={table.tr}>
              <td className={table.td}>{longDate(r.date)}</td>
              {series.map((s) => <td key={s.key} className={table.tdR}>{r[s.key] == null ? 'n/a' : num(r[s.key], s.digits ?? 2)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ViewToggle({ table: isTable, onChange }) {
  return (
    <button type="button" onClick={() => onChange(!isTable)} aria-pressed={isTable}
            className="inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 caption-4 text-ink-secondary transition-colors duration-300 ease-nv hover:bg-raised hover:text-ink">
      {isTable ? <ChartLine size={14} aria-hidden="true" /> : <TableIcon size={14} aria-hidden="true" />}
      {isTable ? 'Chart' : 'Table'}
    </button>
  )
}

export function ChartCard({ title, subtitle, data, series, height = 260, children, actions, legend = true, icon }) {
  const [tableView, setTableView] = useState(false)
  return (
    <Card title={title} subtitle={subtitle} icon={icon}
          actions={<div className="flex flex-wrap items-center gap-2">{actions}<ViewToggle table={tableView} onChange={setTableView} /></div>}>
      {legend && <Legend series={series} last={data[data.length - 1]} />}
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

const lineProps = (key, color, c, width = 2) => ({
  type: 'monotone', dataKey: key, stroke: color, strokeWidth: width, dot: false,
  activeDot: { r: 4, stroke: c.surface, strokeWidth: 2 }, connectNulls: false, isAnimationActive: true,
  animationDuration: 700, animationEasing: 'ease-out',
})

// Vertical gradient fill for an area (colour at the top fading to transparent).
function AreaGradient({ id, color, opacity = 0.35 }) {
  return (
    <defs>
      <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={color} stopOpacity={opacity} />
        <stop offset="100%" stopColor={color} stopOpacity={0} />
      </linearGradient>
    </defs>
  )
}

// ------------------------------------------------------------------ price and indicators
export function PriceChart({ data, height = 340, actions }) {
  const c = useChartColors()
  const gid = useId().replace(/:/g, '')
  const series = [
    { key: 'close', name: 'Close (₹)', color: c.s[0] },
    { key: 'sma_20', name: 'SMA 20', color: c.s[1] },
    { key: 'sma_50', name: 'SMA 50', color: c.s[2] },
    { key: 'sma_200', name: 'SMA 200', color: c.s[3] },
  ]
  const cursor = { stroke: c.muted, strokeWidth: 1, strokeDasharray: '3 3' }
  return (
    <ChartCard title="Price and moving averages" subtitle="Daily close (unadjusted) with simple moving averages" data={data} series={series} height={height} actions={actions}>
      <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <AreaGradient id={gid} color={c.s[0]} />
        <CartesianGrid stroke={c.grid} vertical={false} />
        <XAxis dataKey="date" ticks={monthTicks(data, 12)} interval={0} tickFormatter={shortDate} {...axisProps(c)} />
        <YAxis domain={priceDomain} width={56} tickFormatter={(v) => num(v, 0)} {...axisProps(c)} />
        <Tooltip cursor={cursor} content={<ChartTooltip series={series} />} />
        <Area {...lineProps('close', c.s[0], c)} fill={`url(#${gid})`} />
        {series.slice(1).map((s) => <Line key={s.key} {...lineProps(s.key, s.color, c, 1.5)} />)}
      </ComposedChart>
    </ChartCard>
  )
}

export function VolumeChart({ data, height = 160 }) {
  const c = useChartColors()
  const series = [{ key: 'volume', name: 'Volume (shares)', color: c.neutral, kind: 'bar', digits: 0 }]
  return (
    <ChartCard title="Volume" subtitle="Shares traded each day" data={data} series={series} height={height} legend={false}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={c.grid} vertical={false} />
        <XAxis dataKey="date" ticks={monthTicks(data, 6)} interval={0} tickFormatter={shortDate} {...axisProps(c)} />
        <YAxis width={56} tickFormatter={(v) => (v >= 1e7 ? `${num(v / 1e7, 1)}Cr` : v >= 1e5 ? `${num(v / 1e5, 1)}L` : num(v, 0))} {...axisProps(c)} />
        <Tooltip cursor={{ fill: c.grid }} content={<ChartTooltip series={series} />} />
        <Bar dataKey="volume" fill={c.neutral} radius={[2, 2, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ChartCard>
  )
}

export function RsiChart({ data }) {
  const c = useChartColors()
  const series = [{ key: 'rsi_14', name: 'RSI 14', color: c.s[0] }]
  const ref = (v, pos) => ({ y: v, stroke: c.muted, strokeWidth: 1, strokeDasharray: '4 4', label: { value: String(v), position: pos, fill: c.muted, fontSize: 12 } })
  return (
    <ChartCard title="RSI (14)" subtitle="Above 70 is often read as overbought, below 30 as oversold" data={data} series={series} height={180}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={c.grid} vertical={false} />
        <XAxis dataKey="date" ticks={monthTicks(data, 6)} interval={0} tickFormatter={shortDate} {...axisProps(c)} />
        <YAxis domain={[0, 100]} ticks={[0, 30, 50, 70, 100]} width={56} {...axisProps(c)} />
        <ReferenceLine {...ref(70, 'insideTopRight')} />
        <ReferenceLine {...ref(30, 'insideBottomRight')} />
        <Tooltip cursor={{ stroke: c.muted }} content={<ChartTooltip series={series} />} />
        <Line {...lineProps('rsi_14', c.s[0], c)} />
      </LineChart>
    </ChartCard>
  )
}

export function MacdChart({ data }) {
  const c = useChartColors()
  const series = [
    { key: 'macd', name: 'MACD', color: c.s[0], digits: 3 },
    { key: 'macd_signal', name: 'Signal', color: c.s[1], digits: 3 },
    { key: 'macd_histogram', name: 'Histogram', color: c.neutral, kind: 'bar', digits: 3 },
  ]
  return (
    <ChartCard title="MACD (12, 26, 9)" subtitle="Histogram above zero: MACD above its signal line" data={data} series={series} height={180}>
      <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={c.grid} vertical={false} />
        <XAxis dataKey="date" ticks={monthTicks(data, 6)} interval={0} tickFormatter={shortDate} {...axisProps(c)} />
        <YAxis width={56} tickFormatter={(v) => num(v, 0)} {...axisProps(c)} />
        <ReferenceLine y={0} stroke={c.axis} />
        <Tooltip cursor={{ fill: c.grid }} content={<ChartTooltip series={series} />} />
        <Bar dataKey="macd_histogram" fill={c.neutral} isAnimationActive={false} />
        <Line {...lineProps('macd', c.s[0], c)} />
        <Line {...lineProps('macd_signal', c.s[1], c, 1.5)} />
      </ComposedChart>
    </ChartCard>
  )
}

// ------------------------------------------------------------------ market (overview, market page)
// Large area chart of one series with the brand gradient. `actions` holds the range tabs.
export function MarketAreaChart({ title, subtitle, data, dataKey = 'close', name = 'Close', height = 320, actions, icon }) {
  const c = useChartColors()
  const gid = useId().replace(/:/g, '')
  const series = [{ key: dataKey, name, color: c.blue }]
  return (
    <ChartCard title={title} subtitle={subtitle} data={data} series={series} height={height} actions={actions} legend={false} icon={icon}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`${gid}-stroke`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={c.teal} />
            <stop offset="55%" stopColor={c.blue} />
            <stop offset="100%" stopColor={c.violet} />
          </linearGradient>
          <linearGradient id={`${gid}-fill`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={c.blue} stopOpacity={0.32} />
            <stop offset="100%" stopColor={c.violet} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={c.grid} vertical={false} />
        <XAxis dataKey="date" ticks={monthTicks(data, 8)} interval={0} tickFormatter={shortDate} {...axisProps(c)} />
        <YAxis domain={priceDomain} width={64} tickFormatter={(v) => num(v, 0)} {...axisProps(c)} />
        <Tooltip cursor={{ stroke: c.muted, strokeDasharray: '3 3' }} content={<ChartTooltip series={series} />} />
        <Area type="monotone" dataKey={dataKey} stroke={`url(#${gid}-stroke)`} strokeWidth={2.25} fill={`url(#${gid}-fill)`}
              dot={false} activeDot={{ r: 5, stroke: c.surface, strokeWidth: 2, fill: c.blue }} animationDuration={800} />
      </AreaChart>
    </ChartCard>
  )
}

// Tiny trend line for cards. No axes; colour follows the direction of the period.
export function Sparkline({ data, dataKey = 'close', height = 44, up }) {
  const c = useChartColors()
  const gid = useId().replace(/:/g, '')
  if (!data?.length) return null
  const color = up == null ? c.blue : up ? c.good : c.critical
  return (
    <div style={{ height }} className="w-full" aria-hidden="true">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
          <AreaGradient id={gid} color={color} opacity={0.28} />
          <YAxis hide domain={['dataMin', 'dataMax']} />
          <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.75} fill={`url(#${gid})`} dot={false} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// Backwards compatible small line (Phase 12 dashboard).
export function MiniLine({ data, dataKey = 'close', height = 140, name = 'Close' }) {
  const c = useChartColors()
  const series = [{ key: dataKey, name, color: c.s[0] }]
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={c.grid} vertical={false} />
          <XAxis dataKey="date" ticks={monthTicks(data, 4)} interval={0} tickFormatter={shortDate} {...axisProps(c)} />
          <YAxis domain={priceDomain} width={56} tickFormatter={(v) => num(v, 0)} {...axisProps(c)} />
          <Tooltip cursor={{ stroke: c.muted }} content={<ChartTooltip series={series} />} />
          <Line {...lineProps(dataKey, c.s[0], c)} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ------------------------------------------------------------------ portfolio
export function EquityChart({ data, capital }) {
  const c = useChartColors()
  const gid = useId().replace(/:/g, '')
  const series = [
    { key: 'strategy', name: 'This allocation rule (₹)', color: c.s[0], digits: 0 },
    { key: 'equal_weight', name: 'Equal weights (₹)', color: c.s[1], digits: 0 },
    { key: 'nifty50', name: 'NIFTY 50 (₹)', color: c.s[2], digits: 0 },
  ].filter((s) => data.some((r) => r[s.key] != null))
  return (
    <ChartCard title="Backtest: value of the investment" subtitle="Historical, out of sample, after transaction costs; the dashed line is the starting amount" data={data} series={series} height={300}>
      <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <AreaGradient id={gid} color={c.s[0]} opacity={0.22} />
        <CartesianGrid stroke={c.grid} vertical={false} />
        <XAxis dataKey="date" ticks={monthTicks(data, 12)} interval={0} tickFormatter={shortDate} {...axisProps(c)} />
        <YAxis domain={priceDomain} width={64} tickFormatter={(v) => num(v, 0)} {...axisProps(c)} />
        <ReferenceLine y={capital} stroke={c.muted} strokeDasharray="4 4" strokeWidth={1} />
        <Tooltip cursor={{ stroke: c.muted }} content={<ChartTooltip series={series} />} />
        <Area {...lineProps('strategy', c.s[0], c)} fill={`url(#${gid})`} />
        {series.slice(1).map((s) => <Line key={s.key} {...lineProps(s.key, s.color, c, 1.5)} />)}
      </ComposedChart>
    </ChartCard>
  )
}

// Allocation donut: categorical colours in fixed order (more than 4 stocks: the remaining
// slices use neutral steps and the legend carries identity). Weights in the centre legend.
export function DonutChart({ rows, valueKey = 'weight_pct', labelKey = 'symbol', centerLabel = 'Target weights' }) {
  const c = useChartColors()
  const [activeIdx, setActive] = useState(null)
  const colors = rows.map((_, i) => c.s[i] || [c.neutral, c.muted, c.axis][(i - 4) % 3])
  const active = activeIdx != null ? rows[activeIdx] : null
  return (
    <div className="grid items-center gap-6 sm:grid-cols-[200px_1fr]">
      <div className="relative mx-auto h-[200px] w-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={rows} dataKey={valueKey} nameKey={labelKey} innerRadius={64} outerRadius={96} paddingAngle={2}
                 stroke={c.surface} strokeWidth={2} onMouseEnter={(_, i) => setActive(i)} onMouseLeave={() => setActive(null)}
                 animationDuration={700}>
              {rows.map((r, i) => <Cell key={r[labelKey]} fill={colors[i]} opacity={activeIdx == null || activeIdx === i ? 1 : 0.45} />)}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div>
            <div className="caption-5 text-ink-muted">{active ? active[labelKey] : centerLabel}</div>
            <div className="figure-2 text-ink">{active ? `${num(active[valueKey])}%` : `${rows.length} stocks`}</div>
          </div>
        </div>
      </div>
      <ul className="space-y-2">
        {rows.map((r, i) => (
          <li key={r[labelKey]} onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}
              className={`flex items-center justify-between gap-3 rounded-lg px-2 py-1 transition-colors duration-300 ease-nv ${activeIdx === i ? 'bg-raised' : ''}`}>
            <span className="flex items-center gap-2 caption-2 text-ink"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: colors[i] }} />{r[labelKey]}</span>
            <span className="figure caption-2 text-ink">{num(r[valueKey])}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// Past return against past volatility for each stock, plus the portfolio (a larger point).
// Two different measures on two axes of ONE scatter (not a dual-axis chart).
function ScatterTip({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="rounded-xl border border-line-strong glass-strong px-3 py-2 caption-5 shadow-float">
      <div className="caption-4 text-ink">{p.label}</div>
      <div className="text-ink-secondary">Past return a year <span className="figure text-ink">{num(p.ret)}%</span></div>
      <div className="text-ink-secondary">Volatility <span className="figure text-ink">{num(p.vol)}%</span></div>
    </div>
  )
}

export function RiskReturnScatter({ points, portfolio }) {
  const c = useChartColors()
  const data = points.map((p, i) => ({ ...p, fill: c.s[i] || c.neutral }))
  return (
    <div>
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
          <CartesianGrid stroke={c.grid} />
          <XAxis type="number" dataKey="vol" name="Volatility" unit="%" {...axisProps(c)}
                 label={{ value: 'Volatility, % a year', position: 'insideBottom', offset: -8, fill: c.muted, fontSize: 12 }} />
          <YAxis type="number" dataKey="ret" name="Return" unit="%" width={56} {...axisProps(c)} />
          <ZAxis type="number" dataKey="z" range={[90, 260]} />
          <ReferenceLine y={0} stroke={c.axis} />
          <Tooltip content={<ScatterTip />} cursor={{ strokeDasharray: '3 3', stroke: c.muted }} />
          <Scatter data={data.map((d) => ({ ...d, z: 1 }))}>
            {data.map((d) => <Cell key={d.label} fill={d.fill} stroke={c.surface} strokeWidth={2} />)}
          </Scatter>
          {portfolio && (
            <Scatter data={[{ ...portfolio, z: 3 }]} shape="diamond">
              <Cell fill={c.violet} stroke={c.surface} strokeWidth={2} />
            </Scatter>
          )}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 caption-2 text-ink-secondary" aria-label="Chart key">
      {data.map((d) => <li key={d.label} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: d.fill }} />{d.label}</li>)}
      {portfolio && <li className="flex items-center gap-2"><span className="h-2.5 w-2.5 rotate-45" style={{ background: c.violet }} />{portfolio.label || 'This mix'}</li>}
    </ul>
    </div>
  )
}

// Horizontal comparison bars (e.g. backtest CAGR: this rule, equal weights, NIFTY 50).
export function ComparisonBars({ rows, unit = '%' }) {
  const c = useChartColors()
  const max = Math.max(...rows.map((r) => Math.abs(r.value ?? 0)), 1)
  return (
    <ul className="space-y-3">
      {rows.map((r, i) => (
        <li key={r.label}>
          <div className="flex items-baseline justify-between gap-3 caption-2">
            <span className="flex items-center gap-2 text-ink"><span className="h-2 w-2 rounded-sm" style={{ background: c.s[i] }} />{r.label}</span>
            <span className="figure text-ink">{r.value == null ? 'n/a' : `${r.value > 0 ? '+' : ''}${num(r.value)}${unit}`}</span>
          </div>
          <div className="relative mt-1 h-2 overflow-hidden rounded bg-raised" aria-hidden="true">
            <span className="absolute inset-y-0 left-1/2 z-10 w-0.5 -translate-x-1/2 bg-ink-muted" />
            {r.value != null && (
              <span className="absolute inset-y-0 rounded" style={{
                background: c.s[i],
                left: r.value >= 0 ? '50%' : `${50 - (50 * Math.abs(r.value)) / max}%`,
                width: `${(50 * Math.abs(r.value)) / max}%`,
              }} />
            )}
          </div>
        </li>
      ))}
      <li className="flex justify-between figure caption-5 text-ink-muted" aria-hidden="true">
        <span>-{num(max)}{unit}</span><span>0</span><span>+{num(max)}{unit}</span>
      </li>
    </ul>
  )
}

// A share is a ranked list with thin bars.
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
            <div className="h-full rounded bg-brand" style={{ width: `${Math.max(0, Math.min(100, r[valueKey] ?? 0))}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

// ------------------------------------------------------------------ risk
// Histogram of daily returns: losses red, gains green, the 5% tail marked.
function HistogramTip({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="rounded-xl border border-line-strong glass-strong px-3 py-2 caption-5 shadow-float">
      <div className="caption-4 text-ink">{p.label}</div>
      <div className="text-ink-secondary"><span className="figure text-ink">{p.count}</span> trading days</div>
    </div>
  )
}

export function ReturnHistogram({ bins, p5 }) {
  const c = useChartColors()
  const data = (bins || []).map((b) => ({ ...b, mid: (b.from + b.to) / 2, label: `${num(b.from, 1)}% to ${num(b.to, 1)}%` }))
  if (!data.length) return null
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 22, right: 8, bottom: 0, left: 0 }} barCategoryGap={2}>
          <CartesianGrid stroke={c.grid} vertical={false} />
          <XAxis dataKey="mid" tickFormatter={(v) => `${num(v, 1)}%`} {...axisProps(c)} interval="preserveStartEnd" />
          <YAxis width={40} allowDecimals={false} {...axisProps(c)} />
          <Tooltip cursor={{ fill: c.grid }} content={<HistogramTip />} />
          {p5 != null && <ReferenceLine x={data.reduce((best, d) => (Math.abs(d.mid - p5) < Math.abs(best.mid - p5) ? d : best), data[0]).mid}
                                        stroke={c.critical} strokeDasharray="4 4" label={{ value: '5% tail', fill: c.muted, fontSize: 12, position: 'top' }} />}
          <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive>
            {data.map((d) => <Cell key={d.mid} fill={d.mid < 0 ? c.critical : c.good} fillOpacity={0.8} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// One measure across stocks as horizontal bars (e.g. volatility). Labels carry the values.
export function MetricBars({ rows, unit = '%', digits = 2 }) {
  const max = Math.max(...rows.map((r) => Math.abs(r.value ?? 0)), 1)
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.label}>
          <div className="flex items-baseline justify-between gap-3 caption-2">
            <span className="text-ink">{r.label}</span>
            <span className="figure text-ink">{r.value == null ? 'n/a' : `${num(r.value, digits)}${unit}`}</span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded bg-raised" aria-hidden="true">
            <div className={`h-full rounded ${r.tone === 'critical' ? 'bg-critical' : r.tone === 'warning' ? 'bg-warning' : 'bg-brand'}`}
                 style={{ width: `${(100 * Math.abs(r.value ?? 0)) / max}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

function divergingColor(v, c) {
  const t = Math.max(-1, Math.min(1, v ?? 0))
  const pole = t >= 0 ? c.divPos : c.divNeg
  const a = Math.abs(t)
  return `rgb(${c.divMid.map((m, i) => Math.round(m + (pole[i] - m) * a)).join(',')})`
}

export function CorrelationHeatmap({ matrix }) {
  const c = useChartColors()
  const [tableView, setTableView] = useState(false)
  const names = Object.keys(matrix || {})
  if (names.length < 2) return null
  const short = (s) => s.replace(/\.(NS|BO)$/, '')
  const textOn = (v) => (Math.abs(v ?? 0) > 0.55 ? '#ffffff' : 'var(--nv-ink)')
  return (
    <Card title="Correlation of daily returns" subtitle="1 means the two stocks moved together; low or negative values help diversification"
          actions={<ViewToggle table={tableView} onChange={setTableView} />}>
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
          <div className="inline-grid gap-1" style={{ gridTemplateColumns: `auto repeat(${names.length}, minmax(48px, 72px))` }}>
            <span />
            {names.map((n) => <span key={n} className="pb-1 text-center figure caption-5 text-ink-muted">{short(n)}</span>)}
            {names.map((a) => (
              <div key={a} className="contents">
                <span className="pr-2 text-right figure caption-5 leading-10 text-ink-muted">{short(a)}</span>
                {names.map((b) => {
                  const v = matrix[a]?.[b]
                  return (
                    <span key={b} title={`${short(a)} and ${short(b)}: ${num(v, 2)}`}
                          className="flex h-10 items-center justify-center rounded-lg figure caption-4 transition-transform duration-300 ease-nv hover:scale-105"
                          style={{ background: divergingColor(v, c), color: textOn(v) }}>
                      {num(v, 2)}
                    </span>
                  )
                })}
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-2 caption-5 text-ink-muted" aria-hidden="true">
            <span className="figure">-1</span>
            <span className="h-2 w-32 rounded" style={{ background: `linear-gradient(to right, ${divergingColor(-1, c)}, ${divergingColor(0, c)}, ${divergingColor(1, c)})` }} />
            <span className="figure">+1</span>
          </div>
        </div>
      )}
    </Card>
  )
}

export function SentimentBar({ breakdown }) {
  const c = useChartColors()
  const parts = [
    ['positive', 'Positive', c.good],
    ['neutral', 'Neutral', c.sentimentNeutral],
    ['uncertain', 'Uncertain', c.sentimentUncertain],
    ['negative', 'Negative', c.critical],
  ]
  const total = parts.reduce((s, [k]) => s + (breakdown?.[k] || 0), 0)
  if (!total) return null
  return (
    <div>
      <div className="flex h-3 gap-0.5 overflow-hidden rounded" role="img" aria-label={parts.map(([k, l]) => `${l} ${breakdown?.[k] || 0}`).join(', ')}>
        {parts.filter(([k]) => breakdown?.[k]).map(([k, l, color]) => (
          <span key={k} title={`${l}: ${breakdown[k]}`} style={{ width: `${(100 * breakdown[k]) / total}%`, background: color }} />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 caption-5 text-ink-secondary">
        {parts.map(([k, l, color]) => (
          <li key={k} className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: color }} aria-hidden="true" />
            {l} <span className="figure text-ink">{breakdown?.[k] || 0}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
