// The user's watchlist, stored on their account (GET/PUT /auth/me/watchlist). Shared through a
// context so the dashboard and the watch buttons always agree.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { errorMessage, getWatchlist, putWatchlist } from '../services/api'

const WatchlistContext = createContext(null)

export function WatchlistProvider({ children }) {
  const [symbols, setSymbols] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getWatchlist()
      .then((r) => setSymbols(r.symbols))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  const save = useCallback(async (next) => {
    setSaving(true)
    setError(null)
    try {
      const r = await putWatchlist(next)
      setSymbols(r.symbols)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }, [])

  const toggle = useCallback(
    (symbol) => save(symbols.includes(symbol) ? symbols.filter((s) => s !== symbol) : [symbol, ...symbols]),
    [save, symbols],
  )

  const value = useMemo(() => ({ symbols, loading, saving, error, toggle, save }), [symbols, loading, saving, error, toggle, save])
  return <WatchlistContext.Provider value={value}>{children}</WatchlistContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useWatchlist = () => useContext(WatchlistContext)
