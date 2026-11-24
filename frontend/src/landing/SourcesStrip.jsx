// The proof line under the hero: where the numbers come from, named plainly.
import { useReveal } from '../hooks/useReveal'
import { SOURCES } from './content'

export default function SourcesStrip() {
  const ref = useReveal()
  return (
    <section ref={ref} aria-label="Data sources" className="reveal border-y border-line bg-surface/40">
      <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">
        <p className="caption-4 text-ink-muted">Where the numbers come from</p>
        <ul className="mt-3 grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-5">
          {SOURCES.map(([name, detail]) => (
            <li key={name} className="min-w-0 border-l border-line pl-3">
              <span className="block title-4 text-ink">{name}</span>
              <span className="block caption-5 text-ink-muted">{detail}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
