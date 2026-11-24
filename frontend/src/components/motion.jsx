// Components that use the `motion` library (Phase 12B). Imported only by the signed-in app,
// so the public landing page never downloads it. Every animation respects reduced motion.
import { useEffect, useId, useRef, useState } from 'react'
import { AnimatePresence, animate, motion, useInView, useReducedMotion } from 'motion/react'
import { X } from '@phosphor-icons/react'

export const EASE = [0.22, 1, 0.36, 1]

// ------------------------------------------------------------------ page transition
export function PageTransition({ children, routeKey }) {
  const reduce = useReducedMotion()
  return (
    <motion.div
      key={routeKey}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE }}
    >
      {children}
    </motion.div>
  )
}

// Fade and rise once when scrolled into view; children can stagger with `delay`.
export function Reveal({ children, delay = 0, className = '' }) {
  const reduce = useReducedMotion()
  return (
    <motion.div
      className={className}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -10% 0px' }}
      transition={{ duration: 0.6, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  )
}

// ------------------------------------------------------------------ animated number
// Counts up to `value` the first time it is visible. `format` turns the number into text.
export function AnimatedNumber({ value, format = (v) => String(v), duration = 1.1 }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true })
  const reduce = useReducedMotion()
  // Starts on the real value, so a figure is never shown as 0 if the animation does not run.
  const [shown, setShown] = useState(value)
  useEffect(() => {
    if (value == null || typeof value !== 'number') return undefined
    if (reduce || !inView) {
      setShown(value)
      return undefined
    }
    const controls = animate(0, value, { duration, ease: EASE, onUpdate: (v) => setShown(v), onComplete: () => setShown(value) })
    return () => { controls.stop(); setShown(value) }
  }, [value, inView, reduce, duration])
  return <span ref={ref} className="tabular">{value == null ? 'n/a' : format(shown)}</span>
}

// ------------------------------------------------------------------ tabs with a sliding indicator
export function AnimatedTabs({ tabs, value, onChange, label, size = 'md' }) {
  const id = useId()
  return (
    <div role="tablist" aria-label={label}
         className="relative inline-flex max-w-full gap-1 overflow-x-auto rounded-xl border border-line bg-surface p-1 shadow-card">
      {tabs.map((t) => {
        const active = t.value === value
        return (
          <button key={t.value} role="tab" type="button" aria-selected={active} onClick={() => onChange(t.value)}
                  className={`relative shrink-0 rounded-lg ${size === 'sm' ? 'px-2 py-1 caption-1' : 'px-3 py-1 body-5'} transition-colors duration-300 ease-nv ${active ? 'text-ink' : 'text-ink-secondary hover:text-ink'}`}>
            {active && (
              <motion.span layoutId={`tab-${id}`} className="absolute inset-0 rounded-lg border border-line-strong bg-raised shadow-card"
                           transition={{ type: 'spring', bounce: 0.15, duration: 0.45 }} />
            )}
            <span className="relative inline-flex items-center gap-2">
              {t.icon && <t.icon size={16} aria-hidden="true" />}
              {t.label}
            </span>
          </button>
        )
      })}
    </div>
  )
}

// ------------------------------------------------------------------ modal
export function Modal({ open, onClose, title, children, wide = false }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const prev = document.activeElement
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    setTimeout(() => ref.current?.focus(), 30)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      prev?.focus?.()
    }
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[10vh]"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          <button type="button" aria-label="Close" className="absolute inset-0 cursor-default bg-page/70 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            ref={ref}
            role="dialog"
            aria-modal="true"
            aria-label={title || "Search"}
            tabIndex={-1}
            className={`relative w-full ${wide ? 'max-w-3xl' : 'max-w-xl'} overflow-hidden rounded-2xl border border-line-strong glass-strong shadow-float outline-none`}
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.3, ease: EASE }}
          >
            <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-brand" aria-hidden="true" />
            {title && (
              <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
                <h2 className="title-3 text-ink">{title}</h2>
                <button type="button" onClick={onClose} aria-label="Close"
                        className="rounded-lg p-1 text-ink-secondary transition-colors duration-300 ease-nv hover:bg-raised hover:text-ink">
                  <X size={18} aria-hidden="true" />
                </button>
              </header>
            )}
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// ------------------------------------------------------------------ dropdown menu
export function Dropdown({ trigger, children, align = 'right', width = 'w-64', label }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => { if (!ref.current?.contains(e.target)) setOpen(false) }
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])
  return (
    <div ref={ref} className="relative">
      {trigger({ open, toggle: () => setOpen((o) => !o), 'aria-expanded': open, 'aria-haspopup': 'menu', 'aria-label': label })}
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            className={`absolute ${align === 'right' ? 'right-0' : 'left-0'} top-full z-40 mt-2 ${width} overflow-hidden rounded-2xl border border-line-strong glass-strong p-1 shadow-float`}
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.2, ease: EASE }}
          >
            {children({ close: () => setOpen(false) })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function MenuItem({ icon: Icon, children, onClick, active = false, hint }) {
  return (
    <button type="button" role="menuitem" onClick={onClick}
            className={`flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left body-6 transition-colors duration-300 ease-nv ${active ? 'bg-raised text-ink' : 'text-ink-secondary hover:bg-raised hover:text-ink'}`}>
      {Icon && <Icon size={16} aria-hidden="true" />}
      <span className="flex-1">{children}</span>
      {hint && <span className="caption-5 text-ink-muted">{hint}</span>}
    </button>
  )
}
