// Shared UI (task 12.1.2): buttons, inputs, cards, stat tiles, badges, tabs, skeletons and the
// loading, empty and error states. Every size, radius and colour comes from index.css tokens.
import { forwardRef, useId } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle,
  Info,
  Minus,
  Question,
  Warning,
  WarningCircle,
} from '@phosphor-icons/react'

const motion = 'transition-[background-color,border-color,color,opacity,transform] duration-300 ease-nv'

// ------------------------------------------------------------------ buttons
const VARIANTS = {
  primary: 'bg-ink text-ink-inverse hover:bg-white shadow-[inset_0_1px_0_rgba(255,255,255,0.4)]',
  secondary: 'bg-raised text-ink border border-line hover:bg-raised-2',
  ghost: 'text-ink-secondary hover:text-ink hover:bg-raised',
  danger: 'bg-raised text-critical border border-line hover:bg-raised-2',
}
const SIZES = {
  md: 'button-md px-3 py-2 gap-2', // B2: 8px vertical, 12px horizontal
  sm: 'button-sm px-3 py-2 gap-2',
  xs: 'button-xsm px-2 py-1 gap-1',
}

export function buttonClass(variant = 'primary', size = 'md', extra = '') {
  return `inline-flex items-center justify-center rounded-lg whitespace-nowrap ${motion} active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 ${VARIANTS[variant]} ${SIZES[size]} ${extra}`
}

export const Button = forwardRef(function Button(
  { variant = 'primary', size = 'md', to, href, className = '', children, type = 'button', ...props },
  ref,
) {
  const cls = buttonClass(variant, size, className)
  if (to) return <Link ref={ref} to={to} className={cls} {...props}>{children}</Link>
  if (href) return <a ref={ref} href={href} className={cls} {...props}>{children}</a>
  return <button ref={ref} type={type} className={cls} {...props}>{children}</button>
})

// ------------------------------------------------------------------ form fields
const fieldBase = `rounded-lg border border-line bg-raised px-3 py-2 body-6 text-ink placeholder:text-ink-muted outline-none ${motion} hover:border-line-strong focus:border-accent aria-[invalid=true]:border-critical`

export function Field({ label, hint, error, children, className = '' }) {
  const id = useId()
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block title-4 text-ink-secondary">{label}</label>
      {children({ id, 'aria-describedby': describedBy, 'aria-invalid': Boolean(error) })}
      {error ? (
        <p id={`${id}-error`} className="mt-1 caption-5 text-critical">{error}</p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1 caption-5 text-ink-muted">{hint}</p>
      ) : null}
    </div>
  )
}

export const Input = forwardRef(function Input({ className = 'w-full', ...props }, ref) {
  return <input ref={ref} className={`${fieldBase} ${className}`} {...props} />
})

export function Select({ className = 'w-full', children, ...props }) {
  return (
    <select className={`${fieldBase} appearance-none pr-8 ${className}`} {...props}>
      {children}
    </select>
  )
}

export function Checkbox({ label, ...props }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 body-6 text-ink-secondary">
      <input type="checkbox" className="h-4 w-4 rounded accent-[#3987e5]" {...props} />
      {label}
    </label>
  )
}

