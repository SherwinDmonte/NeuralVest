// Small shared UI pieces: cards, badges, loading/empty/error states, disclaimer.
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  HelpCircle,
  Info,
  Loader2,
  Minus,
} from 'lucide-react'

export function Card({ title, subtitle, actions, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-4 sm:p-5 ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}

// Sentiment / trend labels: colour is never alone - always icon + text.
const TONE = {
  positive: { cls: 'text-good border-good/40', Icon: ArrowUpRight },
  bullish: { cls: 'text-good border-good/40', Icon: ArrowUpRight },
  negative: { cls: 'text-critical border-critical/40', Icon: ArrowDownRight },
  bearish: { cls: 'text-critical border-critical/40', Icon: ArrowDownRight },
  mixed: { cls: 'text-warning border-warning/40', Icon: AlertTriangle },
  neutral: { cls: 'text-ink-secondary border-line', Icon: Minus },
  sideways: { cls: 'text-ink-secondary border-line', Icon: Minus },
  uncertain: { cls: 'text-ink-muted border-line', Icon: HelpCircle },
  insufficient_data: { cls: 'text-ink-muted border-line', Icon: HelpCircle },
}

export function ToneBadge({ value }) {
  if (!value) return null
  const { cls, Icon } = TONE[value] || TONE.uncertain
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {value.replace('_', ' ')}
    </span>
  )
}

export function Chip({ children }) {
  return (
    <span className="inline-flex items-center rounded-md border border-line px-1.5 py-0.5 text-[11px] text-ink-muted">
      {children}
    </span>
  )
}

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="flex items-center gap-2 py-6 text-sm text-ink-secondary" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      {label}
    </div>
  )
}

export function ErrorState({ message, action }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-critical/40 bg-critical/10 p-3 text-sm">
      <AlertTriangle className="h-4 w-4 shrink-0 text-critical" aria-hidden="true" />
      <span className="text-ink">{message}</span>
      {action}
    </div>
  )
}

export function EmptyState({ children }) {
  return (
    <div className="flex items-start gap-2 py-4 text-sm text-ink-muted">
      <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div>{children}</div>
    </div>
  )
}

export function Disclaimer() {
  return (
    <p className="text-xs leading-relaxed text-ink-muted">
      NeuralVest is an educational project. Results are illustrative, are not investment advice and are not
      real-time market data. Prices come from Yahoo Finance via yfinance (may be delayed). AI-generated text comes
      from a small local model and can be wrong; all numbers are computed by NeuralVest in Python.
    </p>
  )
}
