// Shared UI (Phase 12 kit, restyled in Phase 12B for the dark and light themes): buttons,
// fields, cards, stat tiles, badges, tables, skeletons and the loading, empty and error states.
// No animation library here (this file is also used by the public landing page); components
// that use `motion` live in components/motion.jsx.
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

const motionCls = 'transition-[background-color,border-color,color,opacity,transform,box-shadow,filter] duration-300 ease-nv'

// ------------------------------------------------------------------ buttons
const VARIANTS = {
  primary: 'bg-brand-button text-white shadow-[0_8px_24px_-10px_rgba(67,139,255,0.65)] hover:brightness-110 hover:shadow-[0_10px_30px_-8px_rgba(67,139,255,0.8)]',
  secondary: 'bg-raised text-ink border border-line hover:bg-raised-2 hover:border-line-strong',
  ghost: 'text-ink-secondary hover:text-ink hover:bg-raised',
  danger: 'bg-raised text-critical border border-line hover:bg-raised-2',
  glass: 'glass text-ink border border-line hover:border-line-strong',
}
const SIZES = {
  lg: 'button-md px-4 py-3 gap-2',
  md: 'button-md px-3 py-2 gap-2',
  sm: 'button-sm px-3 py-2 gap-2',
  xs: 'button-xsm px-2 py-1 gap-1',
}

export function buttonClass(variant = 'primary', size = 'md', extra = '') {
  return `inline-flex items-center justify-center rounded-xl whitespace-nowrap ${motionCls} active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 ${VARIANTS[variant]} ${SIZES[size]} ${extra}`
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

export function IconButton({ label, children, className = '', ...props }) {
  return (
    <button type="button" aria-label={label} title={label}
            className={`grid h-9 w-9 place-items-center rounded-xl text-ink-secondary ${motionCls} hover:bg-raised hover:text-ink active:scale-95 ${className}`}
            {...props}>
      {children}
    </button>
  )
}

// ------------------------------------------------------------------ form fields
const fieldBase = `rounded-xl border border-line bg-raised px-3 py-2 body-6 text-ink placeholder:text-ink-muted outline-none ${motionCls} hover:border-line-strong focus:border-accent focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--nv-accent)_22%,transparent)] aria-[invalid=true]:border-critical`

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
    <select className={`${fieldBase} cursor-pointer pr-8 ${className}`} {...props}>
      {children}
    </select>
  )
}

export function Checkbox({ label, ...props }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 body-6 text-ink-secondary">
      <input type="checkbox" className="h-4 w-4 rounded accent-[var(--nv-accent)]" {...props} />
      {label}
    </label>
  )
}