// ------------------------------------------------------------------ surfaces
export function Card({ title, subtitle, actions, children, className = '', bodyClass = '' }) {
  return (
    <section className={`rounded-2xl border border-line bg-surface p-4 sm:p-6 ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            {title && <h2 className="title-3 text-ink">{title}</h2>}
            {subtitle && <p className="mt-1 caption-2 text-ink-muted">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

export function PageHeader({ title, description, actions }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="heading-5 text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-2xl body-6 text-ink-secondary">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

// Signature detail: which agent produced a figure. The report's traceability check
// (every number matched to an agent output) made visible.
export function Traced({ agent }) {
  return (
    <span className="figure caption-5 text-ink-muted" title={`Computed by the ${agent} agent in Python`}>
      <span aria-hidden="true">↳ </span>
      {agent}
    </span>
  )
}

export function StatTile({ label, value, sub, traced, className = '' }) {
  return (
    <div className={`flex flex-col rounded-2xl border border-line bg-surface p-4 ${className}`}>
      <div className="caption-2 text-ink-secondary">{label}</div>
      <div className="mt-2 figure-1 text-ink">{value}</div>
      {sub && <div className="mt-1 caption-5 text-ink-muted">{sub}</div>}
      {traced && <div className="mt-auto pt-3"><Traced agent={traced} /></div>}
    </div>
  )
}

// Quiet metadata (replaces pills): mono, muted.
export function Meta({ children, className = '' }) {
  return <span className={`figure caption-5 text-ink-muted ${className}`}>{children}</span>
}

// ------------------------------------------------------------------ status labels
// Colour never alone: the icon carries the colour, the label stays in a text colour.
const TONE = {
  positive: ['text-good', ArrowUpRight],
  bullish: ['text-good', ArrowUpRight],
  solid: ['text-good', ArrowUpRight],
  good: ['text-good', CheckCircle],
  completed: ['text-good', CheckCircle],
  low: ['text-good', Minus],
  negative: ['text-critical', ArrowDownRight],
  bearish: ['text-critical', ArrowDownRight],
  weak: ['text-critical', ArrowDownRight],
  high: ['text-critical', Warning],
  failed: ['text-critical', WarningCircle],
  interrupted: ['text-critical', WarningCircle],
  poor: ['text-critical', Warning],
  mixed: ['text-warning', Warning],
  moderate: ['text-warning', Warning],
  partial: ['text-warning', Warning],
  limited: ['text-warning', Warning],
  neutral: ['text-ink-muted', Minus],
  sideways: ['text-ink-muted', Minus],
  uncertain: ['text-ink-muted', Question],
  insufficient_data: ['text-ink-muted', Question],
}

export function ToneBadge({ value, label }) {
  if (!value) return null
  const [cls, Icon] = TONE[value] || TONE.uncertain
  const text = label || value.replaceAll('_', ' ')
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-line bg-raised px-2 py-0.5 font-sans caption-4 text-ink-secondary">
      <Icon size={14} weight="bold" className={cls} aria-hidden="true" />
      {text.charAt(0).toUpperCase() + text.slice(1)}
    </span>
  )
}

// ------------------------------------------------------------------ tabs
export function Tabs({ tabs, value, onChange, label }) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-lg border border-line bg-surface p-1">
      {tabs.map((t) => {
        const active = t.value === value
        return (
          <button
            key={t.value}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(t.value)}
            className={`rounded-md px-3 py-1 body-5 ${motion} ${active ? 'bg-raised text-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]' : 'text-ink-secondary hover:text-ink'}`}
          >
            {t.label}
          </button>
        )
      })}
    </div>
  )
}

// ------------------------------------------------------------------ tables
export const table = {
  wrap: 'overflow-x-auto rounded-xl border border-line',
  table: 'w-full text-left body-6',
  thead: 'bg-raised/60 caption-4 text-ink-muted',
  th: 'px-3 py-2 font-medium',
  thR: 'px-3 py-2 font-medium text-right',
  tr: 'border-t border-line',
  td: 'px-3 py-2 text-ink-secondary',
  tdR: 'px-3 py-2 text-right figure text-ink',
}

// ------------------------------------------------------------------ states
export function Skeleton({ className = '' }) {
  return <div className={`skeleton rounded-lg ${className}`} aria-hidden="true" />
}

export function CardSkeleton({ rows = 3, className = '' }) {
  return (
    <div className={`rounded-2xl border border-line bg-surface p-6 ${className}`} role="status" aria-label="Loading">
      <Skeleton className="h-4 w-40" />
      <div className="mt-6 space-y-3">
        {Array.from({ length: rows }, (_, i) => (
          <Skeleton key={i} className={`h-4 ${i % 2 ? 'w-2/3' : 'w-full'}`} />
        ))}
      </div>
    </div>
  )
}

export function TileSkeletons({ count = 4 }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" role="status" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="rounded-2xl border border-line bg-surface p-4">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-3 h-8 w-32" />
          <Skeleton className="mt-3 h-3 w-40" />
        </div>
      ))}
    </div>
  )
}

export function PageSkeleton() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6" role="status" aria-label="Loading">
      <Skeleton className="h-8 w-64" />
      <TileSkeletons />
      <CardSkeleton rows={5} />
    </div>
  )
}

export function ErrorState({ message, action }) {
  return (
    <div role="alert" className="flex flex-wrap items-start gap-3 rounded-xl border border-line bg-surface p-4">
      <WarningCircle size={18} className="mt-0.5 shrink-0 text-critical" aria-hidden="true" />
      <p className="min-w-0 flex-1 body-6 text-ink">{message}</p>
      {action}
    </div>
  )
}

export function EmptyState({ icon: Icon = Info, title, children, action }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-xl border border-line bg-surface/60 p-6">
      <Icon size={20} className="text-ink-muted" aria-hidden="true" />
      {title && <h3 className="title-3 text-ink">{title}</h3>}
      {children && <div className="max-w-xl body-6 text-ink-secondary">{children}</div>}
      {action}
    </div>
  )
}

export function Disclaimer({ className = '' }) {
  return (
    <p className={`caption-5 text-ink-muted ${className}`}>
      NeuralVest is an educational project, not a SEBI registered adviser. Results describe the past, are
      illustrative and are not investment advice or real time data. Prices come from Yahoo Finance via yfinance
      and can be delayed. AI text comes from a small local model and can be wrong; every number is computed in
      Python.
    </p>
  )
}

// First letter upper case (readings come from the backend in sentence fragments).
export const sentence = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s)
