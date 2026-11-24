// Theme (Phase 12B): "dark", "light" or "system". The choice is saved in localStorage; the
// resolved theme is the data-theme attribute on <html> (set before first paint by index.html).
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const KEY = 'nv.theme'
const ThemeContext = createContext(null)
const media = () => window.matchMedia('(prefers-color-scheme: light)')

function readChoice() {
  try {
    const v = localStorage.getItem(KEY)
    return ['dark', 'light', 'system'].includes(v) ? v : 'system'
  } catch {
    return 'system'
  }
}

const resolve = (choice) => (choice === 'system' ? (media().matches ? 'light' : 'dark') : choice)

export function ThemeProvider({ children }) {
  const [choice, setChoiceState] = useState(readChoice)
  const [resolved, setResolved] = useState(() => document.documentElement.dataset.theme || resolve(readChoice()))

  const apply = useCallback((next, animate) => {
    const root = document.documentElement
    if (animate && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      root.classList.add('theme-switching')
      setTimeout(() => root.classList.remove('theme-switching'), 450)
    }
    root.dataset.theme = next
    document.querySelector('meta[name=theme-color]')?.setAttribute('content', next === 'light' ? '#f4f7fc' : '#080d18')
    setResolved(next)
  }, [])

  const setChoice = useCallback((next) => {
    try { localStorage.setItem(KEY, next) } catch { /* private mode: still works for this visit */ }
    setChoiceState(next)
    apply(resolve(next), true)
  }, [apply])

  // Follow the operating system while the choice is "system".
  useEffect(() => {
    if (choice !== 'system') return undefined
    const m = media()
    const onChange = () => apply(m.matches ? 'light' : 'dark', true)
    m.addEventListener('change', onChange)
    return () => m.removeEventListener('change', onChange)
  }, [choice, apply])

  const toggle = useCallback(() => setChoice(resolved === 'dark' ? 'light' : 'dark'), [resolved, setChoice])
  const value = useMemo(() => ({ choice, resolved, setChoice, toggle }), [choice, resolved, setChoice, toggle])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useTheme = () => useContext(ThemeContext)
