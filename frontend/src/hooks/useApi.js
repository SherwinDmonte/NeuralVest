// Load data from the API with loading/error state. With a `key`, results are kept in memory for
// `ttl` ms and shared by every component asking for the same key (the top bar, the overview and
// the market page reuse one request). In-flight requests are shared too.
import { useCallback, useEffect, useState } from 'react'
import { errorMessage } from '../services/api'

const cache = new Map() // key -> { at, data }
const inflight = new Map() // key -> promise

function load(key, fn, ttl, force) {
  if (key && !force) {
    const hit = cache.get(key)
    if (hit && Date.now() - hit.at < ttl) return Promise.resolve(hit.data)
    if (inflight.has(key)) return inflight.get(key)
  }
  const p = fn().then((data) => {
    if (key) cache.set(key, { at: Date.now(), data })
    return data
  })
  if (key) {
    inflight.set(key, p)
    p.finally(() => inflight.delete(key))
  }
  return p
}

export function useApi(fn, deps = [], { key = null, ttl = 5 * 60 * 1000, enabled = true } = {}) {
  const cached = key ? cache.get(key) : null
  const [state, setState] = useState({ data: cached?.data ?? null, error: null, loading: enabled && !cached })
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!enabled) return undefined
    let alive = true
    setState((s) => ({ ...s, loading: !(key && cache.get(key) && nonce === 0), error: null }))
    load(key, fn, ttl, nonce > 0)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((err) => alive && setState((s) => ({ data: s.data, error: errorMessage(err), loading: false })))
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { ...state, reload }
}
