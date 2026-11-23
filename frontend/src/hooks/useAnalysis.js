// Runs an analysis: start it, poll its status every 2 s, then load the results.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  errorMessage,
  getAnalysisResult,
  getAnalysisStatus,
  getIndicators,
  rerunAnalysis,
  startAnalysis,
} from '../services/api'

const POLL_MS = 2000
const TERMINAL = ['completed', 'partial', 'failed', 'interrupted']

export function useAnalysis() {
  const [requestId, setRequestId] = useState(null)
  const [status, setStatus] = useState(null) // latest /status payload
  const [result, setResult] = useState(null) // /analysis/{id}
  const [indicators, setIndicators] = useState(null) // /stocks/{symbol}/indicators
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const timer = useRef(null)

  const stopPolling = () => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = null
  }

  const loadResults = useCallback(async (id, symbol) => {
    try {
      const [res, ind] = await Promise.all([
        getAnalysisResult(id),
        getIndicators(symbol).catch(() => null), // charts are optional; the report still shows
      ])
      setResult(res)
      setIndicators(ind)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }, [])

  const poll = useCallback(
    async function pollOnce(id) {
      try {
        const s = await getAnalysisStatus(id)
        setStatus(s)
        if (TERMINAL.includes(s.status)) {
          // Load results for every end state: even a failed run has errors worth showing.
          await loadResults(id, s.symbols[0])
          return
        }
        timer.current = setTimeout(() => pollOnce(id), POLL_MS)
      } catch (err) {
        setError(errorMessage(err))
        setBusy(false)
      }
    },
    [loadResults],
  )

  const begin = useCallback(
    async (startFn) => {
      stopPolling()
      setError(null)
      setResult(null)
      setIndicators(null)
      setStatus(null)
      setBusy(true)
      try {
        const job = await startFn()
        setRequestId(job.request_id)
        setStatus({ status: job.status, symbols: job.symbols, agents: {} })
        poll(job.request_id)
      } catch (err) {
        setError(errorMessage(err))
        setBusy(false)
      }
    },
    [poll],
  )

  const run = useCallback(
    (symbols, includeGdelt, portfolio = null) => begin(() => startAnalysis(symbols, includeGdelt, portfolio)),
    [begin],
  )
  // Charts for another stock of a multi-stock analysis (the first one is loaded automatically).
  const showIndicators = useCallback(async (symbol) => {
    setIndicators(null)
    setIndicators(await getIndicators(symbol).catch(() => null))
  }, [])
  const rerun = useCallback(() => requestId && begin(() => rerunAnalysis(requestId)), [begin, requestId])

  useEffect(() => stopPolling, [])

  return { requestId, status, result, indicators, error, busy, run, rerun, showIndicators }
}
