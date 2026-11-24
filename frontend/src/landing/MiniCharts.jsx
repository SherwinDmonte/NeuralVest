// Lightweight SVG charts for the landing page (no chart library, so the page stays small).
// Lines draw themselves in and bars grow with transform once their section is visible
// (.is-visible on an ancestor); with reduced motion they appear complete.
import { useId } from 'react'

// A line chart over a fixed 600 x H canvas that scales with its container.
export function LineChart({ data, series, height = 180, area = true, label, className = '' }) {
  const gid = useId().replace(/:/g, '')
  const W = 600
  const pad = 6
  const values = data.flatMap((d) => series.map((s) => d[s.key])).filter((v) => v != null)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const x = (i) => pad + (i * (W - 2 * pad)) / Math.max(1, data.length - 1)
  const y = (v) => pad + (1 - (v - min) / span) * (height - 2 * pad)
  const path = (key) => data.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(d[key]).toFixed(1)}`).join(' ')
  const first = series[0]
  return (
    <svg viewBox={`0 0 ${W} ${height}`} className={`block h-auto w-full overflow-visible ${className}`} role="img" aria-label={label}>
      <defs>
        <linearGradient id={`${gid}-a`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={first.color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={first.color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((t) => (
        <line key={t} x1="0" x2={W} y1={height * t} y2={height * t} stroke="var(--nv-line)" strokeWidth="1" />
      ))}
      {area && (
        <path className="lp-fade" d={`${path(first.key)} L${x(data.length - 1)} ${height} L${x(0)} ${height} Z`} fill={`url(#${gid}-a)`} />
      )}
      {series.map((s) => (
        <path key={s.key} className="lp-draw" pathLength="1" d={path(s.key)} fill="none" stroke={s.color}
              strokeWidth={s.width || 2.25} strokeLinecap="round" strokeLinejoin="round" opacity={s.opacity ?? 1} />
      ))}
      <circle className="lp-fade" cx={x(data.length - 1)} cy={y(data[data.length - 1][first.key])} r="4" fill={first.color} stroke="var(--nv-surface)" strokeWidth="2" />
    </svg>
  )
}

// A labelled horizontal bar. `value` is shown as text; the bar length is |value| / max.
export function Bar({ label, value, display, max, color, delay = 0 }) {
  const w = Math.max(2, Math.min(100, (Math.abs(value) / max) * 100))
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="caption-2 text-ink-secondary">{label}</span>
        <span className="figure caption-1 text-ink">{display}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-raised" aria-hidden="true">
        <div className="lp-bar h-full rounded-full" style={{ width: `${w}%`, background: color, transitionDelay: `${delay}ms` }} />
      </div>
    </div>
  )
}

// A two or more part donut with a centred label.
export function Donut({ parts, size = 168, stroke = 18, children, label }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const total = parts.reduce((s, p) => s + p.value, 0) || 1
  const segments = parts.map((p, i) => ({
    ...p,
    len: (p.value / total) * c,
    start: parts.slice(0, i).reduce((s, q) => s + (q.value / total) * c, 0),
  }))
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="lp-spin" role="img" aria-label={label}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--nv-raised)" strokeWidth={stroke} />
        {segments.map((p) => (
          <circle key={p.label} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={p.color} strokeWidth={stroke}
                  strokeDasharray={`${Math.max(0, p.len - 3)} ${c}`} strokeDashoffset={-p.start} />
        ))}
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  )
}
