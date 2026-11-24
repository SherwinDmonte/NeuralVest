// Footer of the signed-in app (Phase 12B): brand, page links, legal links and one short notice.
import { Link } from 'react-router-dom'
import { ArrowUpRight, GithubLogo } from '@phosphor-icons/react'
import { Logo } from '../components/Logo'

const REPO = 'https://github.com/SherwinDmonte/NeuralVest'

const COLUMNS = [
  {
    title: 'Research',
    links: [
      { to: '/app/market', label: 'Market intelligence' },
      { to: '/app/analysis', label: 'Stock analysis' },
      { to: '/app/risk', label: 'Risk analysis' },
      { to: '/app/portfolio', label: 'Portfolio optimization' },
    ],
  },
  {
    title: 'Workspace',
    links: [
      { to: '/app/reports', label: 'Reports' },
      { to: '/app/watchlist', label: 'Watchlist' },
      { to: '/app/agents', label: 'AI agents' },
      { to: '/app/news', label: 'Financial news' },
    ],
  },
  {
    title: 'Support',
    links: [
      { to: '/app/help', label: 'Help' },
      { to: '/app/settings', label: 'Settings' },
      { href: REPO, label: 'Source code' },
    ],
  },
]

const linkCls = 'inline-flex items-center gap-1 body-6 text-ink-secondary transition-colors duration-300 ease-nv hover:text-ink'

function FooterLink({ to, href, label }) {
  if (href) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={linkCls}>
        {label}<ArrowUpRight size={12} aria-hidden="true" />
      </a>
    )
  }
  return <Link to={to} className={linkCls}>{label}</Link>
}

export default function AppFooter() {
  return (
    <footer className="mt-8 border-t border-line">
      <div className="mx-auto w-full max-w-[1600px] px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 md:grid-cols-[minmax(0,1.3fr)_repeat(3,minmax(0,1fr))]">
          <div className="col-span-2 max-w-xs sm:col-span-3 md:col-span-1">
            <Logo to="/app" />
            <p className="mt-3 body-6 text-ink-secondary">
              Multi-agent research for NSE and BSE stocks, running on your own computer.
            </p>
            <a href={REPO} target="_blank" rel="noreferrer" aria-label="NeuralVest on GitHub"
               className="mt-4 inline-grid h-9 w-9 place-items-center rounded-xl border border-line bg-surface text-ink-secondary transition-colors duration-300 ease-nv hover:border-line-strong hover:text-ink">
              <GithubLogo size={18} aria-hidden="true" />
            </a>
          </div>
          {COLUMNS.map((col) => (
            <nav key={col.title} aria-label={col.title}>
              <p className="caption-3 text-ink-muted">{col.title}</p>
              <ul className="mt-3 space-y-2">
                {col.links.map((l) => <li key={l.label}><FooterLink {...l} /></li>)}
              </ul>
            </nav>
          ))}
        </div>
        <div className="mt-10 flex flex-col gap-3 border-t border-line pt-6 caption-5 text-ink-muted sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} NeuralVest · Educational project, not investment advice</p>
          <div className="flex gap-4">
            <Link to="/privacy" className="transition-colors duration-300 ease-nv hover:text-ink">Privacy</Link>
            <Link to="/terms" className="transition-colors duration-300 ease-nv hover:text-ink">Terms</Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
