// Section shell for the landing page: reveals once on scroll (IntersectionObserver) and gives
// charts inside it the .is-visible class they animate from.
import { useReveal } from '../hooks/useReveal'

export function Section({ id, children, className = '', width = 'max-w-6xl', label }) {
  const ref = useReveal()
  return (
    <section id={id} ref={ref} aria-label={label} className={`reveal lp-scope mx-auto w-full ${width} scroll-mt-24 px-4 py-16 sm:px-6 lg:py-24 ${className}`}>
      {children}
    </section>
  )
}

export function Eyebrow({ children }) {
  return (
    <p className="mb-4 flex items-center gap-3 caption-3 uppercase tracking-[0.14em] text-accent-ink">
      <span className="h-px w-6 bg-accent" aria-hidden="true" />{children}
    </p>
  )
}

export function SectionHeading({ eyebrow, title, children }) {
  return (
    <div className="max-w-[680px]">
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h2 className="heading-4 text-ink lg:heading-3">{title}</h2>
      {children && <p className="mt-4 body-3 text-ink-secondary">{children}</p>}
    </div>
  )
}
