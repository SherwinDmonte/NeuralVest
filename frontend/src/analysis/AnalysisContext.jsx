// The analysis currently running (or last finished), shared by the Stock Analysis page, the
// Agent Monitoring page and the dashboard, so switching pages never loses a running job.
// Its id is kept in sessionStorage, so a page reload reopens it (and keeps polling if it is
// still running) instead of showing an empty page.
import { createContext, useContext, useEffect, useRef } from 'react'
import { useAnalysis } from '../hooks/useAnalysis'

const AnalysisContext = createContext(null)
const KEY = 'nv.analysis'

const store = {
  get() {
    try { return sessionStorage.getItem(KEY) } catch { return null }
  },
  set(id) {
    try { if (id) sessionStorage.setItem(KEY, id); else sessionStorage.removeItem(KEY) } catch { /* ignore */ }
  },
}

export function AnalysisProvider({ children }) {
  const analysis = useAnalysis()
  const { requestId, open } = analysis
  const restored = useRef(false)

  useEffect(() => {
    if (restored.current) return
    restored.current = true
    const saved = store.get()
    // A page can also name an analysis in its URL (?request=); that one wins.
    if (saved && !new URLSearchParams(window.location.search).get('request')) open(saved)
  }, [open])

  useEffect(() => {
    if (restored.current) store.set(requestId)
  }, [requestId])

  return <AnalysisContext.Provider value={analysis}>{children}</AnalysisContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useCurrentAnalysis = () => useContext(AnalysisContext)