// ------------------------------------------------------------------ surfaces
export function Card({ title, subtitle, actions, children, className = '', bodyClass = '', icon: Icon, accent = false }) {
  return (
    <section className={`relative rounded-2xl border border-line bg-surface p-4 shadow-card sm:p-6 ${className}`}>
      {accent && <span className="pointer-events-none absolute inset-x-6 top-0 h-px bg-brand opacity-70" aria-hidden="true" />}
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            {Icon && (
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-line bg-raised text-accent-ink">
                <Icon size={18} aria-hidden="true" />
              </span>
            )}
            <div className="min-w-0">
              {title && <h2 className="title-3 text-ink">{title}</h2>}
              {subtitle && <p className="mt-1 caption-2 text-ink-muted">{subtitle}</p>}
            </div>
          </div>
          {actions}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

export function PageHeader({ title, description, actions, eyebrow }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <p className="mb-2 caption-3 text-brand">{eyebrow}</p>}
        <h1 className="heading-5 text-ink sm:heading-4">{title}</h1>
        {description && <p className="mt-2 max-w-2xl body-6 text-ink-secondary">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

// Which agent produced a figure: the report's traceability check made visible.
export function Traced({ agent }) {
  return (
    <span className="figure caption-5 text-ink-muted" title={`Computed by the ${agent} agent in Python`}>
      <span aria-hidden="true" className="text-accent-ink">↳ </span>
      {agent}
    </span>
  )
}

export function StatTile({ label, value, sub, traced, className = '', icon: Icon, children }) {
  return (
    <div className={`group relative flex flex-col overflow-hidden rounded-2xl border border-line bg-surface p-4 shadow-card ${motionCls} hover:-translate-y-0.5 hover:border-line-strong ${className}`}>
      <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-brand opacity-0 transition-opacity duration-300 ease-nv group-hover:opacity-80" aria-hidden="true" />
      <div className="flex items-center justify-between gap-2">
        <span className="caption-2 text-ink-secondary">{label}</span>
        {Icon && <Icon size={16} className="text-ink-muted" aria-hidden="true" />}
      </div>
      <div className="mt-2 figure-1 text-ink">{value}</div>
      {sub && <div className="mt-1 caption-5 text-ink-muted">{sub}</div>}
      {children}
      {traced && <div className="mt-auto pt-3"><Traced agent={traced} /></div>}
    </div>
  )
}

// Quiet metadata: mono, muted.
export function Meta({ children, className = '' }) {
  return <span className={`figure caption-5 text-ink-muted ${className}`}>{children}</span>
}

// A number change with its sign as icon + text (colour never alone).
export function Change({ value, suffix = '%', digits = 2, className = '' }) {
  if (value == null) return <span className={`caption-4 text-ink-muted ${className}`}>n/a</span>
  const up = value > 0
  const down = value < 0
  const Icon = up ? ArrowUpRight : down ? ArrowDownRight : Minus
  const tone = up ? 'text-good bg-good/10 border-good/25' : down ? 'text-critical bg-critical/10 border-critical/25' : 'text-ink-secondary bg-raised border-line'
  return (
    <span className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 figure caption-3 ${tone} ${className}`}>
      <Icon size={12} weight="bold" aria-hidden="true" />
      {up ? '+' : ''}{Number(value).toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}{suffix}
      <span className="sr-only">{up ? 'up' : down ? 'down' : 'unchanged'}</span>
    </span>
  )
}

// ------------------------------------------------------------------ status labels
const TONE = {
  positive: ['good', ArrowUpRight],
  bullish: ['good', ArrowUpRight],
  solid: ['good', ArrowUpRight],
  good: ['good', CheckCircle],
  completed: ['good', CheckCircle],
  low: ['good', Minus],
  negative: ['critical', ArrowDownRight],
  bearish: ['critical', ArrowDownRight],
  weak: ['critical', ArrowDownRight],
  high: ['critical', Warning],
  failed: ['critical', WarningCircle],
  interrupted: ['critical', WarningCircle],
  poor: ['critical', Warning],
  mixed: ['warning', Warning],
  moderate: ['warning', Warning],
  partial: ['warning', Warning],
  limited: ['warning', Warning],
  running: ['neutral', Info],
  queued: ['neutral', Info],
  neutral: ['muted', Minus],
  sideways: ['muted', Minus],
  uncertain: ['muted', Question],
  insufficient_data: ['muted', Question],
}
const TONE_CLS = {
  good: 'border-good/25 bg-good/10 [&>svg]:text-good',
  critical: 'border-critical/25 bg-critical/10 [&>svg]:text-critical',
  warning: 'border-warning/25 bg-warning/10 [&>svg]:text-warning',
  neutral: 'border-neutral/25 bg-neutral/10 [&>svg]:text-neutral',
  muted: 'border-line bg-raised [&>svg]:text-ink-muted',
}

export function ToneBadge({ value, label }) {
  if (!value) return null
  const [tone, Icon] = TONE[value] || TONE.uncertain
  const text = label || value.replaceAll('_', ' ')
  return (
    <span className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 font-sans caption-4 text-ink ${TONE_CLS[tone]}`}>
      <Icon size={13} weight="bold" aria-hidden="true" />
      {text.charAt(0).toUpperCase() + text.slice(1)}
    </span>
  )
}

// Tabs (CSS only; an animated version lives in components/motion.jsx).
export function Tabs({ tabs, value, onChange, label }) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex max-w-full flex-wrap gap-1 rounded-xl border border-line bg-surface p-1 shadow-card">
      {tabs.map((t) => {
        const active = t.value === value
        return (
          <button key={t.value} role="tab" type="button" aria-selected={active} onClick={() => onChange(t.value)}
                  className={`rounded-lg px-3 py-1 body-5 ${motionCls} ${active ? 'bg-raised text-ink shadow-card' : 'text-ink-secondary hover:text-ink'}`}>
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
  thead: 'bg-raised caption-4 text-ink-muted',
  th: 'px-3 py-2 font-medium',
  thR: 'px-3 py-2 font-medium text-right',
  tr: 'border-t border-line transition-colors duration-300 ease-nv hover:bg-raised/60',
  td: 'px-3 py-2 text-ink-secondary',
  tdR: 'px-3 py-2 text-right figure text-ink',
}

// ------------------------------------------------------------------ states
export function Skeleton({ className = '' }) {
  return <div className={`skeleton rounded-lg ${className}`} aria-hidden="true" />
}

export function CardSkeleton({ rows = 3, className = '' }) {
  return (
    <div className={`rounded-2xl border border-line bg-surface p-6 shadow-card ${className}`} role="status" aria-label="Loading">
      <Skeleton className="h-4 w-40" />
      <div className="mt-6 space-y-3">
        {Array.from({ length: rows }, (_, i) => <Skeleton key={i} className={`h-4 ${i % 2 ? 'w-2/3' : 'w-full'}`} />)}
      </div>
    </div>
  )
}

export function TileSkeletons({ count = 4 }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" role="status" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="rounded-2xl border border-line bg-surface p-4 shadow-card">
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
    <div role="alert" className="flex flex-wrap items-start gap-3 rounded-2xl border border-critical/30 bg-critical/5 p-4">
      <WarningCircle size={18} className="mt-0.5 shrink-0 text-critical" aria-hidden="true" />
      <p className="min-w-0 flex-1 body-6 text-ink">{message}</p>
      {action}
    </div>
  )
}

export function EmptyState({ icon: Icon = Info, title, children, action }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-2xl border border-dashed border-line-strong bg-surface/50 p-6">
      <span className="grid h-10 w-10 place-items-center rounded-xl border border-line bg-raised text-accent-ink">
        <Icon size={20} aria-hidden="true" />
      </span>
      {title && <h3 className="title-3 text-ink">{title}</h3>}
      {children && <div className="max-w-xl body-6 text-ink-secondary">{children}</div>}
      {action}
    </div>
  )
}

// First letter upper case (readings come from the backend in sentence fragments).
export const sentence = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s)
