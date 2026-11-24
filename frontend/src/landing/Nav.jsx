// Landing navigation: a floating bar, a full height menu on phones and a thin reading progress
// line along the top edge of the window.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { List, Moon, Sun, X } from '@phosphor-icons/react'
import { useTheme } from '../theme/ThemeContext'
import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/ui'
import { Logo } from '../components/Logo'
import { CTA, LINKS } from './content'
import { useScrollProgress } from './hooks'

function ThemeToggle() {
  const { resolved, toggle } = useTheme()
  return (
    <button type="button" onClick={toggle} aria-label={`Switch to ${resolved === 'dark' ? 'light' : 'dark'} theme`}
            className="grid h-9 w-9 place-items-center rounded-xl text-ink-secondary transition-colors duration-300 ease-nv hover:bg-raised hover:text-ink">
      {resolved === 'dark' ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
    </button>
  )
}

export default function Nav() {
  const [open, setOpen] = useState(false)
  const { user } = useAuth()
  const progress = useScrollProgress()
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])
  const primary = user ? { to: '/app', label: 'Open the app' } : { to: '/register', label: CTA }

  return (
    <>
      <div ref={progress} className="fixed inset-x-0 top-0 z-50 h-0.5 origin-left scale-x-0 bg-accent" aria-hidden="true" />
      <header className="fixed inset-x-0 top-4 z-40 flex justify-center px-4">
        <nav aria-label="Main" className="flex w-full max-w-3xl items-center justify-between gap-4 rounded-2xl border border-line glass py-2 pl-4 pr-2 shadow-card md:w-fit md:max-w-none">
          <Logo />
          <ul className="hidden items-center gap-1 md:flex">
            {LINKS.map((l) => (
              <li key={l.href}>
                <a href={l.href} className="rounded-lg px-3 py-2 body-5 text-ink-secondary transition-colors duration-300 ease-nv hover:text-ink">{l.label}</a>
              </li>
            ))}
          </ul>
          <div className="hidden items-center gap-1 md:flex">
            {!user && <Link to="/login" className="rounded-lg px-3 py-2 body-5 text-ink-secondary transition-colors duration-300 ease-nv hover:text-ink">Log in</Link>}
            <ThemeToggle />
            <Button to={primary.to} size="sm">{primary.label}</Button>
          </div>
          <div className="flex items-center gap-1 md:hidden">
            <ThemeToggle />
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              aria-controls="landing-menu"
              aria-label={open ? 'Close menu' : 'Open menu'}
              className="relative grid h-10 w-10 place-items-center rounded-lg text-ink transition-colors duration-300 ease-nv hover:bg-raised"
            >
              <List size={20} className={`absolute transition-[transform,opacity] duration-500 ease-nv ${open ? 'rotate-90 opacity-0' : 'opacity-100'}`} aria-hidden="true" />
              <X size={20} className={`absolute transition-[transform,opacity] duration-500 ease-nv ${open ? 'opacity-100' : '-rotate-90 opacity-0'}`} aria-hidden="true" />
            </button>
          </div>
        </nav>
      </header>
      <div
        id="landing-menu"
        inert={!open}
        className={`fixed inset-0 z-30 flex flex-col bg-page/95 px-6 pb-8 pt-24 backdrop-blur-xl transition-opacity duration-500 ease-nv md:hidden ${open ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
      >
        <ul className="space-y-2">
          {[...LINKS, ...(user ? [] : [{ to: '/login', label: 'Log in' }])].map((l, i) => {
            const cls = `block py-2 heading-5 text-ink transition-[transform,opacity] duration-500 ease-nv ${open ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'}`
            const style = { transitionDelay: open ? `${Math.min(i * 60, 400)}ms` : '0ms' }
            return (
              <li key={l.label}>
                {l.to ? <Link to={l.to} className={cls} style={style}>{l.label}</Link>
                  : <a href={l.href} onClick={() => setOpen(false)} className={cls} style={style}>{l.label}</a>}
              </li>
            )
          })}
        </ul>
        <Button to={primary.to} className="mt-auto w-full">{primary.label}</Button>
      </div>
    </>
  )
}
