// NeuralVest brand (Phase 12B): an "N" drawn as a path through connected nodes (a small neural
// network) whose last stroke rises like a market line. Gradient teal -> blue -> violet.
// Variants: tile (on a dark tile), plain (transparent), mono (single colour, currentColor).
// `animated`: the nodes pulse in turn and the connections carry a slow flow.
import { useId } from 'react'
import { Link } from 'react-router-dom'

const NODES = [
  [8, 25], [8, 15.5], [8, 7], [16, 16], [24, 25], [24, 13], [27, 6],
]
const PATH = 'M8 25 V7 L24 25 V13 L27 6'

export function Mark({ size = 28, animated = false, variant = 'tile', className = '' }) {
  const id = useId().replace(/:/g, '')
  const stroke = variant === 'mono' ? 'currentColor' : `url(#${id}-g)`
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-g`} x1="4" y1="28" x2="28" y2="4" gradientUnits="userSpaceOnUse">
          <stop stopColor="#16C7B7" />
          <stop offset="0.55" stopColor="#438BFF" />
          <stop offset="1" stopColor="#9B6BFF" />
        </linearGradient>
        <radialGradient id={`${id}-t`} cx="0" cy="0" r="1" gradientTransform="translate(8 4) rotate(50) scale(34)" gradientUnits="userSpaceOnUse">
          <stop stopColor="#17243A" />
          <stop offset="1" stopColor="#0B1220" />
        </radialGradient>
      </defs>
      {variant === 'tile' && (
        <>
          <rect width="32" height="32" rx="9" fill={`url(#${id}-t)`} />
          <rect x="0.5" y="0.5" width="31" height="31" rx="8.5" stroke={`url(#${id}-g)`} strokeOpacity="0.45" />
        </>
      )}
      <path d={PATH} stroke={stroke} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      {animated && (
        <path d={PATH} stroke="#F3F6FC" strokeOpacity="0.55" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" className="nv-flow" />
      )}
      {NODES.map(([x, y], i) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r={i === NODES.length - 1 ? 2.4 : 1.7}
                fill={variant === 'mono' ? 'currentColor' : i === NODES.length - 1 ? '#9B6BFF' : '#F3F6FC'}
                className={animated ? 'nv-pulse' : undefined}
                style={animated ? { animationDelay: `${i * 0.25}s` } : undefined} />
      ))}
    </svg>
  )
}

export function Logo({ to = '/', animated = true, compact = false }) {
  return (
    <Link to={to} className="group inline-flex items-center gap-2 rounded-lg text-ink" aria-label="NeuralVest home">
      <Mark animated={animated} />
      {!compact && (
        <span className="title-2 tracking-tight">
          Neural<span className="text-brand">Vest</span>
        </span>
      )}
    </Link>
  )
}
