// Signed-in app shell (Phase 12B): collapsible sidebar (remembered), mobile drawer, top bar with
// command palette, notifications, theme and profile menus, page transitions, footer.
import { Suspense, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import {
  Bell,
  CaretDoubleLeft,
  CaretDoubleRight,
  Desktop,
  List,
  MagnifyingGlass,
  Moon,
  SignOut,
  Sun,
  User,
  X,
} from '@phosphor-icons/react'
import { useAuth } from '../auth/AuthContext'
import { useCurrentAnalysis } from '../analysis/AnalysisContext'
import { useNotifications } from '../feedback/Notifications'
import { useTheme } from '../theme/ThemeContext'
import { IconButton, PageSkeleton } from '../components/ui'
import { Dropdown, MenuItem, PageTransition } from '../components/motion'
import { Logo, Mark } from '../components/Logo'
import CommandPalette from './CommandPalette'
import AppFooter from './AppFooter'
import { NAV, SECONDARY, titleFor } from './nav'
import { fmtDateTime } from '../utils/format'

const SIDEBAR_KEY = 'nv.sidebar'
const readCollapsed = () => {
  try { return localStorage.getItem(SIDEBAR_KEY) === 'collapsed' } catch { return false }
}

function NavItem({ item, collapsed, running, onNavigate }) {
  const { to, label, Icon, end } = item
  return (
    <li className="group/nav relative">
      <NavLink to={to} end={end} onClick={onNavigate} aria-label={collapsed ? label : undefined}
               className={({ isActive }) => `relative flex h-10 items-center gap-3 rounded-xl px-3 body-5 transition-colors duration-300 ease-nv ${
                 isActive ? 'text-ink' : 'text-ink-secondary hover:bg-raised/70 hover:text-ink'} ${collapsed ? 'justify-center px-0' : ''}`}>
        {({ isActive }) => (
          <>
            {isActive && (
              <motion.span layoutId="nav-active" className="absolute inset-0 rounded-xl border border-line-strong bg-raised shadow-card"
                           transition={{ type: 'spring', bounce: 0.15, duration: 0.45 }} />
            )}
            {isActive && <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-brand" aria-hidden="true" />}
            <Icon size={19} weight={isActive ? 'fill' : 'regular'} className={`relative shrink-0 ${isActive ? 'text-accent-ink' : ''}`} aria-hidden="true" />
            {!collapsed && <span className="relative flex-1 truncate">{label}</span>}
            {running && <span className={`h-2 w-2 rounded-full bg-accent shadow-[0_0_8px_var(--nv-accent)] ${collapsed ? 'absolute right-2 top-2' : 'relative'}`} aria-label="An analysis is running" />}
          </>
        )}
      </NavLink>
      {collapsed && (
        <span role="tooltip" className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap rounded-lg border border-line-strong glass-strong px-2 py-1 caption-4 text-ink opacity-0 shadow-float transition-opacity duration-200 ease-nv group-hover/nav:opacity-100 group-focus-within/nav:opacity-100">
          {label}
        </span>
      )}
    </li>
  )
}

function SidebarBody({ collapsed, onNavigate, running }) {
  return (
    <>
      <nav aria-label="Main" className={`mt-6 flex-1 ${collapsed ? "" : "overflow-y-auto"}`}>
        {!collapsed && <p className="mb-2 px-3 caption-3 text-ink-muted">Workspace</p>}
        <ul className="space-y-1">
          {NAV.map((item) => <NavItem key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} running={item.to === '/app/agents' && running} />)}
        </ul>
      </nav>
      <div className="space-y-2 pt-4">
        <ul className="space-y-1">
          {SECONDARY.map((item) => <NavItem key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} />)}
        </ul>
      </div>
    </>
  )
}

