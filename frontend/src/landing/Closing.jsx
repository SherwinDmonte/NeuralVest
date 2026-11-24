// Lower half of the landing page: evidence, the tagline reveal, questions and the final call.
import { ArrowRight, CaretDown, GithubLogo } from '@phosphor-icons/react'
import { Button } from '../components/ui'
import { Mark } from '../components/Logo'
import { useWordReveal } from '../hooks/useReveal'
import { fmtDate, num } from '../utils/format'
import { CTA, FAQ, REPO, RUN_DATE, TEST_COUNT, snapshot } from './content'
import NeuralBackdrop from './NeuralBackdrop'
import { Section, SectionHeading } from './Section'

export function Evidence() {
  const rf = snapshot.risk_free_rate
  const items = [
    [String(TEST_COUNT), 'automated tests, including checks that every report number traces to an agent'],
    [`${snapshot.run.numbers_traced}/${snapshot.run.numbers_traced}`, `numbers in the ${RUN_DATE} report matched to the agent that computed them`],
    [`${num(rf.value_pct)}%`, `risk free rate: the RBI 91 day T bill yield of ${fmtDate(rf.as_of)}, with its source in every report`],
    ['₹0', 'to run it: Yahoo Finance data, public news feeds, a local model and a free database tier'],
  ]
  return (
    <Section label="Evidence">
      <SectionHeading eyebrow="Built in the open" title="No testimonials yet, so here is the evidence instead" />
      <dl className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
        {items.map(([n, text]) => (
          <div key={text} className="bg-surface p-6">
            <dt className="figure heading-5 text-ink">{n}</dt>
            <dd className="mt-2 caption-2 text-ink-secondary">{text}</dd>
          </div>
        ))}
      </dl>
    </Section>
  )
}

export function TaglineReveal() {
  const ref = useWordReveal()
  const lines = ['Every number has a source.', 'Every sentence is checked against it.']
  return (
    <section aria-label="What NeuralVest promises" className="mx-auto w-full max-w-6xl px-4 py-24 sm:px-6">
      <p ref={ref} className="max-w-[760px] heading-3 lg:heading-1">
        {lines.map((line, li) => (
          <span key={line} className="block">
            {line.split(' ').map((w, wi, all) => (
              <span key={`${li}-${wi}`} className="tagline-word">{w}{wi < all.length - 1 ? ' ' : ''}</span>
            ))}
          </span>
        ))}
      </p>
    </section>
  )
}

export function Faq() {
  return (
    <Section id="faq">
      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <SectionHeading eyebrow="Questions" title="What people ask before they start">
          Still unsure? The code, the tests and the setup guide are on GitHub.
        </SectionHeading>
        <div className="border-t border-line">
          {FAQ.map(([q, a]) => (
            <details key={q} className="group border-b border-line">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 title-3 text-ink transition-colors duration-300 ease-nv hover:text-accent-ink">
                <h3>{q}</h3>
                <CaretDown size={16} className="shrink-0 text-ink-muted transition-transform duration-500 ease-nv group-open:rotate-180" aria-hidden="true" />
              </summary>
              <p className="pb-4 body-6 text-ink-secondary">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </Section>
  )
}

export function FinalCta() {
  return (
    <Section label="Get started">
      <div className="relative isolate overflow-hidden rounded-3xl border border-line bg-surface px-6 py-16 text-center shadow-card sm:px-12">
        <div className="absolute inset-0 -z-10 opacity-80 [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]"><NeuralBackdrop variant="cta" /></div>
        <Mark size={64} animated className="mx-auto" />
        <h2 className="mx-auto mt-6 max-w-[680px] heading-4 text-ink lg:heading-3">Read your next stock with the working shown</h2>
        <p className="mx-auto mt-4 max-w-[520px] body-3 text-ink-secondary">Free and open source. No card, no trial period, nothing to cancel.</p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-4">
          <Button to="/register" size="lg">{CTA}<ArrowRight size={16} aria-hidden="true" /></Button>
          <a href={REPO} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 body-5 text-ink-secondary transition-colors duration-300 ease-nv hover:text-ink">
            <GithubLogo size={18} aria-hidden="true" /> Read the code on GitHub
          </a>
        </div>
      </div>
    </Section>
  )
}
