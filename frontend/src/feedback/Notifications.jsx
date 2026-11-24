// Notifications and toasts (Phase 12B). Only the user's own events are recorded (an analysis
// finished, a PDF downloaded, the watchlist changed). There is no market feed, so nothing here
// claims to be market news. Kept for this browser session.
import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { CheckCircle, Info, WarningCircle, X } from '@phosphor-icons/react'
import { Link } from 'react-router-dom'

const NotificationsContext = createContext(null)
const ICON = { good: CheckCircle, critical: WarningCircle, info: Info }
const TONE = { good: 'text-good', critical: 'text-critical', info: 'text-accent-ink' }
let nextId = 1

export function NotificationsProvider({ children }) {
  const [items, setItems] = useState([])
  const [toasts, setToasts] = useState([])
  const [lastSeen, setLastSeen] = useState(0)
  const timers = useRef({})

  const dismiss = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id))
    clearTimeout(timers.current[id])
  }, [])

  const notify = useCallback((n) => {
    const item = { id: nextId++, at: new Date().toISOString(), tone: 'info', ...n }
    setItems((list) => [item, ...list].slice(0, 30))
    if (n.toast !== false) {
      setToasts((t) => [...t.slice(-2), item])
      timers.current[item.id] = setTimeout(() => dismiss(item.id), 5500)
    }
  }, [dismiss])

  const markRead = useCallback(() => setLastSeen(nextId - 1), [])
  const unread = items.filter((i) => i.id > lastSeen).length
  const value = useMemo(() => ({ items, unread, notify, markRead, clear: () => setItems([]) }), [items, unread, notify, markRead])

  return (
    <NotificationsContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(380px,calc(100vw-32px))] flex-col gap-2" aria-live="polite">
        <AnimatePresence initial={false}>
          {toasts.map((t) => {
            const Icon = ICON[t.tone] || Info
            return (
              <motion.div key={t.id} layout
                          initial={{ opacity: 0, y: 16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, x: 24, transition: { duration: 0.2 } }}
                          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                          className="pointer-events-auto relative overflow-hidden rounded-2xl border border-line-strong glass-strong p-4 shadow-float">
                <span className="absolute inset-y-0 left-0 w-1 bg-brand" aria-hidden="true" />
                <div className="flex items-start gap-3">
                  <Icon size={18} weight="fill" className={`mt-0.5 shrink-0 ${TONE[t.tone]}`} aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="body-5 text-ink">{t.title}</p>
                    {t.body && <p className="mt-1 caption-2 text-ink-secondary">{t.body}</p>}
                    {t.link && <Link to={t.link.to} onClick={() => dismiss(t.id)} className="mt-2 inline-block caption-1 text-accent-ink hover:underline">{t.link.label}</Link>}
                  </div>
                  <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss"
                          className="rounded-lg p-1 text-ink-muted transition-colors duration-300 ease-nv hover:bg-raised hover:text-ink">
                    <X size={14} aria-hidden="true" />
                  </button>
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </NotificationsContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useNotifications = () => useContext(NotificationsContext)