function Notifications() {
  const { items, unread, markRead, clear } = useNotifications()
  return (
    <Dropdown label="Notifications" width="w-80" trigger={({ toggle, ...aria }) => (
      <IconButton label="Notifications" onClick={() => { toggle(); markRead() }} {...aria} className="relative">
        <Bell size={19} aria-hidden="true" />
        {unread > 0 && <span className="absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-brand-button px-1 caption-5 text-white">{unread}</span>}
      </IconButton>
    )}>
      {() => (
        <div>
          <div className="flex items-center justify-between px-3 py-2">
            <span className="title-4 text-ink">Notifications</span>
            {items.length > 0 && <button type="button" onClick={clear} className="caption-4 text-accent-ink hover:underline">Clear</button>}
          </div>
          {items.length === 0 ? (
            <p className="px-3 pb-3 caption-2 text-ink-muted">Your own activity appears here: finished analyses, downloads and watchlist changes.</p>
          ) : (
            <ul className="max-h-80 overflow-y-auto">
              {items.map((n) => (
                <li key={n.id} className="rounded-xl px-3 py-2 hover:bg-raised">
                  <p className="body-5 text-ink">{n.title}</p>
                  {n.body && <p className="caption-5 text-ink-secondary">{n.body}</p>}
                  <p className="figure caption-5 text-ink-muted">{fmtDateTime(n.at)}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Dropdown>
  )
}

function ThemeMenu() {
  const { choice, resolved, setChoice } = useTheme()
  return (
    <Dropdown label="Theme" width="w-48" trigger={({ toggle, ...aria }) => (
      <IconButton label={`Theme: ${choice}`} onClick={toggle} {...aria}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span key={resolved} className="grid place-items-center" initial={{ rotate: -60, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 60, opacity: 0 }} transition={{ duration: 0.25 }}>
            {resolved === 'dark' ? <Moon size={19} aria-hidden="true" /> : <Sun size={19} aria-hidden="true" />}
          </motion.span>
        </AnimatePresence>
      </IconButton>
    )}>
      {({ close }) => (
        <>
          {[['light', 'Light', Sun], ['dark', 'Dark', Moon], ['system', 'System', Desktop]].map(([v, l, I]) => (
            <MenuItem key={v} icon={I} active={choice === v} onClick={() => { setChoice(v); close() }} hint={choice === v ? 'on' : undefined}>{l}</MenuItem>
          ))}
        </>
      )}
    </Dropdown>
  )
}

function ProfileMenu({ user, onLogout }) {
  const navigate = useNavigate()
  const initials = (user?.name || '?').split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()
  return (
    <Dropdown label="Account" width="w-64" trigger={({ toggle, ...aria }) => (
      <button type="button" onClick={toggle} {...aria}
              className="ml-1 grid h-9 w-9 place-items-center rounded-xl bg-brand-button caption-3 text-white transition-transform duration-300 ease-nv hover:scale-105 active:scale-95">
        {initials}
      </button>
    )}>
      {({ close }) => (
        <>
          <div className="px-3 py-2">
            <p className="body-5 text-ink">{user?.name}</p>
            <p className="truncate caption-5 text-ink-muted">{user?.email}</p>
          </div>
          <div className="my-1 h-px bg-line" />
          <MenuItem icon={User} onClick={() => { close(); navigate('/app/settings') }}>Account and settings</MenuItem>
          <MenuItem icon={SignOut} onClick={() => { close(); onLogout() }}>Log out</MenuItem>
        </>
      )}
    </Dropdown>
  )
}

export default function AppShell() {
  const { user, logout } = useAuth()
  const { busy, clear } = useCurrentAnalysis()
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [drawer, setDrawer] = useState(false)
  const [palette, setPalette] = useState(false)
  const location = useLocation()

  useEffect(() => {
    try { localStorage.setItem(SIDEBAR_KEY, collapsed ? 'collapsed' : 'open') } catch { /* ignore */ }
  }, [collapsed])

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPalette((p) => !p)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const doLogout = () => {
    clear()
    logout()
  }

  return (
    <div className="min-h-screen ambient bg-fixed lg:flex">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:text-ink">
        Skip to content
      </a>

      {/* desktop sidebar */}
      <aside className={`sticky top-0 z-40 hidden h-screen shrink-0 flex-col border-r border-line bg-sidebar/80 px-3 py-4 backdrop-blur-xl transition-[width] duration-500 ease-nv lg:flex ${collapsed ? 'w-20' : 'w-68'}`}>
        <div className={`flex h-10 items-center ${collapsed ? 'justify-center' : 'px-2'}`}>
          {collapsed ? <Mark animated size={32} /> : <Logo to="/app" />}
        </div>
        <SidebarBody collapsed={collapsed} running={busy} />
        <button type="button" onClick={() => setCollapsed((c) => !c)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                className={`mt-2 flex h-9 items-center gap-3 rounded-xl px-3 caption-2 text-ink-muted transition-colors duration-300 ease-nv hover:bg-raised hover:text-ink ${collapsed ? 'justify-center' : ''}`}>
          {collapsed ? <CaretDoubleRight size={16} aria-hidden="true" /> : <><CaretDoubleLeft size={16} aria-hidden="true" /> Collapse</>}
        </button>
      </aside>

      {/* mobile drawer */}
      <AnimatePresence>
        {drawer && (
          <motion.div className="fixed inset-0 z-50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <button type="button" aria-label="Close menu" className="absolute inset-0 bg-page/70 backdrop-blur-sm" onClick={() => setDrawer(false)} />
            <motion.aside className="absolute inset-y-0 left-0 flex w-[min(300px,86vw)] flex-col border-r border-line glass-strong px-3 py-4 shadow-float"
                          initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }} transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}>
              <div className="flex items-center justify-between px-2">
                <Logo to="/app" />
                <IconButton label="Close menu" onClick={() => setDrawer(false)}><X size={18} aria-hidden="true" /></IconButton>
              </div>
              <SidebarBody collapsed={false} running={busy} onNavigate={() => setDrawer(false)} />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 border-b border-line glass">
          <div className="mx-auto flex h-16 w-full max-w-[1600px] items-center gap-2 px-4 sm:gap-3 sm:px-6 lg:px-8">
            <IconButton label="Open menu" onClick={() => setDrawer(true)} className="lg:hidden"><List size={20} aria-hidden="true" /></IconButton>
            <div className="min-w-0">
              <p className="hidden caption-5 text-ink-muted sm:block">NeuralVest</p>
              <h2 className="truncate title-3 text-ink">{titleFor(location.pathname)}</h2>
            </div>
            <button type="button" onClick={() => setPalette(true)} aria-label="Search stocks and pages"
                    className="ml-auto flex h-10 items-center gap-2 rounded-xl border border-line bg-surface px-3 caption-2 text-ink-muted transition-colors duration-300 ease-nv hover:border-line-strong hover:text-ink md:w-72">
              <MagnifyingGlass size={16} aria-hidden="true" />
              <span className="hidden flex-1 text-left md:inline">Search stocks and pages</span>
              <kbd className="hidden rounded-md border border-line bg-raised px-1.5 figure caption-5 text-ink-muted md:inline">Ctrl K</kbd>
            </button>
            <div className="flex items-center gap-1">
              <Notifications />
              <ThemeMenu />
              <ProfileMenu user={user} onLogout={doLogout} />
            </div>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Suspense fallback={<PageSkeleton />}>
            <PageTransition routeKey={location.pathname}>
              <Outlet />
            </PageTransition>
          </Suspense>
        </main>
        <AppFooter />
      </div>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  )
}
