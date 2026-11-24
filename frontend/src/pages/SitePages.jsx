// Branded 404, privacy and terms (ship requirements). The privacy text describes what this
// project actually does with data; it is not legal advice.
import { Link } from 'react-router-dom'
import { ArrowLeft } from '@phosphor-icons/react'
import { Button } from '../components/ui'
import { Logo } from '../components/Logo'
import { SiteFooter } from './LandingPage'
import { usePageTitle } from '../hooks/usePageTitle'

function Frame({ children }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6"><Logo /></header>
      <main id="main" className="mx-auto w-full max-w-3xl flex-1 px-4 pb-16 sm:px-6">{children}</main>
      <SiteFooter />
    </div>
  )
}

export function NotFoundPage() {
  usePageTitle('Page not found')
  return (
    <Frame>
      <div className="py-24">
        <p className="figure caption-3 text-accent-ink">404</p>
        <h1 className="mt-2 heading-4 text-ink">This page is not in the ledger</h1>
        <p className="mt-4 max-w-xl body-3 text-ink-secondary">The address may be mistyped, or the page moved. Your reports are safe in your account.</p>
        <div className="mt-8 flex flex-wrap gap-4">
          <Button to="/app">Go to the dashboard</Button>
          <Button to="/" variant="ghost"><ArrowLeft size={16} aria-hidden="true" /> Back to the home page</Button>
        </div>
      </div>
    </Frame>
  )
}

function Legal({ title, updated, children }) {
  usePageTitle(title)
  return (
    <Frame>
      <Link to="/" className="inline-flex items-center gap-2 caption-2 text-ink-secondary transition-colors duration-300 ease-nv hover:text-ink">
        <ArrowLeft size={16} aria-hidden="true" /> Home
      </Link>
      <h1 className="mt-6 heading-4 text-ink">{title}</h1>
      <p className="mt-2 caption-5 text-ink-muted">Last updated {updated}</p>
      <div className="mt-8 space-y-6 body-3 text-ink-secondary [&_h2]:title-2 [&_h2]:text-ink">{children}</div>
    </Frame>
  )
}

export function PrivacyPage() {
  return (
    <Legal title="Privacy" updated="24 Nov 2026">
      <p>NeuralVest is an educational project that you run yourself. This page explains what the app stores and where.</p>
      <h2>What is stored</h2>
      <p>Your name, email and an Argon2 hash of your password (never the password itself), your watchlist, and the analyses and reports you run. They are stored in the MongoDB Atlas database configured in your own backend settings.</p>
      <h2>What leaves your computer</h2>
      <p>The AI model runs locally through Ollama. To analyse a stock the backend downloads public data: prices and statements from Yahoo Finance and headlines from public news feeds (and GDELT when you enable it). Those requests contain stock symbols and company names, never your account details.</p>
      <h2>Cookies and tracking</h2>
      <p>None. The login token is kept in your browser&apos;s session storage and is cleared when you close the tab. There is no analytics or advertising code.</p>
      <h2>Deleting your data</h2>
      <p>Because the database is yours, you can delete your account and reports from MongoDB Atlas at any time.</p>
    </Legal>
  )
}

export function TermsPage() {
  return (
    <Legal title="Terms" updated="24 Nov 2026">
      <p>NeuralVest is provided for learning and research. By using it you accept these terms.</p>
      <h2>Not investment advice</h2>
      <p>NeuralVest is not a SEBI registered investment adviser or research analyst. Reports describe past data and illustrative calculations. They are not recommendations to buy, sell or hold any security, and past performance does not guarantee future results.</p>
      <h2>Data sources</h2>
      <p>Prices and statements come from Yahoo Finance through the unofficial yfinance library and are intended for personal, educational use. Data can be delayed, incomplete or wrong. NeuralVest does not scrape the NSE website.</p>
      <h2>AI text</h2>
      <p>Explanations are written by a small local language model. Their numbers are checked against the calculations, but the wording can still be wrong. The rule based readings are the reference.</p>
      <h2>No warranty</h2>
      <p>The software is provided as is, without warranty of any kind. You are responsible for decisions you make.</p>
    </Legal>
  )
}
