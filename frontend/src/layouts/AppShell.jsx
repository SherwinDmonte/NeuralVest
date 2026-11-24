// Signed-in app layout (task 12.1.4): a 248px sidebar on desktop; on small screens the links
// collapse into one menu button that opens a full height panel.
import { Suspense, useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  ChartLineUp,
  ChartPieSlice,
  FileText,
  House,
  List,
  Newspaper,
  ShieldWarning,
  SignOut,
  TreeStructure,
  X,
} from '@phosphor-icons/react'
import { useAuth } from '../auth/AuthContext'
import { useCurrentAnalysis } from '../analysis/AnalysisContext'
import { Disclaimer, PageSkeleton } from '../components/ui'
import { Logo } from '../components/Logo'

const NAV = [
  { to: '/app', label: 'Dashboard', Icon: House, end: true },
  { to: '/app/analysis', label: 'Stock analysis', Icon: ChartLineUp },
  { to: '/app/agents', label: 'Agent monitoring', Icon: TreeStructure },
  { to: '/app/news', label: 'Financial news', Icon: Newspaper },
  { to: '/app/portfolio', label: 'Portfolio', Icon: ChartPieSlice },
  { to: '/app/risk', label: 'Risk analysis', Icon: ShieldWarning },
  { to: '/app/reports', label: 'Reports', Icon: FileText },
]

function NavItems({ onNavigate, running }) {
  return (
    <ul className="space-y-0.5">
      {NAV.map(({ to, label, Icon, end }) => (
        <li key={to}>
          <NavLink
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex h-9 items-center gap-3 rounded-lg px-3 body-5 transition-colors duration-300 ease-nv ${
                isActive
                  ? 'bg-raised text-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                  : 'text-ink-secondary hover:bg-raised/60 hover:text-ink'
              }`
            }
          >
            <Icon size={18} aria-hidden="true" />
            <span className="flex-1">{label}</span>
            {to === '/app/agents' && running && (
              <span className="h-2 w-2 rounded-full bg-accent" title="An analysis is running" aria-label="An analysis is running" />
            )}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}

function UserBox({ user, onLogout }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-line p-3">
      <div className="min-w-0 flex-1">
        <div className="truncate body-5 text-ink">{user?.name}</div>
        <div className="truncate caption-5 text-ink-muted">{user?.email}</div>
      </div>
      <button
        type="button"
        onClick={onLogout}
        className="rounded-md p-2 text-ink-secondary transition-colors duration-300 ease-nv hover:bg-raised hover:text-ink active:scale-[0.98]"
        aria-label="Log out"
        title="Log out"
      >
        <SignOut size={18} aria-hidden="true" />
      </button>
    </div>
  )
}

export default function AppShell() {
  const { user, logout } = useAuth()
  const { busy, clear } = useCurrentAnalysis()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  const doLogout = () => {
    clear()
    logout()
  }

  return (
    <div className="min-h-screen lg:flex">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-ink focus:px-3 focus:py-2 focus:text-ink-inverse">
        Skip to content
      </a>

      {/* desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-62 shrink-0 flex-col border-r border-line px-4 py-6 lg:flex">
        <Logo to="/app" />
        <nav aria-label="Main" className="mt-8 flex-1">
          <NavItems running={busy} />
        </nav>
        <UserBox user={user} onLogout={doLogout} />
      </aside>

      {/* mobile top bar */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-page/90 px-4 backdrop-blur lg:hidden">
        <Logo to="/app" />
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? 'Close menu' : 'Open menu'}
          className="relative grid h-10 w-10 place-items-center rounded-lg text-ink transition-colors duration-300 ease-nv hover:bg-raised"
        >
          <List size={20} className={`absolute transition-[transform,opacity] duration-500 ease-nv ${open ? 'rotate-90 opacity-0' : 'opacity-100'}`} aria-hidden="true" />
          <X size={20} className={`absolute transition-[transform,opacity] duration-500 ease-nv ${open ? 'opacity-100' : '-rotate-90 opacity-0'}`} aria-hidden="true" />
        </button>
      </header>
      <div
        id="mobile-nav"
        className={`fixed inset-x-0 bottom-0 top-14 z-20 flex flex-col bg-page/95 px-4 py-6 backdrop-blur-xl transition-opacity duration-500 ease-nv lg:hidden ${open ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
        aria-hidden={!open}
        inert={!open}
      >
        <nav aria-label="Main" className="flex-1">
          <NavItems onNavigate={() => setOpen(false)} running={busy} />
        </nav>
        <UserBox user={user} onLogout={doLogout} />
      </div>

      <div className="min-w-0 flex-1">
        <main id="main" className="mx-auto w-full max-w-screen-2xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Suspense fallback={<PageSkeleton />}>
            <Outlet />
          </Suspense>
        </main>
        <footer className="mx-auto w-full max-w-screen-2xl px-4 pb-8 sm:px-6 lg:px-8">
          <Disclaimer className="max-w-3xl" />
        </footer>
      </div>
    </div>
  )
}
