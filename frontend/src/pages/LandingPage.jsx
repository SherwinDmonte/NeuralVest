// Landing page (task 12.3.1, redesigned in Phase 12B). One offer, one audience (Indian retail
// investors and finance students), one primary action: "Create a free account".
// Sections live in src/landing/. Every figure on the page is either live from the public
// /api/market/indices endpoint or copied from a real stored run (src/landing/snapshot.json).
import { Link } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { usePageTitle } from '../hooks/usePageTitle'
import { REPO } from '../landing/content'
import Nav from '../landing/Nav'
import Hero from '../landing/Hero'
import SourcesStrip from '../landing/SourcesStrip'
import TraceDemo from '../landing/TraceDemo'
import AgentStory from '../landing/AgentStory'
import ReportExplorer from '../landing/ReportExplorer'
import { Evidence, Faq, FinalCta, TaglineReveal } from '../landing/Closing'

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-12 sm:px-6 md:flex-row md:justify-between">
        <div className="max-w-md space-y-3">
          <Logo />
          <p className="caption-5 text-ink-muted">
            Educational project, not a SEBI registered adviser and not investment advice. Prices from Yahoo Finance via
            yfinance, end of day and possibly delayed.
          </p>
        </div>
        <nav aria-label="Footer">
          <ul className="flex flex-wrap gap-x-6 gap-y-2 caption-2 text-ink-secondary">
            <li><Link to="/privacy" className="transition-colors duration-300 ease-nv hover:text-ink">Privacy</Link></li>
            <li><Link to="/terms" className="transition-colors duration-300 ease-nv hover:text-ink">Terms</Link></li>
            <li><a href={REPO} target="_blank" rel="noopener noreferrer" className="transition-colors duration-300 ease-nv hover:text-ink">GitHub</a></li>
            <li><Link to="/login" className="transition-colors duration-300 ease-nv hover:text-ink">Log in</Link></li>
          </ul>
        </nav>
      </div>
    </footer>
  )
}

export default function LandingPage() {
  usePageTitle(null)
  return (
    <div className="min-h-screen overflow-x-clip bg-page">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-20 focus:z-50 focus:rounded-lg focus:bg-ink focus:px-3 focus:py-2 focus:text-ink-inverse">
        Skip to content
      </a>
      <Nav />
      <main id="main">
        <Hero />
        <SourcesStrip />
        <TraceDemo />
        <AgentStory />
        <TaglineReveal />
        <ReportExplorer />
        <Evidence />
        <Faq />
        <FinalCta />
      </main>
      <SiteFooter />
    </div>
  )
}
